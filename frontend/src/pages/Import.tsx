import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { listAccounts } from '../api/accounts'
import { type ImportSettings, commitImport, listMappings, previewImport } from '../api/imports'
import { listInstruments } from '../api/instruments'
import { keys } from '../api/keys'
import type { ImportCommit, ImportPreview, ImportResult } from '../api/types'
import ColumnMapper from '../components/ColumnMapper'
import UnknownInstrumentsPanel from '../components/UnknownInstrumentsPanel'
import { SelectField, TextField, buttonClass, secondaryButtonClass } from '../components/fields'
import { splitApiError } from '../lib/form-errors'
import { formatDate, formatMoney, formatQuantity } from '../lib/format'
import { guessColumns } from '../lib/import-columns'
import { type Choice, isResolved, toResolutions } from '../lib/import-resolutions'
import { TRANSACTION_TYPE_LABELS, type TransactionType } from '../lib/labels'

const cardClass = 'rounded-2xl border border-line bg-card p-5 shadow-sm'
const MAX_REJECTED_SHOWN = 50

const DELIMITERS = [
  { value: ';', label: 'Point-virgule (;)' },
  { value: ',', label: 'Virgule (,)' },
  { value: '\t', label: 'Tabulation' },
  { value: '|', label: 'Barre verticale (|)' },
]
const ENCODINGS = ['utf-8', 'utf-8-sig', 'windows-1252', 'iso-8859-15']
const DATE_FORMATS = [
  { value: '%d/%m/%Y', label: 'JJ/MM/AAAA' },
  { value: '%d/%m/%y', label: 'JJ/MM/AA' },
  { value: '%Y-%m-%d', label: 'AAAA-MM-JJ' },
  { value: '%d-%m-%Y', label: 'JJ-MM-AAAA' },
  { value: '%d.%m.%Y', label: 'JJ.MM.AAAA' },
]
const DECIMALS = [
  { value: ',', label: 'Virgule (1 250,50)' },
  { value: '.', label: 'Point (1250.50)' },
]

interface SampleLine {
  line: number
  status: string
  trade_date: string
  type: TransactionType
  instrument_name?: string | null
  quantity?: string | null
  unit_price?: string | null
  amount?: string | null
  label?: string | null
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

function settingsFrom(preview: ImportPreview): ImportSettings {
  const detected = preview.detected
  return {
    delimiter: detected.delimiter ?? ';',
    encoding: detected.encoding ?? 'utf-8',
    date_format: detected.date_format ?? '%d/%m/%Y',
    decimal_separator: detected.decimal_separator ?? ',',
  }
}

export default function Import() {
  const queryClient = useQueryClient()
  const accounts = useQuery({
    queryKey: keys.accountList(false),
    queryFn: () => listAccounts({ includeClosed: false }),
  })
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: listInstruments })
  const mappings = useQuery({ queryKey: keys.importMappings, queryFn: listMappings })

  const [accountId, setAccountId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [columns, setColumns] = useState<Record<string, string>>({})
  const [columnErrors, setColumnErrors] = useState<Record<string, string>>({})
  const [settings, setSettings] = useState<ImportSettings | null>(null)
  const [choices, setChoices] = useState<Record<string, Choice>>({})
  const [confirmRejected, setConfirmRejected] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [result, setResult] = useState<ImportResult | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  const account = accounts.data?.find((item) => item.id === accountId)

  function reset() {
    setPreview(null)
    setColumns({})
    setColumnErrors({})
    setSettings(null)
    setChoices({})
    setConfirmRejected(false)
    setSaveName('')
    setProblem(null)
  }

  const analyse = useMutation({
    mutationFn: (options: { columns?: Record<string, string>; settings?: ImportSettings }) =>
      previewImport({ file: file!, accountId, ...options }),
    onSuccess: (body, options) => {
      setProblem(null)
      setPreview(body)
      setChoices({})
      setConfirmRejected(false)
      const applied = body.columns ?? {}
      const hasColumns = Object.keys(applied).length > 0
      setColumns(
        hasColumns ? applied : { ...(options.columns ?? {}), ...guessIfEmpty(body, options) },
      )
      setSettings(options.settings ?? settingsFrom(body))
    },
    onError: (failure) => setProblem(splitApiError(failure, []).general),
  })

  const commit = useMutation({
    mutationFn: (body: ImportCommit) => commitImport(body),
    onSuccess: async (body) => {
      setProblem(null)
      setResult(body)
      await Promise.all(
        [
          keys.dashboard,
          keys.accounts,
          keys.transactions,
          keys.instruments,
          keys.importMappings,
        ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      )
    },
    onError: (failure) => setProblem(splitApiError(failure, []).general),
  })

  function guessIfEmpty(body: ImportPreview, options: { columns?: Record<string, string> }) {
    if (options.columns && Object.keys(options.columns).length > 0) return {}
    return guessColumns(body.detected.headers ?? [])
  }

  function analyseWithColumns() {
    const errors: Record<string, string> = {}
    if (!columns.trade_date) errors.trade_date = 'Choisissez la colonne de la date.'
    if (!columns.type) errors.type = "Choisissez la colonne du type d'opération."
    setColumnErrors(errors)
    if (Object.keys(errors).length > 0) return
    analyse.mutate({ columns, settings: settings ?? undefined })
  }

  const rejected = preview?.rows_rejected ?? []
  const unknown = preview?.unknown_instruments ?? []
  const mapping = mappings.data?.find((item) => item.id === preview?.mapping_id)
  const needsMapping = preview !== null && Object.keys(preview.columns ?? {}).length === 0
  const unresolved = unknown.some((item) => !isResolved(choices[item.key]))
  const blockedByRejected = rejected.length > 0 && !confirmRejected

  function submit() {
    if (!preview) return
    const body: ImportCommit = {
      preview_id: preview.preview_id,
      confirm_rejected: rejected.length > 0 && confirmRejected,
    }
    if (unknown.length > 0) body.instrument_resolutions = toResolutions(unknown, choices)
    if (saveName.trim() && !preview.mapping_id) body.save_mapping_as = saveName.trim()
    commit.mutate(body)
  }

  if (result) {
    return (
      <section>
        <h2 className="text-xl font-semibold">Importer des opérations</h2>
        <div className={`${cardClass} mt-4`}>
          <h3 className="font-medium">Import terminé</h3>
          <ul className="mt-3 space-y-1">
            <li>{plural(result.rows_added, 'ajoutée', 'ajoutées')}</li>
            <li>{plural(result.rows_skipped, 'ignorée', 'ignorées')}</li>
            <li>{plural(result.rows_rejected, 'rejetée', 'rejetées')}</li>
            {(result.instruments_created ?? 0) > 0 && (
              <li>{plural(result.instruments_created ?? 0, 'actif créé', 'actifs créés')}</li>
            )}
          </ul>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              className="rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink"
              to={`/comptes/${accountId}`}
            >
              Voir le compte
            </Link>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => {
                setResult(null)
                setFile(null)
                setAccountId('')
                reset()
              }}
            >
              Importer un autre fichier
            </button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">Importer des opérations</h2>
      <p className="mt-1 text-sm text-muted">
        Déposez un fichier CSV exporté par votre courtier ou votre établissement. Rien n’est
        enregistré avant votre validation, et le même fichier peut être réimporté sans doublon.
      </p>

      <form
        className={`${cardClass} mt-4 max-w-xl`}
        onSubmit={(event) => {
          event.preventDefault()
          reset()
          analyse.mutate({})
        }}
      >
        {accounts.data && accounts.data.length === 0 ? (
          <p>
            Il faut d’abord un compte pour y importer des opérations.{' '}
            <Link className="text-brand underline" to="/comptes">
              Créer un compte
            </Link>
          </p>
        ) : (
          <SelectField
            id="import-account"
            label="Compte"
            value={accountId}
            onChange={(value) => {
              setAccountId(value)
              reset()
            }}
            options={(accounts.data ?? []).map((item) => ({ value: item.id, label: item.name }))}
            placeholder="Choisir un compte"
          />
        )}
        <div className="mt-3">
          <label className="block text-sm font-medium" htmlFor="import-file">
            Fichier CSV
          </label>
          <input
            id="import-file"
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            className="mt-1 block w-full text-sm"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              reset()
            }}
          />
        </div>
        <button
          type="submit"
          className={`${buttonClass} mt-4`}
          disabled={!accountId || !file || analyse.isPending}
        >
          {analyse.isPending && !preview ? 'Analyse en cours…' : 'Analyser le fichier'}
        </button>
      </form>

      {problem && (
        <p role="alert" className="mt-4 text-danger">
          {problem}
        </p>
      )}

      {preview && needsMapping && (
        <div className={`${cardClass} mt-6`}>
          <h3 className="font-medium">Correspondance des colonnes</h3>
          <p className="mt-1 text-sm text-muted">
            Indiquez quelle colonne du fichier renseigne chaque donnée. Nous avons proposé des
            colonnes d’après leur nom : vérifiez-les.
          </p>
          <ColumnMapper
            headers={preview.detected.headers ?? []}
            columns={columns}
            onChange={setColumns}
            errors={columnErrors}
          />
          <button
            type="button"
            className={`${buttonClass} mt-4`}
            disabled={analyse.isPending}
            onClick={analyseWithColumns}
          >
            Analyser avec ces colonnes
          </button>
        </div>
      )}

      {preview && !needsMapping && (
        <div className="mt-6 space-y-6">
          <div className={cardClass}>
            <h3 className="font-medium">Aperçu</h3>
            {mapping && (
              <p className="mt-1 text-sm text-muted">Paramétrage « {mapping.name} » appliqué.</p>
            )}
            <ul className="mt-3 space-y-1">
              <li>{plural(preview.rows_valid, 'ligne à ajouter', 'lignes à ajouter')}</li>
              {preview.rows_duplicate > 0 && (
                <li>
                  {plural(
                    preview.rows_duplicate,
                    'ligne déjà présente (ignorée)',
                    'lignes déjà présentes (ignorées)',
                  )}
                </li>
              )}
              {rejected.length > 0 && (
                <li className="text-danger">
                  {plural(rejected.length, 'ligne invalide', 'lignes invalides')}
                </li>
              )}
            </ul>

            {preview.sample.length > 0 && account && (
              <div className="mt-4 overflow-x-auto">
                <table
                  aria-label="Aperçu des premières lignes"
                  className="w-full text-left text-sm"
                >
                  <thead className="text-muted">
                    <tr>
                      {[
                        'Ligne',
                        'Date',
                        'Type',
                        'Actif',
                        'Quantité',
                        'Prix',
                        'Montant',
                        'Libellé',
                        'État',
                      ].map((title) => (
                        <th key={title} scope="col" className="py-2 pr-3 font-medium">
                          {title}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(preview.sample as unknown as SampleLine[]).map((line) => (
                      <tr key={line.line} className="border-t border-line">
                        <td className="py-2 pr-3">{line.line}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {formatDate(line.trade_date)}
                        </td>
                        <td className="py-2 pr-3">{TRANSACTION_TYPE_LABELS[line.type]}</td>
                        <td className="py-2 pr-3">{line.instrument_name ?? '—'}</td>
                        <td className="py-2 pr-3">
                          {line.quantity ? formatQuantity(line.quantity) : '—'}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {line.unit_price ? formatMoney(line.unit_price, account.currency) : '—'}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap">
                          {line.amount ? formatMoney(line.amount, account.currency) : '—'}
                        </td>
                        <td className="py-2 pr-3">{line.label ?? '—'}</td>
                        <td className="py-2">
                          {line.status === 'duplicate' ? 'Déjà présente' : 'Nouvelle'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-medium">Réglages du fichier</summary>
              {settings && (
                <div className="grid gap-x-6 sm:grid-cols-2">
                  <SelectField
                    id="set-delimiter"
                    label="Séparateur de colonnes"
                    value={settings.delimiter}
                    onChange={(value) => setSettings({ ...settings, delimiter: value })}
                    options={DELIMITERS}
                  />
                  <SelectField
                    id="set-encoding"
                    label="Encodage"
                    value={settings.encoding}
                    onChange={(value) => setSettings({ ...settings, encoding: value })}
                    options={(ENCODINGS.includes(settings.encoding)
                      ? ENCODINGS
                      : [settings.encoding, ...ENCODINGS]
                    ).map((value) => ({ value, label: value }))}
                  />
                  <SelectField
                    id="set-date"
                    label="Format des dates"
                    value={settings.date_format}
                    onChange={(value) => setSettings({ ...settings, date_format: value })}
                    options={DATE_FORMATS}
                  />
                  <SelectField
                    id="set-decimal"
                    label="Séparateur décimal"
                    value={settings.decimal_separator}
                    onChange={(value) => setSettings({ ...settings, decimal_separator: value })}
                    options={DECIMALS}
                  />
                </div>
              )}
              <button
                type="button"
                className={`${secondaryButtonClass} mt-3`}
                disabled={analyse.isPending}
                onClick={() => analyse.mutate({ columns, settings: settings ?? undefined })}
              >
                Analyser à nouveau
              </button>
            </details>
          </div>

          {rejected.length > 0 && (
            <div className={cardClass}>
              <h3 className="font-medium">Lignes invalides</h3>
              <div className="mt-3 overflow-x-auto">
                <table aria-label="Lignes invalides" className="w-full text-left text-sm">
                  <thead className="text-muted">
                    <tr>
                      <th scope="col" className="py-2 pr-4 font-medium">
                        Ligne
                      </th>
                      <th scope="col" className="py-2 font-medium">
                        Cause
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rejected.slice(0, MAX_REJECTED_SHOWN).map((item) => (
                      <tr key={item.line} className="border-t border-line">
                        <td className="py-2 pr-4">{item.line}</td>
                        <td className="py-2">{item.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rejected.length > MAX_REJECTED_SHOWN && (
                <p className="mt-2 text-sm text-muted">
                  … et {rejected.length - MAX_REJECTED_SHOWN} autres lignes invalides.
                </p>
              )}
              <label className="mt-4 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={confirmRejected}
                  onChange={(event) => setConfirmRejected(event.target.checked)}
                />
                Importer quand même les lignes valides
              </label>
            </div>
          )}

          {unknown.length > 0 && (
            <UnknownInstrumentsPanel
              items={unknown}
              instruments={instruments.data ?? []}
              choices={choices}
              onChange={setChoices}
            />
          )}

          {preview.rows_valid === 0 ? (
            <p className="text-muted">
              Rien de nouveau à importer : toutes les lignes valides sont déjà présentes ou
              écartées.
            </p>
          ) : (
            <div className={cardClass}>
              {!preview.mapping_id && (
                <TextField
                  id="save-mapping"
                  label="Enregistrer ces réglages sous le nom"
                  value={saveName}
                  onChange={setSaveName}
                  hint="Facultatif. Proposés automatiquement au prochain fichier du même établissement."
                />
              )}
              {blockedByRejected && (
                <p className="mt-3 text-sm text-muted">
                  Confirmez l’import partiel ci-dessus, ou corrigez le fichier.
                </p>
              )}
              {unresolved && (
                <p className="mt-3 text-sm text-muted">
                  Décidez du sort de chaque actif inconnu pour pouvoir importer.
                </p>
              )}
              <button
                type="button"
                className={`${buttonClass} mt-4`}
                disabled={blockedByRejected || unresolved || commit.isPending}
                onClick={submit}
              >
                {commit.isPending
                  ? 'Import en cours…'
                  : `Importer ${plural(preview.rows_valid, 'ligne', 'lignes')}`}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
