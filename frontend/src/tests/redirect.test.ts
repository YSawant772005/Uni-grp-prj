import { describe, expect, it } from 'vitest'
import { safeRedirect } from '../router'

describe('safeRedirect (open-redirect guard, UI doc section 4/5)', () => {
  it('accepts local absolute paths', () => {
    expect(safeRedirect('/discover')).toBe('/discover')
    expect(safeRedirect('/programs/abc?tab=evidence')).toBe('/programs/abc?tab=evidence')
    expect(safeRedirect('/login?redirect=/shortlist/run-1')).toBe('/login?redirect=/shortlist/run-1')
    expect(safeRedirect('/')).toBe('/')
  })

  it('rejects absolute URLs', () => {
    expect(safeRedirect('https://evil.example')).toBeNull()
    expect(safeRedirect('http://evil.example/path')).toBeNull()
    expect(safeRedirect('//evil.example')).toBeNull()
    expect(safeRedirect('//evil.example/path')).toBeNull()
  })

  it('rejects protocol-relative tricks and backslash escapes', () => {
    expect(safeRedirect('/\\evil.example')).toBeNull()
    expect(safeRedirect('\\evil')).toBeNull()
  })

  it('rejects non-string or empty values', () => {
    expect(safeRedirect(undefined)).toBeNull()
    expect(safeRedirect(null)).toBeNull()
    expect(safeRedirect(42)).toBeNull()
    expect(safeRedirect('')).toBeNull()
    expect(safeRedirect('discover')).toBeNull() // relative path is not local-app-safe
  })
})
