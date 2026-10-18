<script setup lang="ts">
import { reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { formatDateTime, humanize, valuePreview } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()

// Filter vocabularies mirror backend admin constants (services/admin.py).
const STATUSES = ['candidate', 'in_review', 'conflicted', 'stale', 'verified', 'estimated', 'unavailable', 'rejected']
const ENTITY_TYPES = ['university', 'program', 'intake', 'fee', 'requirement', 'scholarship', 'city', 'outcome', 'country_rule', 'other']
const PAGE_SIZE = 20

const filters = reactive({
  status: typeof route.query.status === 'string' ? route.query.status : '',
  entity_type: typeof route.query.entity_type === 'string' ? route.query.entity_type : '',
  fact_key: typeof route.query.fact_key === 'string' ? route.query.fact_key : '',
  page: Number(route.query.page) || 1,
})

const queue = useAsync(
  () =>
    admin.reviewQueue({
      status: filters.status || undefined,
      entity_type: filters.entity_type || undefined,
      fact_key: filters.fact_key.trim() || undefined,
      page: filters.page,
      page_size: PAGE_SIZE,
    }),
  { immediate: true },
)

watch(
  () => [filters.status, filters.entity_type, filters.fact_key],
  () => {
    filters.page = 1
  },
)

watch(
  () => [filters.status, filters.entity_type, filters.fact_key, filters.page],
  () => {
    void router.replace({
      query: {
        status: filters.status || undefined,
        entity_type: filters.entity_type || undefined,
        fact_key: filters.fact_key.trim() || undefined,
        page: filters.page > 1 ? String(filters.page) : undefined,
      },
    })
    void queue.run()
  },
)

function setPage(page: number) {
  filters.page = page
  window.scrollTo({ top: 0 })
}
</script>

<template>
  <div class="stack">
    <div>
      <h1>Review queue</h1>
      <p class="muted small" style="margin: 0">
        Facts whose evidence needs a human decision. Approving publishes the value; rejecting marks
        the version; requesting evidence asks ingestion for a better source. Every action is logged
        with reason and request id.
      </p>
    </div>

    <section class="card">
      <div class="grid">
        <div class="field" style="margin-bottom: 0">
          <label for="queue-status">Status</label>
          <select id="queue-status" v-model="filters.status">
            <option value="">Reviewable (default)</option>
            <option v-for="status in STATUSES" :key="status" :value="status">{{ humanize(status) }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="queue-entity">Entity type</label>
          <select id="queue-entity" v-model="filters.entity_type">
            <option value="">Any entity</option>
            <option v-for="type in ENTITY_TYPES" :key="type" :value="type">{{ humanize(type) }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="queue-fact-key">Fact key</label>
          <input id="queue-fact-key" v-model="filters.fact_key" type="text" placeholder="e.g. tuition_annual" />
        </div>
      </div>
    </section>

    <AsyncState
      :loading="queue.loading.value"
      :error="queue.error.value"
      :empty="!queue.data.value?.items.length"
      empty-title="Nothing in the queue"
      empty-hint="No facts match these filters - clear them or wait for new ingestion results."
      @retry="queue.run"
    >
      <template #empty-action>
        <button class="btn" type="button" @click="Object.assign(filters, { status: '', entity_type: '', fact_key: '', page: 1 })">
          Clear filters
        </button>
      </template>

      <div v-if="queue.data.value" class="stack">
        <p class="small muted" style="margin: 0" aria-live="polite">
          {{ queue.data.value.total_items }} facts
        </p>
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Fact</th>
                <th>Status</th>
                <th>Current value</th>
                <th>Versions / evidence</th>
                <th>Last review</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.data.value.items" :key="item.fact_id">
                <td>
                  <strong>{{ item.entity_label ?? '—' }}</strong>
                  <div class="small muted">{{ humanize(item.entity_type) }}</div>
                </td>
                <td>
                  {{ item.fact_key }}
                  <div v-if="item.applicability_key" class="small muted">{{ item.applicability_key }}</div>
                </td>
                <td><StatusBadge :status="item.current_status" /></td>
                <td class="mono small" style="max-width: 220px">{{ valuePreview(item.current_value) }}</td>
                <td class="small">{{ item.version_count }} / {{ item.evidence_count }}</td>
                <td class="small">
                  <template v-if="item.last_review">
                    {{ humanize(item.last_review.action) }} · {{ formatDateTime(item.last_review.created_at) }}
                    <div v-if="item.last_review.reason" class="muted">“{{ item.last_review.reason }}”</div>
                  </template>
                  <span v-else class="muted">never reviewed</span>
                </td>
                <td>
                  <RouterLink class="btn btn-sm" :to="`/admin/review/${item.fact_id}`">Open</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationBar
          :page="queue.data.value.page"
          :page-size="queue.data.value.page_size"
          :total-items="queue.data.value.total_items"
          :total-pages="queue.data.value.total_pages"
          @update:page="setPage"
        />
      </div>
    </AsyncState>
  </div>
</template>
