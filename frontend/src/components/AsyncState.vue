<script setup lang="ts">
import { computed } from 'vue'
import { errorMessage } from '../services/api/client'

/**
 * Loading / error / empty / content state machine required by UI doc section 8.
 * Shows stale content while revalidating when data already exists.
 */
const props = withDefaults(
  defineProps<{
    loading?: boolean
    error?: unknown
    empty?: boolean
    emptyTitle?: string
    emptyHint?: string
    /** Skip the empty block when the default slot should render anyway. */
    hideEmpty?: boolean
  }>(),
  { loading: false, error: undefined, empty: false, emptyTitle: 'Nothing here yet', emptyHint: '', hideEmpty: false },
)

const emit = defineEmits<{ retry: [] }>()

const showLoading = computed(() => props.loading && !props.error)
const showError = computed(() => props.error !== undefined && props.error !== null)
const showEmpty = computed(() => !showError.value && !showLoading.value && props.empty && !props.hideEmpty)
</script>

<template>
  <div :aria-busy="loading ? 'true' : undefined">
    <div v-if="showLoading" class="stack-sm" role="status" aria-label="Loading">
      <slot name="loading">
        <div class="skeleton wide" />
        <div class="skeleton mid" />
        <div class="skeleton short" />
      </slot>
    </div>

    <div v-else-if="showError" class="state-block" role="alert">
      <p class="state-title">Could not load this content</p>
      <p>{{ errorMessage(error) }}</p>
      <button class="btn" type="button" @click="emit('retry')">Try again</button>
    </div>

    <div v-else-if="showEmpty" class="state-block">
      <p class="state-title">{{ emptyTitle }}</p>
      <p v-if="emptyHint">{{ emptyHint }}</p>
      <slot name="empty-action" />
    </div>

    <slot v-else />
  </div>
</template>
