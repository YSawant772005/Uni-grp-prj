<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { profile as profileApi, recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'

const auth = useAuthStore()
const router = useRouter()
const ui = useUiStore()

const ANALYSIS_AREAS = [
  { title: 'Eligibility & requirements', subtitle: 'Checking published admission criteria', symbol: '01' },
  { title: 'University matching', subtitle: 'Evaluating academic and career fit', symbol: '02' },
  { title: 'Cost & affordability', subtitle: 'Considering your total study budget', symbol: '03' },
  { title: 'Scholarships & funding', subtitle: 'Reviewing available funding information', symbol: '04' },
  { title: 'Career outcomes & ROI', subtitle: 'Assessing available outcome evidence', symbol: '05' },
]

const state = ref<'checking' | 'running' | 'done' | 'error'>('checking')
const progress = ref(0)
const resultRunId = ref<string | null>(null)
const errorMessage = ref('')
const currentArea = computed(() => Math.min(Math.floor(progress.value / 20), ANALYSIS_AREAS.length - 1))
const runKey = computed(() => `uni.processing.run.${auth.user?.id ?? 'guest'}`)
const statusText = computed(() => state.value === 'checking' ? 'Checking profile'
  : state.value === 'running' ? 'Analyzing profile'
    : state.value === 'done' ? 'Your results are ready'
      : 'Action needed')

let alive = true
let started = false
function delay(ms: number) { return new Promise<void>((resolve) => window.setTimeout(resolve, ms)) }
function cachedRun(): string | null {
  try { return sessionStorage.getItem(runKey.value) } catch { return null }
}
function cacheRun(id: string) {
  try { sessionStorage.setItem(runKey.value, id) } catch { /* storage might be unavailable */ }
}
function clearCachedRun() {
  try { sessionStorage.removeItem(runKey.value) } catch { /* storage might be unavailable */ }
}

async function processProfile() {
  state.value = 'running'
  errorMessage.value = ''
  progress.value = 7
  // Recommendation generation returns one completed run. Percentage and
  // substeps below are animated indicators, not backend-reported checkpoints.
  const request = recommendations.createRun().then(
    (run) => ({ ok: true as const, run }),
    (error: unknown) => ({ ok: false as const, error }),
  )
  for (const percent of [20, 39, 58, 75, 91]) {
    await delay(400)
    if (!alive) return
    progress.value = percent
  }
  const response = await request
  if (!alive) return
  if (response.ok) {
    resultRunId.value = response.run.run_id
    cacheRun(response.run.run_id)
    progress.value = 100
    state.value = 'done'
    ui.push('Your university shortlist is ready.', 'success')
  } else {
    errorMessage.value = isApiError(response.error)
      ? response.error.message
      : 'We saved your profile, but could not create a shortlist. Please try again.'
    state.value = 'error'
  }
}

async function initialize() {
  if (started) return
  started = true
  state.value = 'checking'
  errorMessage.value = ''
  try {
    const completeness = await profileApi.completeness()
    if (!alive) return
    if (!completeness.required_complete) {
      await router.replace('/onboarding')
      return
    }
    const stored = cachedRun()
    if (stored) {
      try {
        await recommendations.getRun(stored)
        if (!alive) return
        resultRunId.value = stored
        progress.value = 100
        state.value = 'done'
        return
      } catch { clearCachedRun() }
    }
    if (alive) await processProfile()
  } catch (error) {
    if (!alive) return
    errorMessage.value = isApiError(error) ? error.message
      : 'Could not verify your saved profile. Check your connection and try again.'
    state.value = 'error'
  }
}
async function retry() {
  if (state.value === 'running' || state.value === 'checking') return
  started = false
  await initialize()
}


onMounted(() => { void initialize() })
onBeforeUnmount(() => { alive = false })
/* UNI_AUTO_SHORTLIST_V1: open finished results immediately, including cached runs. */
watch([state, resultRunId], ([phase, runId]) => {
  if (phase === 'done' && runId) {
    void router.replace(`/shortlist/${encodeURIComponent(runId)}`)
  }
})
</script>

<template>
  <div class="processing-page" aria-labelledby="processing-heading">
    <div class="ambient-glow glow-one" aria-hidden="true"></div>
    <div class="ambient-glow glow-two" aria-hidden="true"></div>

    <div class="processing-layout">
      <div class="processing-breadcrumbs">
        <RouterLink to="/onboarding">Student profile</RouterLink>
        <span aria-hidden="true">/</span>
        <span>Processing Profile</span>
        <span class="step-count">STEP 06 OF 07</span>
      </div>

      <header class="hero-copy">
        <div class="eyebrow"><span class="eyebrow-spark" aria-hidden="true">✦</span> PERSONALIZED UNIVERSITY MATCHING</div>
        <h1 id="processing-heading">
          <template v-if="state === 'done'">Your university matches are <em>ready.</em></template>
          <template v-else-if="state === 'error'">Your profile is saved. <em>Try again.</em></template>
          <template v-else>Processing your <em>student profile.</em></template>
        </h1>
        <p>Your profile has been saved. We're preparing personalized university recommendations based on your goals and available evidence.</p>
      </header>

      <div class="workspace">
        <section class="analysis-panel" aria-labelledby="analysis-title">
          <div class="panel-topline">
            <span class="panel-icon" aria-hidden="true">✧</span>
            <span class="panel-label">YOUR ANALYSIS</span>
            <span class="status-pill" :class="state">
              <span class="status-dot"></span>{{ statusText }}
            </span>
          </div>

          <h2 id="analysis-title">{{ state === 'done' ? 'Your university matches are ready.' : state === 'error' ? 'We need to try that again.' : 'Finding your best-fit programs.' }}</h2>
          <p class="panel-intro">{{ state === 'done' ? 'Your shortlist is prepared. Explore your matches, eligibility details and supporting evidence.' : state === 'error' ? 'Your profile is safe. Recommendation generation was interrupted.' : 'We’re putting your academics, preferences and goals together to create a clearer shortlist.' }}</p>

          <div class="progress-meta">
            <span>{{ state === 'done' ? 'Analysis complete' : state === 'error' ? 'Generation paused' : 'Estimated progress' }}</span>
            <strong>{{ progress }}%</strong>
          </div>
          <div class="progress-track" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100" aria-label="Estimated university matching progress">
            <span class="progress-fill" :style="{ width: `${progress}%` }"></span>
          </div>
          <p class="estimate-note">Progress represents an animation while the recommendation engine works; it is not a live backend measurement.</p>

          <h3 class="checklist-title">WHAT WE CONSIDER</h3>
          <ol class="analysis-list">
            <li v-for="(area, index) in ANALYSIS_AREAS" :key="area.title" :class="{ complete: state === 'done', current: state === 'running' && index === currentArea }">
              <span class="area-number" aria-hidden="true">{{ state === 'done' ? '✓' : area.symbol }}</span>
              <span class="area-text"><strong>{{ area.title }}</strong><small>{{ area.subtitle }}</small></span>
              <span class="area-status" aria-hidden="true">{{ state === 'done' ? '✓' : index === currentArea && state === 'running' ? '●' : '·' }}</span>
            </li>
          </ol>

          <p v-if="state === 'error'" class="error-alert" role="alert">{{ errorMessage }}</p>
          <div class="panel-actions">
            <span v-if="state === 'done' && resultRunId" class="processing-hint" role="status">Opening your shortlisted universities…</span>
            <button v-else-if="state === 'error'" type="button" class="action-primary" @click="retry">Try again <span aria-hidden="true">↻</span></button>
            <span v-else class="processing-hint"><span class="hint-spinner" aria-hidden="true"></span> Preparing your results…</span>
            <RouterLink class="action-secondary" to="/discover">Explore programs <span aria-hidden="true">→</span></RouterLink>
          </div>
        </section>
      </div>
      <div class="bottom-note"><span class="note-spark" aria-hidden="true">✓</span> Your profile has been saved securely. <RouterLink to="/onboarding">Review your answers</RouterLink> whenever you need to.</div>
    </div>
  </div>
</template>

<style scoped>
.processing-page { --green:#07835f; --deep:#153f34; --muted:#67877c; position:relative; isolation:isolate; width:100%; min-height:calc(100dvh - 72px); padding:clamp(27px,3vw,52px) clamp(20px,3.2vw,70px) 58px; overflow:hidden; background:radial-gradient(ellipse at 82% 23%,#d9f2e5 0%, transparent 39%),linear-gradient(120deg,#f8fcf9 0%,#f2faf5 100%); color:var(--deep); }
.processing-layout { position:relative; z-index:1; width:min(100%, 1020px); margin-inline:auto; }
.ambient-glow { position:absolute; z-index:-1; border:1px solid #b2e5ce; border-radius:50%; pointer-events:none; }
.glow-one { height:870px; width:870px; top:-390px; right:-240px; opacity:.24; }
.glow-two { height:1050px; width:1050px; right:-330px; top:-430px; opacity:.21; }
.processing-breadcrumbs { display:flex; align-items:center; gap:11px; color:#708d80; font-size:.8rem; font-weight:650; margin-bottom:32px; }
.processing-breadcrumbs a { color:#0b815c; text-decoration:none; }
.processing-breadcrumbs a:hover { text-decoration:underline; }
.step-count { margin-left:auto; color:#0b8862; letter-spacing:.13em; font-size:.7rem; font-weight:850; }
.hero-copy { max-width:790px; margin:0 auto 32px; text-align:center; }
.eyebrow { display:inline-flex; align-items:center; gap:9px; color:#087d59; letter-spacing:.145em; font-size:.74rem; font-weight:850; margin-bottom:14px; }
.eyebrow-spark { display:grid; place-items:center; width:24px; height:24px; border-radius:9px; background:#dbf4e6; color:#0a9468; font-size:1rem; }
.hero-copy h1 { margin:0 auto 17px; font-size:clamp(2.3rem,4.2vw,4.35rem); line-height:1.1; font-weight:850; letter-spacing:-.05em; max-width:760px; }
.hero-copy h1 em { color:#0a8461; font-style:normal; }
.hero-copy p { margin:0 auto; color:#608276; max-width:630px; line-height:1.7; font-size:1rem; }
.workspace { display:block; width:min(100%, 820px); margin-inline:auto; }
.analysis-panel { position:relative; display:flex; flex-direction:column; background:#fff; border:1px solid #d9e8e1; border-radius:24px; padding:clamp(25px,3vw,42px); box-shadow:0 22px 56px rgba(19,74,46,.075); min-width:0; }
.panel-topline { display:flex; align-items:center; gap:10px; margin-bottom:22px; }
.panel-icon { display:grid; place-items:center; width:33px; height:33px; flex:none; border-radius:9px; background:#e3f7ec; color:#068c62; font-size:1.25rem; }
.panel-label { color:#077854; font-size:.73rem; font-weight:850; letter-spacing:.115em; }
.status-pill { margin-left:auto; display:inline-flex; align-items:center; gap:8px; padding:8px 12px; background:#ecf8f1; color:#09845f; border:1px solid #d5ede1; border-radius:999px; font-weight:750; font-size:.73rem; white-space:nowrap; }
.status-dot { width:7px; height:7px; border-radius:50%; background:currentColor; flex:none; animation:blinking 2s infinite; }
.status-pill.done { color:#08744e; }
.status-pill.error { color:#a33f35; border-color:#f3d9d3; background:#fff4f1; }
.analysis-panel h2 { color:#153f34; font-size:clamp(1.47rem,1.75vw,2rem); letter-spacing:-.035em; line-height:1.25; margin:0 0 10px; text-align:center; }
.panel-intro { color:#6b857b; margin:0 auto 25px; line-height:1.65; font-size:.9rem; max-width:620px; text-align:center; }
.progress-meta { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; gap:10px; color:#718d80; font-size:.79rem; font-weight:700; }
.progress-meta strong { color:#078357; font-size:1rem; }
.progress-track { height:11px; width:100%; border-radius:999px; background:#e8f2ed; overflow:hidden; }
.progress-fill { display:block; height:100%; border-radius:inherit; background:linear-gradient(90deg,#30c593,#098261); transition:width .35s ease; position:relative; }
.progress-fill::after { content:''; position:absolute; inset:0; background:linear-gradient(90deg,transparent,#ffffff5c,transparent); animation:shimmer 1.8s linear infinite; }
.estimate-note { margin:10px 0 23px; font-size:.7rem; line-height:1.5; color:#849a91; }
.checklist-title { font-size:.7rem; color:#0c815d; letter-spacing:.14em; font-weight:850; margin:0 0 13px; }
.analysis-list { display:grid; gap:8px; margin:0; padding:0; list-style:none; }
.analysis-list li { display:flex; align-items:center; gap:12px; border:1px solid #e8f0ea; background:#f9fcfa; border-radius:12px; padding:10px 12px; min-width:0; transition:background .2s,border-color .2s; }
.analysis-list li.complete { background:#edf9f1; border-color:#d2ebdc; }
.analysis-list li.current { border-color:#a8dbc1; background:#f0fbf5; }
.area-number { display:grid; place-items:center; width:32px; height:32px; flex:0 0 32px; border-radius:10px; background:#e1f3e9; color:#0b895f; font-size:.78rem; font-weight:850; }
.area-text { display:block; min-width:0; }
.area-text strong, .area-text small { display:block; }
.area-text strong { font-size:.82rem; font-weight:780; color:#2a5a49; }
.area-text small { font-size:.72rem; margin-top:2px; color:#87a096; line-height:1.4; }
.area-status { font-size:1.12rem; color:#9dc8b4; font-weight:800; margin-left:auto; }
.analysis-list li.complete .area-status { color:#12865b; }
.error-alert { color:#a63e39; padding:12px 14px; background:#fff1ee; border:1px solid #f3ccc3; border-radius:12px; font-size:.82rem; line-height:1.5; margin:15px 0 0; }
.panel-actions { display:flex; flex-wrap:wrap; justify-content:center; align-items:center; gap:11px; padding-top:19px; margin-top:15px; }
.action-primary,.action-secondary { border-radius:11px; display:inline-flex; align-items:center; justify-content:center; gap:18px; min-height:48px; padding:11px 19px; font:inherit; font-size:.84rem; font-weight:800; cursor:pointer; text-decoration:none; }
.action-primary { color:#fff; background:#0b815c; border:1px solid #0b815c; box-shadow:0 10px 21px #0b815c30; }
.action-primary:hover { color:white; background:#076b4c; text-decoration:none; transform:translateY(-1px); }
.action-secondary { color:#176d4f; background:white; border:1px solid #cfe4da; }
.action-secondary:hover { color:#0b6748; background:#f3fbf6; text-decoration:none; }
.processing-hint { display:inline-flex; align-items:center; gap:9px; flex:0 0 auto; color:#598577; font-size:.79rem; font-weight:700; padding:12px 2px; }
.hint-spinner { width:14px; height:14px; border:2px solid #c6e6d7; border-top-color:#0b815c; border-radius:50%; animation:rotate 1.1s linear infinite; }
.bottom-note { margin-top:24px; color:#739283; font-size:.82rem; display:flex; justify-content:center; text-align:center; align-items:center; gap:7px; flex-wrap:wrap; }
.note-spark { display:grid; place-items:center; width:22px; height:22px; color:#0b805e; background:#e2f7e9; border-radius:50%; }
.bottom-note a { color:#087f5c; font-weight:750; text-decoration:underline; }
@keyframes rotate { to { transform:rotate(360deg); } }
@keyframes blinking { 50% { opacity:.38; } }
@keyframes shimmer { from { transform:translateX(-100%); } to { transform:translateX(100%); } }
@media (max-width: 900px) {
  .hero-copy { margin-bottom:28px; }
  .processing-layout { width:100%; }
}
@media (max-width: 560px) {
  .processing-page { padding:22px 14px 40px; }
  .processing-breadcrumbs { margin-bottom:24px; }
  .step-count { font-size:.61rem; }
  .hero-copy h1 { font-size:clamp(2.3rem,9.6vw,3rem); }
  .hero-copy p { font-size:.89rem; }
  .analysis-panel { padding:22px 17px; border-radius:17px; }
  .panel-topline { flex-wrap:wrap; }
  .status-pill { font-size:.66rem; padding:7px 9px; }
  .analysis-panel h2 { font-size:1.49rem; }
  .area-text strong { font-size:.77rem; }
  .area-text small { font-size:.68rem; }
  .panel-actions { flex-direction:column; align-items:stretch; }
  .action-primary,.action-secondary { width:100%; }
  .processing-hint { justify-content:center; }
}
@media (prefers-reduced-motion:reduce) {
  *,*::before,*::after { animation:none !important; transition:none !important; }
}
</style>
