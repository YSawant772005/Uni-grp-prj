<script setup lang="ts">
import { onMounted } from 'vue'
import { library } from '../../services/api/account'
import { useAsync } from '../../composables/useAsync'
import { useSavedStore } from '../../stores/saved'
import { useUiStore } from '../../stores/ui'
import { formatDate } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import CompareToggle from '../../components/CompareToggle.vue'
import MoneyCell from '../../components/MoneyCell.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const savedStore = useSavedStore()
const ui = useUiStore()

const listState = useAsync(() => library.saved(), { immediate: true })

onMounted(() => void savedStore.ensureLoaded())

async function remove(programId: string) {
  try {
    await library.unsave(programId)
    ui.push('Removed from saved programs.', 'success')
    savedStore.ids = savedStore.ids.filter((id) => id !== programId)
    await listState.run()
  } catch (err) {
    ui.pushError(err)
  }
}
</script>

<template>
  <div class="stack">
    <div>
      <h1>Saved programs</h1>
      <p class="muted small" style="margin: 0">
        Your shortlist of programmes to revisit. Save or unsave from any card or detail page.
      </p>
    </div>

    <AsyncState
      :loading="listState.loading.value"
      :error="listState.error.value"
      :empty="!listState.data.value?.items.length"
      empty-title="No saved programs yet"
      empty-hint="Browse discovery and use the Save button on any programme that looks interesting."
      @retry="listState.run"
    >
      <template #empty-action>
        <RouterLink to="/discover" class="btn btn-primary">Explore programs</RouterLink>
      </template>

      <div v-if="listState.data.value?.items.length" class="grid">
        <article v-for="item in listState.data.value.items" :key="item.program_id" class="card stack-sm">
          <div class="row-between">
            <RouterLink :to="`/programs/${item.program_id}`">
              <h3 style="margin: 0">{{ item.program.name }}</h3>
            </RouterLink>
            <StatusBadge :status="item.program.data_quality.status" />
          </div>
          <p class="small muted" style="margin: 0">
            {{ item.program.university.name }} · {{ item.program.country_code }}
          </p>
          <p class="small" style="margin: 0">
            <strong>Tuition:</strong>
            <MoneyCell :cell="item.program.tuition_summary" compact />
          </p>
          <p v-if="item.note" class="small" style="margin: 0">Note: “{{ item.note }}”</p>
          <p v-if="item.saved_at" class="small muted" style="margin: 0">Saved {{ formatDate(item.saved_at) }}</p>
          <div class="row">
            <CompareToggle :program-id="item.program_id" :label="item.program.name" />
            <RouterLink class="btn btn-sm" :to="`/programs/${item.program_id}`">Open</RouterLink>
            <button class="btn btn-sm btn-quiet" type="button" @click="remove(item.program_id)">Remove</button>
          </div>
        </article>
      </div>
    </AsyncState>
  </div>
</template>
