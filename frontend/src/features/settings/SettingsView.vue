<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { humanize } from '../../utils/format'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

async function logout() {
  await auth.logout()
  ui.push('You are signed out.', 'success')
  void router.push('/')
}
</script>

<template>
  <div class="stack" style="max-width: 720px">
    <div>
      <h1>Settings</h1>
      <p class="muted small" style="margin: 0">Account, session and data controls.</p>
    </div>

    <section class="card">
      <h2>Account</h2>
      <dl class="kv">
        <dt>Email</dt>
        <dd>{{ auth.user?.email ?? '—' }}</dd>
        <dt>Display name</dt>
        <dd>{{ auth.user?.display_name ?? 'Not set' }}</dd>
        <dt>Roles</dt>
        <dd>
          <span v-for="role in auth.roleKeys" :key="role" class="badge badge-neutral" style="margin-right: 6px">
            {{ humanize(role) }}
          </span>
        </dd>
      </dl>
      <p class="small muted" style="margin: 10px 0 0">
        Roles are granted by an administrator. A reviewer or admin role also unlocks the
        <RouterLink to="/admin">admin console</RouterLink>, where every action is audit-logged.
      </p>
    </section>

    <section class="card">
      <h2>Session</h2>
      <p class="small muted" style="margin-top: 0">
        Sessions use HttpOnly cookies - no tokens are stored in this browser. Signing out invalidates
        the session on the server.
      </p>
      <button class="btn" type="button" @click="logout">Log out</button>
    </section>

    <section class="card">
      <h2>Your data</h2>
      <ul class="small stack-sm" style="padding-left: 18px">
        <li>View everything we store about you on the <RouterLink to="/profile">profile page</RouterLink>.</li>
        <li>Saved programs, comparisons and scenarios live in your account and are deletable from their pages.</li>
        <li>
          Onboarding drafts are kept only in this browser and can be cleared by removing site data.
        </li>
      </ul>
      <p class="small muted" style="margin: 8px 0 0">
        Account deletion and data export are not enabled in this release - see the
        <RouterLink to="/privacy">privacy page</RouterLink> for how they will work.
      </p>
    </section>

    <section class="card">
      <h2>About this build</h2>
      <p class="small muted" style="margin: 0">
        Evidence-first shortlisting tool. No third-party analytics, no ads, no data sale. Facts show
        their source and status; unknown values are never shown as zero. Read the
        <RouterLink to="/terms">terms and limitations</RouterLink>.
      </p>
    </section>
  </div>
</template>
