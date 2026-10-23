<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { admin } from '../../services/api/admin'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { formatDateTime, humanize, valuePreview } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const sourceId = computed(() => String(route.params.sourceId))
const sourceState = useAsync(() => admin.source(sourceId.value), { immediate: true })
const source = computed(() => sourceState.data.value)

// ----------------------------------------------------------------- edit form

const form = reactive({
  name: '',
  authority_tier: '3',
  owner_or_publisher: '',
  terms_url: '',
  rate_limit_notes: '',
  license_notes: '',
  refresh_interval_hours: '',
  enabled: true,
})

watch(
  source,
  (value) => {
    if (!value) return
    form.name = value.name
    form.authority_tier = String(value.authority_tier)
    form.owner_or_publisher = value.owner_or_publisher ?? ''
    form.terms_url = value.terms_url ?? ''
    form.rate_limit_notes = value.rate_limit_notes ?? ''
    form.license_notes = value.license_notes ?? ''
    form.refresh_interval_hours = value.refresh_interval_hours !== null ? String(value.refresh_interval_hours) : ''
    form.enabled = value.enabled
  },
  { immediate: true },
)

const dirty = computed(() => {
  const value = source.value
  if (!value) return false
  return (
    form.name !== value.name ||
    Number(form.authority_tier) !== value.authority_tier ||
    form.owner_or_publisher !== (value.owner_or_publisher ?? '') ||
    form.terms_url !== (value.terms_url ?? '') ||
    form.rate_limit_notes !== (value.rate_limit_notes ?? '') ||
    form.license_notes !== (value.license_notes ?? '') ||
    (form.refresh_interval_hours ? Number(form.refresh_interval_hours) : null) !== value.refresh_interval_hours ||
    form.enabled !== value.enabled
  )
})

const saving = ref(false)
const saveError = ref('')

async function save() {
  if (saving.value || !dirty.value) return
  saving.value = true
  saveError.value = ''
  try {
    await admin.patchSource(sourceId.value, {
      name: form.name.trim(),
      authority_tier: Number(form.authority_tier),
      owner_or_publisher: form.owner_or_publisher.trim() || null,
      terms_url: form.terms_url.trim() || null,
      rate_limit_notes: form.rate_limit_notes.trim() || null,
      license_notes: form.license_notes.trim() || null,
      refresh_interval_hours: form.refresh_interval_hours ? Number(form.refresh_interval_hours) : null,
      enabled: form.enabled,
    })
    ui.push('Source updated.', 'success')
    await sourceState.run()
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    saveError.value = isApiError(err) ? err.message : 'Save failed - please try again.'
  } finally {
    saving.value = false
  }
}

const refreshing = ref(false)

async function refresh() {
  refreshing.value = true
  try {
    const job = await admin.refreshSource(sourceId.value)
    ui.push(`Refresh job ${job.status} - results appear in the job list after processing.`, 'success')
    await sourceState.run()
  } catch (err) {
    ui.pushError(err)
  } finally {
    refreshing.value = false
  }
}

function parseMetadata(raw: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

const metadataText = ref('')
const metadataError = ref('')

watch(
  source,
  (value) => {
    metadataText.value = JSON.stringify(value?.metadata ?? {}, null, 2)
  },
  { immediate: true },
)

async function saveMetadata() {
  const parsed = parseMetadata(metadataText.value)
  if (!parsed) {
    metadataError.value = 'Metadata must be a JSON object.'
    return
  }
  metadataError.value = ''
  try {
    await admin.patchSource(sourceId.value, { metadata: parsed })
    ui.push('Metadata updated.', 'success')
    await sourceState.run()
  } catch (err) {
    ui.pushError(err)
  }
}
</script>

<template>
  <AsyncState
    :loading="sourceState.loading.value"
    :error="sourceState.error.value"
    :empty="!source"
    empty-title="Source not found"
    @retry="sourceState.run"
  >
    <template #empty-action>
      <RouterLink to="/admin/sources" class="btn">Back to registry</RouterLink>
    </template>

    <div v-if="source" class="stack">
      <div class="row-between">
        <div>
          <p class="small muted" style="margin: 0">
            <RouterLink to="/admin/sources">Source registry</RouterLink> / source
          </p>
          <h1 style="margin-bottom: 2px">{{ source.name }}</h1>
          <p class="muted small" style="margin: 0">
            <a :href="source.base_url" target="_blank" rel="noopener noreferrer">{{ source.base_url }}</a>
          </p>
        </div>
        <div class="row">
          <StatusBadge :status="source.enabled ? 'fresh' : 'cancelled'" :label="source.enabled ? 'enabled' : 'disabled'" />
          <span class="badge badge-neutral">tier {{ source.authority_tier }}</span>
          <button v-if="auth.isAdmin" class="btn btn-sm" type="button" :disabled="refreshing" @click="refresh">
            {{ refreshing ? 'Queuing…' : 'Queue refresh' }}
          </button>
        </div>
      </div>

      <div v-if="!auth.isAdmin" class="banner banner-info">
        You can view this source, but only an administrator can edit it or queue refreshes.
      </div>

      <div class="grid-2">
        <!-- editable fields (patchable subset) -->
        <section v-if="auth.isAdmin" class="card">
          <h2>Edit source</h2>
          <p class="small muted" style="margin-top: 0">
            base_url, source_type and allowed-use policy are immutable after creation - register a new
            source if they were wrong. Changes are audit-logged.
          </p>
          <div v-if="saveError" class="error-summary" role="alert">{{ saveError }}</div>
          <div class="field">
            <label for="edit-name">Name</label>
            <input id="edit-name" v-model="form.name" type="text" />
          </div>
          <div class="grid-2">
            <div class="field">
              <label for="edit-tier">Authority tier</label>
              <select id="edit-tier" v-model="form.authority_tier">
                <option v-for="tier in [1, 2, 3, 4, 5]" :key="tier" :value="String(tier)">{{ tier }}</option>
              </select>
            </div>
            <div class="field">
              <label for="edit-refresh">Refresh interval (hours)</label>
              <input id="edit-refresh" v-model="form.refresh_interval_hours" type="number" min="1" max="8760" />
            </div>
          </div>
          <div class="field">
            <label for="edit-owner">Owner / publisher</label>
            <input id="edit-owner" v-model="form.owner_or_publisher" type="text" />
          </div>
          <div class="field">
            <label for="edit-terms">Terms URL</label>
            <input id="edit-terms" v-model="form.terms_url" type="url" />
          </div>
          <div class="field">
            <label for="edit-rate">Rate-limit notes</label>
            <textarea id="edit-rate" v-model="form.rate_limit_notes" rows="2" />
          </div>
          <div class="field">
            <label for="edit-license">License notes</label>
            <textarea id="edit-license" v-model="form.license_notes" rows="2" />
          </div>
          <label class="checkbox-row">
            <input v-model="form.enabled" type="checkbox" />
            Enabled
          </label>
          <button class="btn btn-primary" type="button" :disabled="saving || !dirty" @click="save">
            {{ saving ? 'Saving…' : 'Save changes' }}
          </button>
        </section>

        <!-- read-only summary + metadata -->
        <div class="stack">
          <section class="card">
            <h2>Policy summary</h2>
            <dl class="kv">
              <dt>Source type</dt>
              <dd>{{ humanize(source.source_type) }}</dd>
              <dt>Allowed use</dt>
              <dd>{{ humanize(source.allowed_use_policy) }}</dd>
              <dt>Documents / jobs</dt>
              <dd>{{ source.documents.length }} / {{ source.recent_jobs.length }}</dd>
              <dt>Created</dt>
              <dd>{{ formatDateTime(source.created_at) }}</dd>
              <dt>Updated</dt>
              <dd>{{ formatDateTime(source.updated_at) }}</dd>
              <dt>Last checked</dt>
              <dd>{{ formatDateTime(source.last_checked_at) }}</dd>
              <dt>Last successful check</dt>
              <dd>{{ formatDateTime(source.last_success_at) }}</dd>
              <dt>Last content change</dt>
              <dd>{{ formatDateTime(source.last_content_changed_at) }}</dd>
              <dt>Automatic refresh</dt>
              <dd>{{ humanize(source.scheduling?.state ?? 'awaiting_operational_approval') }}<span v-if="source.scheduling?.max_records"> · limit {{ source.scheduling.max_records }} records</span></dd>
              <dt>Next scheduled refresh</dt>
              <dd>{{ formatDateTime(source.next_refresh_at) }} · {{ humanize(source.freshness_status ?? 'unknown') }}</dd>
            </dl>
          </section>

          <section class="card">
            <h2>Metadata</h2>
            <p class="small muted" style="margin-top: 0">
              Arbitrary JSON used for scheduling and policy notes. Must be an object.
            </p>
            <span v-if="metadataError" class="field-error">{{ metadataError }}</span>
            <textarea v-model="metadataText" rows="8" style="font-family: var(--mono); font-size: 0.82rem" aria-label="Source metadata JSON" />
            <button v-if="auth.isAdmin" class="btn btn-sm" type="button" style="margin-top: 8px" @click="saveMetadata">
              Save metadata
            </button>
          </section>
        </div>
      </div>

      <!-- recent jobs -->
      <section class="card">
        <h2>Recent jobs</h2>
        <div v-if="source.recent_jobs.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Entity rows (seen/created/updated/rejected)</th>
                <th>Started</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="job in source.recent_jobs" :key="job.id">
                <td>{{ humanize(job.job_type) }}</td>
                <td><StatusBadge :status="job.status" /></td>
                <td class="small mono">
                  {{ job.records_seen }}/{{ job.records_created }}/{{ job.records_updated }}/{{ job.records_rejected }}
                  <div v-if="job.metrics?.version === 2" class="muted">
                    I {{ job.metrics.institutions?.created ?? 0 }} · P {{ job.metrics.programs?.created ?? 0 }} ·
                    F {{ job.metrics.facts?.created ?? 0 }} / {{ job.metrics.facts?.updated ?? 0 }} / {{ job.metrics.facts?.unchanged ?? 0 }}
                  </div>
                  <div v-else class="muted">legacy aggregate</div>
                </td>
                <td class="small">{{ formatDateTime(job.started_at) }}</td>
                <td class="small">{{ job.error_summary ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No jobs recorded for this source yet.</p>
      </section>

      <!-- documents -->
      <section class="card">
        <h2>Documents</h2>
        <div v-if="source.documents.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Fetch</th>
                <th>HTTP</th>
                <th>Source period / publication</th>
                <th>First retrieved / last checked</th>
                <th>Content last changed</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="document in source.documents" :key="document.id">
                <td>
                  <a v-if="document.canonical_url" :href="document.canonical_url" target="_blank" rel="noopener noreferrer">
                    {{ document.title ?? document.canonical_url }}
                  </a>
                  <template v-else>{{ document.title ?? document.canonical_url ?? valuePreview(document.id) }}</template>
                </td>
                <td class="small">{{ document.document_type ? humanize(document.document_type) : '—' }}</td>
                <td class="small"><StatusBadge :status="document.fetch_status" /></td>
                <td class="small">{{ document.http_status ?? '—' }}</td>
                <td class="small">{{ document.academic_period ?? 'Period unknown' }}<br />{{ formatDateTime(document.source_published_at) }}</td>
                <td class="small">{{ formatDateTime(document.retrieved_at) }}<br />{{ formatDateTime(document.last_checked_at) }}</td>
                <td class="small">{{ formatDateTime(document.last_content_changed_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No documents retrieved from this source yet.</p>
      </section>
      <section class="card">
        <h2>Recent retrieval checks</h2>
        <div v-if="source.retrieval_attempts.length" class="table-wrap">
          <table class="data">
            <thead><tr><th>Checked</th><th>Outcome</th><th>HTTP</th><th>Attempts</th><th>URL / diagnostic</th></tr></thead>
            <tbody>
              <tr v-for="(attempt, index) in source.retrieval_attempts" :key="`${attempt.canonical_url}-${attempt.attempted_at}-${index}`">
                <td class="small">{{ formatDateTime(attempt.attempted_at) }}</td>
                <td><StatusBadge :status="attempt.outcome" /></td>
                <td>{{ attempt.http_status ?? '—' }}</td>
                <td>{{ attempt.attempt_count }}</td>
                <td class="small"><a :href="attempt.canonical_url" target="_blank" rel="noopener noreferrer">{{ attempt.canonical_url }}</a><div v-if="attempt.error_summary" class="error">{{ attempt.error_summary }}</div></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No retrieval attempts recorded in the new retrieval history yet.</p>
      </section>
    </div>
  </AsyncState>
</template>
