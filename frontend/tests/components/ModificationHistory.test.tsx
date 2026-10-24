import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ModificationHistory from '../../src/components/ModificationHistory'
import { ETF_ID, transaction } from '../fixtures'

const versions = [
  transaction({
    version: 1,
    type: 'BUY',
    instrument_id: ETF_ID,
    quantity: '10',
    unit_price: '90',
    cash_amount: '-901.99',
    created_at: '2026-01-06T10:00:00Z',
  }),
  transaction({
    version: 2,
    type: 'BUY',
    instrument_id: ETF_ID,
    quantity: '12',
    unit_price: '90',
    cash_amount: '-1081.99',
    created_at: '2026-01-07T09:30:00Z',
  }),
  transaction({ version: 3, voided: true, type: 'BUY', quantity: '12', cash_amount: '-1081.99' }),
]

describe('ModificationHistory', () => {
  it('liste chaque version, de la plus récente à la plus ancienne', () => {
    render(<ModificationHistory versions={versions} />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(within(rows[0]!).getByText('Version 3')).toBeInTheDocument()
    expect(within(rows[2]!).getByText('Version 1')).toBeInTheDocument()
  })

  it("montre ce qui a changé d'une version à l'autre", () => {
    render(<ModificationHistory versions={versions} />)
    const second = screen.getByText('Version 2').closest('tr')!
    expect(within(second).getByText('12')).toBeInTheDocument()
    expect(within(second).getByText(/1\s081,99/)).toBeInTheDocument()
    const first = screen.getByText('Version 1').closest('tr')!
    expect(within(first).getByText('10')).toBeInTheDocument()
  })

  it('signale la version qui annule l’opération', () => {
    render(<ModificationHistory versions={versions} />)
    const third = screen.getByText('Version 3').closest('tr')!
    expect(within(third).getByText('Annulée')).toBeInTheDocument()
  })

  it('indique la date de chaque version', () => {
    render(<ModificationHistory versions={versions} />)
    expect(screen.getByText(/06\/01\/2026/)).toBeInTheDocument()
    expect(screen.getByText(/07\/01\/2026/)).toBeInTheDocument()
  })

  it("explique qu'une opération sans modification n'a qu'une version", () => {
    render(<ModificationHistory versions={[versions[0]!]} />)
    expect(screen.getByText(/Aucune modification/)).toBeInTheDocument()
  })

  it('a un titre accessible', () => {
    render(<ModificationHistory versions={versions} />)
    expect(screen.getByRole('table', { name: 'Historique des modifications' })).toBeInTheDocument()
  })
})
