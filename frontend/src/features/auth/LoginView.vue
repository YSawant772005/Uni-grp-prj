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
const showPassword = ref(false)
const pending = ref(false)
const formError = ref('')
const fieldErrors = ref<{ email?: string; password?: string }>({})
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const redirectTarget = computed(() => safeRedirect(route.query.redirect) ?? (auth.isReviewer ? '/admin' : '/dashboard'))
const signupLink = computed(() => {
  const redirect = safeRedirect(route.query.redirect)
  return redirect ? { path: '/signup', query: { redirect } } : { path: '/signup' }
})

watch(email, () => { fieldErrors.value.email = undefined; formError.value = '' })
watch(password, () => { fieldErrors.value.password = undefined; formError.value = '' })

function validate(): boolean {
  fieldErrors.value = {}
  if (!EMAIL_RE.test(email.value.trim())) fieldErrors.value.email = 'Enter a valid email address.'
  if (!password.value) fieldErrors.value.password = 'Enter your password.'
  return Object.keys(fieldErrors.value).length === 0
}

async function submit() {
  if (pending.value || !validate()) return
  pending.value = true
  formError.value = ''
  try {
    await auth.login(email.value.trim(), password.value)
    void router.push(redirectTarget.value)
  } catch (err) {
    // Never reveal whether an account exists; the backend supplies generic sign-in errors.
    formError.value = isApiError(err) ? err.message : 'Could not sign in. Check your connection and try again.'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <AuthShell mode="login">
    <div class="auth-heading">
      <span class="auth-eyebrow">WELCOME BACK <span aria-hidden="true">✳</span></span>
      <h1>Your next chapter<br /><span>starts here.</span></h1>
      <p>Sign in to continue exploring your university shortlist.</p>
    </div>

    <div v-if="formError" class="auth-alert" role="alert">{{ formError }}</div>

    <form class="auth-form" novalidate :aria-busy="pending" @submit.prevent="submit">
      <div class="auth-field">
        <label for="login-email">Email address</label>
        <div class="auth-input-wrap">
          <svg class="auth-input-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></svg>
          <input id="login-email" v-model="email" type="email" inputmode="email" autocomplete="email" placeholder="you@example.com" required :aria-invalid="Boolean(fieldErrors.email)" :aria-describedby="fieldErrors.email ? 'login-email-error' : undefined" />
        </div>
        <span v-if="fieldErrors.email" id="login-email-error" class="auth-field-error">{{ fieldErrors.email }}</span>
      </div>

      <div class="auth-field">
        <label for="login-password">Password</label>
        <div class="auth-input-wrap">
          <svg class="auth-input-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          <input id="login-password" v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="Enter your password" required :aria-invalid="Boolean(fieldErrors.password)" :aria-describedby="fieldErrors.password ? 'login-password-error' : undefined" />
          <button class="auth-reveal" type="button" :aria-label="showPassword ? 'Hide password' : 'Show password'" :aria-pressed="showPassword" @click="showPassword = !showPassword">{{ showPassword ? 'Hide' : 'Show' }}</button>
        </div>
        <span v-if="fieldErrors.password" id="login-password-error" class="auth-field-error">{{ fieldErrors.password }}</span>
      </div>

      <button class="auth-submit" type="submit" :disabled="pending">
        {{ pending ? 'Signing in…' : 'Log in to my account' }}
        <span v-if="!pending" aria-hidden="true">→</span>
        <span v-else class="auth-loader" aria-hidden="true" />
      </button>
    </form>

    <div class="auth-divider"><span>NEW TO UNISHORTLIST?</span></div>
    <RouterLink class="auth-secondary" :to="signupLink">Create a free account <span aria-hidden="true">↗</span></RouterLink>
    <p class="auth-back"><RouterLink to="/">← Back to home</RouterLink></p>
  </AuthShell>
</template>

<style scoped src="./auth-form.css"></style>
