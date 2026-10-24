import { useState } from 'react'
import { Link } from 'react-router-dom'

interface ExportReminderBannerProps {
  lastExportAt: string | null
  /** Fréquence choisie ; 0 désactive le rappel. */
  reminderDays: number
  hasData: boolean
  today?: Date
}

const DAY = 24 * 60 * 60 * 1000

/** Rappel d'exporter (FR-028) : un oubli de mot de passe rend les données illisibles. */
export default function ExportReminderBanner({
  lastExportAt,
  reminderDays,
  hasData,
  today = new Date(),
}: ExportReminderBannerProps) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed || reminderDays <= 0 || !hasData) return null

  const elapsed =
    lastExportAt === null
      ? null
      : Math.floor((today.getTime() - new Date(lastExportAt).getTime()) / DAY)
  if (elapsed !== null && elapsed < reminderDays) return null

  return (
    <div role="status" className="border-b border-line bg-warn-bg px-4 py-3 text-sm text-warn-ink">
      <p>
        {elapsed === null
          ? 'Vous n’avez encore jamais exporté vos données.'
          : `Votre dernier export date d’il y a ${elapsed} jours.`}{' '}
        Exportez-les régulièrement : si vous oubliez votre mot de passe, elles seraient
        définitivement illisibles.
      </p>
      <div className="mt-2 flex gap-3">
        <Link className="font-medium underline" to="/reglages">
          Exporter maintenant
        </Link>
        <button type="button" className="underline" onClick={() => setDismissed(true)}>
          Plus tard
        </button>
      </div>
    </div>
  )
}
