<script setup lang="ts">
import CollegeUniversitySearch from '../../components/CollegeUniversitySearch.vue'
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import PreferredCountrySearch from '../../components/PreferredCountrySearch.vue'
import { profile as profileApi } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import ProfileDropdown from '../../components/ProfileDropdown.vue'
import CurrentDegreeSearch from '../../components/CurrentDegreeSearch.vue'
import DegreeBranchSearch from '../../components/DegreeBranchSearch.vue'
import { branchesForCurrentDegree } from '../../data/currentDegreeBranches'
import { canonicalCurrentDegree, isCurrentDegreeTitle } from '../../data/currentDegreeTitles'
import MasterProgramSearch from '../../components/MasterProgramSearch.vue'
import SpecializationSearch from '../../components/SpecializationSearch.vue'
import { specializationsForMaster } from '../../data/masterSpecializations'
import { isMasterDegreeTitle } from '../../data/masterDegreeTitles'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import type { Country, Profile } from '../../types/api'

/** Five-stage student profile wizard. PATCH persists valid intermediate stages;
 * the existing onboarding-complete API marks the profile complete at the end.
 */
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const STEP_LABELS = [
  { title: 'Basic Information', short: 'Basic', note: 'Personal details' },
  { title: 'Academic Profile', short: 'Acad.', note: 'Marks, Degree, CGPA' },
  { title: 'Test Scores', short: 'Tests', note: 'IELTS, TOEFL, GRE, GMAT' },
  { title: 'Preferences', short: 'Prefs', note: 'Countries, Course, Budget' },
  { title: 'Career Goals', short: 'Goals', note: 'Job role, Industry' },
]

// Reuse the same custom menu in every Student Profile step.
const GRADE_SCALE_OPTIONS = [
  { value: 'cgpa', label: 'CGPA / 10' },
  { value: 'percentage', label: 'Percentage (%)' },
  { value: 'gpa', label: 'GPA / 4' },
]
const GRAD_STATUS_OPTIONS = [
  { value: 'completed', label: 'Completed' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'other', label: 'Other' },
]
const ENGLISH_STATUS_OPTIONS = [
  { value: 'not_taken', label: 'Not taken' },
  { value: 'booked', label: 'Booked' },
  { value: 'completed', label: 'Completed' },
  { value: 'waived', label: 'Waived' },
  { value: 'unknown', label: 'Not sure yet' },
]
const ENGLISH_TYPE_OPTIONS = [
  { value: 'ielts', label: 'IELTS' },
  { value: 'toefl', label: 'TOEFL' },
  { value: 'pte', label: 'PTE Academic' },
  { value: 'duolingo', label: 'Duolingo' },
  { value: 'cambridge', label: 'Cambridge' },
  { value: 'other', label: 'Other' },
]
const COUNTRY_MODE_OPTIONS = [
  { value: 'specific', label: 'Only these countries' },
  { value: 'considering', label: 'Prefer these, but open to more' },
  { value: 'open', label: 'Open to suggestions' },
]
const CURRENCY_OPTIONS = ['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'AED', 'CHF', 'SGD'].map((value) => ({ value, label: value }))
const BUDGET_BASIS_OPTIONS = [
  { value: 'full_degree_all_in', label: 'Entire degree — tuition and living costs' },
  { value: 'full_degree_tuition', label: 'Entire degree — tuition only' },
  { value: 'annual_all_in', label: 'One year — tuition and living costs' },
  { value: 'annual_tuition', label: 'One year — tuition only' },
]
const INTAKE_TERM_OPTIONS = [
  { value: 'fall', label: 'Fall' },
  { value: 'spring', label: 'Spring' },
  { value: 'winter', label: 'Winter' },
  { value: 'summer', label: 'Summer' },
  { value: 'other', label: 'Not sure' },
]
const RISK_OPTIONS = [
  { value: 'conservative', label: 'Conservative — favor safer-fit programs' },
  { value: 'balanced', label: 'Balanced — a mix of program types' },
  { value: 'ambitious', label: 'Ambitious — reach for challenging programs' },
]

const GRADES: Record<string, number> = { cgpa: 10, percentage: 100, gpa: 4 }
const CURRENT_YEAR = new Date().getFullYear()
const GRADUATION_YEARS = Array.from({ length: 32 }, (_, index) => CURRENT_YEAR + 6 - index)
const INTAKE_YEARS = Array.from({ length: 7 }, (_, index) => CURRENT_YEAR + index)
const GRADUATION_YEAR_OPTIONS = GRADUATION_YEARS.map((year) => ({ value: String(year), label: String(year) }))
const INTAKE_YEAR_OPTIONS = INTAKE_YEARS.map((year) => ({ value: String(year), label: String(year) }))

interface Draft {
  full_name: string
  academic_degree: string
  academic_major: string
  graduation_year: string
  grade_system: string
  grade_value: string
  institution_name: string
  graduation_status: string
  intended_degree_level: string
  field: string
  english_test_status: string
  english_test_type: string
  english_test_overall: string
  gre_score: string
  gmat_score: string
  country_mode: string
  countries: { country_code: string; is_mandatory: boolean }[]
  budget_amount: string
  budget_currency: string
  budget_basis: string
  target_intake_year: string
  target_intake_term: string
  career_goal: string
  industry: string
  risk_tolerance: string
}
function newDraft(): Draft {
  return {
    full_name: '', academic_degree: '', academic_major: '', graduation_year: '',
    grade_system: 'cgpa', grade_value: '', institution_name: '', graduation_status: '',
    intended_degree_level: 'masters', field: '', english_test_status: '', english_test_type: '',
    english_test_overall: '', gre_score: '', gmat_score: '', country_mode: 'considering', countries: [],
    budget_amount: '', budget_currency: 'INR', budget_basis: 'full_degree_all_in',
    target_intake_year: '', target_intake_term: '', career_goal: '', industry: '', risk_tolerance: 'balanced',
  }
}
const draft = reactive<Draft>(newDraft())
const currentStep = ref(0)
const busy = ref(false)
const formError = ref('')
const errors = ref<Record<string, string>>({})
const countries = ref<Country[]>([])
const countryLoadError = ref('')
const loading = ref(true)
const draftKey = computed(() => `uni.onboarding.five-step.${auth.user?.id ?? 'guest'}`)
// Selected named Master's degree is browser-only until a dedicated API field exists.
const desiredProgramKey = computed(() => `uni.onboarding.desired-program.${auth.user?.id ?? 'guest'}`)
const desiredProgram = ref('')
watch(desiredProgram, (value) => {
  try { localStorage.setItem(desiredProgramKey.value, value) } catch { /* storage unavailable */ }
  // Changing the named Master’s degree clears an unrelated field, preventing
  // an accidental mismatched study choice being submitted to the backend.
  if (draft.field && !specializationsForMaster(value).some((option) => option.value === draft.field)) {
    draft.field = ''
  }
  errors.value.field = ''
  errors.value.desired_program = ''
})
const progress = computed(() => Math.round((currentStep.value / STEP_LABELS.length) * 100))
const userEmail = computed(() => auth.user?.email ?? '')
const gradeLimit = computed(() => GRADES[draft.grade_system] ?? 10)
const hasTestScores = computed(() => draft.english_test_status === 'completed')
const selectedCountryNames = computed(() => draft.countries.map((pref) => countries.value.find((c) => c.code === pref.country_code)?.name ?? pref.country_code))
const STEP_TIPS = [
  { eyebrow: 'THE FOUNDATION', title: 'Every great shortlist starts with you.', body: 'Your degree, graduation year and grades help us check published academic entry requirements.', detail: 'Use your official academic scores for the most useful results.' },
  { eyebrow: 'YOUR BACKGROUND', title: 'Make your experience count.', body: 'The details of your education help us assess program prerequisites and academic fit.', detail: 'You can revisit these answers later.' },
  { eyebrow: 'TEST SCORES', title: 'Not taken a test yet? That is okay.', body: 'Choose your current test status. Completed scores help the app check English-language requirements.', detail: 'Only enter scores you have actually received.' },
  { eyebrow: 'YOUR PRIORITIES', title: 'Choose what matters most.', body: 'Destinations, budget and intake help us find programs that fit your plans and financial preferences.', detail: 'Study costs are estimates, not guarantees.' },
  { eyebrow: 'FINAL STEP', title: 'Let your goals guide the search.', body: 'Career interests and risk preference make the shortlist easier to understand and compare.', detail: 'Fit scores support decisions; they do not predict admission.' },
]
const activeTip = computed(() => STEP_TIPS[currentStep.value] ?? STEP_TIPS[0]!)

function saveLocalDraft() {
  try { localStorage.setItem(draftKey.value, JSON.stringify({ ...draft })) } catch { /* private browsing / unavailable storage */ }
}
watch(draft, saveLocalDraft, { deep: true })
// Reset an unrelated branch when the student changes Current Degree.
// Do not clear saved values during hydration or old B.Tech -> canonical title conversion.
watch(() => draft.academic_degree, (newDegree, previousDegree) => {
  if (loading.value) return
  const normalizedPrevious = canonicalCurrentDegree(previousDegree) ?? previousDegree
  const normalizedNext = canonicalCurrentDegree(newDegree) ?? newDegree
  if (normalizedPrevious !== normalizedNext) {
    draft.academic_major = ''
    errors.value.academic_major = ''
  }
})
watch(() => draft.grade_system, () => {
  if (draft.grade_value && Number(draft.grade_value) > gradeLimit.value) draft.grade_value = ''
})
function loadLocalDraft(): Partial<Draft> | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(draftKey.value) ?? localStorage.getItem('uni.onboarding.draft') ?? 'null')
    if (parsed && typeof parsed === 'object') return parsed as Partial<Draft>
  } catch { /* ignore damaged local draft */ }
  return null
}
function hydrateFromProfile(p: Profile) {
  if (p.academic_degree) draft.academic_degree = p.academic_degree
  if (p.academic_major) draft.academic_major = p.academic_major
  if (p.graduation_year != null) draft.graduation_year = String(p.graduation_year)
  if (p.grade_system) draft.grade_system = p.grade_system
  if (p.grade_value != null) draft.grade_value = String(p.grade_value)
  if (p.institution_name) draft.institution_name = p.institution_name
  if (p.graduation_status) draft.graduation_status = p.graduation_status
  if (p.intended_degree_level) draft.intended_degree_level = p.intended_degree_level
  if (p.field_key) draft.field = p.field_key
  if (p.english_test_status) draft.english_test_status = p.english_test_status
  if (p.english_test_type) draft.english_test_type = p.english_test_type
  if (p.english_test_overall != null) draft.english_test_overall = String(p.english_test_overall)
  if (p.other_test_scores?.gre != null) draft.gre_score = String(p.other_test_scores.gre)
  if (p.other_test_scores?.gmat != null) draft.gmat_score = String(p.other_test_scores.gmat)
  if (p.country_mode) draft.country_mode = p.country_mode
  if (p.country_preferences?.length) draft.countries = [...p.country_preferences]
    .sort((a, b) => a.preference_rank - b.preference_rank)
    .map(({ country_code, is_mandatory }) => ({ country_code, is_mandatory }))
  if (p.budget_amount != null) draft.budget_amount = String(p.budget_amount)
  if (p.budget_currency) draft.budget_currency = p.budget_currency
  if (p.budget_basis) draft.budget_basis = p.budget_basis
  if (p.target_intake_year != null) draft.target_intake_year = String(p.target_intake_year)
  if (p.target_intake_term) draft.target_intake_term = p.target_intake_term
  if (p.risk_tolerance) draft.risk_tolerance = p.risk_tolerance
  if (p.career_goal) draft.career_goal = p.career_goal
}

async function initialize() {
  // Existing API data wins for server-supported fields; local draft wins for
  // unsubmitted edits. The name has no editable backend endpoint yet.
  const localDraft = loadLocalDraft()
  let serverDegreeTitle = ''
  if (auth.user?.display_name) draft.full_name = auth.user.display_name
  try {
    const result = await profileApi.get()
    serverDegreeTitle = result.desired_degree_title ?? ''
    hydrateFromProfile(result)
  } catch (e) {
    if (isApiError(e) && e.status !== 404) formError.value = e.message
  }
  if (localDraft) Object.assign(draft, localDraft)
  // UniShortlist currently targets Master's programs. This is the program level,
  // not the individual qualification title entered in the searchable field.
  draft.intended_degree_level = 'masters'
  try { desiredProgram.value = serverDegreeTitle || localStorage.getItem(desiredProgramKey.value) || '' } catch { /* unavailable storage */ }
  if (!Array.isArray(draft.countries)) draft.countries = []
  try {
    countries.value = (await catalog.countries()).items
  } catch {
    countryLoadError.value = 'Could not load available destinations. Check your backend connection and refresh.'
  } finally {
    loading.value = false
  }
}
void initialize()

function toggleCountry(code: string) {
  const index = draft.countries.findIndex((item) => item.country_code === code)
  if (index >= 0) draft.countries.splice(index, 1)
  else draft.countries.push({ country_code: code, is_mandatory: draft.country_mode === 'specific' })
}
watch(() => draft.country_mode, (mode) => {
  for (const item of draft.countries) item.is_mandatory = mode === 'specific'
})
function invalid(field: keyof Draft, message: string) { errors.value[field] = message }
function validateStep(index: number): boolean {
  errors.value = {}
  if (index === 0) {
    if (!draft.full_name.trim()) invalid('full_name', 'Enter your full name.')
    if (!isCurrentDegreeTitle(draft.academic_degree)) invalid('academic_degree', 'Select your current degree from the list.')
    if (!branchesForCurrentDegree(draft.academic_degree).length || !draft.academic_major.trim()) invalid('academic_major', 'Choose your degree and enter your branch.')
    const year = Number(draft.graduation_year)
    if (!draft.graduation_year || !Number.isInteger(year) || year < 1950 || year > CURRENT_YEAR + 10)
      invalid('graduation_year', 'Choose a valid graduation year.')
    const grade = Number(draft.grade_value)
    if (!draft.grade_value || !Number.isFinite(grade) || grade < 0 || grade > gradeLimit.value)
      invalid('grade_value', `Enter a grade between 0 and ${gradeLimit.value}.`)
  }
  if (index === 1) {
    if (!draft.institution_name.trim()) invalid('institution_name', 'Enter your college or university.')
    if (!draft.graduation_status) invalid('graduation_status', 'Select graduation status.')
    if (!draft.intended_degree_level) invalid('intended_degree_level', 'Select a degree level.')
    if (!isMasterDegreeTitle(desiredProgram.value)) errors.value.desired_program = "Choose a Master's degree title from the list."
    if (!draft.field || !specializationsForMaster(desiredProgram.value).some((item) => item.value === draft.field)) {
      invalid('field', 'Choose a specialization related to your selected Master’s degree.')
    }
  }
  if (index === 2) {
    if (!draft.english_test_status) invalid('english_test_status', 'Select your English test status.')
    if (hasTestScores.value) {
      if (!draft.english_test_type) invalid('english_test_type', 'Select the completed English test.')
      if (!draft.english_test_overall || !Number.isFinite(Number(draft.english_test_overall)) || Number(draft.english_test_overall) < 0)
        invalid('english_test_overall', 'Enter a valid overall score.')
    }
    for (const key of ['gre_score', 'gmat_score'] as const) {
      if (draft[key] && (!Number.isFinite(Number(draft[key])) || Number(draft[key]) < 0)) invalid(key, 'Enter a valid score.')
    }
  }
  if (index === 3) {
    if (!draft.countries.length) invalid('countries', 'Choose at least one destination.')
    if (!draft.budget_amount || !Number.isFinite(Number(draft.budget_amount)) || Number(draft.budget_amount) <= 0)
      invalid('budget_amount', 'Enter a budget greater than zero.')
    if (!draft.target_intake_year) invalid('target_intake_year', 'Choose your intake year.')
    if (!draft.target_intake_term) invalid('target_intake_term', 'Choose your intake term.')
  }
  return Object.keys(errors.value).length === 0
}
function stagePayload(index: number): Partial<Profile> & { field?: string } {
  if (index === 0) return {
    academic_degree: draft.academic_degree, academic_major: draft.academic_major,
    graduation_year: Number(draft.graduation_year), grade_system: draft.grade_system,
    grade_value: Number(draft.grade_value), grade_scale_min: 0, grade_scale_max: gradeLimit.value,
  }
  if (index === 1) return {
    institution_name: draft.institution_name.trim(), graduation_status: draft.graduation_status,
    intended_degree_level: draft.intended_degree_level, desired_degree_title: desiredProgram.value, field: draft.field,
  }
  if (index === 2) {
    const other_test_scores: Record<string, number> = {}
    if (draft.gre_score) other_test_scores.gre = Number(draft.gre_score)
    if (draft.gmat_score) other_test_scores.gmat = Number(draft.gmat_score)
    return {
      english_test_status: draft.english_test_status,
      english_test_type: hasTestScores.value ? draft.english_test_type : null,
      english_test_overall: hasTestScores.value ? Number(draft.english_test_overall) : null,
      other_test_scores: Object.keys(other_test_scores).length ? other_test_scores : null,
    }
  }
  if (index === 3) return {
    country_mode: draft.country_mode,
    country_preferences: draft.countries.map((c, i) => ({ ...c, preference_rank: i + 1 })),
    budget_amount: Number(draft.budget_amount), budget_currency: draft.budget_currency,
    budget_basis: draft.budget_basis, target_intake_year: Number(draft.target_intake_year),
    target_intake_term: draft.target_intake_term,
  }
  return { career_goal: draft.career_goal.trim() || null, risk_tolerance: draft.risk_tolerance || null }
}
async function next() {
  if (busy.value || !validateStep(currentStep.value)) return
  formError.value = ''
  busy.value = true
  saveLocalDraft()
  try {
    // Stage changes are saved on the server as well as in the browser.
    await profileApi.patch(stagePayload(currentStep.value))
    currentStep.value = Math.min(currentStep.value + 1, STEP_LABELS.length - 1)
  } catch (err) {
    formError.value = isApiError(err) ? err.message : 'Could not save this step. Please check your connection.'
    if (isApiError(err)) for (const detail of err.details) if (detail.field) errors.value[detail.field] = detail.message
  } finally { busy.value = false }
}
function goToStep(index: number) {
  if (busy.value || index < 0 || index > currentStep.value) return
  formError.value = ''
  errors.value = {}
  currentStep.value = index
}
function back() {
  if (busy.value) return
  formError.value = ''
  errors.value = {}
  currentStep.value = Math.max(0, currentStep.value - 1)
}
function fullPayload() {
  return {
    intended_degree_level: draft.intended_degree_level, desired_degree_title: desiredProgram.value, field: draft.field,
    country_preferences: draft.countries.map((c, i) => ({ ...c, preference_rank: i + 1 })),
    academic_degree: draft.academic_degree, academic_major: draft.academic_major,
    institution_name: draft.institution_name.trim(), grade_system: draft.grade_system,
    grade_value: Number(draft.grade_value), grade_scale_min: 0, grade_scale_max: gradeLimit.value,
    graduation_status: draft.graduation_status, graduation_year: Number(draft.graduation_year),
    english_test_status: draft.english_test_status,
    english_test_type: hasTestScores.value ? draft.english_test_type : null,
    english_test_overall: hasTestScores.value ? Number(draft.english_test_overall) : null,
    budget_amount: Number(draft.budget_amount), budget_currency: draft.budget_currency,
    budget_basis: draft.budget_basis, target_intake_year: Number(draft.target_intake_year),
    target_intake_term: draft.target_intake_term, risk_tolerance: draft.risk_tolerance || null,
  }
}
async function finish() {
  if (busy.value || !validateStep(4)) return
  busy.value = true
  formError.value = ''
  try {
    await profileApi.completeOnboarding(fullPayload())
    // completeOnboarding replaces the optional profile fields, so apply them after.
    const other_test_scores: Record<string, number> = {}
    if (draft.gre_score) other_test_scores.gre = Number(draft.gre_score)
    if (draft.gmat_score) other_test_scores.gmat = Number(draft.gmat_score)
    try {
      await profileApi.patch({
        country_mode: draft.country_mode, risk_tolerance: draft.risk_tolerance,
        academic_major: draft.academic_major,
        career_goal: [draft.career_goal.trim(), draft.industry.trim() ? `Industry: ${draft.industry.trim()}` : ''].filter(Boolean).join('\n') || null,
        other_test_scores: Object.keys(other_test_scores).length ? other_test_scores : null,
      })
    } catch (optionalError) {
      ui.push('Your required profile is saved, but some optional details could not be saved. You can update them later.', 'error')
    }
    try { localStorage.removeItem(draftKey.value) } catch { /* no storage */ }
    ui.push('Student profile saved successfully.', 'success')
    // The analysis runs on its own route, not inside the onboarding form.
    // Clear the last run from this browser session so a newly edited profile
    // generates a fresh shortlist instead of showing stale recommendations.
    try { sessionStorage.removeItem(`uni.processing.run.${auth.user?.id ?? 'guest'}`) } catch { /* unavailable storage */ }
    await router.replace('/processing-profile')
  } catch (err) {
    formError.value = isApiError(err) ? err.message : 'Could not complete your profile. Please try again.'
    if (isApiError(err)) for (const detail of err.details) if (detail.field) errors.value[detail.field] = detail.message
  } finally { busy.value = false }
}

</script>

<template>
  <div class="profile-start-page">
    <div class="profile-wrap">
      <div class="profile-heading">
        <div class="profile-heading-main">
          <span class="profile-breadcrumb"><span class="breadcrumb-dot" aria-hidden="true"></span> YOUR STUDY ABROAD JOURNEY</span>
          <h1>Let's build your <span>student profile.</span></h1>
          <p>A few details about you will help us find programs that match your goals.</p>
        </div>
        <div class="profile-heading-aside" aria-label="Profile setup consists of five steps">
          <span class="heading-badge-icon" aria-hidden="true">✦</span>
          <span><strong>Personalized for you</strong><small>5 simple steps to get started</small></span>
        </div>
      </div>

      <div class="profile-window">
        <div class="profile-grid">
          <aside class="wizard-rail" aria-label="Profile setup progress">
            <div class="wizard-rail-header">
              <span class="wizard-rail-kicker">GETTING STARTED</span>
              <h2>Your journey</h2>
              <p>Complete these steps to build a profile that's uniquely yours.</p>
            </div>
            <ol class="wizard-list">
              <li v-for="(item, index) in STEP_LABELS" :key="item.title" :class="{ active: index === currentStep, complete: index < currentStep }" :aria-current="index === currentStep ? 'step' : undefined">
                <button type="button" class="wizard-step-button" :disabled="busy || index > currentStep" :aria-label="`${item.title}, step ${index + 1}${index < currentStep ? ', completed' : index === currentStep ? ', current step' : ''}`" @click="goToStep(index)">
                  <span class="wizard-circle" aria-hidden="true">{{ index < currentStep ? '✓' : index + 1 }}</span>
                  <span class="wizard-step-copy"><strong>{{ item.title }}</strong><small>{{ item.note }}</small></span>
                  <span class="wizard-mobile-label" aria-hidden="true">{{ item.short }}</span>
                </button>
              </li>
            </ol>
            <div class="wizard-note">
              <span class="wizard-note-icon" aria-hidden="true">✦</span>
              <div><strong>A better way to choose.</strong><p>Your academic details are saved as you progress.</p></div>
            </div>
          </aside>

          <div class="wizard-content">
            <div v-if="loading" class="wizard-loading" role="status">Loading your saved profile…</div>
            <template v-else>
              <div class="wizard-title-row">
                <div>
                  <span class="step-eyebrow">STEP {{ String(currentStep + 1).padStart(2, '0') }} <span aria-hidden="true">/</span> {{ String(STEP_LABELS.length).padStart(2, '0') }}</span>
                  <h2>{{ STEP_LABELS[currentStep]?.title }}</h2>
                  <p class="step-subtitle">{{ currentStep === 0 ? 'Start with your personal and educational basics.' : currentStep === 1 ? 'Tell us a little more about your education.' : currentStep === 2 ? 'Your test scores help us assess program requirements.' : currentStep === 3 ? 'Help us understand where and when you want to study.' : 'Almost done — tell us where you want to go next.' }}</p>
                </div>
                <div class="step-progress"><strong>{{ progress }}%</strong><small>Completed</small></div>
              </div>
              <div class="progress-bar" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100" aria-label="Saved profile steps"><span :style="{ width: progress + '%' }" /></div>
              <div v-if="formError" class="wizard-error" role="alert">{{ formError }}</div>

              <div class="wizard-workspace">
              <form class="wizard-form" novalidate @submit.prevent="currentStep === 4 ? finish() : next()">
                <!-- Step 1 reproduces the requested Basic Information layout. -->
                <template v-if="currentStep === 0">
                  <div class="form-section-intro"><span class="form-section-icon" aria-hidden="true">01</span><div><h3>Personal &amp; education details</h3><p>Start with the essentials. You can update your academic preferences later.</p></div></div>
                  <div class="form-row">
                    <div class="form-field"><label for="full-name">Full Name <b>*</b></label><input id="full-name" v-model.trim="draft.full_name" autocomplete="name" placeholder="Your full name" :aria-invalid="Boolean(errors.full_name)" /><small v-if="errors.full_name" class="input-error">{{ errors.full_name }}</small><small v-else class="field-note">Stored in your browser draft; account name editing is not yet available.</small></div>
                    <div class="form-field"><label for="profile-email">Email</label><input id="profile-email" :value="userEmail" type="email" autocomplete="email" readonly class="readonly-input" /><small class="field-note">Linked to your account · read-only</small></div>
                  </div>
                  <div class="form-row">
                    <div class="form-field"><label for="current-degree">Current Degree <b>*</b></label><CurrentDegreeSearch id="current-degree" v-model="draft.academic_degree" :invalid="Boolean(errors.academic_degree)" /><small v-if="errors.academic_degree" class="input-error">{{ errors.academic_degree }}</small></div>
                    <div class="form-field"><label for="branch">Branch <b>*</b></label><DegreeBranchSearch id="branch" v-model="draft.academic_major" :degree-title="draft.academic_degree" :invalid="Boolean(errors.academic_major)" /><small v-if="errors.academic_major" class="input-error">{{ errors.academic_major }}</small></div>
                  </div>
                  <div class="form-row">
                    <div class="form-field"><label for="grad-year">Graduation Year <b>*</b></label><ProfileDropdown id="grad-year" v-model="draft.graduation_year" :options="GRADUATION_YEAR_OPTIONS" placeholder="Select year" :invalid="Boolean(errors.graduation_year)" /><small v-if="errors.graduation_year" class="input-error">{{ errors.graduation_year }}</small></div>
                    <div class="form-field"><label for="grade-value">Current CGPA / Percentage <b>*</b></label><div class="grade-input"><input id="grade-value" v-model="draft.grade_value" type="number" min="0" :max="gradeLimit" step="0.01" placeholder="8.2" :aria-invalid="Boolean(errors.grade_value)" /><ProfileDropdown id="grade-scale" v-model="draft.grade_system" :options="GRADE_SCALE_OPTIONS" placeholder="Grade scale" aria-label="Grade scale" /></div><small v-if="errors.grade_value" class="input-error">{{ errors.grade_value }}</small></div>
                  </div>
                </template>

                <template v-if="currentStep === 1">
                  <p class="form-description">Your qualifications help us check published entry requirements.</p>
                  <div class="form-field"><label for="institution">College / University <b>*</b></label><CollegeUniversitySearch id="institution" v-model="draft.institution_name" /><small v-if="errors.institution_name" class="input-error">{{ errors.institution_name }}</small></div>
                  <div class="form-row"><div class="form-field"><label for="grad-status">Graduation Status <b>*</b></label><ProfileDropdown id="grad-status" v-model="draft.graduation_status" :options="GRAD_STATUS_OPTIONS" placeholder="Select status" :invalid="Boolean(errors.graduation_status)" /><small v-if="errors.graduation_status" class="input-error">{{ errors.graduation_status }}</small></div>
                  <div class="form-field"><label for="degree-level">Qualification level</label><input id="degree-level" value="Master's degree" readonly class="readonly-input" /><small class="field-note">This platform focuses on Master's-level programs.</small></div></div>
                  <div class="form-field">
                    <label for="desired-program">Desired Master's Degree <b>*</b></label>
                    <MasterProgramSearch id="desired-program" v-model="desiredProgram" />
                    <small v-if="errors.desired_program" class="input-error">{{ errors.desired_program }}</small><small v-else class="field-note">Select one of the 98 named Master’s degree titles. Available specializations will update automatically.</small>
                  </div>
                  <div class="form-field"><label for="study-field">Intended Field of Study / Specialization <b>*</b></label><SpecializationSearch id="study-field" v-model="draft.field" :degree-title="desiredProgram" :invalid="Boolean(errors.field)" /><small v-if="errors.field" class="input-error">{{ errors.field }}</small><small v-else class="field-note">Search specializations relevant to the selected Master’s degree. Options are examples; university offerings may differ.</small></div>
                </template>

                <template v-if="currentStep === 2">
                  <p class="form-description">It's okay if you haven't taken an English test yet.</p>
                  <div class="form-field"><label for="english-status">English Test Status <b>*</b></label><ProfileDropdown id="english-status" v-model="draft.english_test_status" :options="ENGLISH_STATUS_OPTIONS" placeholder="Select status" :invalid="Boolean(errors.english_test_status)" /><small v-if="errors.english_test_status" class="input-error">{{ errors.english_test_status }}</small></div>
                  <div v-if="hasTestScores" class="form-row"><div class="form-field"><label for="english-type">Test Taken <b>*</b></label><ProfileDropdown id="english-type" v-model="draft.english_test_type" :options="ENGLISH_TYPE_OPTIONS" placeholder="Choose test" :invalid="Boolean(errors.english_test_type)" /><small v-if="errors.english_test_type" class="input-error">{{ errors.english_test_type }}</small></div><div class="form-field"><label for="english-score">Overall Score <b>*</b></label><input id="english-score" v-model="draft.english_test_overall" type="number" min="0" step="0.1" placeholder="e.g. 7.5" /><small v-if="errors.english_test_overall" class="input-error">{{ errors.english_test_overall }}</small></div></div>
                  <div class="form-row"><div class="form-field"><label for="gre-score">GRE Score <span>(optional)</span></label><input id="gre-score" v-model="draft.gre_score" type="number" min="0" placeholder="e.g. 320" /><small v-if="errors.gre_score" class="input-error">{{ errors.gre_score }}</small></div><div class="form-field"><label for="gmat-score">GMAT Score <span>(optional)</span></label><input id="gmat-score" v-model="draft.gmat_score" type="number" min="0" placeholder="e.g. 650" /><small v-if="errors.gmat_score" class="input-error">{{ errors.gmat_score }}</small></div></div>
                </template>

                <template v-if="currentStep === 3">
                  <p class="form-description">Choose at least one destination and tell us what you can spend.</p>
                  <div class="form-field"><label for="country-mode">Destination Preference</label><ProfileDropdown id="country-mode" v-model="draft.country_mode" :options="COUNTRY_MODE_OPTIONS" placeholder="Select destination preference" /></div>
                  <fieldset class="country-picker"><legend>Preferred Countries <b>*</b></legend><p v-if="countryLoadError" class="input-error">{{ countryLoadError }}</p><PreferredCountrySearch v-else :countries="countries" :selected-codes="draft.countries.map((country) => country.country_code)" :disabled="busy" @toggle="toggleCountry" /><small v-if="errors.countries" class="input-error">{{ errors.countries }}</small></fieldset>
                  <div class="form-row"><div class="form-field"><label for="budget">Study Budget <b>*</b></label><input id="budget" v-model="draft.budget_amount" type="number" min="1" step="1" placeholder="e.g. 2500000" /><small v-if="errors.budget_amount" class="input-error">{{ errors.budget_amount }}</small></div><div class="form-field"><label for="currency">Currency</label><ProfileDropdown id="currency" v-model="draft.budget_currency" :options="CURRENCY_OPTIONS" placeholder="Select currency" /></div></div>
                  <div class="form-field"><label for="budget-basis">What does your budget cover?</label><ProfileDropdown id="budget-basis" v-model="draft.budget_basis" :options="BUDGET_BASIS_OPTIONS" placeholder="Choose budget coverage" /></div>
                  <div class="form-row"><div class="form-field"><label for="intake-year">Target Intake Year <b>*</b></label><ProfileDropdown id="intake-year" v-model="draft.target_intake_year" :options="INTAKE_YEAR_OPTIONS" placeholder="Select year" :invalid="Boolean(errors.target_intake_year)" /><small v-if="errors.target_intake_year" class="input-error">{{ errors.target_intake_year }}</small></div><div class="form-field"><label for="intake-term">Intake Term <b>*</b></label><ProfileDropdown id="intake-term" v-model="draft.target_intake_term" :options="INTAKE_TERM_OPTIONS" placeholder="Select term" :invalid="Boolean(errors.target_intake_term)" /><small v-if="errors.target_intake_term" class="input-error">{{ errors.target_intake_term }}</small></div></div>
                </template>

                <template v-if="currentStep === 4">
                  <p class="form-description">One last step! These details are optional, but help personalize your shortlist.</p>
                  <div class="form-field"><label for="career-goal">Target Job Role / Career Goal <span>(optional)</span></label><textarea id="career-goal" v-model="draft.career_goal" rows="3" maxlength="1500" placeholder="e.g. I want to become a machine learning engineer" /></div>
                  <div class="form-field"><label for="industry">Preferred Industry <span>(optional)</span></label><input id="industry" v-model="draft.industry" maxlength="250" placeholder="e.g. Technology, Healthcare, Finance" /></div>
                  <div class="form-field"><label for="risk">Application Strategy</label><ProfileDropdown id="risk" v-model="draft.risk_tolerance" :options="RISK_OPTIONS" placeholder="Choose strategy" /></div>
                  <div class="review-card"><strong>Your profile at a glance</strong><p>{{ draft.academic_degree }} · {{ draft.academic_major }} · {{ draft.grade_value }} ({{ draft.grade_system }})</p><p>{{ selectedCountryNames.join(', ') || 'No countries selected' }} · {{ draft.budget_currency }} {{ draft.budget_amount }}</p><p>Target intake: {{ draft.target_intake_term }} {{ draft.target_intake_year }}</p></div>
                </template>

                <div class="wizard-actions">
                  <button v-if="currentStep > 0" class="profile-back" type="button" :disabled="busy" @click="back">← Back</button>
                  <span v-else class="step-help">Fields with * are required</span>
                  <button class="profile-primary" type="submit" :disabled="busy || Boolean(countryLoadError && currentStep === 3)">{{ busy ? 'Saving…' : currentStep === 4 ? 'Complete Profile ✓' : 'Save & Continue →' }}</button>
                </div>
                <p class="draft-note"><span aria-hidden="true">●</span> Your progress is saved as you continue. Unsaved edits stay on this device.</p>
              </form>
              <aside class="wizard-context" aria-label="Guidance for this profile step">
                <div class="context-symbol" aria-hidden="true">✦</div>
                <span class="context-kicker">{{ activeTip.eyebrow }}</span>
                <h3>{{ activeTip.title }}</h3>
                <p>{{ activeTip.body }}</p>
                <div class="context-divider"></div>
                <div class="context-tip"><span aria-hidden="true">✓</span>{{ activeTip.detail }}</div>
                <div class="context-footer">UNI<span>SHORTLIST</span> · YOUR NEXT STEP</div>
              </aside>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scoped to the five-step student onboarding page. No shared/global styles changed. */
.profile-start-page {
  --profile-ink: #183335;
  --profile-muted: #708488;
  --profile-green: #0d805e;
  --profile-green-dark: #076849;
  --profile-line: #e3ebeb;
  min-height: calc(100vh - 72px);
  width: 100%;
  padding: clamp(28px, 3vw, 56px) clamp(20px, 3.2vw, 70px) 90px;
  background:
    radial-gradient(circle at 2% 10%, rgba(33, 172, 123, .085), transparent 30%),
    radial-gradient(circle at 99% 4%, rgba(85, 154, 228, .10), transparent 27%),
    #f7faf9;
  color: var(--profile-ink);
}
.profile-wrap { width: 100%; max-width: none; margin: 0; min-width: 0; }
.profile-heading { display: flex; align-items: end; justify-content: space-between; gap: 30px; margin-bottom: 28px; }
.profile-heading-main { min-width: 0; }
.profile-breadcrumb { display: inline-flex; align-items: center; gap: 9px; color: #0e8363; font-size: .74rem; font-weight: 800; letter-spacing: .13em; }
.breadcrumb-dot { width: 8px; height: 8px; border-radius: 50%; background: #15b586; box-shadow: 0 0 0 4px #e4f6ee; }
.profile-heading h1 { margin: 13px 0 8px; font-size: clamp(1.8rem, 3.1vw, 2.65rem); letter-spacing: -.045em; line-height: 1.2; font-weight: 800; color: #163a35; }
.profile-heading h1 span { color: #087e60; }
.profile-heading p { margin: 0; color: var(--profile-muted); font-size: .99rem; line-height: 1.55; }
.profile-heading-aside { display: flex; align-items: center; gap: 13px; flex: none; background: #fff; border: 1px solid #deece7; border-radius: 15px; padding: 13px 17px; box-shadow: 0 5px 17px rgba(18, 91, 71, .035); }
.heading-badge-icon { display: grid; place-items: center; width: 38px; height: 38px; background: #e6f7ef; border-radius: 11px; color: #0b8c64; font-size: 1.3rem; }
.profile-heading-aside strong, .profile-heading-aside small { display: block; }
.profile-heading-aside strong { font-size: .83rem; font-weight: 750; }
.profile-heading-aside small { color: #718b86; font-size: .73rem; margin-top: 1px; }
.profile-window { width: 100%; min-width: 0; background: #fff; border: 1px solid #dae7e3; border-radius: 20px; box-shadow: 0 25px 70px rgba(20, 71, 65, .085), 0 3px 12px rgba(20, 71, 65, .02); overflow: hidden; }
.profile-grid { width: 100%; min-width: 0; display: grid; grid-template-columns: clamp(255px, 21vw, 340px) minmax(0, 1fr); min-height: 615px; }
.wizard-rail { display: flex; flex-direction: column; min-width: 0; background: linear-gradient(165deg, #f3faf7, #f9fcfb 64%); border-right: 1px solid #e1ece8; padding: 35px 20px 27px; }
.wizard-rail-header { padding: 0 13px 24px; }
.wizard-rail-kicker { font-size: .68rem; letter-spacing: .14em; font-weight: 800; color: #158665; }
.wizard-rail-header h2 { margin: 8px 0 7px; font-size: 1.32rem; font-weight: 800; letter-spacing: -.03em; color: #173c34; }
.wizard-rail-header p { color: #789087; font-size: .76rem; line-height: 1.5; margin: 0; }
.wizard-list { margin: 0; padding: 0; list-style: none; }
.wizard-list li { position: relative; margin-bottom: 7px; }
.wizard-list li:not(:last-child)::before { content: ''; position: absolute; left: 28px; top: 49px; height: 37px; width: 2px; background: #d8e8e1; }
.wizard-step-button { display: flex; align-items: center; text-align: left; gap: 13px; width: 100%; padding: 12px 9px; min-height: 64px; border: 1px solid transparent; background: transparent; border-radius: 12px; color: #829591; font: inherit; cursor: pointer; position: relative; }
.wizard-step-button:disabled { cursor: default; opacity: 1; }
.wizard-step-button:hover:not(:disabled) { background: #e8f5ef; }
.wizard-list li.active .wizard-step-button { background: #e4f5ed; border-color: #d4ebdf; box-shadow: 0 3px 9px rgba(12, 120, 83, .05); }
.wizard-list li.complete .wizard-step-button { color: #286c58; }
.wizard-circle { display: grid; place-items: center; flex: 0 0 31px; width: 31px; height: 31px; border: 1.5px solid #d8e6e1; border-radius: 50%; background: #fff; color: #889c95; font-size: .78rem; font-weight: 800; position: relative; z-index: 1; }
.wizard-list li.active .wizard-circle { background: #0b8661; border-color: #0b8661; color: white; box-shadow: 0 4px 10px #0b86612d; }
.wizard-list li.complete .wizard-circle { background: #daf3e7; border-color: #c8ebdb; color: #078258; }
.wizard-step-copy { display: block; min-width: 0; }
.wizard-step-copy strong, .wizard-step-copy small { display: block; }
.wizard-step-copy strong { color: inherit; font-size: .83rem; font-weight: 800; line-height: 1.35; }
.wizard-list li.active .wizard-step-copy strong { color: #116949; }
.wizard-step-copy small { color: #8aa097; font-size: .72rem; margin-top: 4px; line-height: 1.3; }
.wizard-mobile-label { display: none; }
.wizard-note { margin-top: auto; display: flex; align-items: start; gap: 11px; background: #e6f4ef; border: 1px solid #d8ebe2; border-radius: 13px; padding: 15px; }
.wizard-note-icon { display: grid; place-items: center; flex: 0 0 26px; height: 26px; border-radius: 8px; background: #d0eede; color: #078a60; }
.wizard-note strong { color: #235748; font-size: .77rem; }
.wizard-note p { color: #718f83; font-size: .73rem; line-height: 1.45; margin: 3px 0 0; }
.wizard-content { width: 100%; min-width: 0; padding: 42px clamp(26px, 4.25vw, 61px) 35px; }
.wizard-title-row { max-width: 980px; display: flex; justify-content: space-between; align-items: center; gap: 20px; }
.step-eyebrow { display: block; color: #0c9069; font-size: .73rem; letter-spacing: .12em; font-weight: 800; }
.step-eyebrow span { padding: 0 4px; color: #a1b7b0; }
.wizard-title-row h2 { margin: 7px 0 3px; color: #183b35; font-size: clamp(1.37rem, 2.2vw, 1.67rem); font-weight: 800; letter-spacing: -.025em; }
.step-subtitle { font-size: .83rem; line-height: 1.55; color: #7a8d89; margin: 0; }
.step-progress { display: flex; flex-direction: column; align-items: end; justify-content: center; flex: none; }
.step-progress strong { font-size: 1.44rem; font-weight: 850; line-height: 1.2; color: #138762; }
.step-progress small { font-size: .7rem; color: #869994; margin-top: 3px; }
.progress-bar { max-width: 980px; height: 7px; border-radius: 99px; background: #edf3f0; margin: 23px 0 32px; overflow: hidden; }
.progress-bar span { display: block; height: 100%; background: linear-gradient(90deg,#1dbc8d,#087954); border-radius: inherit; transition: width .2s ease; }
.wizard-loading { padding: 65px 0; color: #748d86; }
.wizard-error { color: #9d2c2c; border: 1px solid #f6c5c5; background: #fff3f3; border-radius: 10px; padding: 11px 14px; margin-bottom: 21px; font-size: .83rem; }
.wizard-form { display: flex; flex-direction: column; gap: 22px; width: 100%; max-width: 980px; min-width: 0; margin-left: 0; }
.form-description { background: #f1f8f5; border: 1px solid #dbeee4; color: #4e7564; border-radius: 10px; padding: 12px 15px; margin: 0; font-size: .83rem; line-height: 1.55; }
.form-field { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.form-field label, .country-picker legend { font-size: .83rem; font-weight: 750; line-height: 1.35; color: #24413c; }
.form-field label b, .country-picker legend b { color: #0f976b; }
.form-field label span { color: #91a09b; font-size: .75rem; font-weight: 500; }
.form-field input, .form-field select, .form-field textarea { display: block; width: 100%; min-width: 0; max-width: 100%; min-height: 49px; padding: 11px 14px; border: 1px solid #d7e4df; border-radius: 10px; background: #fff; box-sizing: border-box; color: #294540; font: inherit; font-size: .9rem; box-shadow: 0 1px 3px #123b2d08; transition: border-color .16s, box-shadow .16s; }
.form-field textarea { min-height: 100px; resize: vertical; }
.form-field input::placeholder, .form-field textarea::placeholder { color: #a1b2ab; }
.form-field input:focus, .form-field select:focus, .form-field textarea:focus { outline: none; border-color: #199d74; box-shadow: 0 0 0 3px #17966e1f; }
.form-field [aria-invalid='true'] { border-color: #d45555; }
.form-field .readonly-input { background: #f6f9f8; color: #728982; cursor: not-allowed; }
.input-error { color: #ae3838; font-size: .75rem; }
.field-note { color: #889b95; font-size: .72rem; line-height: 1.45; margin-top: 0; }
.form-row { width: 100%; min-width: 0; display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 22px; }
.grade-input { width: 100%; min-width: 0; display: grid; grid-template-columns: minmax(0,1fr) 116px; gap: 8px; }
.grade-input input, .grade-input select { width: 100%; min-width: 0; }
.grade-input select { padding: 10px 8px; font-size: .79rem; }
.country-picker { min-width: 0; margin: 0; padding: 0; border: 0; }
.country-picker legend { padding: 0 0 12px; }
.country-list { display: flex; flex-wrap: wrap; gap: 9px; max-height: 180px; overflow: auto; }
.country-pill { display: inline-flex; align-items: center; gap: 9px; padding: 10px 13px; border-radius: 10px; background: #f9fcfa; border: 1px solid #dce8e2; color: #4e6f63; font-size: .8rem; cursor: pointer; }
.country-pill.selected { background: #e6f6ee; border-color: #77ccb0; color: #106e4f; }
.country-pill input { width: 15px; height: 15px; min-height: auto; accent-color: #0d8c63; }
.review-card { background: #f1f8f5; border: 1px solid #d7eae1; border-radius: 12px; padding: 18px; color: #537367; font-size: .84rem; }
.review-card strong { font-size: .97rem; color: #174e3b; }
.review-card p { margin: 7px 0 0; }
.wizard-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; border-top: 1px solid #e8efec; padding-top: 25px; margin-top: 4px; min-width: 0; }
.step-help { color: #8ba099; font-size: .76rem; }
.profile-primary { display: inline-flex; align-items: center; justify-content: center; flex: none; min-height: 49px; padding: 12px 23px; border: 1px solid #0c805a; border-radius: 10px; background: #0b815c; color: #fff; font: inherit; font-size: .89rem; font-weight: 800; line-height: 1.3; white-space: nowrap; cursor: pointer; box-shadow: 0 7px 17px #0b815c2e; transition: background .16s, transform .16s; }
.profile-primary:hover:not(:disabled) { background: #086648; transform: translateY(-1px); }
.profile-primary:disabled { opacity: .55; cursor: not-allowed; }
.profile-back, .profile-secondary { display: inline-flex; align-items: center; justify-content: center; padding: 11px 19px; min-height: 46px; border: 1px solid #d3e4dc; border-radius: 10px; background: #fff; color: #216c52; font: inherit; font-size: .83rem; font-weight: 750; text-decoration: none; cursor: pointer; }
.profile-back:hover:not(:disabled), .profile-secondary:hover { background: #f0faf5; text-decoration: none; }
.draft-note { display: flex; align-items: start; gap: 7px; margin: -9px 0 0; color: #8ca198; font-size: .73rem; line-height: 1.45; }
.draft-note span { color: #0d926c; font-size: .58rem; margin-top: 3px; }
/* Processing profile uses the same colors, card, grid, and type hierarchy as onboarding. */
.processing-window .profile-grid { min-height: 690px; }
.processing-rail .wizard-list li:not(:last-child)::before { background: #c8e8d8; }
.processing-rail .wizard-step-button { cursor: default; }
.processing-content { padding-top: 44px; }
.processing-phase-tag { display: inline-flex; align-items: center; gap: 7px; padding: 8px 12px; border-radius: 999px; border: 1px solid #d5e9de; background: #ecf7f0; color: #0d815e; font-size: .76rem; font-weight: 800; white-space: nowrap; }
.processing-phase-tag::before { content: ''; display: block; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.processing-phase-tag.ready { background: #e4f8ef; color: #087a51; }
.processing-phase-tag.failed { background: #fff1ee; color: #a94031; border-color: #f2d4ce; }
.processing-panel { margin-top: 27px; padding: 27px clamp(18px, 3vw, 34px) 24px; border: 1px solid #dfece6; background: linear-gradient(180deg, #fbfefc 0%, #fff 46%); border-radius: 17px; min-width: 0; box-shadow: 0 7px 26px #1b70500a; }
.processing-icon { width: 111px; height: 111px; margin: 0 auto 9px; }
.processing-icon svg { display: block; width: 100%; height: 100%; }
.processing-panel h3 { margin: 0 auto 7px; max-width: 500px; font-size: 1.04rem; line-height: 1.45; font-weight: 800; letter-spacing: -.015em; text-align: center; color: #183b35; }
.processing-copy { margin: 0 auto 24px; max-width: 450px; color: #7a8d89; font-size: .82rem; line-height: 1.55; text-align: center; }
.processing-meter-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 9px; color: #758e84; font-size: .78rem; }
.processing-meter-heading strong { font-size: .9rem; color: #0d815e; font-weight: 800; }
.processing-meter { height: 9px; background: #e7f2ec; border-radius: 99px; overflow: hidden; }
.processing-meter > span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #34bc8b, #0b815c); transition: width .35s ease; }
.processing-checklist-heading { margin: 24px 0 14px; font-size: .74rem; font-weight: 800; text-transform: uppercase; letter-spacing: .09em; color: #6b8c80; }
.processing-checklist { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.processing-checklist li { display: flex; align-items: center; gap: 11px; color: #536f64; font-size: .86rem; line-height: 1.45; }
.processing-checklist li.complete { color: #155f45; }
.processing-checklist .checkmark { display: grid; place-items: center; width: 22px; height: 22px; flex: 0 0 22px; border-radius: 50%; border: 1px solid #d0e6dc; background: #f0f8f3; color: #a3b8ab; font-size: 1.1rem; line-height: 1; font-weight: 800; }
.processing-checklist li.complete .checkmark { background: #d7f4e4; color: #0d815e; border-color: #bbe8d2; font-size: .75rem; }
.processing-error { margin: 20px 0 0; }
.processing-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 25px; padding-top: 22px; border-top: 1px solid #e7efea; }
.processing-waiting { display: block; flex: 1 1 100%; color: #81978d; font-size: .79rem; margin: 0 0 4px; }
@media (max-width: 1000px) {
  .profile-grid { grid-template-columns: 245px minmax(0,1fr); }
  .wizard-rail { padding: 28px 13px; }
  .wizard-content { padding: 33px 30px; }
  .form-row { gap: 15px; }
  .grade-input { grid-template-columns: minmax(0,1fr) 98px; }
}
@media (max-width: 760px) {
  .profile-start-page { padding: 28px 14px 60px; }
  .profile-heading { align-items: start; }
  .profile-heading-aside { display: none; }
  .profile-grid { grid-template-columns: minmax(0,1fr); }
  .wizard-rail { display: block; padding: 16px; border-right: 0; border-bottom: 1px solid #e4eee8; }
  .wizard-rail-header, .wizard-note { display: none; }
  .wizard-list { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 4px; }
  .wizard-list li { min-width: 0; margin: 0; }
  .wizard-list li::before { display: none; }
  .wizard-step-button { display: flex; flex-direction: column; min-width: 0; gap: 6px; padding: 9px 0; min-height: 69px; text-align: center; justify-content: flex-start; }
  .wizard-circle { flex: none; width: 27px; height: 27px; font-size: .72rem; }
  .wizard-step-copy { display: none; }
  .wizard-mobile-label { display: block; font-size: .64rem; font-weight: 750; line-height: 1.2; overflow-wrap: anywhere; color: #688276; }
  .wizard-list li.active .wizard-mobile-label { color: #0b805e; }
  .wizard-content { padding: 28px 24px 30px; }
  .form-row { gap: 16px; }
  .grade-input { grid-template-columns: minmax(0,1fr) 112px; }
}
@media (max-width: 520px) {
  .profile-start-page { padding: 23px 10px 45px; }
  .profile-heading { margin-bottom: 22px; }
  .profile-heading h1 { font-size: 1.8rem; }
  .profile-heading p { font-size: .89rem; }
  .profile-window { border-radius: 14px; }
  .wizard-rail { padding: 11px 10px; }
  .wizard-step-button { padding: 9px 1px; }
  .wizard-mobile-label { font-size: .57rem; }
  .wizard-content { padding: 25px 18px 26px; }
  .wizard-title-row h2 { font-size: 1.38rem; }
  .step-subtitle { font-size: .78rem; }
  .step-progress strong { font-size: 1.2rem; }
  .progress-bar { margin: 21px 0 26px; }
  .form-row { grid-template-columns: minmax(0,1fr); gap: 20px; }
  .grade-input { grid-template-columns: minmax(0,1fr) 118px; }
  .wizard-actions { flex-wrap: wrap; }
  .profile-primary, .profile-back { width: 100%; }
  .wizard-actions .profile-back { order: 1; }
  .step-help { flex: 1; }
  .draft-note { line-height: 1.5; }
}
@media (max-width: 760px) {
  .processing-window .profile-grid { min-height: auto; }
  .processing-steps { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .processing-content { padding-top: 30px; }
  .processing-panel { margin-top: 21px; padding: 25px 22px; }
  .processing-steps .wizard-mobile-label { font-size: .58rem; }
}
@media (max-width: 520px) {
  .processing-content { padding: 25px 15px 27px; }
  .processing-steps { gap: 1px; }
  .processing-steps .wizard-step-button { padding-inline: 0; }
  .processing-steps .wizard-circle { width: 25px; height: 25px; flex-basis: 25px; }
  .processing-steps .wizard-mobile-label { font-size: .52rem; letter-spacing: -.02em; }
  .processing-phase-tag { padding: 7px 9px; font-size: .67rem; }
  .processing-panel { padding: 21px 16px; }
  .processing-icon { width: 95px; height: 95px; }
  .processing-panel h3 { font-size: .98rem; }
  .processing-checklist li { font-size: .81rem; }
  .processing-actions .profile-primary, .processing-actions .profile-secondary { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .progress-bar span, .profile-primary, .processing-meter > span { transition: none; }
}

/* Profile UI polish: this page only. Keep the existing 5-step data flow intact. */
.profile-start-page {
  padding: clamp(25px, 2.4vw, 39px) clamp(18px, 2.6vw, 48px) 66px;
  background: radial-gradient(circle at top left, #e8f6ef 0, transparent 30%), #f5f9f7;
}
.profile-heading { margin-bottom: 23px; align-items: center; }
.profile-heading h1 { margin: 9px 0 7px; font-size: clamp(1.85rem, 2.6vw, 2.45rem); line-height: 1.16; }
.profile-heading p { font-size: .96rem; }
.profile-heading-aside { border-radius: 13px; padding: 12px 15px; }
.profile-window { border-radius: 17px; box-shadow: 0 14px 45px rgba(18, 83, 57, .065); }
.profile-grid { grid-template-columns: clamp(248px, 18vw, 286px) minmax(0, 1fr); min-height: 590px; }
.wizard-rail { padding: 31px 17px 25px; background: #f7fbf8; }
.wizard-rail-header { padding: 0 8px 21px; }
.wizard-rail-header h2 { font-size: 1.3rem; }
.wizard-rail-header p { font-size: .81rem; }
.wizard-step-button { padding: 10px 11px; min-height: 61px; }
.wizard-list li:not(:last-child)::before { left: 28px; top: 48px; height: 36px; }
.wizard-step-copy strong { font-size: .89rem; }
.wizard-step-copy small { font-size: .76rem; }
.wizard-circle { width: 31px; height: 31px; }
.wizard-note { border-radius: 11px; padding: 13px; }
.wizard-content { padding: 31px clamp(23px, 3.2vw, 52px) 28px; }
.wizard-title-row { width: 100%; max-width: none; align-items: center; }
.wizard-title-row h2 { margin: 8px 0 6px; font-size: clamp(1.5rem, 2vw, 1.9rem); }
.step-subtitle { font-size: .91rem; }
.step-progress strong { font-size: 1.45rem; }
.progress-bar { max-width: none; margin: 19px 0 24px; height: 8px; }
.wizard-workspace { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0; min-width: 0; width: 100%; align-items: start; }
.wizard-form { width: 100%; max-width: none; min-width: 0; gap: 20px; }
.form-section-intro { display: flex; align-items: center; gap: 12px; background: #f3faf6; border: 1px solid #e0eee5; border-radius: 12px; padding: 13px 15px; margin-bottom: 2px; }
.form-section-icon { display: grid; place-items: center; border-radius: 9px; width: 37px; height: 37px; flex: 0 0 37px; color: #087d5b; font-size: .84rem; font-weight: 850; background: #dff3e8; }
.form-section-intro h3 { color: #1c4538; font-size: .96rem; font-weight: 800; line-height: 1.2; margin: 0 0 4px; }
.form-section-intro p { margin: 0; color: #748c80; font-size: .79rem; line-height: 1.35; }
.form-field { gap: 8px; }
.form-field label, .country-picker legend { font-size: .9rem; font-weight: 750; color: #183a2f; }
.form-field label span { font-size: .8rem; }
.form-field input, .form-field select, .form-field textarea { min-height: 52px; border-radius: 11px; padding: 13px 15px; font-size: .94rem; }
.form-row { gap: clamp(15px, 1.8vw, 26px); }
.grade-input { grid-template-columns: minmax(0, 1fr) minmax(142px, 37%); gap: 9px; }
.field-note { font-size: .75rem; line-height: 1.45; color: #8aa096; }
.wizard-actions { margin-top: 2px; padding-top: 21px; }
.profile-primary { padding: 13px 25px; min-height: 52px; font-size: .95rem; }
.draft-note { font-size: .76rem; }
.wizard-context { display: none; }
.context-symbol { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 15px; color: #0c855f; background: #d9f2e5; font-size: 1.5rem; margin-bottom: 22px; }
.context-kicker { display: inline-block; font-size: .7rem; font-weight: 900; letter-spacing: .11em; color: #0b8660; }
.wizard-context h3 { margin: 14px 0 10px; color: #173d32; font-size: 1.45rem; line-height: 1.25; letter-spacing: -.025em; }
.wizard-context p { margin: 0; color: #668575; font-size: .88rem; line-height: 1.7; }
.context-divider { height: 1px; background: #d5eade; margin: 24px 0 20px; }
.context-tip { display: flex; align-items: flex-start; gap: 10px; color: #346c56; font-size: .8rem; line-height: 1.6; }
.context-tip span { color: #0c915f; font-size: .92rem; font-weight: 800; }
.context-footer { margin-top: 50px; color: #91afa0; font-size: .65rem; font-weight: 800; letter-spacing: .09em; }
.context-footer span { color: #0f8661; }
@media (min-width: 1450px) {
  .wizard-workspace { grid-template-columns: minmax(0, 1fr) 260px; gap: clamp(22px, 2.2vw, 35px); }
  .wizard-context { display: block; min-height: 410px; border: 1px solid #d7eadf; border-radius: 14px; padding: 23px 22px; background: linear-gradient(158deg, #effaf3, #f8fcf9); }
}
@media (max-width: 1000px) {
  .profile-grid { grid-template-columns: 235px minmax(0, 1fr); }
  .wizard-content { padding: 28px 25px; }
  .grade-input { grid-template-columns: minmax(0, 1fr) 137px; }
}
@media (max-width: 760px) {
  .profile-start-page { padding: 22px 12px 48px; }
  .profile-grid { grid-template-columns: minmax(0, 1fr); }
  .wizard-content { padding: 25px 21px; }
  .wizard-rail { padding: 14px; }
  .form-row { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .wizard-form { gap: 19px; }
  .grade-input { grid-template-columns: minmax(0,1fr) minmax(144px, 40%); }
  .wizard-context { display: none; }
}
@media (max-width: 480px) {
  .profile-start-page { padding-inline: 9px; }
  .profile-heading h1 { font-size: 1.72rem; }
  .wizard-content { padding: 22px 17px; }
  .form-section-intro { padding: 12px; }
  .form-section-intro p { font-size: .74rem; }
  .grade-input { grid-template-columns: minmax(0,1fr) 143px; }
  .form-field input, .form-field select, .form-field textarea { min-height: 51px; }
}


/* Use a horizontal stepper on tablets, before the form columns become cramped. */
@media (min-width: 761px) and (max-width: 900px) {
  .profile-grid { grid-template-columns: minmax(0, 1fr); }
  .wizard-rail { display: block; padding: 14px 20px; border-right: 0; border-bottom: 1px solid #e4eee8; }
  .wizard-rail-header, .wizard-note { display: none; }
  .wizard-list { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 5px; }
  .wizard-list li { margin: 0; min-width: 0; }
  .wizard-list li::before { display: none; }
  .wizard-step-button { flex-direction: column; align-items: center; gap: 7px; min-height: 67px; padding: 8px 3px; text-align: center; }
  .wizard-step-copy { display: none; }
  .wizard-mobile-label { display: block; font-size: .7rem; font-weight: 800; color: #658173; }
  .wizard-content { padding: 30px; }
}
</style>
