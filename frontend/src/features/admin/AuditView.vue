<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { formatDateTime, humanize, valuePreview } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'

const route = useRoute()
const router = useRouter()

const filters = reactive({
  action: typeof route.query.action === 'string' ? route.query.action : '',
  actor_user_id: typeof route.query.actor === 'string' ? route.query.actor : '',
  entity_type: typeof route.query.entity_type === 'string' ? route.query.entity_type : '',
  since: typeof route.query.since === 'string' ? route.query.since : '',
  page: Number(route.query.page) || 1,
})

const events = useAsync(
  () =>
    admin.auditEvents({
      action: filters.action.trim() || undefined,
      actor_user_id: filters.actor_user_id.trim() || undefined,
      entity_type: filters.entity_type.trim() || undefined,
      since: filters.since ? `${filters.since}:00` : undefined,
      page: filters.page,
    }),
  { immediate: true },
)

watch(
  () => [filters.action, filters.actor_user_id, filters.entity_type, filters.since],
  () => {
    filters.page = 1
  },
)

watch(
  () => [filters.action, filters.actor_user_id, filters.entity_type, filters.since, filters.page],
  () => {
    void router.replace({
      query: {
        action: filters.action.trim() || undefined,
        actor: filters.actor_user_id.trim() || undefined,
        entity_type: filters.entity_type.trim() || undefined,
        since: filters.since || undefined,
        page: filters.page > 1 ? String(filters.page) : undefined,
      },
    })
    void events.run()
  },
)

// ------------------------------------------------------------------- expansion

const expanded = ref<Record<string, boolean>>({})

function toggle(id: string) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] }
}
</script>

<template>
  <div class="stack">
    <div>
      <h1>Audit log</h1>
      <p class="muted small" style="margin: 0">
        Append-only record of every reviewer action and administrative change: who did what, to which
        entity, with which request id, and the before/after state. Entries cannot be edited or
        deleted through this application.
      </p>
    </div>

    <section class="card">
      <div class="grid">
        <div class="field" style="margin-bottom: 0">
          <label for="audit-action">Action</label>
          <input id="audit-action" v-model="filters.action" type="text" placeholder="e.g. fact.approved" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="audit-actor">Actor user id</label>
          <input id="audit-actor" v-model="filters.actor_user_id" type="text" placeholder="filter by reviewer uuid" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="audit-entity">Entity type</label>
          <input id="audit-entity" v-model="filters.entity_type" type="text" placeholder="e.g. fact_version" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="audit-since">Since</label>
          <input id="audit-since" v-model="filters.since" type="datetime-local" />
        </div>
      </div>
    </section>

    <AsyncState
      :loading="events.loading.value"
      :error="events.error.value"
      :empty="!events.data.value?.items.length"
      empty-title="No audit events match"
      empty-hint="Adjust the filters to widen the search."
      @retry="events.run"
    >
      <div v-if="events.data.value" class="stack">
        <p class="small muted" style="margin: 0" aria-live="polite">
          {{ events.data.value.total_items }} events
        </p>
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Reason</th>
                <th>Request id</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="event in events.data.value.items" :key="event.id">
                <tr>
                  <td class="small nowrap">{{ formatDateTime(event.created_at) }}</td>
                  <td class="small mono">
                    {{ event.actor_type === 'system' ? 'system' : `${event.actor_type} ${event.actor_user_id?.slice(0, 8) ?? '—'}…` }}
                  </td>
                  <td class="small">{{ humanize(event.action) }}</td>
                  <td class="small">
                    {{ event.entity_type ? humanize(event.entity_type) : '—' }}
                    <div v-if="event.entity_id" class="muted mono">{{ event.entity_id.slice(0, 8) }}…</div>
                  </td>
                  <td class="small">{{ event.reason ?? '—' }}</td>
                  <td class="small mono">{{ event.request_id ? event.request_id.slice(0, 12) : '—' }}</td>
                  <td>
                    <button
                      v-if="event.before_summary || event.after_summary"
                      class="btn btn-sm"
                      type="button"
                      @click="toggle(event.id)"
                    >
                      {{ expanded[event.id] ? 'Hide' : 'Before/after' }}
                    </button>
                  </td>
                </tr>
                <tr v-if="expanded[event.id]">
                  <td colspan="7" style="background: var(--bg)">
                    <div class="grid-2">
                      <div>
                        <h4 style="margin: 0 0 4px">Before</h4>
                        <pre v-if="event.before_summary" class="json-block">{{ JSON.stringify(event.before_summary, null, 2) }}</pre>
                        <p v-else class="small muted" style="margin: 0">Nothing (new entity or no prior state).</p>
                      </div>
                      <div>
                        <h4 style="margin: 0 0 4px">After</h4>
                        <pre v-if="event.after_summary" class="json-block">{{ JSON.stringify(event.after_summary, null, 2) }}</pre>
                        <p v-else class="small muted" style="margin: 0">{{ valuePreview(event.action) }} (no state snapshot).</p>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <PaginationBar
          :page="events.data.value.page"
          :page-size="events.data.value.page_size"
          :total-items="events.data.value.total_items"
          :total-pages="events.data.value.total_pages"
          @update:page="(next) => (filters.page = next)"
        />
      </div>
    </AsyncState>
  </div>
</template>
