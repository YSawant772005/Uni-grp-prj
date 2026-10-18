import { defineStore } from 'pinia'
import { auth } from '../services/api/account'
import { isApiError } from '../services/api/client'
import type { AuthUser } from '../types/api'

/**
 * localStorage marker meaning "a session may exist". It avoids probing
 * /auth/refresh (rate-limited) for clearly anonymous visitors, and it is
 * removed whenever the backend says the session is gone.
 */
const SESSION_MARKER = 'uni.session'

interface AuthState {
  user: AuthUser | null
  loaded: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({ user: null, loaded: false }),
  getters: {
    isAuthenticated: (s): boolean => s.user !== null,
    roleKeys: (s): string[] => s.user?.roles ?? [],
    isAdmin(): boolean {
      return this.roleKeys.includes('admin')
    },
    isReviewer(): boolean {
      return this.roleKeys.includes('reviewer') || this.isAdmin
    },
  },
  actions: {
    /** Called from the router guard exactly once per page load. */
    async ensureLoaded() {
      if (this.loaded) return
      if (typeof localStorage === 'undefined' || localStorage.getItem(SESSION_MARKER) !== '1') {
        this.loaded = true
        this.user = null
        return
      }
      try {
        this.user = await auth.me()
        this.loaded = true
      } catch (err) {
        this.user = null
        this.loaded = true
        // only forget the session when the backend confirmed it is gone
        if (isApiError(err) && err.status === 401) this.clearSession()
      }
    },
    async login(email: string, password: string) {
      this.user = await auth.login(email, password)
      this.loaded = true
      this.markSession()
    },
    async register(email: string, password: string) {
      this.user = await auth.register(email, password)
      this.loaded = true
      this.markSession()
    },
    async logout() {
      try {
        await auth.logout()
      } finally {
        this.user = null
        this.loaded = true
        this.clearSession()
      }
    },
    /** Invoked by the client's unauthorized handler when refresh failed. */
    clearUser() {
      this.user = null
      this.loaded = true
      this.clearSession()
    },
    markSession() {
      localStorage.setItem(SESSION_MARKER, '1')
    },
    clearSession() {
      localStorage.removeItem(SESSION_MARKER)
    },
  },
})
