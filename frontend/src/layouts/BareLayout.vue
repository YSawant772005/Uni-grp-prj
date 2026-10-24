<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TheHeader from '../components/TheHeader.vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isOnboarding = computed(() => route.name === 'onboarding' || route.name === 'processing-profile')
const isFullWidthPage = computed(() =>
  route.name === 'login' || route.name === 'signup' || isOnboarding.value,
)

async function logout() {
  await auth.logout()
  void router.push('/')
}
</script>

<template>
  <div class="shell">
    <a class="bare-skip-link" href="#main">Skip to main content</a>
    <template v-if="isOnboarding">
      <header class="onboarding-header">
        <div class="onboarding-header-inner" style="width: 100% !important; max-width: none !important; margin: 0 !important; padding-inline: clamp(14px, 2.5vw, 44px) !important; box-sizing: border-box !important;">
          <RouterLink class="onboarding-brand" to="/" aria-label="UniShortlist home">
            <span class="onboarding-brand-icon" aria-hidden="true">U</span>
            <span>UniShortlist</span>
          </RouterLink>
          <span class="onboarding-header-label">Student profile setup</span>
          <nav class="onboarding-header-nav" aria-label="Profile setup navigation">
            <RouterLink to="/discover">Exit setup</RouterLink>
            <button type="button" @click="logout">Log out</button>
          </nav>
        </div>
      </header>
    </template>
    <TheHeader v-else variant="public" />
    <main id="main" class="bare-main" :class="{ 'bare-main-full': isFullWidthPage }">
      <RouterView v-if="isFullWidthPage" />
      <div v-else class="container bare-container"><RouterView /></div>
    </main>
  </div>
</template>

<style scoped>
.bare-main { flex: 1; padding: 40px 0 64px; display: flex; align-items: flex-start; }
.bare-container { width: 100%; max-width: 560px; }
.bare-main-full { display: block; width: 100%; min-width: 0; padding: 0; }
.bare-skip-link { position: absolute; left: -999px; top: 0; padding: 9px 14px; background: white; z-index: 100; }
.bare-skip-link:focus { left: 8px; }
.onboarding-header { width: 100%; background: #fff; border-bottom: 1px solid #e4ebea; }
.onboarding-header-inner { display: flex; align-items: center; gap: 25px; width: min(100% - 40px, 1180px); min-height: 72px; margin: auto; }
.onboarding-brand { display: inline-flex; align-items: center; gap: 10px; white-space: nowrap; color: #16382e; font-size: 1.04rem; font-weight: 850; letter-spacing: -.025em; }
.onboarding-brand:hover { text-decoration: none; }
.onboarding-brand-icon { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; background: #087955; color: white; font-size: 1.12rem; font-weight: 900; }
.onboarding-header-label { color: #899a9c; font-size: .84rem; padding-left: 23px; border-left: 1px solid #e0e8e7; }
.onboarding-header-nav { display: flex; gap: 15px; align-items: center; margin-left: auto; }
.onboarding-header-nav a, .onboarding-header-nav button { white-space: nowrap; color: #416b61; font-size: .86rem; font-weight: 650; }
.onboarding-header-nav button { padding: 8px 14px; background: #ecf7f1; border: 1px solid #d5e9dd; border-radius: 9px; cursor: pointer; color: #0d7755; }
.onboarding-header-nav button:hover { background: #dbf0e4; }
@media (max-width: 570px) {
  .onboarding-header-inner { gap: 10px; width: min(100% - 24px, 1180px); min-height: 65px; }
  .onboarding-header-label { display: none; }
  .onboarding-brand { font-size: .96rem; }
  .onboarding-brand-icon { width: 32px; height: 32px; }
  .onboarding-header-nav { gap: 9px; }
  .onboarding-header-nav a, .onboarding-header-nav button { font-size: .78rem; }
  .onboarding-header-nav button { padding: 7px 10px; }
}
</style>
