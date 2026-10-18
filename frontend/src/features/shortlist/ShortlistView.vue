<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { profile as profileApi, recommendations } from '../../services/api/account'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import { formatDate, formatNumber, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'

const router = useRouter()
const ui = useUiStore()

const runsState = useAsync(() => recommendations.listRuns(), { immediate: true })
const profileState = useAsync(() => profileApi.completeness(), { immediate: true })

const needsProfile = ref(false)
onMounted(async () => {
  const completeness = await profileState.run()
  needsProfile.value = Boolean(completeness && !completeness.required_complete)
})

const creating = ref(false)

async function createRun() {
  if (creating.value) return
  creating.value = true
  try {
    const run = await recommendations.createRun()
    ui.push('Shortlist generated. Existing runs are kept unchanged.', 'success')
    void router.push(`/shortlist/${run.run_id}`)
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: '/shortlist' } })
      return
    }
    ui.pushError(err)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="stack">
    <div class="row-between">
      <div>
        <h1>Your shortlists</h1>
        <p class="muted small" style="margin: 0">
          Each run is a reproducible snapshot: it keeps the ruleset version and your profile inputs
          from the moment it was generated. Re-running creates a new run - old results stay.
        </p>
      </div>
      <button class="btn btn-primary" type="button" :disabled="creating" @click="createRun">
        {{ creating ? 'Generating…' : 'New shortlist run' }}
      </button>
    </div>

    <div v-if="needsProfile" class="banner banner-warn">
      Your profile is missing required answers - a run now would leave gaps in eligibility and cost
      results. <RouterLink to="/onboarding">Finish onboarding</RouterLink> for better output.
    </div>

    <AsyncState
      :loading="runsState.loading.value"
      :error="runsState.error.value"
      :empty="!runsState.data.value?.items.length"
      empty-title="No shortlist runs yet"
      empty-hint="Generate a run to see Ambitious, Target and Safer-fit groups with explanations."
      @retry="runsState.run"
    >
      <div v-if="runsState.data.value?.items.length" class="stack">
        <RouterLink
          v-for="run in runsState.data.value.items"
          :key="run.run_id"
          :to="`/shortlist/${run.run_id}`"
          class="card"
          style="display: block; color: inherit"
        >
          <div class="row-between">
            <div>
              <strong>Run {{ formatDate(run.created_at) }}</strong>
              <div class="small muted">
                ruleset {{ run.ruleset_version ?? 'unknown' }} · {{ humanize(run.status) }}
              </div>
            </div>
            <div class="row" v-if="run.result_summary">
              <span v-for="(count, tier) in run.result_summary" :key="tier" class="badge badge-neutral">
                {{ humanize(tier) }}: {{ formatNumber(count, 0) }}
              </span>
            </div>
          </div>
        </RouterLink>
      </div>
    </AsyncState>
  </div>
</template>
