import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import { ApiError } from '../../src/api/client'
import * as instrumentsApi from '../../src/api/instruments'
import * as transactionsApi from '../../src/api/transactions'
import AccountDetail from '../../src/pages/AccountDetail'
import {
  ETF_ID,
  FUND_ID,
  LIVRET_ID,
  PEA_ID,
  account,
  detail,
  instrument,
  summary,
  transaction,
} from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/accounts')
vi.mock('../../src/api/instruments')
vi.mock('../../src/api/transactions')

const plain = (text: string | null) => (text ?? '').replace(/\s/g, ' ')
const TX_ID = transaction().id

function show(id: string = PEA_ID) {
  return renderWithProviders(<AccountDetail />, {
    route: `/comptes/${id}`,
    path: '/comptes/:accountId',
  })
}

beforeEach(() => {
  vi.mocked(accountsApi.getAccount).mockReset().mockResolvedValue(detail())
  vi.mocked(accountsApi.listAccounts)
    .mockReset()
    .mockResolvedValue([summary(), summary({ id: LIVRET_ID, type: 'LIVRET_A', name: 'Livret A' })])
  vi.mocked(accountsApi.patchAccount).mockReset().mockResolvedValue(account())
  vi.mocked(accountsApi.declareBalance)
    .mockReset()
    .mockResolvedValue({} as never)
  vi.mocked(instrumentsApi.listInstruments)
    .mockReset()
    .mockResolvedValue([
      instrument(),
      instrument({ id: FUND_ID, kind: 'EURO_FUND', name: 'Fonds en euros', isin: undefined }),
    ])
  vi.mocked(transactionsApi.listTransactions)
    .mockReset()
    .mockResolvedValue({
      items: [
        transaction(),
        transaction({
          id: '66666666-6666-4666-8666-666666666666',
          version: 2,
          type: 'BUY',
          instrument_id: ETF_ID,
          quantity: '10',
          unit_price: '90',
          fees: '1.99',
          cash_amount: '-901.99',
          trade_date: '2026-01-06',
        }),
      ],
      next_cursor: null,
    })
  vi.mocked(transactionsApi.createTransaction).mockReset().mockResolvedValue({
    transaction: transaction(),
    warnings: [],
  })
  vi.mocked(transactionsApi.updateTransaction).mockReset().mockResolvedValue({
    transaction: transaction(),
    warnings: [],
  })
  vi.mocked(transactionsApi.voidTransaction)
    .mockReset()
    .mockResolvedValue({
      transaction: transaction({ voided: true }),
      warnings: [],
    })
  vi.mocked(transactionsApi.createTransfer)
    .mockReset()
    .mockResolvedValue({} as never)
  vi.mocked(transactionsApi.getTransaction)
    .mockReset()
    .mockResolvedValue({
      current: transaction({ version: 2 }),
      versions: [
        transaction({ version: 1, quantity: '10' }),
        transaction({ version: 2, quantity: '12' }),
      ],
    })
})

describe('en-tête et valeur', () => {
  it('affiche le compte, sa valeur, sa trésorerie et le caractère estimé', async () => {
    show()
    expect(
      await screen.findByRole('heading', { level: 2, name: 'PEA Courtier A' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Plan d’épargne en actions (PEA)')).toBeInTheDocument()
    expect(plain(screen.getByTestId('account-value').textContent)).toBe('1 000,00 €')
    expect(plain(screen.getByTestId('account-cash').textContent)).toBe('98,01 €')
    expect(screen.getByText('Valeur estimée')).toBeInTheDocument()
  })

  it('interroge le compte demandé par l’adresse', async () => {
    show(PEA_ID)
    await screen.findByRole('heading', { level: 2, name: 'PEA Courtier A' })
    expect(vi.mocked(accountsApi.getAccount).mock.calls[0]?.[0]).toBe(PEA_ID)
  })

  it('signale un compte introuvable', async () => {
    vi.mocked(accountsApi.getAccount).mockRejectedValue(
      new ApiError(404, 'not_found', 'Compte introuvable.'),
    )
    show()
    expect(await screen.findByRole('alert')).toHaveTextContent('Compte introuvable')
    expect(screen.getByRole('link', { name: 'Retour aux comptes' })).toHaveAttribute(
      'href',
      '/comptes',
    )
  })

  it('liste les avertissements de valorisation', async () => {
    show()
    expect(await screen.findByText('Aucun prix connu.')).toBeInTheDocument()
  })
})

describe('positions', () => {
  it('montre actif, quantité, prix de revient unitaire et valeur', async () => {
    show()
    const table = await screen.findByRole('table', { name: 'Positions' })
    const row = within(table).getByText('ETF Monde').closest('tr')!
    expect(within(row).getByText('10')).toBeInTheDocument()
    expect(plain(within(row).getByText(/90,199/).textContent)).toBe('90,199 €')
    expect(plain(within(row).getByText(/901,99/).textContent)).toBe('901,99 €')
    expect(within(row).getByText('estimé')).toBeInTheDocument()
  })

  it('nomme la cause quand un prix est ancien', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        warnings: [
          { code: 'price_stale', instrument_id: ETF_ID, message: 'Prix ancien (du 10/01/2026).' },
        ],
      }),
    )
    show()
    const table = await screen.findByRole('table', { name: 'Positions' })
    const row = within(table).getByText('ETF Monde').closest('tr')!
    expect(within(row).getByText('prix ancien')).toBeInTheDocument()
  })

  it('montre le prix de souscription et l’écart d’une SCPI', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        positions: [
          {
            instrument_id: ETF_ID,
            kind: 'SCPI',
            quantity: '10',
            unit_cost: '251.2',
            total_cost: '2512',
            value: '2250',
            price: '225',
            price_date: '2026-01-20',
            estimated: false,
            subscription_price: '250',
          },
        ],
        warnings: [],
      }),
    )
    show()
    const table = await screen.findByRole('table', { name: 'Positions' })
    const row = within(table).getByText('ETF Monde').closest('tr')!
    expect(plain(row.textContent)).toContain('Souscription 250,00 €')
    expect(plain(row.textContent)).toMatch(/Écart [-−]262,00 €/)
  })

  it('indique une position qui ne peut pas être valorisée', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        positions: [
          {
            instrument_id: ETF_ID,
            quantity: '-2',
            unit_cost: null,
            value: null,
            estimated: true,
          },
        ],
      }),
    )
    show()
    const table = await screen.findByRole('table', { name: 'Positions' })
    expect(within(table).getByText('Non valorisée')).toBeInTheDocument()
  })

  it('dit quand il n’y a aucune position', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(detail({ positions: [], warnings: [] }))
    show()
    expect(await screen.findByText(/Aucune position/)).toBeInTheDocument()
  })
})

describe('plafonds et blocages', () => {
  it('montre le plafond du PEA avec une jauge', async () => {
    show()
    const gauge = await screen.findByRole('progressbar', { name: 'Plafond du PEA utilisé' })
    expect(gauge).toHaveAttribute('aria-valuenow', '1')
    expect(plain(screen.getByTestId('cap-text').textContent)).toBe(
      '1 000,00 € versés sur un plafond de 150 000,00 €',
    )
  })

  it('signale un plafond dépassé', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        deposit_cap_usage: { deposited: '160000', cap: '150000', remaining: '0', exceeded: true },
      }),
    )
    show()
    expect(await screen.findByText('Plafond dépassé')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })

  it('montre le solde et le plafond du Livret A', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        ...summary({ id: LIVRET_ID, type: 'LIVRET_A', name: 'Livret A' }),
        positions: [],
        warnings: [],
        cash: '3000',
        deposit_cap_usage: { deposited: '3000', cap: '22950', remaining: '19950', exceeded: false },
      }),
    )
    show(LIVRET_ID)
    expect(
      await screen.findByRole('progressbar', { name: 'Plafond du Livret A utilisé' }),
    ).toBeInTheDocument()
    expect(plain(screen.getByTestId('cap-text').textContent)).toBe(
      '3 000,00 € de solde sur un plafond de 22 950,00 €',
    )
  })

  it('montre les sommes bloquées d’un PEE', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        ...summary({ type: 'PEE', name: 'PEE' }),
        deposit_cap_usage: undefined,
        locked_amount: '1500',
        positions: [],
        warnings: [],
      }),
    )
    show()
    expect(plain((await screen.findByTestId('locked-amount')).textContent)).toBe('1 500,00 €')
  })

  it('n’affiche aucun plafond pour un compte-titres', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({ ...summary({ type: 'CTO', name: 'CTO' }), deposit_cap_usage: undefined }),
    )
    show()
    await screen.findByRole('heading', { level: 2, name: 'CTO' })
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})

describe('opérations', () => {
  it('liste les opérations du compte avec libellé, date et montant', async () => {
    show()
    const table = await screen.findByRole('table', { name: 'Opérations' })
    expect(vi.mocked(transactionsApi.listTransactions).mock.calls[0]?.[0]).toMatchObject({
      accountId: PEA_ID,
    })
    const deposit = within(table).getByText('Versement').closest('tr')!
    expect(within(deposit).getByText('05/01/2026')).toBeInTheDocument()
    expect(plain(within(deposit).getByText(/1\s000,00/).textContent)).toBe('1 000,00 €')
    const purchase = within(table).getByText('Achat').closest('tr')!
    expect(within(purchase).getByText('ETF Monde')).toBeInTheDocument()
    expect(within(purchase).getByText(/-901,99/)).toBeInTheDocument()
  })

  it('saisit une nouvelle opération puis recharge', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Nouvelle opération' }))
    await user.type(screen.getByLabelText('Date'), '2026-02-01')
    await user.type(screen.getByLabelText('Montant (EUR)'), '200')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(transactionsApi.createTransaction).toHaveBeenCalledOnce())
    expect(vi.mocked(transactionsApi.createTransaction).mock.calls[0]?.[0]).toMatchObject({
      account_id: PEA_ID,
      type: 'DEPOSIT',
      trade_date: '2026-02-01',
      amount: '200',
    })
    await waitFor(() => expect(accountsApi.getAccount).toHaveBeenCalledTimes(2))
    expect(transactionsApi.listTransactions).toHaveBeenCalledTimes(2)
  })

  it('passe les quantités détenues au formulaire pour prévenir d’une vente excédentaire', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Nouvelle opération' }))
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'SELL')
    await user.selectOptions(screen.getByLabelText('Actif'), ETF_ID)
    await user.type(screen.getByLabelText('Quantité'), '15')
    expect(screen.getByRole('status')).toHaveTextContent(/dépasse la quantité détenue \(10\)/)
  })

  it('modifie une opération existante', async () => {
    show()
    const user = userEvent.setup()
    const table = await screen.findByRole('table', { name: 'Opérations' })
    const row = within(table).getByText('Achat').closest('tr')!
    await user.click(within(row).getByRole('button', { name: 'Modifier' }))
    const quantity = screen.getByLabelText('Quantité')
    expect(quantity).toHaveValue('10')
    await user.clear(quantity)
    await user.type(quantity, '12')
    await user.click(screen.getByRole('button', { name: 'Enregistrer la modification' }))
    await waitFor(() => expect(transactionsApi.updateTransaction).toHaveBeenCalledOnce())
    const [id, input] = vi.mocked(transactionsApi.updateTransaction).mock.calls[0]!
    expect(id).toBe('66666666-6666-4666-8666-666666666666')
    expect(input).toMatchObject({ type: 'BUY', quantity: '12', unit_price: '90', fees: '1.99' })
  })

  it('annule une opération après confirmation', async () => {
    show()
    const user = userEvent.setup()
    const table = await screen.findByRole('table', { name: 'Opérations' })
    const row = within(table).getByText('Versement').closest('tr')!
    await user.click(within(row).getByRole('button', { name: 'Annuler l’opération' }))
    expect(transactionsApi.voidTransaction).not.toHaveBeenCalled()
    await user.click(within(row).getByRole('button', { name: 'Confirmer l’annulation' }))
    await waitFor(() => expect(transactionsApi.voidTransaction).toHaveBeenCalledWith(TX_ID))
    await waitFor(() => expect(accountsApi.getAccount).toHaveBeenCalledTimes(2))
  })

  it('affiche l’historique des modifications', async () => {
    show()
    const user = userEvent.setup()
    const table = await screen.findByRole('table', { name: 'Opérations' })
    const row = within(table).getByText('Versement').closest('tr')!
    await user.click(within(row).getByRole('button', { name: 'Historique' }))
    expect(
      await screen.findByRole('table', { name: 'Historique des modifications' }),
    ).toBeInTheDocument()
    expect(transactionsApi.getTransaction).toHaveBeenCalledWith(TX_ID)
  })

  it('désigne un virement et l’annule avec ses deux jambes', async () => {
    vi.mocked(transactionsApi.listTransactions).mockResolvedValue({
      items: [
        transaction({
          type: 'TRANSFER_OUT',
          cash_amount: '-500',
          transfer_group_id: '77777777-7777-4777-8777-777777777777',
        }),
      ],
      next_cursor: null,
    })
    show()
    const user = userEvent.setup()
    const table = await screen.findByRole('table', { name: 'Opérations' })
    const row = within(table).getByText('Virement sortant').closest('tr')!
    expect(within(row).queryByRole('button', { name: 'Modifier' })).not.toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: 'Annuler l’opération' }))
    expect(within(row).getByText(/les deux comptes/)).toBeInTheDocument()
  })

  it('dit quand il n’y a aucune opération', async () => {
    vi.mocked(transactionsApi.listTransactions).mockResolvedValue({ items: [], next_cursor: null })
    show()
    expect(await screen.findByText(/Aucune opération/)).toBeInTheDocument()
  })

  it('charge la page suivante quand il y en a une', async () => {
    vi.mocked(transactionsApi.listTransactions)
      .mockResolvedValueOnce({ items: [transaction()], next_cursor: 'suite' })
      .mockResolvedValueOnce({
        items: [
          transaction({ id: '88888888-8888-4888-8888-888888888888', trade_date: '2026-01-04' }),
        ],
        next_cursor: null,
      })
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Charger plus d’opérations' }))
    await waitFor(() => expect(screen.getAllByText('Versement')).toHaveLength(2))
    expect(vi.mocked(transactionsApi.listTransactions).mock.calls[1]?.[0]).toMatchObject({
      cursor: 'suite',
    })
  })
})

describe('virement', () => {
  it('enregistre un virement vers un autre compte ouvert', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Virement' }))
    await user.selectOptions(screen.getByLabelText('Compte destination'), LIVRET_ID)
    await user.type(screen.getByLabelText('Date'), '2026-03-01')
    await user.type(screen.getByLabelText('Montant (EUR)'), '500')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le virement' }))
    await waitFor(() => expect(transactionsApi.createTransfer).toHaveBeenCalledOnce())
    expect(vi.mocked(transactionsApi.createTransfer).mock.calls[0]?.[0]).toMatchObject({
      from_account_id: PEA_ID,
      to_account_id: LIVRET_ID,
      amount: '500',
    })
  })
})

describe('solde déclaré', () => {
  beforeEach(() => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(
      detail({
        ...summary({ type: 'ASSURANCE_VIE', name: 'Assurance-vie' }),
        positions: [],
        warnings: [],
      }),
    )
  })

  it('déclare le solde d’un fonds en euros', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Déclarer un solde' }))
    await user.selectOptions(screen.getByLabelText('Actif sans cours'), FUND_ID)
    await user.type(screen.getByLabelText('Date du solde'), '2026-01-01')
    await user.type(screen.getByLabelText('Solde (EUR)'), '5 000')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le solde' }))
    await waitFor(() => expect(accountsApi.declareBalance).toHaveBeenCalledOnce())
    expect(vi.mocked(accountsApi.declareBalance).mock.calls[0]?.[0]).toEqual({
      account_id: PEA_ID,
      instrument_id: FUND_ID,
      balance_date: '2026-01-01',
      amount: '5000',
      currency: 'EUR',
    })
    await waitFor(() => expect(accountsApi.getAccount).toHaveBeenCalledTimes(2))
  })

  it('n’offre pas la déclaration de solde sur un PEA', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(detail())
    show()
    await screen.findByRole('table', { name: 'Opérations' })
    expect(screen.queryByRole('button', { name: 'Déclarer un solde' })).not.toBeInTheDocument()
  })

  it('autorise un solde nul', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Déclarer un solde' }))
    await user.selectOptions(screen.getByLabelText('Actif sans cours'), FUND_ID)
    await user.type(screen.getByLabelText('Date du solde'), '2026-01-01')
    await user.type(screen.getByLabelText('Solde (EUR)'), '0')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le solde' }))
    await waitFor(() => expect(accountsApi.declareBalance).toHaveBeenCalledOnce())
  })

  it('refuse un solde négatif', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Déclarer un solde' }))
    await user.selectOptions(screen.getByLabelText('Actif sans cours'), FUND_ID)
    await user.type(screen.getByLabelText('Date du solde'), '2026-01-01')
    await user.type(screen.getByLabelText('Solde (EUR)'), '-5')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le solde' }))
    expect(await screen.findByText('Le solde ne peut pas être négatif.')).toBeInTheDocument()
    expect(accountsApi.declareBalance).not.toHaveBeenCalled()
  })
})

describe('clôture', () => {
  it('clôture le compte à la date du jour', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Clôturer le compte' }))
    await user.click(screen.getByRole('button', { name: 'Confirmer la clôture' }))
    await waitFor(() => expect(accountsApi.patchAccount).toHaveBeenCalledOnce())
    const [id, patch] = vi.mocked(accountsApi.patchAccount).mock.calls[0]!
    expect(id).toBe(PEA_ID)
    expect(patch.closed_on).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('rouvre un compte clos', async () => {
    vi.mocked(accountsApi.getAccount).mockResolvedValue(detail({ closed_on: '2026-06-30' }))
    show()
    const user = userEvent.setup()
    expect(await screen.findByText(/Clos le 30\/06\/2026/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Rouvrir le compte' }))
    await waitFor(() =>
      expect(accountsApi.patchAccount).toHaveBeenCalledWith(PEA_ID, { closed_on: null }),
    )
  })

  it('renomme le compte et change son établissement', async () => {
    show()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Opérations' })
    await user.click(screen.getByRole('button', { name: 'Renommer' }))
    const name = screen.getByLabelText('Nom du compte')
    await user.clear(name)
    await user.type(name, 'PEA Courtier B')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le nom' }))
    await waitFor(() =>
      expect(accountsApi.patchAccount).toHaveBeenCalledWith(PEA_ID, {
        name: 'PEA Courtier B',
        institution: 'Courtier A',
      }),
    )
  })
})
