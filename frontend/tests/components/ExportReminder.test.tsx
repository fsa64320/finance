import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as accountsApi from '../../src/api/accounts'
import * as settingsApi from '../../src/api/settings'
import ExportReminder from '../../src/components/ExportReminder'
import { settingsBody, summary } from '../fixtures'
import { renderWithProviders } from '../utils'

vi.mock('../../src/api/accounts')
vi.mock('../../src/api/settings')

beforeEach(() => {
  vi.mocked(accountsApi.listAccounts).mockReset().mockResolvedValue([summary()])
  vi.mocked(settingsApi.getSettings)
    .mockReset()
    .mockResolvedValue(settingsBody({ last_export_at: null, export_reminder_days: 30 }) as never)
})

describe('ExportReminder', () => {
  it('affiche le rappel quand il y a des données jamais exportées', async () => {
    renderWithProviders(<ExportReminder />)
    expect(await screen.findByRole('status')).toHaveTextContent(/jamais exporté/i)
  })

  it('ne dit rien sans compte', async () => {
    vi.mocked(accountsApi.listAccounts).mockResolvedValue([])
    renderWithProviders(<ExportReminder />)
    await vi.waitFor(() => expect(accountsApi.listAccounts).toHaveBeenCalled())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('ne casse rien quand les réglages ne se chargent pas', async () => {
    vi.mocked(settingsApi.getSettings).mockRejectedValue(new Error('réseau'))
    renderWithProviders(<ExportReminder />)
    await vi.waitFor(() => expect(settingsApi.getSettings).toHaveBeenCalled())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
