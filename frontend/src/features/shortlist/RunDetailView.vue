<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import { formatDate, formatNumber, formatValue, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import ShortlistDataWarnings from '../../components/ShortlistDataWarnings.vue'
import CompareToggle from '../../components/CompareToggle.vue'
import SaveToggle from '../../components/SaveToggle.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import ShortlistPagination from '../../components/ShortlistPagination.vue'
import type { ExplanationEntry, RecommendationItem, TierKey } from '../../types/api'

/** Step 7 - UI filters are client-side and never alter the saved recommendation run. */
const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const runId = computed(() => String(route.params.runId))
const runState = useAsync(() => recommendations.getRun(runId.value), { immediate: true })
const explanationsState = useAsync(() => recommendations.explanations(runId.value), { immediate: true })
const run = computed(() => runState.data.value)

const TIERS: { key: TierKey; label: string; hint: string }[] = [
  { key: 'ambitious', label: 'Ambitious', hint: 'Stretch programs: some published requirements may be challenging.' },
  { key: 'target', label: 'Target', hint: 'Programs aligned with your academic profile and preferences.' },
  { key: 'safer_fit', label: 'Safer-fit', hint: 'Your profile clears more of the published requirements; admission is not guaranteed.' },
]

type TierChoice = 'all' | TierKey
const tierFilter = ref<TierChoice>('all')
const selectedCountries = ref<string[]>([])
const selectedStatuses = ref<string[]>([])
const minFitPercent = ref(0)
const sortBy = ref<'best' | 'name' | 'country'>('best')
const query = ref('')
const showExcluded = ref(false)
// Pagination is applied *after* filtering and sorting, so totals stay accurate.
const resultsPage = ref(1)
const resultsPageSize = ref(6)
const excludedPage = ref(1)
const excludedPageSize = ref(6)

/** The run is the source of truth for tier membership. Explanation details enrich it. */
const allItems = computed<(RecommendationItem | ExplanationEntry)[]>(() => {
  const byProgram = new Map<string, RecommendationItem | ExplanationEntry>()
  const details = new Map((explanationsState.data.value?.items ?? []).map((item) => [item.program_id, item]))
  for (const tier of TIERS) {
    for (const item of run.value?.tiers[tier.key] ?? []) {
      const enriched = details.get(item.program_id)
      byProgram.set(item.program_id, enriched ? { ...item, ...enriched, tier: tier.key } : { ...item, tier: tier.key })
    }
  }
  return [...byProgram.values()]
})

const excluded = computed(() => (explanationsState.data.value?.items ?? []).filter((item) => item.tier === null))
const counts = computed(() => ({
  all: allItems.value.length,
  ambitious: allItems.value.filter((item) => item.tier === 'ambitious').length,
  target: allItems.value.filter((item) => item.tier === 'target').length,
  safer_fit: allItems.value.filter((item) => item.tier === 'safer_fit').length,
}))

function countryName(code: string): string {
  try {
    return new Intl.DisplayNames(['en'], { type: 'region' }).of(code.toUpperCase()) ?? code.toUpperCase()
  } catch {
    return code.toUpperCase()
  }
}

const countries = computed(() => {
  const totals = new Map<string, number>()
  for (const item of allItems.value) {
    const code = item.country_code.toUpperCase()
    totals.set(code, (totals.get(code) ?? 0) + 1)
  }
  return [...totals].map(([code, count]) => ({ code, count, name: countryName(code) }))
    .sort((a, b) => a.name.localeCompare(b.name))
})

const eligibilityOptions = computed(() => {
  const statuses = new Map<string, number>()
  for (const item of allItems.value) {
    const status = item.eligibility_status
    statuses.set(status, (statuses.get(status) ?? 0) + 1)
  }
  return [...statuses].map(([status, count]) => ({ status, count, label: statusLabel(status) }))
})

function statusLabel(status: string): string {
  if (status === 'unknown_needs_review') return 'Needs review'
  if (status === 'conditionally_eligible') return 'Conditionally eligible'
  return humanize(status)
}

const visibleItems = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  const filtered = allItems.value.filter((item) => {
    if (tierFilter.value !== 'all' && item.tier !== tierFilter.value) return false
    if (selectedCountries.value.length && !selectedCountries.value.includes(item.country_code.toUpperCase())) return false
    if (selectedStatuses.value.length && !selectedStatuses.value.includes(item.eligibility_status)) return false
    if (minFitPercent.value > 0 && (item.fit_score === null || item.fit_score * 100 < minFitPercent.value)) return false
    if (needle && !`${item.university} ${item.program_name} ${countryName(item.country_code)}`.toLocaleLowerCase().includes(needle)) return false
    return true
  })
  return filtered.sort((a, b) => {
    if (sortBy.value === 'name') return a.university.localeCompare(b.university) || a.program_name.localeCompare(b.program_name)
    if (sortBy.value === 'country') return countryName(a.country_code).localeCompare(countryName(b.country_code)) || a.university.localeCompare(b.university)
    return (b.fit_score ?? -1) - (a.fit_score ?? -1) || a.university.localeCompare(b.university)
  })
})

const resultsTotalPages = computed(() => Math.max(1, Math.ceil(visibleItems.value.length / resultsPageSize.value)))
const paginatedItems = computed(() => visibleItems.value.slice(
  (resultsPage.value - 1) * resultsPageSize.value,
  resultsPage.value * resultsPageSize.value,
))
const excludedTotalPages = computed(() => Math.max(1, Math.ceil(excluded.value.length / excludedPageSize.value)))
const paginatedExcluded = computed(() => excluded.value.slice(
  (excludedPage.value - 1) * excludedPageSize.value,
  excludedPage.value * excludedPageSize.value,
))

// New searches/filters begin at page 1, rather than showing a blank later page.
watch([tierFilter, selectedCountries, selectedStatuses, minFitPercent, sortBy, query], () => {
  resultsPage.value = 1
})
// Keep page indices valid if a recommendation run refreshes or is replaced.
watch(resultsTotalPages, (lastPage) => { resultsPage.value = Math.min(resultsPage.value, lastPage) })
watch(excludedTotalPages, (lastPage) => { excludedPage.value = Math.min(excludedPage.value, lastPage) })
watch(runId, () => { resultsPage.value = 1; excludedPage.value = 1 })
function changeResultsPageSize(size: number) { resultsPageSize.value = size; resultsPage.value = 1 }
function changeExcludedPageSize(size: number) { excludedPageSize.value = size; excludedPage.value = 1 }

const activeTier = computed(() => TIERS.find((tier) => tier.key === tierFilter.value))
const hasFilters = computed(() => tierFilter.value !== 'all' || selectedCountries.value.length > 0 || selectedStatuses.value.length > 0 || minFitPercent.value > 0 || Boolean(query.value.trim()))

function toggleCountry(code: string) {
  selectedCountries.value = selectedCountries.value.includes(code)
    ? selectedCountries.value.filter((value) => value !== code)
    : [...selectedCountries.value, code]
}
function toggleStatus(status: string) {
  selectedStatuses.value = selectedStatuses.value.includes(status)
    ? selectedStatuses.value.filter((value) => value !== status)
    : [...selectedStatuses.value, status]
}
function resetFilters() {
  tierFilter.value = 'all'
  selectedCountries.value = []
  selectedStatuses.value = []
  minFitPercent.value = 0
  query.value = ''
  sortBy.value = 'best'
  resultsPage.value = 1
}
function fitPercent(score: number | null): number | null {
  return score === null ? null : Math.max(0, Math.min(100, Math.round(score * 100)))
}
function explainItem(item: RecommendationItem | ExplanationEntry): ExplanationEntry | null {
  return 'why' in item ? item : null
}
const rerunning = ref(false)
async function rerun() {
  if (rerunning.value) return
  rerunning.value = true
  try {
    const newRun = await recommendations.createRun()
    ui.push('New shortlist generated. Your previous results are still saved.', 'success')
    await router.push(`/shortlist/${newRun.run_id}`)
    // Router reuses this view when only the runId changes.
    resetFilters()
    await Promise.all([runState.run(), explanationsState.run()])
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      await router.push({ path: '/login', query: { redirect: route.fullPath } })
    } else ui.pushError(err)
  } finally {
    rerunning.value = false
  }
}
</script>

<template>
  <AsyncState
    :loading="runState.loading.value"
    :error="runState.error.value"
    :empty="!run"
    empty-title="Shortlist not found"
    empty-hint="It may belong to another account, or the link may be out of date."
    @retry="runState.run"
  >
    <template #empty-action>
      <RouterLink to="/shortlist" class="btn">Back to your shortlists</RouterLink>
    </template>

    <div v-if="run" class="results-page">
      <div class="results-breadcrumb">
        <RouterLink to="/profile">Your profile</RouterLink>
        <span aria-hidden="true">/</span>
        <span>Shortlist results</span>
      </div>

      <div class="results-intro">
        <div>
          <span class="results-eyebrow"><span class="eyebrow-dot"></span> STEP 07 · YOUR UNIVERSITY MATCHES</span>
          <h1 v-if="counts.all">Find your <span>right-fit university.</span></h1>
          <h1 v-else>Your shortlist, <span>clearly explained.</span></h1>
          <p v-if="counts.all">Explore program matches built around your profile and study preferences.</p>
          <p v-else>Your recommendations are ready to review. See what happened and what you can do next.</p>
        </div>
        <div class="intro-actions">
          <RouterLink to="/onboarding" class="action-muted">Edit profile</RouterLink>
          <button class="action-primary" type="button" :disabled="rerunning" @click="rerun">{{ rerunning ? 'Generating…' : '↻ New shortlist' }}</button>
        </div>
      </div>

      <div class="results-summary" aria-label="Recommendation run summary">
        <div class="summary-stat"><span class="summary-stat-icon green" aria-hidden="true">✓</span><div><strong>{{ counts.all }}</strong><span>Shortlisted programs</span></div></div>
        <div class="summary-stat"><span class="summary-stat-icon amber" aria-hidden="true">!</span><div><strong>{{ run.excluded_count }}</strong><span>Programs excluded</span></div></div>
        <div class="summary-stat"><span class="summary-stat-icon mint" aria-hidden="true">↗</span><div><strong>{{ counts.all + run.excluded_count }}</strong><span>Programs evaluated in this run</span></div></div>
      </div>

      <div class="results-notice">
        <span class="notice-icon" aria-hidden="true">✦</span>
        <p><strong>Evidence-first matching.</strong> These are program fit scores, <strong>not admission probabilities.</strong> Requirements and available evidence vary by university.</p>
      </div>

      <ShortlistDataWarnings :warnings="run.data_warnings" :demo="allItems.some((item) => String(item.program_name ?? '').includes('[FICTIONAL DEMO]'))" />

      <div class="results-layout">
        <aside v-if="counts.all" class="filter-panel" aria-label="Shortlist filters">
          <div class="filter-heading"><h2>Filters</h2><button type="button" :disabled="!hasFilters" @click="resetFilters">Reset</button></div>
          <div class="filter-section">
            <h3>Country <span>{{ countries.length }}</span></h3>
            <p v-if="!countries.length" class="filter-hint">No countries to filter.</p>
            <label v-for="country in countries" :key="country.code" class="filter-check">
              <input type="checkbox" :checked="selectedCountries.includes(country.code)" @change="toggleCountry(country.code)" />
              <span>{{ country.name }}</span><small>{{ country.count }}</small>
            </label>
          </div>
          <div class="filter-section">
            <h3>Eligibility</h3>
            <label v-for="option in eligibilityOptions" :key="option.status" class="filter-check">
              <input type="checkbox" :checked="selectedStatuses.includes(option.status)" @change="toggleStatus(option.status)" />
              <span>{{ option.label }}</span><small>{{ option.count }}</small>
            </label>
          </div>
          <div class="filter-section">
            <h3>Minimum fit score</h3>
            <div class="score-range-label"><span>Any score</span><strong>{{ minFitPercent }}%</strong></div>
            <input v-model.number="minFitPercent" class="score-range" type="range" min="0" max="100" step="5" aria-label="Minimum program fit score percentage" />
            <p class="filter-hint">Fit is not an admission chance. Programs with missing fit scores are hidden above 0%.</p>
          </div>
          <div class="filter-section">
            <h3>Sort results</h3>
            <select v-model="sortBy" class="filter-select" aria-label="Sort programs">
              <option value="best">Best fit first</option>
              <option value="name">University name</option>
              <option value="country">Country</option>
            </select>
          </div>
          <div class="finance-nudge">
            <span class="finance-nudge-icon" aria-hidden="true">◎</span>
            <strong>Planning your budget?</strong>
            <p>Compare study costs and funding using the dedicated financial tools.</p>
            <RouterLink to="/finance">Explore cost planning →</RouterLink>
          </div>
        </aside>

        <aside v-else class="guide-panel" aria-label="What to do next">
          <div class="guide-head"><span class="guide-mark" aria-hidden="true">✦</span><span>YOUR NEXT STEPS</span></div>
          <h2>Turn this into a better shortlist.</h2>
          <p>The system evaluated your current profile and couldn't include any programs. Here's how to review the result.</p>
          <div class="guide-steps">
            <div><span>01</span><div><strong>Review exclusions</strong><small>See the reasons and any missing requirements.</small></div></div>
            <div><span>02</span><div><strong>Check your profile</strong><small>Confirm academic information, destination, intake, and budget.</small></div></div>
            <div><span>03</span><div><strong>Generate again</strong><small>Create a new saved run after making changes.</small></div></div>
          </div>
          <RouterLink to="/onboarding" class="guide-primary">Review your profile <span aria-hidden="true">→</span></RouterLink>
          <RouterLink to="/discover" class="guide-secondary">Browse all programs <span aria-hidden="true">↗</span></RouterLink>
          <div class="guide-footnote">Exclusion decisions are based on the requirements and source information available for this run.</div>
        </aside>

        <section class="results-main" aria-labelledby="results-list-heading">
          <div v-if="run?.matching_preferences?.degree_title" class="degree-match-context">
            <strong>Matching:</strong> {{ run.matching_preferences.degree_title }}
            <span v-if="run.matching_preferences.specialization"> Â· {{ run.matching_preferences.specialization }}</span>
            <small>Only programs with a matching degree award and specialization appear in this shortlist. No matches means none were verified in the current catalogue.</small>
          </div>
          <div class="results-main-head">
            <div><span class="results-label">PERSONALIZED MATCHES</span><h2 id="results-list-heading">{{ counts.all ? `${counts.all} ${counts.all === 1 ? 'program' : 'programs'} shortlisted for you` : 'What your results mean' }}</h2><p>Generated {{ formatDate(run.created_at) || 'recently' }} · {{ humanize(run.status) }}</p></div>
            <RouterLink class="history-link" to="/shortlist">View history ↗</RouterLink>
          </div>

          <div v-if="counts.all" class="results-tabs" role="group" aria-label="Filter by match category">
            <button type="button" :class="{ selected: tierFilter === 'all' }" :aria-pressed="tierFilter === 'all'" @click="tierFilter = 'all'">All <span>{{ counts.all }}</span></button>
            <button v-for="tier in TIERS" :key="tier.key" type="button" :class="{ selected: tierFilter === tier.key }" :aria-pressed="tierFilter === tier.key" @click="tierFilter = tier.key">{{ tier.label }} <span>{{ counts[tier.key] }}</span></button>
          </div>

          <div v-if="counts.all" class="results-toolbar">
            <label class="results-search"><span aria-hidden="true">⌕</span><input v-model="query" type="search" placeholder="Search universities or programs" aria-label="Search shortlist results" /></label>
            <span>{{ visibleItems.length }} {{ visibleItems.length === 1 ? 'result' : 'results' }}</span>
          </div>
          <p v-if="counts.all && activeTier" class="tier-tip">{{ activeTier.hint }}</p>

          <div v-if="!counts.all" class="zero-state">
            <div class="zero-art" aria-hidden="true">
              <svg viewBox="0 0 120 120" fill="none" aria-hidden="true">
                <circle cx="60" cy="60" r="56" fill="#EDF9F3"/>
                <rect x="30" y="25" width="51" height="63" rx="9" fill="white" stroke="#C4E9D5" stroke-width="2.5"/>
                <rect x="39" y="38" width="24" height="5" rx="2.5" fill="#B0DEC6"/>
                <rect x="39" y="50" width="32" height="5" rx="2.5" fill="#D6EDE0"/>
                <rect x="39" y="62" width="25" height="5" rx="2.5" fill="#D6EDE0"/>
                <circle cx="77" cy="76" r="17" fill="#E5F7EC" stroke="#159A6C" stroke-width="3.5"/>
                <path d="M89.5 88.5 103 102" stroke="#0C825C" stroke-width="6" stroke-linecap="round"/>
                <path d="M77 69v9" stroke="#159A6C" stroke-width="3.5" stroke-linecap="round"/>
                <circle cx="77" cy="83" r="2" fill="#159A6C"/>
              </svg>
            </div>
            <span class="zero-kicker">NO ELIGIBLE MATCHES IN THIS RUN</span>
            <h3>We couldn't shortlist a program yet.</h3>
            <p>{{ run.excluded_count ? `${run.excluded_count} ${run.excluded_count === 1 ? 'program was' : 'programs were'} excluded based on this run's requirements.` : 'No programs were included in this run.' }} Review the details below to see why, then update your profile or explore the full program catalog.</p>
            <div class="zero-actions">
              <RouterLink to="/onboarding" class="action-primary">Review profile <span aria-hidden="true">→</span></RouterLink>
              <RouterLink to="/discover" class="action-muted">Explore universities</RouterLink>
            </div>
          </div>

          <div v-if="visibleItems.length" class="result-card-list">
            <article v-for="item in paginatedItems" :key="item.program_id" class="result-card">
              <div class="result-card-main">
                <div class="uni-monogram" aria-hidden="true">{{ item.university.slice(0, 1).toUpperCase() }}</div>
                <div class="result-card-info">
                  <div class="result-title-row">
                    <div>
                      <h3><RouterLink :to="`/programs/${item.program_id}`">{{ item.university }}</RouterLink></h3>
                      <p class="university-place"><span aria-hidden="true">⌖</span>{{ countryName(item.country_code) }} · {{ item.program_name }}</p>
                    </div>
                    <span class="tier-tag" :class="`tier-${item.tier}`">{{ item.tier === 'safer_fit' ? 'Safer-fit' : humanize(item.tier) }} match</span>
                  </div>
                  <div class="result-details">
                    <p><span class="fact-dot"></span><strong>Eligibility:</strong> <StatusBadge :status="item.eligibility_status" /></p>
                    <p v-for="reason in item.reason_codes.slice(0, 2)" :key="reason"><span class="fact-dot"></span>{{ humanize(reason) }}</p>
                    <p v-if="!item.reason_codes.length"><span class="fact-dot"></span>Review the published program requirements</p>
                  </div>
                  <div v-if="item.concerns.length || item.missing_information.length" class="result-alerts">
                    <span v-for="concern in item.concerns.slice(0, 2)" :key="concern">⚑ {{ humanize(concern) }}</span>
                    <span v-for="missing in item.missing_information.slice(0, 2)" :key="missing">ⓘ Missing: {{ humanize(missing) }}</span>
                  </div>
                </div>
              </div>

              <div class="result-card-side">
                <div class="fit-ring" :style="{ '--ring-progress': `${fitPercent(item.fit_score) ?? 0}%` }" :class="{ 'fit-unknown': item.fit_score === null }" :aria-label="item.fit_score === null ? 'Fit score unavailable' : `${fitPercent(item.fit_score)} percent fit score; not an admission probability`">
                  <div><strong>{{ fitPercent(item.fit_score) === null ? '—' : `${fitPercent(item.fit_score)}%` }}</strong><small>FIT SCORE</small></div>
                </div>
                <RouterLink class="detail-button" :to="`/programs/${item.program_id}`">View details <span aria-hidden="true">→</span></RouterLink>
              </div>

              <div class="result-card-footer">
                <div class="card-actions"><SaveToggle :program-id="item.program_id" /><CompareToggle :program-id="item.program_id" :label="item.program_name" /><RouterLink :to="`/finance?program=${item.program_id}`" class="finance-link">Explore costs →</RouterLink></div>
                <details v-if="explainItem(item)" class="evidence-details">
                  <summary>Why this match? <span aria-hidden="true">⌄</span></summary>
                  <div v-if="explainItem(item)?.score_breakdown?.length" class="evidence-table-wrap">
                    <table><thead><tr><th>Factor</th><th>Weight</th><th>Score</th><th>Explanation</th></tr></thead><tbody>
                      <tr v-for="entry in explainItem(item)?.score_breakdown" :key="entry.dimension"><td>{{ humanize(entry.dimension) }}</td><td>{{ formatNumber(entry.weight, 2) }}</td><td>{{ entry.score === null ? 'Unavailable' : formatNumber(entry.score, 2) }}</td><td>{{ entry.note ?? '—' }}</td></tr>
                    </tbody></table>
                  </div>
                  <p v-if="explainItem(item)?.why?.hard_constraint_status" class="evidence-hard">Hard constraints: <strong>{{ humanize(explainItem(item)?.why?.hard_constraint_status) }}</strong></p>
                  <div v-if="explainItem(item)?.why?.requirement_outcomes?.length" class="evidence-table-wrap">
                    <table><thead><tr><th>Requirement</th><th>Expected</th><th>Your value</th><th>Status</th></tr></thead><tbody>
                      <tr v-for="outcome in explainItem(item)?.why?.requirement_outcomes" :key="outcome.requirement_id"><td>{{ outcome.explanation ?? outcome.requirement_id.slice(0, 8) }}</td><td>{{ formatValue(outcome.expected) }}</td><td>{{ formatValue(outcome.applicant_value) }}</td><td>{{ humanize(outcome.status) }}</td></tr>
                    </tbody></table>
                  </div>
                </details>
              </div>
            </article>
          </div>

          <ShortlistPagination
            v-if="visibleItems.length"
            class="results-pager"
            :page="resultsPage"
            :page-size="resultsPageSize"
            :total-items="visibleItems.length"
            label="Shortlisted programs"
            @update:page="resultsPage = $event"
            @update:page-size="changeResultsPageSize"
          />

          <div v-else-if="counts.all" class="results-empty">
            <span aria-hidden="true">⌕</span><h3>No matches for these filters</h3>
            <p>{{ counts.all ? 'Try another country, tier, eligibility status, or fit score.' : 'No programs are in this run yet. Update your profile or create a new shortlist.' }}</p>
            <button v-if="hasFilters" class="action-primary" type="button" @click="resetFilters">Clear filters</button>
            <RouterLink v-else class="action-primary" to="/onboarding">Review profile</RouterLink>
          </div>

          <section v-if="!counts.all && run.excluded_count" class="exclusion-review" aria-labelledby="exclusions-heading">
            <div class="exclusion-review-head">
              <div>
                <span class="results-label">UNDERSTAND YOUR RESULTS</span>
                <h3 id="exclusions-heading">Programs to review <span>{{ run.excluded_count }}</span></h3>
                <p>These programs were excluded in this recommendation run. Explore the reason codes and check each program's published requirements.</p>
              </div>
            </div>
            <p v-if="explanationsState.loading.value" class="exclusion-loading" role="status">Loading individual program explanations…</p>
            <p v-else-if="explanationsState.error.value" class="exclusion-loading">The individual explanations couldn't be loaded. You can try again using the button below.
              <button class="exclusion-retry" type="button" @click="explanationsState.run()">Retry explanations</button>
            </p>
            <template v-else-if="excluded.length">
              <div class="exclusion-grid">
                <article v-for="item in paginatedExcluded" :key="item.program_id" class="exclusion-card">
                  <span class="excluded-avatar" aria-hidden="true">{{ item.university.slice(0, 1).toUpperCase() }}</span>
                  <div class="exclusion-card-copy">
                    <div class="exclusion-card-title-row"><h4>{{ item.university }}</h4><span class="exclusion-pill">Excluded</span></div>
                    <p class="excluded-program">{{ item.program_name }} <span aria-hidden="true">·</span> {{ countryName(item.country_code) }}</p>
                    <div class="reason-wrap" v-if="item.reason_codes.length">
                      <span v-for="reason in item.reason_codes.slice(0, 3)" :key="reason" class="reason-tag">{{ humanize(reason) }}</span>
                    </div>
                    <p v-else class="exclusion-context">No specific reason code is available for this program.</p>
                    <p v-if="item.concerns.length" class="exclusion-context"><strong>Concerns:</strong> {{ item.concerns.slice(0, 2).map(humanize).join(' · ') }}</p>
                    <p v-if="item.missing_information.length" class="exclusion-context"><strong>Missing information:</strong> {{ item.missing_information.slice(0, 2).map(humanize).join(' · ') }}</p>
                    <RouterLink :to="`/programs/${item.program_id}`" class="excluded-detail">View program details <span aria-hidden="true">→</span></RouterLink>
                  </div>
                </article>
              </div>
              <ShortlistPagination
                class="results-pager excluded-pager"
                :page="excludedPage"
                :page-size="excludedPageSize"
                :total-items="excluded.length"
                label="Excluded programs"
                @update:page="excludedPage = $event"
                @update:page-size="changeExcludedPageSize"
              />
            </template>
            <div v-else class="exclusion-loading">Individual excluded-program details aren't available for this run. The total above comes from the saved recommendation result.</div>
          </section>

          <div v-if="counts.all && run.excluded_count > 0" class="excluded-panel">
            <button type="button" :aria-expanded="showExcluded" @click="showExcluded = !showExcluded"><span>Programs excluded by requirements</span><strong>{{ run.excluded_count }} {{ showExcluded ? '⌃' : '⌄' }}</strong></button>
            <div v-if="showExcluded" class="excluded-body">
              <p>These programs were excluded by mandatory constraints. The evidence may change when you update your profile.</p>
              <template v-if="excluded.length">
                <div v-for="item in paginatedExcluded" :key="item.program_id" class="excluded-item"><RouterLink :to="`/programs/${item.program_id}`">{{ item.university }} — {{ item.program_name }}</RouterLink><span>{{ item.reason_codes.map(humanize).join(' · ') || 'Does not meet a mandatory requirement' }}</span></div>
              </template>
              <p v-else>Details about excluded programs are currently unavailable.</p>
              <ShortlistPagination
                v-if="excluded.length"
                class="results-pager excluded-pager"
                :page="excludedPage"
                :page-size="excludedPageSize"
                :total-items="excluded.length"
                label="Excluded programs"
                @update:page="excludedPage = $event"
                @update:page-size="changeExcludedPageSize"
              />
            </div>
          </div>

          <p class="results-footnote">Results are based on your saved profile and available evidence. Scores are for comparing fit, not predicting admission. Tuition, scholarships, and outcomes require source verification.</p>
        </section>
      </div>
    </div>
  </AsyncState>
</template>

<style scoped>
.degree-match-context { display: flex; align-items: baseline; flex-wrap: wrap; gap: 5px; padding: 13px 16px; margin-bottom: 18px; border: 1px solid #cbe8d8; border-radius: 12px; background: #f0faf5; color: #155a43; font-size: .87rem; }
.degree-match-context small { display: block; width: 100%; margin-top: 3px; color: #5d7c6d; font-size: .77rem; line-height: 1.5; }
.results-page { --r-green: #0b805d; --r-ink: #1a3733; --r-muted: #738982; --r-line: #dce9e3; color: var(--r-ink); }
.results-breadcrumb { display: flex; gap: 10px; align-items: center; color: #9cb0a6; font-size: .76rem; padding: 0 0 24px; }
.results-breadcrumb a { color: #558674; }
.results-intro { display: flex; justify-content: space-between; align-items: center; gap: 22px; margin-bottom: 25px; }
.results-eyebrow { display: inline-flex; align-items: center; gap: 9px; font-size: .71rem; letter-spacing: .125em; font-weight: 850; color: #0b8661; }
.eyebrow-dot { width: 8px; height: 8px; background: #19bd90; border-radius: 50%; box-shadow: 0 0 0 4px #e2f5eb; }
.results-intro h1 { color: #173b34; font-size: clamp(1.65rem, 2.8vw, 2.5rem); letter-spacing: -.045em; font-weight: 840; margin: 10px 0 7px; }
.results-intro h1 span { color: #087f5d; }
.results-intro p { color: var(--r-muted); font-size: .91rem; margin: 0; }
.intro-actions { display: flex; align-items: center; gap: 10px; flex: none; }
.action-muted, .action-primary { display: inline-flex; align-items: center; justify-content: center; border-radius: 11px; min-height: 43px; padding: 11px 17px; font-size: .83rem; font-family: inherit; font-weight: 780; cursor: pointer; text-decoration: none; white-space: nowrap; }
.action-muted { background: white; color: #276c55; border: 1px solid #d8e7e0; }
.action-primary { background: #0b815f; border: 1px solid #0b815f; color: #fff; box-shadow: 0 6px 14px #0a8a6028; }
.action-primary:hover { background: #066c4c; text-decoration: none; }
.action-primary:disabled { opacity: .6; cursor: wait; }
.results-notice { display: flex; align-items: flex-start; gap: 12px; border: 1px solid #d6e9df; background: #eff9f4; border-radius: 12px; padding: 12px 17px; margin-bottom: 19px; }
.results-notice p { margin: 0; font-size: .79rem; line-height: 1.55; color: #547a69; }
.results-notice strong { color: #246148; }
.notice-icon { background: #daf2e5; color: #0c8a61; width: 25px; height: 25px; border-radius: 7px; flex: none; display: grid; place-items: center; }
.results-warning { margin-bottom: 18px; border-radius: 10px; background: #fff9ee; padding: 12px 16px; border: 1px solid #f3dcaa; color: #825d17; font-size: .81rem; }
.results-warning summary { cursor: pointer; font-weight: 750; }
.results-warning ul { margin: 9px 0 0; padding-left: 18px; }
.results-layout { display: grid; grid-template-columns: minmax(200px, 260px) minmax(0, 1fr); gap: 20px; align-items: start; }
.filter-panel, .results-main { background: #fff; border: 1px solid var(--r-line); border-radius: 16px; box-shadow: 0 12px 33px #1b695c08; min-width: 0; }
.filter-panel { padding: 21px 19px; }
.filter-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding-bottom: 19px; }
.filter-heading h2 { font-size: 1.06rem; margin: 0; letter-spacing: -.02em; color: #1f4238; }
.filter-heading button { background: none; border: 0; font: inherit; font-size: .76rem; color: #0a8561; font-weight: 750; cursor: pointer; }
.filter-heading button:disabled { color: #a7b6af; cursor: default; }
.filter-section { padding: 17px 0 19px; border-top: 1px solid #ebf1ed; }
.filter-section h3 { font-size: .84rem; color: #214b3d; margin: 0 0 12px; display: flex; justify-content: space-between; }
.filter-section h3 span { color: #91a49a; font-weight: 600; }
.filter-check { display: flex; align-items: center; min-width: 0; gap: 10px; padding: 6px 1px; cursor: pointer; font-size: .83rem; color: #5c776b; }
.filter-check input { width: 15px; height: 15px; accent-color: #0b8560; margin: 0; flex: none; }
.filter-check span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
.filter-check small { color: #9aad9f; font-size: .75rem; }
.score-range-label { display: flex; justify-content: space-between; color: #81978e; font-size: .73rem; margin-bottom: 8px; }
.score-range-label strong { color: #07865e; }
.score-range { width: 100%; accent-color: #0b865e; }
.filter-hint { color: #8aa096; font-size: .73rem; line-height: 1.45; margin: 5px 0 0; }
.filter-select { width: 100%; padding: 11px; min-width: 0; color: #2a5443; font: inherit; font-size: .81rem; border: 1px solid #d8e7df; border-radius: 9px; background: #fff; }
.finance-nudge { padding: 16px; border: 1px solid #d3eadc; background: #f0f9f4; border-radius: 12px; display: flex; flex-direction: column; align-items: flex-start; }
.finance-nudge-icon { font-size: 1.45rem; color: #12845d; }
.finance-nudge strong { font-size: .81rem; margin: 5px 0; }
.finance-nudge p { color: #779484; font-size: .73rem; line-height: 1.5; }
.finance-nudge a { font-size: .74rem; font-weight: 770; color: #098258; }
.results-main { padding: 25px; }
.results-main-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; }
.results-label { color: #0d8d66; font-size: .66rem; font-weight: 840; letter-spacing: .12em; }
.results-main-head h2 { color: #183c35; font-size: clamp(1.18rem, 1.8vw, 1.57rem); line-height: 1.35; letter-spacing: -.028em; margin: 6px 0; }
.results-main-head p { color: #849c91; font-size: .76rem; margin: 0; }
.history-link { color: #0d825c; font-size: .77rem; font-weight: 750; white-space: nowrap; }
.results-tabs { display: flex; flex-wrap: wrap; gap: 7px; border-bottom: 1px solid #e6efea; margin: 25px 0 17px; }
.results-tabs button { border: 0; border-bottom: 2px solid transparent; border-radius: 8px 8px 0 0; background: transparent; color: #829a8d; font: inherit; font-size: .77rem; font-weight: 760; padding: 11px 12px 13px; cursor: pointer; white-space: nowrap; }
.results-tabs button.selected { color: #087f5a; background: #f2f9f5; border-bottom-color: #0b9068; }
.results-tabs button span { display: inline-flex; align-items: center; justify-content: center; min-width: 21px; border-radius: 99px; padding: 0 5px; font-size: .7rem; background: #eef3ef; color: #728d7c; margin-left: 3px; }
.results-tabs button.selected span { background: #dff2e7; color: #087d5b; }
.results-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; }
.results-toolbar > span { font-size: .75rem; font-weight: 740; color: #91a49b; white-space: nowrap; }
.results-search { display: flex; align-items: center; gap: 8px; min-height: 40px; flex: 1; max-width: 405px; border: 1px solid #dce9e3; border-radius: 10px; background: #fdfefd; padding: 0 12px; }
.results-search span { font-size: 1.25rem; color: #80a093; }
.results-search input { border: 0; outline: none; background: transparent; width: 100%; min-width: 0; font: inherit; font-size: .8rem; color: #345b4d; }
.results-search input::placeholder { color: #9bb0a6; }
.tier-tip { border-radius: 9px; background: #f4faf6; color: #567e69; padding: 11px 13px; margin: 0 0 15px; font-size: .79rem; }
.result-card-list { display: grid; gap: 14px; }
.result-card { display: grid; grid-template-columns: minmax(0,1fr) 124px; gap: 11px 16px; padding: 19px 19px 15px; border: 1px solid #dce9e3; border-radius: 14px; background: #fff; box-shadow: 0 5px 14px #1e694b08; min-width: 0; }
.result-card:hover { border-color: #abdcc4; }
.result-card-main { display: flex; align-items: flex-start; gap: 15px; min-width: 0; }
.uni-monogram { flex: 0 0 49px; width: 49px; height: 49px; display: grid; place-items: center; border-radius: 13px; background: #e8f4ef; color: #0c825e; font-size: 1.45rem; font-weight: 850; border: 1px solid #cae9da; }
.result-card-info { flex: 1; min-width: 0; }
.result-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 7px; flex-wrap: wrap; }
.result-title-row h3 { font-size: 1.01rem; letter-spacing: -.02em; line-height: 1.35; margin: 2px 0 5px; }
.result-title-row h3 a { color: #194438; }
.university-place { display: flex; align-items: baseline; gap: 5px; color: #738d81; font-size: .76rem; margin: 0 0 11px; line-height: 1.45; }
.university-place > span { color: #14a275; font-weight: 900; }
.tier-tag { display: inline-flex; border-radius: 7px; padding: 4px 9px; background: #ecf6fd; color: #407398; font-size: .7rem; font-weight: 810; white-space: nowrap; }
.tier-tag.tier-target { background: #e2f6e9; color: #118250; }
.tier-tag.tier-safer_fit { background: #e4f5f0; color: #0c7159; }
.tier-tag.tier-ambitious { background: #fff5df; color: #967012; }
.result-details { display: grid; gap: 5px; }
.result-details p { margin: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 7px; font-size: .76rem; line-height: 1.5; color: #70897d; }
.result-details p strong { color: #45685a; }
.fact-dot { width: 7px; height: 7px; background: #26b987; border-radius: 50%; flex: none; }
.result-alerts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.result-alerts span { background: #fff7e9; color: #906d32; border-radius: 5px; padding: 3px 7px; font-size: .68rem; overflow-wrap: anywhere; }
.result-alerts span:nth-child(even) { background: #f1f6fa; color: #688297; }
.result-card-side { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 12px; }
.fit-ring { height: 93px; width: 93px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(#17a773 var(--ring-progress), #e9f1ed 0); }
.fit-ring.fit-unknown { background: #eaf0ec; }
.fit-ring > div { display: flex; flex-direction: column; align-items: center; justify-content: center; background: white; border-radius: 50%; height: 74px; width: 74px; }
.fit-ring strong { font-size: 1.37rem; line-height: 1.2; color: #1d674f; }
.fit-ring small { color: #88a096; font-size: .53rem; font-weight: 820; letter-spacing: .04em; }
.detail-button { display: flex; align-items: center; justify-content: center; gap: 5px; min-height: 34px; width: 100%; padding: 7px; border: 1px solid #badac8; color: #0d805b; border-radius: 8px; font-size: .73rem; font-weight: 830; white-space: nowrap; }
.detail-button:hover { background: #f2faf6; text-decoration: none; }
.result-card-footer { grid-column: 1 / -1; border-top: 1px solid #eef3ef; padding-top: 12px; display: flex; flex-direction: column; gap: 11px; }
.card-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
.card-actions :deep(.btn) { border-radius: 8px; padding: 6px 11px; font-size: .74rem; color: #39715a; border-color: #dceae1; background: #f8fcfa; }
.finance-link { font-size: .73rem; font-weight: 760; color: #0d865f; margin-left: auto; }
.evidence-details { padding: 5px 0 0; }
.evidence-details summary { cursor: pointer; font-size: .73rem; font-weight: 810; color: #0b8560; }
.evidence-details summary span { padding-left: 5px; }
.evidence-table-wrap { max-width: 100%; overflow-x: auto; margin-top: 13px; }
.evidence-table-wrap table { border-collapse: collapse; width: 100%; min-width: 420px; text-align: left; color: #496858; font-size: .72rem; }
.evidence-table-wrap th, .evidence-table-wrap td { padding: 8px 10px; border-bottom: 1px solid #e1ede6; vertical-align: top; }
.evidence-table-wrap th { background: #f6faf7; font-weight: 800; }
.evidence-hard { font-size: .74rem; margin: 10px 0; color: #617f70; }
.results-empty { text-align: center; padding: 60px 22px; border: 1px dashed #d9e9df; border-radius: 12px; }
.results-empty > span { font-size: 2rem; color: #0b906c; }
.results-empty h3 { margin: 8px 0; font-size: 1.13rem; }
.results-empty p { color: #80958b; font-size: .83rem; }
.excluded-panel { margin-top: 26px; border: 1px solid #e3eae4; border-radius: 12px; background: #fcfefc; overflow: hidden; }
.excluded-panel > button { display: flex; width: 100%; justify-content: space-between; align-items: center; padding: 17px; gap: 12px; text-align: left; border: 0; background: transparent; color: #657b6f; font: inherit; font-weight: 760; cursor: pointer; font-size: .83rem; }
.excluded-body { border-top: 1px solid #e3eae4; padding: 17px; font-size: .79rem; color: #6e8177; }
.excluded-item { display: flex; flex-direction: column; gap: 4px; border-top: 1px solid #eef2ee; padding: 10px 0; }
.excluded-item span { font-size: .72rem; }
.results-footnote { margin: 18px 0 0; color: #93a69b; font-size: .7rem; line-height: 1.55; }
/* Pagination is shared by shortlisted and excluded results. */
.results-pager { margin-top: 18px; }
.excluded-pager { margin-top: 14px; }
/* Empty-run experience: meaningful results, without invented matches. */
.results-summary { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:12px; margin: 0 0 17px; }
.summary-stat { display:flex; gap:13px; align-items:center; padding:17px 19px; background:#fff; border:1px solid #dfebe5; border-radius:14px; box-shadow:0 8px 25px rgba(15,98,69,.035); min-width:0; }
.summary-stat-icon { width:42px; height:42px; flex:none; display:grid; place-items:center; border-radius:12px; background:#e5f7ed; color:#0b805d; font-size:1.15rem; font-weight:850; }
.summary-stat-icon.amber { background:#fff4e6; color:#b07b32; }
.summary-stat-icon.mint { background:#eaf3f2; color:#457c70; }
.summary-stat div { display:flex; flex-direction:column; gap:2px; min-width:0; }
.summary-stat strong { font-size:1.43rem; font-weight:850; color:#173d32; letter-spacing:-.04em; line-height:1.14; }
.summary-stat div span { font-size:.75rem; color:#798f84; font-weight:650; line-height:1.35; }
.guide-panel { background:linear-gradient(158deg,#f0faf5 0%,#fff 70%); border:1px solid #d7e9de; border-radius:17px; padding:25px 21px; box-shadow:0 12px 35px rgba(31,101,71,.04); }
.guide-head { display:flex; align-items:center; gap:9px; font-size:.67rem; color:#09865f; letter-spacing:.11em; font-weight:850; }
.guide-mark { width:26px; height:26px; display:grid; place-items:center; border-radius:8px; background:#d7f2e4; font-size:1rem; }
.guide-panel h2 { color:#164734; margin:17px 0 9px; font-size:1.26rem; letter-spacing:-.035em; line-height:1.3; }
.guide-panel > p { color:#72877c; line-height:1.6; font-size:.79rem; margin-bottom:21px; }
.guide-steps { display:grid; gap:18px; border-top:1px solid #e2eee6; padding-top:21px; }
.guide-steps > div { display:flex; align-items:flex-start; gap:11px; }
.guide-steps > div > span { font-size:.68rem; color:#0d845d; background:#ddf3e6; border-radius:8px; padding:6px 7px; font-weight:850; }
.guide-steps strong,.guide-steps small { display:block; }
.guide-steps strong { font-size:.79rem; color:#244d3b; }
.guide-steps small { color:#859a8d; font-size:.72rem; line-height:1.5; margin-top:3px; }
.guide-primary,.guide-secondary { display:flex; align-items:center; justify-content:space-between; gap:10px; border-radius:10px; padding:11px 13px; text-decoration:none; font-size:.81rem; font-weight:800; }
.guide-primary { background:#09805d; color:#fff; margin-top:23px; }
.guide-primary:hover { background:#07694e; text-decoration:none; }
.guide-secondary { border:1px solid #d7e9df; background:#fff; color:#157757; margin-top:9px; }
.guide-secondary:hover { text-decoration:none; background:#f4faf6; }
.guide-footnote { border-top:1px solid #e4eee7; margin-top:25px; padding-top:17px; font-size:.7rem; line-height:1.6; color:#91a49a; }
.zero-state { text-align:center; background:linear-gradient(168deg,#f7fdf9,#fff 82%); border:1px solid #deeee4; border-radius:16px; padding:30px clamp(18px,4vw,38px) 30px; margin-top:23px; }
.zero-art { width:115px; height:115px; margin:0 auto 10px; }
.zero-art svg { display:block; width:100%; height:100%; }
.zero-kicker { font-size:.66rem; font-weight:850; letter-spacing:.13em; color:#168461; }
.zero-state h3 { font-size:clamp(1.28rem,2.1vw,1.65rem); color:#174433; line-height:1.27; letter-spacing:-.035em; margin:9px 0 9px; }
.zero-state > p { max-width:510px; margin:0 auto; color:#70887c; line-height:1.65; font-size:.86rem; }
.zero-actions { display:flex; align-items:center; justify-content:center; gap:10px; flex-wrap:wrap; margin-top:21px; }
.exclusion-review { margin-top:27px; border-top:1px solid #e8efeb; padding-top:25px; }
.exclusion-review-head { display:flex; justify-content:space-between; align-items:flex-start; gap:15px; margin-bottom:18px; }
.exclusion-review h3 { margin:6px 0 5px; font-size:1.22rem; color:#1d4838; line-height:1.35; }
.exclusion-review h3 span { display:inline-grid; place-items:center; background:#fff4df; color:#976827; border-radius:99px; padding:2px 9px; font-size:.7rem; vertical-align:middle; }
.exclusion-review-head p { margin:0; color:#81978b; font-size:.8rem; line-height:1.55; }
.exclusion-grid { display:grid; grid-template-columns:minmax(0,1fr); gap:11px; }
.exclusion-card { display:flex; gap:13px; padding:17px; border:1px solid #e2eae4; border-radius:12px; background:#fff; }
.excluded-avatar { flex:0 0 40px; width:40px; height:40px; border:1px solid #dcece0; background:#edf8f1; border-radius:11px; display:grid;place-items:center; font-size:1.2rem; font-weight:850;color:#247250; }
.exclusion-card-copy { min-width:0; flex:1; }
.exclusion-card-title-row { display:flex;align-items:flex-start;justify-content:space-between;gap:9px;flex-wrap:wrap; }
.exclusion-card h4 { margin:1px 0 4px; color:#214c39; font-size:.93rem; line-height:1.4; }
.exclusion-pill { background:#fff4e5;color:#8c6929;border:1px solid #f6e4c7;padding:3px 8px;border-radius:99px;font-size:.64rem;font-weight:820;white-space:nowrap; }
.excluded-program { font-size:.76rem; color:#759184; margin:0 0 12px; line-height:1.5; }
.reason-wrap { display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px; }
.reason-tag { padding:5px 9px; border:1px solid #e9dcca; border-radius:7px; background:#fffbf5; color:#91754b; font-size:.69rem; font-weight:650; }
.exclusion-context { margin:3px 0 9px; color:#7c9185; font-size:.72rem; line-height:1.5; }
.exclusion-context strong { color:#586e60; }
.excluded-detail { display:inline-flex;align-items:center;gap:8px;color:#08815e;font-weight:790;font-size:.76rem; }
.exclusion-loading { font-size:.8rem;color:#839489;background:#f8fbf9;padding:16px;border:1px dashed #dbe7df;border-radius:10px; }
.exclusion-retry { margin-left:10px; color:#087956; background:none; border:0; text-decoration:underline; cursor:pointer; font:inherit; font-weight:750; }
.show-more-excluded { display:flex;align-items:center;justify-content:center;width:100%;margin-top:12px;border:1px solid #cfe6d9;background:#f4fbf7;color:#13805a;padding:13px;border-radius:10px;font:inherit;font-weight:780;font-size:.79rem;cursor:pointer;gap:10px; }
.show-more-excluded:hover { background:#e7f5ec; }
.results-main,.guide-panel,.summary-stat { min-width:0; }
@media (max-width: 1000px) { .results-summary { gap:8px; } .summary-stat { padding:13px; gap:9px; } .summary-stat-icon { width:36px; height:36px; } }
@media (max-width: 740px) { .results-summary { grid-template-columns: repeat(3,minmax(0,1fr)); } .summary-stat { flex-direction:column; align-items:flex-start; } .results-layout { gap:14px; } .guide-panel { padding:20px; } }
@media (max-width: 490px) { .results-summary { gap:7px; } .summary-stat { padding:12px 9px; } .summary-stat-icon { width:28px; height:28px; font-size:.87rem; border-radius:8px; } .summary-stat strong { font-size:1.14rem; } .summary-stat div span { font-size:.64rem; } .zero-state { padding:25px 14px; } .zero-state h3 { font-size:1.26rem; } .exclusion-card { gap:10px; padding:13px; } .excluded-avatar { flex-basis:32px; width:32px; height:32px; font-size:.95rem; } .zero-actions > * { width:100%; } }

@media (max-width: 950px) {
  .results-layout { grid-template-columns: 215px minmax(0,1fr); gap: 14px; }
  .results-main { padding: 21px 17px; }
  .filter-panel { padding: 19px 15px; }
  .result-card { grid-template-columns: minmax(0,1fr) 100px; padding: 16px 13px; }
  .result-card-main { gap: 10px; }
  .uni-monogram { width: 40px; height: 40px; flex-basis: 40px; font-size: 1.1rem; }
  .result-title-row h3 { font-size: .93rem; }
  .fit-ring { width: 75px; height: 75px; }
  .fit-ring > div { width: 60px; height: 60px; }
  .fit-ring strong { font-size: 1.05rem; }
}
@media (max-width: 740px) {
  .results-breadcrumb { padding-bottom: 16px; }
  .results-intro { align-items: flex-start; flex-direction: column; }
  .results-layout { grid-template-columns: minmax(0,1fr); }
  .filter-panel { padding: 15px 18px; }
  .filter-section { padding: 13px 0; }
  .results-main { padding: 21px 15px; }
}
@media (max-width: 440px) {
  .results-intro h1 { font-size: 1.78rem; }
  .intro-actions { width: 100%; }
  .intro-actions > * { flex: 1; }
  .results-main-head { flex-direction: column; gap: 7px; }
  .results-tabs { flex-wrap: nowrap; overflow-x: auto; }
  .results-tabs button { padding: 11px 9px 12px; font-size: .72rem; }
  .result-card { grid-template-columns: minmax(0,1fr); }
  .result-card-side { flex-direction: row; justify-content: space-between; border-top: 1px solid #eef3ef; padding-top: 11px; }
  .result-card-side .detail-button { width: auto; min-width: 138px; }
  .university-place { overflow-wrap: anywhere; }
  .finance-link { margin-left: 0; }
}
/* --------------------------------------------------------------------------
   Full-width shortlist, designed for the wider authenticated application shell.
   Cards stay legible rather than stretching into extremely long text lines.
   -------------------------------------------------------------------------- */
.results-page { width: 100%; min-width: 0; max-width: none; }
.results-breadcrumb { padding-bottom: 17px; }
.results-intro { margin-bottom: 19px; }
.results-intro h1 { font-size: clamp(1.75rem, 2.4vw, 2.4rem); }
.results-summary { gap: 16px; margin-bottom: 18px; }
.results-layout { grid-template-columns: 270px minmax(0, 1fr); gap: 22px; }
.filter-panel { position: sticky; top: 94px; max-height: calc(100vh - 115px); overflow-y: auto; overscroll-behavior: contain; }
.results-main { padding: clamp(19px, 1.7vw, 30px); }
.results-main-head { align-items: center; }
.results-tabs { margin-top: 20px; }
.results-toolbar { margin-bottom: 17px; }
.results-search { max-width: 490px; }
.result-card-list { gap: 16px; }
.result-card {
  grid-template-columns: minmax(0, 1fr) 106px;
  grid-template-rows: 1fr auto;
  gap: 10px 13px;
  padding: 17px;
  border-radius: 13px;
  transition: border-color .16s ease, box-shadow .16s ease;
}
.result-card:hover { box-shadow: 0 7px 25px #0f70471a; }
.result-card-main { gap: 12px; }
.uni-monogram { width: 43px; height: 43px; flex-basis: 43px; border-radius: 11px; font-size: 1.15rem; }
.result-title-row { gap: 9px; }
.result-title-row h3 { font-size: clamp(.95rem, 1.1vw, 1.1rem); line-height: 1.35; }
.result-card-side { gap: 9px; }
.fit-ring { width: 84px; height: 84px; }
.fit-ring > div { width: 67px; height: 67px; }
.fit-ring strong { font-size: 1.16rem; }
.result-card-footer { padding-top: 10px; gap: 8px; }
.card-actions { gap: 7px; }
.card-actions :deep(.btn) { min-height: 33px; }
.results-pager { margin-top: 18px; }
.exclusion-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); }

/* Two-column cards use wide monitors instead of leaving a long central strip. */
@media (min-width: 1540px) {
  .result-card-list { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: stretch; }
  .result-card { grid-template-columns: minmax(0, 1fr) 96px; }
  .result-title-row { align-items: flex-start; }
  .tier-tag { font-size: .66rem; }
  .result-card-info { overflow-wrap: anywhere; }
}

/* The filters move above results on narrower screens, giving programs room. */
@media (max-width: 1090px) {
  .results-layout { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .filter-panel { position: static; max-height: none; overflow: visible; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 24px; }
  .filter-heading { grid-column: 1 / -1; }
  .filter-section { padding: 12px 0; }
  .finance-nudge { grid-column: 1 / -1; }
  .guide-panel { max-width: none; }
  .result-card-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .result-card { grid-template-columns: minmax(0, 1fr) 86px; }
  .fit-ring { width: 73px; height: 73px; }
  .fit-ring > div { width: 59px; height: 59px; }
  .fit-ring strong { font-size: 1.05rem; }
}
@media (max-width: 850px) {
  .result-card-list { grid-template-columns: minmax(0, 1fr); }
  .result-card { grid-template-columns: minmax(0, 1fr) 110px; }
  .fit-ring { width: 84px; height: 84px; }
  .fit-ring > div { width: 67px; height: 67px; }
}
@media (max-width: 610px) {
  .filter-panel { grid-template-columns: minmax(0, 1fr); }
  .results-summary { gap: 8px; }
  .results-main { padding: 16px 13px; }
  .results-intro { gap: 13px; }
  .result-card { grid-template-columns: minmax(0, 1fr); padding: 14px; gap: 12px; }
  .result-card-main { gap: 9px; }
  .result-card-side { flex-direction: row; justify-content: space-between; padding-top: 10px; border-top: 1px solid #edf2ee; }
  .result-card-side .detail-button { max-width: 160px; min-width: 125px; }
  .result-card-footer { padding-top: 11px; }
  .result-title-row { align-items: flex-start; }
  .result-title-row h3 { font-size: .96rem; }
  .uni-monogram { flex-basis: 38px; width: 38px; height: 38px; }
  .result-details p { font-size: .76rem; }
}
@media (prefers-reduced-motion: reduce) { .result-card, .action-primary { transition: none; } }
</style>
