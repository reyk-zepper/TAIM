import type { WSEvent } from '../types/ws-events'

type EventHandler = (event: WSEvent) => void

export class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers: Map<string, EventHandler[]> = new Map()
  private _sessionId: string

  constructor(sessionId: string) {
    this._sessionId = sessionId
  }

  get sessionId(): string {
    return this._sessionId
  }

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.ws = new WebSocket(`${protocol}//${host}/ws/${this._sessionId}`)

    this.ws.onmessage = (e) => {
      const event: WSEvent = JSON.parse(e.data)
      const handlers = this.handlers.get(event.type) || []
      handlers.forEach((h) => h(event))
      this.handlers.get('*')?.forEach((h) => h(event))
    }

    this.ws.onopen = () => {
      this.handlers.get('_connected')?.forEach((h) => h({ type: '_connected' }))
    }

    this.ws.onclose = () => {
      this.handlers.get('_disconnected')?.forEach((h) => h({ type: '_disconnected' }))
    }
  }

  send(content: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ content }))
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
    this.ws?.close()
    this.ws = null
  }
}
