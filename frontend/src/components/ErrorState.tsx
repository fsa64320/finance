interface ErrorStateProps {
  message: string
  onRetry?: () => void
  className?: string
}

/** Erreur annoncée, avec la cause et, quand c'est utile, une nouvelle tentative. */
export default function ErrorState({ message, onRetry, className = '' }: ErrorStateProps) {
  return (
    <div role="alert" className={`text-danger ${className}`.trim()}>
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          className="mt-2 rounded-lg border border-line px-3 py-1.5 text-sm text-ink"
          onClick={onRetry}
        >
          Réessayer
        </button>
      )}
    </div>
  )
}
