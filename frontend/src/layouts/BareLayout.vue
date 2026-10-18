<script setup lang="ts">
import TheHeader from '../components/TheHeader.vue'
</script>

<template>
  <div class="shell">
    <TheHeader variant="public" />
    <main id="main" class="bare-main">
      <div class="container">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
.bare-main {
  flex: 1;
  padding: 40px 0 64px;
  display: flex;
  align-items: flex-start;
}
.bare-main > .container {
  width: 100%;
  max-width: 560px;
}
</style>
