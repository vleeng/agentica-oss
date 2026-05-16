import { useState, useEffect, useRef } from 'react'
import { agentsApi, authApi, createAgentWebSocket, normalizeAgentChatError, type AuthMe } from '../../lib/api'
import { summarizeAgentProgress } from '../../lib/chatProgress'
import type { AgentDesign } from '../../types/agent'
import { getAuthToken } from '../../stores/auth'
import { RichText } from '../visual/RichText'
import { Bot, Send } from 'lucide-react'
import { ChatContextHeader } from './ChatContextHeader'

interface Props {
  agentId: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  status?: string
}

export function StandaloneChat({ agentId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [viewerContext, setViewerContext] = useState<AuthMe | null>(null)
  const [agentDesign, setAgentDesign] = useState<AgentDesign | null>(null)
  
  const sessionId = useRef(`pub_${agentId}_${Date.now()}`)
  const wsRef = useRef<ReturnType<typeof createAgentWebSocket> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const apiKey = new URLSearchParams(window.location.search).get('api_key') || ''
  // Refs so the stable WS callbacks always target the current message
  const onTokenRef = useRef<(token: string) => void>(() => {})
  const onDoneRef  = useRef<(sid: string) => void>(() => {})
  const onErrorRef = useRef<(msg: string) => void>(() => {})
  const onStatusRef = useRef<(label: string | null) => void>(() => {})
  
  const [agentReady, setAgentReady] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    if (apiKey) {
      setAgentReady('ok')
      return
    }
    agentsApi.getState(agentId)
      .then(() => setAgentReady('ok'))
      .catch(() => setAgentReady('error'))
  }, [agentId, apiKey])

  useEffect(() => {
    let cancelled = false
    const token = getAuthToken()

    if (!apiKey && token) {
      authApi
        .me()
        .then((me) => {
          if (!cancelled) setViewerContext(me)
        })
        .catch(() => {
          if (!cancelled) setViewerContext(null)
        })

      agentsApi
        .getDesign(agentId)
        .then((design) => {
          if (!cancelled) setAgentDesign(design)
        })
        .catch(() => {
          if (!cancelled) setAgentDesign(null)
        })
    }

    return () => {
      cancelled = true
    }
  }, [agentId, apiKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // Montamos un primer mensaje de bienvenida local
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: '¡Hola! Soy tu agente virtual. ¿En qué puedo ayudarte el día de hoy?',
      }
    ])
    
    return () => {
      wsRef.current?.close()
    }
  }, [agentId])

  const sendMessage = () => {
    if (!input.trim() || sending || agentReady !== 'ok') return
    const userMsg = input.trim()
    setInput('')
    setSending(true)

    setMessages(prev => [...prev, {
      id: `u_${Date.now()}`,
      role: 'user',
      content: userMsg,
    }])

    const assistantId = `a_${Date.now()}`
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      status: 'Pensando',
    }])

    // Update refs so the stable WS callbacks always point to the current message
    onTokenRef.current = (token) => {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: m.content + token, status: 'Redactando respuesta' } : m
      ))
    }
    onDoneRef.current = () => {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, streaming: false, status: undefined } : m
      ))
      setSending(false)
    }
    onErrorRef.current = (err) => {
      const friendlyMessage = normalizeAgentChatError(err)
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: `Error: ${friendlyMessage}`, streaming: false, status: undefined } : m
      ))
      setSending(false)
    }
    onStatusRef.current = (label) => {
      if (!label) return
      setMessages(prev => prev.map(m =>
        m.id === assistantId && m.streaming ? { ...m, status: label } : m
      ))
    }
    if (!wsRef.current) {
      wsRef.current = createAgentWebSocket(
        agentId,
        (token) => onTokenRef.current(token),
        (sid)   => onDoneRef.current(sid),
        (msg)   => onErrorRef.current(msg),
        (payload) => onStatusRef.current(summarizeAgentProgress(payload)),
        (payload) => onStatusRef.current(summarizeAgentProgress(payload)),
        { apiKey },
      )
    }

    wsRef.current.send(userMsg, sessionId.current)
  }

  if (agentReady === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 text-gray-500">
        <Bot size={40} className="animate-bounce mb-4 text-violet-600" />
        <p>Conectando con el Agente...</p>
      </div>
    )
  }

  if (agentReady === 'error') {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 text-red-500">
        <Bot size={40} className="mb-4 text-red-600" />
        <p className="font-semibold text-lg text-gray-800">Agente no disponible</p>
        <p className="text-sm text-gray-500 max-w-md text-center mt-2">
          El agente {agentId} no existe, o se encuentra temporalmente fuera de línea.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50 font-sans">
      {/* Header Premium Liviano */}
      <header className="flex items-center justify-center p-4 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 flex items-center justify-center rounded-full bg-violet-100 text-violet-700">
            <Bot size={20} />
          </div>
          <h1 className="text-xl font-semibold text-gray-800">Agentica IA</h1>
        </div>
      </header>

      {/* Caja de mensajes */}
      <main className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto p-4 md:p-6 space-y-6">
        <ChatContextHeader
          agentName={agentDesign?.spec.name || `Agente ${agentId.slice(0, 8)}`}
          agentId={agentId}
          tenantName={viewerContext?.tenant_name}
          tenantId={viewerContext?.tenant_id || agentDesign?.tenant_id}
          userName={viewerContext?.full_name}
          userEmail={viewerContext?.email}
          environmentLabel="Agente desplegado"
          channelLabel={apiKey ? 'Link/API key' : 'Web chat'}
        />
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-violet-600 flex-shrink-0 flex items-center justify-center text-white mr-3 mt-1 shadow-md">
                <Bot size={16} />
              </div>
            )}
            
            <div className={`max-w-[85%] md:max-w-[75%] px-5 py-3.5 rounded-2xl text-[15px] leading-relaxed shadow-sm ${
              msg.role === 'user'
                ? 'bg-violet-600 text-white rounded-br-sm'
                : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
            }`}>
              {msg.role === 'user'
                ? <p className="whitespace-pre-wrap">{msg.content}</p>
                : msg.content
                  ? <RichText content={msg.content} />
                  : msg.streaming
                  ? <span className="animate-pulse">●</span>
                  : null
              }
              {msg.role === 'assistant' && msg.status && (
                <div className="mt-2 text-xs font-medium text-violet-600">
                  {msg.status}...
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      {/* Imput Footer */}
      <footer className="w-full max-w-3xl mx-auto p-4 md:p-6 bg-transparent">
        <div className="relative flex items-center shadow-lg rounded-2xl bg-white border border-gray-200 focus-within:border-violet-500 focus-within:ring-2 focus-within:ring-violet-200 transition-all">
          <input
            type="text"
            className="flex-1 px-5 py-4 bg-transparent outline-none text-gray-700 placeholder-gray-400"
            placeholder="Mensaje a tu asistente IA..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            disabled={sending}
          />
          <button
            onClick={sendMessage}
            disabled={sending || !input.trim()}
            className="absolute right-2 p-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-300 text-white rounded-xl transition-colors shadow-sm"
            aria-label="Enviar"
          >
            <Send size={18} className={sending ? 'animate-pulse' : ''} />
          </button>
        </div>
        <p className="text-center text-xs text-gray-400 mt-3">
          Powered by <span className="font-semibold text-gray-500">Agentica</span>
        </p>
      </footer>
    </div>
  )
}
