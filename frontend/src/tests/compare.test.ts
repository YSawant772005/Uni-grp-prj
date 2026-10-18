import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { COMPARE_LIMIT, useCompareStore } from '../stores/compare'

const STORAGE_KEY = 'uni.compare'

describe('compare store (temporary comparison tray)', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('adds, contains and removes entries', () => {
    const compare = useCompareStore()
    expect(compare.add('p1', 'MSc Data Science')).toBe(true)
    expect(compare.contains('p1')).toBe(true)
    expect(compare.count).toBe(1)
    expect(compare.ids).toEqual(['p1'])

    compare.remove('p1')
    expect(compare.contains('p1')).toBe(false)
    expect(compare.count).toBe(0)
  })

  it('toggles entries in both directions', () => {
    const compare = useCompareStore()
    expect(compare.toggle('p1')).toBe(true)
    expect(compare.contains('p1')).toBe(true)
    expect(compare.toggle('p1')).toBe(true)
    expect(compare.contains('p1')).toBe(false)
  })

  it('is idempotent on duplicate adds', () => {
    const compare = useCompareStore()
    compare.add('p1', 'A')
    compare.add('p1', 'B')
    expect(compare.count).toBe(1)
  })

  it('enforces the backend limit of 6 programs', () => {
    const compare = useCompareStore()
    for (let i = 0; i < COMPARE_LIMIT; i += 1) {
      expect(compare.add(`p${i}`)).toBe(true)
    }
    expect(compare.isFull).toBe(true)
    expect(compare.add('overflow')).toBe(false)
    expect(compare.count).toBe(COMPARE_LIMIT)
    // removing one makes room again
    compare.remove('p0')
    expect(compare.isFull).toBe(false)
    expect(compare.add('overflow')).toBe(true)
  })

  it('persists the tray to localStorage and restores it', () => {
    const compare = useCompareStore()
    compare.add('p1', 'MSc DS')
    compare.add('p2')

    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as { id: string; label?: string }[]
    expect(raw.map((entry) => entry.id)).toEqual(['p1', 'p2'])
    expect(raw[0].label).toBe('MSc DS')

    // a fresh pinia (e.g. page reload) restores the same tray
    setActivePinia(createPinia())
    const restored = useCompareStore()
    expect(restored.ids).toEqual(['p1', 'p2'])
  })

  it('starts empty when localStorage holds corrupt data', () => {
    localStorage.setItem(STORAGE_KEY, '{not json')
    const compare = useCompareStore()
    expect(compare.count).toBe(0)

    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ nope: true }, 'bad', { id: 'ok' }]))
    setActivePinia(createPinia())
    const filtered = useCompareStore()
    expect(filtered.ids).toEqual(['ok'])
  })

  it('truncates oversized stored trays to the limit', () => {
    const many = Array.from({ length: 10 }, (_, i) => ({ id: `p${i}` }))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(many))
    const compare = useCompareStore()
    expect(compare.count).toBe(COMPARE_LIMIT)
  })

  it('setEntries replaces the tray (used by saved comparisons and deep links)', () => {
    const compare = useCompareStore()
    compare.add('old')
    compare.setEntries([{ id: 'a' }, { id: 'b', label: 'B' }])
    expect(compare.ids).toEqual(['a', 'b'])
    compare.clear()
    expect(compare.count).toBe(0)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('[]')
  })
})
