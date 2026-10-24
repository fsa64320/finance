import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ErrorState from '../../src/components/ErrorState'
import LoadingState from '../../src/components/LoadingState'

describe('LoadingState', () => {
  it('annonce le chargement aux technologies d’assistance', () => {
    render(<LoadingState />)
    expect(screen.getByRole('status')).toHaveTextContent('Chargement…')
  })

  it('accepte un libellé précis', () => {
    render(<LoadingState label="Chargement de l’historique…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Chargement de l’historique…')
  })
})

describe('ErrorState', () => {
  it('annonce l’erreur et propose de réessayer', async () => {
    const onRetry = vi.fn()
    render(<ErrorState message="Impossible de charger les comptes." onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Impossible de charger les comptes.')
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('n’affiche pas de bouton sans action de nouvelle tentative', () => {
    render(<ErrorState message="Fichier invalide : la colonne Date est absente." />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
