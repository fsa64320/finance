import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import ChangePasswordForm from '../../src/components/ChangePasswordForm'

const OLD = 'ancien-mot-de-passe-1'
const NEW = 'nouveau-mot-de-passe-2'

afterEach(() => {
  vi.useRealTimers()
})

async function fill(
  user: ReturnType<typeof userEvent.setup>,
  current = OLD,
  next = NEW,
  again = NEW,
) {
  if (current) await user.type(screen.getByLabelText('Mot de passe actuel'), current)
  await user.type(screen.getByLabelText('Nouveau mot de passe'), next)
  await user.type(screen.getByLabelText('Confirmer le nouveau mot de passe'), again)
  await user.click(screen.getByRole('button', { name: 'Changer le mot de passe' }))
}

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<ChangePasswordForm onSubmit={onSubmit} />)
  return onSubmit
}

describe('ChangePasswordForm', () => {
  it('utilise les bons attributs de saisie et rappelle les règles', () => {
    setup()
    expect(screen.getByLabelText('Mot de passe actuel')).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
    expect(screen.getByLabelText('Nouveau mot de passe')).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
    expect(screen.getByLabelText('Confirmer le nouveau mot de passe')).toHaveAttribute(
      'type',
      'password',
    )
    expect(screen.getByText(/entre 12 et 128 caractères/i)).toBeInTheDocument()
  })

  it('transmet les deux mots de passe', async () => {
    const onSubmit = setup()
    await fill(userEvent.setup())
    expect(onSubmit).toHaveBeenCalledWith(OLD, NEW)
  })

  it('confirme le changement et vide les champs', async () => {
    setup()
    await fill(userEvent.setup())
    expect(await screen.findByRole('status')).toHaveTextContent(/mot de passe changé/i)
    expect(screen.getByRole('status')).toHaveTextContent(/ancien/i)
    expect(screen.getByLabelText('Nouveau mot de passe')).toHaveValue('')
  })

  it('bloque un nouveau mot de passe trop court', async () => {
    const onSubmit = setup()
    await fill(userEvent.setup(), OLD, 'court', 'court')
    expect(await screen.findByRole('alert')).toHaveTextContent(/au moins 12 caractères/i)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('bloque une confirmation différente', async () => {
    const onSubmit = setup()
    await fill(userEvent.setup(), OLD, NEW, NEW + 'x')
    expect(await screen.findByRole('alert')).toHaveTextContent(/ne correspondent pas/i)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('bloque un nouveau mot de passe identique à l’actuel', async () => {
    const onSubmit = setup()
    await fill(userEvent.setup(), OLD, OLD, OLD)
    expect(await screen.findByRole('alert')).toHaveTextContent(/différer|différent/i)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('exige le mot de passe actuel', async () => {
    const onSubmit = setup()
    await fill(userEvent.setup(), '')
    expect(await screen.findByRole('alert')).toHaveTextContent(/mot de passe actuel/i)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('signale un mot de passe actuel incorrect sans rien changer', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(401, 'invalid_credentials', 'Mot de passe incorrect.'))
    setup(onSubmit)
    await fill(userEvent.setup())
    expect(await screen.findByRole('alert')).toHaveTextContent(/mot de passe actuel est incorrect/i)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('affiche la règle refusée par le serveur', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(422, 'validation_error', 'Données invalides', [
          { field: 'new_password', message: 'Ce mot de passe est trop courant.' },
        ]),
      )
    setup(onSubmit)
    await fill(userEvent.setup())
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce mot de passe est trop courant.')
  })

  it('décompte après trop d’essais et bloque le bouton', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(429, 'too_many_attempts', 'Trop d’essais', undefined, 3))
    render(<ChangePasswordForm onSubmit={onSubmit} />)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await fill(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(/3 secondes/i)
    expect(screen.getByRole('button', { name: 'Changer le mot de passe' })).toBeDisabled()
    // Une seconde à la fois : React ne programme le minuteur suivant qu'après le rendu.
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
    }
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Changer le mot de passe' })).toBeEnabled()
  })

  it('ne garde pas les mots de passe affichés après un échec', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(401, 'invalid_credentials', 'Mot de passe incorrect.'))
    setup(onSubmit)
    await fill(userEvent.setup())
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Mot de passe actuel')).toHaveValue('')
  })
})
