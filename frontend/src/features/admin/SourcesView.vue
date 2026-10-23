<script setup lang="ts">
import { reactive, ref } from 'vue'
import { admin } from '../../services/api/admin'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import { humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const auth = useAuthStore()
const ui = useUiStore()

const SOURCE_TYPES = ['official_university', 'government', 'regulator', 'statistical', 'licensed_aggregator', 'other']
const POLICIES = [
  ['permitted_fetch', 'Automated fetching permitted'],
  ['licensed_api', 'Licensed API'],
  ['public_dataset', 'Public dataset'],
  ['manual_reference', 'Manual reference only (no automation)'],
  ['review_required', 'Review required before use'],
  ['prohibited_automated_fetch', 'Automated fetching prohibited'],
]

const page = ref(1)
const sourcesState = useAsync(() => admin.sources({ page: page.value, page_size: 20 }), { immediate: true })

// ----------------------------------------------------------------- create form

const showCreate = ref(false)
const createForm = reactive({
  name: '',
  base_url: '',
  source_type: 'official_university',
  authority_tier: '3',
  owner_or_publisher: '',
  allowed_use_policy: 'permitted_fetch',
  terms_url: '',
  refresh_interval_hours: '',
  enabled: true,
})
const createErrors = ref<Record<string, string>>({})
const creating = ref(false)

async function createSource() {
  if (creating.value) return
  creating.value = true
  createErrors.value = {}
  try {
    await admin.createSource({
      name: createForm.name.trim(),
      base_url: createForm.base_url.trim(),
      source_type: createForm.source_type,
      authority_tier: Number(createForm.authority_tier),
      owner_or_publisher: createForm.owner_or_publisher.trim() || null,
      allowed_use_policy: createForm.allowed_use_policy,
      terms_url: createForm.terms_url.trim() || null,
      refresh_interval_hours: createForm.refresh_interval_hours ? Number(createForm.refresh_interval_hours) : null,
      enabled: createForm.enabled,
    })
    ui.push('Source registered.', 'success')
    showCreate.value = false
    createForm.name = ''
    createForm.base_url = ''
    createForm.owner_or_publisher = ''
    createForm.terms_url = ''
    createForm.refresh_interval_hours = ''
    await sourcesState.run()
  } catch (err) {
    if (isApiError(err)) {
      const next: Record<string, string> = {}
      for (const detail of err.details) {
        if (detail.field) next[detail.field] = detail.message
      }
      createErrors.value = next
      ui.pushError(err)
    } else {
      ui.pushError(err)
    }
  } finally {
    creating.value = false
  }
}

// ----------------------------------------------------------------- refresh

const refreshing = ref<string | null>(null)

async function refresh(sourceId: string) {
  refreshing.value = sourceId
  try {
    const job = await admin.refreshSource(sourceId)
    ui.push(`Refresh job ${job.status === 'queued' ? 'queued' : job.status} - only permitted sources may be refreshed.`, 'success')
    await sourcesState.run()
  } catch (err) {
    // 403 REFRESH_NOT_PERMITTED for manual_reference/prohibited sources - explain, don't hide
    ui.pushError(err)
  } finally {
    refreshing.value = null
  }
}
</script>

<template>
  <div class="stack">
    <div class="row-between">
      <div>
        <h1>Source registry</h1>
        <p class="muted small" style="margin: 0">
          Every source with its authority tier and allowed-use policy. Refresh is only available for
          sources whose recorded policy permits automated fetching; the backend enforces this
          regardless of what this screen shows.
        </p>
      </div>
      <button v-if="auth.isAdmin" class="btn btn-primary" type="button" @click="showCreate = !showCreate">
        {{ showCreate ? 'Close form' : 'Register a source' }}
      </button>
    </div>

    <!-- create -->
    <section v-if="showCreate && auth.isAdmin" class="card">
      <h2>Register a source</h2>
      <div class="grid-2">
        <div class="field">
          <label for="src-name">Name <span class="muted">(required)</span></label>
          <input id="src-name" v-model="createForm.name" type="text" :aria-invalid="Boolean(createErrors.name)" />
          <span v-if="createErrors.name" class="field-error">{{ createErrors.name }}</span>
        </div>
        <div class="field">
          <label for="src-url">Base URL <span class="muted">(required)</span></label>
          <input id="src-url" v-model="createForm.base_url" type="url" placeholder="https://…" :aria-invalid="Boolean(createErrors.base_url)" />
          <span v-if="createErrors.base_url" class="field-error">{{ createErrors.base_url }}</span>
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="src-type">Source type</label>
          <select id="src-type" v-model="createForm.source_type">
            <option v-for="type in SOURCE_TYPES" :key="type" :value="type">{{ humanize(type) }}</option>
          </select>
        </div>
        <div class="field">
          <label for="src-policy">Allowed-use policy</label>
          <select id="src-policy" v-model="createForm.allowed_use_policy">
            <option v-for="[value, label] in POLICIES" :key="value" :value="value">{{ label }}</option>
          </select>
          <span class="help">Automated refresh requires permitted_fetch, licensed_api or public_dataset.</span>
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="src-tier">Authority tier (1 best - 5 worst)</label>
          <select id="src-tier" v-model="createForm.authority_tier">
            <option v-for="tier in [1, 2, 3, 4, 5]" :key="tier" :value="String(tier)">{{ tier }}</option>
          </select>
        </div>
        <div class="field">
          <label for="src-refresh">Refresh interval (hours)</label>
          <input id="src-refresh" v-model="createForm.refresh_interval_hours" type="number" min="1" max="8760" placeholder="leave empty for manual" :aria-invalid="Boolean(createErrors.refresh_interval_hours)" />
          <span v-if="createErrors.refresh_interval_hours" class="field-error">{{ createErrors.refresh_interval_hours }}</span>
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="src-owner">Owner / publisher</label>
          <input id="src-owner" v-model="createForm.owner_or_publisher" type="text" />
        </div>
        <div class="field">
          <label for="src-terms">Terms URL</label>
          <input id="src-terms" v-model="createForm.terms_url" type="url" placeholder="https://…/terms" />
        </div>
      </div>
      <label class="checkbox-row">
        <input v-model="createForm.enabled" type="checkbox" />
        Enabled (allowed to be scheduled)
      </label>
      <button class="btn btn-primary" type="button" :disabled="creating" @click="createSource">
        {{ creating ? 'Saving…' : 'Register source' }}
      </button>
    </section>

    <AsyncState
      :loading="sourcesState.loading.value"
      :error="sourcesState.error.value"
      :empty="!sourcesState.data.value?.items.length"
      empty-title="No sources registered"
      empty-hint="Register the first source to start building evidence."
      @retry="sourcesState.run"
    >
      <div v-if="sourcesState.data.value" class="stack">
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Source</th>
                <th>Type / tier</th>
                <th>Policy</th>
                <th>Refresh</th>
                <th>Last check / dataset period</th>
                <th>Docs / jobs</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="source in sourcesState.data.value.items" :key="source.id">
                <td>
                  <RouterLink :to="`/admin/sources/${source.id}`"><strong>{{ source.name }}</strong></RouterLink>
                  <div class="small muted">{{ source.base_url }}</div>
                </td>
                <td class="small">
                  {{ humanize(source.source_type) }}<br />
                  <span class="badge badge-neutral">tier {{ source.authority_tier }}</span>
                </td>
                <td class="small">{{ humanize(source.allowed_use_policy) }}</td>
                <td class="small">
                  <StatusBadge :status="source.enabled ? 'fresh' : 'cancelled'" :label="source.enabled ? 'enabled' : 'disabled'" />
                  <div v-if="source.refresh_interval_hours" class="muted">every {{ source.refresh_interval_hours }}h</div>
                  <div v-if="source.next_refresh_at" class="muted">next {{ source.next_refresh_at }}</div>
                </td>
                <td class="small">
                  <div>{{ source.last_success_at ?? 'No successful check recorded' }}</div>
                  <div v-if="source.latest_academic_period" class="muted">period {{ source.latest_academic_period }}</div>
                  <div v-if="source.latest_source_published_at" class="muted">published {{ source.latest_source_published_at }}</div>
                  <span v-if="source.freshness_status === 'stale'" class="error">Source is overdue for refresh.</span>
                </td>
                <td class="small">{{ source.document_count ?? '—' }} / {{ source.job_count ?? '—' }}</td>
                <td>
                  <div class="row">
                    <RouterLink class="btn btn-sm" :to="`/admin/sources/${source.id}`">Open</RouterLink>
                    <button
                      v-if="auth.isAdmin"
                      class="btn btn-sm btn-quiet"
                      type="button"
                      :disabled="refreshing === source.id"
                      @click="refresh(source.id)"
                    >
                      {{ refreshing === source.id ? 'Queuing…' : 'Refresh' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationBar
          :page="sourcesState.data.value.page"
          :page-size="sourcesState.data.value.page_size"
          :total-items="sourcesState.data.value.total_items"
          :total-pages="sourcesState.data.value.total_pages"
          @update:page="(next) => { page = next }"
        />
      </div>
    </AsyncState>
  </div>
</template>
