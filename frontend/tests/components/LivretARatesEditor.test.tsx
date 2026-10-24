import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import LivretARatesEditor from '../../src/components/LivretARatesEditor'
import { LIVRET_RATES } from '../fixtures'

function setup(rates = LIVRET_RATES, onAdd = vi.fn().mockResolvedValue(undefined)) {
  render(<LivretARatesEditor rates={rates} onAdd={onAdd} />)
  return onAdd
}

describe('LivretARatesEditor', () => {
  it('liste les taux datés avec leur date d’effet', () => {
    setup()
    const table = screen.getByRole('table', { name: 'Taux du Livret A' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]!).getByText('01/02/2025')).toBeInTheDocument()
    expect(within(rows[0]!).getByText(/2,40/)).toBeInTheDocument()
    expect(within(rows[1]!).getByText('01/08/2025')).toBeInTheDocument()
  })

  it('invite à saisir un taux quand la table est vide', () => {
    setup([])
    expect(screen.getByText(/Aucun taux/)).toBeInTheDocument()
  })

  it('prévient que les taux sont indicatifs et à vérifier', () => {
    setup()
    expect(screen.getByText(/vérifiez/i)).toBeInTheDocument()
  })

  it('ajoute un taux à une date d’effet', async () => {
    const onAdd = setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText("Date d'effet"), '2026-02-01')
    await user.type(screen.getByLabelText('Taux annuel (%)'), '1,5')
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    expect(onAdd).toHaveBeenCalledWith({ effective_from: '2026-02-01', value: '1.5' })
  })

  it('refuse un taux hors de 0 à 100 % ou une date manquante', async () => {
    const onAdd = setup()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    expect(await screen.findByText("La date d'effet est obligatoire.")).toBeInTheDocument()
    expect(screen.getByText('Saisissez le taux annuel.')).toBeInTheDocument()
    await user.type(screen.getByLabelText("Date d'effet"), '2026-02-01')
    await user.type(screen.getByLabelText('Taux annuel (%)'), '120')
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    expect(
      await screen.findByText('Le taux est un pourcentage entre 0 et 100.'),
    ).toBeInTheDocument()
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('vide le formulaire après un ajout réussi', async () => {
    setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText("Date d'effet"), '2026-02-01')
    await user.type(screen.getByLabelText('Taux annuel (%)'), '1,5')
    await user.click(screen.getByRole('button', { name: 'Ajouter le taux' }))
    await screen.findByRole('button', { name: 'Ajouter le taux' })
    expect(screen.getByLabelText('Taux annuel (%)')).toHaveValue('')
  })
})
