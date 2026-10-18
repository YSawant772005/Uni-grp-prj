<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import { formatDateTime, humanize, valuePreview } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

// Vocabularies mirror backend constants (services/admin.py).
const JOB_STATUSES = ['queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled']
const JOB_TYPES = ['discover', 'fetch', 'parse', 'normalize', 'validate', 'refresh']

const filters = ref({
  status: typeof route.query.status === 'string' ? route.query.status : '',
  job_type: typeof route.query.job_type === 'string' ? route.query.job_type : '',
  source_id: typeof route.query.source_id === 'string' ? route.query.source_id : '',
  page: Number(route.query.page) || 1,
})

const jobs = useAsync(
  () =>
    admin.jobs({
      status: filters.value.status || undefined,
      job_type: filters.value.job_type || undefined,
      source_id: filters.value.source_id || undefined,
      page: filters.value.page,
    }),
  { immediate: true },
)

watch(
  () => [filters.value.status, filters.value.job_type, filters.value.source_id],
  () => {
    filters.value.page = 1
  },
)

watch(
  () => [filters.value.status, filters.value.job_type, filters.value.source_id, filters.value.page],
  () => {
    void router.replace({
      query: {
        status: filters.value.status || undefined,
        job_type: filters.value.job_type || undefined,
        source_id: filters.value.source_id || undefined,
        page: filters.value.page > 1 ? String(filters.value.page) : undefined,
      },
    })
    void jobs.run()
  },
)

// -------------------------------------------------------------- job expansion

const expandedId = ref<string | null>(null)
const detail = useAsync(() => (expandedId.value ? admin.job(expandedId.value) : Promise.resolve(null)), {
  immediate: false,
})

function toggle(id: string) {
  if (expandedId.value === id) {
    expandedId.value = null
    return
  }
  expandedId.value = id
  void detail.run()
}

// ------------------------------------------------------------------- retry

const retrying = ref<string | null>(null)

async function retry(jobId: string) {
  retrying.value = jobId
  try {
    const job = await admin.retryJob(jobId)
    ui.push(`Retry ${job.status === 'queued' ? 'queued' : job.status}.`, 'success')
    await jobs.run()
  } catch (err) {
    // 409 RETRY_NOT_ALLOWED on repeat/running jobs - surface the server message
    ui.pushError(err)
  } finally {
    retrying.value = null
  }
}

const canRetry = (status: string) => status === 'failed' || status === 'cancelled'
</script>

<template>
  <div class="stack">
    <div>
      <h1>Ingestion jobs</h1>
      <p class="muted small" style="margin: 0">
        Discover, fetch, parse, normalize, validate and refresh runs. Statuses are real: a refresh
        that could not create facts returns <code>partial</code>, never a fake success. Payloads are
        never displayed - only counters and validation errors.
      </p>
    </div>

    <section class="card">
      <div class="grid">
        <div class="field" style="margin-bottom: 0">
          <label for="job-status">Status</label>
          <select id="job-status" v-model="filters.status">
            <option value="">Any status</option>
            <option v-for="status in JOB_STATUSES" :key="status" :value="status">{{ humanize(status) }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="job-type">Type</label>
          <select id="job-type" v-model="filters.job_type">
            <option value="">Any type</option>
            <option v-for="type in JOB_TYPES" :key="type" :value="type">{{ humanize(type) }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="job-source">Source id</label>
          <input id="job-source" v-model="filters.source_id" type="text" placeholder="filter by source uuid" />
        </div>
      </div>
    </section>

    <AsyncState
      :loading="jobs.loading.value"
      :error="jobs.error.value"
      :empty="!jobs.data.value?.items.length"
      empty-title="No jobs match"
      empty-hint="Adjust the filters, or queue a refresh from the source registry."
      @retry="jobs.run"
    >
      <template #empty-action>
        <RouterLink to="/admin/sources" class="btn">Open source registry</RouterLink>
      </template>

      <div v-if="jobs.data.value" class="stack">
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Records seen/created/updated/rejected</th>
                <th>Worker</th>
                <th>Started → finished</th>
                <th>Error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="job in jobs.data.value.items" :key="job.id">
                <tr>
                  <td>
                    {{ humanize(job.job_type) }}
                    <div v-if="job.source_id" class="small muted mono">{{ job.source_id.slice(0, 8) }}…</div>
                  </td>
                  <td><StatusBadge :status="job.status" /></td>
                  <td class="small mono">
                    {{ job.records_seen }}/{{ job.records_created }}/{{ job.records_updated }}/{{ job.records_rejected }}
                  </td>
                  <td class="small mono">{{ job.worker_version ?? '—' }}</td>
                  <td class="small">
                    {{ formatDateTime(job.started_at) }}<br />
                    {{ formatDateTime(job.finished_at) }}
                  </td>
                  <td class="small">{{ job.error_summary ?? '—' }}</td>
                  <td>
                    <div class="row">
                      <button class="btn btn-sm" type="button" @click="toggle(job.id)">
                        {{ expandedId === job.id ? 'Hide' : 'Details' }}
                      </button>
                      <button
                        v-if="canRetry(job.status)"
                        class="btn btn-sm btn-quiet"
                        type="button"
                        :disabled="retrying === job.id"
                        @click="retry(job.id)"
                      >
                        {{ retrying === job.id ? 'Queueing…' : 'Retry' }}
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="expandedId === job.id">
                  <td colspan="7" style="background: var(--bg)">
                    <AsyncState :loading="detail.loading.value" :error="detail.error.value" :empty="!detail.data.value" @retry="detail.run">
                      <div v-if="detail.data.value" class="stack-sm">
                        <h4 style="margin: 0">Job {{ detail.data.value.id }}</h4>
                        <p class="small muted" style="margin: 0">
                          created by {{ detail.data.value.created_by_user_id ? `user ${detail.data.value.created_by_user_id.slice(0, 8)}…` : 'scheduler' }}
                          · created {{ formatDateTime(detail.data.value.created_at) }}
                        </p>
                        <div v-if="detail.data.value.items.length" class="table-wrap">
                          <table class="data">
                            <thead>
                              <tr>
                                <th>Entity</th>
                                <th>External key</th>
                                <th>Status</th>
                                <th>Validation errors</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="item in detail.data.value.items" :key="item.id">
                                <td>{{ item.entity_type ? humanize(item.entity_type) : '—' }}</td>
                                <td class="mono small">{{ item.external_key ?? '—' }}</td>
                                <td><StatusBadge :status="item.status" /></td>
                                <td class="mono small">{{ item.validation_errors ? valuePreview(item.validation_errors, 120) : '—' }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <p v-else class="small muted" style="margin: 0">
                          No items recorded (the job produced no candidate rows - counters above are
                          the source of truth; nothing was fabricated).
                        </p>
                      </div>
                    </AsyncState>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <PaginationBar
          :page="jobs.data.value.page"
          :page-size="jobs.data.value.page_size"
          :total-items="jobs.data.value.total_items"
          :total-pages="jobs.data.value.total_pages"
          @update:page="(next) => (filters.page = next)"
        />
      </div>
    </AsyncState>
  </div>
</template>
