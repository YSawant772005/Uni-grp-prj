<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { formatDate, formatNumber, formatValue, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import CompareToggle from '../../components/CompareToggle.vue'
import SaveToggle from '../../components/SaveToggle.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { ExplanationEntry, RecommendationItem, TierKey } from '../../types/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const runId = computed(() => String(route.params.runId))

const runState = useAsync(() => recommendations.getRun(runId.value), { immediate: true })
const explanationsState = useAsync(() => recommendations.explanations(runId.value), { immediate: true })

const run = computed(() => runState.data.value)
const explanationItems = computed(() => explanationsState.data.value?.items ?? [])

/** Merge run tiers (authoritative membership) with explanation details; the
 * page still renders tiers when only the explanations call failed. */
const mergedItems = computed(() => {
  const byProgram = new Map<string, RecommendationItem | ExplanationEntry>()
  for (const tier of ['ambitious', 'target', 'safer_fit'] as TierKey[]) {
    for (const item of run.value?.tiers[tier] ?? []) byProgram.set(item.program_id, item)
  }
  for (const item of explanationItems.value) byProgram.set(item.program_id, item)
  return [...byProgram.values()]
})

const TIERS: { key: TierKey; title: string; description: string }[] = [
  {
    key: 'ambitious',
    title: 'Ambitious',
    description:
      'Programmes that stretch your profile - your numbers sit below some published thresholds. Worth aiming at, with realistic alternatives alongside.',
  },
  {
    key: 'target',
    title: 'Target',
    description:
      'Programmes where your profile aligns well with published requirements and your stated preferences.',
  },
  {
    key: 'safer_fit',
    title: 'Safer-fit',
    description:
      'Programmes where you comfortably clear published requirements. Lower academic risk - still verify every requirement before applying.',
  },
]

const tierFilter = ref<'all' | TierKey>('all')

function itemsFor(tier: TierKey): (RecommendationItem | ExplanationEntry)[] {
  return mergedItems.value.filter((item) => item.tier === tier)
}

const excluded = computed(() => mergedItems.value.filter((item) => item.tier === null))

const visibleTiers = computed(() =>
  TIERS.filter((tier) => tierFilter.value === 'all' || tierFilter.value === tier.key),
)

function explainItem(item: RecommendationItem | ExplanationEntry): ExplanationEntry | null {
  return 'why' in item ? item : null
}

// --------------------------------------------------------------------- re-run

const rerunning = ref(false)

async function rerun() {
  if (rerunning.value) return
  rerunning.value = true
  try {
    const newRun = await recommendations.createRun()
    ui.push('New run generated - this run stays available in your history.', 'success')
    void router.push(`/shortlist/${newRun.run_id}`)
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    ui.pushError(err)
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
    empty-title="Run not found"
    empty-hint="It may belong to another account, or the link is out of date."
    @retry="runState.run"
  >
    <template #empty-action>
      <RouterLink to="/shortlist" class="btn">Back to your shortlists</RouterLink>
    </template>

    <div v-if="run" class="stack">
      <div class="row-between">
        <div>
          <h1 style="margin-bottom: 2px">Shortlist run</h1>
          <p class="muted small" style="margin: 0">
            {{ formatDate(run.created_at) }} · ruleset {{ run.ruleset_version ?? 'unknown' }} ·
            status {{ humanize(run.status) }}
          </p>
        </div>
        <button class="btn btn-primary" type="button" :disabled="rerunning" @click="rerun">
          {{ rerunning ? 'Generating…' : 'Re-run with current profile' }}
        </button>
      </div>

      <div class="banner banner-info">
        <strong>How to read this:</strong> tiers compare your profile to published requirements and
        your preferences - they are a fit heuristic, <em>not</em> an admission probability. Eligibility
        status is a requirement-level check; the fit score is a separate weighted preference score.
        Both can disagree, and that is useful information.
      </div>

      <div v-if="run.data_warnings.length" class="banner banner-warn" role="status">
        <strong>Data warnings</strong>
        <ul style="margin: 4px 0 0; padding-left: 18px">
          <li v-for="warning in run.data_warnings" :key="warning" class="small">{{ warning }}</li>
        </ul>
      </div>

      <!-- tier filter -->
      <div class="tabs" role="tablist" aria-label="Filter tiers">
        <button type="button" role="tab" :aria-selected="tierFilter === 'all'" @click="tierFilter = 'all'">
          All tiers
        </button>
        <button
          v-for="tier in TIERS"
          :key="tier.key"
          type="button"
          role="tab"
          :aria-selected="tierFilter === tier.key"
          @click="tierFilter = tier.key"
        >
          {{ tier.title }} ({{ run.result_summary?.[tier.key] ?? itemsFor(tier.key).length }})
        </button>
      </div>

      <!-- tiers -->
      <section v-for="tier in visibleTiers" :key="tier.key" class="stack">
        <div class="card-flat">
          <h2>{{ tier.title }}</h2>
          <p class="muted small" style="margin: 0">{{ tier.description }}</p>
        </div>

        <div v-if="itemsFor(tier.key).length === 0" class="state-block">
          <p class="state-title">No programmes in this tier for this run</p>
          <p class="small">Try re-running after updating your profile or relaxing destination constraints.</p>
        </div>

        <article v-for="item in itemsFor(tier.key)" :key="item.id" class="card stack-sm">
          <div class="row-between">
            <RouterLink :to="`/programs/${item.program_id}`">
              <h3 style="margin: 0">{{ item.program_name ?? 'Program' }}</h3>
            </RouterLink>
            <StatusBadge :status="item.eligibility_status" />
          </div>
          <p class="small muted" style="margin: 0">
            {{ item.university }} · {{ item.country_code }}
          </p>
          <div class="row">
            <span class="small">
              <strong>Fit score:</strong>
              <template v-if="item.fit_score !== null">
                {{ formatNumber(item.fit_score, 2) }} / 1.00
                <span class="score-bar" style="display: inline-block; vertical-align: middle">
                  <span :style="{ width: `${Math.round((item.fit_score ?? 0) * 100)}%` }" />
                </span>
              </template>
              <span v-else class="muted">Not available (missing inputs)</span>
            </span>
          </div>

          <ul v-if="item.reason_codes.length" class="small" style="margin: 0; padding-left: 18px">
            <li v-for="reason in item.reason_codes" :key="reason">{{ humanize(reason) }}</li>
          </ul>
          <div v-if="item.concerns.length" class="row">
            <span v-for="concern in item.concerns" :key="concern" class="badge badge-warn">
              concern: {{ humanize(concern) }}
            </span>
          </div>
          <div v-if="item.missing_information.length" class="row">
            <span v-for="missing in item.missing_information" :key="missing" class="badge badge-info">
              missing: {{ humanize(missing) }}
            </span>
          </div>

          <!-- full explanation (present when explanations endpoint was used) -->
          <details v-if="explainItem(item)" class="card card-flat">
            <summary style="cursor: pointer"><strong>Why this result?</strong> - dimensions, weights and requirement checks</summary>
            <div v-if="explainItem(item)?.score_breakdown?.length" class="stack-sm" style="margin-top: 10px">
              <div class="table-wrap">
                <table class="data">
                  <thead>
                    <tr>
                      <th>Dimension</th>
                      <th>Weight</th>
                      <th>Score</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="entry in explainItem(item)?.score_breakdown" :key="entry.dimension">
                      <td>{{ humanize(entry.dimension) }}</td>
                      <td>{{ formatNumber(entry.weight, 2) }}</td>
                      <td>
                        <template v-if="entry.score !== null">{{ formatNumber(entry.score, 2) }}</template>
                        <span v-else class="muted">Not scored</span>
                      </td>
                      <td class="small">{{ entry.note ?? '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-if="explainItem(item)?.why" class="small muted" style="margin: 0">
                Hard-constraint status:
                <strong>{{ explainItem(item)?.why?.hard_constraint_status }}</strong>
              </p>
            </div>
            <div v-if="explainItem(item)?.why?.requirement_outcomes?.length" style="margin-top: 10px">
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
                    <tr v-for="outcome in explainItem(item)?.why?.requirement_outcomes" :key="outcome.requirement_id">
                      <td class="mono small">{{ outcome.requirement_id.slice(0, 8) }}…</td>
                      <td class="mono small">{{ formatValue(outcome.expected) }}</td>
                      <td class="mono small">{{ formatValue(outcome.applicant_value) }}</td>
                      <td><StatusBadge :status="outcome.status" /></td>
                      <td class="small">{{ outcome.explanation ?? '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </details>

          <div class="row">
            <SaveToggle :program-id="item.program_id" />
            <CompareToggle :program-id="item.program_id" :label="item.program_name ?? undefined" />
            <RouterLink class="btn btn-sm" :to="`/programs/${item.program_id}`">Open detail</RouterLink>
            <RouterLink class="btn btn-sm btn-quiet" :to="`/finance?program=${item.program_id}`">Costs</RouterLink>
          </div>
        </article>
      </section>

      <!-- excluded -->
      <section v-if="excluded.length" class="stack">
        <div class="card-flat">
          <h2>Excluded by hard constraints ({{ excluded.length }})</h2>
          <p class="muted small" style="margin: 0">
            These programmes were filtered out before scoring because a mandatory constraint (country,
            budget or a published hard requirement) could not be met. The reason codes explain why -
            fixing the underlying input can change this on the next run.
          </p>
        </div>
        <article v-for="item in excluded" :key="item.id" class="card card-flat">
          <div class="row-between">
            <RouterLink :to="`/programs/${item.program_id}`">
              <strong>{{ item.program_name ?? 'Program' }}</strong>
            </RouterLink>
            <span class="badge badge-danger">excluded</span>
          </div>
          <ul class="small" style="margin: 6px 0 0; padding-left: 18px">
            <li v-for="reason in item.reason_codes" :key="reason">{{ humanize(reason) }}</li>
          </ul>
        </article>
      </section>

      <p v-if="!auth.isAuthenticated" class="small muted">
        This run was created in your session - <RouterLink to="/login">log in</RouterLink> from another
        device to see it again.
      </p>
    </div>
  </AsyncState>
</template>
