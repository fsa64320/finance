import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StaleBadge from '../../src/components/StaleBadge'

describe('StaleBadge', () => {
  it('dit « estimé » par défaut', () => {
    render(<StaleBadge />)
    expect(screen.getByText('estimé')).toBeInTheDocument()
  })

  it.each([
    ['price_stale', 'prix ancien'],
    ['rate_stale', 'taux ancien'],
    ['rate_missing', 'taux manquant'],
    ['declared_balance_missing', 'solde non déclaré'],
    ['non_convertible', 'non convertible'],
  ])('nomme la cause %s', (code, label) => {
    render(<StaleBadge code={code} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('retombe sur « estimé » pour une cause inconnue ou un prix absent', () => {
    render(
      <>
        <StaleBadge code="price_missing" />
        <StaleBadge code="autre" />
      </>,
    )
    expect(screen.getAllByText('estimé')).toHaveLength(2)
  })

  it('accepte un libellé imposé', () => {
    render(<StaleBadge label="Estimé" />)
    expect(screen.getByText('Estimé')).toBeInTheDocument()
  })

  it('ne repose pas sur la couleur seule : le texte porte l’information', () => {
    render(<StaleBadge code="price_stale" />)
    expect(screen.getByText('prix ancien')).toHaveTextContent(/\S/)
  })
})
