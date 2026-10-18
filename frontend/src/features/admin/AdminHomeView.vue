<script setup lang="ts">
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { formatDateTime } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const auth = useAuthStore()

const queueState = useAsync(() => admin.reviewQueue({ page_size: 5 }), { immediate: true })
const jobsState = useAsync(
  () => (auth.isAdmin ? admin.jobs({ page_size: 5 }) : Promise.resolve(null)),
  { immediate: true },
)
</script>

<template>
  <div class="stack">
    <div>
      <h1>Admin console</h1>
      <p class="muted small" style="margin: 0">
        Evidence review, source registry, ingestion jobs and the audit log. Every action here is
        recorded with your user id, the request id and before/after state - the log is append-only.
        Hiding a button in this UI is never the security boundary; the backend enforces roles on
        every request.
      </p>
    </div>

    <div class="grid">
      <RouterLink to="/admin/review" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Review queue</h3>
        <p class="small muted" style="margin: 0">
          Facts waiting for human verification: candidates, conflicts and stale values. Approve,
          reject or request better evidence - each decision is versioned.
        </p>
        <p v-if="queueState.data.value" class="small" style="margin: 8px 0 0">
          <strong>{{ queueState.data.value.total_items }}</strong> facts currently in the queue
        </p>
      </RouterLink>

      <RouterLink to="/admin/sources" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Source registry</h3>
        <p class="small muted" style="margin: 0">
          Sources with their authority tier, allowed-use policy and refresh intervals. Only sources
          whose policy permits automated fetching can be refreshed.
        </p>
      </RouterLink>

      <RouterLink v-if="auth.isAdmin" to="/admin/jobs" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Ingestion jobs</h3>
        <p class="small muted" style="margin: 0">
          Discover, fetch, parse, normalize, validate and refresh runs with counters and errors.
          Payloads are never shown - only status and validation errors.
        </p>
        <p v-if="jobsState.data.value" class="small" style="margin: 8px 0 0">
          <strong>{{ jobsState.data.value.total_items }}</strong> jobs recorded
        </p>
      </RouterLink>

      <RouterLink v-if="auth.isAdmin" to="/admin/audit" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Audit log</h3>
        <p class="small muted" style="margin: 0">
          Append-only record of every reviewer action and administrative change, with request ids
          for support.
        </p>
      </RouterLink>
    </div>

    <!-- live queue preview -->
    <section class="stack">
      <h2>Needs attention now</h2>
      <AsyncState
        :loading="queueState.loading.value"
        :error="queueState.error.value"
        :empty="!queueState.data.value?.items.length"
        empty-title="Queue is clear"
        empty-hint="No facts are waiting for review - new candidates arrive from validated ingestion jobs."
        @retry="queueState.run"
      >
        <div v-if="queueState.data.value?.items.length" class="stack-sm">
          <RouterLink
            v-for="item in queueState.data.value.items"
            :key="item.fact_id"
            :to="`/admin/review/${item.fact_id}`"
            class="card card-flat row-between"
            style="color: inherit"
          >
            <div>
              <strong>{{ item.entity_label ?? item.entity_type }} · {{ item.fact_key }}</strong>
              <div class="small muted">
                {{ item.entity_type }} · {{ item.version_count }} version(s) ·
                {{ item.evidence_count }} evidence
                <template v-if="item.last_review"> · last: {{ item.last_review.action }} {{ formatDateTime(item.last_review.created_at) }}</template>
              </div>
            </div>
            <StatusBadge :status="item.current_status" />
          </RouterLink>
        </div>
      </AsyncState>
    </section>
  </div>
</template>
