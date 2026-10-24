import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AUTH_STATUS_KEY, getAuthStatus } from './api/auth'
import Layout from './components/Layout'
import AccountDetail from './pages/AccountDetail'
import Accounts from './pages/Accounts'
import Dashboard from './pages/Dashboard'
import Import from './pages/Import'
import Instruments from './pages/Instruments'
import Login from './pages/Login'
import NotFound from './pages/NotFound'

function AuthGate() {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: AUTH_STATUS_KEY, queryFn: getAuthStatus, retry: false })
  const refresh = () => queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })

  if (status.isPending) {
    return (
      <p role="status" className="p-8 text-muted">
        Chargement…
      </p>
    )
  }
  if (status.isError) {
    return (
      <div role="alert" className="mx-auto max-w-md p-8">
        <p>Impossible de joindre le serveur. Vérifiez qu'il est démarré, puis réessayez.</p>
        <button
          type="button"
          className="mt-4 rounded-lg border border-line px-3 py-1.5"
          onClick={() => void status.refetch()}
        >
          Réessayer
        </button>
      </div>
    )
  }
  if (status.data === 'uninitialized') return <Login mode="setup" onSuccess={refresh} />
  if (status.data === 'locked') return <Login mode="unlock" onSuccess={refresh} />

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="comptes" element={<Accounts />} />
          <Route path="comptes/:accountId" element={<AccountDetail />} />
          <Route path="actifs" element={<Instruments />} />
          <Route path="import" element={<Import />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  const [queryClient] = useState(() => new QueryClient())
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  )
}
