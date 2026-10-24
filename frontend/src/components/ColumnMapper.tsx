import { IMPORT_FIELDS, IMPORT_FIELD_ORDER, type ImportField } from '../lib/import-columns'
import { SelectField } from './fields'

interface ColumnMapperProps {
  headers: string[]
  columns: Record<string, string>
  onChange: (columns: Record<string, string>) => void
  errors?: Partial<Record<string, string>>
}

/** Associe chaque donnée d'opération à une colonne du fichier. */
export default function ColumnMapper({
  headers,
  columns,
  onChange,
  errors = {},
}: ColumnMapperProps) {
  function choose(field: ImportField, header: string) {
    const next = { ...columns }
    if (header === '') delete next[field]
    else next[field] = header
    onChange(next)
  }

  return (
    <div className="grid gap-x-6 sm:grid-cols-2">
      {IMPORT_FIELD_ORDER.map((key) => {
        const info = IMPORT_FIELDS.find((item) => item.key === key)!
        return (
          <SelectField
            key={key}
            id={`col-${key}`}
            label={info.required ? `${info.label} (obligatoire)` : info.label}
            value={columns[key] ?? ''}
            onChange={(header) => choose(key, header)}
            options={headers.map((header) => ({ value: header, label: header }))}
            placeholder="Non utilisée"
            error={errors[key]}
          />
        )
      })}
    </div>
  )
}
