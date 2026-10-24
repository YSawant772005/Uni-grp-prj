<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useCompareStore } from '../../stores/compare'
import { profile as profileApi, recommendations, library } from '../../services/api/account'
import { errorMessage } from '../../services/api/client'
import { formatDate, formatMoney, humanize } from '../../utils/format'
import type { Completeness, Profile, RunListItem, SavedProgram } from '../../types/api'

import DashboardCampus3D from './DashboardCampus3D.vue'

const auth = useAuthStore()
const compare = useCompareStore()
const loading = ref(true)
const refreshing = ref(false)
const profile = ref<Profile | null>(null)
const completeness = ref<Completeness | null>(null)
const runs = ref<RunListItem[]>([])
const saved = ref<SavedProgram[]>([])
const errors = ref<string[]>([])

async function load() {
  if (loading.value === false && refreshing.value) return
  refreshing.value = true
  const [profileResult, completenessResult, runsResult, savedResult] = await Promise.allSettled([
    profileApi.get(),
    profileApi.completeness(),
    recommendations.listRuns(),
    library.saved(),
  ] as const)
  const nextErrors: string[] = []
  if (profileResult.status === 'fulfilled') profile.value = profileResult.value
  else nextErrors.push(`Profile: ${errorMessage(profileResult.reason)}`)
  if (completenessResult.status === 'fulfilled') completeness.value = completenessResult.value
  else nextErrors.push(`Progress: ${errorMessage(completenessResult.reason)}`)
  if (runsResult.status === 'fulfilled') runs.value = runsResult.value.items ?? []
  else nextErrors.push(`Shortlists: ${errorMessage(runsResult.reason)}`)
  if (savedResult.status === 'fulfilled') saved.value = savedResult.value.items ?? []
  else nextErrors.push(`Saved programs: ${errorMessage(savedResult.reason)}`)
  errors.value = nextErrors
  loading.value = false
  refreshing.value = false
}

onMounted(() => { void load() })

const firstName = computed(() => {
  const name = auth.user?.display_name?.trim() || auth.user?.email?.split('@')[0] || 'student'
  return name.split(/[\s._-]+/)[0] || 'student'
})
const profilePercentage = computed(() => {
  const n = completeness.value?.percentage
  return typeof n === 'number' && Number.isFinite(n) ? Math.min(100, Math.max(0, Math.round(n))) : null
})
const profileReady = computed(() => Boolean(completeness.value?.required_complete))
const lastRun = computed(() => runs.value[0] ?? null)
const runTotal = (run: RunListItem | null) => {
  if (!run?.result_summary) return null
  return Object.values(run.result_summary).reduce<number>((sum, count) => sum + (typeof count === 'number' ? count : 0), 0)
}
const matchedTotal = computed(() => runTotal(lastRun.value))
const missingItems = computed(() => (completeness.value?.items ?? []).filter(item => item.required && !item.complete).slice(0, 3))
const preferredCountries = computed(() => (profile.value?.country_preferences ?? []).slice().sort((a,b) => a.preference_rank - b.preference_rank))
const degreeName = computed(() => {
  // `desired_degree_title` was added to Profile by the exact-match patch;
  // older profiles use just the level. Keep both API versions compatible.
  const p = profile.value as (Profile & { desired_degree_title?: string | null }) | null
  return p?.desired_degree_title || (p?.intended_degree_level ? humanize(p.intended_degree_level) : 'Not selected')
})
const fieldName = computed(() => profile.value?.field_key ? humanize(profile.value.field_key).replace(/\b\w/g, c => c.toUpperCase()) : 'Not selected')
const budget = computed(() => {
  const p = profile.value
  return p?.budget_amount != null ? formatMoney(p.budget_amount, p.budget_currency) : 'Not set'
})
const intake = computed(() => {
  const p = profile.value
  return p?.target_intake_year && p.target_intake_term ? `${humanize(p.target_intake_term)} ${p.target_intake_year}` : 'Not selected'
})
const nextAction = computed(() => {
  if (!profileReady.value) return { label: 'Complete your profile', to: '/onboarding', description: 'Tell us your goals so your shortlist can match the degree and specialization you want.' }
  if (!runs.value.length) return { label: 'Generate your shortlist', to: '/shortlist', description: 'Your profile is ready. Generate your first personalized university shortlist.' }
  return { label: 'View latest shortlist', to: `/shortlist/${lastRun.value?.run_id}`, description: 'Your shortlist is ready. Compare options or refine your profile to explore more programs.' }
})

function countryName(code: string) {
  try { return new Intl.DisplayNames(['en'], { type: 'region' }).of(code.toUpperCase()) ?? code }
  catch { return code }
}
</script>

<template>
  <div class="uds-dashboard" aria-label="Student dashboard">
    <div class="uds-eyebrow"><span class="uds-dot"/> YOUR STUDY ABROAD WORKSPACE</div>
    <section class="uds-hero" aria-labelledby="uds-title">
      <div class="uds-hero-main">
        <span class="uds-welcome">STUDENT DASHBOARD</span>
        <h1 id="uds-title">Welcome back, <span>{{ firstName }}.</span></h1>
        <p>Everything you need for your Master's journey, organized in one place. Pick up exactly where you left off.</p>
        <div class="uds-hero-pills" aria-label="Workspace status">
          <span class="uds-hero-pill"><b aria-hidden="true"></b>{{ profileReady ? 'Profile ready' : 'Profile in progress' }}</span>
          <span class="uds-hero-pill"><b aria-hidden="true"></b>{{ runs.length ? 'Your shortlist is ready' : 'Recommendations when you are ready' }}</span>
        </div>
        <div class="uds-hero-actions">
          <RouterLink class="uds-button uds-button-main" :to="nextAction.to">{{ nextAction.label }} <span aria-hidden="true">↗</span></RouterLink>
          <RouterLink class="uds-button uds-button-light" to="/discover">Explore programs <span aria-hidden="true">→</span></RouterLink>
        </div>
      </div>
      <div class="uds-hero-aside">
        <DashboardCampus3D />
        <div class="uds-hero-note"><strong>Your next step</strong><span>{{ nextAction.description }}</span></div>
      </div>
    </section>

    <div v-if="errors.length" class="uds-alert" role="status">
      <div><strong>Some dashboard information couldn't load.</strong><span>{{ errors.join(' · ') }}</span></div>
      <button type="button" class="uds-link-button" :disabled="refreshing" @click="load">{{ refreshing ? 'Retrying…' : 'Retry' }}</button>
    </div>

    <section class="uds-stats" aria-label="Your progress at a glance">
      <RouterLink to="/profile" class="uds-stat">
        <span class="uds-stat-top"><span class="uds-stat-icon uds-icon-green" aria-hidden="true">✓</span><span class="uds-stat-arrow" aria-hidden="true">↗</span></span>
        <strong>{{ profilePercentage === null ? '—' : `${profilePercentage}%` }}</strong>
        <span>Profile completed</span>
        <div class="uds-mini-progress" aria-hidden="true"><i :style="{ width: `${profilePercentage ?? 0}%` }" /></div>
      </RouterLink>
      <RouterLink to="/shortlist" class="uds-stat">
        <span class="uds-stat-top"><span class="uds-stat-icon uds-icon-mint" aria-hidden="true">▦</span><span class="uds-stat-arrow" aria-hidden="true">↗</span></span>
        <strong>{{ matchedTotal === null ? '—' : matchedTotal }}</strong>
        <span>Latest shortlisted programs</span>
        <small>{{ runs.length ? `${runs.length} shortlist run${runs.length === 1 ? '' : 's'}` : 'No shortlist generated yet' }}</small>
      </RouterLink>
      <RouterLink to="/saved" class="uds-stat">
        <span class="uds-stat-top"><span class="uds-stat-icon uds-icon-lime" aria-hidden="true">♡</span><span class="uds-stat-arrow" aria-hidden="true">↗</span></span>
        <strong>{{ loading ? '—' : saved.length }}</strong>
        <span>Saved programs</span>
        <small>Keep your favorites in one place</small>
      </RouterLink>
      <RouterLink to="/compare" class="uds-stat">
        <span class="uds-stat-top"><span class="uds-stat-icon uds-icon-cream" aria-hidden="true">⇄</span><span class="uds-stat-arrow" aria-hidden="true">↗</span></span>
        <strong>{{ compare.count }}</strong>
        <span>Ready to compare</span>
        <small>Compare up to 6 programs</small>
      </RouterLink>
    </section>

    <div class="uds-columns">
      <div class="uds-main-column">
        <section class="uds-panel uds-progress-panel">
          <div class="uds-panel-header">
            <div><div class="uds-section-overline">YOUR JOURNEY</div><h2>Keep your application moving</h2></div>
            <RouterLink to="/onboarding" class="uds-panel-link">Edit profile <span aria-hidden="true">↗</span></RouterLink>
          </div>
          <div class="uds-step-list">
            <div class="uds-step" :class="{ 'uds-step-done': profileReady }">
              <span class="uds-step-index">{{ profileReady ? '✓' : '01' }}</span>
              <div><strong>Build your student profile</strong><span>{{ profileReady ? 'Your required details are complete.' : 'Add your academic background, degree, specialization and preferences.' }}</span></div>
              <RouterLink :to="profileReady ? '/profile' : '/onboarding'">{{ profileReady ? 'View' : 'Continue' }} →</RouterLink>
            </div>
            <div class="uds-step" :class="{ 'uds-step-done': runs.length > 0 }">
              <span class="uds-step-index">{{ runs.length ? '✓' : '02' }}</span>
              <div><strong>Generate a personalized shortlist</strong><span>{{ runs.length ? 'Your recommendations have been generated.' : 'Get matching programs based on your actual study goals.' }}</span></div>
              <RouterLink to="/shortlist">{{ runs.length ? 'View' : 'Start' }} →</RouterLink>
            </div>
            <div class="uds-step" :class="{ 'uds-step-done': saved.length > 0 }">
              <span class="uds-step-index">{{ saved.length ? '✓' : '03' }}</span>
              <div><strong>Save and compare your favorites</strong><span>{{ saved.length ? `${saved.length} saved program${saved.length === 1 ? '' : 's'} so far.` : 'Shortlist your favorite options and compare the details.' }}</span></div>
              <RouterLink :to="saved.length ? '/saved' : '/discover'">{{ saved.length ? 'Open' : 'Explore' }} →</RouterLink>
            </div>
          </div>
          <p v-if="missingItems.length" class="uds-missing">To complete your profile: {{ missingItems.map(item => item.label).join(' · ') }}.</p>
        </section>

        <section class="uds-panel uds-history">
          <div class="uds-panel-header"><div><div class="uds-section-overline">YOUR RESULTS</div><h2>Recent shortlists</h2></div><RouterLink to="/shortlist" class="uds-panel-link">View all <span aria-hidden="true">→</span></RouterLink></div>
          <div v-if="!runs.length" class="uds-empty"><span class="uds-empty-illustration" aria-hidden="true">▤</span><strong>No shortlists yet</strong><p>Once you've completed your profile, you'll find your recommendation history here.</p><RouterLink class="uds-button uds-button-outline" to="/shortlist">Go to shortlists →</RouterLink></div>
          <div v-else class="uds-history-list">
            <RouterLink v-for="run in runs.slice(0,3)" :key="run.run_id" :to="`/shortlist/${run.run_id}`" class="uds-history-item">
              <span class="uds-run-mark" aria-hidden="true">↗</span>
              <span class="uds-run-info"><strong>University shortlist</strong><small>{{ formatDate(run.created_at) || 'Date unavailable' }} · {{ humanize(run.status) }}</small></span>
              <span class="uds-run-count">{{ runTotal(run) ?? '—' }} <small>matches</small></span><span class="uds-run-arrow" aria-hidden="true">→</span>
            </RouterLink>
          </div>
        </section>

        <section class="uds-panel uds-saved">
          <div class="uds-panel-header"><div><div class="uds-section-overline">BOOKMARKED</div><h2>Saved programs</h2></div><RouterLink to="/saved" class="uds-panel-link">See saved <span aria-hidden="true">→</span></RouterLink></div>
          <div v-if="!saved.length" class="uds-saved-empty"><span aria-hidden="true">♡</span><div><strong>No saved programs yet</strong><p>Browse programs and save the ones you want to revisit.</p></div><RouterLink to="/discover" class="uds-button uds-button-outline">Discover →</RouterLink></div>
          <div v-else class="uds-saved-list"><RouterLink v-for="item in saved.slice(0,3)" :key="item.program_id" :to="`/programs/${item.program_id}`" class="uds-saved-item"><span class="uds-saved-initial" aria-hidden="true">U</span><span><strong>{{ item.program.name }}</strong><small>{{ item.program.university.name }} · {{ countryName(item.program.country_code) }}</small></span><span class="uds-run-arrow" aria-hidden="true">→</span></RouterLink></div>
        </section>
      </div>

      <aside class="uds-side-column" aria-label="Study plan and useful actions">
        <section class="uds-panel uds-plan">
          <div class="uds-section-overline">AT A GLANCE</div><h2>Your study plan</h2>
          <div class="uds-plan-entry"><span>Target degree</span><strong>{{ degreeName }}</strong></div>
          <div class="uds-plan-entry"><span>Specialization</span><strong>{{ fieldName }}</strong></div>
          <div class="uds-plan-entry"><span>Preferred destinations</span><strong>{{ preferredCountries.length ? preferredCountries.slice(0, 3).map(country => countryName(country.country_code)).join(', ') + (preferredCountries.length > 3 ? ` +${preferredCountries.length - 3}` : '') : 'Not selected' }}</strong></div>
          <div class="uds-plan-entry"><span>Study budget</span><strong>{{ budget }}</strong></div>
          <div class="uds-plan-entry"><span>Target intake</span><strong>{{ intake }}</strong></div>
          <RouterLink to="/onboarding" class="uds-button uds-button-outline uds-full">Update study preferences <span aria-hidden="true">↗</span></RouterLink>
        </section>
        <section class="uds-panel uds-tools"><div class="uds-section-overline">QUICK ACCESS</div><h2>Plan your next move</h2><RouterLink to="/discover"><span class="uds-tool-icon" aria-hidden="true">⌕</span><span>Discover universities<small>Find programs for your goals</small></span><b aria-hidden="true">↗</b></RouterLink><RouterLink to="/finance"><span class="uds-tool-icon" aria-hidden="true">₹</span><span>Calculate study costs<small>Plan tuition and living expenses</small></span><b aria-hidden="true">↗</b></RouterLink><RouterLink to="/compare"><span class="uds-tool-icon" aria-hidden="true">⇄</span><span>Compare programs<small>See options side by side</small></span><b aria-hidden="true">↗</b></RouterLink><RouterLink to="/destinations"><span class="uds-tool-icon" aria-hidden="true">◈</span><span>Explore destinations<small>Research study countries</small></span><b aria-hidden="true">↗</b></RouterLink></section>
        <div class="uds-disclaimer"><span aria-hidden="true">✦</span><div><strong>Decisions backed by evidence</strong><p>Fit scores help you compare programs; they do not predict admission. Verify university details before applying.</p></div></div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.uds-dashboard{--uds-ink:#123e34;--uds-muted:#718c83;--uds-line:#dcebe4;--uds-green:#087d5a;--uds-bg:#eff8f3;color:var(--uds-ink);width:100%;max-width:none;padding:6px 0 32px;font-family:inherit}
.uds-dashboard *{box-sizing:border-box}.uds-dashboard a{text-decoration:none}.uds-eyebrow,.uds-section-overline,.uds-welcome{font-size:.68rem;letter-spacing:.125em;font-weight:850;color:#078767}.uds-eyebrow{display:flex;align-items:center;gap:9px;margin-bottom:14px}.uds-dot{width:7px;height:7px;border-radius:50%;background:#1eb68d}
.uds-hero{position:relative;overflow:hidden;display:flex;justify-content:space-between;align-items:center;gap:24px;background:linear-gradient(118deg,#e5f7ef 0%,#f3fcf7 57%,#e3f4eb 100%);border:1px solid #d5ebe0;border-radius:21px;padding:38px clamp(24px,3.3vw,54px);min-height:270px;margin-bottom:22px}
.uds-hero:after{content:"";position:absolute;right:-85px;top:-150px;width:440px;height:440px;border:1px solid #b6e2cb;border-radius:50%;pointer-events:none}.uds-hero-main{position:relative;z-index:2;max-width:690px}.uds-welcome{display:block;margin-bottom:14px}.uds-hero h1{font-size:clamp(1.85rem,3vw,2.9rem);font-weight:880;letter-spacing:-.055em;line-height:1.13;margin:0 0 14px;color:#153d32}.uds-hero h1 span{color:#008867}.uds-hero p{max-width:570px;margin:0;color:#617f73;font-size:1rem;line-height:1.65}.uds-hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:25px}.uds-button{display:inline-flex;align-items:center;justify-content:center;gap:20px;border:1px solid transparent;border-radius:11px;padding:11px 18px;font-weight:800;font-size:.85rem;transition:transform .16s,background .16s,color .16s;white-space:nowrap}.uds-button:hover{transform:translateY(-2px)}.uds-button-main{background:#078663;color:#fff!important;box-shadow:0 10px 20px #087d5a26}.uds-button-main:hover{background:#066e51}.uds-button-light{background:#fff;color:#0c634e!important;border-color:#d5e9df}.uds-button-outline{background:#fff;color:#08785a!important;border-color:#cce3d6}.uds-full{width:100%;justify-content:space-between}.uds-hero-aside{position:relative;z-index:1;flex:0 0 265px;display:flex;align-items:center;flex-direction:column;gap:12px}.uds-orbit{display:grid;place-items:center;width:132px;height:132px;border:2px solid #b6decb;border-radius:50%;position:relative}.uds-orbit:before{content:"";position:absolute;inset:13px;border-radius:50%;border:1px dashed #8fd4b3}.uds-orbit span{display:grid;place-items:center;width:66px;height:66px;border-radius:19px;background:linear-gradient(135deg,#008c67,#0a654c);color:white;font-size:2.1rem;font-weight:950;box-shadow:0 13px 27px #056b4c37}.uds-orbit i{position:absolute;width:14px;height:14px;background:#20bd88;border-radius:50%}.uds-orbit-one{top:13px;left:12px}.uds-orbit-two{right:-6px;bottom:35px;background:#f2bd69!important}.uds-hero-note{display:flex;flex-direction:column;gap:4px;background:#ffffffd9;border:1px solid #d4e9de;box-shadow:0 6px 17px #0b59370b;border-radius:12px;padding:12px 15px;width:100%}.uds-hero-note strong{font-size:.78rem}.uds-hero-note span{font-size:.73rem;line-height:1.4;color:#6e887d}
.uds-alert{display:flex;justify-content:space-between;gap:15px;align-items:center;border:1px solid #eed8a2;background:#fffaf0;color:#7f5715;padding:13px 16px;border-radius:12px;margin-bottom:20px}.uds-alert>div{display:flex;flex-direction:column;gap:3px;font-size:.8rem}.uds-alert strong{font-size:.85rem}.uds-link-button{background:transparent;border:0;color:#91661e;cursor:pointer;text-decoration:underline;font-weight:800}
.uds-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:22px}.uds-stat{background:#fff;border:1px solid var(--uds-line);border-radius:16px;padding:21px 22px;color:var(--uds-ink)!important;box-shadow:0 5px 18px #205b4029;display:flex;flex-direction:column;min-height:183px;transition:transform .15s,border-color .15s}.uds-stat:hover{transform:translateY(-3px);border-color:#9bcfb5}.uds-stat-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:13px}.uds-stat-icon{display:grid;place-items:center;width:41px;height:41px;border-radius:12px;font-size:1.28rem;font-weight:900}.uds-icon-green{color:#079b74;background:#e3f7ed}.uds-icon-mint{color:#069774;background:#dcf5ef}.uds-icon-lime{color:#6a9a42;background:#eff7df}.uds-icon-cream{color:#b88433;background:#fdf2e1}.uds-stat-arrow{font-size:1.1rem;color:#8eb1a1}.uds-stat strong{font-size:2rem;letter-spacing:-.06em;line-height:1.05;margin-bottom:8px}.uds-stat>span:nth-last-of-type(1){font-weight:720;font-size:.85rem}.uds-stat small{font-size:.73rem;color:#799287;margin-top:8px}.uds-mini-progress{height:6px;border-radius:20px;background:#e8f2ec;margin-top:18px;overflow:hidden}.uds-mini-progress i{height:100%;display:block;background:linear-gradient(90deg,#1dc695,#078761);border-radius:20px}
.uds-columns{display:grid;grid-template-columns:minmax(0,1.64fr) minmax(305px,.9fr);align-items:start;gap:20px}.uds-main-column,.uds-side-column{display:grid;gap:20px;min-width:0}.uds-panel{background:#fff;border:1px solid var(--uds-line);border-radius:17px;padding:23px 25px;box-shadow:0 5px 20px #205b400d;min-width:0}.uds-panel-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}.uds-panel h2{font-size:1.18rem;letter-spacing:-.035em;margin:6px 0 0;color:#163e33;font-weight:850}.uds-panel-link{white-space:nowrap;font-size:.8rem;font-weight:800;color:#087e5e!important}.uds-panel-link:hover{text-decoration:underline}.uds-step-list{border:1px solid #e1eee6;border-radius:12px;overflow:hidden}.uds-step{padding:16px;display:flex;align-items:center;gap:15px}.uds-step+.uds-step{border-top:1px solid #e7efe9}.uds-step-index{width:39px;height:39px;display:grid;place-items:center;flex:none;border-radius:50%;background:#f2f7f3;border:1px solid #dce9e0;font-size:.79rem;font-weight:900;color:#668476}.uds-step-done .uds-step-index{background:#dff5e9;color:#09835f;border-color:#caecda}.uds-step>div{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}.uds-step strong{font-size:.86rem}.uds-step div span{font-size:.75rem;color:#83998e;line-height:1.4}.uds-step>a{color:#087b5c!important;font-size:.8rem;font-weight:800;white-space:nowrap}.uds-missing{padding:12px 15px;background:#fbf7e9;color:#97702e;margin:13px 0 0;border-radius:10px;font-size:.75rem}
.uds-empty{background:#f9fcfa;border:1px dashed #d8e7df;border-radius:13px;display:flex;align-items:center;flex-direction:column;text-align:center;padding:22px 20px 26px}.uds-empty-illustration{display:grid;place-items:center;width:60px;height:60px;color:#078b67;background:#e5f8ee;border-radius:19px;font-size:1.7rem;margin-bottom:10px}.uds-empty strong{font-size:.9rem}.uds-empty p{font-size:.76rem;color:#84988e;max-width:330px;margin:6px 0 17px}.uds-history-list{display:grid;gap:0}.uds-history-item,.uds-saved-item{display:flex;align-items:center;gap:13px;color:#194336!important;padding:15px 4px}.uds-history-item+.uds-history-item,.uds-saved-item+.uds-saved-item{border-top:1px solid #e9f0eb}.uds-run-mark,.uds-saved-initial{display:grid;place-items:center;width:43px;height:43px;flex:none;border-radius:12px;background:#e9f7ef;color:#058664;font-size:1.25rem;font-weight:900}.uds-run-info,.uds-saved-item>span:nth-child(2){display:flex;flex-direction:column;gap:4px;flex:1;min-width:0}.uds-run-info strong,.uds-saved-item strong{font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.uds-run-info small,.uds-saved-item small{font-size:.74rem;color:#84998d;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.uds-run-count{font-size:.95rem;font-weight:900;color:#08775a;margin-left:auto}.uds-run-count small{font-size:.68rem;font-weight:600;color:#819c8d}.uds-run-arrow{color:#76aa95}.uds-saved-empty{display:flex;align-items:center;gap:16px;background:#f8fcf9;border-radius:12px;padding:18px}.uds-saved-empty>span{font-size:2rem;color:#19ad85}.uds-saved-empty>div{flex:1}.uds-saved-empty strong{font-size:.88rem}.uds-saved-empty p{color:#879b90;font-size:.76rem;margin:3px 0 0}
.uds-plan{background:linear-gradient(155deg,#f2fbf6,#fff 65%)}.uds-plan-entry{padding:14px 0;border-bottom:1px solid #e1ede5;display:flex;flex-direction:column;gap:5px}.uds-plan-entry span{font-size:.73rem;color:#7c9588}.uds-plan-entry strong{font-size:.88rem;line-height:1.45;word-break:break-word}.uds-plan .uds-full{margin-top:21px}.uds-tools>a{display:flex;align-items:center;gap:12px;padding:14px 2px;color:#244b3f!important}.uds-tools>a+a{border-top:1px solid #e9f0eb}.uds-tool-icon{display:grid;place-items:center;width:39px;height:39px;flex:none;border-radius:12px;background:#eaf8ef;color:#088360;font-size:1.35rem}.uds-tools>a>span:nth-child(2){display:flex;flex-direction:column;gap:3px;font-size:.85rem;font-weight:800;flex:1}.uds-tools small{font-size:.73rem;color:#8fa195;font-weight:450}.uds-tools b{font-size:.95rem;color:#66a087}.uds-disclaimer{display:flex;gap:13px;background:#e8f7ed;border:1px solid #ccebd7;border-radius:14px;padding:17px}.uds-disclaimer>span{font-size:1.1rem;color:#07946b}.uds-disclaimer strong{font-size:.82rem}.uds-disclaimer p{margin:5px 0 0;color:#6b8979;line-height:1.6;font-size:.74rem}
@media(max-width:1050px){.uds-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.uds-columns{grid-template-columns:1fr}.uds-side-column{grid-template-columns:repeat(2,minmax(0,1fr))}.uds-disclaimer{grid-column:1/-1}}
@media(max-width:720px){.uds-hero{padding:28px 22px}.uds-hero-aside{display:none}.uds-stats{gap:10px}.uds-stat{padding:15px;min-height:164px}.uds-stat strong{font-size:1.7rem}.uds-columns,.uds-main-column,.uds-side-column{gap:12px}.uds-side-column{grid-template-columns:1fr}.uds-panel{padding:19px 16px}.uds-step{gap:10px;padding:13px 10px}.uds-step-index{width:30px;height:30px}.uds-step strong{font-size:.78rem}.uds-step div span{font-size:.7rem}.uds-panel-header{align-items:start}.uds-saved-empty{flex-wrap:wrap}.uds-stat small{line-height:1.3}}
@media(prefers-reduced-motion:reduce){.uds-button,.uds-stat{transition:none}.uds-button:hover,.uds-stat:hover{transform:none}}
</style>

<style scoped>
/* UNISHORTLIST DASHBOARD 3D UPGRADE v1 — inserted as a scoped style block. */
.uds-dashboard { --uds-ink:#123b30; --uds-muted:#6c887d; --uds-line:#daeae0; }
.uds-eyebrow { font-weight:900; gap:10px; color:#087a59; margin:4px 0 15px; }
.uds-dot { width:9px; height:9px; background:#15b887; box-shadow:0 0 0 5px #d7f5e9; }
.uds-hero { min-height:388px; padding:39px clamp(26px,3.1vw,53px); gap:16px; border-radius:25px; margin-bottom:23px; background: radial-gradient(circle at 87% 25%,#c0e9d7 0%,transparent 36%),radial-gradient(circle at 6% 90%,#eafbf1,transparent 50%),linear-gradient(120deg,#f2fbf5 0%,#e5f5eb 100%); box-shadow:0 18px 45px #1b5c3814; border-color:#cce8d9; isolation:isolate; }
.uds-hero::before { content:""; position:absolute; width:410px; height:410px; top:-224px; left:45%; border-radius:50%; border:1px solid #ffffff93; pointer-events:none; }
.uds-hero:after { width:470px; height:470px; right:-105px; top:-133px; border:1px solid #addbc52e; box-shadow:0 0 0 55px #ffffff20,0 0 0 115px #d2eddd17; }
.uds-hero-main { flex:1 1 58%; max-width:750px; }
.uds-welcome { display:inline-flex; align-items:center; padding:8px 12px; border:1px solid #b7dfca; border-radius:999px; color:#087b5a; background:#ffffffad; margin-bottom:20px; font-size:.67rem; letter-spacing:.11em; }
.uds-hero h1 { font-size:clamp(2.15rem,3.6vw,3.7rem); line-height:1.11; margin-bottom:17px; max-width:730px; text-wrap:balance; }
.uds-hero h1 span { background:linear-gradient(98deg,#05936d,#0f7859); background-clip:text; -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.uds-hero p { max-width:555px; line-height:1.73; color:#59796b; font-size:.96rem; }
.uds-hero-pills { display:flex; flex-wrap:wrap; gap:9px; margin-top:20px; }
.uds-hero-pill { background:#ffffffa6; border:1px solid #d0e9da; display:inline-flex; align-items:center; gap:7px; font-size:.7rem; font-weight:750; color:#285949; border-radius:40px; padding:8px 11px; }
.uds-hero-pill b { width:6px; height:6px; display:inline-block; background:#0f9f73; border-radius:50%; }
.uds-hero-actions { margin-top:25px; }
.uds-button { min-height:44px; border-radius:11px; padding:12px 19px; box-shadow:0 3px 8px #1d6a4110; transition:transform .2s ease, box-shadow .2s ease,background .2s ease; }
.uds-button-main { background:linear-gradient(125deg,#079267,#056e54); box-shadow:0 10px 24px #0085602d; }
.uds-button-main:hover { box-shadow:0 15px 27px #0085603c; }
.uds-button:focus-visible, .uds-stat:focus-visible,.uds-history-item:focus-visible,.uds-step a:focus-visible { outline:3px solid #21b98f; outline-offset:3px; }
.uds-hero-aside { flex:0 1 480px; width: min(43%,480px); gap:0; align-self:center; justify-content:center; }
.uds-hero-note { z-index:2; position:relative; width:86%; margin:-2px auto 0; padding:12px 17px; border-radius:14px; border:1px solid #cfe9da; background:#ffffffde; box-shadow:0 13px 29px #24583a1b; }
.uds-hero-note strong { font-size:.78rem; letter-spacing:-.01em; }
.uds-hero-note span { font-size:.72rem; color:#608475; line-height:1.55; }
.uds-stats { gap:17px; margin-bottom:22px; }
.uds-stat { position:relative; overflow:hidden; border:1px solid #e0ece4; border-radius:18px; padding:22px; min-height:186px; box-shadow:0 9px 27px #205c3e0b; isolation:isolate; transform:translateY(0); transition:transform .24s ease,box-shadow .24s ease,border-color .24s ease; }
.uds-stat::after { content:""; position:absolute; top:-42px; right:-42px; width:125px; height:125px; border-radius:50%; border:20px solid #ecf8f1; opacity:.68; pointer-events:none; z-index:-1; }
.uds-stat:hover { transform:translateY(-6px); box-shadow:0 19px 35px #205b3f17; border-color:#93d4b3; }
.uds-stat-icon { width:45px; height:45px; border-radius:14px; box-shadow:inset 0 1px 0 #ffffffa6; transition:transform .3s ease; }
.uds-stat:hover .uds-stat-icon { transform:translateY(-3px) rotate(-7deg); }
.uds-stat strong { margin-bottom:9px; font-size:2.2rem; font-variant-numeric:tabular-nums; }
.uds-stat small { color:#789186; }
.uds-mini-progress { height:7px; background:#e4f1e9; margin-top:auto; }
.uds-mini-progress i { box-shadow:0 0 13px #17c38d7a; }
.uds-columns { gap:20px; }
.uds-panel { border-radius:19px; padding:24px 26px; border-color:#dceae1; box-shadow:0 10px 29px #16422b0d; }
.uds-panel h2 { font-size:1.21rem; }
.uds-panel-header { padding-bottom:12px; border-bottom:1px solid #edf3ef; margin-bottom:12px; }
.uds-section-overline { font-size:.64rem; letter-spacing:.14em; }
.uds-step-list { border:0; border-radius:0; overflow:visible; }
.uds-step { position:relative; border:1px solid #e7f0e9; border-radius:12px; padding:16px; margin-top:10px; transition:background .2s ease,transform .2s ease,border-color .2s ease; }
.uds-step + .uds-step { border-top:1px solid #e7f0e9; }
.uds-step:hover { background:#f7fcf8; border-color:#bfdfce; transform:translateX(3px); }
.uds-step-index { height:41px; width:41px; border-radius:12px; }
.uds-step-done .uds-step-index { background:linear-gradient(140deg,#ddf8e9,#bfead2); }
.uds-history-item, .uds-saved-item { border-radius:11px; padding:15px 10px; transition:background .2s ease, transform .2s ease; }
.uds-history-item:hover,.uds-saved-item:hover { background:#f3fbf5; transform:translateX(3px); }
.uds-run-mark, .uds-saved-initial { background:linear-gradient(145deg,#e9f9f0,#d7f0e2); }
.uds-saved-empty { border:1px solid #edf2ed; }
.uds-plan { background:radial-gradient(circle at 100% 0,#d8f2e4 0,transparent 47%),linear-gradient(160deg,#f1fbf5,#fff 75%); }
.uds-plan-entry { padding:14px 0; }
.uds-plan-entry span { font-weight:650; font-size:.73rem; }
.uds-tools>a { padding:14px 6px; border-radius:10px; transition:transform .2s ease,background .2s ease; }
.uds-tools>a:hover { background:#f5fbf6; transform:translateX(3px); }
.uds-tool-icon { background:linear-gradient(135deg,#e5f8ef,#d6f0e2); }
.uds-disclaimer { border-radius:17px; }
@keyframes uds-rise-in { from { opacity:0; transform:translateY(18px); } to { opacity:1; transform:translateY(0); } }
@keyframes uds-gentle-breathe { 0%,100% { box-shadow:0 11px 24px #096c4f14; } 50% { box-shadow:0 17px 34px #096c4f23; } }
.uds-hero { animation:uds-rise-in .55s ease both; }
.uds-stat { animation:uds-rise-in .58s ease both; }
.uds-stat:nth-child(1) { animation-delay:.08s; }.uds-stat:nth-child(2) { animation-delay:.15s; }.uds-stat:nth-child(3) { animation-delay:.22s; }.uds-stat:nth-child(4) { animation-delay:.29s; }
.uds-panel { animation:uds-rise-in .55s ease both; animation-delay:.28s; }
.uds-hero-note { animation:uds-gentle-breathe 6s ease-in-out infinite; }
@media(max-width:1180px) { .uds-hero { padding:31px; }.uds-hero-aside { flex-basis:380px; width:42%; }.uds-hero h1 { font-size:clamp(2rem,3.2vw,3rem); } }
@media(max-width:880px) { .uds-hero { display:grid; grid-template-columns:minmax(0,1fr); gap:3px; }.uds-hero-aside { display:flex; width:100%; flex:initial; max-width:100%; min-width:0; }.uds-hero-main { width:100%; }.uds-hero-note { max-width:430px; margin-top:-5px; } }
@media(max-width:720px) { .uds-hero { padding:24px 20px; border-radius:18px; }.uds-hero h1 { font-size:clamp(2rem,8vw,3rem); }.uds-hero-pills { gap:6px; }.uds-hero-pill { padding:7px 9px; font-size:.66rem; }.uds-stats { gap:11px; }.uds-stat { border-radius:14px; min-height:168px; padding:16px; }.uds-stat strong { font-size:1.8rem; }.uds-panel { padding:20px 17px; } }
@media(max-width:430px) { .uds-hero-actions { flex-direction:column; align-items:stretch; }.uds-button { width:100%; justify-content:space-between; }.uds-hero-note { width:100%; }.uds-stat { min-height:166px; padding:14px; }.uds-stat strong { font-size:1.65rem; } }
@media(prefers-reduced-motion:reduce) { .uds-dashboard .uds-hero,.uds-dashboard .uds-stat,.uds-dashboard .uds-panel,.uds-dashboard .uds-hero-note { animation:none!important; }.uds-dashboard .uds-step,.uds-dashboard .uds-history-item,.uds-dashboard .uds-tools>a,.uds-dashboard .uds-saved-item,.uds-dashboard .uds-stat-icon { transition:none!important; }.uds-dashboard .uds-step:hover,.uds-dashboard .uds-history-item:hover,.uds-dashboard .uds-tools>a:hover,.uds-dashboard .uds-saved-item:hover,.uds-dashboard .uds-stat:hover { transform:none!important; } }

</style>
