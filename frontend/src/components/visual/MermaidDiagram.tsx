import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'neutral',
  suppressErrors: true,
})

export function MermaidDiagram({ chart }: { chart: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const id = useId().replace(/:/g, '')

  useEffect(() => {
    if (!chart || chart.trim() === '') {
      setError('Sin diagrama disponible.')
      return
    }

    let active = true

    // Validate syntax before rendering to avoid Mermaid polluting the DOM
    mermaid.parse(chart).then(valid => {
      if (!active) return
      if (!valid) {
        setError('Sintaxis de diagrama inválida.')
        return
      }
      mermaid
        .render(`agentica-${id}`, chart)
        .then(({ svg }) => {
          if (!active) return
          setSvg(svg)
          setError('')
        })
        .catch(() => {
          if (!active) return
          setError('No se pudo renderizar el diagrama.')
        })
    }).catch(() => {
      if (!active) return
      setError('Sintaxis de diagrama inválida.')
    })

    return () => {
      active = false
    }
  }, [chart, id])

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>Flujo del agente</CardTitle>
      </CardHeader>
      <CardContent>
        {error ? (
          <pre className="overflow-x-auto rounded-lg bg-slate-50 p-4 text-xs text-slate-600">{chart}</pre>
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
