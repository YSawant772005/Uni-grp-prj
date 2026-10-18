<script setup lang="ts">
import { computed } from 'vue'
import { humanize } from '../utils/format'

/** Text+colour status pill. Colour is never the only signal (UI doc section 9). */
const props = defineProps<{ status: string | null | undefined; label?: string }>()

const MAP: Record<string, string> = {
  // fact / record lifecycle
  verified: 'ok',
  official: 'ok',
  recognized: 'ok',
  candidate: 'warn',
  unverified: 'warn',
  estimated: 'info',
  stale: 'warn',
  conflicted: 'danger',
  in_review: 'info',
  rejected: 'danger',
  superseded: 'neutral',
  unavailable: 'neutral',
  unknown: 'neutral',
  partial: 'warn',
  fresh: 'ok',
  not_officially_recognized: 'danger',
  under_review: 'info',
  // eligibility outcomes
  eligible: 'ok',
  conditionally_eligible: 'warn',
  ineligible: 'danger',
  unknown_needs_review: 'warn',
  // scholarship matching
  match: 'ok',
  matching: 'ok',
  possible_match: 'warn',
  needs_review: 'warn',
  no_match: 'neutral',
  not_matching: 'neutral',
  not_eligible: 'danger',
  needs_manual_review: 'warn',
  // rule evaluation outcomes
  pass: 'ok',
  fail: 'danger',
  conditional: 'warn',
  // evidence direction
  supports: 'ok',
  conflicts: 'danger',
  // jobs
  queued: 'info',
  running: 'info',
  succeeded: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
  // application / fetch states
  open: 'ok',
  closed: 'neutral',
  skipped: 'neutral',
}

const TEXT: Record<string, string> = {
  candidate: 'Candidate (not verified)',
  unverified: 'Unverified',
  estimated: 'Estimated',
  stale: 'Stale - needs refresh',
  conflicted: 'Conflicted',
  in_review: 'In review',
  superseded: 'Superseded',
  unavailable: 'Not available',
  unknown: 'Unknown',
  partial: 'Partial data',
  fresh: 'Fresh',
  not_officially_recognized: 'Not officially recognized',
  conditionally_eligible: 'Conditionally eligible',
  unknown_needs_review: 'Needs manual review',
  possible_match: 'Possible match',
  needs_review: 'Needs review',
  no_match: 'No clear match',
  not_matching: 'No match on published rules',
  needs_manual_review: 'Needs manual review',
  pass: 'Meets rule',
  fail: 'Does not meet',
  conditional: 'Conditional',
  open: 'Open for applications',
}

const tone = computed(() => MAP[props.status ?? ''] ?? 'neutral')
const text = computed(() => props.label ?? TEXT[props.status ?? ''] ?? humanize(props.status))
</script>

<template>
  <span class="badge" :class="`badge-${tone}`">{{ text }}</span>
</template>
