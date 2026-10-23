<script setup lang="ts">
import type { ProgramDetail, ProgramSummary } from '../types/api'
import { academicLabel, pageStatus, qualityWarnings } from '../utils/programQuality'
import StatusBadge from './StatusBadge.vue'

defineProps<{ program: ProgramSummary & Partial<ProgramDetail>; details?: boolean }>()
</script>

<template>
  <div class="stack-sm small" :class="details ? 'banner banner-warn' : ''" role="status">
    <div>Official program page: <StatusBadge :status="pageStatus(program)" /></div>
    <div>Academic information: <strong>{{ academicLabel(program) }}</strong></div>
    <template v-if="details">
      <p class="small muted" style="margin: 0">Page verification does not verify every academic detail or determine admission.</p>
      <ul v-if="qualityWarnings(program).length" style="margin: 0; padding-left: 18px">
        <li v-for="warning in qualityWarnings(program)" :key="warning">{{ warning }}</li>
      </ul>
    </template>
  </div>
</template>
