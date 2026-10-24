import { useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'

import { AUTH_STATUS_KEY, lockInstance } from '../api/auth'
import { BRAND } from '../brand'
import { NAV_ITEMS } from '../nav'
import ExportReminder from './ExportReminder'
import Logo from './Logo'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-brand-soft text-ink' : 'text-muted'}`

/** Barre latérale sur ordinateur, barre basse sur téléphone ; jamais de défilement horizontal. */
export default function Layout() {
  const queryClient = useQueryClient()

  async function lock() {
    try {
      await lockInstance()
    } finally {
      await queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })
    }
  }

  return (
    <div className="min-h-screen overflow-x-hidden md:grid md:grid-cols-[14rem_1fr]">
      <aside className="border-b border-line bg-card p-4 md:min-h-screen md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-3 md:block">
          <div className="flex items-center gap-3">
            <Logo />
            <h1 className="text-lg font-semibold">{BRAND.name}</h1>
          </div>
          <button
            type="button"
            onClick={lock}
            className="rounded-lg border border-line px-3 py-1.5 text-sm md:mt-4 md:w-full"
          >
            Verrouiller
          </button>
        </div>
        <nav
          aria-label="Navigation principale"
          className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-line bg-card p-2 md:static md:mt-6 md:flex-col md:justify-start md:border-0 md:p-0"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} className={linkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-col pb-16 md:pb-0">
        <ExportReminder />
        <main className="flex-1 p-4 md:p-8">
          <Outlet />
        </main>
        <footer className="border-t border-line p-4 text-xs text-muted">{BRAND.disclaimer}</footer>
      </div>
    </div>
  )
}
