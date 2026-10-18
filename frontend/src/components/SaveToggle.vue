<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useSavedStore } from '../stores/saved'
import { useUiStore } from '../stores/ui'

/** Save/unsave toggle; prompts login only when the action needs persistence. */
const props = defineProps<{ programId: string }>()

const auth = useAuthStore()
const saved = useSavedStore()
const ui = useUiStore()
const router = useRouter()
const route = useRoute()
const pending = ref(false)

onMounted(() => void saved.ensureLoaded())

const isSaved = computed(() => saved.isSaved(props.programId))

async function toggle() {
  if (!auth.isAuthenticated) {
    void router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  pending.value = true
  try {
    const wasSaved = isSaved.value
    const ok = await saved.toggle(props.programId)
    if (ok) ui.push(wasSaved ? 'Removed from your saved programs.' : 'Saved to your shortlist.', 'success')
  } catch (err) {
    ui.pushError(err)
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <button
    class="btn btn-sm"
    type="button"
    :aria-pressed="isSaved"
    :disabled="pending"
    @click="toggle"
  >
    {{ isSaved ? 'Saved ✓' : 'Save' }}
  </button>
</template>
