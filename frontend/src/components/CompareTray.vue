<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { COMPARE_LIMIT, useCompareStore } from '../stores/compare'

/** Floating comparison tray (UI doc section 6.4): count, remove, clear, go compare. */
const compare = useCompareStore()
const route = useRoute()

const visible = computed(() => compare.count > 0 && !route.path.startsWith('/compare'))
</script>

<template>
  <aside v-if="visible" class="compare-tray" aria-label="Comparison tray">
    <strong>{{ compare.count }} of {{ COMPARE_LIMIT }} selected</strong>
    <ul class="tray-chips">
      <li v-for="entry in compare.entries" :key="entry.id" class="chip">
        {{ entry.label ?? `Program ${entry.id.slice(0, 8)}…` }}
        <button
          type="button"
          :aria-label="`Remove ${entry.label ?? 'program'} from comparison`"
          @click="compare.remove(entry.id)"
        >
          ×
        </button>
      </li>
    </ul>
    <RouterLink to="/compare" class="btn btn-primary btn-sm">Compare now</RouterLink>
    <button class="btn btn-quiet btn-sm compare-tray-clear" type="button" @click="compare.clear()">
      Clear
    </button>
  </aside>
</template>

<style scoped>
.compare-tray-clear {
  color: #cbd5e1;
}
.compare-tray-clear:hover {
  background: rgb(255 255 255 / 12%);
}
</style>
