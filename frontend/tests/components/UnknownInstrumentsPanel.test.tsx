import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import UnknownInstrumentsPanel, {
  isResolved,
  toResolutions,
} from '../../src/components/UnknownInstrumentsPanel'
import { ETF_ID, instrument } from '../fixtures'

const ALPHA = { key: 'FR0000000036', name: 'Fonds Inconnu Alpha', isin: 'FR0000000036', rows: 2 }
const BETA = { key: 'name:fonds inconnu beta', name: 'Fonds Inconnu Beta', isin: null, rows: 1 }

function setup(choices = {}) {
  const onChange = vi.fn()
  render(
    <UnknownInstrumentsPanel
      items={[ALPHA, BETA]}
      instruments={[instrument()]}
      choices={choices}
      onChange={onChange}
    />,
  )
  return onChange
}

describe('UnknownInstrumentsPanel', () => {
  it('explique que rien n’est créé avant la validation', () => {
    setup()
    expect(screen.getByRole('heading', { name: 'Actifs inconnus' })).toBeInTheDocument()
    expect(screen.getByText(/rien n’est créé avant la validation/i)).toBeInTheDocument()
  })

  it('présente chaque actif avec son code ISIN et le nombre de lignes', () => {
    setup()
    const alpha = screen.getByRole('group', { name: /Fonds Inconnu Alpha/ })
    expect(alpha).toHaveTextContent('FR0000000036')
    expect(alpha).toHaveTextContent('2 lignes')
    expect(screen.getByRole('group', { name: /Fonds Inconnu Beta/ })).toHaveTextContent('1 ligne')
  })

  it('propose créer, rattacher ou ignorer, sans choix par défaut', () => {
    setup()
    const alpha = screen.getByRole('group', { name: /Fonds Inconnu Alpha/ })
    for (const name of ['Créer cet actif', 'Rattacher à un actif existant', 'Ignorer ces lignes']) {
      expect(within(alpha).getByRole('radio', { name })).not.toBeChecked()
    }
  })

  it('demande le type de l’actif à créer', async () => {
    const onChange = setup()
    const alpha = screen.getByRole('group', { name: /Fonds Inconnu Alpha/ })
    await userEvent.click(within(alpha).getByRole('radio', { name: 'Créer cet actif' }))
    expect(onChange).toHaveBeenCalledWith({ [ALPHA.key]: { action: 'create' } })
  })

  it('affiche le type à choisir quand « créer » est retenu', async () => {
    const onChange = setup({ [ALPHA.key]: { action: 'create' } })
    const alpha = screen.getByRole('group', { name: /Fonds Inconnu Alpha/ })
    await userEvent.selectOptions(within(alpha).getByLabelText("Type de l'actif"), 'FUND')
    expect(onChange).toHaveBeenCalledWith({ [ALPHA.key]: { action: 'create', kind: 'FUND' } })
  })

  it('liste les actifs existants quand « rattacher » est retenu', async () => {
    const onChange = setup({ [BETA.key]: { action: 'link' } })
    const beta = screen.getByRole('group', { name: /Fonds Inconnu Beta/ })
    await userEvent.selectOptions(within(beta).getByLabelText('Actif existant'), ETF_ID)
    expect(onChange).toHaveBeenCalledWith({ [BETA.key]: { action: 'link', instrumentId: ETF_ID } })
  })

  it('n’affiche pas les listes tant que l’action ne les demande pas', () => {
    setup({ [ALPHA.key]: { action: 'skip' } })
    expect(screen.queryByLabelText("Type de l'actif")).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Actif existant')).not.toBeInTheDocument()
  })
})

describe('isResolved et toResolutions', () => {
  it('une décision est complète quand elle a ce qu’il lui faut', () => {
    expect(isResolved(undefined)).toBe(false)
    expect(isResolved({ action: 'create' })).toBe(false)
    expect(isResolved({ action: 'create', kind: 'ETF' })).toBe(true)
    expect(isResolved({ action: 'link' })).toBe(false)
    expect(isResolved({ action: 'link', instrumentId: ETF_ID })).toBe(true)
    expect(isResolved({ action: 'skip' })).toBe(true)
  })

  it('produit les résolutions du contrat', () => {
    expect(
      toResolutions([ALPHA, BETA], {
        [ALPHA.key]: { action: 'create', kind: 'FUND' },
        [BETA.key]: { action: 'link', instrumentId: ETF_ID },
      }),
    ).toEqual([
      { key: ALPHA.key, action: 'create', kind: 'FUND' },
      { key: BETA.key, action: 'link', instrument_id: ETF_ID },
    ])
    expect(toResolutions([ALPHA], { [ALPHA.key]: { action: 'skip' } })).toEqual([
      { key: ALPHA.key, action: 'skip' },
    ])
  })
})
