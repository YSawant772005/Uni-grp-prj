<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { finance } from '../../services/api/finance'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { formatMoney, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { CostEstimate, CostItem } from '../../types/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const SCENARIOS = [
  ['low', 'Low', 'Conservative spending assumptions'],
  ['base', 'Base', 'Typical published values'],
  ['high', 'High', 'Upper-bound assumptions'],
] as const

const programId = ref(typeof route.query.program === 'string' ? route.query.program : '')
const scenario = ref<'low' | 'base' | 'high'>('base')
const currency = ref('')
const fundingAmount = ref('')
const fundingCurrency = ref('')

// ------------------------------------------------------- program picker

const searchQuery = ref('')
const searchResults = useAsync(
  () => (searchQuery.value.trim() ? catalog.programs({ q: searchQuery.value.trim(), page_size: 8 }) : Promise.resolve(null)),
  { immediate: false },
)
watch(searchQuery, () => {
  if (searchQuery.value.trim().length >= 2) void searchResults.run()
})

function pick(program: { id: string; name: string }) {
  programId.value = program.id
  searchQuery.value = ''
  void router.replace({ query: { program: program.id } })
}

function clearProgram() {
  programId.value = ''
  void router.replace({ query: {} })
}

// ------------------------------------------------------- estimate request

const estimate = useAsync(
  () =>
    programId.value
      ? finance.estimate({
          program_id: programId.value,
          scenario: scenario.value,
          currency: currency.value || undefined,
          funding_amount: fundingAmount.value ? Number(fundingAmount.value) : undefined,
          funding_currency: fundingCurrency.value || undefined,
        })
      : Promise.resolve(null),
  { immediate: Boolean(programId.value) },
)

watch([programId, scenario, currency], () => {
  if (programId.value) void estimate.run()
})

function refreshWithFunding() {
  if (programId.value) void estimate.run()
}

// three-scenario comparison once a program is chosen
const scenarios = useAsync(
  () => (programId.value ? finance.programEstimates(programId.value) : Promise.resolve(null)),
  { immediate: Boolean(programId.value) },
)
watch(programId, () => {
  if (programId.value) void scenarios.run()
})

// ------------------------------------------------------- save scenario

const saving = ref(false)
const saveName = ref('')

async function saveScenario() {
  if (saving.value || !programId.value) return
  saving.value = true
  try {
    await finance.estimate({
      program_id: programId.value,
      scenario: scenario.value,
      currency: currency.value || undefined,
      funding_amount: fundingAmount.value ? Number(fundingAmount.value) : undefined,
      funding_currency: fundingCurrency.value || undefined,
      save: true,
      name: saveName.value || undefined,
    })
    ui.push('Cost scenario saved to your account.', 'success')
    saveName.value = ''
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    ui.pushError(err)
  } finally {
    saving.value = false
  }
}

// ------------------------------------------------------- derived display

const current = computed<CostEstimate | null>(() => estimate.data.value ?? null)
const allScenarios = computed(() => {
  const map = scenarios.data.value?.scenarios
  return map ? [map.low, map.base, map.high] : []
})
const unavailableItems = computed<CostItem[]>(
  () => (current.value?.items ?? []).filter((item) => item.amount === null),
)
const breakdownWarnings = computed(() => current.value?.data_warnings ?? [])
</script>

<template>
  <div class="stack">
    <div>
      <h1>Cost estimates</h1>
      <p class="muted small" style="margin: 0">
        Full-degree cost model: every component shown separately with its currency, period, status
        and source. Unknown components are listed as unavailable and excluded from the total -
        the total is never inflated or faked.
      </p>
    </div>

    <!-- program picker -->
    <section class="card">
      <h2>1. Choose a program</h2>
      <div v-if="programId" class="row">
        <span class="badge badge-info">Selected</span>
        <RouterLink :to="`/programs/${programId}`"><strong>{{ programId }}</strong></RouterLink>
        <button class="btn btn-sm" type="button" @click="clearProgram">Change</button>
      </div>
      <div v-else class="field">
        <label for="program-search">Search by name</label>
        <input id="program-search" v-model="searchQuery" type="search" placeholder="e.g. Data Science" />
        <ul v-if="searchResults.data.value?.items.length" class="picker-list" style="margin-top: 8px">
          <li v-for="program in searchResults.data.value.items" :key="program.id">
            <button type="button" @click="pick(program)">
              <span>{{ program.name }}</span>
              <span class="small muted">{{ program.university.name }} · {{ program.country_code }}</span>
            </button>
          </li>
        </ul>
        <p v-else-if="searchQuery.length >= 2 && !searchResults.loading.value" class="small muted" style="margin: 8px 0 0">
          No matches - try a different keyword.
        </p>
      </div>
    </section>

    <!-- options -->
    <section v-if="programId" class="card">
      <h2>2. Scenario and currency</h2>
      <div class="grid">
        <div class="field">
          <label for="scenario">Scenario</label>
          <select id="scenario" v-model="scenario">
            <option v-for="[value, label, hint] in SCENARIOS" :key="value" :value="value">
              {{ label }} - {{ hint }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="currency">Target currency</label>
          <select id="currency" v-model="currency">
            <option value="">Automatic (from source data)</option>
            <option v-for="code in ['USD', 'EUR', 'GBP', 'INR', 'AUD', 'CAD', 'CHF', 'SGD']" :key="code" :value="code">
              {{ code }}
            </option>
          </select>
          <span class="help">Conversions use dated reference rates and show the rate source.</span>
        </div>
      </div>
      <div class="grid">
        <div class="field">
          <label for="funding-amount">Known funding / scholarship (optional)</label>
          <input id="funding-amount" v-model="fundingAmount" type="number" min="0" step="any" placeholder="e.g. 15000" />
        </div>
        <div class="field">
          <label for="funding-currency">Funding currency</label>
          <select id="funding-currency" v-model="fundingCurrency">
            <option value="">Same as estimate</option>
            <option v-for="code in ['USD', 'EUR', 'GBP', 'INR', 'AUD', 'CAD', 'CHF', 'SGD']" :key="code" :value="code">
              {{ code }}
            </option>
          </select>
        </div>
      </div>
      <button class="btn btn-sm" type="button" @click="refreshWithFunding">Recompute with funding</button>
    </section>

    <!-- result -->
    <AsyncState
      v-if="programId"
      :loading="estimate.loading.value"
      :error="estimate.error.value"
      :empty="!current"
      empty-title="No estimate yet"
      @retry="estimate.run"
    >
      <div v-if="current" class="stack">
        <div class="card">
          <div class="row-between">
            <h2 style="margin: 0">{{ humanize(current.scenario) }} scenario total</h2>
            <StatusBadge :status="current.total_status" />
          </div>
          <p v-if="current.total !== null" style="font-size: 1.4rem; margin: 8px 0 0">
            <strong>{{ formatMoney(current.total, current.currency) }}</strong>
            <span class="small muted">
              ({{ current.currency }} · sum of the {{ current.items.filter((i) => i.amount !== null).length }} known components)
            </span>
          </p>
          <p v-else class="banner banner-warn" style="margin: 8px 0 0">
            Total unavailable - required components are missing. The estimate below lists exactly what
            is known and what is not.
          </p>
          <dl class="kv" style="margin-top: 10px">
            <dt>Tuition period</dt>
            <dd>{{ current.assumptions.tuition_period ? humanize(current.assumptions.tuition_period) : 'unknown' }}</dd>
            <dt>Duration</dt>
            <dd>{{ current.assumptions.duration_months ? `${current.assumptions.duration_months} months` : 'unknown' }}</dd>
            <dt>Conversion</dt>
            <dd>{{ current.assumptions.currency_conversion ?? 'No conversion applied' }}</dd>
            <dt>Calculation version</dt>
            <dd class="mono">{{ current.calculation_version }}</dd>
            <template v-if="current.funding_amount !== null">
              <dt>Known funding</dt>
              <dd>{{ formatMoney(current.funding_amount, current.funding_currency ?? current.currency) }}</dd>
              <dt>Gap after funding</dt>
              <dd>{{ current.funding_gap !== null ? formatMoney(current.funding_gap, current.currency) : 'Not computable' }}</dd>
            </template>
          </dl>
        </div>

        <!-- warnings -->
        <div v-if="breakdownWarnings.length" class="banner banner-warn" role="status">
          <strong>Notes on this estimate</strong>
          <ul style="margin: 4px 0 0; padding-left: 18px">
            <li v-for="warning in breakdownWarnings" :key="warning" class="small mono">{{ warning }}</li>
          </ul>
        </div>

        <!-- component breakdown -->
        <div class="card">
          <h2>Component breakdown</h2>
          <div class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Component</th>
                  <th>Amount</th>
                  <th>Period</th>
                  <th>Status</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in current.items" :key="item.cost_type">
                  <td>{{ item.label }}</td>
                  <td>
                    <template v-if="item.amount !== null">
                      <strong>{{ formatMoney(item.amount, item.currency) }}</strong>
                      <span v-if="item.converted_from" class="small muted"> (from {{ item.converted_from }})</span>
                    </template>
                    <span v-else class="muted">Not available</span>
                  </td>
                  <td class="small">{{ item.period ? humanize(item.period) : '—' }}</td>
                  <td><StatusBadge :status="item.status" /></td>
                  <td class="small">{{ item.note ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="unavailableItems.length" class="small muted" style="margin: 8px 0 0">
            {{ unavailableItems.length }} component{{ unavailableItems.length > 1 ? 's' : '' }} unavailable
            ({{ unavailableItems.map((item) => item.label).join(', ') }}) - excluded from the total, not
            counted as zero.
          </p>
        </div>

        <!-- three-scenario comparison -->
        <div v-if="allScenarios.length === 3" class="card">
          <h2>All scenarios at a glance</h2>
          <div class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in allScenarios" :key="entry.scenario">
                  <td>{{ humanize(entry.scenario) }}</td>
                  <td>{{ entry.total !== null ? formatMoney(entry.total, entry.currency) : 'Not available' }}</td>
                  <td><StatusBadge :status="entry.total_status" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- save -->
        <div v-if="auth.isAuthenticated" class="card">
          <h2>Save this scenario</h2>
          <div class="row">
            <input v-model="saveName" type="text" placeholder="Name (optional)" aria-label="Scenario name" style="max-width: 320px" />
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveScenario">
              {{ saving ? 'Saving…' : 'Save scenario' }}
            </button>
          </div>
        </div>
        <p v-else class="small muted">
          <RouterLink :to="{ path: '/login', query: { redirect: route.fullPath } }">Log in</RouterLink>
          to save this scenario for later.
        </p>

      </div>
    </AsyncState>

    <div class="banner banner-info">
      Estimates combine published facts with scenario assumptions. They are not quotes and do not
      include costs a university has not published. Check the official page before committing funds -
      every row links its source.
    </div>
  </div>
</template>
