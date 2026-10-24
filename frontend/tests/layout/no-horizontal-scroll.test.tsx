/**
 * FR-026 : le tableau de bord et la liste des comptes tiennent à 375 px sans défilement horizontal.
 *
 * jsdom ne calcule pas la mise en page : ces tests vérifient les garanties structurelles qui
 * l'assurent (tableaux dans un conteneur qui défile, aucune largeur fixe supérieure à l'écran,
 * graphiques à largeur relative, racine qui rogne le débordement). La vérification dans un vrai
 * navigateur à 375 px relève du test de bout en bout (T128).
 */
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import * as dashboardApi from '../../src/api/dashboard'
import Layout from '../../src/components/Layout'
import Accounts from '../../src/pages/Accounts'
import Dashboard from '../../src/pages/Dashboard'
import { allocationBody, seriesBody, summary, summaryBody } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/dashboard')
vi.mock('../../src/api/accounts')
vi.mock('../../src/api/auth')

const SCREEN = 375

beforeEach(() => {
  vi.mocked(dashboardApi.getSummary).mockResolvedValue(summaryBody() as never)
  vi.mocked(dashboardApi.getSeries).mockResolvedValue(seriesBody() as never)
  vi.mocked(dashboardApi.getAllocation).mockResolvedValue(allocationBody() as never)
  vi.mocked(accountsApi.listAccounts).mockResolvedValue([
    summary({ name: 'Un compte au nom particulièrement long pour vérifier le retour à la ligne' }),
  ])
})

function pixelWidths(root: HTMLElement): number[] {
  const widths: number[] = []
  for (const element of root.querySelectorAll<HTMLElement>('*')) {
    const inline = /(?:^|;)\s*(?:min-)?width:\s*(\d+(?:\.\d+)?)px/.exec(
      element.getAttribute('style') ?? '',
    )
    if (inline) widths.push(Number(inline[1]))
    for (const token of element.classList) {
      const arbitrary = /^(?:min-)?w-\[(\d+)px\]$/.exec(token)
      if (arbitrary) widths.push(Number(arbitrary[1]))
    }
  }
  return widths
}

async function assertFits(container: HTMLElement) {
  expect(pixelWidths(container).filter((width) => width > SCREEN)).toEqual([])
  for (const table of container.querySelectorAll('table')) {
    expect(table.closest('.overflow-x-auto'), 'un tableau sans conteneur qui défile').not.toBeNull()
  }
  for (const chart of container.querySelectorAll('.recharts-responsive-container')) {
    expect(chart).toHaveStyle({ width: '100%' })
  }
}

describe('375 px de large', () => {
  it('le tableau de bord ne déborde pas', async () => {
    const { container } = renderWithProviders(<Dashboard />)
    await screen.findByTestId('net-worth')
    await screen.findByRole('link', { name: /Un compte au nom/ })
    await assertFits(container)
  })

  it('la liste des comptes ne déborde pas', async () => {
    const { container } = renderWithProviders(<Accounts />)
    await screen.findByRole('link', { name: /Un compte au nom/ })
    await assertFits(container)
  })

  it('la mise en page rogne tout débordement horizontal', () => {
    const { container } = renderWithProviders(<Layout />)
    expect(container.firstElementChild).toHaveClass('overflow-x-hidden')
  })

  it('le viewport est adapté aux téléphones', async () => {
    const html = await import('../../index.html?raw')
    expect(html.default).toContain('width=device-width, initial-scale=1.0')
  })
})
