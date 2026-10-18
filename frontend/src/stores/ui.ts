import { defineStore } from 'pinia'
import { isApiError } from '../services/api/client'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'success' | 'error'
}

/** Transient user feedback (toasts). Error toasts surface API messages verbatim. */
export const useUiStore = defineStore('ui', {
  state: () => ({ toasts: [] as Toast[], seq: 0 }),
  actions: {
    push(text: string, tone: Toast['tone'] = 'info') {
      const id = ++this.seq
      this.toasts.push({ id, text, tone })
      setTimeout(() => this.dismiss(id), 7000)
    },
    dismiss(id: number) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
    /** Show an error with the server's message; include request id for support. */
    pushError(err: unknown) {
      let text = 'Something went wrong. Please try again.'
      if (isApiError(err)) {
        text = err.message
        if (err.requestId) text += ` (reference ${err.requestId})`
      } else if (err instanceof Error && err.message === 'Network error - please try again.') {
        text = err.message
      }
      this.push(text, 'error')
    },
  },
})
