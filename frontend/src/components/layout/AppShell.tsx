import { Menu, Plus, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '../../stores/auth'
import { Button } from '../ui/button'

const navItems = [
  { to: '/', label: 'Agentes', end: true },
  { to: '/wizard', label: 'Crear agente' },
  { to: '/usage', label: 'Uso' },
  { to: '/providers', label: 'Bóveda IA' },
  { to: '/custom-tools', label: 'Mis tools' },
  { to: '/keys', label: 'API Keys' },
]

const libraryItems = [
  { to: '/skills', label: 'Skills' },
  { to: '/mcp', label: 'MCPs' },
  { to: '/knowledge-bases', label: 'Conocimiento' },
]

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const clearToken = useAuthStore((state) => state.clearToken)
  const navigate = useNavigate()
  const location = useLocation()

  const pageTitle = useMemo(() => {
    const match = [...navItems, ...libraryItems].find((item) => item.to === location.pathname)
    if (match) return match.label
    if (location.pathname.startsWith('/agents/')) return 'Monitor'
    return 'Agentica'
  }, [location.pathname])

  const logout = () => {
    clearToken()
    navigate('/login')
  }

  const docsHref = `${import.meta.env.VITE_API_URL || ''}/docs`

  return (
    <div className="flex min-h-screen bg-[radial-gradient(circle_at_top,#f5f3ff,transparent_38%),linear-gradient(180deg,#f8fafc,white)]">
      {mobileOpen && (
        <button
          className="fixed inset-0 z-40 bg-slate-950/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-800 bg-slate-950 text-slate-100 transition-transform duration-200 md:relative md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="border-b border-slate-800 px-6 py-5">
          <button className="flex items-center gap-3 text-left" onClick={() => navigate('/')}>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-600/20 text-violet-300">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="text-lg font-semibold tracking-tight">Agentica</div>
              <div className="text-sm text-slate-400">Control de agentes IA</div>
            </div>
          </button>
          <Button className="mt-5 w-full justify-start" onClick={() => navigate('/wizard')}>
            <Plus className="h-4 w-4" />
            Nuevo agente
          </Button>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-6">
          <div className="space-y-1">
            {navItems.map((item) => (
              <ShellNavItem key={item.to} {...item} onNavigate={() => setMobileOpen(false)} />
            ))}
          </div>

          <div className="mt-8">
            <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Librería
            </p>
            <div className="space-y-1">
              {libraryItems.map((item) => (
                <ShellNavItem key={item.to} {...item} onNavigate={() => setMobileOpen(false)} />
              ))}
            </div>
          </div>
        </nav>

        <div className="border-t border-slate-800 p-4">
          <a
            href={docsHref}
            target="_blank"
            rel="noreferrer"
            className="block rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
          >
            API Docs
          </a>
          <button
            onClick={logout}
            className="mt-2 block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-400 transition hover:bg-slate-900 hover:text-white"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 md:px-8">
            <div className="flex items-center gap-3">
              <button
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-600 md:hidden"
                onClick={() => setMobileOpen(true)}
              >
                <Menu className="h-5 w-5" />
              </button>
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-600">
                  Workspace
                </div>
                <h1 className="text-lg font-semibold text-slate-950">{pageTitle}</h1>
              </div>
            </div>
            <div className="hidden text-sm text-slate-500 md:block">
              Diseño, monitoreo y operación desde una sola consola.
            </div>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

function ShellNavItem({
  to,
  label,
  end,
  onNavigate,
}: {
  to: string
  label: string
  end?: boolean
  onNavigate: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `block rounded-lg px-3 py-2.5 text-sm transition ${
          isActive
            ? 'bg-violet-600 text-white shadow-sm'
            : 'text-slate-300 hover:bg-slate-900 hover:text-white'
        }`
      }
    >
      {label}
    </NavLink>
  )
}
