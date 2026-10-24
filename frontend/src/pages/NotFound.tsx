import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section>
      <h2 className="text-xl font-semibold">Page introuvable</h2>
      <p className="mt-2">
        <Link className="text-brand underline" to="/">
          Retour au tableau de bord
        </Link>
      </p>
    </section>
  )
}
