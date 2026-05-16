import type { ReactNode } from 'react'

function normalizeRichTextContent(content: string): string {
  return String(content || '')
    .replace(/\r\n/g, '\n')
    .replace(/([^\n])\s+(#{1,3}\s+)/g, '$1\n\n$2')
    .replace(/([.!?])\s+(\d+\.\s+)/g, '$1\n$2')
    .replace(/([^\n])\s+([-*]\s+)/g, '$1\n$2')
}

// ── Inline rendering (bold, italic, inline-code) ──────────────────────────────
function renderInline(text: string): ReactNode[] {
  // Split on inline-code first, then bold, then italic
  const segments = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g)
  return segments.map((seg, i) => {
    if (seg.startsWith('`') && seg.endsWith('`'))
      return <code key={i} className="rounded bg-slate-900/90 px-1.5 py-0.5 text-[0.85em] text-white font-mono">{seg.slice(1, -1)}</code>
    if (seg.startsWith('**') && seg.endsWith('**'))
      return <strong key={i}>{seg.slice(2, -2)}</strong>
    if (seg.startsWith('*') && seg.endsWith('*'))
      return <em key={i}>{seg.slice(1, -1)}</em>
    return <span key={i}>{seg}</span>
  })
}

// ── Table parser ─────────────────────────────────────────────────────────────
function parseTable(lines: string[]): ReactNode {
  const rows = lines.map(l =>
    l.replace(/^\||\|$/g, '').split('|').map(c => c.trim())
  )
  // Second row is separator (---|---); remove it
  const [header, , ...body] = rows
  return (
    <div key={Math.random()} className="overflow-x-auto my-3">
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

// ── Main component ────────────────────────────────────────────────────────────
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
      <ul key={key++} className="list-disc space-y-1 pl-5 my-2">
        {bulletItems.map((item, i) => <li key={i} className="text-sm leading-7">{renderInline(item)}</li>)}
      </ul>
    )
    bulletItems = []
  }

  const flushOrdered = () => {
    if (!orderedItems.length) return
    nodes.push(
      <ol key={key++} className="list-decimal space-y-1 pl-5 my-2">
        {orderedItems.map((item, i) => <li key={i} className="text-sm leading-7">{renderInline(item)}</li>)}
      </ol>
    )
    orderedItems = []
  }

  const flushTable = () => {
    if (tableLines.length < 3) { tableLines = []; return }
    nodes.push(parseTable(tableLines))
    tableLines = []
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.trimEnd()

    // ── Table row ──
    if (line.startsWith('|')) {
      flushBullet(); flushOrdered()
      tableLines.push(line)
      continue
    } else {
      flushTable()
    }

    // ── Horizontal rule ──
    if (/^[-*_]{3,}$/.test(line.trim())) {
      flushBullet(); flushOrdered()
      nodes.push(<hr key={key++} className="my-3 border-slate-200" />)
      continue
    }

    // ── Headings ──
    const h3 = line.match(/^###\s+(.+)/)
    const h2 = line.match(/^##\s+(.+)/)
    const h1 = line.match(/^#\s+(.+)/)
    if (h3) {
      flushBullet(); flushOrdered()
      nodes.push(<h3 key={key++} className="text-sm font-semibold text-slate-800 mt-4 mb-1">{renderInline(h3[1])}</h3>)
      continue
    }
    if (h2) {
      flushBullet(); flushOrdered()
      nodes.push(<h2 key={key++} className="text-base font-semibold text-slate-900 mt-4 mb-1">{renderInline(h2[1])}</h2>)
      continue
    }
    if (h1) {
      flushBullet(); flushOrdered()
      nodes.push(<h1 key={key++} className="text-lg font-bold text-slate-900 mt-4 mb-1">{renderInline(h1[1])}</h1>)
      continue
    }

    // ── Bullet list ──
    if (line.startsWith('- ') || line.startsWith('* ')) {
      flushOrdered()
      bulletItems.push(line.slice(2))
      continue
    }

    // ── Ordered list ──
    const orderedMatch = line.match(/^\d+\.\s+(.+)/)
    if (orderedMatch) {
      flushBullet()
      orderedItems.push(orderedMatch[1])
      continue
    }

    // ── Empty line ──
    if (!line.trim()) {
      flushBullet(); flushOrdered()
      continue
    }

    // ── Regular paragraph ──
    flushBullet(); flushOrdered()
    nodes.push(
      <p key={key++} className="text-sm leading-7 whitespace-pre-wrap">
        {renderInline(line)}
      </p>
    )
  }

  flushBullet()
  flushOrdered()
  flushTable()

  return <div className="space-y-1">{nodes}</div>
}
