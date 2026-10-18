<script setup lang="ts">
import { computed } from 'vue'
import type { MoneyCell } from '../types/api'
import { formatDate, formatMoney, humanize } from '../utils/format'
import StatusBadge from './StatusBadge.vue'

/**
 * Renders a money fact with currency, period, status and provenance.
 * A missing value is shown as "Not available" - never as zero.
 */
const props = withDefaults(
  defineProps<{ cell: MoneyCell | null | undefined; compact?: boolean }>(),
  { compact: false },
)

const hasValue = computed(() => props.cell?.value !== null && props.cell?.value !== undefined)
const amount = computed(() =>
  hasValue.value ? formatMoney(props.cell?.value ?? null, props.cell?.unit) : 'Not available',
)
const qualifiers = computed(() => {
  const parts: string[] = []
  if (props.cell?.period) parts.push(humanize(props.cell.period))
  if (props.cell?.academic_year) parts.push(props.cell.academic_year)
  return parts.join(' · ')
})
const source = computed(() => props.cell?.source ?? null)
</script>

<template>
  <span class="money-cell">
    <strong>{{ amount }}</strong>
    <StatusBadge v-if="cell?.status" :status="cell.status" class="nowrap" />
    <span v-if="!compact && qualifiers" class="small muted">{{ qualifiers }}</span>
    <span v-if="!compact && source?.title" class="small muted">
      —
      <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
      <template v-else>{{ source.title }}</template>
      <template v-if="source.retrieved_at"> (retrieved {{ formatDate(source.retrieved_at) }})</template>
    </span>
  </span>
</template>
