import { defineStore } from 'pinia'
import { library } from '../services/api/account'
import { useAuthStore } from './auth'

/** Cached set of saved program ids, used by save toggles across the app. */
export const useSavedStore = defineStore('saved', {
  state: () => ({
    ids: [] as string[],
    loaded: false,
    pending: false,
  }),
  actions: {
    async ensureLoaded() {
      const auth = useAuthStore()
      if (!auth.isAuthenticated || this.loaded || this.pending) return
      this.pending = true
      try {
        const res = await library.saved()
        this.ids = res.items.map((item) => item.program_id)
        this.loaded = true
      } catch {
        // non-fatal: toggles still work per action; leave loaded=false to retry later
      } finally {
        this.pending = false
      }
    },
    isSaved(id: string): boolean {
      return this.ids.includes(id)
    },
    /** Toggle a program in the user's shortlist. Returns false when signed out. */
    async toggle(id: string): Promise<boolean> {
      const auth = useAuthStore()
      if (!auth.isAuthenticated) return false
      await this.ensureLoaded()
      if (this.isSaved(id)) {
        await library.unsave(id)
        this.ids = this.ids.filter((savedId) => savedId !== id)
      } else {
        await library.save(id)
        this.ids.push(id)
      }
      return true
    },
  },
})
