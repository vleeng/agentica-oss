import type { ReactNode } from 'react'

const COMMON_HEADINGS = [
  'Nombre de la receta',
  'Ingredientes',
  'Preparacion',
  'Preparación',
  'Consejos',
  'Consejos utiles',
  'Consejos útiles',
  'Tips',
  'Tiempo total',
  'Tiempo aproximado',
  'Tiempo estimado',
  'Porciones',
  'Analisis nutricional',
  'Análisis nutricional',
  'Para la masa',
  'Para el relleno',
  'Para servir',
]

function normalizeRichTextContent(content: string): string {
  let normalized = String(content || '')
    .replace(/\r\n/g, '\n')
    .replace(/([^\n])\s+(#{1,3}\s+)/g, '$1\n\n$2')
    .replace(/([.!?])\s+(\d+\.\s+)/g, '$1\n$2')
    .replace(/([.!?])\s+(\d+\)\s+)/g, '$1\n$2')
    .replace(/([^\n])\s+([-*]\s+)/g, '$1\n$2')

  for (const heading of COMMON_HEADINGS) {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    normalized = normalized.replace(
      new RegExp(`(^|\\n)(\\d+[\\.)]\\s+[^\\n:]{3,120}?)\\s+(${escaped}:)`, 'g'),
      '$1## $2\n\n### $3',
    )
  }

  for (const heading of COMMON_HEADINGS) {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    normalized = normalized.replace(new RegExp(`([^\\n])\\s+(${escaped}:)`, 'g'), '$1\n\n$2')
    normalized = normalized.replace(new RegExp(`(^|\\n)(${escaped}:)`, 'g'), '$1### $2')
  }

  normalized = normalized.replace(/(^|\n)(\d+[\.)]\s+[^\n:#]{3,120})(?=\n### )/g, '$1## $2')

  return normalized
}

function renderInline(text: string): ReactNode[] {
  const segments = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g)
  return segments.map((seg, i) => {
    if (seg.startsWith('`') && seg.endsWith('`')) {
      return (
        <code key={i} className="rounded bg-slate-900/90 px-1.5 py-0.5 text-[0.85em] font-mono text-white">
          {seg.slice(1, -1)}
        </code>
      )
    }
    if (seg.startsWith('**') && seg.endsWith('**')) {
      return <strong key={i}>{seg.slice(2, -2)}</strong>
    }
    if (seg.startsWith('*') && seg.endsWith('*')) {
      return <em key={i}>{seg.slice(1, -1)}</em>
    }
    return <span key={i}>{seg}</span>
  })
}

function parseTable(lines: string[]): ReactNode {
  const rows = lines.map((line) =>
    line.replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()),
  )
  const [header, , ...body] = rows
  return (
    <div key={Math.random()} className="my-3 overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="bg-slate-100">
            {header.map((cell, ci) => (
              <th key={ci} className="border border-slate-300 px-3 py-2 text-left font-semibold text-slate-700">
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
              {row.map((cell, ci) => (
                <td key={ci} className="border border-slate-300 px-3 py-2 text-slate-700">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderLabeledParagraph(line: string): ReactNode | null {
  const match = line.match(
    /^(Nombre de la receta|Ingredientes|Preparacion|Preparación|Consejos|Consejos utiles|Consejos útiles|Tips|Tiempo total|Tiempo aproximado|Tiempo estimado|Porciones|Analisis nutricional|Análisis nutricional):\s*(.*)$/i,
  )
  if (!match) return null

  const [, label, rest] = match
  return (
    <p className="whitespace-pre-wrap text-sm leading-7">
      <strong>{label}:</strong>
      {rest ? <> {renderInline(rest)}</> : null}
    </p>
  )
}

export function RichText({ content }: { content: string }) {
  const lines = normalizeRichTextContent(content).split('\n')
  const nodes: ReactNode[] = []

  let bulletItems: string[] = []
  let orderedItems: string[] = []
  let tableLines: string[] = []
  let key = 0

  const flushBullet = () => {
    if (!bulletItems.length) return
    nodes.push(
      <ul key={key++} className="my-2 list-disc space-y-1 pl-5">
        {bulletItems.map((item, i) => (
          <li key={i} className="text-sm leading-7">
            {renderInline(item)}
          </li>
        ))}
      </ul>,
    )
    bulletItems = []
  }

  const flushOrdered = () => {
    if (!orderedItems.length) return
    nodes.push(
      <ol key={key++} className="my-2 list-decimal space-y-1 pl-5">
        {orderedItems.map((item, i) => (
          <li key={i} className="text-sm leading-7">
            {renderInline(item)}
          </li>
        ))}
      </ol>,
    )
    orderedItems = []
  }

  const flushTable = () => {
    if (tableLines.length < 3) {
      tableLines = []
      return
    }
    nodes.push(parseTable(tableLines))
    tableLines = []
  }

  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i]
    const line = raw.trimEnd()

    if (line.startsWith('|')) {
      flushBullet()
      flushOrdered()
      tableLines.push(line)
      continue
    }
    flushTable()

    if (/^[-*_]{3,}$/.test(line.trim())) {
      flushBullet()
      flushOrdered()
      nodes.push(<hr key={key++} className="my-3 border-slate-200" />)
      continue
    }

    const h3 = line.match(/^###\s+(.+)/)
    const h2 = line.match(/^##\s+(.+)/)
    const h1 = line.match(/^#\s+(.+)/)
    if (h3) {
      flushBullet()
      flushOrdered()
      nodes.push(
        <h3 key={key++} className="mb-2 mt-5 text-base font-bold text-slate-900">
          {renderInline(h3[1])}
        </h3>,
      )
      continue
    }
    if (h2) {
      flushBullet()
      flushOrdered()
      nodes.push(
        <h2 key={key++} className="mb-1 mt-4 text-base font-semibold text-slate-900">
          {renderInline(h2[1])}
        </h2>,
      )
      continue
    }
    if (h1) {
      flushBullet()
      flushOrdered()
      nodes.push(
        <h1 key={key++} className="mb-1 mt-4 text-lg font-bold text-slate-900">
          {renderInline(h1[1])}
        </h1>,
      )
      continue
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      flushOrdered()
      bulletItems.push(line.slice(2))
      continue
    }

    const orderedMatch = line.match(/^\d+[.)]\s+(.+)/)
    if (orderedMatch) {
      flushBullet()
      orderedItems.push(orderedMatch[1])
      continue
    }

    if (!line.trim()) {
      flushBullet()
      flushOrdered()
      continue
    }

    flushBullet()
    flushOrdered()
    const labeled = renderLabeledParagraph(line)
    if (labeled) {
      nodes.push(<div key={key++}>{labeled}</div>)
      continue
    }
    nodes.push(
      <p key={key++} className="whitespace-pre-wrap text-sm leading-7">
        {renderInline(line)}
      </p>,
    )
  }

  flushBullet()
  flushOrdered()
  flushTable()

  return <div className="space-y-1">{nodes}</div>
}
