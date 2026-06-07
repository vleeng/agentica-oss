import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  Building2,
  CircleUserRound,
  Code2,
  ExternalLink,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Server,
  Shield,
  Wand2,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useProductProfile } from '../../contexts/ProductProfileContext'
import { getProductBranding } from '../../lib/productBranding'
import { getAuthRole, useAuthStore } from '../../stores/auth'
import { Button } from '../ui/button'

const navItems = [
  { to: '/', label: 'Agentes', end: true, icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/wizard', label: 'Crear agente', icon: <Wand2 className="h-4 w-4" /> },
  { to: '/usage', label: 'Observabilidad', icon: <BarChart3 className="h-4 w-4" /> },
  { to: '/account', label: 'Cuenta', icon: <CircleUserRound className="h-4 w-4" /> },
  { to: '/access', label: 'Accesos', icon: <Building2 className="h-4 w-4" /> },
  { to: '/providers', label: 'Boveda IA', icon: <Shield className="h-4 w-4" /> },
  { to: '/custom-tools', label: 'Mis tools', icon: <Code2 className="h-4 w-4" /> },
  { to: '/keys', label: 'API Keys', icon: <KeyRound className="h-4 w-4" /> },
]

const libraryItems = [
  { to: '/skills', label: 'Skills', icon: <Zap className="h-4 w-4" /> },
  { to: '/mcp', label: 'MCPs', icon: <Server className="h-4 w-4" /> },
  { to: '/knowledge-bases', label: 'Conocimiento', icon: <BookOpen className="h-4 w-4" /> },
]

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const clearToken = useAuthStore((state) => state.clearToken)
  const navigate = useNavigate()
  const location = useLocation()
  const role = getAuthRole()
  const product = useProductProfile()
  const branding = useMemo(() => getProductBranding(product), [product])
  const isViewer = role === 'viewer'
  const isOwner = role === 'owner'

  const visibleNavItems = useMemo(
    () =>
      navItems.filter((item) => {
        if (item.to === '/usage' && !product.features.billing) return false
        if (isViewer) return ['/', '/usage', '/account'].includes(item.to)
        if (item.to === '/access') return isOwner
        return true
      }),
    [isOwner, isViewer, product.features.billing]
  )
  const visibleLibraryItems = useMemo(() => (isViewer ? [] : libraryItems), [isViewer])

  const pageTitle = useMemo(() => {
    const match = [...visibleNavItems, ...visibleLibraryItems].find((item) => item.to === location.pathname)
    if (match) return match.label
    if (location.pathname.startsWith('/agents/')) return 'Monitor'
    return branding.appName
  }, [branding.appName, location.pathname, visibleLibraryItems, visibleNavItems])

  const logout = () => {
    clearToken()
    navigate('/login')
  }

  const docsHref = `${import.meta.env.VITE_API_URL || ''}/docs`

  useEffect(() => {
    console.info('[Agentica][Nav] route', { pathname: location.pathname, role })
  }, [location.pathname, role])

  return (
    <div className="flex min-h-screen bg-slate-50">
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
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-900/40">
              <BrainCircuit className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="text-lg font-semibold tracking-tight">{branding.appName}</div>
              <div className="text-xs text-slate-400">{branding.shellSubtitle}</div>
            </div>
          </button>
          {!isViewer && (
            <Button className="mt-5 w-full justify-start" onClick={() => navigate('/wizard')}>
              <Plus className="h-4 w-4" />
              Nuevo agente
            </Button>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-6">
          <div className="space-y-0.5">
            {visibleNavItems.map((item) => (
              <ShellNavItem key={item.to} {...item} onNavigate={() => setMobileOpen(false)} />
            ))}
          </div>

          {visibleLibraryItems.length > 0 && (
            <div className="mt-6">
              <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Libreria
              </p>
              <div className="space-y-0.5">
                {visibleLibraryItems.map((item) => (
                  <ShellNavItem key={item.to} {...item} onNavigate={() => setMobileOpen(false)} />
                ))}
              </div>
            </div>
          )}
        </nav>

        <div className="space-y-1 border-t border-slate-800 p-4">
          <a
            href={docsHref}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-slate-800/70 hover:text-white"
          >
            <ExternalLink className="h-4 w-4 shrink-0" />
            API Docs
          </a>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-slate-400 transition hover:bg-rose-900/40 hover:text-rose-300"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Cerrar sesion
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-slate-200/60 bg-white/90 backdrop-blur-md">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 md:px-8">
            <div className="flex items-center gap-3">
              <button
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 md:hidden"
                onClick={() => setMobileOpen(true)}
              >
                <Menu className="h-4 w-4" />
              </button>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-violet-500">
                  {branding.workspaceLabel}
                </div>
                <h1 className="text-base font-semibold leading-tight text-slate-950">{pageTitle}</h1>
              </div>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              <span className="text-xs text-slate-400">{branding.consoleLabel}</span>
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
  icon,
  onNavigate,
}: {
  to: string
  label: string
  end?: boolean
  icon?: ReactNode
  onNavigate: () => void
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
          isActive
            ? 'bg-violet-600/90 text-white shadow-sm shadow-violet-900/30'
            : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
        }`
      }
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {label}
    </NavLink>
  )
}
