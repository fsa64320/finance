import { describe, expect, it } from 'vitest'

import { guessColumns } from '../../src/lib/import-columns'
import { IMPORT_COLUMNS, IMPORT_HEADERS } from '../fixtures'

describe('guessColumns', () => {
  it('reconnaît les en-têtes courants d’un export français', () => {
    expect(guessColumns(IMPORT_HEADERS)).toEqual(IMPORT_COLUMNS)
  })

  it('reconnaît des variantes avec majuscules, accents et mots en plus', () => {
    const guessed = guessColumns([
      "DATE D'OPÉRATION",
      'Type',
      'Nom du produit',
      'Code ISIN',
      'Nombre de parts',
      'Prix unitaire',
      'Montant net',
      'Frais de courtage',
      'Identifiant',
    ])
    expect(guessed).toEqual({
      trade_date: "DATE D'OPÉRATION",
      type: 'Type',
      instrument_name: 'Nom du produit',
      isin: 'Code ISIN',
      quantity: 'Nombre de parts',
      unit_price: 'Prix unitaire',
      amount: 'Montant net',
      fees: 'Frais de courtage',
      external_id: 'Identifiant',
    })
  })

  it('n’utilise une colonne qu’une fois, sauf le libellé qui sert aussi de nom d’actif', () => {
    const guessed = guessColumns(['Date', 'Opération', 'Montant', 'Montant brut'])
    expect(guessed.amount).toBe('Montant')
    expect(Object.values(guessed).filter((name) => name === 'Montant brut')).toHaveLength(0)
  })

  it('ne devine rien quand rien ne ressemble', () => {
    expect(guessColumns(['A', 'B', 'C'])).toEqual({})
  })
})
