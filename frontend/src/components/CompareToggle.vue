<script setup lang="ts">
import { computed } from 'vue'
import { COMPARE_LIMIT, useCompareStore } from '../stores/compare'
import { useUiStore } from '../stores/ui'

/** Add/remove a program from the comparison tray; explains the limit when full. */
const props = defineProps<{ programId: string; label?: string }>()

const compare = useCompareStore()
const ui = useUiStore()

const inCompare = computed(() => compare.contains(props.programId))

function toggle() {
  const ok = compare.toggle(props.programId, props.label)
  if (!ok) {
    ui.push(`Compare supports up to ${COMPARE_LIMIT} programs. Remove one before adding another.`, 'error')
  }
}
</script>

<template>
  <button class="btn btn-sm" type="button" :aria-pressed="inCompare" @click="toggle">
    {{ inCompare ? 'In compare ✓' : 'Compare' }}
  </button>
</template>
