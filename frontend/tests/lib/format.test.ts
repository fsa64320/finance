import { describe, expect, it } from 'vitest'

import { formatDate, formatMoney, formatPercent, formatQuantity } from '../../src/lib/format'

// L'espace insécable fine de fr-FR varie selon la version d'ICU : on normalise les espaces.
const plain = (text: string) => text.replace(/\s/g, ' ').replace('−', '-')

describe('formatMoney', () => {
  it('formate en euros à la française avec deux décimales', () => {
    expect(plain(formatMoney('1234.5'))).toBe('1 234,50 €')
    expect(plain(formatMoney('0'))).toBe('0,00 €')
  })

  it("arrondit la moitié vers l'extérieur de zéro, comme le backend", () => {
    expect(plain(formatMoney('2.675'))).toBe('2,68 €')
    expect(plain(formatMoney('-2.675'))).toBe('-2,68 €')
    expect(plain(formatMoney('0.005'))).toBe('0,01 €')
    expect(plain(formatMoney('0.004'))).toBe('0,00 €')
  })

  it('reste exact sur de grands montants et de longues décimales', () => {
    expect(plain(formatMoney('123456789012.345'))).toBe('123 456 789 012,35 €')
    expect(plain(formatMoney('0.1'))).toBe('0,10 €')
  })

  it('accepte une autre devise', () => {
    expect(plain(formatMoney('90.2', 'USD'))).toContain('90,20')
  })

  it("refuse un texte qui n'est pas un décimal", () => {
    expect(() => formatMoney('abc')).toThrow()
    expect(() => formatMoney('1e3')).toThrow()
  })
})

describe('formatPercent', () => {
  it('exprime un pourcentage déjà en pourcents', () => {
    expect(plain(formatPercent('12.5'))).toBe('12,50 %')
    expect(plain(formatPercent('-0.5'))).toBe('-0,50 %')
    expect(plain(formatPercent('100'))).toBe('100,00 %')
  })
})

describe('formatQuantity', () => {
  it("retire les zéros inutiles et garde jusqu'à 6 décimales", () => {
    expect(plain(formatQuantity('10.000000'))).toBe('10')
    expect(plain(formatQuantity('0.125'))).toBe('0,125')
    expect(plain(formatQuantity('1234.567891'))).toBe('1 234,567891')
  })
})

describe('formatDate', () => {
  it('affiche une date ISO au format français sans décalage de fuseau', () => {
    expect(formatDate('2026-01-05')).toBe('05/01/2026')
    expect(formatDate('2026-12-31')).toBe('31/12/2026')
  })

  it('refuse une date invalide', () => {
    expect(() => formatDate('pas une date')).toThrow()
  })
})
