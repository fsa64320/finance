import path from 'node:path'

import type { Locator, Page } from '@playwright/test'

/** Mot de passe jetable des tests de bout en bout. */
export const PASSWORD = 'e2e-tulipe-bleue-47-horizon'

export const CSV_DIR = path.resolve(import.meta.dirname, '../../../backend/tests/fixtures/csv')

/** Date ISO d'il y a `days` jours : un prix ne peut pas être daté dans le futur. */
export function daysAgo(days: number): string {
  const date = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
  return date.toISOString().slice(0, 10)
}

/** Capture pour le README, seulement quand `E2E_SCREENSHOTS=1`. */
export async function shot(page: Page, name: string): Promise<void> {
  if (!process.env.E2E_SCREENSHOTS) return
  await page.screenshot({
    path: path.resolve(import.meta.dirname, `../../../docs/images/${name}.png`),
    animations: 'disabled',
  })
}

/** Nom accessible approximatif de l'élément qui a le focus. */
export async function focusedName(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    if (!el) return ''
    const labelled = (el as HTMLInputElement).labels?.[0]?.textContent
    return (el.getAttribute('aria-label') ?? labelled ?? el.textContent ?? '').trim()
  })
}

/** Avance au clavier jusqu'à l'élément nommé ; échoue s'il n'est pas atteignable. */
export async function tabTo(page: Page, name: string | RegExp, limit = 60): Promise<void> {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    const current = await focusedName(page)
    if (typeof name === 'string' ? current === name : name.test(current)) return
  }
  throw new Error(`« ${String(name)} » n'est pas atteignable au clavier`)
}

/** Vrai si l'élément qui a le focus a un indicateur visible (contour ou ombre). */
export async function focusIsVisible(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    if (!el || el === document.body) return false
    const style = getComputedStyle(el)
    const outline = style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0
    return outline || style.boxShadow !== 'none'
  })
}

/** Éléments qui dépassent le bord droit de l'écran (liste vide si la page tient). */
export async function overflowing(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const limit = window.innerWidth
    if (document.documentElement.scrollWidth <= limit) return []
    const found: string[] = []
    for (const el of document.querySelectorAll<HTMLElement>('body *')) {
      const box = el.getBoundingClientRect()
      if (box.right > limit + 1 && box.width > 0) {
        found.push(
          `${el.tagName.toLowerCase()}.${el.className.toString().slice(0, 60)} → ${Math.round(box.right)} px`,
        )
      }
    }
    return found.slice(0, 8)
  })
}

export async function fits(page: Page): Promise<boolean> {
  return (await overflowing(page)).length === 0
}

export async function text(locator: Locator): Promise<string> {
  return (await locator.innerText()).replace(/\s+/g, ' ').trim()
}
