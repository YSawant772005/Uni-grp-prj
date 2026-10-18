<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { finance } from '../../services/api/finance'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import { formatMoney, formatDateTime } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { LoanScenario } from '../../types/api'

const ui = useUiStore()

// ---------------------------------------------------------------------- state

const form = reactive({
  name: '',
  principal_amount: '',
  currency: 'INR',
  annual_interest_rate: '',
  tenure_months: '24',
  moratorium_months: '0',
  interest_during_moratorium: 'none',
})

const MORATORIUM_MODES = [
  ['none', 'No interest charged during moratorium'],
  ['simple_interest', 'Simple interest charged on the principal during moratorium'],
  ['capitalize', 'Interest capitalized (added to principal) during moratorium'],
] as const

const fieldErrors = ref<Record<string, string>>({})
const serverError = ref('')
const pending = ref(false)
const result = ref<LoanScenario | null>(null)

const saved = useAsync(() => finance.loans(), { immediate: true })

function validate(): boolean {
  const errors: Record<string, string> = {}
  const principal = Number(form.principal_amount)
  const rate = Number(form.annual_interest_rate)
  const tenure = Number(form.tenure_months)
  const moratorium = Number(form.moratorium_months)
  if (!form.principal_amount || Number.isNaN(principal) || principal <= 0)
    errors.principal_amount = 'Enter a loan amount above zero.'
  if (form.annual_interest_rate === '' || Number.isNaN(rate) || rate < 0 || rate > 100)
    errors.annual_interest_rate = 'Interest rate must be between 0 and 100 percent.'
  if (!form.tenure_months || Number.isNaN(tenure) || tenure < 1 || tenure > 480)
    errors.tenure_months = 'Tenure must be 1-480 months.'
  if (form.moratorium_months === '' || Number.isNaN(moratorium) || moratorium < 0 || moratorium >= tenure)
    errors.moratorium_months = 'Moratorium must be shorter than the tenure.'
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function calculate(keepResult = true) {
  if (pending.value || !validate()) return
  pending.value = true
  serverError.value = ''
  try {
    const scenario = await finance.createLoan({
      name: form.name || 'Admission loan scenario',
      principal_amount: Number(form.principal_amount),
      currency: form.currency,
      annual_interest_rate: Number(form.annual_interest_rate),
      tenure_months: Number(form.tenure_months),
      moratorium_months: Number(form.moratorium_months),
      interest_during_moratorium: form.interest_during_moratorium,
      ...(keepResult ? {} : { save: false }),
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

function loadSaved(scenario: LoanScenario) {
  form.name = scenario.name
  form.principal_amount = String(scenario.inputs.principal_amount)
  form.currency = scenario.inputs.currency
  form.annual_interest_rate = String(scenario.inputs.annual_interest_rate)
  form.tenure_months = String(scenario.inputs.tenure_months)
  form.moratorium_months = String(scenario.inputs.moratorium_months)
  form.interest_during_moratorium = scenario.inputs.interest_during_moratorium
  result.value = scenario
  fieldErrors.value = {}
  serverError.value = ''
}

async function removeSaved(id: string) {
  try {
    await finance.deleteLoan(id)
    ui.push('Scenario deleted.', 'success')
    if (result.value?.id === id) result.value = null
    await saved.run()
  } catch (err) {
    ui.pushError(err)
  }
}

const scheduleOpen = ref(false)
const schedule = computed(() => result.value?.results.schedule ?? [])
const schedulePreview = computed(() => (scheduleOpen.value ? schedule.value : schedule.value.slice(0, 12)))
</script>

<template>
  <div class="stack">
    <div>
      <h1>Loan scenarios</h1>
      <p class="muted small" style="margin: 0">
        Illustrative amortization for education loans: EMI, moratorium handling and full monthly
        schedule. This is not financial advice and approval is never guaranteed - the numbers assume
        a fixed rate for the full tenure.
      </p>
    </div>

    <div class="grid-2">
      <!-- form -->
      <section class="card">
        <h2>Loan inputs</h2>
        <div v-if="serverError" class="error-summary" role="alert">{{ serverError }}</div>
        <div class="field">
          <label for="loan-name">Scenario name <span class="muted">(optional)</span></label>
          <input id="loan-name" v-model="form.name" type="text" placeholder="SBI education loan" />
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="loan-principal">Principal <span class="muted">(required)</span></label>
            <input id="loan-principal" v-model="form.principal_amount" type="number" min="1" step="any" :aria-invalid="Boolean(fieldErrors.principal_amount)" />
            <span v-if="fieldErrors.principal_amount" class="field-error">{{ fieldErrors.principal_amount }}</span>
          </div>
          <div class="field">
            <label for="loan-currency">Currency</label>
            <select id="loan-currency" v-model="form.currency">
              <option v-for="code in ['INR', 'USD', 'EUR', 'GBP', 'AUD', 'CAD']" :key="code" :value="code">{{ code }}</option>
            </select>
          </div>
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="loan-rate">Annual interest rate (%) <span class="muted">(required)</span></label>
            <input id="loan-rate" v-model="form.annual_interest_rate" type="number" min="0" max="100" step="0.05" :aria-invalid="Boolean(fieldErrors.annual_interest_rate)" />
            <span v-if="fieldErrors.annual_interest_rate" class="field-error">{{ fieldErrors.annual_interest_rate }}</span>
          </div>
          <div class="field">
            <label for="loan-tenure">Tenure (months) <span class="muted">(required)</span></label>
            <input id="loan-tenure" v-model="form.tenure_months" type="number" min="1" max="480" :aria-invalid="Boolean(fieldErrors.tenure_months)" />
            <span v-if="fieldErrors.tenure_months" class="field-error">{{ fieldErrors.tenure_months }}</span>
          </div>
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="loan-moratorium">Moratorium (months)</label>
            <input id="loan-moratorium" v-model="form.moratorium_months" type="number" min="0" :aria-invalid="Boolean(fieldErrors.moratorium_months)" />
            <span v-if="fieldErrors.moratorium_months" class="field-error">{{ fieldErrors.moratorium_months }}</span>
          </div>
          <div class="field">
            <label for="loan-moratorium-mode">Interest during moratorium</label>
            <select id="loan-moratorium-mode" v-model="form.interest_during_moratorium">
              <option v-for="[value, label] in MORATORIUM_MODES" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
        </div>
        <button class="btn btn-primary" type="button" :disabled="pending" @click="calculate()">
          {{ pending ? 'Computing…' : 'Compute scenario' }}
        </button>
        <p class="small muted" style="margin: 8px 0 0">
          Scenarios are saved to your account so you can revisit them from any device.
        </p>
      </section>

      <!-- results -->
      <section v-if="result" class="card">
        <div class="row-between">
          <h2 style="margin: 0">{{ result.name }}</h2>
          <StatusBadge status="estimated" label="illustrative" />
        </div>
        <dl class="kv" style="margin-top: 10px">
          <dt>EMI</dt>
          <dd><strong>{{ formatMoney(result.results.emi, result.inputs.currency) }}</strong> / month</dd>
          <dt>Repayment months</dt>
          <dd>{{ result.results.repayment_months }}</dd>
          <dt>Principal after moratorium</dt>
          <dd>{{ formatMoney(result.results.principal_after_moratorium, result.inputs.currency) }}</dd>
          <dt>Moratorium interest</dt>
          <dd>{{ formatMoney(result.results.moratorium_interest, result.inputs.currency) }}</dd>
          <dt>Total interest</dt>
          <dd>{{ formatMoney(result.results.total_interest, result.inputs.currency) }}</dd>
          <dt>Total payable</dt>
          <dd><strong>{{ formatMoney(result.results.total_payable, result.inputs.currency) }}</strong></dd>
        </dl>
        <div class="banner banner-info" style="margin-top: 10px">
          <strong>{{ result.interest_method }}</strong>
          <ul style="margin: 4px 0 0; padding-left: 18px">
            <li v-for="assumption in result.assumptions" :key="assumption" class="small">{{ assumption }}</li>
          </ul>
          <p class="small" style="margin: 6px 0 0">{{ result.disclaimer }}</p>
        </div>

        <div class="row-between" style="margin-top: 12px">
          <h3 style="margin: 0">Monthly schedule</h3>
          <button class="btn btn-sm" type="button" @click="scheduleOpen = !scheduleOpen">
            {{ scheduleOpen ? 'Show first 12 only' : `Show all ${schedule.length} months` }}
          </button>
        </div>
        <div class="table-wrap" style="margin-top: 8px">
          <table class="data">
            <thead>
              <tr>
                <th>Month</th>
                <th>EMI</th>
                <th>Interest</th>
                <th>Principal</th>
                <th>Closing balance</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in schedulePreview" :key="row.month">
                <td>{{ row.month }}</td>
                <td>{{ formatMoney(row.emi, result.inputs.currency) }}</td>
                <td>{{ formatMoney(row.interest, result.inputs.currency) }}</td>
                <td>{{ formatMoney(row.principal, result.inputs.currency) }}</td>
                <td>{{ formatMoney(row.closing_balance, result.inputs.currency) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!scheduleOpen && schedule.length > 12" class="small muted" style="margin: 6px 0 0">
          Showing 12 of {{ schedule.length }} months - interest and principal reconcile to
          {{ formatMoney(result.results.total_payable, result.inputs.currency) }} total.
        </p>
      </section>
    </div>

    <!-- saved scenarios -->
    <section class="stack">
      <h2>Saved scenarios</h2>
      <AsyncState
        :loading="saved.loading.value"
        :error="saved.error.value"
        :empty="!saved.data.value?.items.length"
        empty-title="No saved scenarios yet"
        empty-hint="Compute a scenario above and it will be stored here."
        @retry="saved.run"
      >
        <div v-if="saved.data.value?.items.length" class="stack-sm">
          <div v-for="scenario in saved.data.value.items" :key="scenario.id" class="card row-between">
            <div>
              <strong>{{ scenario.name }}</strong>
              <div class="small muted">
                {{ formatMoney(scenario.inputs.principal_amount, scenario.inputs.currency) }} at
                {{ scenario.inputs.annual_interest_rate }}% · {{ scenario.inputs.tenure_months }} months
                <template v-if="scenario.inputs.moratorium_months">
                  · {{ scenario.inputs.moratorium_months }}-month moratorium
                </template>
                <template v-if="scenario.created_at"> · created {{ formatDateTime(scenario.created_at) }}</template>
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

    <p class="small muted">
      Loan approval, final rates and fees are decided by the lender - treat every number here as an
      estimate to compare options, not a quote. Verify the final terms on the official lender portal.
    </p>
  </div>
</template>
