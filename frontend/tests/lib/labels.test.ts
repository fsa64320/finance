import { describe, expect, it } from 'vitest'

import {
  ACCOUNT_TYPE_LABELS,
  INSTRUMENT_KIND_LABELS,
  TRANSACTION_TYPE_LABELS,
  transactionTypesFor,
} from '../../src/lib/labels'

describe('libellés', () => {
  it('nomme les cinq types de compte', () => {
    expect(ACCOUNT_TYPE_LABELS).toEqual({
      PEE: 'Plan d’épargne entreprise (PEE)',
      PEA: 'Plan d’épargne en actions (PEA)',
      CTO: 'Compte-titres ordinaire (CTO)',
      ASSURANCE_VIE: 'Assurance-vie',
      LIVRET_A: 'Livret A',
    })
  })

  it('nomme les sept types d’actif', () => {
    expect(Object.keys(INSTRUMENT_KIND_LABELS).sort()).toEqual(
      ['CASH', 'EQUITY', 'ETF', 'EURO_FUND', 'FCPE', 'FUND', 'SCPI'].sort(),
    )
  })

  it('nomme tous les types d’opération, virements compris', () => {
    expect(TRANSACTION_TYPE_LABELS.BUY).toBe('Achat')
    expect(TRANSACTION_TYPE_LABELS.EMPLOYER_MATCH).toBe('Abondement')
    expect(TRANSACTION_TYPE_LABELS.TRANSFER_OUT).toBe('Virement sortant')
    expect(Object.keys(TRANSACTION_TYPE_LABELS)).toHaveLength(11)
  })

  it('limite les types saisissables selon le compte', () => {
    expect(transactionTypesFor('PEE')).toContain('EMPLOYER_MATCH')
    for (const kind of ['PEA', 'CTO', 'ASSURANCE_VIE', 'LIVRET_A'] as const) {
      expect(transactionTypesFor(kind)).not.toContain('EMPLOYER_MATCH')
    }
    expect(transactionTypesFor('LIVRET_A')).not.toContain('BUY')
    expect(transactionTypesFor('LIVRET_A')).not.toContain('SELL')
    expect(transactionTypesFor('PEA')).toContain('BUY')
    expect(transactionTypesFor('PEA')).not.toContain('TRANSFER_OUT')
  })
})
