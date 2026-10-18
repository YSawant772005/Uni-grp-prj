<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { catalog } from '../../services/api/catalog'
import { finance } from '../../services/api/finance'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { formatDateTime, formatMoney, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { RoiScenario } from '../../types/api'

const auth = useAuthStore()
const ui = useUiStore()

// ------------------------------------------------- public: career evidence search

const outcomeQuery = reactive({ field: '', country: '' })
const outcomes = useAsync(
  () =>
    catalog.outcomesSearch({
      field: outcomeQuery.field.trim() || undefined,
      country: outcomeQuery.country.trim().toUpperCase() || undefined,
      page: 1,
    }),
  { immediate: true },
)
const countriesState = useAsync(() => catalog.countries(), { immediate: true })

// ------------------------------------------------- authed: scenario builder

const form = reactive({
  name: '',
  program_id: '',
  currency: 'INR',
  education_cost: '',
  expected_annual_income: '',
  annual_expenses: '',
  employment_delay_months: '0',
})

const fieldErrors = ref<Record<string, string>>({})
const serverError = ref('')
const pending = ref(false)
const result = ref<RoiScenario | null>(null)

const saved = useAsync(() => (auth.isAuthenticated ? finance.rois() : Promise.resolve(null)), {
  immediate: true,
})

function validate(): boolean {
  const errors: Record<string, string> = {}
  const cost = Number(form.education_cost)
  const income = Number(form.expected_annual_income)
  const expenses = form.annual_expenses === '' ? null : Number(form.annual_expenses)
  const delay = Number(form.employment_delay_months)
  if (form.education_cost === '' || Number.isNaN(cost) || cost < 0)
    errors.education_cost = 'Enter the education cost (0 if already paid).'
  if (form.expected_annual_income === '' || Number.isNaN(income) || income < 0)
    errors.expected_annual_income = 'Enter your expected annual income after graduation.'
  if (expenses !== null && (Number.isNaN(expenses) || expenses < 0))
    errors.annual_expenses = 'Annual expenses must be zero or more.'
  if (Number.isNaN(delay) || delay < 0 || delay > 120)
    errors.employment_delay_months = 'Delay must be 0-120 months.'
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function compute() {
  if (pending.value || !validate()) return
  pending.value = true
  serverError.value = ''
  try {
    const scenario = await finance.createRoi({
      name: form.name || 'My ROI scenario',
      program_id: form.program_id || null,
      currency: form.currency,
      education_cost: Number(form.education_cost),
      expected_annual_income: Number(form.expected_annual_income),
      annual_expenses: form.annual_expenses === '' ? null : Number(form.annual_expenses),
      employment_delay_months: Number(form.employment_delay_months),
    })
    result.value = scenario
    await saved.run()
  } catch (err) {
    if (isApiError(err)) {
      serverError.value = err.message
      const next: Record<string, string> = {}
      for (const detail of err.details) {
        if (detail.field) next[detail.field] = detail.message
      }
      fieldErrors.value = next
    } else {
      serverError.value = 'Could not compute the scenario. Check your connection and try again.'
    }
  } finally {
    pending.value = false
  }
}

function loadSaved(scenario: RoiScenario) {
  form.name = scenario.name
  form.program_id = scenario.program_id ?? ''
  form.currency = scenario.currency
  form.education_cost = scenario.inputs.education_cost !== null ? String(scenario.inputs.education_cost) : ''
  form.expected_annual_income =
    scenario.inputs.expected_annual_income !== null ? String(scenario.inputs.expected_annual_income) : ''
  form.annual_expenses = scenario.inputs.annual_expenses !== null ? String(scenario.inputs.annual_expenses) : ''
  form.employment_delay_months = String(scenario.inputs.employment_delay_months)
  result.value = scenario
}

async function removeSaved(id: string) {
  try {
    await finance.deleteRoi(id)
    ui.push('Scenario deleted.', 'success')
    if (result.value?.id === id) result.value = null
    await saved.run()
  } catch (err) {
    ui.pushError(err)
  }
}

const paybackText = computed(() => {
  const r = result.value?.results
  if (!r) return ''
  if (r.payback_months === null) {
    return r.payback_status === 'no_positive_surplus'
      ? 'No positive surplus - with these assumptions the degree never pays back within the model.'
      : 'Unknown - required inputs are missing, so no payback is computed (never a fabricated number).'
  }
  const years = Math.floor(r.payback_months / 12)
  const months = r.payback_months % 12
  return `${r.payback_months} months (${years ? `${years} yr ` : ''}${months} mo) after graduation`
})

const paybackTone = computed(() => {
  const r = result.value?.results
  if (!r) return 'neutral'
  if (r.payback_months === null) return r.payback_status === 'no_positive_surplus' ? 'danger' : 'warn'
  return r.payback_months <= 120 ? 'ok' : 'warn'
})
</script>

<template>
  <div class="stack">
    <div>
      <h1>Career evidence and ROI</h1>
      <p class="muted small" style="margin: 0">
        Outcome evidence carries cohort, year, sample size and population scope. The ROI model shows
        payback only when the inputs produce a positive surplus - otherwise it says so, and never
        invents a number.
      </p>
    </div>

    <div class="banner banner-info">
      <strong>Read this first:</strong> payback estimates are illustrations built on your own
      assumptions about cost and salary - they are not predictions, promises or financial advice.
      Salary outcomes vary widely by person, role, market and luck. Compare scenarios, then verify
      with real offer data.
    </div>

    <!-- scenario builder -->
    <section v-if="auth.isAuthenticated" class="card">
      <h2>Model a scenario</h2>
      <div v-if="serverError" class="error-summary" role="alert">{{ serverError }}</div>
      <div class="grid-2">
        <div class="field">
          <label for="roi-name">Scenario name <span class="muted">(optional)</span></label>
          <input id="roi-name" v-model="form.name" type="text" placeholder="MSc Data Science, 2 years" />
        </div>
        <div class="field">
          <label for="roi-currency">Currency</label>
          <select id="roi-currency" v-model="form.currency">
            <option v-for="code in ['INR', 'USD', 'EUR', 'GBP', 'AUD', 'CAD']" :key="code" :value="code">{{ code }}</option>
          </select>
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="roi-cost">Education cost <span class="muted">(required)</span></label>
          <input id="roi-cost" v-model="form.education_cost" type="number" min="0" step="any" :aria-invalid="Boolean(fieldErrors.education_cost)" />
          <span v-if="fieldErrors.education_cost" class="field-error">{{ fieldErrors.education_cost }}</span>
        </div>
        <div class="field">
          <label for="roi-income">Expected annual income <span class="muted">(required)</span></label>
          <input id="roi-income" v-model="form.expected_annual_income" type="number" min="0" step="any" :aria-invalid="Boolean(fieldErrors.expected_annual_income)" />
          <span v-if="fieldErrors.expected_annual_income" class="field-error">{{ fieldErrors.expected_annual_income }}</span>
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="roi-expenses">Annual expenses <span class="muted">(optional)</span></label>
          <input id="roi-expenses" v-model="form.annual_expenses" type="number" min="0" step="any" :aria-invalid="Boolean(fieldErrors.annual_expenses)" />
          <span v-if="fieldErrors.annual_expenses" class="field-error">{{ fieldErrors.annual_expenses }}</span>
        </div>
        <div class="field">
          <label for="roi-delay">Employment delay (months)</label>
          <input id="roi-delay" v-model="form.employment_delay_months" type="number" min="0" max="120" :aria-invalid="Boolean(fieldErrors.employment_delay_months)" />
          <span v-if="fieldErrors.employment_delay_months" class="field-error">{{ fieldErrors.employment_delay_months }}</span>
        </div>
      </div>
      <div class="field">
        <label for="roi-program">Program link <span class="muted">(optional)</span></label>
        <input id="roi-program" v-model="form.program_id" type="text" placeholder="Paste a program id from its detail page" />
        <span class="help">Linking a program ties the scenario to that catalogue entry's evidence.</span>
      </div>
      <button class="btn btn-primary" type="button" :disabled="pending" @click="compute">
        {{ pending ? 'Computing…' : 'Compute payback' }}
      </button>
    </section>

    <!-- result -->
    <section v-if="result" class="card">
      <div class="row-between">
        <h2 style="margin: 0">{{ result.name }}</h2>
        <div class="row">
          <StatusBadge :status="result.results.payback_status" :label="humanize(result.results.payback_status)" />
          <span class="badge badge-neutral">{{ result.scope }}</span>
        </div>
      </div>
      <p :class="['banner', paybackTone === 'danger' ? 'banner-danger' : paybackTone === 'warn' ? 'banner-warn' : 'banner-info']" style="margin: 10px 0">
        <strong>Payback:</strong> {{ paybackText }}
      </p>
      <dl class="kv">
        <dt>Monthly surplus</dt>
        <dd>
          <template v-if="result.results.monthly_surplus !== null && result.results.monthly_surplus !== undefined">
            {{ formatMoney(result.results.monthly_surplus, result.currency) }}
          </template>
          <span v-else class="muted">Not available</span>
        </dd>
        <dt>Input provenance</dt>
        <dd>{{ humanize(result.input_provenance) }} (your assumptions, not sourced outcome data)</dd>
        <dt>Calculation version</dt>
        <dd class="mono">{{ result.calculation_version ?? 'unknown' }}</dd>
      </dl>
      <div v-if="result.results.warnings?.length" class="banner banner-warn" style="margin-top: 10px">
        <ul style="margin: 0; padding-left: 18px">
          <li v-for="warning in result.results.warnings" :key="warning" class="small mono">{{ warning }}</li>
        </ul>
      </div>
      <p class="small muted" style="margin-top: 10px">{{ result.disclaimer }}</p>
    </section>

    <p v-else-if="!auth.isAuthenticated" class="small muted">
      <RouterLink :to="{ path: '/login', query: { redirect: '/roi' } }">Log in</RouterLink> to model
      payback scenarios; the career evidence search below is open to everyone.
    </p>

    <!-- saved scenarios -->
    <section v-if="auth.isAuthenticated" class="stack">
      <h2>Saved scenarios</h2>
      <AsyncState
        :loading="saved.loading.value"
        :error="saved.error.value"
        :empty="!saved.data.value?.items.length"
        empty-title="No saved scenarios yet"
        empty-hint="Compute one above - it will be stored with your assumptions for later comparison."
        @retry="saved.run"
      >
        <div v-if="saved.data.value?.items.length" class="stack-sm">
          <div v-for="scenario in saved.data.value.items" :key="scenario.id" class="card row-between">
            <div>
              <strong>{{ scenario.name }}</strong>
              <div class="small muted">
                cost {{ scenario.inputs.education_cost ?? 'unknown' }} · income
                {{ scenario.inputs.expected_annual_income ?? 'unknown' }} {{ scenario.currency }}
                <template v-if="scenario.results.payback_months !== null">
                  · payback {{ scenario.results.payback_months }} months</template
                ><template v-else> · payback {{ humanize(scenario.results.payback_status) }}</template>
                <template v-if="scenario.created_at"> · {{ formatDateTime(scenario.created_at) }}</template>
              </div>
            </div>
            <div class="row">
              <button class="btn btn-sm" type="button" @click="loadSaved(scenario)">Open</button>
              <button class="btn btn-sm btn-quiet" type="button" @click="removeSaved(scenario.id)">Delete</button>
            </div>
          </div>
        </div>
      </AsyncState>
    </section>

    <!-- public evidence search -->
    <section class="stack">
      <h2>Career outcome evidence</h2>
      <p class="muted small" style="margin-top: 0">
        Published metrics with methodology and scope attached. Numbers apply to the population they
        measured - they say nothing guaranteed about an individual's outcome.
      </p>
      <section class="card">
        <div class="grid">
          <div class="field" style="margin-bottom: 0">
            <label for="outcome-field">Field</label>
            <input id="outcome-field" v-model="outcomeQuery.field" type="text" placeholder="e.g. data_science" />
          </div>
          <div class="field" style="margin-bottom: 0">
            <label for="outcome-country">Country</label>
            <select id="outcome-country" v-model="outcomeQuery.country">
              <option value="">Any country</option>
              <option v-for="country in countriesState.data.value?.items ?? []" :key="country.code" :value="country.code">
                {{ country.name }}
              </option>
            </select>
          </div>
        </div>
      </section>
      <AsyncState
        :loading="outcomes.loading.value"
        :error="outcomes.error.value"
        :empty="!outcomes.data.value?.items.length"
        empty-title="No outcome evidence matches"
        empty-hint="Try a broader field or clear the country filter."
        @retry="outcomes.run"
      >
        <div v-if="outcomes.data.value" class="stack">
          <p class="banner banner-info" style="margin: 0">{{ outcomes.data.value.scope_note }}</p>
          <div class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Cohort</th>
                  <th>Sample</th>
                  <th>Scope</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="metric in outcomes.data.value.items" :key="metric.id">
                  <td>{{ humanize(metric.metric_key) }}</td>
                  <td>
                    <strong>{{ metric.metric_value }}{{ metric.metric_unit === '%' ? '%' : ` ${metric.metric_unit}` }}</strong>
                    <span v-if="metric.currency" class="small muted"> {{ metric.currency }}</span>
                  </td>
                  <td class="small">{{ metric.cohort_label ?? '—' }}{{ metric.cohort_year ? ` (${metric.cohort_year})` : '' }}</td>
                  <td class="small">{{ metric.sample_size ?? 'unknown' }}</td>
                  <td class="small">{{ metric.population_scope }}<span v-if="metric.methodology_note"> - {{ metric.methodology_note }}</span></td>
                  <td><StatusBadge :status="metric.status" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </AsyncState>
    </section>
  </div>
</template>
