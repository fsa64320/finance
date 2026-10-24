import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import ExportReminderBanner from '../../src/components/ExportReminderBanner'

const TODAY = new Date('2026-10-24T12:00:00Z')

function banner(props: Partial<React.ComponentProps<typeof ExportReminderBanner>> = {}) {
  return render(
    <MemoryRouter>
      <ExportReminderBanner
        lastExportAt={null}
        reminderDays={30}
        hasData
        today={TODAY}
        {...props}
      />
    </MemoryRouter>,
  )
}

describe('ExportReminderBanner', () => {
  it('rappelle d’exporter quand des données n’ont jamais été exportées', () => {
    banner()
    expect(screen.getByRole('status')).toHaveTextContent(/jamais exporté/i)
    expect(screen.getByRole('link', { name: 'Exporter maintenant' })).toHaveAttribute(
      'href',
      '/reglages',
    )
  })

  it('rappelle quand le dernier export est plus ancien que la fréquence choisie', () => {
    banner({ lastExportAt: '2026-09-01T10:00:00Z' })
    expect(screen.getByRole('status')).toHaveTextContent(/il y a 53 jours/)
  })

  it('rappelle pourquoi : un oubli de mot de passe rend les données illisibles', () => {
    banner()
    expect(screen.getByRole('status')).toHaveTextContent(/mot de passe/i)
  })

  it('se tait quand l’export est récent', () => {
    banner({ lastExportAt: '2026-10-20T10:00:00Z' })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('se déclenche pile au bout du délai', () => {
    banner({ lastExportAt: '2026-09-24T12:00:00Z', reminderDays: 30 })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    banner({ lastExportAt: '2026-09-23T12:00:00Z', reminderDays: 30 })
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('se tait quand le rappel est désactivé', () => {
    banner({ reminderDays: 0 })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('se tait tant qu’il n’y a rien à exporter', () => {
    banner({ hasData: false })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('peut être reporté', async () => {
    banner()
    await userEvent.click(screen.getByRole('button', { name: 'Plus tard' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
