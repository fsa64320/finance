import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PriceEntryForm from '../../src/components/PriceEntryForm'
import { ETF_ID, instrument } from '../fixtures'

const SCPI = instrument({ id: 'scpi-1', kind: 'SCPI', name: 'SCPI Exemple', isin: undefined })
const FUND = instrument({ id: 'fund-1', kind: 'FUND', name: 'Fonds Exemple', isin: undefined })

function setup(item = instrument(), onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<PriceEntryForm instrument={item} onSubmit={onSubmit} onCancel={() => {}} />)
  return onSubmit
}

describe('actions et ETF', () => {
  it('saisit un cours à une date', async () => {
    const onSubmit = setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.type(screen.getByLabelText('Cours (EUR)'), '98,40')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onSubmit).toHaveBeenCalledWith([
      {
        instrument_id: ETF_ID,
        price_date: '2026-10-20',
        kind: 'MARKET',
        value: '98.40',
        currency: 'EUR',
      },
    ])
  })

  it('refuse un prix nul, illisible ou une date manquante', async () => {
    const onSubmit = setup()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('La date est obligatoire.')).toBeInTheDocument()
    expect(screen.getByText('Saisissez un prix.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.type(screen.getByLabelText('Cours (EUR)'), '0')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Le prix doit être strictement positif.')).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Cours (EUR)'))
    await user.type(screen.getByLabelText('Cours (EUR)'), 'abc')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText(/Saisissez un nombre/)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuse une date dans le futur', async () => {
    const onSubmit = setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2999-01-01')
    await user.type(screen.getByLabelText('Cours (EUR)'), '10')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('La date ne peut pas être dans le futur.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('fonds', () => {
  it('saisit une valeur liquidative', async () => {
    const onSubmit = setup(FUND)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.type(screen.getByLabelText('Valeur liquidative (EUR)'), '151,2')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onSubmit).toHaveBeenCalledWith([
      {
        instrument_id: 'fund-1',
        price_date: '2026-10-20',
        kind: 'NAV',
        value: '151.2',
        currency: 'EUR',
      },
    ])
  })
})

describe('SCPI', () => {
  it('propose un prix de souscription et un prix de retrait', () => {
    setup(SCPI)
    expect(screen.getByLabelText('Prix de souscription (EUR)')).toBeInTheDocument()
    expect(screen.getByLabelText('Prix de retrait (EUR)')).toBeInTheDocument()
    expect(screen.getByText(/écart initial/i)).toBeInTheDocument()
  })

  it('enregistre les deux prix à la même date', async () => {
    const onSubmit = setup(SCPI)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.type(screen.getByLabelText('Prix de souscription (EUR)'), '250')
    await user.type(screen.getByLabelText('Prix de retrait (EUR)'), '225,50')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onSubmit).toHaveBeenCalledWith([
      {
        instrument_id: 'scpi-1',
        price_date: '2026-10-20',
        kind: 'SUBSCRIPTION',
        value: '250',
        currency: 'EUR',
      },
      {
        instrument_id: 'scpi-1',
        price_date: '2026-10-20',
        kind: 'REDEMPTION',
        value: '225.50',
        currency: 'EUR',
      },
    ])
  })

  it('accepte un seul des deux prix mais pas aucun', async () => {
    const onSubmit = setup(SCPI)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Saisissez au moins un des deux prix.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Prix de retrait (EUR)'), '225')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onSubmit).toHaveBeenCalledWith([
      {
        instrument_id: 'scpi-1',
        price_date: '2026-10-20',
        kind: 'REDEMPTION',
        value: '225',
        currency: 'EUR',
      },
    ])
  })
})

describe('erreurs du serveur', () => {
  it('place l’erreur du serveur sur le champ concerné', async () => {
    const { ApiError } = await import('../../src/api/client')
    const onSubmit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(422, 'validation_error', 'Données invalides', [
          { field: 'value', message: 'Le prix doit être strictement positif.' },
        ]),
      )
    setup(instrument(), onSubmit)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Date du prix'), '2026-10-20')
    await user.type(screen.getByLabelText('Cours (EUR)'), '5')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Le prix doit être strictement positif.')).toBeInTheDocument()
  })
})
