<script setup lang="ts">
import CompareTray from '../components/CompareTray.vue'
import TheFooter from '../components/TheFooter.vue'
import TheHeader from '../components/TheHeader.vue'
</script>

<template>
  <div class="shell shell-app">
    <TheHeader variant="app" />
    <main id="main">
      <div class="container page app-workspace">
        <RouterView />
      </div>
    </main>
    <TheFooter />
    <CompareTray />
  </div>
</template>

<style scoped>
/* App pages should use the full available desktop width.
   Public/auth/onboarding pages have separate layouts and remain unchanged. */
.shell-app { background: #f6f9f8; }
.app-workspace {
  width: 100%;
  max-width: none;
  margin: 0;
  min-width: 0;
  padding: 28px clamp(18px, 2.15vw, 46px) 88px;
}
.shell-app :deep(.site-header-app .container),
.shell-app :deep(.site-footer .container) {
  width: 100%;
  max-width: none;
  margin-inline: 0;
  padding-inline: clamp(18px, 2.15vw, 46px);
}
@media (max-width: 760px) {
  .app-workspace { padding: 20px 14px 62px; }
  .shell-app :deep(.site-header-app .container),
  .shell-app :deep(.site-footer .container) { padding-inline: 14px; }
}
</style>
