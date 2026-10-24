<script setup lang="ts">
import { computed } from 'vue'

/** Client-side shortlist pagination. Parent owns the filtered/sorted items. */
const props = defineProps<{
  page: number
  pageSize: number
  totalItems: number
  label: string
}>()
const emit = defineEmits<{
  'update:page': [page: number]
  'update:page-size': [size: number]
}>()
const PAGE_SIZES = [3, 6, 9, 12]
const totalPages = computed(() => Math.max(1, Math.ceil(props.totalItems / props.pageSize)))
const firstItem = computed(() => props.totalItems ? (props.page - 1) * props.pageSize + 1 : 0)
const lastItem = computed(() => Math.min(props.page * props.pageSize, props.totalItems))

// Compact desktop/mobile page buttons, with gaps shown as ellipses.
const pages = computed<(number | '…')[]>(() => {
  const last = totalPages.value
  if (last <= 5) return Array.from({ length: last }, (_, index) => index + 1)
  const unique = new Set([1, last, props.page - 1, props.page, props.page + 1]
    .filter((value) => value >= 1 && value <= last))
  const numbered = [...unique].sort((a, b) => a - b)
  const result: (number | '…')[] = []
  for (const current of numbered) {
    if (result.length && typeof result[result.length - 1] === 'number') {
      const previous = result[result.length - 1] as number
      if (current - previous === 2) result.push(previous + 1)
      if (current - previous > 2) result.push('…')
    }
    result.push(current)
  }
  return result
})
function setPage(value: number) {
  if (value >= 1 && value <= totalPages.value && value !== props.page) emit('update:page', value)
}
function setPageSize(event: Event) {
  const size = Number((event.target as HTMLSelectElement).value)
  if (PAGE_SIZES.includes(size)) emit('update:page-size', size)
}
</script>

<template>
  <nav v-if="totalItems > 0" class="shortlist-pagination" :aria-label="`${label} pagination`">
    <div class="pagination-overview" aria-live="polite">
      <strong>{{ firstItem }}–{{ lastItem }}</strong> of {{ totalItems }} {{ label.toLowerCase() }}
    </div>
    <div class="pagination-navigation" v-if="totalPages > 1">
      <button class="page-direction" type="button" :disabled="page === 1" aria-label="Previous page" @click="setPage(page - 1)">‹ <span>Previous</span></button>
      <template v-for="(number, index) in pages" :key="`${number}-${index}`">
        <span v-if="number === '…'" class="page-ellipsis" aria-hidden="true">…</span>
        <button v-else type="button" class="page-number" :class="{ active: number === page }" :aria-label="`Page ${number}`" :aria-current="number === page ? 'page' : undefined" @click="setPage(number)">{{ number }}</button>
      </template>
      <button class="page-direction" type="button" :disabled="page === totalPages" aria-label="Next page" @click="setPage(page + 1)"><span>Next</span> ›</button>
    </div>
    <label class="pagination-size"><span>Show</span>
      <select :value="pageSize" :aria-label="`${label}: items per page`" @change="setPageSize">
        <option v-for="size in PAGE_SIZES" :key="size" :value="size">{{ size }}</option>
      </select>
      <span>per page</span>
    </label>
  </nav>
</template>

<style scoped>
.shortlist-pagination { --paging-accent: #0c825e; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 15px; padding: 15px 17px; border: 1px solid #deebe4; border-radius: 13px; background: #f8fcfa; color: #668273; font-size: .79rem; }
.pagination-overview { white-space: nowrap; }
.pagination-overview strong { color: #1e5943; font-weight: 850; }
.pagination-navigation { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 5px; }
.pagination-navigation button { display: inline-flex; align-items: center; justify-content: center; font: inherit; font-weight: 780; cursor: pointer; transition: background .15s, border-color .15s; }
.page-number { width: 34px; height: 34px; border: 1px solid #dce9e2; border-radius: 9px; background: #fff; color: #426e5c; }
.page-number.active { background: var(--paging-accent); border-color: var(--paging-accent); color: #fff; box-shadow: 0 4px 12px #0c825e24; }
.page-number:hover:not(.active) { background: #e8f7ef; }
.page-direction { min-height: 34px; gap: 6px; padding: 5px 9px; border: 1px solid #dce9e2; border-radius: 9px; background: #fff; color: #326850; }
.page-direction:hover:not(:disabled) { background: #eaf7ef; }
.pagination-navigation button:disabled { opacity: .42; cursor: not-allowed; }
.page-ellipsis { padding: 0 4px; color: #91a99c; }
.pagination-size { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; color: #768b7f; }
.pagination-size select { font: inherit; font-weight: 750; min-width: 54px; padding: 6px 8px; border-radius: 8px; border: 1px solid #d0e2d7; background: #fff; color: #17523c; cursor: pointer; }
.shortlist-pagination button:focus-visible, .pagination-size select:focus-visible { outline: 2px solid #1cad7a; outline-offset: 2px; }
@media (max-width: 820px) { .shortlist-pagination { justify-content: center; gap: 11px; } .pagination-overview { flex: 1 1 100%; text-align: center; } }
@media (max-width: 490px) { .shortlist-pagination { padding: 13px 10px; } .page-direction span { display: none; } .page-direction { width: 30px; padding: 0; font-size: 1.3rem; } .page-number { width: 30px; height: 32px; } .pagination-navigation { gap: 3px; } .pagination-size { justify-content: center; flex: 1 1 100%; } }
@media (prefers-reduced-motion: reduce) { .pagination-navigation button { transition: none; } }
</style>
