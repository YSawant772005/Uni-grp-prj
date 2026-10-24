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

const TABS = ['overview', 'requirements', 'fees', 'outcomes', 'living', 'reviews', 'intakes', 'evidence'] as const
const TAB_LABELS: Record<(typeof TABS)[number], string> = {
  overview: 'Overview',
  requirements: 'Admission Requirements',
  fees: 'Cost & Scholarships',
  outcomes: 'Jobs & ROI',
  living: 'Living in City',
  reviews: 'Reviews',
  intakes: 'Intakes',
  evidence: 'Sources & Evidence',
}
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
const isFictionalDemo = computed(() => Boolean(program.value && (
  /fictional demo|^demo(?:\s|_)/i.test(program.value.name) ||
  /fictional demo|^demo(?:\s|_)/i.test(program.value.university.name)
)))
const countryLabel = computed(() => {
  const code = program.value?.country_code
  if (!code) return 'Unknown destination'
  try { return new Intl.DisplayNames(['en'], { type: 'region' }).of(code) ?? code } catch { return code }
})
const intakeLabel = computed(() => program.value?.nearest_intake
  ? `${humanize(program.value.nearest_intake.intake_term)} ${program.value.nearest_intake.intake_year}`
  : 'Not available')
const warningLabel = (key: string): string => ({
  affordability_unavailable: 'Budget fit cannot yet be calculated',
  living_unknown: 'Living cost data is unavailable',
  no_cost_components: 'Detailed study costs are not available',
  outcomes_unavailable: 'Verified graduate outcomes are not available',
  tuition_unknown: 'Tuition information is unavailable',
  no_exact_degree_and_specialization_match_in_current_catalogue: 'No exact program match is available in this catalogue',
}[key] ?? humanize(key))


// ------------------------------------------------- profile-based eligibility check

const checking = ref(false)
const evaluation = ref<Awaited<ReturnType<typeof recommendations.evaluate>> | null>(null)


watch(programId, () => {
  evaluation.value = null
  evidencePage.value = 1
  void programState.run()
  void evidenceState.run()
  void outcomesState.run()
})
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

    <div v-if="program" class="university-detail">
      <!-- The existing shared app header is supplied by AppLayout. No second header here. -->
      <nav class="ud-breadcrumb" aria-label="Breadcrumb">
        <RouterLink to="/shortlist">Shortlist</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ program.university.name }}</span>
      </nav>

      <section class="ud-hero" aria-labelledby="university-title">
        <div class="ud-emblem" aria-hidden="true">{{ program.university.name.trim().charAt(0).toUpperCase() }}</div>
        <div class="ud-identity">
          <span class="ud-eyebrow">UNIVERSITY &amp; PROGRAM DETAILS</span>
          <h1 id="university-title">{{ program.university.name }}</h1>
          <p class="ud-location">{{ countryLabel }} <span aria-hidden="true">·</span> {{ program.university.city || 'City unavailable' }}
            <span aria-hidden="true">·</span> <StatusBadge :status="program.university.recognition_status" />
          </p>
          <div class="ud-program-name"><span>Selected program</span><strong>{{ program.name }}</strong></div>
          <span v-if="isFictionalDemo" class="ud-demo">FICTIONAL DEMO — testing data, not a real institution</span>
        </div>
        <div class="ud-hero-actions">
          <SaveToggle :program-id="program.id" />
          <CompareToggle :program-id="program.id" :label="program.name" />
          <RouterLink class="btn btn-sm" :to="`/finance?program=${program.id}`">Explore costs ↗</RouterLink>
        </div>
      </section>

      <div v-if="program.data_quality.warnings.length" class="ud-disclosure">
        <details>
          <summary>{{ program.data_quality.warnings.length }} data availability {{ program.data_quality.warnings.length === 1 ? 'note' : 'notes' }} · {{ humanize(program.data_quality.status) }}</summary>
          <ul><li v-for="warning in program.data_quality.warnings" :key="warning">{{ warningLabel(warning) }}</li></ul>
        </details>
      </div>

      <div class="ud-tabs-outer">
        <div class="ud-tabs" role="tablist" aria-label="University and program information">
          <button v-for="tab in TABS" :key="tab" type="button" role="tab"
            :aria-selected="activeTab === tab"
            @click="activeTab = tab">{{ TAB_LABELS[tab] }}</button>
        </div>
      </div>

      <!-- Overview: university-first layout, using only data actually in the API -->
      <section v-if="activeTab === 'overview'" class="ud-section">
        <div class="ud-overview-grid">
          <article class="ud-card ud-about">
            <h2>Overview</h2>
            <div class="ud-overview-body">
              <div class="ud-campus-illustration" role="img" aria-label="Decorative illustration of a university campus, not an actual campus photograph">
                <svg viewBox="0 0 440 260" aria-hidden="true" focusable="false">
                  <defs><linearGradient id="udsky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#cbece0"/><stop offset="1" stop-color="#f7fcf9"/></linearGradient></defs>
                  <rect width="440" height="260" fill="url(#udsky)"/><circle cx="355" cy="51" r="28" fill="#fff" opacity=".75"/>
                  <path d="M0 208Q105 179 219 207T440 200V260H0Z" fill="#cae6d2"/>
                  <path d="M93 222V112L219 48L344 112V222Z" fill="#fdfefe" stroke="#5f9e87" stroke-width="4"/>
                  <path d="M74 114L219 38L365 114" fill="none" stroke="#087f5c" stroke-linecap="round" stroke-width="14"/>
                  <rect x="198" y="70" width="42" height="25" rx="3" fill="#d1ece1"/><path d="M111 128H327" stroke="#86baa3" stroke-width="4"/>
                  <g fill="#d4ede4" stroke="#8cbba6" stroke-width="3"><rect x="119" y="147" width="33" height="39" rx="5"/><rect x="165" y="147" width="33" height="39" rx="5"/><rect x="242" y="147" width="33" height="39" rx="5"/><rect x="288" y="147" width="33" height="39" rx="5"/></g>
                  <path d="M204 222V173A15 15 0 0 1 234 173V222" fill="#0a8964"/><path d="M0 222H440" stroke="#77ad91" stroke-width="5"/>
                  <g fill="#399a75"><circle cx="42" cy="194" r="27"/><circle cx="405" cy="196" r="25"/><circle cx="24" cy="211" r="21"/></g>
                </svg>
                <span>Illustrative campus graphic</span>
              </div>
              <div class="ud-overview-copy">
                <p>{{ program.description || `Explore ${program.name} at ${program.university.name}. Program information is displayed only where it is available from the catalogue.` }}</p>
                <dl class="ud-highlights">
                  <div><dt>Program</dt><dd>{{ program.name }}</dd></div>
                  <div><dt>Field</dt><dd>{{ program.field.display_name }}</dd></div>
                  <div><dt>Teaching language</dt><dd>{{ program.language || 'Not available' }}</dd></div>
                  <div><dt>Study mode</dt><dd>{{ humanize(program.study_mode) }}</dd></div>
                </dl>
                <a v-if="program.official_program_url" class="ud-source-link" :href="program.official_program_url" target="_blank" rel="noopener noreferrer">Official program page ↗</a>
                <p v-else class="ud-mini-note">Official program page not available.</p>
              </div>
            </div>
          </article>
        </div>

        <div class="ud-stats">
          <article><span>Global ranking</span><strong>Not available</strong><small>Not provided by the catalogue</small></article>
          <article><span>Acceptance rate</span><strong>Not available</strong><small>No verified figure published</small></article>
          <article><span>Program duration</span><strong>{{ formatDuration(program.duration_months) }}</strong><small>{{ humanize(program.degree_level) }}</small></article>
          <article><span>Next intake</span><strong>{{ intakeLabel }}</strong><small>{{ program.nearest_intake?.application_deadline ? `Deadline: ${formatDate(program.nearest_intake.application_deadline)}` : 'Deadline not available' }}</small></article>
        </div>
        <div class="ud-summary-row">
          <article class="ud-card"><h3>Tuition overview</h3><MoneyCell :cell="program.tuition_summary" /><RouterLink :to="`/finance?program=${program.id}`">Plan total study costs ↗</RouterLink></article>
          <article class="ud-card"><h3>Recognition status</h3><StatusBadge :status="program.university.recognition_status"/><p class="ud-mini-note">Check awarding body and local recognition before applying.</p></article>
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
      <section v-else-if="activeTab === 'requirements'" class="ud-card ud-tab-card">
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
      <section v-else-if="activeTab === 'fees'" class="ud-card ud-tab-card">
        <h2>Cost &amp; Scholarships</h2>
        <p class="ud-muted">Tuition and fee figures are listed only when available. Synthetic demo figures are not official university prices.</p>
        <div class="ud-inline-actions"><RouterLink :to="`/finance?program=${program.id}`">Calculate total costs →</RouterLink><RouterLink to="/scholarships">Explore scholarships →</RouterLink></div>
        <h3>Tuition and fees</h3>
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

      <!-- City and reviews: the catalogue has no university imagery, city-living facts or review endpoint -->
      <section v-else-if="activeTab === 'living'" class="ud-section">
        <div class="ud-card ud-tab-card">
          <h2>Living in {{ program.university.city || 'the city' }}</h2>
          <p class="ud-muted">Find out more about studying in {{ countryLabel }}. Local living-cost and lifestyle facts vary by city and student circumstances.</p>
          <div class="ud-stats ud-stats-3">
            <article><span>City</span><strong>{{ program.university.city || 'Not available' }}</strong><small>University location</small></article>
            <article><span>Country</span><strong>{{ countryLabel }}</strong><small>Study destination</small></article>
            <article><span>Verified living expenses</span><strong>Not available</strong><small>Use the finance tool for available estimates</small></article>
          </div>
          <div class="ud-inline-actions"><RouterLink :to="`/destinations/${program.country_code}`">View destination guide →</RouterLink><RouterLink :to="`/finance?program=${program.id}`">Explore living costs →</RouterLink></div>
        </div>
      </section>
      <section v-else-if="activeTab === 'reviews'" class="ud-section">
        <div class="ud-card ud-tab-card ud-empty">
          <div class="ud-empty-icon" aria-hidden="true">☆</div>
          <h2>Student reviews</h2>
          <p>Verified student reviews are not available for this institution yet. We'll show them here only when a trustworthy source is provided.</p>
          <p v-if="isFictionalDemo" class="ud-demo">This is a fictional demo institution; real student reviews do not exist.</p>
        </div>
      </section>

      <!-- intakes -->
      <section v-else-if="activeTab === 'intakes'" class="ud-card ud-tab-card">
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
          <h2>Jobs &amp; ROI — career evidence</h2>
          <p class="muted small" style="margin-top: 0">
            Verified graduate employment and salary data, when available, show cohort and sample details.
            These figures are not personal salary or employment guarantees.
          </p>
          <RouterLink to="/roi" class="ud-source-link">Explore ROI planning →</RouterLink>
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


<style scoped>
.university-detail { width: 100%; min-width: 0; color: #133e35; padding-bottom: 44px; }
.ud-breadcrumb { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; color: #77938b; font-size: .83rem; padding: 3px 0 19px; }
.ud-breadcrumb a { color: #07815e; text-decoration: none; }
.ud-hero { display: flex; align-items: center; gap: 24px; padding: 28px; border: 1px solid #dbe8e1; border-radius: 18px; background: #fff; box-shadow: 0 14px 36px rgba(25, 72, 55, .06); }
.ud-emblem { flex: 0 0 100px; width: 100px; height: 100px; border-radius: 18px; background: linear-gradient(140deg,#07583e,#0b956a); border: 1px solid #0e815e; box-shadow: inset 0 1px 0 #ffffff55; display: grid; place-items: center; color: #fff; font-size: 3rem; font-weight: 900; }
.ud-identity { flex: 1; min-width: 0; }
.ud-eyebrow { display: block; font-size: .71rem; font-weight: 800; letter-spacing: .13em; color: #15976e; margin-bottom: 7px; }
.ud-identity h1 { margin: 0 0 10px; font-weight: 850; letter-spacing: -.035em; line-height: 1.16; font-size: clamp(1.5rem, 2.4vw, 2.25rem); overflow-wrap: anywhere; }
.ud-location { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; font-size: .87rem; margin: 0 0 11px; color: #627e73; }
.ud-program-name { display: flex; flex-wrap: wrap; gap: 9px; font-size: .84rem; color: #537167; line-height: 1.4; }
.ud-program-name strong { font-weight: 750; color: #125943; }
.ud-hero-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 0 0 auto; justify-content: flex-end; max-width: 340px; }
.ud-hero-actions :deep(.btn) { border-radius: 9px; min-height: 40px; font-weight: 700; }
.ud-demo { display: inline-flex; margin-top: 10px; padding: 5px 10px; color: #88510a; background: #fff4de; border: 1px solid #f1dcae; border-radius: 8px; font-size: .72rem; font-weight: 750; }
.ud-disclosure { margin: 13px 0 0; border: 1px solid #f1e2bf; border-radius: 11px; background: #fffaf0; color: #8d681b; padding: 10px 17px; font-size: .82rem; }
.ud-disclosure summary { cursor: pointer; font-weight: 750; }
.ud-disclosure ul { margin: 11px 0 1px; padding-left: 20px; }
.ud-disclosure li { margin: 4px 0; }
.ud-tabs-outer { overflow-x: auto; margin: 21px 0 25px; border-bottom: 1px solid #deebe4; scrollbar-width: thin; }
.ud-tabs { display: flex; gap: 3px; width: max-content; min-width: 100%; }
.ud-tabs button { padding: 14px 18px; border: 0; border-bottom: 3px solid transparent; font: inherit; font-size: .85rem; font-weight: 750; white-space: nowrap; cursor: pointer; background: transparent; color: #72867e; }
.ud-tabs button[aria-selected='true'] { color: #087a59; border-bottom-color: #0f9970; }
.ud-tabs button:hover { background: #eff8f3; color: #0b664d; }
.ud-tabs button:focus-visible { outline: 3px solid #9adac4; outline-offset: -3px; }
.ud-section { display: grid; gap: 20px; min-width: 0; }
.ud-card { background: #fff; border: 1px solid #dce9e1; border-radius: 15px; padding: 22px; min-width: 0; box-shadow: 0 9px 30px rgba(27, 81, 57, .035); }
.ud-card h2 { margin: 0 0 15px; font-size: 1.23rem; letter-spacing: -.025em; color: #163f34; }
.ud-card h3 { margin: 0 0 13px; font-size: 1.02rem; color: #184e3f; }
.ud-overview-body { display: grid; grid-template-columns: minmax(250px, .9fr) minmax(0, 1.1fr); gap: 24px; align-items: start; }
.ud-campus-illustration { overflow: hidden; border-radius: 13px; background: #edf8f2; border: 1px solid #d7e9dd; position: relative; }
.ud-campus-illustration svg { display: block; width: 100%; height: auto; }
.ud-campus-illustration span { position: absolute; bottom: 9px; right: 10px; color: #255b49; background: #ffffffd9; border-radius: 6px; padding: 4px 8px; font-size: .68rem; }
.ud-overview-copy p { color: #5b756b; line-height: 1.65; margin: 0 0 15px; }
.ud-highlights { display: grid; gap: 11px; margin: 15px 0; }
.ud-highlights div { border-bottom: 1px solid #edf1ee; padding-bottom: 8px; }
.ud-highlights dt { color: #8aa095; font-size: .73rem; }
.ud-highlights dd { color: #204f3e; font-weight: 700; margin: 3px 0 0; font-size: .84rem; }
.ud-source-link, .ud-inline-actions a, .ud-summary-row a { display: inline-flex; color: #087a57; font-weight: 750; text-decoration: none; font-size: .84rem; }
.ud-source-link:hover, .ud-inline-actions a:hover, .ud-summary-row a:hover { text-decoration: underline; }
.ud-mini-note { margin: 10px 0 0; color: #86998c; font-size: .76rem; }
.ud-stats { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 14px; }
.ud-stats article { min-width: 0; padding: 18px; background: #f4faf7; border: 1px solid #deebe3; border-radius: 13px; }
.ud-stats span, .ud-stats small { display: block; color: #738f82; font-size: .76rem; }
.ud-stats strong { display: block; margin: 8px 0; font-size: clamp(1rem, 1.4vw, 1.4rem); font-weight: 850; color: #153d30; overflow-wrap: anywhere; }
.ud-stats small { line-height: 1.4; }
.ud-stats-3 { grid-template-columns: repeat(3,minmax(0,1fr)); margin: 18px 0; }
.ud-summary-row { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 15px; }
.ud-summary-row article { display: flex; flex-direction: column; align-items: start; gap: 7px; }
.ud-tab-card { margin-top: 0; }
.ud-muted { color: #6d887b; line-height: 1.6; font-size: .89rem; }
.ud-inline-actions { display: flex; flex-wrap: wrap; gap: 18px; padding: 12px 0 20px; }
.ud-empty { display: flex; align-items: center; flex-direction: column; text-align: center; padding: 60px 24px; }
.ud-empty p { max-width: 560px; color: #72897e; }
.ud-empty-icon { display: grid; place-items: center; width: 74px; height: 74px; background: #e4f6ec; color: #13976c; border-radius: 50%; font-size: 2rem; margin-bottom: 18px; }
.university-detail :deep(.data) { width: 100%; }
.university-detail :deep(.table-wrap) { max-width: 100%; overflow-x: auto; }
@media(max-width: 1050px) { .ud-hero { flex-wrap: wrap; } .ud-hero-actions { justify-content: flex-start; max-width: none; width: 100%; } }
@media(max-width: 750px) { .ud-hero { padding: 19px; gap: 16px; } .ud-emblem { flex-basis: 68px; width: 68px; height: 68px; font-size: 2rem; } .ud-overview-body { grid-template-columns: minmax(0,1fr); } .ud-stats, .ud-stats-3 { grid-template-columns: repeat(2,minmax(0,1fr)); } .ud-summary-row { grid-template-columns: minmax(0,1fr); } .ud-card { padding: 17px; } }
@media(max-width: 480px) { .ud-hero { gap: 12px; } .ud-identity h1 { font-size: 1.4rem; } .ud-program-name { flex-direction: column; gap: 2px; } .ud-stats, .ud-stats-3 { grid-template-columns: minmax(0,1fr); } .ud-hero-actions { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); } .ud-hero-actions :deep(.btn) { width: 100%; } .ud-tabs button { padding: 12px 13px; font-size: .8rem; } }
</style>
