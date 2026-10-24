<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthShell from '../../components/auth/AuthShell.vue'
import { isApiError } from '../../services/api/client'
import { useAuthStore } from '../../stores/auth'
import { safeRedirect } from '../../router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const confirm = ref('')
const showPassword = ref(false)
const showConfirm = ref(false)
const pending = ref(false)
const formError = ref('')
const fieldErrors = ref<{ email?: string; password?: string; confirm?: string }>({})

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const checks = computed(() => [
  { label: '12+ characters', ok: password.value.length >= 12 },
  { label: 'Upper and lowercase', ok: /[a-z]/.test(password.value) && /[A-Z]/.test(password.value) },
  { label: 'One number', ok: /\d/.test(password.value) },
  { label: 'One symbol', ok: /[^A-Za-z0-9]/.test(password.value) },
])
const passwordOk = computed(() => checks.value.every((check) => check.ok))
const loginLink = computed(() => {
  const redirect = safeRedirect(route.query.redirect)
  return redirect ? { path: '/login', query: { redirect } } : { path: '/login' }
})

watch(email, () => { fieldErrors.value.email = undefined; formError.value = '' })
watch(password, () => { fieldErrors.value.password = undefined; formError.value = '' })
watch(confirm, () => { fieldErrors.value.confirm = undefined; formError.value = '' })

function validate(): boolean {
  fieldErrors.value = {}
  if (!EMAIL_RE.test(email.value.trim())) fieldErrors.value.email = 'Enter a valid email address.'
  if (!passwordOk.value) fieldErrors.value.password = 'Your password must meet all four requirements.'
  if (!confirm.value || confirm.value !== password.value) fieldErrors.value.confirm = 'Passwords do not match.'
  return Object.keys(fieldErrors.value).length === 0
}

async function submit() {
  if (pending.value || !validate()) return
  pending.value = true
  formError.value = ''
  try {
    await auth.register(email.value.trim(), password.value)
    // First-time journey stays on the existing onboarding flow.
    void router.push(safeRedirect(route.query.redirect) ?? '/dashboard')
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
  <AuthShell mode="signup">
    <div class="auth-heading auth-heading-signup">
      <span class="auth-eyebrow">LET'S GET STARTED <span aria-hidden="true">✳</span></span>
      <h1>Make room for<br /><span>what's next.</span></h1>
      <p>Create your account and start building a university shortlist that reflects your goals.</p>
    </div>

    <div v-if="formError" class="auth-alert" role="alert">{{ formError }}</div>

    <form class="auth-form auth-form-signup" novalidate :aria-busy="pending" @submit.prevent="submit">
      <div class="auth-field">
        <label for="signup-email">Email address</label>
        <div class="auth-input-wrap">
          <svg class="auth-input-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></svg>
          <input id="signup-email" v-model="email" type="email" inputmode="email" autocomplete="email" placeholder="you@example.com" required :aria-invalid="Boolean(fieldErrors.email)" :aria-describedby="fieldErrors.email ? 'signup-email-error' : undefined" />
        </div>
        <span v-if="fieldErrors.email" id="signup-email-error" class="auth-field-error">{{ fieldErrors.email }}</span>
      </div>

      <div class="auth-field">
        <label for="signup-password">Create password</label>
        <div class="auth-input-wrap">
          <svg class="auth-input-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          <input id="signup-password" v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" placeholder="Create a strong password" required :aria-describedby="fieldErrors.password ? 'signup-password-rules signup-password-error' : 'signup-password-rules'" :aria-invalid="Boolean(fieldErrors.password)" />
          <button class="auth-reveal" type="button" :aria-label="showPassword ? 'Hide password' : 'Show password'" :aria-pressed="showPassword" @click="showPassword = !showPassword">{{ showPassword ? 'Hide' : 'Show' }}</button>
        </div>
        <ul id="signup-password-rules" class="auth-rule-grid" aria-label="Password requirements">
          <li v-for="check in checks" :key="check.label" :class="{ 'auth-rule-met': check.ok }"><span aria-hidden="true">{{ check.ok ? '✓' : '○' }}</span> {{ check.label }}</li>
        </ul>
        <span v-if="fieldErrors.password" id="signup-password-error" class="auth-field-error">{{ fieldErrors.password }}</span>
      </div>

      <div class="auth-field">
        <label for="signup-confirm">Confirm password</label>
        <div class="auth-input-wrap">
          <svg class="auth-input-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          <input id="signup-confirm" v-model="confirm" :type="showConfirm ? 'text' : 'password'" autocomplete="new-password" placeholder="Repeat your password" required :aria-invalid="Boolean(fieldErrors.confirm)" :aria-describedby="fieldErrors.confirm ? 'signup-confirm-error' : undefined" />
          <button class="auth-reveal" type="button" :aria-label="showConfirm ? 'Hide confirmation password' : 'Show confirmation password'" :aria-pressed="showConfirm" @click="showConfirm = !showConfirm">{{ showConfirm ? 'Hide' : 'Show' }}</button>
        </div>
        <span v-if="fieldErrors.confirm" id="signup-confirm-error" class="auth-field-error">{{ fieldErrors.confirm }}</span>
      </div>

      <button class="auth-submit" type="submit" :disabled="pending">
        {{ pending ? 'Creating account…' : 'Create my free account' }}
        <span v-if="!pending" aria-hidden="true">→</span>
        <span v-else class="auth-loader" aria-hidden="true" />
      </button>
      <p class="auth-terms">By creating an account, you agree to our <RouterLink to="/terms">Terms</RouterLink> and acknowledge our <RouterLink to="/privacy">Privacy Policy</RouterLink>.</p>
    </form>

    <p class="auth-switch">Already have an account? <RouterLink :to="loginLink">Log in <span aria-hidden="true">→</span></RouterLink></p>
    <p class="auth-back"><RouterLink to="/">← Back to home</RouterLink></p>
  </AuthShell>
</template>

<style scoped src="./auth-form.css"></style>
