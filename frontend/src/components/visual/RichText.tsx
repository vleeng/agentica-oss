import type { ReactNode } from 'react'

function renderInline(text: string) {
  const parts = text.split(/(`[^`]+`)/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={index} className="rounded bg-slate-900/90 px-1.5 py-0.5 text-[0.85em] text-white">
          {part.slice(1, -1)}
        </code>
      )
    }

    const boldParts = part.split(/(\*\*[^*]+\*\*)/g)
    return boldParts.map((boldPart, boldIndex) => {
      if (boldPart.startsWith('**') && boldPart.endsWith('**')) {
        return <strong key={`${index}-${boldIndex}`}>{boldPart.slice(2, -2)}</strong>
      }
      return <span key={`${index}-${boldIndex}`}>{boldPart}</span>
    })
  })
}

export function RichText({ content }: { content: string }) {
  const blocks = content.split('\n')
  const nodes: ReactNode[] = []
  let listItems: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    nodes.push(
      <ul key={`list-${nodes.length}`} className="list-disc space-y-1 pl-5">
        {listItems.map((item, index) => (
          <li key={index}>{renderInline(item)}</li>
        ))}
      </ul>
    )
    listItems = []
  }

  for (const raw of blocks) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flushList()
      continue
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      listItems.push(line.slice(2))
      continue
    }

    flushList()
    nodes.push(
      <p key={`p-${nodes.length}`} className="whitespace-pre-wrap">
        {renderInline(line)}
      </p>
    )
  }

  flushList()

  return <div className="space-y-3 text-sm leading-7">{nodes}</div>
}
