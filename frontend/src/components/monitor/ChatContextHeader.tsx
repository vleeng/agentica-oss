import type { ReactNode } from 'react'

import { Bot, Building2, Fingerprint, Globe, UserRound } from 'lucide-react'

import { Badge } from '../ui/badge'

interface Props {
  agentName: string
  agentId: string
  tenantName?: string | null
  tenantId?: string | null
  userName?: string | null
  userEmail?: string | null
  environmentLabel: string
  channelLabel: string
}

function shortId(value: string | null | undefined) {
  return value ? value.slice(0, 8) : '...'
}

export function ChatContextHeader({
  agentName,
  agentId,
  tenantName,
  tenantId,
  userName,
  userEmail,
  environmentLabel,
  channelLabel,
}: Props) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="violet">{environmentLabel}</Badge>
        <Badge tone="blue">{channelLabel}</Badge>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <ContextItem
          icon={<Bot className="h-4 w-4" />}
          label="Agente"
          primary={agentName}
          secondary={`id: ${shortId(agentId)}`}
        />
        <ContextItem
          icon={<UserRound className="h-4 w-4" />}
          label="Usuario"
          primary={userName || userEmail || 'Visitante externo'}
          secondary={userEmail && userName ? userEmail : userName || undefined}
        />
        <ContextItem
          icon={<Building2 className="h-4 w-4" />}
          label="Tenant"
          primary={tenantName || 'Tenant no expuesto'}
          secondary={tenantId ? `id: ${shortId(tenantId)}` : undefined}
        />
        <ContextItem
          icon={<Globe className="h-4 w-4" />}
          label="Entorno"
          primary={environmentLabel}
          secondary={channelLabel}
        />
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <Fingerprint className="h-3.5 w-3.5" />
        <span>
          Contexto operativo visible para identificar rápido el agente y el workspace desde donde se usa.
        </span>
      </div>
    </div>
  )
}

function ContextItem({
  icon,
  label,
  primary,
  secondary,
}: {
  icon: ReactNode
  label: string
  primary: string
  secondary?: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-slate-500">
        <span className="text-violet-600">{icon}</span>
        <span>{label}</span>
      </div>
      <div className="mt-2 text-sm font-medium text-slate-900">{primary}</div>
      {secondary && <div className="mt-1 text-xs text-slate-500">{secondary}</div>}
    </div>
  )
}
