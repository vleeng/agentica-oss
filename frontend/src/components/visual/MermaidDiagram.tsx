import mermaid from 'mermaid'
import type { ReactNode } from 'react'
import { useEffect, useId, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'neutral',
})

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function sanitizeMermaidChart(chart: string) {
  const lines = chart.split('\n')
  const nodeIdMap = new Map<string, string>()

  for (const line of lines) {
    const match = line.match(/^\s*([A-Za-z0-9_-]+)\s*(?:\(\[|\[\(|\[|\{)/)
    if (!match) continue
    const rawId = match[1]
    const safeId = `node_${rawId.replace(/[^A-Za-z0-9_]/g, '_').replace(/^(\d)/, 'n_$1').toLowerCase()}`
    if (safeId !== rawId) {
      nodeIdMap.set(rawId, safeId)
    }
  }

  if (nodeIdMap.size === 0) return chart

  let sanitized = chart
  for (const [rawId, safeId] of nodeIdMap.entries()) {
    const pattern = new RegExp(`\\b${escapeRegExp(rawId)}\\b`, 'g')
    sanitized = sanitized.replace(pattern, safeId)
  }
  return sanitized
}

export function MermaidDiagram({ chart, actions }: { chart: string; actions?: ReactNode }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const id = useId().replace(/:/g, '')

  useEffect(() => {
    if (!chart || chart.trim() === '') {
      setSvg('')
      setError('Sin diagrama disponible.')
      return
    }

    let active = true
    const safeChart = sanitizeMermaidChart(chart)

    mermaid
      .parse(safeChart)
      .then((valid) => {
        if (!active) return
        if (!valid) {
          setSvg('')
          setError('Sintaxis de diagrama invalida.')
          return
        }
        mermaid
          .render(`agentica-${id}`, safeChart)
          .then(({ svg: renderedSvg }) => {
            if (!active) return
            setSvg(renderedSvg)
            setError('')
          })
          .catch(() => {
            if (!active) return
            setSvg('')
            setError('No se pudo renderizar el diagrama.')
          })
      })
      .catch(() => {
        if (!active) return
        setSvg('')
        setError('Sintaxis de diagrama invalida.')
      })

    return () => {
      active = false
    }
  }, [chart, id])

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Flujo del agente</CardTitle>
          {actions}
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {error}
            </div>
            <details className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-medium text-slate-700">
                Ver codigo Mermaid
              </summary>
              <pre className="mt-3 overflow-x-auto text-xs text-slate-600">{chart}</pre>
            </details>
          </div>
        ) : (
          <div
            className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-4"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
      </CardContent>
    </Card>
  )
}
