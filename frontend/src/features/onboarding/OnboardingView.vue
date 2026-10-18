<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { profile as profileApi, recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import type { Country } from '../../types/api'

/** 8-question quick profile wizard (UI doc section 6.1 / 7.3). */

const router = useRouter()
const route = useRoute()
const ui = useUiStore()

// ---------------------------------------------------------------- option lists
// Mirrors backend enums (app/models/enums.py) and the seeded field catalogue.

const DEGREE_LEVELS = [
  ['masters', "Master's (MSc/MA/MEng/MBA and similar)"],
  ['phd', 'PhD / doctorate'],
  ['diploma', 'Postgraduate diploma'],
  ['certificate', 'Certificate programme'],
  ['bachelors', "Bachelor's (if you are switching early)"],
  ['other', 'Other'],
]
const FIELDS = [
  ['computer_science', 'Computer Science'],
  ['artificial_intelligence', 'Artificial Intelligence'],
  ['data_science', 'Data Science'],
  ['business_analytics', 'Business Analytics'],
  ['robotics', 'Robotics'],
  ['mechanical_engineering', 'Mechanical Engineering'],
  ['finance', 'Finance'],
]
const COUNTRY_MODES = [
  ['specific', 'Only these countries - treat them as a hard constraint'],
  ['considering', 'Prefer these countries, but stay open to more'],
  ['open', 'Open to recommendations anywhere'],
]
const GRADE_SYSTEMS = [
  ['cgpa', 'CGPA'],
  ['percentage', 'Percentage'],
  ['gpa', 'GPA (4.0 scale)'],
  ['other', 'Other scale'],
]
const GRADE_SCALES: Record<string, [number, number]> = {
  cgpa: [0, 10],
  percentage: [0, 100],
  gpa: [0, 4],
  other: [0, 100],
}
const GRADUATION_STATUSES = [
  ['completed', 'Completed'],
  ['in_progress', 'In progress'],
  ['other', 'Other'],
]
const TEST_STATUSES = [
  ['not_taken', 'Not taken yet'],
  ['booked', 'Booked'],
  ['completed', 'Completed - I have scores'],
  ['waived', 'Waived by the university'],
  ['unknown', 'Not sure yet'],
]
const TEST_TYPES = [
  ['ielts', 'IELTS'],
  ['toefl', 'TOEFL'],
  ['pte', 'PTE Academic'],
  ['duolingo', 'Duolingo English Test'],
  ['cambridge', 'Cambridge'],
  ['other', 'Other'],
]
const BUDGET_BASES = [
  ['annual_tuition', 'Tuition only - per year'],
  ['annual_all_in', 'Tuition + living costs - per year'],
  ['full_degree_tuition', 'Tuition only - full degree'],
  ['full_degree_all_in', 'Everything (tuition, living, insurance, travel) - full degree'],
]
const INTAKE_TERMS = [
  ['fall', 'Fall (August-September)'],
  ['spring', 'Spring (January-February)'],
  ['winter', 'Winter'],
  ['summer', 'Summer'],
  ['other', 'Other / not sure'],
]
const RISK_TOLERANCES = [
  ['conservative', 'Conservative - prefer safer fits'],
  ['balanced', 'Balanced'],
  ['ambitious', 'Ambitious - happy to aim high'],
]
const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AUD', 'CAD', 'CHF', 'SGD', 'AED']
const CURRENT_YEAR = new Date().getFullYear()
const YEARS = Array.from({ length: 7 }, (_, i) => CURRENT_YEAR + i)

// ------------------------------------------------------------------- wizard state

interface Draft {
  intended_degree_level: string
  field: string
  country_mode: string
  countries: { country_code: string; is_mandatory: boolean }[]
  academic_degree: string
  academic_major: string
  institution_name: string
  grade_system: string
  grade_value: string
  grade_scale_min: string
  grade_scale_max: string
  graduation_status: string
  graduation_year: string
  english_test_status: string
  english_test_type: string
  english_test_overall: string
  budget_amount: string
  budget_currency: string
  budget_basis: string
  target_intake_year: string
  target_intake_term: string
  risk_tolerance: string
}

function emptyDraft(): Draft {
  return {
    intended_degree_level: 'masters',
    field: '',
    country_mode: 'considering',
    countries: [],
    academic_degree: '',
    academic_major: '',
    institution_name: '',
    grade_system: 'cgpa',
    grade_value: '',
    grade_scale_min: '0',
    grade_scale_max: '10',
    graduation_status: '',
    graduation_year: '',
    english_test_status: '',
    english_test_type: '',
    english_test_overall: '',
    budget_amount: '',
    budget_currency: '',
    budget_basis: '',
    target_intake_year: '',
    target_intake_term: '',
    risk_tolerance: '',
  }
}

const DRAFT_KEY = 'uni.onboarding.draft'
const draft = reactive<Draft>(emptyDraft())
const step = ref(0)
const stepErrors = ref<Record<string, string>>({})
const serverError = ref('')
const pending = ref(false)
const completed = ref(false)
const generating = ref(false)
const completedRunId = ref<string | null>(null)

const STEPS = [
  'Degree level',
  'Field of study',
  'Destinations',
  'Academics',
  'Graduation',
  'English test',
  'Budget',
  'Intake',
  'Review',
]
const LAST_INPUT_STEP = 7

// field -> step index, used to jump to the failing step on server validation
const FIELD_STEP: Record<string, number> = {
  intended_degree_level: 0,
  field: 1,
  country_preferences: 2,
  academic_degree: 3,
  academic_major: 3,
  institution_name: 3,
  grade_value: 3,
  grade_scale_min: 3,
  grade_scale_max: 3,
  grade_system: 3,
  graduation_status: 4,
  graduation_year: 4,
  english_test_status: 5,
  english_test_type: 5,
  english_test_overall: 5,
  budget_amount: 6,
  budget_currency: 6,
  budget_basis: 6,
  target_intake_year: 7,
  target_intake_term: 7,
  risk_tolerance: 7,
}

// ------------------------------------------------------------------ draft storage

function persistDraft() {
  localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...draft }))
}

watch(draft, persistDraft)

function loadDraft() {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? 'null')
    if (stored && typeof stored === 'object') {
      Object.assign(draft, emptyDraft(), stored)
      if (!Array.isArray(draft.countries)) draft.countries = []
    }
  } catch {
    // corrupt draft: start clean
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
}

// ------------------------------------------------------------- profile hydration

const countries = ref<Country[]>([])
const profileLoaded = ref(false)

useAsync(async () => {
  const res = await catalog.countries()
  countries.value = res.items
}, { immediate: true })

const profileState = useAsync(() => profileApi.get())
const completenessState = useAsync(() => profileApi.completeness())

async function hydrate() {
  loadDraft()
  const existing = await profileState.run()
  if (existing) {
    profileLoaded.value = true
    // server values fill any gaps the local draft does not have yet
    const fromProfile: Partial<Draft> = {}
    if (existing.intended_degree_level) fromProfile.intended_degree_level = existing.intended_degree_level
    if (existing.field_key) fromProfile.field = existing.field_key
    if (existing.country_mode) fromProfile.country_mode = existing.country_mode
    if (existing.academic_degree) fromProfile.academic_degree = existing.academic_degree
    if (existing.academic_major) fromProfile.academic_major = existing.academic_major
    if (existing.institution_name) fromProfile.institution_name = existing.institution_name
    if (existing.grade_system) fromProfile.grade_system = existing.grade_system
    if (existing.grade_value !== null) fromProfile.grade_value = String(existing.grade_value)
    if (existing.grade_scale_min !== null) fromProfile.grade_scale_min = String(existing.grade_scale_min)
    if (existing.grade_scale_max !== null) fromProfile.grade_scale_max = String(existing.grade_scale_max)
    if (existing.graduation_status) fromProfile.graduation_status = existing.graduation_status
    if (existing.graduation_year !== null) fromProfile.graduation_year = String(existing.graduation_year)
    if (existing.english_test_status) fromProfile.english_test_status = existing.english_test_status
    if (existing.english_test_type) fromProfile.english_test_type = existing.english_test_type
    if (existing.english_test_overall !== null) fromProfile.english_test_overall = String(existing.english_test_overall)
    if (existing.budget_amount !== null) fromProfile.budget_amount = String(existing.budget_amount)
    if (existing.budget_currency) fromProfile.budget_currency = existing.budget_currency
    if (existing.budget_basis) fromProfile.budget_basis = existing.budget_basis
    if (existing.target_intake_year !== null) fromProfile.target_intake_year = String(existing.target_intake_year)
    if (existing.target_intake_term) fromProfile.target_intake_term = existing.target_intake_term

    // only fill blanks: a draft the user is working on wins over stale server values
    for (const [key, value] of Object.entries(fromProfile)) {
      const k = key as keyof Draft
      if (k === 'countries') continue
      if (draft[k] === '' && value !== '') draft[k] = value as never
    }
    if (draft.countries.length === 0 && existing.country_preferences.length > 0) {
      draft.countries = [...existing.country_preferences]
        .sort((a, b) => a.preference_rank - b.preference_rank)
        .map((pref) => ({ country_code: pref.country_code, is_mandatory: pref.is_mandatory }))
    }
    // reflect the mode the server holds when the draft never chose one explicitly
    if (existing.country_mode && !localStorage.getItem(DRAFT_KEY)) draft.country_mode = existing.country_mode
  }
  // deep link from ProfileView (?step=N)
  const wanted = Number(route.query.step)
  if (Number.isInteger(wanted) && wanted >= 0 && wanted <= LAST_INPUT_STEP) step.value = wanted
}

void hydrate()

watch([step], () => {
  void router.replace({ query: { ...route.query, step: String(step.value) } })
})

// ------------------------------------------------------------- country selection

const countryIndex = computed(() => new Map(countries.value.map((c) => [c.code, c])))

function toggleCountry(code: string) {
  const at = draft.countries.findIndex((c) => c.country_code === code)
  if (at >= 0) draft.countries.splice(at, 1)
  else draft.countries.push({ country_code: code, is_mandatory: draft.country_mode === 'specific' })
}

function moveCountry(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= draft.countries.length) return
  const list = draft.countries
  ;[list[index], list[target]] = [list[target], list[index]]
}

watch(
  () => draft.country_mode,
  (mode) => {
    for (const c of draft.countries) c.is_mandatory = mode === 'specific'
  },
)

watch(
  () => draft.grade_system,
  (system) => {
    const scale = GRADE_SCALES[system] ?? GRADE_SCALES.other
    draft.grade_scale_min = String(scale[0])
    draft.grade_scale_max = String(scale[1])
  },
)

// -------------------------------------------------------------------- step logic

const isLast = computed(() => step.value === LAST_INPUT_STEP + 1)

function validateStep(index: number): boolean {
  const errors: Record<string, string> = {}
  const d = draft
  if (index === 0 && !d.intended_degree_level) errors.intended_degree_level = 'Pick your intended degree level.'
  if (index === 1 && !d.field) errors.field = 'Pick the field you want to study.'
  if (index === 2 && d.countries.length === 0)
    errors.country_preferences = 'Pick at least one country - even when you are open to anywhere, name one you would consider.'
  if (index === 3) {
    if (!d.academic_degree.trim()) errors.academic_degree = 'Enter the degree you hold or are pursuing.'
    if (!d.institution_name.trim()) errors.institution_name = 'Enter your institution.'
    const grade = Number(d.grade_value)
    if (d.grade_value === '' || Number.isNaN(grade)) errors.grade_value = 'Enter your grade as a number.'
    else if (grade < Number(d.grade_scale_min) || grade > Number(d.grade_scale_max))
      errors.grade_value = `Grade must be within ${d.grade_scale_min}-${d.grade_scale_max}.`
  }
  if (index === 4) {
    if (!d.graduation_status) errors.graduation_status = 'Pick your graduation status.'
    const year = Number(d.graduation_year)
    if (!d.graduation_year || Number.isNaN(year) || year < 1950 || year > 2100)
      errors.graduation_year = 'Enter your graduation year (or expected year).'
  }
  if (index === 5) {
    if (!d.english_test_status) errors.english_test_status = 'Tell us where you stand with English tests.'
    if (d.english_test_status === 'completed') {
      if (!d.english_test_type) errors.english_test_type = 'Which test did you take?'
      const overall = Number(d.english_test_overall)
      if (d.english_test_overall === '' || Number.isNaN(overall))
        errors.english_test_overall = 'Enter your overall score.'
    }
  }
  if (index === 6) {
    const amount = Number(d.budget_amount)
    if (d.budget_amount === '' || Number.isNaN(amount) || amount <= 0)
      errors.budget_amount = 'Enter your total budget as a positive number.'
    if (!d.budget_currency) errors.budget_currency = 'Pick a currency.'
    if (!d.budget_basis) errors.budget_basis = 'Tell us what the budget covers.'
  }
  if (index === 7) {
    const year = Number(d.target_intake_year)
    if (!d.target_intake_year || Number.isNaN(year)) errors.target_intake_year = 'Pick your intended intake year.'
    if (!d.target_intake_term) errors.target_intake_term = 'Pick the intake term.'
  }
  stepErrors.value = errors
  return Object.keys(errors).length === 0
}

function next() {
  if (step.value <= LAST_INPUT_STEP && !validateStep(step.value)) return
  stepErrors.value = {}
  step.value = Math.min(step.value + 1, STEPS.length - 1)
}

function back() {
  stepErrors.value = {}
  step.value = Math.max(step.value - 1, 0)
}

function errorFor(field: string): string | undefined {
  return stepErrors.value[field]
}

// ------------------------------------------------------------------ review step

const reviewRows = computed(() => {
  const d = draft
  return [
    { step: 0, label: 'Degree level', value: DEGREE_LEVELS.find(([k]) => k === d.intended_degree_level)?.[1] ?? d.intended_degree_level },
    { step: 1, label: 'Field', value: FIELDS.find(([k]) => k === d.field)?.[1] ?? d.field },
    {
      step: 2,
      label: 'Destinations',
      value:
        d.countries.length === 0
          ? 'Not set'
          : d.countries.map((c, i) => `${i + 1}. ${countryIndex.value.get(c.country_code)?.name ?? c.country_code}${c.is_mandatory ? ' (mandatory)' : ''}`).join(', '),
    },
    { step: 3, label: 'Academics', value: `${d.academic_degree}${d.academic_major ? ` - ${d.academic_major}` : ''}, ${d.institution_name} - ${d.grade_value} / ${d.grade_scale_max} (${d.grade_system})` },
    { step: 4, label: 'Graduation', value: `${GRADUATION_STATUSES.find(([k]) => k === d.graduation_status)?.[1] ?? d.graduation_status}, ${d.graduation_year}` },
    {
      step: 5,
      label: 'English test',
      value:
        d.english_test_status === 'completed'
          ? `${TEST_TYPES.find(([k]) => k === d.english_test_type)?.[1] ?? d.english_test_type} overall ${d.english_test_overall}`
          : (TEST_STATUSES.find(([k]) => k === d.english_test_status)?.[1] ?? d.english_test_status),
    },
    { step: 6, label: 'Budget', value: `${d.budget_currency} ${d.budget_amount} - ${BUDGET_BASES.find(([k]) => k === d.budget_basis)?.[1] ?? d.budget_basis}` },
    { step: 7, label: 'Intake', value: `${INTAKE_TERMS.find(([k]) => k === d.target_intake_term)?.[1] ?? d.target_intake_term} ${d.target_intake_year}` },
  ]
})

// ---------------------------------------------------------------------- submit

async function submit() {
  if (pending.value) return
  pending.value = true
  serverError.value = ''
  const d = draft
  const payload = {
    intended_degree_level: d.intended_degree_level,
    field: d.field,
    country_mode: d.country_mode,
    country_preferences: d.countries.map((c, i) => ({
      country_code: c.country_code,
      preference_rank: i + 1,
      is_mandatory: c.is_mandatory,
    })),
    academic_degree: d.academic_degree.trim(),
    academic_major: d.academic_major.trim() || null,
    institution_name: d.institution_name.trim(),
    grade_value: Number(d.grade_value),
    grade_scale_min: Number(d.grade_scale_min),
    grade_scale_max: Number(d.grade_scale_max),
    grade_system: d.grade_system,
    graduation_status: d.graduation_status,
    graduation_year: Number(d.graduation_year),
    english_test_status: d.english_test_status,
    english_test_type: d.english_test_status === 'completed' ? d.english_test_type : null,
    english_test_overall: d.english_test_status === 'completed' ? Number(d.english_test_overall) : null,
    budget_amount: Number(d.budget_amount),
    budget_currency: d.budget_currency,
    budget_basis: d.budget_basis,
    target_intake_year: Number(d.target_intake_year),
    target_intake_term: d.target_intake_term,
    risk_tolerance: d.risk_tolerance || null,
  }
  try {
    // complete the quick profile, then persist optional country-mode/risk via PATCH
    const result = await profileApi.completeOnboarding(payload)
    if (d.country_mode || d.risk_tolerance) {
      try {
        await profileApi.patch({
          country_mode: d.country_mode || null,
          risk_tolerance: d.risk_tolerance || null,
        })
      } catch {
        // non-fatal: the quick profile is already complete
      }
    }
    clearDraft()
    completed.value = true
    profileLoaded.value = true
    void completenessState.run()
    ui.push(
      result.completeness.required_complete
        ? 'Profile saved - all required answers are in.'
        : 'Profile saved, some optional answers are still missing.',
      'success',
    )
  } catch (err) {
    if (isApiError(err)) {
      serverError.value = err.message
      const errors: Record<string, string> = {}
      let jump: number | null = null
      for (const detail of err.details) {
        if (detail.field) {
          errors[detail.field] = detail.message
          const target = FIELD_STEP[detail.field]
          if (jump === null && target !== undefined) jump = target
        }
      }
      stepErrors.value = errors
      if (jump !== null && jump <= LAST_INPUT_STEP) step.value = jump
    } else {
      serverError.value = 'Could not save your profile. Check your connection and try again.'
    }
  } finally {
    pending.value = false
  }
}

async function generateShortlist() {
  if (generating.value) return
  generating.value = true
  try {
    const run = await recommendations.createRun()
    completedRunId.value = run.run_id
    void router.push(`/shortlist/${run.run_id}`)
  } catch (err) {
    ui.pushError(err)
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="stack" style="max-width: 720px; margin: 0 auto">
    <div>
      <h1>Build your profile</h1>
      <p class="muted small" style="margin: 0">
        Eight quick questions. Nothing is guessed - whatever you skip stays visibly missing in your
        results. You can come back and edit any answer later from your
        <RouterLink to="/profile">profile</RouterLink>.
      </p>
    </div>

    <!-- completed confirmation -->
    <div v-if="completed" class="card stack">
      <h2>Profile saved ✓</h2>
      <p class="muted">
        Your answers now drive eligibility checks, cost estimates, scholarship matching and the
        shortlist. Generate your first shortlist now, or explore first - the choice is yours.
      </p>
      <div class="row">
        <button class="btn btn-primary" type="button" :disabled="generating" @click="generateShortlist">
          {{ generating ? 'Generating…' : 'Generate my shortlist' }}
        </button>
        <RouterLink to="/discover" class="btn">Explore programs first</RouterLink>
        <RouterLink to="/profile" class="btn btn-quiet">Back to profile</RouterLink>
      </div>
    </div>

    <div v-else class="card">
      <!-- progress -->
      <ol class="steps" aria-label="Progress">
        <li
          v-for="(label, index) in STEPS"
          :key="label"
          :class="{ active: index === step, done: index < step }"
          :aria-current="index === step ? 'step' : undefined"
        >
          {{ index + 1 }}. {{ label }}
        </li>
      </ol>

      <div v-if="serverError" class="error-summary" role="alert">{{ serverError }}</div>

      <!-- step 0: degree level -->
      <section v-if="step === 0" class="stack-sm">
        <h2>1. What degree are you applying for?</h2>
        <p class="muted small">Pick the level that matches the programmes you want to see.</p>
        <div class="field">
          <label for="degree-level">Intended degree level <span class="muted">(required)</span></label>
          <select id="degree-level" v-model="draft.intended_degree_level" :aria-invalid="Boolean(errorFor('intended_degree_level'))">
            <option v-for="[value, label] in DEGREE_LEVELS" :key="value" :value="value">{{ label }}</option>
          </select>
          <span v-if="errorFor('intended_degree_level')" class="field-error">{{ errorFor('intended_degree_level') }}</span>
        </div>
      </section>

      <!-- step 1: field -->
      <section v-if="step === 1" class="stack-sm">
        <h2>2. What field do you want to study?</h2>
        <p class="muted small">This drives programme matching and eligibility thresholds.</p>
        <div class="field">
          <label for="field">Field of study <span class="muted">(required)</span></label>
          <select id="field" v-model="draft.field" :aria-invalid="Boolean(errorFor('field'))">
            <option value="" disabled>Choose a field…</option>
            <option v-for="[value, label] in FIELDS" :key="value" :value="value">{{ label }}</option>
          </select>
          <span v-if="errorFor('field')" class="field-error">{{ errorFor('field') }}</span>
        </div>
      </section>

      <!-- step 2: destinations -->
      <section v-if="step === 2" class="stack-sm">
        <h2>3. Where do you want to study?</h2>
        <p class="muted small">
          Selection order is your preference rank. "Mandatory" countries become hard constraints in
          shortlist runs - the tool will not suggest programmes outside them.
        </p>
        <div class="field">
          <label for="country-mode">How should destinations be treated?</label>
          <select id="country-mode" v-model="draft.country_mode">
            <option v-for="[value, label] in COUNTRY_MODES" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field">
          <label>Destination countries <span class="muted">(required - pick at least one)</span></label>
          <div v-if="draft.countries.length" class="stack-sm">
            <div v-for="(choice, index) in draft.countries" :key="choice.country_code" class="row">
              <strong class="small">{{ index + 1 }}.</strong>
              <span>{{ countryIndex.get(choice.country_code)?.name ?? choice.country_code }}</span>
              <label class="checkbox-row small" style="margin: 0">
                <input v-model="choice.is_mandatory" type="checkbox" :disabled="draft.country_mode === 'specific'" />
                mandatory
              </label>
              <button class="btn btn-sm btn-quiet" type="button" :disabled="index === 0" @click="moveCountry(index, -1)">↑</button>
              <button class="btn btn-sm btn-quiet" type="button" :disabled="index === draft.countries.length - 1" @click="moveCountry(index, 1)">↓</button>
              <button class="btn btn-sm btn-quiet" type="button" :aria-label="`Remove ${choice.country_code}`" @click="toggleCountry(choice.country_code)">
                Remove
              </button>
            </div>
          </div>
          <p v-else class="muted small" style="margin: 0">No countries selected yet.</p>
          <span v-if="errorFor('country_preferences')" class="field-error">{{ errorFor('country_preferences') }}</span>
        </div>
        <div class="field">
          <label for="country-picker">Add a country</label>
          <select id="country-picker" :value="''" @change="toggleCountry(($event.target as HTMLSelectElement).value)">
            <option value="" disabled>Choose a country…</option>
            <option
              v-for="country in countries.filter((c) => !draft.countries.some((d) => d.country_code === c.code))"
              :key="country.code"
              :value="country.code"
            >
              {{ country.name }}
            </option>
          </select>
        </div>
      </section>

      <!-- step 3: academics -->
      <section v-if="step === 3" class="stack-sm">
        <h2>4. Your academic background</h2>
        <p class="muted small">
          Grade and grading scale are stored separately - CGPA and percentage are never treated as
          interchangeable.
        </p>
        <div class="field">
          <label for="academic-degree">Degree you hold or are pursuing <span class="muted">(required)</span></label>
          <input id="academic-degree" v-model="draft.academic_degree" type="text" placeholder="B.Tech, BSc, BA…" :aria-invalid="Boolean(errorFor('academic_degree'))" />
          <span v-if="errorFor('academic_degree')" class="field-error">{{ errorFor('academic_degree') }}</span>
        </div>
        <div class="field">
          <label for="academic-major">Major / specialisation <span class="muted">(optional)</span></label>
          <input id="academic-major" v-model="draft.academic_major" type="text" placeholder="Computer Science" />
        </div>
        <div class="field">
          <label for="institution">Institution <span class="muted">(required)</span></label>
          <input id="institution" v-model="draft.institution_name" type="text" placeholder="Your university or college" :aria-invalid="Boolean(errorFor('institution_name'))" />
          <span v-if="errorFor('institution_name')" class="field-error">{{ errorFor('institution_name') }}</span>
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="grade-system">Grading system <span class="muted">(required)</span></label>
            <select id="grade-system" v-model="draft.grade_system">
              <option v-for="[value, label] in GRADE_SYSTEMS" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
          <div class="field">
            <label for="grade-value">Your grade <span class="muted">(required)</span></label>
            <input id="grade-value" v-model="draft.grade_value" type="number" step="0.01" min="0" :aria-invalid="Boolean(errorFor('grade_value'))" />
            <span v-if="errorFor('grade_value')" class="field-error">{{ errorFor('grade_value') }}</span>
          </div>
        </div>
        <p class="small muted" style="margin: 0">
          Scale: {{ draft.grade_scale_min }} - {{ draft.grade_scale_max }} (auto-set for
          {{ draft.grade_system }})
        </p>
      </section>

      <!-- step 4: graduation -->
      <section v-if="step === 4" class="stack-sm">
        <h2>5. Graduation status and year</h2>
        <div class="field">
          <label for="graduation-status">Status <span class="muted">(required)</span></label>
          <select id="graduation-status" v-model="draft.graduation_status" :aria-invalid="Boolean(errorFor('graduation_status'))">
            <option value="" disabled>Choose…</option>
            <option v-for="[value, label] in GRADUATION_STATUSES" :key="value" :value="value">{{ label }}</option>
          </select>
          <span v-if="errorFor('graduation_status')" class="field-error">{{ errorFor('graduation_status') }}</span>
        </div>
        <div class="field">
          <label for="graduation-year">Graduation year (or expected) <span class="muted">(required)</span></label>
          <input id="graduation-year" v-model="draft.graduation_year" type="number" min="1950" max="2100" placeholder="2024" :aria-invalid="Boolean(errorFor('graduation_year'))" />
          <span v-if="errorFor('graduation_year')" class="field-error">{{ errorFor('graduation_year') }}</span>
        </div>
      </section>

      <!-- step 5: english test -->
      <section v-if="step === 5" class="stack-sm">
        <h2>6. English test</h2>
        <p class="muted small">Test status is not the same as a test score - tell us both when you have them.</p>
        <div class="field">
          <label for="test-status">Status <span class="muted">(required)</span></label>
          <select id="test-status" v-model="draft.english_test_status" :aria-invalid="Boolean(errorFor('english_test_status'))">
            <option value="" disabled>Choose…</option>
            <option v-for="[value, label] in TEST_STATUSES" :key="value" :value="value">{{ label }}</option>
          </select>
          <span v-if="errorFor('english_test_status')" class="field-error">{{ errorFor('english_test_status') }}</span>
        </div>
        <template v-if="draft.english_test_status === 'completed'">
          <div class="grid-2">
            <div class="field">
              <label for="test-type">Test <span class="muted">(required)</span></label>
              <select id="test-type" v-model="draft.english_test_type" :aria-invalid="Boolean(errorFor('english_test_type'))">
                <option value="" disabled>Choose…</option>
                <option v-for="[value, label] in TEST_TYPES" :key="value" :value="value">{{ label }}</option>
              </select>
              <span v-if="errorFor('english_test_type')" class="field-error">{{ errorFor('english_test_type') }}</span>
            </div>
            <div class="field">
              <label for="test-overall">Overall score <span class="muted">(required)</span></label>
              <input id="test-overall" v-model="draft.english_test_overall" type="number" step="0.5" min="0" :aria-invalid="Boolean(errorFor('english_test_overall'))" />
              <span v-if="errorFor('english_test_overall')" class="field-error">{{ errorFor('english_test_overall') }}</span>
            </div>
          </div>
        </template>
      </section>

      <!-- step 6: budget -->
      <section v-if="step === 6" class="stack-sm">
        <h2>7. Total budget</h2>
        <p class="muted small">Give the number you can actually spend, and what it has to cover.</p>
        <div class="grid-2">
          <div class="field">
            <label for="budget-amount">Amount <span class="muted">(required)</span></label>
            <input id="budget-amount" v-model="draft.budget_amount" type="number" min="1" step="any" :aria-invalid="Boolean(errorFor('budget_amount'))" />
            <span v-if="errorFor('budget_amount')" class="field-error">{{ errorFor('budget_amount') }}</span>
          </div>
          <div class="field">
            <label for="budget-currency">Currency <span class="muted">(required)</span></label>
            <select id="budget-currency" v-model="draft.budget_currency" :aria-invalid="Boolean(errorFor('budget_currency'))">
              <option value="" disabled>Choose…</option>
              <option v-for="code in CURRENCIES" :key="code" :value="code">{{ code }}</option>
            </select>
            <span v-if="errorFor('budget_currency')" class="field-error">{{ errorFor('budget_currency') }}</span>
          </div>
        </div>
        <div class="field">
          <label for="budget-basis">What does it cover? <span class="muted">(required)</span></label>
          <select id="budget-basis" v-model="draft.budget_basis" :aria-invalid="Boolean(errorFor('budget_basis'))">
            <option value="" disabled>Choose…</option>
            <option v-for="[value, label] in BUDGET_BASES" :key="value" :value="value">{{ label }}</option>
          </select>
          <span v-if="errorFor('budget_basis')" class="field-error">{{ errorFor('budget_basis') }}</span>
        </div>
      </section>

      <!-- step 7: intake -->
      <section v-if="step === 7" class="stack-sm">
        <h2>8. Intended intake</h2>
        <div class="grid-2">
          <div class="field">
            <label for="intake-year">Year <span class="muted">(required)</span></label>
            <select id="intake-year" v-model="draft.target_intake_year" :aria-invalid="Boolean(errorFor('target_intake_year'))">
              <option value="" disabled>Choose…</option>
              <option v-for="year in YEARS" :key="year" :value="String(year)">{{ year }}</option>
            </select>
            <span v-if="errorFor('target_intake_year')" class="field-error">{{ errorFor('target_intake_year') }}</span>
          </div>
          <div class="field">
            <label for="intake-term">Term <span class="muted">(required)</span></label>
            <select id="intake-term" v-model="draft.target_intake_term" :aria-invalid="Boolean(errorFor('target_intake_term'))">
              <option value="" disabled>Choose…</option>
              <option v-for="[value, label] in INTAKE_TERMS" :key="value" :value="value">{{ label }}</option>
            </select>
            <span v-if="errorFor('target_intake_term')" class="field-error">{{ errorFor('target_intake_term') }}</span>
          </div>
        </div>
        <div class="field">
          <label for="risk">How ambitious should the shortlist be? <span class="muted">(optional)</span></label>
          <select id="risk" v-model="draft.risk_tolerance">
            <option value="">No preference</option>
            <option v-for="[value, label] in RISK_TOLERANCES" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
      </section>

      <!-- review -->
      <section v-if="isLast" class="stack-sm">
        <h2>Review your answers</h2>
        <p class="muted small">
          Check everything before saving - each answer can be edited at its step.
        </p>
        <dl class="kv">
          <template v-for="row in reviewRows" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>
              {{ row.value }}
              <button class="btn btn-sm btn-quiet" type="button" @click="step = row.step">Edit</button>
            </dd>
          </template>
        </dl>
      </section>

      <!-- nav -->
      <div class="row-between" style="margin-top: 18px">
        <button class="btn" type="button" :disabled="step === 0 || pending" @click="back">← Back</button>
        <button v-if="!isLast" class="btn btn-primary" type="button" @click="next">Next →</button>
        <button v-else class="btn btn-primary" type="button" :disabled="pending" @click="submit">
          {{ pending ? 'Saving…' : 'Save profile' }}
        </button>
      </div>
      <p class="small muted" style="margin: 10px 0 0">
        Drafts are kept in this browser as you go - closing the tab and coming back keeps your answers.
      </p>
    </div>
  </div>
</template>
