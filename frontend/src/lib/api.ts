/** Unified API client for the MoRead backend. */

export const API_BASE = ''

// ---- 访问令牌（局域网保护；设置中启用后所有 /api 请求需携带） ----
const TOKEN_KEY = 'moread-token'

export function getToken(): string {
  try { return localStorage.getItem(TOKEN_KEY) ?? '' } catch { return '' }
}

export function setToken(t: string) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* ignore */ }
}

/** 给媒体/SSE 等 URL 追加 ?token=（EventSource/媒体标签无法设置请求头） */
export function withToken(url: string): string {
  const t = getToken()
  if (!t) return url
  return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(t)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const t = getToken()
  return t ? { 'X-MoRead-Token': t, ...extra } : { ...extra }
}

function onAuthRequired() {
  window.dispatchEvent(new CustomEvent('moread-auth-required'))
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    if (resp.status === 401) onAuthRequired()
    let msg = `请求失败（HTTP ${resp.status}）`
    try {
      const data = await resp.json()
      if (typeof data?.detail === 'string') msg = data.detail
      else if (Array.isArray(data?.detail)) {
        msg = data.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('；')
      }
    } catch { /* keep default */ }
    throw new ApiError(resp.status, msg)
  }
  return resp.json() as Promise<T>
}

export const api = {
  async get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.entries(params)
            .filter(([, v]) => v !== undefined && v !== '')
            .map(([k, v]) => [k, String(v)]),
        ).toString()
      : ''
    try {
      const resp = await fetch(`${API_BASE}${path}${qs}`, { headers: authHeaders() })
      return await handle<T>(resp)
    } catch (err) {
      if (err instanceof ApiError) throw err
      throw new ApiError(0, '网络异常：无法连接本地服务，请确认后端已启动')
    }
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    try {
      const resp = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      return await handle<T>(resp)
    } catch (err) {
      if (err instanceof ApiError) throw err
      throw new ApiError(0, '网络异常：无法连接本地服务')
    }
  },

  async put<T>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, {
      method: 'PUT',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    })
    return handle<T>(resp)
  },

  async patch<T>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, {
      method: 'PATCH',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    })
    return handle<T>(resp)
  },

  async delete<T>(path: string): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, { headers: authHeaders(), method: 'DELETE' })
    return handle<T>(resp)
  },

  async upload<T>(path: string, files: File[]): Promise<T> {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    const resp = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: authHeaders(), body: form })
    return handle<T>(resp)
  },
}

// ---------------------------------------------------------------------------
// SSE with exponential backoff auto-reconnect (断线自动重连)
// ---------------------------------------------------------------------------

export interface TaskSseEvent {
  task_id: string
  status?: string
  progress?: number
  speed?: string
  eta?: string
  message?: string
  error?: string
  imported?: number
}

export interface TaskSnapshot {
  id: string
  tool: string
  status: string
  progress: number
  message: string
  [key: string]: unknown
}

/**
 * Subscribe to a task's SSE status stream. Returns an unsubscribe function.
 * Reconnects with 1s→2s→4s…(max 30s) backoff until `shouldStop()` or a
 * terminal event arrives.
 */
export function subscribeTask(
  taskId: string,
  handlers: {
    onSnapshot?: (snap: TaskSnapshot) => void
    onProgress?: (ev: TaskSseEvent) => void
    onEnd?: (status: string) => void
    onReconnecting?: (delayMs: number) => void
  },
): () => void {
  let stopped = false
  let attempt = 0
  let es: EventSource | null = null

  const connect = () => {
    if (stopped) return
    es = new EventSource(withToken(`${API_BASE}/api/tasks/${taskId}/status`))

    es.addEventListener('snapshot', (e) => {
      try { handlers.onSnapshot?.(JSON.parse((e as MessageEvent).data)) } catch { /* ignore */ }
    })
    es.addEventListener('progress', (e) => {
      attempt = 0 // success resets backoff
      try { handlers.onProgress?.(JSON.parse((e as MessageEvent).data)) } catch { /* ignore */ }
    })
    es.addEventListener('end', (e) => {
      let status = 'completed'
      try { status = JSON.parse((e as MessageEvent).data).status } catch { /* ignore */ }
      es?.close()
      stopped = true
      handlers.onEnd?.(status)
    })
    es.onerror = () => {
      es?.close()
      if (stopped) return
      const delay = Math.min(30000, 1000 * 2 ** attempt)
      attempt += 1
      handlers.onReconnecting?.(delay)
      setTimeout(connect, delay)
    }
  }
  connect()
  return () => {
    stopped = true
    es?.close()
  }
}
