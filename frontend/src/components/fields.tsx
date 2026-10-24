import type { ReactNode } from 'react'

const inputClass =
  'mt-1 block w-full rounded-lg border border-line bg-card px-3 py-2 text-ink shadow-sm'

interface FieldShellProps {
  id: string
  label: string
  error?: string
  hint?: string
  children: (describedBy: string | undefined) => ReactNode
}

function FieldShell({ id, label, error, hint, children }: FieldShellProps) {
  const messageId = `${id}-message`
  const text = error ?? hint
  return (
    <div className="mt-3">
      <label className="block text-sm font-medium" htmlFor={id}>
        {label}
      </label>
      {children(text ? messageId : undefined)}
      {text && (
        <p id={messageId} className={`mt-1 text-sm ${error ? 'text-danger' : 'text-muted'}`}>
          {text}
        </p>
      )}
    </div>
  )
}

interface TextFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  error?: string
  hint?: string
  type?: 'text' | 'date'
  inputMode?: 'decimal' | 'text'
  autoComplete?: string
  placeholder?: string
}

export function TextField({
  id,
  label,
  value,
  onChange,
  error,
  hint,
  type = 'text',
  inputMode,
  autoComplete,
  placeholder,
}: TextFieldProps) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint}>
      {(describedBy) => (
        <input
          id={id}
          type={type}
          className={inputClass}
          value={value}
          inputMode={inputMode}
          autoComplete={autoComplete}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FieldShell>
  )
}

interface SelectFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  error?: string
  placeholder?: string
}

export function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  error,
  placeholder,
}: SelectFieldProps) {
  return (
    <FieldShell id={id} label={label} error={error}>
      {(describedBy) => (
        <select
          id={id}
          className={inputClass}
          value={value}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value)}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  )
}

export const buttonClass =
  'rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink disabled:opacity-50'
export const secondaryButtonClass = 'rounded-lg border border-line px-4 py-2 font-medium'
export const smallButtonClass = 'rounded-md border border-line px-2 py-1 text-xs'
