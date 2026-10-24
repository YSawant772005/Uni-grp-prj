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
watch(() => route.fullPath, () => {
  open.value = false
})

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
  if (props.variant === 'public') {
    return [
      { to: '/discover', label: 'Discover' },
      { to: '/shortlist', label: 'My shortlists' },
      { to: '/saved', label: 'Saved' },
    ]
  }
  return [
    { to: '/discover', label: 'Discover' },
    { to: '/shortlist', label: 'Shortlist' },
    { to: '/compare', label: 'Compare', badge: compare.count || undefined },
    { to: '/saved', label: 'Saved' },
  ]
})

// Signed-in navigation deliberately stays compact on wide monitors.
const primaryAppLinks = computed(() => links.value.filter((link) =>
  ['/discover', '/shortlist', '/compare', '/saved'].includes(link.to),
))
// Clicking the logo while signed in should stay in the application instead of
// unexpectedly taking a student to the public marketing/landing page.
const brandDestination = computed(() => props.variant === 'admin' ? '/admin'
  : props.variant === 'app' && auth.isAuthenticated ? '/dashboard' : '/')

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
  <header class="site-header" :class="{ 'site-header-public': variant === 'public', 'site-header-app': variant === 'app' }">
    <div class="container">
      <RouterLink :to="brandDestination" class="brand">
        <span v-if="variant === 'public'" class="public-brand-icon" aria-hidden="true">U<span>.</span></span>
        <span v-if="variant === 'app'" class="app-brand-icon" aria-hidden="true">U</span>
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
        <template v-if="variant === 'public' && route.name === 'landing'">
          <a href="#how-it-works" @click="open = false">How it works</a>
          <a href="#features" @click="open = false">Features</a>
          <a href="#destinations" @click="open = false">Destinations</a>
        </template>
        <template v-if="variant === 'app' && auth.isAuthenticated">
          <RouterLink to="/dashboard" class="app-nav-link">Dashboard</RouterLink>
          <RouterLink v-for="link in primaryAppLinks" :key="link.to" :to="link.to" class="app-nav-link">
            {{ link.label }}<span v-if="link.badge" class="nav-count">{{ link.badge }}</span>
          </RouterLink>
          <RouterLink v-if="showAdminLink" to="/admin" class="app-nav-link">Admin</RouterLink>
          <RouterLink to="/profile" class="app-profile-link"><span class="profile-nav-icon" aria-hidden="true">●</span> Profile</RouterLink>
          <button class="app-logout" type="button" @click="logout">Log out</button>
        </template>
        <template v-else>
          <RouterLink v-for="link in links" :key="link.to" :to="link.to">
            {{ link.label }}<span v-if="link.badge" class="nav-count">{{ link.badge }}</span>
          </RouterLink>
          <RouterLink v-if="showAdminLink" to="/admin">Admin</RouterLink>
          <template v-if="variant !== 'admin'">
            <template v-if="auth.isAuthenticated">
              <RouterLink to="/profile">Profile</RouterLink>
              <button class="btn btn-quiet btn-sm" type="button" @click="logout">Log out</button>
            </template>
            <template v-else>
              <RouterLink to="/login">Log in</RouterLink>
              <RouterLink to="/signup" class="btn btn-primary btn-sm">{{ variant === 'public' ? 'Get started ↗' : 'Sign up' }}</RouterLink>
            </template>
          </template>
        </template>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.site-header-public { background: #fff; border-bottom: 1px solid #e8efea; }
.site-header-public .container { min-height: 75px; max-width: 1192px; }
.site-header-public .brand { color: #17312c; font-size: 1.04rem; letter-spacing: -.03em; align-items: center; gap: 10px; }
.site-header-public .brand .tagline { display: none; }
.public-brand-icon { display: inline-grid; place-items: center; height: 35px; width: 35px; border-radius: 10px; background: #0b795a; font-weight: 900; letter-spacing: -.06em; font-size: 1.22rem; color: white; }
.public-brand-icon span { color: #a5edc7; }
.site-header-public .main-nav { gap: 8px; }
.site-header-public .main-nav a { color: #4c655a; font-weight: 600; font-size: .85rem; }
.site-header-public .main-nav a:hover { background: #edf8f2; color: #0b795a; }
.site-header-public .main-nav a.router-link-exact-active { color: #0b795a; background: #edf8f2; }
.site-header-public .main-nav a.btn-primary { background: #0b795a; border: 1px solid #0b795a; color: white; padding: 9px 18px; min-height: 40px; border-radius: 9px; }
.site-header-public .main-nav a.btn-primary:hover { background: #075c46; }
@media (max-width: 960px) {
  .site-header-public .container { padding-block: 13px; }
  .site-header-public .main-nav { gap: 5px; }
  .site-header-public .main-nav a { width: 100%; }
  .site-header-public .menu-toggle { border-color: #d1e3d9; color: #165c46; background: #f4faf5; }
}

/* Student application header — edge-to-edge container, compact nav on desktop. */
.site-header-app {
  background: #fff;
  border-bottom: 1px solid #e1ebe5;
  box-shadow: 0 2px 12px rgba(25,72,57,.035);
}
.site-header-app .container {
  width: 100%; max-width: none; margin: 0;
  min-height: 74px; padding: 0 clamp(18px, 2.15vw, 46px);
  display: flex; align-items: center; flex-wrap: nowrap; gap: 22px;
}
.site-header-app .brand {
  display: flex; align-items: center; gap: 10px;
  flex: none; margin-right: auto; font-size: 1.05rem;
  font-weight: 850; letter-spacing: -.035em; color: #174538;
}
.site-header-app .brand .tagline { display: none; }
.app-brand-icon {
  display: grid; place-items: center; width: 38px; height: 38px;
  border-radius: 11px; background: #09805c; color: #fff;
  font-size: 1.2rem; font-weight: 900;
}
.site-header-app .main-nav {
  display: flex; align-items: center; flex-wrap: nowrap;
  gap: clamp(2px, .45vw, 8px); margin-left: auto; min-width: 0;
}
.site-header-app .main-nav > a,
.site-header-app .main-nav > button,
.site-header-app .nav-more > summary {
  display: inline-flex; align-items: center; justify-content: center;
  gap: 6px; padding: 10px 12px; border-radius: 10px;
  color: #486b60; font: inherit; font-weight: 740; font-size: .85rem;
  line-height: 1.3; text-decoration: none; white-space: nowrap; cursor: pointer;
}
.site-header-app .main-nav > a:hover,
.site-header-app .nav-more > summary:hover,
.site-header-app .main-nav > button:hover { color: #087e59; background: #eef8f2; }
.site-header-app .main-nav > a.router-link-active { color: #087e59; background: #eaf6ef; }
.site-header-app .app-profile-link {
  color: #087e59 !important; border: 1px solid #cee9db;
  background: #f2faf6; margin-left: 4px;
}
.profile-nav-icon { font-size: .7rem; color: #10a577; }
.site-header-app .main-nav > .app-logout {
  border: 1px solid #dfebe4; background: #fff; color: #4c665b;
}
.site-header-app .menu-toggle { display: none; }
.site-header-app .nav-more { position: relative; flex: none; }
.site-header-app .nav-more > summary { list-style: none; user-select: none; }
.site-header-app .nav-more > summary::-webkit-details-marker { display: none; }
.site-header-app .nav-more[open] > summary { background: #eaf6ef; color: #087e59; }
.site-header-app .nav-more-menu {
  position: absolute; z-index: 45; right: 0; top: calc(100% + 9px);
  min-width: 205px; padding: 8px; background: #fff;
  border: 1px solid #dcece3; border-radius: 13px;
  box-shadow: 0 16px 38px rgba(25,72,57,.13);
  display: grid; gap: 2px;
}
.site-header-app .nav-more-menu a {
  display: block; padding: 11px 12px; border-radius: 8px;
  color: #466c5f; font-size: .86rem; font-weight: 680; text-decoration: none;
}
.site-header-app .nav-more-menu a:hover,
.site-header-app .nav-more-menu a.router-link-active { background: #edf8f2; color: #087e59; }
@media (max-width: 1190px) {
  .site-header-app .container { min-height: 67px; flex-wrap: wrap; gap: 8px; padding-block: 10px; }
  .site-header-app .menu-toggle {
    display: inline-flex; align-items: center; justify-content: center;
    margin-left: auto; border: 1px solid #d6e8de; border-radius: 9px;
    background: #f2faf6; color: #117756; font-size: .83rem; font-weight: 780;
  }
  .site-header-app .main-nav { display: none; width: 100%; margin: 4px 0 0; }
  .site-header-app .main-nav.open {
    display: grid; grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 5px; padding: 11px; border-radius: 12px;
    border: 1px solid #e1ebe4; background: #fbfefc;
  }
  .site-header-app .main-nav > a,
  .site-header-app .main-nav > button,
  .site-header-app .nav-more > summary {
    width: 100%; min-height: 40px; justify-content: flex-start;
    padding: 10px 12px; text-align: left;
  }
  .site-header-app .nav-more { width: 100%; }
  .site-header-app .nav-more-menu {
    position: static; box-shadow: none; min-width: 0; margin-top: 4px;
  }
  .site-header-app .app-profile-link { margin-left: 0; }
}
@media (max-width: 620px) {
  .site-header-app .container { padding-inline: 14px; }
  .site-header-app .main-nav.open { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .site-header-app .nav-more { grid-column: 1 / -1; }
}

/* Public header: full-width rather than a visibly narrow center strip. */
.site-header-public .container {
  width: 100%; max-width: none;
  padding-inline: clamp(18px, 2.15vw, 46px);
}
</style>
