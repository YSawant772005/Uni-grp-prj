<script setup lang="ts">
import type { ProgramSummary } from '../types/api'
import { formatDate, formatDuration } from '../utils/format'
import CompareToggle from './CompareToggle.vue'
import MoneyCell from './MoneyCell.vue'
import SaveToggle from './SaveToggle.vue'
import ProgramQuality from './ProgramQuality.vue'

/** Catalogue result card (UI doc section 7.4). No eligibility claims here:
 * eligibility requires evaluating the profile, which catalogue data alone lacks. */
defineProps<{ program: ProgramSummary }>()
</script>

<template>
  <article class="card stack-sm">
    <div class="row-between">
      <RouterLink :to="`/programs/${program.id}`">
        <h3 style="margin: 0">{{ program.name }}</h3>
      </RouterLink>
      <ProgramQuality :program="program" />
    </div>
    <p class="small muted" style="margin: 0">
      {{ program.university.name }} · {{ program.university.city ?? 'City not available' }}, {{ program.country_code }}
    </p>
    <p class="small" style="margin: 0">
      {{ program.degree_level }} · {{ program.field?.display_name ?? 'Field not available' }}
      · {{ program.duration_months ? formatDuration(program.duration_months) : 'Duration not available' }}
      · {{ program.language ?? 'Language not specified' }}
    </p>
    <p class="small" style="margin: 0">
      <strong>Tuition:</strong>
      <MoneyCell :cell="program.tuition_summary" compact />
    </p>
    <p v-if="program.nearest_intake" class="small muted" style="margin: 0">
      Next intake {{ program.nearest_intake.intake_term }} {{ program.nearest_intake.intake_year }}
      <template v-if="program.nearest_intake.application_deadline">
        · deadline {{ formatDate(program.nearest_intake.application_deadline) }}</template
      ><template v-else> · deadline not available</template><template v-if="program.nearest_intake.is_open_for_applications"> · open now</template>
    </p>
    <p v-else class="small muted" style="margin: 0">Intake and deadline not available</p>
    <div class="row">
      <SaveToggle :program-id="program.id" />
      <CompareToggle :program-id="program.id" :label="program.name" />
      <RouterLink class="btn btn-sm btn-quiet" :to="`/finance?program=${program.id}`">Estimate costs</RouterLink>
    </div>
  </article>
</template>
