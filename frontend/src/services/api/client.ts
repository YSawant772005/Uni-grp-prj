/**
 * Typed fetch client for the backend API.
 *
 * - Cookies only (HttpOnly session); tokens never touched from JS.
 * - Errors always surface as `ApiError` parsed from the contract's error envelope.
 * - A 401 caused by an expired access token is refreshed exactly once and the
 *   original request retried; anything else reports session-expired to the app.
 */
import type { ApiErrorBody, ErrorDetail } from '../../types/api'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ErrorDetail[]
  readonly requestId: string | null

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? []
    this.requestId = body.request_id
  }

  /** Field-level message for form display, if the server sent one. */
  fieldError(field: string): string | null {
    return this.details.find((d) => d.field === field)?.message ?? null
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}

/** Generic message for display when a request fails outside the envelope (network). */
export function errorMessage(err: unknown): string {
  if (isApiError(err)) return err.message
  if (err instanceof Error) return 'Network error - please try again.'
  return 'Something went wrong.'
}

type UnauthorizedHook = () => void
let onUnauthorized: UnauthorizedHook | null = null

/** Registered by the auth store: called when the session can no longer be restored. */
export function setUnauthorizedHandler(hook: UnauthorizedHook | null): void {
  onUnauthorized = hook
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Query parameters; null/undefined/'' values are dropped. */
  query?: Record<string, string | number | boolean | null | undefined>
  signal?: AbortSignal
  /** Internal: prevents infinite refresh/retry loops. */
  _retried?: boolean
}

function buildQuery(query: RequestOptions['query']): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue
    params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

async function rawRequest(path: string, opts: RequestOptions): Promise<unknown> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, {
    method: opts.method ?? 'GET',
    headers,
    credentials: 'include',
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  })
  const data = await parseBody(res)
  if (!res.ok) {
    const envelope = (data as { error?: ApiErrorBody } | null)?.error
    throw new ApiError(res.status, envelope ?? {
      code: 'UNKNOWN_ERROR',
      message: `Request failed with status ${res.status}.`,
      request_id: null,
      details: [],
    })
  }
  return data
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  try {
    return (await rawRequest(path, opts)) as T
  } catch (err) {
    if (isApiError(err) && err.status === 401 && !opts._retried) {
      // access token may simply be stale: refresh once, then replay the request
      const refreshed = await tryRefresh()
      if (refreshed) return request<T>(path, { ...opts, _retried: true })
      onUnauthorized?.()
    }
    throw err
  }
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    return res.ok
  } catch {
    return false
  }
}
