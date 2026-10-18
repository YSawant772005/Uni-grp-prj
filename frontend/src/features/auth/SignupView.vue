<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isApiError } from '../../services/api/client'
import { useAuthStore } from '../../stores/auth'
import { safeRedirect } from '../../router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const confirm = ref('')
const pending = ref(false)
const formError = ref('')
const fieldErrors = ref<{ email?: string; password?: string; confirm?: string }>({})

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const checks = computed(() => [
  { label: 'At least 12 characters', ok: password.value.length >= 12 },
  { label: 'An uppercase and a lowercase letter', ok: /[a-z]/.test(password.value) && /[A-Z]/.test(password.value) },
  { label: 'A digit', ok: /\d/.test(password.value) },
  { label: 'A symbol', ok: /[^A-Za-z0-9]/.test(password.value) },
])
const passwordOk = computed(() => checks.value.every((check) => check.ok))

function validate(): boolean {
  fieldErrors.value = {}
  if (!EMAIL_RE.test(email.value.trim())) fieldErrors.value.email = 'Enter a valid email address.'
  if (!passwordOk.value) fieldErrors.value.password = 'Your password does not meet the rules below.'
  if (confirm.value !== password.value) fieldErrors.value.confirm = 'Passwords do not match.'
  return Object.keys(fieldErrors.value).length === 0
}

async function submit() {
  if (pending.value || !validate()) return
  pending.value = true
  formError.value = ''
  try {
    await auth.register(email.value.trim(), password.value)
    // first-time journey: straight to the profile wizard (UI doc section 6.1)
    void router.push(safeRedirect(route.query.redirect) ?? '/onboarding')
  } catch (err) {
    if (isApiError(err)) {
      formError.value = err.message
      const next: typeof fieldErrors.value = {}
      for (const detail of err.details) {
        if (detail.field === 'email') next.email = detail.message
        if (detail.field === 'password') next.password = detail.message
      }
      fieldErrors.value = next
    } else {
      formError.value = 'Could not create your account. Check your connection and try again.'
    }
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="card">
    <h1>Create your account</h1>
    <p class="muted small">One email and a strong password. No payment details, ever.</p>

    <div v-if="formError" class="error-summary" role="alert">{{ formError }}</div>

    <form novalidate @submit.prevent="submit">
      <div class="field">
        <label for="signup-email">Email</label>
        <input
          id="signup-email"
          v-model="email"
          type="email"
          autocomplete="email"
          required
          :aria-invalid="Boolean(fieldErrors.email)"
          :aria-describedby="fieldErrors.email ? 'signup-email-error' : undefined"
        />
        <span v-if="fieldErrors.email" id="signup-email-error" class="field-error">{{ fieldErrors.email }}</span>
      </div>

      <div class="field">
        <label for="signup-password">Password</label>
        <input
          id="signup-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          required
          :aria-invalid="Boolean(fieldErrors.password)"
          aria-describedby="signup-password-rules"
        />
        <ul id="signup-password-rules" class="small muted" style="margin: 4px 0 0; padding-left: 18px">
          <li v-for="check in checks" :key="check.label" :style="{ color: check.ok ? 'var(--ok)' : undefined }">
            {{ check.ok ? '✓' : '·' }} {{ check.label }}
          </li>
        </ul>
        <span v-if="fieldErrors.password" class="field-error">{{ fieldErrors.password }}</span>
      </div>

      <div class="field">
        <label for="signup-confirm">Confirm password</label>
        <input
          id="signup-confirm"
          v-model="confirm"
          type="password"
          autocomplete="new-password"
          required
          :aria-invalid="Boolean(fieldErrors.confirm)"
          :aria-describedby="fieldErrors.confirm ? 'signup-confirm-error' : undefined"
        />
        <span v-if="fieldErrors.confirm" id="signup-confirm-error" class="field-error">{{ fieldErrors.confirm }}</span>
      </div>

      <button class="btn btn-primary" type="submit" :disabled="pending" style="width: 100%">
        {{ pending ? 'Creating account…' : 'Create account' }}
      </button>
    </form>

    <p class="small" style="margin-top: 14px">
      Already registered?
      <RouterLink :to="{ path: '/login', query: { redirect: String(route.query.redirect ?? '') } }">
        Log in
      </RouterLink>
    </p>
  </div>
</template>
