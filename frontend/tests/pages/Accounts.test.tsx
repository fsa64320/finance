import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import { ApiError } from '../../src/api/client'
import Accounts from '../../src/pages/Accounts'
import { LIVRET_ID, PEA_ID, account, summary } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/accounts')

const plain = (text: string) => text.replace(/\s/g, ' ')

beforeEach(() => {
  vi.mocked(accountsApi.listAccounts)
    .mockReset()
    .mockResolvedValue([
      summary(),
      summary({
        id: LIVRET_ID,
        type: 'LIVRET_A',
        name: 'Livret A',
        institution: 'Banque',
        value: '2500',
        estimated: true,
        settings: { deposit_cap: '22950' },
      }),
    ])
  vi.mocked(accountsApi.createAccount).mockReset().mockResolvedValue(account())
})

describe('liste des comptes', () => {
  it('affiche nom, type, établissement et valeur de chaque compte', async () => {
    renderWithProviders(<Accounts />)
    const table = await screen.findByRole('table', { name: 'Comptes' })
    const pea = within(table).getByRole('link', { name: 'PEA Courtier A' }).closest('tr')!
    expect(within(pea).getByText('Plan d’épargne en actions (PEA)')).toBeInTheDocument()
    expect(within(pea).getByText('Courtier A')).toBeInTheDocument()
    expect(plain(within(pea).getByText(/1 000,00/).textContent!)).toBe('1 000,00 €')
  })

  it('pointe vers le détail du compte', async () => {
    renderWithProviders(<Accounts />)
    const link = await screen.findByRole('link', { name: 'PEA Courtier A' })
    expect(link).toHaveAttribute('href', `/comptes/${PEA_ID}`)
  })

  it('signale les valeurs estimées', async () => {
    renderWithProviders(<Accounts />)
    const livret = (await screen.findByRole('link', { name: 'Livret A' })).closest('tr')!
    expect(within(livret).getByText('Estimé')).toBeInTheDocument()
    const pea = screen.getByRole('link', { name: 'PEA Courtier A' }).closest('tr')!
    expect(within(pea).queryByText('Estimé')).not.toBeInTheDocument()
  })

  it('invite à créer un premier compte quand il n’y en a pas', async () => {
    vi.mocked(accountsApi.listAccounts).mockResolvedValue([])
    renderWithProviders(<Accounts />)
    expect(await screen.findByText(/Aucun compte pour le moment/)).toBeInTheDocument()
  })

  it('charge d’abord les comptes ouverts, puis les comptes clos à la demande', async () => {
    renderWithProviders(<Accounts />)
    await screen.findByRole('table', { name: 'Comptes' })
    expect(vi.mocked(accountsApi.listAccounts).mock.calls[0]?.[0]).toMatchObject({
      includeClosed: false,
    })
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Afficher les comptes clos'))
    await waitFor(() =>
      expect(vi.mocked(accountsApi.listAccounts).mock.calls.at(-1)?.[0]).toMatchObject({
        includeClosed: true,
      }),
    )
  })

  it('marque un compte clos', async () => {
    vi.mocked(accountsApi.listAccounts).mockResolvedValue([
      summary({ closed_on: '2026-06-30', name: 'Ancien PEA' }),
    ])
    renderWithProviders(<Accounts />)
    const row = (await screen.findByRole('link', { name: 'Ancien PEA' })).closest('tr')!
    expect(within(row).getByText(/Clos le 30\/06\/2026/)).toBeInTheDocument()
  })

  it('signale une erreur de chargement', async () => {
    vi.mocked(accountsApi.listAccounts).mockRejectedValue(new Error('réseau'))
    renderWithProviders(<Accounts />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Impossible de charger/)
  })
})

describe('création d’un compte', () => {
  it('propose les cinq types de compte', async () => {
    renderWithProviders(<Accounts />)
    await screen.findByRole('table', { name: 'Comptes' })
    const options = within(screen.getByLabelText('Type de compte')).getAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual([
      'Plan d’épargne entreprise (PEE)',
      'Plan d’épargne en actions (PEA)',
      'Compte-titres ordinaire (CTO)',
      'Assurance-vie',
      'Livret A',
    ])
  })

  it.each([
    ['PEE', 'PEE'],
    ['PEA', 'PEA'],
    ['CTO', 'CTO'],
    ['ASSURANCE_VIE', 'Assurance-vie de Marie'],
    ['LIVRET_A', 'Livret A de Marie'],
  ] as const)('crée un compte %s', async (type, name) => {
    renderWithProviders(<Accounts />)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Comptes' })
    await user.selectOptions(screen.getByLabelText('Type de compte'), type)
    await user.type(screen.getByLabelText('Nom du compte'), name)
    await user.type(screen.getByLabelText('Établissement'), 'Banque X')
    await user.type(screen.getByLabelText("Date d'ouverture"), '2026-01-02')
    await user.click(screen.getByRole('button', { name: 'Créer le compte' }))
    await waitFor(() => expect(accountsApi.createAccount).toHaveBeenCalledOnce())
    expect(vi.mocked(accountsApi.createAccount).mock.calls[0]?.[0]).toEqual({
      type,
      name,
      institution: 'Banque X',
      opened_on: '2026-01-02',
    })
    await waitFor(() => expect(accountsApi.listAccounts).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText('Nom du compte')).toHaveValue('')
  })

  it("omet l'établissement quand il est vide", async () => {
    renderWithProviders(<Accounts />)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Comptes' })
    await user.type(screen.getByLabelText('Nom du compte'), 'Sans banque')
    await user.type(screen.getByLabelText("Date d'ouverture"), '2026-01-02')
    await user.click(screen.getByRole('button', { name: 'Créer le compte' }))
    await waitFor(() => expect(accountsApi.createAccount).toHaveBeenCalledOnce())
    expect(vi.mocked(accountsApi.createAccount).mock.calls[0]?.[0]).not.toHaveProperty(
      'institution',
    )
  })

  it('exige un nom et une date d’ouverture', async () => {
    renderWithProviders(<Accounts />)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Comptes' })
    await user.click(screen.getByRole('button', { name: 'Créer le compte' }))
    expect(await screen.findByText('Le nom du compte est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText("La date d'ouverture est obligatoire.")).toBeInTheDocument()
    expect(accountsApi.createAccount).not.toHaveBeenCalled()
  })

  it('signale un nom déjà pris', async () => {
    vi.mocked(accountsApi.createAccount).mockRejectedValue(
      new ApiError(409, 'conflict', 'Un compte ouvert porte déjà le nom « PEA ».'),
    )
    renderWithProviders(<Accounts />)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Comptes' })
    await user.type(screen.getByLabelText('Nom du compte'), 'PEA')
    await user.type(screen.getByLabelText("Date d'ouverture"), '2026-01-02')
    await user.click(screen.getByRole('button', { name: 'Créer le compte' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/porte déjà le nom/)
  })
})
