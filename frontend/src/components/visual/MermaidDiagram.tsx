import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'neutral',
})

export function MermaidDiagram({ chart }: { chart: string }) {
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

    mermaid
      .parse(chart)
      .then((valid) => {
        if (!active) return
        if (!valid) {
          setSvg('')
          setError('Sintaxis de diagrama invalida.')
          return
        }
        mermaid
          .render(`agentica-${id}`, chart)
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
        <CardTitle>Flujo del agente</CardTitle>
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
