<script setup lang="ts">
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
</script>

<template>
  <div class="toast-stack" aria-live="polite">
    <div
      v-for="toast in ui.toasts"
      :key="toast.id"
      class="toast"
      :class="`toast-${toast.tone}`"
      :role="toast.tone === 'error' ? 'alert' : 'status'"
    >
      <span>{{ toast.text }}</span>
      <button type="button" aria-label="Dismiss notification" @click="ui.dismiss(toast.id)">×</button>
    </div>
  </div>
</template>
