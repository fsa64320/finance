import { describe, expect, it } from 'vitest'

import { isPositiveDecimal, normalizeDecimalInput } from '../../src/lib/decimal-input'

describe('normalizeDecimalInput', () => {
  it.each([
    ['1000', '1000'],
    ['1 000,50', '1000.50'],
    ['1 000,5', '1000.5'],
    ['1 000.5', '1000.5'],
    ['  90,199 ', '90.199'],
    ['-2,5', '-2.5'],
    ['0', '0'],
  ])('accepte %j', (given, expected) => {
    expect(normalizeDecimalInput(given)).toBe(expected)
  })

  it.each(['', ' ', 'abc', '1e3', '1,2,3', '1.', '.5', '--1', '1 2 x', 'NaN'])(
    'refuse %j',
    (given) => {
      expect(normalizeDecimalInput(given)).toBeNull()
    },
  )
})

describe('isPositiveDecimal', () => {
  it('distingue strictement positif, nul et négatif', () => {
    expect(isPositiveDecimal('0.01')).toBe(true)
    expect(isPositiveDecimal('0')).toBe(false)
    expect(isPositiveDecimal('0.000')).toBe(false)
    expect(isPositiveDecimal('-1')).toBe(false)
  })
})
