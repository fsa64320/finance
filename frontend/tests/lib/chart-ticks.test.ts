import { describe, expect, it } from 'vitest'

import { formatTickDate, formatTickMoney, spanInDays } from '../../src/lib/chart-ticks'

const plain = (text: string) => text.replace(/\s/g, ' ')

describe('graduations de l’axe des dates', () => {
  it('mesure l’étendue de la courbe en jours', () => {
    expect(spanInDays('2026-01-01', '2026-01-31')).toBe(30)
    expect(spanInDays('2026-01-31', '2026-01-31')).toBe(0)
  })

  it('montre le jour et le mois sur une courte période (pas de mois répété)', () => {
    expect(formatTickDate('2026-10-24', 90)).toBe('24/10')
    expect(formatTickDate('2026-02-03', 120)).toBe('03/02')
  })

  it('montre le mois et l’année sur une longue période', () => {
    expect(formatTickDate('2026-10-24', 365)).toBe('10/26')
    expect(formatTickDate('2021-03-01', 1800)).toBe('03/21')
  })
})

describe('graduations de l’axe des montants', () => {
  it('arrondit à l’euro et garde les séparateurs', () => {
    expect(plain(formatTickMoney(1000, 'EUR'))).toBe('1 000 €')
    expect(plain(formatTickMoney(8508.8541, 'EUR'))).toBe('8 509 €')
    expect(plain(formatTickMoney(0, 'EUR'))).toBe('0 €')
  })
})
