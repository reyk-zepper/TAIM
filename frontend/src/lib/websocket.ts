import type { WSEvent } from '../types/ws-events'

type EventHandler = (event: WSEvent) => void

const MAX_RECONNECT_ATTEMPTS = 5
const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 30000

export class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers: Map<string, EventHandler[]> = new Map()
  private _sessionId: string
  private _reconnectAttempts = 0
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private _intentionalClose = false
  private _messageQueue: string[] = []

  constructor(sessionId: string) {
    this._sessionId = sessionId
  }

  get sessionId(): string {
    return this._sessionId
  }

  connect(): void {
    this._intentionalClose = false
    this._createConnection()
  }

  private _createConnection(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.ws = new WebSocket(`${protocol}//${host}/ws/${this._sessionId}`)

    this.ws.onopen = () => {
      this._reconnectAttempts = 0
      this._emit('_connected', { type: '_connected' })

      // Flush queued messages
      while (this._messageQueue.length > 0) {
        const msg = this._messageQueue.shift()!
        this.ws?.send(msg)
      }
    }

    this.ws.onmessage = (e) => {
      const event: WSEvent = JSON.parse(e.data)
      this._emit(event.type, event)
      this._emit('*', event)
    }

    this.ws.onclose = () => {
      this._emit('_disconnected', { type: '_disconnected' })
      if (!this._intentionalClose) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      // onclose will fire after onerror — reconnect handled there
    }
  }

  private _scheduleReconnect(): void {
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this._emit('_reconnect_failed', { type: '_reconnect_failed' })
      return
    }

    const delay = Math.min(
      BASE_DELAY_MS * Math.pow(2, this._reconnectAttempts),
      MAX_DELAY_MS
    )
    this._reconnectAttempts++

    this._emit('_reconnecting', {
      type: '_reconnecting',
      content: `Reconnecting (attempt ${this._reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`,
    })

    this._reconnectTimer = setTimeout(() => {
      this._createConnection()
    }, delay)
  }

  send(content: string): void {
    const msg = JSON.stringify({ content })
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(msg)
    } else {
      // Queue message for when connection is restored
      this._messageQueue.push(msg)
    }
  }

  on(type: string, handler: EventHandler): () => void {
    if (!this.handlers.has(type)) this.handlers.set(type, [])
    this.handlers.get(type)!.push(handler)
    return () => {
      const arr = this.handlers.get(type)
      if (arr) {
        const idx = arr.indexOf(handler)
        if (idx >= 0) arr.splice(idx, 1)
      }
    }
  }

  disconnect(): void {
    this._intentionalClose = true
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
    }
    this.ws?.close()
    this.ws = null
    this._messageQueue = []
  }

  private _emit(type: string, event: WSEvent): void {
    const handlers = this.handlers.get(type) || []
    handlers.forEach((h) => h(event))
  }
}
