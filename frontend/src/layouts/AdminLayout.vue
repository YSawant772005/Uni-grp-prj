<script setup lang="ts">
import TheHeader from '../components/TheHeader.vue'
</script>

<template>
  <div class="shell">
    <TheHeader variant="admin" />
    <main id="main">
      <div class="container page">
        <RouterView />
      </div>
    </main>
  </div>
</template>
