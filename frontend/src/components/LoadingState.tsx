interface LoadingStateProps {
  label?: string
  className?: string
}

/** Indicateur de chargement annoncé aux technologies d'assistance. */
export default function LoadingState({ label = 'Chargement…', className = '' }: LoadingStateProps) {
  return (
    <p role="status" className={`text-muted ${className}`.trim()}>
      {label}
    </p>
  )
}
