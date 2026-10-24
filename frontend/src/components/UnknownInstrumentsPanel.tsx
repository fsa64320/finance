import type { Instrument, InstrumentKind } from '../api/types'
import type { Choice, UnknownInstrument } from '../lib/import-resolutions'
import { INSTRUMENT_KIND_LABELS } from '../lib/labels'
import { SelectField } from './fields'

const KIND_OPTIONS = (Object.keys(INSTRUMENT_KIND_LABELS) as InstrumentKind[]).map((kind) => ({
  value: kind,
  label: INSTRUMENT_KIND_LABELS[kind],
}))

const ACTIONS: { action: Choice['action']; label: string }[] = [
  { action: 'create', label: 'Créer cet actif' },
  { action: 'link', label: 'Rattacher à un actif existant' },
  { action: 'skip', label: 'Ignorer ces lignes' },
]

interface UnknownInstrumentsPanelProps {
  items: UnknownInstrument[]
  instruments: Instrument[]
  choices: Record<string, Choice>
  onChange: (choices: Record<string, Choice>) => void
}

/** Pour chaque actif du fichier que l'application ne connaît pas : créer, rattacher ou ignorer. */
export default function UnknownInstrumentsPanel({
  items,
  instruments,
  choices,
  onChange,
}: UnknownInstrumentsPanelProps) {
  const set = (key: string, choice: Choice) => onChange({ ...choices, [key]: choice })

  return (
    <section className="rounded-2xl border border-line bg-card p-5 shadow-sm">
      <h3 className="font-medium">Actifs inconnus</h3>
      <p className="mt-1 text-sm text-muted">
        Ces actifs ne sont pas encore dans l’application : rien n’est créé avant la validation.
        Choisissez ce qu’il faut en faire.
      </p>
      {items.map((item, index) => {
        const choice = choices[item.key]
        const rows = item.rows ?? 0
        return (
          <fieldset key={item.key} className="mt-4 border-t border-line pt-3">
            <legend className="font-medium">{item.name}</legend>
            <p className="text-sm text-muted">
              {item.isin ? `${item.isin} · ` : ''}
              {rows} {rows > 1 ? 'lignes' : 'ligne'}
            </p>
            <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
              {ACTIONS.map(({ action, label }) => (
                <label key={action} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name={`unknown-${index}`}
                    checked={choice?.action === action}
                    onChange={() => set(item.key, { action })}
                  />
                  {label}
                </label>
              ))}
            </div>
            {choice?.action === 'create' && (
              <SelectField
                id={`kind-${index}`}
                label="Type de l'actif"
                value={choice.kind ?? ''}
                onChange={(kind) =>
                  set(item.key, { action: 'create', kind: kind as InstrumentKind })
                }
                options={KIND_OPTIONS}
                placeholder="Choisir un type"
              />
            )}
            {choice?.action === 'link' && (
              <SelectField
                id={`link-${index}`}
                label="Actif existant"
                value={choice.instrumentId ?? ''}
                onChange={(instrumentId) => set(item.key, { action: 'link', instrumentId })}
                options={instruments.map((instrument) => ({
                  value: instrument.id,
                  label: instrument.name,
                }))}
                placeholder="Choisir un actif"
              />
            )}
          </fieldset>
        )
      })}
    </section>
  )
}
