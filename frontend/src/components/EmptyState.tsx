import { Link } from 'react-router-dom'

/** Écran d'accueil quand il n'y a encore aucun compte : un seul geste à faire, bien visible. */
export default function EmptyState() {
  return (
    <div className="rounded-2xl border border-line bg-card p-6 shadow-sm">
      <h3 className="text-lg font-semibold">Commencez par créer un compte</h3>
      <p className="mt-2 text-muted">
        PEA, compte-titres, assurance-vie, PEE ou Livret A : ajoutez un premier compte, puis vos
        opérations. Le tableau de bord se remplit au fur et à mesure.
      </p>
      <Link
        to="/comptes"
        className="mt-4 inline-block rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink"
      >
        Créer un compte
      </Link>
    </div>
  )
}
