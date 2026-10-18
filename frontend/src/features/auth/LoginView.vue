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
const pending = ref(false)
const formError = ref('')
const fieldErrors = ref<{ email?: string; password?: string }>({})

const redirectTarget = computed(() => safeRedirect(route.query.redirect) ?? '/discover')

function validate(): boolean {
  fieldErrors.value = {}
  if (!email.value.trim()) fieldErrors.value.email = 'Enter your email address.'
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
    // server returns a generic 401 message; never reveal whether an email exists
    formError.value = isApiError(err) ? err.message : 'Could not sign in. Check your connection and try again.'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="card">
    <h1>Log in</h1>
    <p class="muted small">Continue your shortlist where you left it.</p>

    <div v-if="formError" class="error-summary" role="alert">{{ formError }}</div>

    <form novalidate @submit.prevent="submit">
      <div class="field">
        <label for="login-email">Email</label>
        <input
          id="login-email"
          v-model="email"
          type="email"
          autocomplete="email"
          required
          :aria-invalid="Boolean(fieldErrors.email)"
          :aria-describedby="fieldErrors.email ? 'login-email-error' : undefined"
        />
        <span v-if="fieldErrors.email" id="login-email-error" class="field-error">{{ fieldErrors.email }}</span>
      </div>

      <div class="field">
        <label for="login-password">Password</label>
        <input
          id="login-password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          :aria-invalid="Boolean(fieldErrors.password)"
          :aria-describedby="fieldErrors.password ? 'login-password-error' : undefined"
        />
        <span v-if="fieldErrors.password" id="login-password-error" class="field-error">
          {{ fieldErrors.password }}
        </span>
      </div>

      <button class="btn btn-primary" type="submit" :disabled="pending" style="width: 100%">
        {{ pending ? 'Signing in…' : 'Log in' }}
      </button>
    </form>

    <p class="small" style="margin-top: 14px">
      New here?
      <RouterLink :to="{ path: '/signup', query: { redirect: String(route.query.redirect ?? '') } }">
        Create an account
      </RouterLink>
    </p>
  </div>
</template>
