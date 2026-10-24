import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import NetWorthChart from '../../src/components/NetWorthChart'
import { seriesBody } from '../fixtures'

const plain = (text: string | null) => (text ?? '').replace(/\s/g, ' ')

describe('NetWorthChart', () => {
  it('décrit la courbe en texte pour les lecteurs d’écran', () => {
    render(<NetWorthChart points={seriesBody().points} currency="EUR" />)
    const figure = screen.getByRole('img', { name: /Évolution du patrimoine/ })
    const label = plain(figure.getAttribute('aria-label'))
    expect(label).toContain('1 000,00 €')
    expect(label).toContain('05/01/2026')
    expect(label).toContain('8 500,00 €')
    expect(label).toContain('24/10/2026')
  })

  it('signale que des points sont estimés', () => {
    render(<NetWorthChart points={seriesBody().points} currency="EUR" />)
    expect(screen.getByText(/valeurs estimées/i)).toBeInTheDocument()
  })

  it('ne signale rien quand aucun point n’est estimé', () => {
    const points = seriesBody().points.map((p) => ({ ...p, estimated: false }))
    render(<NetWorthChart points={points} currency="EUR" />)
    expect(screen.queryByText(/valeurs estimées/i)).not.toBeInTheDocument()
  })

  it('explique qu’il n’y a rien à tracer sans historique', () => {
    render(<NetWorthChart points={[]} currency="EUR" />)
    expect(screen.getByText(/Pas encore d'historique à afficher/)).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('tient dans la largeur du parent', () => {
    const { container } = render(<NetWorthChart points={seriesBody().points} currency="EUR" />)
    expect(container.querySelector('.recharts-responsive-container')).toHaveStyle({ width: '100%' })
  })
})
