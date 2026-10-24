import { type FormEvent, useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import ConfirmDialog from './ConfirmDialog'
import { TextField, buttonClass } from './fields'

const MIN_LENGTH = 12
const MAX_LENGTH = 128

interface ChangePasswordFormProps {
  onSubmit: (current: string, next: string) => Promise<unknown>
}

function seconds(count: number): string {
  return `${count} seconde${count > 1 ? 's' : ''}`
}

/** Changement du mot de passe (FR-033) : l'ancien est exigé et cesse de fonctionner ensuite. */
export default function ChangePasswordForm({ onSubmit }: ChangePasswordFormProps) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [pending, setPending] = useState(false)
  const [retryIn, setRetryIn] = useState(0)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    if (retryIn <= 0) return
    const timer = setTimeout(() => setRetryIn((remaining) => remaining - 1), 1000)
    return () => clearTimeout(timer)
  }, [retryIn])

  function problem(): string | null {
    if (current === '') return 'Saisissez votre mot de passe actuel.'
    if (next.length < MIN_LENGTH) {
      return `Le nouveau mot de passe doit faire au moins ${MIN_LENGTH} caractères.`
    }
    if (next.length > MAX_LENGTH) {
      return `Le nouveau mot de passe doit faire au plus ${MAX_LENGTH} caractères.`
    }
    if (next === current) return "Le nouveau mot de passe doit différer de l'actuel."
    if (next !== confirmation) return 'Les deux nouveaux mots de passe ne correspondent pas.'
    return null
  }

  function clear() {
    setCurrent('')
    setNext('')
    setConfirmation('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (pending || retryIn > 0) return
    setDone(false)
    const local = problem()
    if (local) {
      setError(local)
      return
    }
    setError(null)
    setConfirming(true)
  }

  async function apply() {
    setConfirming(false)
    setPending(true)
    try {
      await onSubmit(current, next)
      clear()
      setDone(true)
    } catch (failure) {
      clear()
      if (failure instanceof ApiError && failure.status === 429) {
        setRetryIn(failure.retryAfter ?? 1)
      } else if (failure instanceof ApiError && failure.status === 401) {
        setError('Votre mot de passe actuel est incorrect.')
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
    <form onSubmit={submit} noValidate aria-label="Changer le mot de passe" className="max-w-md">
      <p className="text-sm text-muted">
        Le nouveau mot de passe doit faire entre 12 et 128 caractères, sans être trop courant. Vos
        données sont rechiffrées avec lui : l’ancien cesse de fonctionner tout de suite. Il ne peut
        pas être récupéré en cas d’oubli.
      </p>
      <TextField
        id="pwd-current"
        label="Mot de passe actuel"
        type="password"
        autoComplete="current-password"
        value={current}
        onChange={setCurrent}
      />
      <TextField
        id="pwd-new"
        label="Nouveau mot de passe"
        type="password"
        autoComplete="new-password"
        value={next}
        onChange={setNext}
      />
      <TextField
        id="pwd-confirm"
        label="Confirmer le nouveau mot de passe"
        type="password"
        autoComplete="new-password"
        value={confirmation}
        onChange={setConfirmation}
      />
      {message && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {message}
        </p>
      )}
      {done && (
        <p role="status" className="mt-3 text-sm">
          Mot de passe changé. L’ancien ne fonctionne plus : utilisez le nouveau au prochain
          déverrouillage.
        </p>
      )}
      <button type="submit" className={`${buttonClass} mt-4`} disabled={pending || retryIn > 0}>
        Changer le mot de passe
      </button>
      <ConfirmDialog
        open={confirming}
        title="Changer le mot de passe ?"
        description="Vos données seront rechiffrées avec le nouveau mot de passe, et l'ancien mot de passe cessera de fonctionner immédiatement. Aucun moyen ne permet de récupérer un mot de passe oublié."
        confirmLabel="Changer le mot de passe"
        cancelLabel="Annuler"
        onCancel={() => setConfirming(false)}
        onConfirm={() => void apply()}
      />
    </form>
  )
}
