import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '../src/api/auth'
import App from '../src/App'

vi.mock('../src/api/auth')

afterEach(() => {
  vi.resetAllMocks()
})

describe('App', () => {
  it("propose de créer le mot de passe quand l'instance est vierge", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue('uninitialized')
    render(<App />)
    expect(await screen.findByRole('button', { name: /créer/i })).toBeInTheDocument()
  })

  it("demande le mot de passe quand l'instance est verrouillée", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue('locked')
    render(<App />)
    expect(await screen.findByRole('button', { name: /déverrouiller/i })).toBeInTheDocument()
  })

  it("affiche l'application quand la session est ouverte", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue('unlocked')
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Finance' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Tableau de bord' })).toBeInTheDocument()
  })

  it('rappelle que les valeurs sont indicatives', async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue('unlocked')
    render(<App />)
    expect(
      await screen.findByText(/ne constituent pas un conseil en investissement/i),
    ).toBeInTheDocument()
  })

  it('verrouille depuis le bouton Verrouiller', async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValueOnce('unlocked').mockResolvedValue('locked')
    vi.mocked(authApi.lockInstance).mockResolvedValue(undefined)
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /verrouiller/i }))
    await waitFor(() => expect(authApi.lockInstance).toHaveBeenCalledOnce())
    expect(await screen.findByRole('button', { name: /déverrouiller/i })).toBeInTheDocument()
  })

  it("signale une panne de l'API", async () => {
    vi.mocked(authApi.getAuthStatus).mockRejectedValue(new Error('réseau'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/impossible de joindre/i)
  })
})
