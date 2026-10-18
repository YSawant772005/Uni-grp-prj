<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { catalog } from '../../services/api/catalog'
import { profile as profileApi } from '../../services/api/account'
import { useAsync } from '../../composables/useAsync'
import { useSavedStore } from '../../stores/saved'
import { formatDate, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { Completeness, Country, Profile } from '../../types/api'

const savedStore = useSavedStore()
onMounted(() => void savedStore.ensureLoaded())

const profileState = useAsync(() => profileApi.get(), { immediate: true })
const completenessState = useAsync(() => profileApi.completeness(), { immediate: true })
const countriesState = useAsync(() => catalog.countries(), { immediate: true })

const profile = computed(() => profileState.data.value)
const completeness = computed<Completeness | null>(() => completenessState.data.value)
const countryName = computed(() => {
  const map = new Map<string, string>()
  for (const country of (countriesState.data.value?.items ?? []) as Country[]) {
    map.set(country.code, country.name)
  }
  return map
})

function displayName(code: string): string {
  return countryName.value.get(code) ?? code
}

/** Non-null profile values as label/value rows, grouped by section. */
function rows(p: Profile | null): { label: string; value: string }[] {
  if (!p) return []
  const out: { label: string; value: string }[] = []
  const push = (label: string, value: string | number | null | undefined, suffix = '') => {
    if (value !== null && value !== undefined && value !== '') out.push({ label, value: `${value}${suffix}` })
  }
  push('Degree level', p.intended_degree_level ? humanize(p.intended_degree_level) : null)
  push('Field', p.field_key ? humanize(p.field_key) : null)
  push('Country mode', p.country_mode ? humanize(p.country_mode) : null)
  push('Risk tolerance', p.risk_tolerance ? humanize(p.risk_tolerance) : null)
  push('Academic degree', p.academic_degree)
  push('Academic major', p.academic_major)
  push('Institution', p.institution_name)
  if (p.grade_value !== null && p.grade_scale_max !== null) {
    out.push({ label: 'Grade', value: `${p.grade_value} / ${p.grade_scale_max}${p.grade_system ? ` (${humanize(p.grade_system)})` : ''}` })
  }
  push('Graduation', p.graduation_status ? humanize(p.graduation_status) : null)
  push('Graduation year', p.graduation_year)
  push('Backlogs', p.backlog_count)
  if (p.english_test_status) {
    const score = p.english_test_overall !== null ? `, overall ${p.english_test_overall}` : ''
    out.push({ label: 'English test', value: `${humanize(p.english_test_status)}${p.english_test_type ? ` - ${humanize(p.english_test_type)}` : ''}${score}` })
  }
  push('Work experience', p.work_experience_months, ' months')
  push('Career goal', p.career_goal)
  if (p.budget_amount !== null && p.budget_currency) {
    out.push({ label: 'Budget', value: `${p.budget_currency} ${p.budget_amount}${p.budget_basis ? ` - ${humanize(p.budget_basis)}` : ''}` })
  }
  if (p.target_intake_year !== null && p.target_intake_term) {
    out.push({ label: 'Target intake', value: `${humanize(p.target_intake_term)} ${p.target_intake_year}` })
  }
  push('Profile completed', p.profile_completed_at ? formatDate(p.profile_completed_at) : null)
  return out
}

const profileRows = computed(() => rows(profile.value))

const preferences = computed(() => {
  const prefs = [...(profile.value?.country_preferences ?? [])]
  return prefs.sort((a, b) => a.preference_rank - b.preference_rank)
})

const priorities = computed(() => (profile.value?.priorities ?? []).slice().sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)))

const missingRequired = computed(() =>
  (completeness.value?.items ?? []).filter((item) => item.required && !item.complete),
)
</script>

<template>
  <div class="stack">
    <div class="row-between">
      <div>
        <h1>Your profile</h1>
        <p class="muted small" style="margin: 0">
          The answers below drive eligibility checks, cost estimates and shortlist quality. Edit
          anything by resuming the onboarding wizard.
        </p>
      </div>
      <RouterLink to="/onboarding" class="btn btn-primary">Edit via onboarding wizard</RouterLink>
    </div>

    <AsyncState
      :loading="profileState.loading.value"
      :error="profileState.error.value"
      :empty="!profile"
      empty-title="No profile yet"
      empty-hint="Answer eight quick questions to unlock shortlists, costs and matching."
      @retry="profileState.run"
    >
      <template #empty-action>
        <RouterLink to="/onboarding" class="btn btn-primary">Start onboarding</RouterLink>
      </template>

      <div v-if="profile" class="stack">
        <!-- completeness -->
        <section class="card" aria-labelledby="completeness-heading">
          <div class="row-between">
            <h2 id="completeness-heading">Profile completeness</h2>
            <strong v-if="completeness">{{ completeness.percentage }}%</strong>
          </div>
          <div class="progress-track" role="img" :aria-label="`Profile ${completeness?.percentage ?? 0} percent complete`">
            <div class="progress-fill" :style="{ width: `${completeness?.percentage ?? 0}%` }" />
          </div>
          <p v-if="missingRequired.length" class="small" style="margin: 8px 0 0">
            Missing required:
            {{ missingRequired.map((item) => item.label).join(', ') }} -
            <RouterLink to="/onboarding">finish onboarding</RouterLink>
          </p>
          <p v-else class="small" style="margin: 8px 0 0; color: var(--ok)">
            All required answers are complete.
          </p>
        </section>

        <div class="grid-2">
          <section class="card">
            <h2>Answers</h2>
            <dl class="kv">
              <template v-for="row in profileRows" :key="row.label">
                <dt>{{ row.label }}</dt>
                <dd>{{ row.value }}</dd>
              </template>
            </dl>
          </section>

          <div class="stack">
            <section class="card">
              <h2>Destination preferences</h2>
              <p v-if="preferences.length === 0" class="muted small" style="margin: 0">
                No destinations set -
                <RouterLink to="/onboarding">add them in onboarding</RouterLink>.
              </p>
              <ol v-else class="stack-sm" style="padding-left: 18px; margin: 0">
                <li v-for="pref in preferences" :key="pref.country_code">
                  {{ displayName(pref.country_code) }}
                  <StatusBadge v-if="pref.is_mandatory" status="candidate" label="mandatory" />
                </li>
              </ol>
            </section>

            <section class="card">
              <h2>Priorities</h2>
              <p v-if="priorities.length === 0" class="muted small" style="margin: 0">
                No priorities set (optional) - add them via
                <RouterLink to="/onboarding">onboarding</RouterLink>.
              </p>
              <dl v-else class="kv">
                <template v-for="prio in priorities" :key="prio.key">
                  <dt>{{ humanize(prio.key) }}</dt>
                  <dd>weight {{ prio.weight ?? 'unset' }} / 5</dd>
                </template>
              </dl>
            </section>
          </div>
        </div>
      </div>
    </AsyncState>
  </div>
</template>
