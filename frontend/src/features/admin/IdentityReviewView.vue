<script setup lang="ts">
import { reactive, watch } from 'vue'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { formatDateTime } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'

const status = reactive({ value: 'pending' })
const queue = useAsync(() => admin.identityReviews({ status: status.value, page_size: 100 }), {
  immediate: true,
})
watch(() => status.value, () => void queue.run())
const decisions = reactive<Record<string, { universityId: string; reason: string }>>({})
const busy = reactive<Record<string, boolean>>({})
const errors = reactive<Record<string, string>>({})

function decision(reviewId: string) {
  return (decisions[reviewId] ??= { universityId: '', reason: '' })
}

async function act(reviewId: string, action: 'approve' | 'reject' | 'defer') {
  const form = decision(reviewId)
  if (!form.reason.trim() || (action === 'approve' && !form.universityId.trim())) return
  busy[reviewId] = true
  errors[reviewId] = ''
  try {
    if (action === 'approve') {
      await admin.approveIdentityReview(reviewId, form.universityId.trim(), form.reason.trim())
    } else if (action === 'reject') {
      await admin.rejectIdentityReview(reviewId, form.reason.trim())
    } else {
      await admin.deferIdentityReview(reviewId, form.reason.trim())
    }
    await queue.run()
  } catch (error) {
    errors[reviewId] = error instanceof Error ? error.message : 'Unable to save this decision.'
  } finally {
    busy[reviewId] = false
  }
}
</script>

<template>
  <div class="stack">
    <div>
      <h1>Institution identity review</h1>
      <p class="muted small" style="margin: 0">
        Compare source identifiers and evidence before linking a source record. Approving adds the
        source identity to the selected institution; it does not merge or delete institutions.
      </p>
    </div>

    <section class="card field" style="max-width: 320px">
      <label for="identity-review-status">Review state</label>
      <select id="identity-review-status" v-model="status.value">
        <option value="pending">Pending</option>
        <option value="approved">Approved links</option>
        <option value="rejected">Rejected</option>
        <option value="deferred">Deferred</option>
      </select>
    </section>

    <AsyncState
      :loading="queue.loading.value"
      :error="queue.error.value"
      :empty="!queue.data.value?.items.length"
      empty-title="No identity candidates"
      empty-hint="Weak or conflicting source identity candidates will appear here after ingestion."
      @retry="queue.run"
    >
      <section v-for="item in queue.data.value?.items" :key="item.id" class="card stack">
        <div class="row-between">
          <div>
            <h2 style="margin: 0">{{ item.candidate.name ?? 'Unnamed source record' }}</h2>
            <p class="small muted" style="margin: 4px 0 0">
              {{ item.source?.name ?? 'Unknown source' }} · {{ item.candidate.country_code ?? 'Country unknown' }}
              · retrieved {{ item.source_document ? formatDateTime(item.source_document.retrieved_at) : 'unknown' }}
            </p>
          </div>
          <a v-if="item.source_document" :href="item.source_document.url" target="_blank" rel="noopener noreferrer">
            Open source
          </a>
        </div>

        <dl class="grid">
          <div>
            <dt class="small muted">Review state</dt>
            <dd class="small">{{ item.status }}<template v-if="item.reviewed_at"> · {{ formatDateTime(item.reviewed_at) }}</template></dd>
          </div>
          <div>
            <dt class="small muted">Source key</dt>
            <dd class="mono small">{{ item.external_key }}</dd>
          </div>
          <div>
            <dt class="small muted">Identifiers</dt>
            <dd class="mono small">{{ JSON.stringify(item.candidate.identifiers ?? {}) }}</dd>
          </div>
          <div>
            <dt class="small muted">Website / aliases</dt>
            <dd class="small">{{ item.candidate.website ?? 'Unknown' }} · {{ (item.candidate.aliases ?? []).join(', ') || 'No aliases' }}</dd>
          </div>
          <div>
            <dt class="small muted">Suggested institution</dt>
            <dd class="small">
              {{ item.suggested_university?.name ?? 'No strong candidate' }}
              <span v-if="item.suggested_university" class="mono"> · {{ item.suggested_university.id }}</span>
            </dd>
          </div>
          <div v-if="item.source">
            <dt class="small muted">Publisher / use policy</dt>
            <dd class="small">{{ item.source.owner_or_publisher ?? 'Publisher unknown' }} · {{ item.source.allowed_use_policy }}</dd>
            <a v-if="item.source.terms_url" :href="item.source.terms_url" target="_blank" rel="noopener noreferrer">Source terms</a>
            <p v-if="item.source.license_notes" class="small muted">{{ item.source.license_notes }}</p>
          </div>
        </dl>

        <details v-if="item.source_document?.content_excerpt">
          <summary>Retrieved source excerpt</summary>
          <p class="small" style="white-space: pre-wrap">{{ item.source_document.content_excerpt }}</p>
          <p class="small muted">HTTP {{ item.source_document.http_status ?? 'unknown' }} · {{ item.source_document.fetch_status ?? 'fetch state unknown' }}</p>
        </details>

        <details v-if="item.suggested_university">
          <summary>Canonical identity evidence</summary>
          <p class="small">Official website: <a v-if="item.suggested_university.official_website_url" :href="item.suggested_university.official_website_url" target="_blank" rel="noopener noreferrer">{{ item.suggested_university.official_website_url }}</a><span v-else>unknown</span></p>
          <ul class="small">
            <li v-for="identifier in item.suggested_university.accepted_identifiers ?? []" :key="`${identifier.namespace}:${identifier.value}:${identifier.source_key}`">
              {{ identifier.namespace }}: <span class="mono">{{ identifier.value }}</span> · {{ identifier.scope }} · {{ identifier.source_key }}
            </li>
          </ul>
        </details>

        <ul class="small">
          <li v-for="issue in item.identity_review" :key="`${issue.code}-${issue.message}`">
            {{ issue.code }}: {{ issue.message }}
          </li>
        </ul>

        <details v-if="item.candidate.program_candidates?.length" open>
          <summary>Source programme candidates ({{ item.candidate.program_candidate_count }})</summary>
          <ul class="small">
            <li v-for="program in item.candidate.program_candidates" :key="program.external_key">
              {{ program.title }} <span class="muted">· {{ program.discipline ?? 'discipline unavailable' }}</span>
            </li>
          </ul>
        </details>

        <details v-if="item.events?.length || item.review_reason">
          <summary>Review history</summary>
          <p v-if="item.review_reason" class="small">Current reason: {{ item.review_reason }}</p>
          <ul class="small">
            <li v-for="event in item.events ?? []" :key="event.id">
              {{ event.action }} · {{ formatDateTime(event.created_at) }} · {{ event.reason }} · reviewer {{ event.actor_user_id }}
            </li>
          </ul>
        </details>

        <div v-if="item.status === 'pending'" class="grid">
          <div class="field">
            <label :for="`target-${item.id}`">University UUID to link</label>
            <input :id="`target-${item.id}`" v-model="decision(item.id).universityId" class="mono" />
          </div>
          <div class="field">
            <label :for="`reason-${item.id}`">Decision reason</label>
            <input :id="`reason-${item.id}`" v-model="decision(item.id).reason" />
          </div>
        </div>
        <p v-if="errors[item.id]" class="error" role="alert">{{ errors[item.id] }}</p>
        <div v-if="item.status === 'pending'" class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn-primary" :disabled="busy[item.id] || !decision(item.id).reason.trim() || !decision(item.id).universityId.trim()" @click="act(item.id, 'approve')">
            Approve link
          </button>
          <button class="btn" :disabled="busy[item.id] || !decision(item.id).reason.trim()" @click="act(item.id, 'reject')">
            Reject
          </button>
          <button class="btn" :disabled="busy[item.id] || !decision(item.id).reason.trim()" @click="act(item.id, 'defer')">
            Defer
          </button>
        </div>
      </section>
    </AsyncState>
  </div>
</template>
