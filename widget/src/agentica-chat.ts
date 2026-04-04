/**
 * AGENTICA Web Chat Widget
 * Web Component autónomo — sin dependencias del host.
 *
 * Uso:
 *   <script src="https://cdn.agentica.io/widget/v1.js"></script>
 *   <agentica-chat
 *     agent-id="agt_abc123"
 *     api-key="pk_live_..."
 *     ws-url="wss://api.axenova.com/api/v1/agents/agt_abc123/ws"
 *     theme="light"
 *     placeholder="Preguntame algo..."
 *     welcome="Hola, soy tu asistente."
 *     position="bottom-right"
 *   ></agentica-chat>
 */

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  timestamp: number
}

class AgenticaChat extends HTMLElement {
  private shadow: ShadowRoot
  private ws: WebSocket | null = null
  private messages: Message[] = []
  private sessionId: string
  private isOpen = false
  private isConnecting = false

  // Atributos observados
  static get observedAttributes() {
    return ['agent-id', 'ws-url', 'api-key', 'theme', 'placeholder', 'welcome', 'position']
  }

  constructor() {
    super()
    this.shadow = this.attachShadow({ mode: 'open' })
    this.sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2)}`
  }

  connectedCallback() {
    this.render()
    this.bindEvents()
  }

  get agentId()    { return this.getAttribute('agent-id')   || '' }
  get wsUrl()      { return this.getAttribute('ws-url')     || '' }
  get apiKey()     { return this.getAttribute('api-key')    || '' }
  get theme()      { return this.getAttribute('theme')      || 'light' }
  get placeholder(){ return this.getAttribute('placeholder')|| 'Escribí tu mensaje...' }
  get welcome()    { return this.getAttribute('welcome')    || '¡Hola! ¿En qué puedo ayudarte?' }
  get position()   { return this.getAttribute('position')   || 'bottom-right' }

  private render() {
    const isDark = this.theme === 'dark'
    this.shadow.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

        #launcher {
          position: fixed;
          ${this.position.includes('right') ? 'right: 24px;' : 'left: 24px;'}
          bottom: 24px;
          width: 56px; height: 56px;
          background: #7c3aed;
          border-radius: 50%;
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 4px 16px rgba(124,58,237,0.4);
          transition: transform 0.2s, box-shadow 0.2s;
          border: none;
          z-index: 99999;
        }
        #launcher:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(124,58,237,0.5); }
        #launcher svg { width: 26px; height: 26px; fill: white; }

        #chat-window {
          position: fixed;
          ${this.position.includes('right') ? 'right: 24px;' : 'left: 24px;'}
          bottom: 92px;
          width: 380px;
          max-height: 560px;
          background: ${isDark ? '#1a1a2e' : '#ffffff'};
          border-radius: 16px;
          box-shadow: 0 8px 40px rgba(0,0,0,0.18);
          display: flex; flex-direction: column;
          overflow: hidden;
          transition: opacity 0.2s, transform 0.2s;
          z-index: 99998;
          border: 1px solid ${isDark ? '#2d2d4e' : '#e5e7eb'};
        }
        #chat-window.hidden { opacity: 0; transform: translateY(12px) scale(0.97); pointer-events: none; }

        #chat-header {
          padding: 16px 18px;
          background: #7c3aed;
          color: white;
          display: flex; align-items: center; justify-content: space-between;
          flex-shrink: 0;
        }
        #chat-header .title { font-size: 15px; font-weight: 600; }
        #chat-header .subtitle { font-size: 12px; opacity: 0.8; margin-top: 2px; }
        #close-btn { background: none; border: none; color: white; cursor: pointer; padding: 4px; border-radius: 6px; }
        #close-btn:hover { background: rgba(255,255,255,0.15); }

        #messages {
          flex: 1; overflow-y: auto; padding: 16px;
          display: flex; flex-direction: column; gap: 10px;
          scroll-behavior: smooth;
        }
        #messages::-webkit-scrollbar { width: 4px; }
        #messages::-webkit-scrollbar-thumb { background: ${isDark ? '#444' : '#ddd'}; border-radius: 2px; }

        .msg { max-width: 82%; display: flex; flex-direction: column; gap: 2px; }
        .msg.user { align-self: flex-end; align-items: flex-end; }
        .msg.assistant { align-self: flex-start; }

        .bubble {
          padding: 10px 14px; border-radius: 16px;
          font-size: 14px; line-height: 1.5;
          word-break: break-word;
        }
        .user .bubble {
          background: #7c3aed; color: white;
          border-bottom-right-radius: 4px;
        }
        .assistant .bubble {
          background: ${isDark ? '#2d2d4e' : '#f3f4f6'};
          color: ${isDark ? '#e5e7eb' : '#111827'};
          border-bottom-left-radius: 4px;
        }
        .bubble.streaming::after {
          content: '▌'; animation: blink 0.8s infinite; margin-left: 2px;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

        .timestamp { font-size: 11px; color: ${isDark ? '#6b7280' : '#9ca3af'}; }

        #input-area {
          padding: 12px 14px;
          border-top: 1px solid ${isDark ? '#2d2d4e' : '#e5e7eb'};
          display: flex; gap: 8px; align-items: flex-end;
          flex-shrink: 0;
          background: ${isDark ? '#1a1a2e' : '#ffffff'};
        }
        #input {
          flex: 1; border: 1px solid ${isDark ? '#3d3d5e' : '#d1d5db'};
          border-radius: 10px; padding: 10px 14px;
          font-size: 14px; resize: none; outline: none;
          background: ${isDark ? '#252540' : '#f9fafb'};
          color: ${isDark ? '#e5e7eb' : '#111827'};
          max-height: 120px; line-height: 1.4;
          transition: border-color 0.15s;
        }
        #input:focus { border-color: #7c3aed; }
        #input::placeholder { color: ${isDark ? '#6b7280' : '#9ca3af'}; }

        #send-btn {
          width: 38px; height: 38px; flex-shrink: 0;
          background: #7c3aed; border: none; border-radius: 10px;
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          transition: background 0.15s, transform 0.1s;
        }
        #send-btn:hover { background: #6d28d9; }
        #send-btn:active { transform: scale(0.94); }
        #send-btn:disabled { background: #c4b5fd; cursor: not-allowed; }
        #send-btn svg { width: 18px; height: 18px; fill: white; }

        #status-bar {
          text-align: center; padding: 6px; font-size: 11px;
          color: ${isDark ? '#6b7280' : '#9ca3af'};
          background: ${isDark ? '#252540' : '#f9fafb'};
          border-top: 1px solid ${isDark ? '#2d2d4e' : '#e5e7eb'};
          flex-shrink: 0;
        }
      </style>

      <button id="launcher" aria-label="Abrir chat">
        <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
      </button>

      <div id="chat-window" class="hidden">
        <div id="chat-header">
          <div>
            <div class="title">Asistente IA</div>
            <div class="subtitle" id="status-text">Conectando...</div>
          </div>
          <button id="close-btn" aria-label="Cerrar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        <div id="messages"></div>

        <div id="input-area">
          <textarea id="input" rows="1" placeholder="${this.placeholder}"></textarea>
          <button id="send-btn" disabled>
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>

        <div id="status-bar">Powered by AGENTICA</div>
      </div>
    `
  }

  private bindEvents() {
    const launcher   = this.shadow.getElementById('launcher')!
    const closeBtn   = this.shadow.getElementById('close-btn')!
    const input      = this.shadow.getElementById('input') as HTMLTextAreaElement
    const sendBtn    = this.shadow.getElementById('send-btn') as HTMLButtonElement

    launcher.addEventListener('click', () => this.toggleChat())
    closeBtn.addEventListener('click', () => this.toggleChat())
    sendBtn.addEventListener('click', () => this.sendMessage())
    input.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        this.sendMessage()
      }
    })
    input.addEventListener('input', () => {
      input.style.height = 'auto'
      input.style.height = Math.min(input.scrollHeight, 120) + 'px'
      sendBtn.disabled = !input.value.trim() || !this.ws || this.ws.readyState !== WebSocket.OPEN
    })
  }

  private toggleChat() {
    this.isOpen = !this.isOpen
    const win = this.shadow.getElementById('chat-window')!
    win.classList.toggle('hidden', !this.isOpen)

    if (this.isOpen && !this.ws) {
      this.connectWebSocket()
      if (this.messages.length === 0) {
        this.addMessage('assistant', this.welcome)
      }
    }
  }

  private connectWebSocket() {
    if (this.isConnecting || !this.wsUrl) return
    this.isConnecting = true
    this.setStatus('Conectando...')

    this.ws = new WebSocket(`${this.wsUrl}?session_id=${this.sessionId}`)

    this.ws.onopen = () => {
      this.isConnecting = false
      this.setStatus('En línea')
      const sendBtn = this.shadow.getElementById('send-btn') as HTMLButtonElement
      const input   = this.shadow.getElementById('input') as HTMLTextAreaElement
      sendBtn.disabled = !input.value.trim()
    }

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      this.handleServerMessage(data)
    }

    this.ws.onerror = () => {
      this.setStatus('Error de conexión')
      this.isConnecting = false
    }

    this.ws.onclose = () => {
      this.setStatus('Desconectado — clic para reconectar')
      this.ws = null
      this.isConnecting = false
    }
  }

  private handleServerMessage(data: { type: string; content?: string; message?: string; session_id?: string; latency_ms?: number }) {
    if (data.type === 'token') {
      this.appendToken(data.content || '')
    } else if (data.type === 'done') {
      this.finalizeStreaming()
      this.setStatus(`Respondió en ${data.latency_ms?.toFixed(0)}ms`)
      const sendBtn = this.shadow.getElementById('send-btn') as HTMLButtonElement
      const input   = this.shadow.getElementById('input') as HTMLTextAreaElement
      sendBtn.disabled = !input.value.trim()
    } else if (data.type === 'error') {
      this.addMessage('assistant', `Error: ${data.message}`)
    }
  }

  private sendMessage() {
    const input   = this.shadow.getElementById('input') as HTMLTextAreaElement
    const sendBtn = this.shadow.getElementById('send-btn') as HTMLButtonElement
    const text    = input.value.trim()

    if (!text || !this.ws || this.ws.readyState !== WebSocket.OPEN) return

    this.addMessage('user', text)
    this.addStreamingPlaceholder()

    this.ws.send(JSON.stringify({ input: text, session_id: this.sessionId }))

    input.value = ''
    input.style.height = 'auto'
    sendBtn.disabled = true
    this.setStatus('Procesando...')
  }

  private addMessage(role: 'user' | 'assistant', content: string) {
    const msg: Message = { id: `m_${Date.now()}`, role, content, timestamp: Date.now() }
    this.messages.push(msg)
    this.renderMessage(msg)
  }

  private addStreamingPlaceholder() {
    const msg: Message = {
      id: 'streaming',
      role: 'assistant',
      content: '',
      streaming: true,
      timestamp: Date.now(),
    }
    this.messages.push(msg)
    this.renderMessage(msg)
  }

  private appendToken(token: string) {
    const el = this.shadow.querySelector('[data-id="streaming"] .bubble') as HTMLElement
    if (el) {
      const msg = this.messages.find(m => m.id === 'streaming')
      if (msg) {
        msg.content += token
        el.textContent = msg.content
      }
    }
    this.scrollToBottom()
  }

  private finalizeStreaming() {
    const el = this.shadow.querySelector('[data-id="streaming"]')
    if (el) {
      const msg = this.messages.find(m => m.id === 'streaming')
      if (msg) {
        msg.id = `m_${Date.now()}`
        msg.streaming = false
        el.setAttribute('data-id', msg.id)
        const bubble = el.querySelector('.bubble')
        if (bubble) bubble.classList.remove('streaming')
      }
    }
  }

  private renderMessage(msg: Message) {
    const container = this.shadow.getElementById('messages')!
    const div = document.createElement('div')
    div.className = `msg ${msg.role}`
    div.setAttribute('data-id', msg.id)
    div.innerHTML = `
      <div class="bubble${msg.streaming ? ' streaming' : ''}">${this.escapeHtml(msg.content)}</div>
      <span class="timestamp">${new Date(msg.timestamp).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}</span>
    `
    container.appendChild(div)
    this.scrollToBottom()
  }

  private scrollToBottom() {
    const messages = this.shadow.getElementById('messages')!
    messages.scrollTop = messages.scrollHeight
  }

  private setStatus(text: string) {
    const el = this.shadow.getElementById('status-text')
    if (el) el.textContent = text
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>')
  }
}

customElements.define('agentica-chat', AgenticaChat)
