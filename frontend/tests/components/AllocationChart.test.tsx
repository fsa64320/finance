import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import AllocationChart from '../../src/components/AllocationChart'
import { allocationBody } from '../fixtures'

const plain = (text: string | null) => (text ?? '').replace(/\s/g, ' ')

describe('AllocationChart', () => {
  it('liste chaque classe avec sa valeur et son poids', () => {
    render(<AllocationChart slices={allocationBody().slices} currency="EUR" />)
    const list = screen.getByRole('list', { name: 'Répartition par classe d’actifs' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(plain(rows[0]!.textContent)).toContain('Actions et ETF')
    expect(plain(rows[0]!.textContent)).toContain('901,99 €')
    expect(plain(rows[0]!.textContent)).toContain('10,61 %')
    expect(plain(rows[1]!.textContent)).toContain('Fonds en euros')
    expect(plain(rows[2]!.textContent)).toContain('Liquidités')
  })

  it('nomme les cinq classes en français', () => {
    const slices = [
      { asset_class: 'equities_etf' as const, value: '1', weight_percent: '20' },
      { asset_class: 'funds' as const, value: '1', weight_percent: '20' },
      { asset_class: 'scpi' as const, value: '1', weight_percent: '20' },
      { asset_class: 'euro_funds' as const, value: '1', weight_percent: '20' },
      { asset_class: 'cash' as const, value: '1', weight_percent: '20' },
    ]
    render(<AllocationChart slices={slices} currency="EUR" />)
    for (const label of ['Actions et ETF', 'Fonds', 'SCPI', 'Fonds en euros', 'Liquidités']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('décrit le graphique en texte', () => {
    render(<AllocationChart slices={allocationBody().slices} currency="EUR" />)
    expect(screen.getByRole('img', { name: /Répartition du patrimoine/ })).toBeInTheDocument()
  })

  it('explique qu’il n’y a rien à répartir', () => {
    render(<AllocationChart slices={[]} currency="EUR" />)
    expect(screen.getByText(/Rien à répartir pour le moment/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})
