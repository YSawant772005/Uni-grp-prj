import { defineStore } from 'pinia'

/** Backend compare endpoint accepts 2..6 programs; mirror the ceiling here. */
export const COMPARE_LIMIT = 6

const STORAGE_KEY = 'uni.compare'

export interface CompareEntry {
  id: string
  label?: string
}

function load(): CompareEntry[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    if (Array.isArray(raw)) {
      return raw
        .filter((entry): entry is CompareEntry => typeof (entry as CompareEntry)?.id === 'string')
        .slice(0, COMPARE_LIMIT)
    }
  } catch {
    // corrupt storage is not fatal - start empty
  }
  return []
}

/** In-app comparison tray (temporary compare set), persisted locally. */
export const useCompareStore = defineStore('compare', {
  state: () => ({ entries: load() as CompareEntry[] }),
  getters: {
    ids: (s): string[] => s.entries.map((entry) => entry.id),
    count: (s): number => s.entries.length,
    isFull(): boolean {
      return this.count >= COMPARE_LIMIT
    },
  },
  actions: {
    contains(id: string): boolean {
      return this.entries.some((entry) => entry.id === id)
    },
    /** Returns false when the tray is full (caller informs the user). */
    add(id: string, label?: string): boolean {
      if (this.contains(id)) return true
      if (this.entries.length >= COMPARE_LIMIT) return false
      this.entries.push({ id, label })
      this.persist()
      return true
    },
    remove(id: string) {
      this.entries = this.entries.filter((entry) => entry.id !== id)
      this.persist()
    },
    toggle(id: string, label?: string): boolean {
      if (this.contains(id)) {
        this.remove(id)
        return true
      }
      return this.add(id, label)
    },
    clear() {
      this.entries = []
      this.persist()
    },
    setEntries(entries: CompareEntry[]) {
      this.entries = entries.slice(0, COMPARE_LIMIT)
      this.persist()
    },
    persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.entries))
    },
  },
})
