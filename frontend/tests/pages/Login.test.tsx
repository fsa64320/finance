import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../../src/api/auth'
import { ApiError } from '../../src/api/client'
import Login from '../../src/pages/Login'

vi.mock('../../src/api/auth')

const VALID = 'tulipe-bleue-47-horizon'

afterEach(() => {
  vi.useRealTimers()
  vi.resetAllMocks()
})

describe('Login en création de mot de passe', () => {
  const onSuccess = vi.fn()

  beforeEach(() => {
    onSuccess.mockReset()
    render(<Login mode="setup" onSuccess={onSuccess} />)
  })

  it("avertit qu'un oubli rend les données irrécupérables et invite à exporter (FR-028)", () => {
    const note = screen.getByRole('note')
    expect(note).toHaveTextContent(/irrécupérables/i)
    expect(note).toHaveTextContent(/exportez/i)
  })

  it('affiche les règles du mot de passe', () => {
    expect(screen.getByText(/entre 12 et 128 caractères/i)).toBeInTheDocument()
  })

  it('utilise les bons attributs de saisie', () => {
    expect(screen.getByLabelText('Mot de passe')).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText('Confirmer le mot de passe')).toHaveAttribute('type', 'password')
  })

  it("bloque un mot de passe trop court sans appeler l'API", async () => {
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), 'court')
    await user.type(screen.getByLabelText('Confirmer le mot de passe'), 'court')
    await user.click(screen.getByRole('button', { name: /créer/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/au moins 12 caractères/i)
    expect(authApi.setupPassword).not.toHaveBeenCalled()
  })

  it('bloque une confirmation différente', async () => {
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.type(screen.getByLabelText('Confirmer le mot de passe'), VALID + 'x')
    await user.click(screen.getByRole('button', { name: /créer/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/ne correspondent pas/i)
    expect(authApi.setupPassword).not.toHaveBeenCalled()
  })

  it('crée le mot de passe puis prévient le parent', async () => {
    vi.mocked(authApi.setupPassword).mockResolvedValue(undefined)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.type(screen.getByLabelText('Confirmer le mot de passe'), VALID)
    await user.click(screen.getByRole('button', { name: /créer/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
    expect(authApi.setupPassword).toHaveBeenCalledWith(VALID)
  })

  it('affiche la règle renvoyée par le serveur pour un mot de passe courant', async () => {
    vi.mocked(authApi.setupPassword).mockRejectedValue(
      new ApiError(422, 'weak_password', 'Mot de passe refusé', [
        { field: 'password', message: 'Ce mot de passe est trop courant.' },
      ]),
    )
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), 'motdepasse123')
    await user.type(screen.getByLabelText('Confirmer le mot de passe'), 'motdepasse123')
    await user.click(screen.getByRole('button', { name: /créer/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce mot de passe est trop courant.')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})

describe('Login en déverrouillage', () => {
  const onSuccess = vi.fn()

  beforeEach(() => {
    onSuccess.mockReset()
  })

  it("demande un seul champ avec l'attribut current-password", () => {
    render(<Login mode="unlock" onSuccess={onSuccess} />)
    expect(screen.getByLabelText('Mot de passe')).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
    expect(screen.queryByLabelText('Confirmer le mot de passe')).not.toBeInTheDocument()
  })

  it('déverrouille puis prévient le parent', async () => {
    vi.mocked(authApi.unlockInstance).mockResolvedValue(undefined)
    render(<Login mode="unlock" onSuccess={onSuccess} />)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.click(screen.getByRole('button', { name: /déverrouiller/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
    expect(authApi.unlockInstance).toHaveBeenCalledWith(VALID)
  })

  it('signale un mot de passe incorrect', async () => {
    vi.mocked(authApi.unlockInstance).mockRejectedValue(
      new ApiError(401, 'invalid_credentials', 'Mot de passe incorrect.'),
    )
    render(<Login mode="unlock" onSuccess={onSuccess} />)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.click(screen.getByRole('button', { name: /déverrouiller/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/mot de passe incorrect/i)
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it("compte à rebours après trop d'essais et bloque le bouton", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(authApi.unlockInstance).mockRejectedValue(
      new ApiError(429, 'too_many_attempts', "Trop d'essais", undefined, 3),
    )
    render(<Login mode="unlock" onSuccess={onSuccess} />)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.click(screen.getByRole('button', { name: /déverrouiller/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/3 secondes/i)
    expect(screen.getByRole('button', { name: /déverrouiller/i })).toBeDisabled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByRole('alert')).toHaveTextContent(/2 secondes/i)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(screen.getByRole('button', { name: /déverrouiller/i })).toBeEnabled()
  })

  it('ne conserve pas le mot de passe affiché après un échec', async () => {
    vi.mocked(authApi.unlockInstance).mockRejectedValue(
      new ApiError(401, 'invalid_credentials', 'Mot de passe incorrect.'),
    )
    render(<Login mode="unlock" onSuccess={onSuccess} />)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mot de passe'), VALID)
    await user.click(screen.getByRole('button', { name: /déverrouiller/i }))
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Mot de passe')).toHaveValue('')
  })
})
