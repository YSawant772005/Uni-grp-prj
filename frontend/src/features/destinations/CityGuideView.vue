<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { useAsync } from '../../composables/useAsync'
import { formatMoney, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { CityRef } from '../../types/api'

const route = useRoute()
const countryCode = computed(() => String(route.params.countryCode).toUpperCase())
const citySlug = computed(() => String(route.params.citySlug))

// URLs carry the stable slug; the API needs the city id - resolve via the
// country's city list (small, already-cached on the country guide).
const citiesState = useAsync(() => catalog.cities(countryCode.value), { immediate: true })
const cityRef = computed<CityRef | null>(
  () => citiesState.data.value?.items.find((city) => city.slug === citySlug.value) ?? null,
)

const cityState = useAsync(
  () => (cityRef.value ? catalog.city(cityRef.value.id) : Promise.resolve(null)),
  { immediate: true },
)
// the id only becomes available after the city list loads
watch(cityRef, (ref) => {
  if (ref) void cityState.run()
})
const city = computed(() => cityState.data.value)

/** Living costs older than the current calendar year carry a staleness warning. */
const stale = computed(() => {
  const year = city.value?.living_cost_year
  return year !== null && year !== undefined && year < new Date().getFullYear() - 1
})
</script>

<template>
  <AsyncState
    :loading="citiesState.loading.value || cityState.loading.value"
    :error="cityState.error.value ?? citiesState.error.value"
    :empty="!city"
    empty-title="City guide not found"
    empty-hint="This city may not have a profile yet, or the link is out of date."
    @retry="citiesState.run"
  >
    <template #empty-action>
      <RouterLink :to="`/destinations/${countryCode}`" class="btn">Back to {{ countryCode }}</RouterLink>
    </template>

    <div v-if="city" class="stack">
      <div>
        <p class="small muted" style="margin: 0">
          <RouterLink to="/destinations">Destinations</RouterLink> /
          <RouterLink :to="`/destinations/${countryCode}`">{{ countryCode }}</RouterLink>
        </p>
        <h1 style="margin-bottom: 2px">{{ city.name }}</h1>
        <p v-if="city.admin_region" class="muted small" style="margin: 0">{{ city.admin_region }}</p>
      </div>

      <section class="card">
        <div class="row-between">
          <h2 style="margin: 0">Living costs</h2>
          <div class="row">
            <StatusBadge v-if="city.living_cost_year" :status="stale ? 'stale' : 'fresh'" />
            <span v-if="city.living_cost_year" class="small muted">
              reference year {{ city.living_cost_year }}
            </span>
          </div>
        </div>
        <div v-if="stale" class="banner banner-warn" style="margin-top: 8px" role="status">
          These figures are from {{ city.living_cost_year }} - treat them as a floor for budgeting
          and check current rents before committing.
        </div>
        <div v-if="city.living_costs.length" class="table-wrap" style="margin-top: 10px">
          <table class="data">
            <thead>
              <tr>
                <th>Category</th>
                <th>Low</th>
                <th>Typical</th>
                <th>High</th>
                <th>Period</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cost in city.living_costs" :key="cost.category">
                <td>{{ humanize(cost.category) }}</td>
                <td>{{ formatMoney(cost.min, cost.currency) }}</td>
                <td><strong>{{ formatMoney(cost.typical, cost.currency) }}</strong></td>
                <td>{{ formatMoney(cost.max, cost.currency) }}</td>
                <td class="small">{{ humanize(cost.period) }} ({{ cost.effective_year }})</td>
                <td><StatusBadge :status="cost.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">No living-cost data recorded for this city yet.</p>
        <p class="small muted" style="margin: 10px 0 0">
          Ranges are indicative monthly costs for a student - your actual spend depends on
          lifestyle and housing choices. Use these in the
          <RouterLink to="/finance">cost estimator</RouterLink>, not as a quote.
        </p>
      </section>

      <section class="card">
        <h2>Programs in {{ city.name }}</h2>
        <RouterLink class="btn btn-sm" :to="`/discover?country=${countryCode}`">
          Browse {{ countryCode }} programs
        </RouterLink>
      </section>
    </div>
  </AsyncState>
</template>
