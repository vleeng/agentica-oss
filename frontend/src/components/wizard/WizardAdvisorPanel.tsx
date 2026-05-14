import { AlertTriangle, CheckCircle2, HelpCircle, Lightbulb, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import type { WizardAdvisorItem, WizardAdvisorResponse, WizardState } from '../../types/agent'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'

interface Props {
  enabled: boolean
  loading: boolean
  result: WizardAdvisorResponse | null
  error: string
  onToggle: (enabled: boolean) => void
  onAnalyze: (finalReview?: boolean) => void
  onApplyPatch: (patch: Partial<WizardState>) => void
}

const statusTone = {
  ready: 'green',
  requires_review: 'amber',
  high_risk: 'rose',
} as const

const statusLabel = {
  ready: 'Listo',
  requires_review: 'Revisar',
  high_risk: 'Riesgo alto',
}

export function WizardAdvisorPanel({
  enabled,
  loading,
  result,
  error,
  onToggle,
  onAnalyze,
  onApplyPatch,
}: Props) {
  const hasPatch = result && Object.keys(result.proposed_patch || {}).length > 0

  return (
    <aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-violet-600" />
            <h3 className="text-sm font-semibold text-slate-950">Asistente de diseño</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Revisa alcance, riesgos y coherencia antes de generar.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onToggle(!enabled)}
          className={`relative h-6 w-11 shrink-0 rounded-full transition ${enabled ? 'bg-violet-600' : 'bg-slate-300'}`}
          aria-label="Activar asistente de diseño"
        >
          <span
            className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${enabled ? 'left-6' : 'left-1'}`}
          />
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={enabled ? 'primary' : 'secondary'}
          disabled={!enabled || loading}
          onClick={() => onAnalyze(false)}
        >
          <Sparkles className="h-3.5 w-3.5" />
          {loading ? 'Analizando...' : 'Analizar paso'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={!enabled || loading}
          onClick={() => onAnalyze(true)}
        >
          Revisión final
        </Button>
      </div>

      {!enabled && (
        <div className="mt-4 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs leading-5 text-slate-500">
          Activá el asistente cuando quieras validar un objetivo, una selección de tools o el diseño completo.
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
          {error}
        </div>
      )}

      {result && enabled && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-2">
              <Badge tone={statusTone[result.status]}>{statusLabel[result.status]}</Badge>
              <span className="text-sm font-semibold text-slate-950">{result.score}/100</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-600">{result.summary}</p>
            <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-400">
              Fuente: {result.source === 'ai' ? 'IA' : 'reglas'}
            </p>
          </div>

          <AdvisorSection title="Riesgos" icon={<AlertTriangle className="h-3.5 w-3.5" />} items={result.risks} />
          <AdvisorSection title="Preguntas" icon={<HelpCircle className="h-3.5 w-3.5" />} items={result.questions} />
          <AdvisorSection title="Sugerencias" icon={<Lightbulb className="h-3.5 w-3.5" />} items={result.suggestions} />

          {hasPatch && (
            <div className="rounded-lg border border-violet-200 bg-violet-50 p-3">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-violet-700" />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-violet-900">Mejora aplicable</div>
                  <p className="mt-1 text-xs leading-5 text-violet-800">
                    El asistente propone ajustar el estado del wizard con un cambio seguro.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    className="mt-3"
                    onClick={() => onApplyPatch(result.proposed_patch)}
                  >
                    Aplicar mejora
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  )
}

function AdvisorSection({
  title,
  icon,
  items,
}: {
  title: string
  icon: ReactNode
  items: WizardAdvisorItem[]
}) {
  if (!items.length) return null

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {icon}
        {title}
      </div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={`${item.title}-${index}`} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <div className="text-xs font-semibold text-slate-900">{item.title}</div>
              <SeverityBadge severity={item.severity} />
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">{item.detail}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function SeverityBadge({ severity }: { severity: WizardAdvisorItem['severity'] }) {
  const tone = severity === 'critical' ? 'rose' : severity === 'warning' ? 'amber' : 'slate'
  const label = severity === 'critical' ? 'Crítico' : severity === 'warning' ? 'Atención' : 'Info'
  return <Badge tone={tone} className="shrink-0 px-2 py-0.5 text-[10px]">{label}</Badge>
}
