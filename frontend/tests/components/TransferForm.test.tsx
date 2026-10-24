import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import TransferForm from '../../src/components/TransferForm'
import { LIVRET_ID, PEA_ID, account } from '../fixtures'

const onSubmit = vi.fn()
const onCancel = vi.fn()
const accounts = [
  account(),
  account({ id: LIVRET_ID, type: 'LIVRET_A', name: 'Livret A', institution: 'Banque' }),
]

function setup(fromAccountId: string = PEA_ID) {
  render(
    <TransferForm
      accounts={accounts}
      fromAccountId={fromAccountId}
      onSubmit={onSubmit}
      onCancel={onCancel}
    />,
  )
  return userEvent.setup()
}

beforeEach(() => {
  onSubmit.mockReset().mockResolvedValue({ warnings: [] })
  onCancel.mockReset()
})

describe('TransferForm', () => {
  it('présélectionne le compte source', () => {
    setup()
    expect(screen.getByLabelText('Compte source')).toHaveValue(PEA_ID)
  })

  it('envoie le virement avec un montant normalisé', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText('Compte destination'), LIVRET_ID)
    await user.type(screen.getByLabelText('Date'), '2026-03-01')
    await user.type(screen.getByLabelText('Montant (EUR)'), '500,25')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le virement' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0]?.[0]).toEqual({
      from_account_id: PEA_ID,
      to_account_id: LIVRET_ID,
      trade_date: '2026-03-01',
      amount: '500.25',
      currency: 'EUR',
    })
  })

  it('refuse deux comptes identiques', async () => {
    const user = setup()
    await user.selectOptions(screen.getByLabelText('Compte destination'), PEA_ID)
    await user.type(screen.getByLabelText('Date'), '2026-03-01')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le virement' }))
    expect(await screen.findByText('Choisissez deux comptes différents.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('exige une destination, une date et un montant positif', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: 'Enregistrer le virement' }))
    expect(await screen.findByText('Choisissez le compte destination.')).toBeInTheDocument()
    expect(screen.getByText('La date est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText('Le montant doit être strictement positif.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("affiche l'erreur du serveur", async () => {
    onSubmit.mockRejectedValue(
      new ApiError(422, 'validation_error', 'Données invalides', [
        {
          field: 'trade_date',
          message: "La date du virement précède l'ouverture d'un des comptes.",
        },
      ]),
    )
    const user = setup()
    await user.selectOptions(screen.getByLabelText('Compte destination'), LIVRET_ID)
    await user.type(screen.getByLabelText('Date'), '2026-03-01')
    await user.type(screen.getByLabelText('Montant (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer le virement' }))
    expect(await screen.findByText(/précède l'ouverture/)).toBeInTheDocument()
  })

  it('annule', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

describe('TransferForm avec un seul compte', () => {
  it('explique qu’il faut deux comptes', () => {
    render(
      <TransferForm
        accounts={[account()]}
        fromAccountId={PEA_ID}
        onSubmit={onSubmit}
        onCancel={onCancel}
      />,
    )
    expect(screen.getByText(/au moins deux comptes ouverts/i)).toBeInTheDocument()
  })
})
