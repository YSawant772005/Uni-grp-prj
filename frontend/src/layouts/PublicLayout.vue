<script setup lang="ts">
import TheFooter from '../components/TheFooter.vue'
import TheHeader from '../components/TheHeader.vue'
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main">Skip to main content</a>
    <TheHeader variant="public" />
    <main id="main">
      <RouterView />
    </main>
    <TheFooter />
  </div>
</template>

<style scoped>
.skip-link {
  position: absolute;
  left: -999px;
  top: 0;
  background: var(--paper);
  padding: 8px 12px;
  z-index: 100;
}
.skip-link:focus {
  left: 8px;
}
</style>
