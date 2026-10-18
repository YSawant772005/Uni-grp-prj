<script setup lang="ts">
import CompareTray from '../components/CompareTray.vue'
import TheFooter from '../components/TheFooter.vue'
import TheHeader from '../components/TheHeader.vue'
</script>

<template>
  <div class="shell">
    <TheHeader variant="app" />
    <main id="main">
      <div class="container page">
        <RouterView />
      </div>
    </main>
    <TheFooter />
    <CompareTray />
  </div>
</template>
