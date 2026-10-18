<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useCompareStore } from '../stores/compare'
import { useUiStore } from '../stores/ui'

/**
 * One header for all layouts: public (anonymous), app (student) and admin.
 * Hiding links is a convenience only - authorization is enforced server-side.
 */
const props = withDefaults(defineProps<{ variant?: 'public' | 'app' | 'admin' }>(), {
  variant: 'public',
})

const auth = useAuthStore()
const compare = useCompareStore()
const ui = useUiStore()
const router = useRouter()
const route = useRoute()
const open = ref(false)

// never leave the mobile menu open after navigation
watch(() => route.fullPath, () => (open.value = false))

interface NavLink {
  to: string
  label: string
  badge?: number
}

const links = computed<NavLink[]>(() => {
  if (props.variant === 'admin') {
    const items: NavLink[] = [
      { to: '/admin', label: 'Overview' },
      { to: '/admin/review', label: 'Review queue' },
      { to: '/admin/sources', label: 'Sources' },
    ]
    if (auth.isAdmin) {
      items.push({ to: '/admin/jobs', label: 'Jobs' }, { to: '/admin/audit', label: 'Audit log' })
    }
    return items
  }
  if (!auth.isAuthenticated) {
    return [{ to: '/discover', label: 'Explore programs' }]
  }
  return [
    { to: '/discover', label: 'Discover' },
    { to: '/shortlist', label: 'Shortlist' },
    { to: '/compare', label: 'Compare', badge: compare.count || undefined },
    { to: '/saved', label: 'Saved' },
    { to: '/finance', label: 'Finance' },
    { to: '/scholarships', label: 'Scholarships' },
    { to: '/loans', label: 'Loans' },
    { to: '/roi', label: 'ROI' },
    { to: '/destinations', label: 'Destinations' },
  ]
})

const showAdminLink = computed(() => auth.isReviewer && props.variant !== 'admin')

async function logout() {
  await auth.logout()
  ui.push('You are signed out.', 'info')
  void router.push('/')
}
</script>

<template>
  <div v-if="variant === 'admin'" class="admin-banner">
    <div class="container row-between">
      <span>Admin console - every action here is recorded in the audit log.</span>
      <RouterLink to="/">Open the app</RouterLink>
    </div>
  </div>
  <header class="site-header">
    <div class="container">
      <RouterLink to="/" class="brand">
        <span>UniShortlist</span>
        <span class="tagline">{{ variant === 'admin' ? 'admin' : 'evidence-first shortlisting' }}</span>
      </RouterLink>
      <button
        class="btn btn-quiet menu-toggle"
        type="button"
        :aria-expanded="open"
        aria-controls="main-nav"
        @click="open = !open"
      >
        Menu
      </button>
      <nav id="main-nav" class="main-nav" :class="{ open }" :aria-label="variant === 'admin' ? 'Admin' : 'Main'">
        <RouterLink v-for="link in links" :key="link.to" :to="link.to">
          {{ link.label }}<span v-if="link.badge" class="nav-count">{{ link.badge }}</span>
        </RouterLink>
        <RouterLink v-if="showAdminLink" to="/admin">Admin</RouterLink>
        <template v-if="variant !== 'admin'">
          <template v-if="auth.isAuthenticated">
            <RouterLink to="/profile">Profile</RouterLink>
            <RouterLink to="/settings">Settings</RouterLink>
            <button class="btn btn-quiet btn-sm" type="button" @click="logout">Log out</button>
          </template>
          <template v-else>
            <RouterLink to="/login">Log in</RouterLink>
            <RouterLink to="/signup" class="btn btn-primary btn-sm">Sign up</RouterLink>
          </template>
        </template>
      </nav>
    </div>
  </header>
</template>
