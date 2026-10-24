import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PriceFetchConsent from '../../src/components/PriceFetchConsent'
import { settingsBody } from '../fixtures'

function setup(enabled = false, onChange = vi.fn().mockResolvedValue(undefined)) {
  render(
    <PriceFetchConsent
      settings={settingsBody({ auto_fetch_prices: enabled }) as never}
      onChange={onChange}
    />,
  )
  return onChange
}

describe('PriceFetchConsent', () => {
  it('annonce que rien ne sort tant que la récupération est désactivée', () => {
    setup()
    expect(screen.getByRole('status')).toHaveTextContent(/désactivée/i)
    expect(screen.getByRole('status')).toHaveTextContent(/rien ne sort/i)
  })

  it('liste les services contactés et les données envoyées à chacun', () => {
    setup()
    const list = screen.getByRole('list', { name: 'Services contactés' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('BCE')
    expect(items[1]).toHaveTextContent('Yahoo Finance')
    expect(items[1]).toHaveTextContent('Le ticker de chaque actif suivi')
    expect(items[2]).toHaveTextContent('Le code ISIN de l’actif concerné, rien d’autre.')
  })

  it('n’active qu’après un choix explicite', async () => {
    const onChange = setup()
    expect(onChange).not.toHaveBeenCalled()
    await userEvent.click(
      screen.getByRole('button', { name: 'Activer la récupération automatique' }),
    )
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('se désactive à tout moment', async () => {
    const onChange = setup(true)
    expect(screen.getByRole('status')).toHaveTextContent(/activée/i)
    await userEvent.click(
      screen.getByRole('button', { name: 'Désactiver la récupération automatique' }),
    )
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it('désactive le bouton pendant l’envoi', async () => {
    const onChange = vi.fn(() => new Promise<void>(() => {}))
    setup(false, onChange)
    await userEvent.click(
      screen.getByRole('button', { name: 'Activer la récupération automatique' }),
    )
    expect(await screen.findByRole('button', { name: 'Enregistrement…' })).toBeDisabled()
  })
})
