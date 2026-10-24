import { useQuery } from '@tanstack/react-query'

import { listAccounts } from '../api/accounts'
import { keys } from '../api/keys'
import { getSettings } from '../api/settings'
import ExportReminderBanner from './ExportReminderBanner'

/** Lit les réglages et les comptes ; en cas d'échec, le rappel se tait plutôt que de gêner. */
export default function ExportReminder() {
  const settings = useQuery({ queryKey: keys.settings, queryFn: getSettings })
  const accounts = useQuery({
    queryKey: keys.accountList(false),
    queryFn: () => listAccounts({ includeClosed: false }),
  })
  if (!settings.data || !accounts.data) return null
  return (
    <ExportReminderBanner
      lastExportAt={settings.data.last_export_at ?? null}
      reminderDays={settings.data.export_reminder_days}
      hasData={accounts.data.length > 0}
    />
  )
}
