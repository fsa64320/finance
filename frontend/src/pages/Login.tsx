import { type FormEvent, useEffect, useState } from 'react'

import { setupPassword, unlockInstance } from '../api/auth'
import { ApiError } from '../api/client'
import Logo from '../components/Logo'
import { BRAND } from '../brand'

const MIN_LENGTH = 12
const MAX_LENGTH = 128

export type LoginMode = 'setup' | 'unlock'

interface LoginProps {
  mode: LoginMode
  onSuccess: () => void
}

function seconds(count: number): string {
  return `${count} seconde${count > 1 ? 's' : ''}`
}

const inputClass =
  'mt-1 block w-full rounded-lg border border-line bg-card px-3 py-2 text-ink shadow-sm'
const buttonClass =
  'mt-4 w-full rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink disabled:opacity-50'

export default function Login({ mode, onSuccess }: LoginProps) {
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [retryIn, setRetryIn] = useState(0)

  useEffect(() => {
    if (retryIn <= 0) return
    const timer = setTimeout(() => setRetryIn((remaining) => remaining - 1), 1000)
    return () => clearTimeout(timer)
  }, [retryIn])

  const isSetup = mode === 'setup'

  function validateLocally(): string | null {
    if (password.length < MIN_LENGTH) {
      return `Le mot de passe doit faire au moins ${MIN_LENGTH} caractères.`
    }
    if (password.length > MAX_LENGTH) {
      return `Le mot de passe doit faire au plus ${MAX_LENGTH} caractères.`
    }
    if (password !== confirmation) return 'Les deux mots de passe ne correspondent pas.'
    return null
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending || retryIn > 0) return
    if (isSetup) {
      const problem = validateLocally()
      if (problem) {
        setError(problem)
        return
      }
    }
    setError(null)
    setPending(true)
    try {
      await (isSetup ? setupPassword(password) : unlockInstance(password))
      setPassword('')
      setConfirmation('')
      onSuccess()
    } catch (failure) {
      setPassword('')
      setConfirmation('')
      if (failure instanceof ApiError && failure.status === 429) {
        setRetryIn(failure.retryAfter ?? 1)
      } else if (failure instanceof ApiError && failure.status === 401) {
        setError('Mot de passe incorrect.')
      } else if (failure instanceof ApiError && failure.details?.[0]) {
        setError(failure.details[0].message)
      } else if (failure instanceof ApiError) {
        setError(failure.message)
      } else {
        setError('Une erreur inattendue est survenue.')
      }
    } finally {
      setPending(false)
    }
  }

  const message = retryIn > 0 ? `Trop d'essais. Réessayez dans ${seconds(retryIn)}.` : error

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-4">
      <header className="flex items-center gap-3">
        <Logo className="h-10 w-10" />
        <div>
          <h1 className="text-2xl font-semibold">{BRAND.name}</h1>
          <p className="text-sm text-muted">{BRAND.tagline}</p>
        </div>
      </header>

      <form
        onSubmit={submit}
        className="rounded-2xl border border-line bg-card p-5 shadow-sm"
        noValidate
      >
        <h2 className="text-lg font-medium">
          {isSetup ? 'Créer votre mot de passe' : 'Déverrouiller'}
        </h2>

        {isSetup && (
          <>
            <div role="note" className="mt-3 rounded-lg bg-warn-bg p-3 text-sm text-warn-ink">
              <strong>Ce mot de passe ne peut pas être récupéré.</strong> Si vous l'oubliez, vos
              données seront irrécupérables. Exportez régulièrement vos données depuis les réglages.
            </div>
            <ul className="mt-3 list-disc pl-5 text-sm text-muted">
              <li>Entre 12 et 128 caractères</li>
              <li>Ni trop courant, ni une suite ou une répétition de caractères</li>
              <li>Une phrase de passe est plus sûre qu'un mot unique</li>
            </ul>
          </>
        )}

        <label className="mt-4 block text-sm font-medium" htmlFor="password">
          Mot de passe
        </label>
        <input
          id="password"
          type="password"
          className={inputClass}
          autoComplete={isSetup ? 'new-password' : 'current-password'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoFocus
        />

        {isSetup && (
          <>
            <label className="mt-3 block text-sm font-medium" htmlFor="confirmation">
              Confirmer le mot de passe
            </label>
            <input
              id="confirmation"
              type="password"
              className={inputClass}
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </>
        )}

        {message && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {message}
          </p>
        )}

        <button type="submit" className={buttonClass} disabled={pending || retryIn > 0}>
          {isSetup ? 'Créer le mot de passe' : 'Déverrouiller'}
        </button>
      </form>
    </main>
  )
}
