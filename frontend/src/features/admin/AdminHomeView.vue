<script setup lang="ts">
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { formatDateTime } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const auth = useAuthStore()

const institutions = useAsync(() => admin.institutionReviews({ page_size: 5 }), { immediate: true })
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
      <RouterLink to="/admin/identity-reviews" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Institution identity review</h3>
        <p class="small muted" style="margin: 0">
          Resolve ambiguous source identifiers and weak match suggestions. Approved links keep
          institutions separate and record reviewer evidence.
        </p>
      </RouterLink>

      <RouterLink to="/admin/institution-reviews" class="card" style="color: inherit">
        <h3 style="margin-top: 0">University and Master’s review</h3>
        <p class="small muted" style="margin: 0">
          Review each canonical university once, with its accepted identifiers, source facts,
          official website evidence and associated programme records grouped together.
        </p>
      </RouterLink>

      <RouterLink to="/admin/program-publication" class="card" style="color: inherit">
        <h3 style="margin-top: 0">Program publication review</h3>
        <p class="small muted" style="margin: 0">
          Review Master's program identity and source evidence before making a candidate visible in discovery.
          Publishing a program does not verify its admission, fee, or deadline facts.
        </p>
      </RouterLink>

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

    <section class="stack">
      <h2>University evidence collection</h2>
      <p v-if="institutions.data.value" class="small muted">{{ institutions.data.value.stage_counts.ready_for_review ?? 0 }} ready for human review · {{ institutions.data.value.stage_counts.discovery ?? 0 }} awaiting programme discovery · {{ institutions.data.value.stage_counts.evidence_collection ?? 0 }} collecting evidence</p>
      <AsyncState :loading="institutions.loading.value" :error="institutions.error.value" :empty="!institutions.data.value?.items.length"
        empty-title="No pending university packages" @retry="institutions.run">
        <RouterLink v-for="item in institutions.data.value?.items" :key="item.university_id" :to="`/admin/institution-reviews/${item.university_id}`" class="card card-flat row-between" style="color: inherit">
          <div><strong>{{ item.name }}</strong><p class="small muted">{{ item.country_code }} · {{ item.program_count }} named programme records</p></div>
          <StatusBadge :status="item.workflow_stage" />
        </RouterLink>
      </AsyncState>
    </section>

    <details>
      <summary>Technical fact review</summary>
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
    </details>
  </div>
</template>
