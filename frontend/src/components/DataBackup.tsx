import { type FormEvent, useState } from 'react'

import { ApiError } from '../api/client'
import { formatDate } from '../lib/format'
import { TextField, buttonClass, secondaryButtonClass } from './fields'

interface DataBackupProps {
  lastExportAt: string | null
  reminderDays: number
  onExport: () => Promise<unknown>
  onRestore: (file: File) => Promise<unknown>
  onReminderChange: (days: number) => Promise<unknown>
}

const MAX_PROBLEMS_SHOWN = 8

/** Export, restauration et rappel d'export (FR-030) : le fichier n'est pas chiffré. */
export default function DataBackup({
  lastExportAt,
  reminderDays,
  onExport,
  onRestore,
  onReminderChange,
}: DataBackupProps) {
  const [exported, setExported] = useState(false)
  const [exportError, setExportError] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [days, setDays] = useState(String(reminderDays))
  const [dayError, setDayError] = useState<string | undefined>()
  const [file, setFile] = useState<File | null>(null)
  const [restored, setRestored] = useState(false)
  const [restoreProblems, setRestoreProblems] = useState<string[] | null>(null)
  const [restoring, setRestoring] = useState(false)

  async function runExport() {
    setExported(false)
    setExportError(false)
    setExporting(true)
    try {
      await onExport()
      setExported(true)
    } catch {
      setExportError(true)
    } finally {
      setExporting(false)
    }
  }

  async function saveReminder(event: FormEvent) {
    event.preventDefault()
    const value = Number(days)
    if (days.trim() === '' || !Number.isInteger(value) || value < 0) {
      setDayError('Saisissez un nombre de jours, 0 ou plus.')
      return
    }
    setDayError(undefined)
    await onReminderChange(value)
  }

  async function runRestore() {
    if (!file) return
    setRestored(false)
    setRestoreProblems(null)
    setRestoring(true)
    try {
      await onRestore(file)
      setRestored(true)
    } catch (failure) {
      if (failure instanceof ApiError && failure.details?.length) {
        const lines = failure.details.map((detail) => `${detail.field} : ${detail.message}`)
        const shown = lines.slice(0, MAX_PROBLEMS_SHOWN)
        if (lines.length > shown.length) shown.push(`… et ${lines.length - shown.length} autres.`)
        setRestoreProblems([...shown, 'Rien n’a été modifié.'])
      } else if (failure instanceof Error) {
        setRestoreProblems([failure.message])
      } else {
        setRestoreProblems(['La restauration a échoué.'])
      }
    } finally {
      setRestoring(false)
    }
  }

  return (
    <div>
      <p role="note" className="rounded-lg bg-warn-bg p-3 text-sm text-warn-ink">
        <strong>Le fichier d’export n’est pas chiffré.</strong> Toute personne qui le détient lit
        l’ensemble de votre patrimoine : rangez-le dans un lieu sûr, par exemple un coffre chiffré.
      </p>

      <div className="mt-4">
        <button
          type="button"
          className={buttonClass}
          disabled={exporting}
          onClick={() => void runExport()}
        >
          {exporting ? 'Export en cours…' : 'Exporter mes données'}
        </button>
        <p className="mt-2 text-sm text-muted">
          {lastExportAt
            ? `Dernier export : ${formatDate(lastExportAt.slice(0, 10))}`
            : 'Aucun export pour l’instant.'}
        </p>
        {exported && (
          <p role="status" className="mt-2 text-sm">
            Export téléchargé. Conservez le fichier en lieu sûr.
          </p>
        )}
        {exportError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            L’export a échoué. Réessayez.
          </p>
        )}
      </div>

      <form onSubmit={saveReminder} noValidate className="mt-6 max-w-sm">
        <TextField
          id="reminder-days"
          label="Me rappeler d’exporter tous les (jours)"
          type="number"
          inputMode="decimal"
          value={days}
          onChange={setDays}
          error={dayError}
          hint="0 désactive le rappel."
        />
        <button type="submit" className={`${secondaryButtonClass} mt-3`}>
          Enregistrer le rappel
        </button>
      </form>

      <div className="mt-8">
        <h4 className="font-medium">Restaurer</h4>
        <p className="mt-1 text-sm text-muted">
          La restauration n’est possible que sur une installation vide (aucun compte). Le fichier
          est vérifié en entier avant toute écriture.
        </p>
        <label className="mt-3 block text-sm font-medium" htmlFor="restore-file">
          Fichier d’export à restaurer
        </label>
        <input
          id="restore-file"
          type="file"
          accept=".json,application/json"
          className="mt-1 block w-full text-sm"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null)
            setRestored(false)
            setRestoreProblems(null)
          }}
        />
        <button
          type="button"
          className={`${secondaryButtonClass} mt-3`}
          disabled={!file || restoring}
          onClick={() => void runRestore()}
        >
          {restoring ? 'Restauration…' : 'Restaurer'}
        </button>
        {restored && (
          <p role="status" aria-label="Résultat de la restauration" className="mt-3 text-sm">
            Données restaurées.
          </p>
        )}
        {restoreProblems && (
          <div role="alert" className="mt-3 text-sm text-danger">
            <ul className="list-disc pl-5">
              {restoreProblems.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
