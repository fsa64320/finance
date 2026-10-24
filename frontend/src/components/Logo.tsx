/** Marque du projet : trois barres ascendantes dans un carré arrondi. Dessin original. */
export default function Logo({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="var(--brand)" />
      <rect x="7" y="17" width="4.5" height="8" rx="1.2" fill="var(--brand-ink)" />
      <rect x="13.75" y="12" width="4.5" height="13" rx="1.2" fill="var(--brand-ink)" />
      <rect x="20.5" y="7" width="4.5" height="18" rx="1.2" fill="var(--brand-ink)" />
    </svg>
  )
}
