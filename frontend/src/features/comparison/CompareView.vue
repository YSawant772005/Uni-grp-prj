<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { library } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useCompareStore } from '../../stores/compare'
import { useUiStore } from '../../stores/ui'
import { humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import MoneyCell from '../../components/MoneyCell.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { COMPARE_LIMIT } from '../../stores/compare'
import type { CompareItem } from '../../types/api'

const route = useRoute()
const router = useRouter()
const compare = useCompareStore()
const ui = useUiStore()

// allow ?ids=a,b,c deep links (shareable comparison sets)
watch(
  () => route.query.ids,
  (raw) => {
    if (typeof raw !== 'string' || !raw) return
    const ids = raw.split(',').map((s) => s.trim()).filter(Boolean)
    if (ids.length) compare.setEntries(ids.map((id) => ({ id })))
  },
  { immediate: true },
)

const selectedIds = computed(() => compare.ids)

const results = useAsync(
  () => (selectedIds.value.length >= 2 ? library.compare(selectedIds.value) : Promise.resolve(null)),
  { immediate: true },
)

watch(selectedIds, (ids) => {
  void router.replace({ query: ids.length ? { ids: ids.join(',') } : {} })
  if (ids.length >= 2) void results.run()
})

const items = computed<CompareItem[]>(() => results.data.value?.items ?? [])
const tooFew = computed(() => selectedIds.value.length < 2)

// ---------------------------------------------------------------- saved comparisons

const savedComparisons = useAsync(() => library.comparisons(), { immediate: true })
const saving = ref(false)
const saveTitle = ref('')

async function saveComparison() {
  if (saving.value || selectedIds.value.length < 2) return
  saving.value = true
  try {
    await library.createComparison(selectedIds.value, saveTitle.value || 'My comparison')
    ui.push('Comparison saved to your account.', 'success')
    saveTitle.value = ''
    await savedComparisons.run()
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: '/compare' } })
      return
    }
    ui.pushError(err)
  } finally {
    saving.value = false
  }
}

async function removeComparison(id: string) {
  try {
    await library.deleteComparison(id)
    ui.push('Saved comparison deleted.', 'success')
    await savedComparisons.run()
  } catch (err) {
    ui.pushError(err)
  }
}

// ---------------------------------------------------------------- attribute rows

interface Row {
  label: string
  render: (item: CompareItem) => string | { component: 'money'; cell: CompareItem['tuition'] } | { component: 'status'; status: string | null; fallback: string }
}

const rows: Row[] = [
  { label: 'Programme', render: (i) => i.name },
  { label: 'University', render: (i) => i.university },
  { label: 'Country', render: (i) => i.country_code },
  { label: 'Degree level', render: (i) => humanize(i.degree_level) },
  { label: 'Duration', render: (i) => (i.duration_months ? `${i.duration_months} months` : 'Not available') },
  { label: 'Language', render: (i) => humanize(i.language) },
  {
    label: 'Tuition',
    render: (i) => ({ component: 'money', cell: i.tuition }),
  },
  {
    label: 'Nearest deadline',
    render: (i) => (i.nearest_deadline ? new Date(i.nearest_deadline).toLocaleDateString() : 'Not published'),
  },
  {
    label: 'Requirements (published)',
    render: (i) => `${i.requirements_total} total, ${i.requirements_unverified} unverified`,
  },
  { label: 'Recognition', render: (i) => humanize(i.recognition_status) },
  {
    label: 'Eligibility vs your profile',
    render: (i) => ({ component: 'status', status: i.eligibility_status, fallback: 'Not evaluated - run a shortlist first' }),
  },
  {
    label: 'Data confidence',
    render: (i) => ({ component: 'status', status: i.data_quality.status, fallback: 'Unknown' }),
  },
]
</script>

<template>
  <div class="stack">
    <div>
      <h1>Compare programs</h1>
      <p class="muted small" style="margin: 0">
        Up to {{ COMPARE_LIMIT }} programmes, aligned attribute-by-attribute. Missing or incomparable
        values are labelled - never shown as zero. Cost figures keep their currency and period; check
        the basis before comparing across countries.
      </p>
    </div>

    <!-- tray controls -->
    <section class="card">
      <div class="row-between">
        <strong>{{ selectedIds.length }} of {{ COMPARE_LIMIT }} selected</strong>
        <button v-if="selectedIds.length" class="btn btn-sm" type="button" @click="compare.clear()">
          Clear all
        </button>
      </div>
      <ul class="row" style="list-style: none; padding: 0; margin: 8px 0 0">
        <li v-for="entry in compare.entries" :key="entry.id" class="chip badge badge-neutral">
          {{ entry.label ?? `Program ${entry.id.slice(0, 8)}…` }}
          <button
            type="button"
            :aria-label="`Remove ${entry.label ?? 'program'} from comparison`"
            style="border: none; background: none; cursor: pointer"
            @click="compare.remove(entry.id)"
          >
            ×
          </button>
        </li>
      </ul>
      <p v-if="tooFew" class="small muted" style="margin: 8px 0 0">
        Select at least two programmes to compare -
        <RouterLink to="/discover">add them from discovery</RouterLink> or your
        <RouterLink to="/saved">saved list</RouterLink>.
      </p>
    </section>

    <AsyncState
      :loading="results.loading.value"
      :error="results.error.value"
      :empty="!items.length"
      :hide-empty="tooFew"
      empty-title="Nothing to compare yet"
      empty-hint="Add programmes using the Compare button on any card."
      @retry="results.run"
    >
      <div v-if="items.length" class="stack">
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th scope="col">Attribute</th>
                <th v-for="item in items" :key="item.program_id" scope="col">
                  <RouterLink :to="`/programs/${item.program_id}`">{{ item.name }}</RouterLink>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.label">
                <th scope="row" style="background: var(--bg)">{{ row.label }}</th>
                <td v-for="item in items" :key="item.program_id + row.label">
                  <template v-if="typeof row.render(item) === 'string'">
                    {{ row.render(item) }}
                  </template>
                  <template v-else-if="'component' in (row.render(item) as object) && (row.render(item) as { component: string }).component === 'money'">
                    <MoneyCell :cell="(row.render(item) as { cell: CompareItem['tuition'] }).cell" compact />
                  </template>
                  <template v-else>
                    <StatusBadge
                      :status="(row.render(item) as { status: string | null }).status"
                      :label="!(row.render(item) as { status: string | null }).status ? (row.render(item) as { fallback: string }).fallback : undefined"
                    />
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- save -->
        <section class="card">
          <h2>Save this comparison</h2>
          <div class="row">
            <input
              v-model="saveTitle"
              type="text"
              placeholder="Comparison title (optional)"
              aria-label="Comparison title"
              style="max-width: 320px"
            />
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveComparison">
              {{ saving ? 'Saving…' : 'Save comparison' }}
            </button>
          </div>
          <p class="small muted" style="margin: 6px 0 0">
            Saved comparisons are private to your account and can be reopened later.
          </p>
        </section>
      </div>
    </AsyncState>

    <!-- saved comparisons list -->
    <section v-if="savedComparisons.data.value?.items.length" class="stack">
      <h2>Saved comparisons</h2>
      <div v-for="comparison in savedComparisons.data.value.items" :key="comparison.id" class="card row-between">
        <div>
          <strong>{{ comparison.title }}</strong>
          <div class="small muted">{{ comparison.program_ids.length }} programmes</div>
        </div>
        <div class="row">
          <button
            class="btn btn-sm"
            type="button"
            @click="compare.setEntries(comparison.program_ids.map((id) => ({ id }))); router.push('/compare')"
          >
            Open
          </button>
          <button class="btn btn-sm btn-quiet" type="button" @click="removeComparison(comparison.id)">
            Delete
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
