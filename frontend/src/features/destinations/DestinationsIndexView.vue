<script setup lang="ts">
import { catalog } from '../../services/api/catalog'
import { useAsync } from '../../composables/useAsync'
import AsyncState from '../../components/AsyncState.vue'

const countriesState = useAsync(() => catalog.countries(), { immediate: true })
</script>

<template>
  <div class="stack">
    <div>
      <h1>Destination guides</h1>
      <p class="muted small" style="margin: 0">
        Country and city pages with official study/immigration links, post-study work rules (with
        freshness notes) and living-cost context. Official links open the government source so you
        can verify the current rule yourself.
      </p>
    </div>

    <AsyncState
      :loading="countriesState.loading.value"
      :error="countriesState.error.value"
      :empty="!countriesState.data.value?.items.length"
      empty-title="No destinations loaded yet"
      empty-hint="The destination catalogue is populated by reviewed data - check back soon."
      @retry="countriesState.run"
    >
      <div v-if="countriesState.data.value?.items.length" class="grid">
        <article v-for="country in countriesState.data.value.items" :key="country.code" class="card stack-sm">
          <RouterLink :to="`/destinations/${country.code}`">
            <h3 style="margin: 0">{{ country.name }}</h3>
          </RouterLink>
          <p class="small muted" style="margin: 0">
            {{ country.region }} · {{ country.city_count }} cit{{ country.city_count === 1 ? 'y' : 'ies' }} ·
            {{ country.university_count }} universities
          </p>
          <div class="row">
            <RouterLink class="btn btn-sm" :to="`/destinations/${country.code}`">Open guide</RouterLink>
            <a
              v-if="country.official_study_url"
              class="btn btn-sm btn-quiet"
              :href="country.official_study_url"
              target="_blank"
              rel="noopener noreferrer"
            >Official study site ↗</a>
          </div>
        </article>
      </div>
    </AsyncState>
  </div>
</template>
