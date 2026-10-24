import { describe, expect, it } from 'vitest'

import { formatPercentOf, formatUnitPrice } from '../../src/lib/format'

const plain = (text: string) => text.replace(/\s/g, ' ')

describe('formatUnitPrice', () => {
  it('garde jusqu’à quatre décimales utiles, deux au minimum', () => {
    expect(plain(formatUnitPrice('90.199'))).toBe('90,199 €')
    expect(plain(formatUnitPrice('95.0995'))).toBe('95,0995 €')
    expect(plain(formatUnitPrice('90'))).toBe('90,00 €')
    expect(plain(formatUnitPrice('90.5'))).toBe('90,50 €')
  })

  it('arrondit la moitié vers l’extérieur de zéro à quatre décimales', () => {
    expect(plain(formatUnitPrice('0.12345'))).toBe('0,1235 €')
    expect(plain(formatUnitPrice('-0.12345'))).toBe('-0,1235 €')
  })
})

describe('formatPercentOf', () => {
  it('donne la part en pourcents, sans flottant', () => {
    expect(formatPercentOf('120000', '150000')).toBe('80')
    expect(formatPercentOf('1000', '150000')).toBe('1')
    expect(formatPercentOf('0', '150000')).toBe('0')
  })

  it('plafonne à 100 pour l’affichage d’une jauge', () => {
    expect(formatPercentOf('160000', '150000', { capAt100: true })).toBe('100')
    expect(formatPercentOf('160000', '150000')).toBe('107')
  })

  it('refuse un plafond nul', () => {
    expect(() => formatPercentOf('1', '0')).toThrow()
  })
})
