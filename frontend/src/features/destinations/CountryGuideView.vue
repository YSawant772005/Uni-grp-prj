<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { useAsync } from '../../composables/useAsync'
import { formatDate, truncate } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const code = computed(() => String(route.params.countryCode).toUpperCase())

const countryState = useAsync(() => catalog.country(code.value), { immediate: true })
const programsState = useAsync(
  () => catalog.programs({ country: code.value, page_size: 6, sort: 'name' }),
  { immediate: true },
)

const country = computed(() => countryState.data.value)

/** A rule is stale when its last check is older than ~120 days. */
function isStale(lastChecked: string | null): boolean {
  if (!lastChecked) return true
  return Date.now() - new Date(lastChecked).getTime() > 120 * 24 * 60 * 60 * 1000
}
</script>

<template>
  <AsyncState
    :loading="countryState.loading.value"
    :error="countryState.error.value"
    :empty="!country"
    empty-title="Country guide not found"
    empty-hint="Check the country code or browse all destinations."
    @retry="countryState.run"
  >
    <template #empty-action>
      <RouterLink to="/destinations" class="btn">All destinations</RouterLink>
    </template>

    <div v-if="country" class="stack">
      <div class="row-between">
        <div>
          <h1 style="margin-bottom: 2px">{{ country.name }}</h1>
          <p class="muted small" style="margin: 0">
            {{ country.region }} ·
            <RouterLink :to="`/discover?country=${country.code}`">
              {{ programsState.data.value?.total_items ?? '—' }} programs in the catalogue
            </RouterLink>
          </p>
        </div>
        <div class="row">
          <a
            v-if="country.official_study_url"
            class="btn btn-sm"
            :href="country.official_study_url"
            target="_blank"
            rel="noopener noreferrer"
          >Official study portal ↗</a>
          <a
            v-if="country.official_immigration_url"
            class="btn btn-sm btn-quiet"
            :href="country.official_immigration_url"
            target="_blank"
            rel="noopener noreferrer"
          >Immigration authority ↗</a>
        </div>
      </div>

      <!-- official rules -->
      <section class="card">
        <h2>Official rules (study & post-study work)</h2>
        <p class="muted small" style="margin-top: 0">
          Each rule links its government source and shows when it was last checked. Rules change -
          always confirm on the official page before making decisions.
        </p>
        <div v-if="country.official_rules.length" class="table-wrap">
          <table class="data">
            <thead>
              <tr>
                <th>Rule</th>
                <th>Summary</th>
                <th>Effective</th>
                <th>Last checked</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in country.official_rules" :key="rule.id">
                <td>
                  <a v-if="rule.official_url" :href="rule.official_url" target="_blank" rel="noopener noreferrer">
                    {{ rule.title }}
                  </a>
                  <template v-else>{{ rule.title }}</template>
                  <div><span class="badge badge-neutral">{{ rule.rule_type }}</span></div>
                </td>
                <td class="small">{{ rule.summary ? truncate(rule.summary, 220) : '—' }}</td>
                <td class="small">
                  {{ rule.effective_from ? formatDate(rule.effective_from) : '—' }}
                  <template v-if="rule.effective_to"> → {{ formatDate(rule.effective_to) }}</template>
                </td>
                <td class="small">
                  <div class="row">
                    <StatusBadge :status="isStale(rule.last_checked_at) ? 'stale' : 'fresh'" />
                    <span>{{ rule.last_checked_at ? formatDate(rule.last_checked_at) : 'never' }}</span>
                  </div>
                  <span v-if="rule.freshness_note" class="small muted">{{ rule.freshness_note }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No official rules recorded for this country yet.</p>
      </section>

      <!-- cities -->
      <section class="card">
        <h2>Cities</h2>
        <div v-if="country.cities.length" class="grid">
          <article v-for="city in country.cities" :key="city.id" class="card card-flat">
            <RouterLink :to="`/destinations/${country.code}/${city.slug}`">
              <h3 style="margin: 0">{{ city.name }}</h3>
            </RouterLink>
            <p v-if="city.admin_region" class="small muted" style="margin: 0">{{ city.admin_region }}</p>
            <RouterLink class="btn btn-sm" :to="`/destinations/${country.code}/${city.slug}`">
              Living costs & details
            </RouterLink>
          </article>
        </div>
        <p v-else class="muted">No city profiles recorded yet.</p>
      </section>
    </div>
  </AsyncState>
</template>
