import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import ChartSummary from '../../src/components/ChartSummary'

describe('ChartSummary', () => {
  it('propose le tableau de données derrière un résumé repliable', async () => {
    render(
      <ChartSummary
        caption="Évolution du patrimoine"
        columns={['Date', 'Valeur']}
        rows={[
          ['01/01/2026', '1 000,00 €'],
          ['01/02/2026', '1 250,50 €'],
        ]}
      />,
    )
    const summary = screen.getByText('Afficher les données du graphique')
    await userEvent.click(summary)
    const table = screen.getByRole('table', { name: 'Évolution du patrimoine' })
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((c) => c.textContent),
    ).toEqual(['Date', 'Valeur'])
    expect(within(table).getByText('1 250,50 €')).toBeInTheDocument()
  })

  it('n’affiche rien sans ligne', () => {
    const { container } = render(<ChartSummary caption="vide" columns={['A']} rows={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
