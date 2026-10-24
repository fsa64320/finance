import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import AccountList from '../../src/components/AccountList'
import EmptyState from '../../src/components/EmptyState'
import { LIVRET_ID, PEA_ID, summary } from '../fixtures'

const plain = (text: string | null) => (text ?? '').replace(/\s/g, ' ')

const accounts = [
  summary(),
  summary({
    id: LIVRET_ID,
    type: 'LIVRET_A',
    name: 'Livret A',
    institution: 'Banque',
    value: '2500',
    estimated: true,
  }),
  summary({
    id: '99999999-9999-4999-8999-999999999999',
    name: 'Ancien PEA',
    closed_on: '2026-06-30',
  }),
]

function renderList(props: Partial<React.ComponentProps<typeof AccountList>> = {}) {
  return render(
    <MemoryRouter>
      <AccountList accounts={accounts} {...props} />
    </MemoryRouter>,
  )
}

describe('AccountList', () => {
  it('montre type, établissement et valeur de chaque compte', () => {
    renderList()
    const row = screen.getByRole('link', { name: 'PEA Courtier A' }).closest('tr')!
    expect(within(row).getByText('Plan d’épargne en actions (PEA)')).toBeInTheDocument()
    expect(within(row).getByText('Courtier A')).toBeInTheDocument()
    expect(plain(within(row).getByText(/1\s000,00/).textContent)).toBe('1 000,00 €')
  })

  it('pointe vers le détail du compte', () => {
    renderList()
    expect(screen.getByRole('link', { name: 'PEA Courtier A' })).toHaveAttribute(
      'href',
      `/comptes/${PEA_ID}`,
    )
  })

  it('met la pastille « Estimé » sur les valeurs estimées seulement', () => {
    renderList()
    expect(
      within(screen.getByRole('link', { name: 'Livret A' }).closest('tr')!).getByText('Estimé'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('link', { name: 'PEA Courtier A' }).closest('tr')!).queryByText(
        'Estimé',
      ),
    ).not.toBeInTheDocument()
  })

  it('n’affiche la colonne Statut qu’à la demande', () => {
    renderList()
    expect(screen.queryByRole('columnheader', { name: 'Statut' })).not.toBeInTheDocument()
    renderList({ showStatus: true })
    expect(screen.getByRole('columnheader', { name: 'Statut' })).toBeInTheDocument()
    expect(screen.getByText(/Clos le 30\/06\/2026/)).toBeInTheDocument()
  })

  it('porte un nom accessible modifiable', () => {
    renderList({ label: 'Mes comptes' })
    expect(screen.getByRole('table', { name: 'Mes comptes' })).toBeInTheDocument()
  })

  it('met le tableau dans un conteneur qui défile au lieu de déborder de la page', () => {
    const { container } = renderList()
    const table = container.querySelector('table')!
    expect(table.closest('.overflow-x-auto')).not.toBeNull()
  })
})

describe('EmptyState', () => {
  it('guide vers la création du premier compte', () => {
    render(
      <MemoryRouter>
        <EmptyState />
      </MemoryRouter>,
    )
    expect(
      screen.getByRole('heading', { name: /Commencez par créer un compte/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Créer un compte' })).toHaveAttribute(
      'href',
      '/comptes',
    )
    expect(
      screen.getByText(/PEA, compte-titres, assurance-vie, PEE ou Livret A/),
    ).toBeInTheDocument()
  })
})

describe('alignement des montants (FR-036)', () => {
  it('aligne à droite et en chiffres tabulaires la colonne des valeurs', () => {
    render(
      <MemoryRouter>
        <AccountList accounts={[summary()]} />
      </MemoryRouter>,
    )
    const cells = screen.getAllByRole('cell')
    const money = cells.filter((cell) => /€/.test(cell.textContent ?? ''))
    expect(money.length).toBeGreaterThan(0)
    for (const cell of money) {
      expect(cell).toHaveClass('text-right')
      expect(cell).toHaveClass('tabular-nums')
    }
  })
})
