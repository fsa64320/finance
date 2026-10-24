import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import TransactionForm from '../../src/components/TransactionForm'
import { ETF_ID, FUND_ID, account, instrument, transaction } from '../fixtures'

const onSubmit = vi.fn()
const onCancel = vi.fn()

const instruments = [
  instrument(),
  instrument({ id: FUND_ID, kind: 'FUND', name: 'Fonds Actions', isin: undefined }),
]

function setup(props: Partial<React.ComponentProps<typeof TransactionForm>> = {}) {
  render(
    <TransactionForm
      account={account({ type: 'CTO' })}
      instruments={instruments}
      holdings={{ [ETF_ID]: '10' }}
      onSubmit={onSubmit}
      onCancel={onCancel}
      {...props}
    />,
  )
  return userEvent.setup()
}

const typeOptions = () =>
  within(screen.getByLabelText("Type d'opération"))
    .getAllByRole('option')
    .map((option) => option.textContent)

beforeEach(() => {
  onSubmit.mockReset().mockResolvedValue({ warnings: [] })
  onCancel.mockReset()
})

describe('champs selon le type', () => {
  it('propose par défaut un versement avec montant et date', () => {
    setup()
    expect(screen.getByLabelText("Type d'opération")).toHaveValue('DEPOSIT')
    expect(screen.getByLabelText('Montant (EUR)')).toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(screen.queryByLabelText('Quantité')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Actif')).not.toBeInTheDocument()
  })

  it('affiche actif, quantité, prix et frais pour un achat, sans montant libre', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'BUY')
    for (const label of ['Actif', 'Quantité', 'Prix unitaire (EUR)', 'Frais (EUR)']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
    expect(screen.queryByLabelText('Montant (EUR)')).not.toBeInTheDocument()
  })

  it('demande un actif pour un dividende', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'DIVIDEND')
    expect(screen.getByLabelText('Actif')).toBeInTheDocument()
    expect(screen.getByLabelText('Montant (EUR)')).toBeInTheDocument()
  })

  it("réserve l'abondement au PEE", () => {
    setup({ account: account({ type: 'PEE' }) })
    expect(typeOptions()).toContain('Abondement')
  })

  it.each(['PEA', 'CTO', 'ASSURANCE_VIE', 'LIVRET_A'] as const)(
    "n'offre pas l'abondement sur un compte %s",
    (type) => {
      setup({ account: account({ type }) })
      expect(typeOptions()).not.toContain('Abondement')
    },
  )

  it("n'offre ni achat ni vente sur un Livret A", () => {
    setup({ account: account({ type: 'LIVRET_A' }) })
    expect(typeOptions()).not.toContain('Achat')
    expect(typeOptions()).not.toContain('Vente')
  })

  it('propose une date de déblocage pour un versement sur un PEE seulement', () => {
    setup({ account: account({ type: 'PEE' }) })
    expect(screen.getByLabelText('Date de déblocage')).toBeInTheDocument()
  })

  it("n'affiche pas de date de déblocage hors PEE", () => {
    setup({ account: account({ type: 'PEA' }) })
    expect(screen.queryByLabelText('Date de déblocage')).not.toBeInTheDocument()
  })
})

describe('envoi', () => {
  it('envoie un versement avec des décimaux normalisés', async () => {
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '1 000,50')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0]?.[0]).toEqual({
      account_id: account().id,
      type: 'DEPOSIT',
      trade_date: '2026-01-05',
      amount: '1000.50',
      currency: 'EUR',
    })
  })

  it('envoie un achat avec actif, quantité, prix et frais', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'BUY')
    await user.type(screen.getByLabelText('Date'), '2026-01-06')
    await user.selectOptions(screen.getByLabelText('Actif'), ETF_ID)
    await user.type(screen.getByLabelText('Quantité'), '10')
    await user.type(screen.getByLabelText('Prix unitaire (EUR)'), '90')
    await user.type(screen.getByLabelText('Frais (EUR)'), '1,99')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0]?.[0]).toEqual({
      account_id: account().id,
      type: 'BUY',
      trade_date: '2026-01-06',
      instrument_id: ETF_ID,
      quantity: '10',
      unit_price: '90',
      fees: '1.99',
      currency: 'EUR',
    })
  })

  it('envoie la date de déblocage et le libellé quand ils sont saisis', async () => {
    const user = setup({ account: account({ type: 'PEE' }) })
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '500')
    await user.type(screen.getByLabelText('Date de déblocage'), '2031-01-05')
    await user.type(screen.getByLabelText('Libellé'), 'Participation')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0]?.[0]).toMatchObject({
      unlock_date: '2031-01-05',
      label: 'Participation',
    })
  })
})

describe('validation locale', () => {
  async function submitWith(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
  }

  it('exige une date', async () => {
    const user = setup()
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await submitWith(user)
    expect(await screen.findByText('La date est obligatoire.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuse un montant nul, négatif ou illisible', async () => {
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    for (const [typed, message] of [
      ['0', 'Le montant doit être strictement positif.'],
      ['-5', 'Le montant doit être strictement positif.'],
      ['abc', 'Saisissez un nombre, par exemple 1 250,50.'],
    ] as const) {
      const field = screen.getByLabelText('Montant (EUR)')
      await user.clear(field)
      await user.type(field, typed)
      await submitWith(user)
      expect(await screen.findByText(message)).toBeInTheDocument()
    }
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("refuse une date antérieure à l'ouverture du compte", async () => {
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2025-12-31')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await submitWith(user)
    expect(await screen.findByText(/précède l'ouverture du compte/)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('exige actif, quantité et prix pour un achat', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'BUY')
    await user.type(screen.getByLabelText('Date'), '2026-01-06')
    await submitWith(user)
    expect(await screen.findByText("Choisissez l'actif.")).toBeInTheDocument()
    expect(screen.getAllByText('La quantité doit être strictement positive.')).toHaveLength(1)
    expect(screen.getAllByText('Le prix doit être strictement positif.')).toHaveLength(1)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuse des frais négatifs', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'BUY')
    await user.type(screen.getByLabelText('Date'), '2026-01-06')
    await user.selectOptions(screen.getByLabelText('Actif'), ETF_ID)
    await user.type(screen.getByLabelText('Quantité'), '1')
    await user.type(screen.getByLabelText('Prix unitaire (EUR)'), '1')
    await user.type(screen.getByLabelText('Frais (EUR)'), '-1')
    await submitWith(user)
    expect(await screen.findByText('Les frais ne peuvent pas être négatifs.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('avertissements et erreurs du serveur', () => {
  async function fillSale(user: ReturnType<typeof userEvent.setup>, quantity: string) {
    await user.selectOptions(screen.getByLabelText("Type d'opération"), 'SELL')
    await user.type(screen.getByLabelText('Date'), '2026-02-01')
    await user.selectOptions(screen.getByLabelText('Actif'), ETF_ID)
    await user.type(screen.getByLabelText('Quantité'), quantity)
    await user.type(screen.getByLabelText('Prix unitaire (EUR)'), '95')
  }

  it('prévient sans bloquer quand la vente dépasse la quantité détenue', async () => {
    const user = setup()
    await fillSale(user, '12')
    expect(screen.getByRole('status')).toHaveTextContent(/dépasse la quantité détenue \(10\)/)
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
  })

  it('ne prévient pas quand la quantité vendue est détenue', async () => {
    const user = setup()
    await fillSale(user, '10')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('affiche les avertissements renvoyés après enregistrement', async () => {
    onSubmit.mockResolvedValue({
      warnings: ['Les liquidités du compte sont négatives à cette date.'],
    })
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /liquidités du compte sont négatives/,
    )
  })

  it('place la règle du serveur sous le bon champ', async () => {
    onSubmit.mockRejectedValue(
      new ApiError(422, 'validation_error', 'Données invalides', [
        { field: 'amount', message: 'Le montant doit être strictement positif.' },
      ]),
    )
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const field = await screen.findByLabelText('Montant (EUR)')
    await waitFor(() => expect(field).toHaveAccessibleDescription(/strictement positif/))
  })

  it('affiche une erreur générale quand le champ est inconnu du formulaire', async () => {
    onSubmit.mockRejectedValue(new ApiError(500, 'internal_error', 'Erreur interne'))
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Erreur interne')
  })
})

describe('modification et annulation', () => {
  it("préremplit l'opération à modifier", () => {
    setup({
      initial: transaction({
        type: 'BUY',
        instrument_id: ETF_ID,
        quantity: '10',
        unit_price: '90',
        fees: '1.99',
        cash_amount: '-901.99',
        trade_date: '2026-01-06',
      }),
    })
    expect(screen.getByLabelText("Type d'opération")).toHaveValue('BUY')
    expect(screen.getByLabelText('Date')).toHaveValue('2026-01-06')
    expect(screen.getByLabelText('Actif')).toHaveValue(ETF_ID)
    expect(screen.getByLabelText('Quantité')).toHaveValue('10')
    expect(screen.getByLabelText('Prix unitaire (EUR)')).toHaveValue('90')
    expect(screen.getByLabelText('Frais (EUR)')).toHaveValue('1.99')
    expect(screen.getByRole('button', { name: 'Enregistrer la modification' })).toBeInTheDocument()
  })

  it('préremplit le montant d’un versement en valeur positive', () => {
    setup({ initial: transaction({ type: 'WITHDRAWAL', cash_amount: '-250' }) })
    expect(screen.getByLabelText('Montant (EUR)')).toHaveValue('250')
  })

  it('annule la saisie', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('bloque le bouton pendant l’envoi', async () => {
    let release: (value: { warnings: string[] }) => void = () => {}
    onSubmit.mockReturnValue(new Promise((resolve) => (release = resolve)))
    const user = setup()
    await user.type(screen.getByLabelText('Date'), '2026-01-05')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByRole('button', { name: /Enregistrement/ })).toBeDisabled()
    release({ warnings: [] })
  })
})
