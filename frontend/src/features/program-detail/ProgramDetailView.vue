<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { formatDate, formatDuration, formatValue, humanize, truncate } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import CompareToggle from '../../components/CompareToggle.vue'
import MoneyCell from '../../components/MoneyCell.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import SaveToggle from '../../components/SaveToggle.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const programId = computed(() => String(route.params.programId))

const TABS = ['overview', 'requirements', 'fees', 'intakes', 'evidence', 'outcomes'] as const
type Tab = (typeof TABS)[number]

const activeTab = ref<Tab>(
  (TABS as readonly string[]).includes(String(route.query.tab)) ? (String(route.query.tab) as Tab) : 'overview',
)

watch(activeTab, (tab) => {
  void router.replace({ query: { ...route.query, tab: tab === 'overview' ? undefined : tab } })
})

const programState = useAsync(() => catalog.program(programId.value), { immediate: true })
const evidencePage = ref(1)
const evidenceState = useAsync(
  () => catalog.evidence(programId.value, evidencePage.value),
  { immediate: true },
)
const outcomesState = useAsync(() => catalog.outcomes(programId.value), { immediate: true })

const program = computed(() => programState.data.value)

// ------------------------------------------------- profile-based eligibility check

const checking = ref(false)
const evaluation = ref<Awaited<ReturnType<typeof recommendations.evaluate>> | null>(null)

async function checkEligibility() {
  checking.value = true
  try {
    const res = await recommendations.evaluate([programId.value])
    evaluation.value = res
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    ui.pushError(err)
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <AsyncState
    :loading="programState.loading.value"
    :error="programState.error.value"
    :empty="!program"
    empty-title="Program not found"
    empty-hint="It may have been retired, or the link is wrong."
    @retry="programState.run"
  >
    <template #empty-action>
      <RouterLink to="/discover" class="btn">Back to discovery</RouterLink>
    </template>

    <div v-if="program" class="stack">
      <!-- header -->
      <div class="row-between">
        <div>
          <h1 style="margin-bottom: 4px">{{ program.name }}</h1>
          <p class="muted" style="margin: 0">
            {{ program.university.name }} · {{ program.university.city }}, {{ program.country_code }}
            · {{ program.degree_level }} · {{ humanize(program.study_mode) }} · {{ program.language }}
          </p>
          <p class="small muted" style="margin: 4px 0 0">
            {{ formatDuration(program.duration_months) }}
            <template v-if="program.nearest_intake">
              · next intake {{ program.nearest_intake.intake_term }} {{ program.nearest_intake.intake_year }}
              <template v-if="program.nearest_intake.application_deadline">
                · deadline {{ formatDate(program.nearest_intake.application_deadline) }}
              </template>
            </template>
          </p>
        </div>
        <div class="row">
          <SaveToggle :program-id="program.id" />
          <CompareToggle :program-id="program.id" :label="program.name" />
          <RouterLink class="btn btn-sm" :to="`/finance?program=${program.id}`">Estimate costs</RouterLink>
        </div>
      </div>

      <!-- data quality banner -->
      <div v-if="program.data_quality.warnings.length" class="banner banner-warn" role="status">
        <strong>Data quality - {{ program.data_quality.status }}</strong>
        <ul style="margin: 4px 0 0; padding-left: 18px">
          <li v-for="warning in program.data_quality.warnings" :key="warning" class="small">{{ warning }}</li>
        </ul>
      </div>

      <!-- tabs -->
      <div class="tabs" role="tablist" aria-label="Program sections">
        <button
          v-for="tab in TABS"
          :key="tab"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab"
          @click="activeTab = tab"
        >
          {{ humanize(tab) }}
        </button>
      </div>

      <!-- overview -->
      <section v-if="activeTab === 'overview'" class="stack">
        <div class="card">
          <h2>About the program</h2>
          <p>{{ program.description ?? 'No description published yet.' }}</p>
          <dl class="kv">
            <dt>Field</dt>
            <dd>{{ program.field.display_name }}</dd>
            <dt>Recognition</dt>
            <dd>
              <StatusBadge :status="program.university.recognition_status" />
            </dd>
            <dt>Official page</dt>
            <dd>
              <a v-if="program.official_program_url" :href="program.official_program_url" target="_blank" rel="noopener noreferrer">
                {{ program.official_program_url }}
              </a>
              <span v-else class="muted">Not published</span>
            </dd>
            <dt>Tuition summary</dt>
            <dd><MoneyCell :cell="program.tuition_summary" /></dd>
          </dl>
        </div>

        <!-- eligibility check (explicit action, never implied) -->
        <div class="card">
          <h2>Check against my profile</h2>
          <p class="muted small" style="margin-top: 0">
            Runs a requirement-by-requirement check using your saved profile. This is an
            interpretation of published requirements - never a claim of admission.
          </p>
          <button class="btn btn-primary" type="button" :disabled="checking" @click="checkEligibility">
            {{ checking ? 'Evaluating…' : auth.isAuthenticated ? 'Check my eligibility' : 'Log in to check eligibility' }}
          </button>
          <div v-if="evaluation?.items?.length" class="stack-sm" style="margin-top: 12px">
            <div class="row">
              <StatusBadge :status="evaluation.items[0].status" />
              <span class="small muted">{{ evaluation.items[0].requirements.length }} requirements evaluated</span>
            </div>
            <div class="table-wrap">
              <table class="data">
                <thead>
                  <tr>
                    <th>Requirement</th>
                    <th>Expected</th>
                    <th>Your value</th>
                    <th>Status</th>
                    <th>Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="req in evaluation.items[0].requirements" :key="req.requirement_id">
                    <td>
                      {{ humanize(req.requirement_key) }}
                      <span v-if="req.is_mandatory" class="badge badge-neutral">mandatory</span>
                    </td>
                    <td class="mono">{{ formatValue(req.expected_value) }}</td>
                    <td class="mono">{{ formatValue(req.evaluated_value) }}</td>
                    <td><StatusBadge :status="req.status" /></td>
                    <td class="small">{{ req.explanation ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <!-- requirements -->
      <section v-else-if="activeTab === 'requirements'" class="card">
        <h2>Admission requirements</h2>
        <div v-if="program.requirements.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Requirement</th>
                <th>Expected</th>
                <th>Weight</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="req in program.requirements" :key="req.id">
                <td>
                  {{ humanize(req.requirement_key) }}
                  <span class="badge badge-neutral">{{ humanize(req.requirement_type) }}</span>
                  <span v-if="req.is_mandatory" class="badge badge-warn">mandatory</span>
                  <span v-if="req.group_key" class="small muted">group: {{ req.group_key }} ({{ req.group_operator }})</span>
                </td>
                <td class="mono">{{ req.expected_value ? formatValue(req.expected_value) : 'See note' }}</td>
                <td>{{ humanize(req.operator) }}</td>
                <td>
                  <StatusBadge :status="req.evidence.status" />
                  <a
                    v-if="req.evidence.source?.url"
                    class="small"
                    :href="req.evidence.source.url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {{ req.evidence.source.title ?? 'source' }}
                  </a>
                  <span v-if="req.applicability_notes" class="small muted">{{ req.applicability_notes }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No admission requirements published for this program yet.</p>
      </section>

      <!-- fees -->
      <section v-else-if="activeTab === 'fees'" class="card">
        <h2>Tuition and fees</h2>
        <div v-if="program.fees.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Fee</th>
                <th>Amount</th>
                <th>Period</th>
                <th>Category</th>
                <th>Status & source</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="fee in program.fees" :key="fee.id">
                <td>
                  {{ humanize(fee.fee_type) }}
                  <span v-if="fee.is_mandatory" class="badge badge-warn">mandatory</span>
                </td>
                <td>
                  <strong v-if="fee.amount !== null">{{ fee.currency }} {{ fee.amount }}</strong>
                  <span v-else class="muted">Not available</span>
                </td>
                <td class="small">{{ fee.period ? humanize(fee.period) : '—' }}{{ fee.academic_year ? ` · ${fee.academic_year}` : '' }}</td>
                <td class="small">{{ fee.student_category ? humanize(fee.student_category) : 'all students' }}</td>
                <td>
                  <StatusBadge :status="fee.status" />
                  <a
                    v-if="fee.provenance?.source?.url"
                    class="small"
                    :href="fee.provenance.source.url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {{ fee.provenance.source.title ?? 'source' }}
                  </a>
                  <span v-if="fee.provenance" class="small muted">v{{ fee.provenance.version_number }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No fees published yet - unknown values are never shown as zero.</p>
        <p class="small muted">
          Model the full degree cost with
          <RouterLink :to="`/finance?program=${program.id}`">cost estimates</RouterLink> (low/base/high
          scenarios).
        </p>
      </section>

      <!-- intakes -->
      <section v-else-if="activeTab === 'intakes'" class="card">
        <h2>Intakes and deadlines</h2>
        <div v-if="program.intakes.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Intake</th>
                <th>Opens</th>
                <th>Deadline</th>
                <th>Start</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="intake in program.intakes" :key="intake.id">
                <td>{{ humanize(intake.intake_term) }} {{ intake.intake_year }}</td>
                <td class="small">{{ intake.application_open_date ? formatDate(intake.application_open_date) : '—' }}</td>
                <td class="small">{{ intake.application_deadline ? formatDate(intake.application_deadline) : 'Not published' }}</td>
                <td class="small">{{ intake.start_date ? formatDate(intake.start_date) : '—' }}</td>
                <td>
                  <StatusBadge :status="intake.is_open_for_applications ? 'open' : 'closed'" />
                  <StatusBadge v-if="intake.status !== 'open'" :status="intake.status" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No intakes published yet.</p>
      </section>

      <!-- evidence -->
      <section v-else-if="activeTab === 'evidence'" class="stack">
        <div class="card">
          <h2>Sources and evidence history</h2>
          <p class="muted small" style="margin-top: 0">
            Every material fact with its version history, source excerpt and review state. Nothing
            here is published without passing validation and (for candidates) human review.
          </p>
        </div>
        <AsyncState
          :loading="evidenceState.loading.value"
          :error="evidenceState.error.value"
          :empty="!evidenceState.data.value?.items.length"
          empty-title="No evidence recorded yet"
          empty-hint="Facts appear here once catalogue entries are linked to sources."
          @retry="evidenceState.run"
        >
          <div v-if="evidenceState.data.value" class="stack">
            <article v-for="item in evidenceState.data.value.items" :key="item.fact_id" class="card">
              <div class="row-between">
                <h3 style="margin: 0">{{ humanize(item.fact_key) }}</h3>
                <StatusBadge :status="item.current_status" />
              </div>
              <p v-if="item.applicability_key" class="small muted" style="margin: 2px 0">
                applies to: {{ item.applicability_key }}
              </p>
              <div v-for="version in item.versions" :key="version.version_number" class="stack-sm" style="margin-top: 8px">
                <div class="row">
                  <span class="badge badge-neutral">v{{ version.version_number }}</span>
                  <StatusBadge :status="version.status" />
                  <span v-if="version.applicable_intake_year" class="small muted">
                    intake {{ version.applicable_intake_term ?? '' }} {{ version.applicable_intake_year }}
                  </span>
                  <span class="small muted">{{ humanize(version.extraction_method) }}</span>
                </div>
                <pre class="json-block">{{ formatValue(version.value) }}</pre>
              </div>
              <ul v-if="item.sources.length" class="timeline" style="margin-top: 10px">
                <li v-for="(source, index) in item.sources" :key="index">
                  <div class="row">
                    <StatusBadge :status="source.supports_or_conflicts" />
                    <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">
                      {{ source.title ?? source.url }}
                    </a>
                    <span v-else class="small muted">{{ source.title ?? 'source removed' }}</span>
                  </div>
                  <p v-if="source.excerpt" class="small" style="margin: 2px 0">“{{ truncate(source.excerpt, 240) }}”</p>
                  <p v-if="source.retrieved_at" class="small muted" style="margin: 0">
                    retrieved {{ formatDate(source.retrieved_at) }}
                  </p>
                </li>
              </ul>
            </article>
            <PaginationBar
              :page="evidenceState.data.value.page"
              :page-size="evidenceState.data.value.page_size"
              :total-items="evidenceState.data.value.total_items"
              :total-pages="evidenceState.data.value.total_pages"
              @update:page="(page) => { evidencePage = page; evidenceState.run() }"
            />
          </div>
        </AsyncState>
      </section>

      <!-- outcomes -->
      <section v-else-if="activeTab === 'outcomes'" class="stack">
        <div class="card">
          <h2>Career and outcome evidence</h2>
          <p class="muted small" style="margin-top: 0">
            Outcome metrics with cohort, year, sample size and population scope. Numbers apply to the
            stated population - they never promise what an individual will earn.
          </p>
        </div>
        <AsyncState
          :loading="outcomesState.loading.value"
          :error="outcomesState.error.value"
          :empty="!outcomesState.data.value?.items.length"
          empty-title="No outcome evidence for this program"
          empty-hint="Program-level evidence is sparse; try the country-level destination guide instead."
          @retry="outcomesState.run"
        >
          <template #empty-action>
            <RouterLink v-if="program" class="btn" :to="`/destinations/${program.country_code}`">
              Open {{ program.country_code }} destination guide
            </RouterLink>
          </template>
          <div v-if="outcomesState.data.value?.items.length" class="table-wrap">
            <table class="data">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Cohort</th>
                  <th>Sample</th>
                  <th>Scope</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="metric in outcomesState.data.value.items" :key="metric.metric_key">
                  <td>{{ humanize(metric.metric_key) }}</td>
                  <td>
                    <strong>{{ metric.metric_value }}{{ metric.metric_unit === '%' ? '%' : ` ${metric.metric_unit}` }}</strong>
                    <span v-if="metric.currency" class="small muted"> {{ metric.currency }}</span>
                  </td>
                  <td class="small">{{ metric.cohort_label ?? '—' }}{{ metric.cohort_year ? ` (${metric.cohort_year})` : '' }}</td>
                  <td class="small">{{ metric.sample_size ?? 'unknown' }}</td>
                  <td class="small">{{ metric.population_scope }}<span v-if="metric.methodology_note"> - {{ metric.methodology_note }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </AsyncState>
      </section>
    </div>
  </AsyncState>
</template>
