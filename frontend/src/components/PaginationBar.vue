<script setup lang="ts">
import { computed } from 'vue'

/** Server-driven pagination controls (UI doc section 7.4). */
const props = defineProps<{
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}>()

const emit = defineEmits<{ 'update:page': [page: number] }>()

const hasPrev = computed(() => props.page > 1)
const hasNext = computed(() => props.page < props.totalPages)
const range = computed(() => {
  if (props.totalItems === 0) return ''
  const start = (props.page - 1) * props.pageSize + 1
  const end = Math.min(props.page * props.pageSize, props.totalItems)
  return `${start}-${end} of ${props.totalItems}`
})
</script>

<template>
  <nav v-if="totalPages > 1 || totalItems > 0" class="row-between" aria-label="Pagination">
    <span class="small muted" aria-live="polite">{{ range }}</span>
    <div class="row">
      <button class="btn btn-sm" type="button" :disabled="!hasPrev" @click="emit('update:page', page - 1)">
        ← Previous
      </button>
      <span class="small muted">Page {{ page }} of {{ Math.max(totalPages, 1) }}</span>
      <button class="btn btn-sm" type="button" :disabled="!hasNext" @click="emit('update:page', page + 1)">
        Next →
      </button>
    </div>
  </nav>
</template>
