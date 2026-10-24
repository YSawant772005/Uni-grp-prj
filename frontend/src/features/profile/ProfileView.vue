<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { catalog } from '../../services/api/catalog'
import { profile as profileApi } from '../../services/api/account'
import { useAsync } from '../../composables/useAsync'
import { useSavedStore } from '../../stores/saved'
import { useAuthStore } from '../../stores/auth'
import { formatDate, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { Completeness, Country, Profile } from '../../types/api'

const auth = useAuthStore()
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

function pushIf(out: { label: string; value: string }[], label: string, value: string | number | null | undefined, suffix = '') {
  if (value !== null && value !== undefined && value !== '') out.push({ label, value: `${value}${suffix}` })
}

const profileRows = computed(() => {
  const p = profile.value
  if (!p) return [] as { label: string; value: string }[]
  const out: { label: string; value: string }[] = []
  pushIf(out, 'Degree level', p.intended_degree_level ? humanize(p.intended_degree_level) : null)
  pushIf(out, 'Field', p.field_key ? humanize(p.field_key) : null)
  pushIf(out, 'Country mode', p.country_mode ? humanize(p.country_mode) : null)
  pushIf(out, 'Risk tolerance', p.risk_tolerance ? humanize(p.risk_tolerance) : null)
  pushIf(out, 'Academic degree', p.academic_degree)
  pushIf(out, 'Academic major', p.academic_major)
  pushIf(out, 'Institution', p.institution_name)
  if (p.grade_value !== null && p.grade_scale_max !== null) {
    out.push({ label: 'Grade', value: `${p.grade_value} / ${p.grade_scale_max}${p.grade_system ? ` (${humanize(p.grade_system)})` : ''}` })
  }
  pushIf(out, 'Graduation', p.graduation_status ? humanize(p.graduation_status) : null)
  pushIf(out, 'Graduation year', p.graduation_year)
  pushIf(out, 'Backlogs', p.backlog_count)
  if (p.english_test_status) {
    const score = p.english_test_overall !== null ? `, overall ${p.english_test_overall}` : ''
    out.push({ label: 'English test', value: `${humanize(p.english_test_status)}${p.english_test_type ? ` - ${humanize(p.english_test_type)}` : ''}${score}` })
  }
  pushIf(out, 'Work experience', p.work_experience_months, ' months')
  pushIf(out, 'Career goal', p.career_goal)
  if (p.budget_amount !== null && p.budget_currency) {
    out.push({ label: 'Budget', value: `${p.budget_currency} ${p.budget_amount}${p.budget_basis ? ` - ${humanize(p.budget_basis)}` : ''}` })
  }
  if (p.target_intake_year !== null && p.target_intake_term) {
    out.push({ label: 'Target intake', value: `${humanize(p.target_intake_term)} ${p.target_intake_year}` })
  }
  pushIf(out, 'Profile completed', p.profile_completed_at ? formatDate(p.profile_completed_at) : null)
  return out
})

const academicRows = computed(() => profileRows.value.filter((row) => [
  'Academic degree', 'Academic major', 'Institution', 'Grade', 'Graduation', 'Graduation year', 'Backlogs', 'English test',
].includes(row.label)))

const studyRows = computed(() => profileRows.value.filter((row) => [
  'Degree level', 'Field', 'Country mode', 'Risk tolerance', 'Budget', 'Target intake', 'Work experience', 'Career goal',
].includes(row.label)))

const preferences = computed(() => {
  const prefs = [...(profile.value?.country_preferences ?? [])]
  return prefs.sort((a, b) => a.preference_rank - b.preference_rank)
})

const priorities = computed(() => (profile.value?.priorities ?? []).slice().sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)))

const missingRequired = computed(() =>
  (completeness.value?.items ?? []).filter((item) => item.required && !item.complete),
)

const savedCount = computed(() => savedStore.ids.length)
const preferredCount = computed(() => preferences.value.length)
const priorityCount = computed(() => priorities.value.length)
const completionPercent = computed(() => Math.max(0, Math.min(100, Math.round(completeness.value?.percentage ?? 0))))
const completionText = computed(() => completionPercent.value >= 100 ? 'Complete' : 'In progress')
const heroName = computed(() => auth.user?.display_name?.trim() || auth.user?.email?.split('@')[0] || 'Student')
const heroInitial = computed(() => heroName.value.trim().charAt(0).toUpperCase() || 'S')
const desiredDegree = computed(() => {
  const p = profile.value as (Profile & { desired_degree_title?: string | null }) | null
  return p?.desired_degree_title || (p?.intended_degree_level ? humanize(p.intended_degree_level) : 'Master\'s plan')
})
const fieldLabel = computed(() => profile.value?.field_key ? humanize(profile.value.field_key).replace(/\b\w/g, (c) => c.toUpperCase()) : (profile.value?.academic_major || 'Field not selected'))
const profileCompletedOn = computed(() => profile.value?.profile_completed_at ? formatDate(profile.value.profile_completed_at) : 'Not completed yet')
const topCountries = computed(() => preferences.value.slice(0, 3).map((pref) => displayName(pref.country_code)))
</script>

<template>
  <div class="upf-page">
    <section class="upf-hero">
      <div class="upf-hero-copy">
        <div class="upf-eyebrow"><span class="upf-dot" /> YOUR PROFILE SPACE</div>
        <h1>Make your <span>profile</span> feel complete.</h1>
        <p>
          Review your academic background, goals and destinations in one clean place. This refreshed profile is built to feel
          more premium, more animated and easier to scan.
        </p>
        <div class="upf-hero-actions">
          <RouterLink to="/onboarding" class="upf-btn upf-btn-primary">Edit via onboarding wizard <span aria-hidden="true">↗</span></RouterLink>
          <RouterLink to="/shortlist" class="upf-btn upf-btn-secondary">View shortlist <span aria-hidden="true">→</span></RouterLink>
        </div>
      </div>

      <div class="upf-hero-visual" aria-hidden="true">
        <div class="upf-orbit-ring"></div>
        <div class="upf-floating-card upf-main-float">
          <div class="upf-avatar">{{ heroInitial }}</div>
          <strong>{{ heroName }}</strong>
          <span>{{ desiredDegree }}</span>
          <small>{{ fieldLabel }}</small>
          <div class="upf-pill">{{ completionPercent }}% ready</div>
        </div>
        <div class="upf-floating-card upf-mini-float upf-mini-top">
          <strong>{{ preferredCount }}</strong>
          <span>Preferred countries</span>
        </div>
        <div class="upf-floating-card upf-mini-float upf-mini-bottom">
          <strong>{{ savedCount }}</strong>
          <span>Saved programs</span>
        </div>
      </div>
    </section>

    <AsyncState
      :loading="profileState.loading.value"
      :error="profileState.error.value"
      :empty="!profile"
      empty-title="No profile yet"
      empty-hint="Answer a few quick questions to unlock shortlists, costs and matching."
      @retry="profileState.run"
    >
      <template #empty-action>
        <RouterLink to="/onboarding" class="upf-btn upf-btn-primary">Start onboarding</RouterLink>
      </template>

      <div v-if="profile" class="upf-body">
        <div v-if="missingRequired.length" class="upf-alert upf-alert-warn" role="status">
          <div>
            <strong>Finish the missing required details</strong>
            <span>{{ missingRequired.map((item) => item.label).join(', ') }}</span>
          </div>
          <RouterLink to="/onboarding">Complete now →</RouterLink>
        </div>

        <section class="upf-stats" aria-label="Profile highlights">
          <article class="upf-stat-card">
            <div class="upf-stat-icon upf-stat-green">✓</div>
            <strong>{{ completionPercent }}%</strong>
            <span>Profile completion</span>
            <small>{{ completionText }}</small>
          </article>
          <article class="upf-stat-card">
            <div class="upf-stat-icon upf-stat-blue">✦</div>
            <strong>{{ savedCount }}</strong>
            <span>Saved programs</span>
            <small>Ready to revisit</small>
          </article>
          <article class="upf-stat-card">
            <div class="upf-stat-icon upf-stat-mint">⌁</div>
            <strong>{{ preferredCount }}</strong>
            <span>Destination choices</span>
            <small>{{ topCountries.length ? topCountries.join(' · ') : 'No countries selected yet' }}</small>
          </article>
          <article class="upf-stat-card">
            <div class="upf-stat-icon upf-stat-gold">★</div>
            <strong>{{ priorityCount }}</strong>
            <span>Active priorities</span>
            <small>Used in your matching</small>
          </article>
        </section>

        <div class="upf-grid">
          <div class="upf-main-column">
            <section class="upf-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">PROFILE OVERVIEW</div>
                  <h2>Your profile at a glance</h2>
                </div>
                <div class="upf-header-meta">Updated {{ profileCompletedOn }}</div>
              </div>

              <div class="upf-highlight-row">
                <div class="upf-highlight-box">
                  <span class="upf-label">Desired degree</span>
                  <strong>{{ desiredDegree }}</strong>
                </div>
                <div class="upf-highlight-box">
                  <span class="upf-label">Field</span>
                  <strong>{{ fieldLabel }}</strong>
                </div>
                <div class="upf-highlight-box">
                  <span class="upf-label">Top countries</span>
                  <strong>{{ topCountries.length ? topCountries.join(', ') : 'Not selected' }}</strong>
                </div>
              </div>
            </section>

            <section class="upf-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">ACADEMIC FOUNDATION</div>
                  <h2>Your academic details</h2>
                </div>
              </div>
              <dl class="upf-kv-grid">
                <template v-for="row in academicRows" :key="row.label">
                  <div class="upf-kv-card">
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.value }}</dd>
                  </div>
                </template>
              </dl>
            </section>

            <section class="upf-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">STUDY PLAN</div>
                  <h2>Goals, preferences and fit</h2>
                </div>
              </div>
              <dl class="upf-kv-grid upf-kv-grid-compact">
                <template v-for="row in studyRows" :key="row.label">
                  <div class="upf-kv-card">
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.value }}</dd>
                  </div>
                </template>
              </dl>
            </section>
          </div>

          <div class="upf-side-column">
            <section class="upf-panel upf-glass-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">DESTINATIONS</div>
                  <h2>Where you want to study</h2>
                </div>
              </div>

              <p v-if="preferences.length === 0" class="upf-empty-note">
                No destinations selected yet.
                <RouterLink to="/onboarding">Add them in onboarding</RouterLink>.
              </p>

              <div v-else class="upf-chip-list">
                <div v-for="pref in preferences" :key="pref.country_code" class="upf-chip-card">
                  <div>
                    <strong>{{ displayName(pref.country_code) }}</strong>
                    <span>Preference #{{ pref.preference_rank }}</span>
                  </div>
                  <StatusBadge v-if="pref.is_mandatory" status="candidate" label="mandatory" />
                </div>
              </div>
            </section>

            <section class="upf-panel upf-glass-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">PRIORITIES</div>
                  <h2>What matters most</h2>
                </div>
              </div>

              <p v-if="priorities.length === 0" class="upf-empty-note">
                No priorities set yet.
                <RouterLink to="/onboarding">Add them in onboarding</RouterLink>.
              </p>

              <div v-else class="upf-priority-list">
                <div v-for="prio in priorities" :key="prio.key" class="upf-priority-item">
                  <div>
                    <strong>{{ humanize(prio.key) }}</strong>
                    <span>Used when matching programs</span>
                  </div>
                  <b>{{ prio.weight ?? '—' }}/5</b>
                </div>
              </div>
            </section>

            <section class="upf-panel upf-tips-panel">
              <div class="upf-panel-header">
                <div>
                  <div class="upf-section-overline">PROFILE TIPS</div>
                  <h2>Keep this profile strong</h2>
                </div>
              </div>
              <ul class="upf-tip-list">
                <li>Use accurate academic scores for better shortlisting.</li>
                <li>Update your budget and intake before generating a new shortlist.</li>
                <li>Choose destination preferences to improve recommendation quality.</li>
              </ul>
              <RouterLink to="/onboarding" class="upf-btn upf-btn-secondary upf-btn-wide">Refine my profile →</RouterLink>
            </section>
          </div>
        </div>
      </div>
    </AsyncState>
  </div>
</template>

<style scoped>
.upf-page {
  --upf-bg: #f4fbf7;
  --upf-card: #ffffff;
  --upf-card-soft: rgba(255, 255, 255, 0.7);
  --upf-ink: #123a30;
  --upf-ink-soft: #68847a;
  --upf-line: #d7e8de;
  --upf-accent: #0a8b69;
  --upf-accent-dark: #056b51;
  --upf-shadow: 0 18px 45px rgba(22, 76, 56, 0.08);
  width: 100%;
  max-width: none;
  color: var(--upf-ink);
  padding: 10px 0 36px;
}
.upf-page * { box-sizing: border-box; }
.upf-page a { text-decoration: none; }

.upf-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  align-items: center;
  gap: 28px;
  padding: 36px clamp(22px, 3vw, 42px);
  border-radius: 26px;
  border: 1px solid #d3e9de;
  background: linear-gradient(135deg, #ebfbf2 0%, #f8fdf9 48%, #e1f5ea 100%);
  margin-bottom: 22px;
}
.upf-hero::before,
.upf-hero::after {
  content: "";
  position: absolute;
  border-radius: 999px;
  border: 1px solid rgba(17, 157, 113, 0.15);
  pointer-events: none;
}
.upf-hero::before { width: 480px; height: 480px; right: -150px; top: -180px; }
.upf-hero::after { width: 280px; height: 280px; left: -120px; bottom: -120px; }
.upf-eyebrow,
.upf-section-overline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #0a8b69;
}
.upf-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #18b987;
}
.upf-hero-copy {
  position: relative;
  z-index: 1;
}
.upf-hero-copy h1 {
  margin: 14px 0 12px;
  font-size: clamp(2rem, 3.2vw, 3.35rem);
  line-height: 1.05;
  letter-spacing: -0.055em;
  font-weight: 900;
}
.upf-hero-copy h1 span { color: var(--upf-accent); }
.upf-hero-copy p {
  max-width: 650px;
  color: var(--upf-ink-soft);
  line-height: 1.7;
  margin: 0;
  font-size: 1rem;
}
.upf-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}
.upf-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 48px;
  border-radius: 14px;
  padding: 12px 18px;
  font-size: 0.92rem;
  font-weight: 800;
  border: 1px solid transparent;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
.upf-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(9, 113, 84, 0.14);
}
.upf-btn-primary {
  background: linear-gradient(135deg, #0a8b69, #0f7358);
  color: #ffffff !important;
}
.upf-btn-secondary {
  background: #ffffff;
  color: #0c7358 !important;
  border-color: #d5e8de;
}
.upf-btn-wide { width: 100%; }

.upf-hero-visual {
  position: relative;
  min-height: 270px;
}
.upf-orbit-ring {
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  border: 1px dashed rgba(10, 139, 105, 0.25);
  animation: upf-spin 18s linear infinite;
}
.upf-floating-card {
  position: absolute;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(213, 233, 224, 0.95);
  border-radius: 20px;
  box-shadow: var(--upf-shadow);
  backdrop-filter: blur(10px);
}
.upf-main-float {
  left: 50%;
  top: 52%;
  width: min(290px, 80%);
  transform: translate(-50%, -50%);
  padding: 22px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: upf-float-main 6s ease-in-out infinite;
}
.upf-avatar {
  width: 68px;
  height: 68px;
  border-radius: 22px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0a8b69, #19b487);
  color: #ffffff;
  font-size: 1.8rem;
  font-weight: 900;
  box-shadow: 0 16px 30px rgba(10, 139, 105, 0.24);
}
.upf-main-float strong {
  font-size: 1.15rem;
}
.upf-main-float span,
.upf-main-float small {
  color: var(--upf-ink-soft);
}
.upf-pill {
  margin-top: 4px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #e7faf0;
  color: #08755a;
  font-size: 0.78rem;
  font-weight: 800;
}
.upf-mini-float {
  width: 150px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.upf-mini-top {
  right: 2%;
  top: 9%;
  animation: upf-float-side 5.8s ease-in-out infinite;
}
.upf-mini-bottom {
  left: 5%;
  bottom: 9%;
  animation: upf-float-side 6.5s ease-in-out infinite reverse;
}
.upf-mini-float strong { font-size: 1.15rem; }
.upf-mini-float span { color: var(--upf-ink-soft); font-size: 0.8rem; }

.upf-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-radius: 16px;
  margin-bottom: 18px;
}
.upf-alert strong { display: block; margin-bottom: 3px; }
.upf-alert span { color: #8a5f2d; font-size: 0.86rem; }
.upf-alert-warn {
  background: #fff8ec;
  border: 1px solid #f0ddb0;
}
.upf-alert a { color: #8a5f2d !important; font-weight: 800; white-space: nowrap; }

.upf-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 22px;
}
.upf-stat-card {
  position: relative;
  overflow: hidden;
  background: var(--upf-card);
  border: 1px solid var(--upf-line);
  border-radius: 20px;
  padding: 20px;
  min-height: 162px;
  box-shadow: 0 10px 28px rgba(18, 68, 52, 0.06);
  transition: transform 0.18s ease, border-color 0.18s ease;
  animation: upf-soft-bob 7s ease-in-out infinite;
}
.upf-stat-card:nth-child(2) { animation-delay: 0.4s; }
.upf-stat-card:nth-child(3) { animation-delay: 0.9s; }
.upf-stat-card:nth-child(4) { animation-delay: 1.3s; }
.upf-stat-card:hover {
  transform: translateY(-4px);
  border-color: #a9d6bf;
}
.upf-stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-weight: 900;
  font-size: 1.1rem;
  margin-bottom: 16px;
}
.upf-stat-green { background: #e6fbf0; color: #0a8b69; }
.upf-stat-blue { background: #ecf6ff; color: #2f86d9; }
.upf-stat-mint { background: #ebf7f1; color: #29916f; }
.upf-stat-gold { background: #fff5de; color: #b1841e; }
.upf-stat-card strong {
  display: block;
  font-size: 1.95rem;
  line-height: 1.05;
  letter-spacing: -0.05em;
  margin-bottom: 8px;
}
.upf-stat-card span {
  display: block;
  font-weight: 800;
}
.upf-stat-card small {
  display: block;
  margin-top: 8px;
  color: var(--upf-ink-soft);
  line-height: 1.45;
}

.upf-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.8fr);
  gap: 20px;
  align-items: start;
}
.upf-main-column,
.upf-side-column {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.upf-panel {
  background: var(--upf-card);
  border: 1px solid var(--upf-line);
  border-radius: 22px;
  padding: 24px;
  box-shadow: 0 10px 26px rgba(17, 66, 51, 0.05);
}
.upf-glass-panel {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 252, 249, 0.96));
}
.upf-panel-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}
.upf-panel-header h2 {
  margin: 8px 0 0;
  font-size: 1.3rem;
  letter-spacing: -0.03em;
  font-weight: 850;
}
.upf-header-meta {
  color: var(--upf-ink-soft);
  font-size: 0.78rem;
  font-weight: 700;
  white-space: nowrap;
}

.upf-highlight-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.upf-highlight-box {
  border-radius: 18px;
  padding: 18px;
  background: linear-gradient(180deg, #f8fcfa, #eef8f3);
  border: 1px solid #dfede5;
}
.upf-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #699184;
  margin-bottom: 8px;
}
.upf-highlight-box strong {
  font-size: 1rem;
  line-height: 1.5;
}

.upf-kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.upf-kv-grid-compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.upf-kv-card {
  min-width: 0;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #e1ece6;
  background: #fbfefd;
}
.upf-kv-card dt {
  margin: 0 0 8px;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #6d8a7f;
}
.upf-kv-card dd {
  margin: 0;
  color: var(--upf-ink);
  font-size: 0.98rem;
  line-height: 1.55;
  word-break: break-word;
}

.upf-empty-note {
  margin: 0;
  color: var(--upf-ink-soft);
  line-height: 1.6;
}
.upf-empty-note a { color: var(--upf-accent) !important; font-weight: 800; }
.upf-chip-list,
.upf-priority-list {
  display: grid;
  gap: 12px;
}
.upf-chip-card,
.upf-priority-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid #e0ece5;
  border-radius: 16px;
  background: #fbfefd;
}
.upf-chip-card strong,
.upf-priority-item strong {
  display: block;
  margin-bottom: 3px;
}
.upf-chip-card span,
.upf-priority-item span {
  color: var(--upf-ink-soft);
  font-size: 0.83rem;
}
.upf-priority-item b {
  min-width: 56px;
  text-align: center;
  padding: 8px 10px;
  border-radius: 999px;
  background: #e9f8ef;
  color: #0c775c;
  font-size: 0.86rem;
}
.upf-tips-panel {
  background: linear-gradient(160deg, #effbf4, #ffffff);
}
.upf-tip-list {
  margin: 0 0 18px;
  padding-left: 18px;
  color: var(--upf-ink-soft);
}
.upf-tip-list li + li { margin-top: 10px; }

@keyframes upf-float-main {
  0%, 100% { transform: translate(-50%, -50%) translateY(0px); }
  50% { transform: translate(-50%, -50%) translateY(-10px); }
}
@keyframes upf-float-side {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-8px); }
}
@keyframes upf-soft-bob {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-3px); }
}
@keyframes upf-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 1100px) {
  .upf-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .upf-grid { grid-template-columns: 1fr; }
  .upf-side-column { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 820px) {
  .upf-hero { grid-template-columns: 1fr; }
  .upf-hero-visual { min-height: 230px; }
  .upf-highlight-row,
  .upf-kv-grid,
  .upf-kv-grid-compact,
  .upf-side-column { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .upf-hero { padding: 24px 18px; border-radius: 20px; }
  .upf-panel { padding: 18px; border-radius: 18px; }
  .upf-stats { grid-template-columns: 1fr; gap: 12px; }
  .upf-alert, .upf-panel-header, .upf-chip-card, .upf-priority-item { flex-direction: column; align-items: flex-start; }
  .upf-header-meta { white-space: normal; }
  .upf-hero-actions { flex-direction: column; }
  .upf-btn { width: 100%; }
  .upf-main-float { width: min(280px, 86%); }
  .upf-mini-float { width: 132px; }
}
@media (prefers-reduced-motion: reduce) {
  .upf-orbit-ring,
  .upf-main-float,
  .upf-mini-top,
  .upf-mini-bottom,
  .upf-stat-card,
  .upf-btn { animation: none !important; transition: none !important; }
}
</style>
