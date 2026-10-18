import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  errorMessage,
  isApiError,
  request,
  setUnauthorizedHandler,
} from '../services/api/client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const envelope = {
  error: {
    code: 'VALIDATION_ERROR',
    message: 'One or more fields are invalid.',
    request_id: 'req-123',
    details: [{ field: 'reason', code: 'missing', message: 'reason is required.' }],
  },
}

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    setUnauthorizedHandler(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
  })

  it('parses the error envelope into ApiError', async () => {
    vi.mocked(fetch).mockImplementation(async () => jsonResponse(422, envelope))

    await expect(request('/x')).rejects.toSatisfy(isApiError)

    try {
      await request('/x')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      const apiError = err as ApiError
      expect(apiError.status).toBe(422)
      expect(apiError.code).toBe('VALIDATION_ERROR')
      expect(apiError.requestId).toBe('req-123')
      expect(apiError.fieldError('reason')).toBe('reason is required.')
      expect(apiError.fieldError('other')).toBeNull()
    }
  })

  it('falls back to a generic error when the body is not the envelope', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('oops', { status: 500 }))

    try {
      await request('/x')
      expect.unreachable()
    } catch (err) {
      const apiError = err as ApiError
      expect(apiError.status).toBe(500)
      expect(apiError.code).toBe('UNKNOWN_ERROR')
      expect(apiError.details).toEqual([])
    }
  })

  it('refreshes once on 401 and replays the original request', async () => {
    const unauthorized = jsonResponse(401, {
      error: { code: 'UNAUTHENTICATED', message: 'Sign in.', request_id: null, details: [] },
    })
    vi.mocked(fetch)
      .mockResolvedValueOnce(unauthorized)
      .mockResolvedValueOnce(jsonResponse(204, null)) // refresh succeeds
      .mockResolvedValueOnce(jsonResponse(200, { items: [] }))

    const result = await request<{ items: unknown[] }>('/protected')

    expect(result).toEqual({ items: [] })
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3)
    const [refreshCall, replayCall] = [vi.mocked(fetch).mock.calls[1], vi.mocked(fetch).mock.calls[2]]
    expect(String(refreshCall[0])).toContain('/auth/refresh')
    expect(String(replayCall[0])).toContain('/protected')
    expect(replayCall[1]?.credentials).toBe('include')
  })

  it('does not loop refresh/retry when refresh itself fails', async () => {
    const unauthorized = jsonResponse(401, {
      error: { code: 'UNAUTHENTICATED', message: 'Sign in.', request_id: null, details: [] },
    })
    vi.mocked(fetch).mockResolvedValue(unauthorized)
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(request('/protected')).rejects.toMatchObject({ status: 401 })
    // original + refresh, no replay
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('fires the unauthorized handler for a plain 401 after failed refresh', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(401, {
        error: { code: 'UNAUTHENTICATED', message: 'Sign in.', request_id: null, details: [] },
      }),
    )
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(request('/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalled()
  })

  it('does not fire the unauthorized handler on non-401 errors', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, {
      error: { code: 'NOT_FOUND', message: 'Gone.', request_id: null, details: [] },
    }))
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(request('/missing')).rejects.toMatchObject({ status: 404 })
    expect(handler).not.toHaveBeenCalled()
  })

  it('drops empty query parameters', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, {}))

    await request('/list', { query: { q: 'ds', country: '', page: undefined, size: 10 } })

    const url = String(vi.mocked(fetch).mock.calls[0][0])
    expect(url).toContain('q=ds')
    expect(url).toContain('size=10')
    expect(url).not.toContain('country=')
    expect(url).not.toContain('page=')
  })

  it('maps network failures to a friendly message', () => {
    expect(errorMessage(new TypeError('fetch failed'))).toBe('Network error - please try again.')
    expect(errorMessage(new ApiError(400, envelope.error))).toBe('One or more fields are invalid.')
    expect(errorMessage('weird')).toBe('Something went wrong.')
  })

  it('sends JSON bodies with content-type and includes cookies', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(201, { id: '1' }))

    await request('/things', { method: 'POST', body: { name: 'x' } })

    const call = vi.mocked(fetch).mock.calls[0]
    expect(call[1]?.method).toBe('POST')
    expect(call[1]?.credentials).toBe('include')
    expect(call[1]?.body).toBe(JSON.stringify({ name: 'x' }))
    expect((call[1]?.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })
})
