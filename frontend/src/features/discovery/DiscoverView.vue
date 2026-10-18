<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { useAsync } from '../../composables/useAsync'
import { useDebouncedValue } from '../../composables/useDebouncedValue'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import ProgramCard from '../../components/ProgramCard.vue'

/** Program search with debounced query, shareable filter state and server pagination. */

const route = useRoute()
const router = useRouter()

// Field options mirror the seeded catalogue (backend/app/db/seed.py FIELDS).
const FIELD_OPTIONS: [string, string][] = [
  ['computer_science', 'Computer Science'],
  ['artificial_intelligence', 'Artificial Intelligence'],
  ['data_science', 'Data Science'],
  ['business_analytics', 'Business Analytics'],
  ['robotics', 'Robotics'],
  ['mechanical_engineering', 'Mechanical Engineering'],
  ['finance', 'Finance'],
]
const SORT_OPTIONS = [
  ['name', 'Name'],
  ['deadline', 'Application deadline'],
  ['tuition', 'Tuition'],
  ['country', 'Country'],
]
const PAGE_SIZE = 12

// ------------------------------------------------------- shareable filter state

const filters = reactive({
  q: typeof route.query.q === 'string' ? route.query.q : '',
  country: typeof route.query.country === 'string' ? route.query.country : '',
  field: typeof route.query.field === 'string' ? route.query.field : '',
  degree_level: typeof route.query.degree_level === 'string' ? route.query.degree_level : '',
  language: typeof route.query.language === 'string' ? route.query.language : '',
  sort: (typeof route.query.sort === 'string' ? route.query.sort : 'name') as
    | 'name'
    | 'deadline'
    | 'tuition'
    | 'country',
  order: (typeof route.query.order === 'string' ? route.query.order : 'asc') as 'asc' | 'desc',
  page: Number(route.query.page) || 1,
})

const debouncedQuery = useDebouncedValue(computed(() => filters.q), 350)

const countriesState = useAsync(() => catalog.countries(), { immediate: true })
const countryOptions = computed(() => countriesState.data.value?.items ?? [])

const results = useAsync(
  () =>
    catalog.programs({
      q: debouncedQuery.value.trim() || undefined,
      country: filters.country || undefined,
      field: filters.field || undefined,
      degree_level: filters.degree_level || undefined,
      language: filters.language || undefined,
      sort: filters.sort,
      order: filters.order,
      page: filters.page,
      page_size: PAGE_SIZE,
    }),
  { immediate: true },
)

const hasFilters = computed(
  () => Boolean(filters.q || filters.country || filters.field || filters.degree_level || filters.language),
)

// keep the URL in sync so results are shareable (UI doc section 5)
function syncUrl() {
  void router.replace({
    query: {
      q: filters.q || undefined,
      country: filters.country || undefined,
      field: filters.field || undefined,
      degree_level: filters.degree_level || undefined,
      language: filters.language || undefined,
      sort: filters.sort !== 'name' ? filters.sort : undefined,
      order: filters.order !== 'asc' ? filters.order : undefined,
      page: filters.page > 1 ? String(filters.page) : undefined,
    },
  })
}

watch(
  [() => filters.country, () => filters.field, () => filters.degree_level, () => filters.language, () => filters.sort, () => filters.order],
  () => {
    filters.page = 1
  },
)

watch([debouncedQuery, () => filters.country, () => filters.field, () => filters.degree_level, () => filters.language, () => filters.sort, () => filters.order, () => filters.page], () => {
  syncUrl()
  void results.run()
})

function clearFilters() {
  filters.q = ''
  filters.country = ''
  filters.field = ''
  filters.degree_level = ''
  filters.language = ''
  filters.page = 1
}

function setPage(page: number) {
  filters.page = page
  void results.run()
  window.scrollTo({ top: 0 })
}

// the search input writes to filters.q immediately (debounce applies to the request)
const searchInput = computed({
  get: () => filters.q,
  set: (value: string) => {
    filters.q = value
  },
})
</script>

<template>
  <div class="stack">
    <div>
      <h1>Discover programs</h1>
      <p class="muted small" style="margin: 0">
        Search the catalogue, filter and sort. Eligibility is never claimed from catalogue data
        alone - run a shortlist after building your profile to see requirement-level checks.
      </p>
    </div>

    <section class="card" aria-label="Search and filters">
      <div class="field" style="margin-bottom: 10px">
        <label for="discover-q">Search</label>
        <input
          id="discover-q"
          v-model="searchInput"
          type="search"
          placeholder="Program, university or keyword…"
          autocomplete="off"
        />
      </div>
      <div class="grid">
        <div class="field" style="margin-bottom: 0">
          <label for="filter-country">Country</label>
          <select id="filter-country" v-model="filters.country">
            <option value="">Any country</option>
            <option v-for="country in countryOptions" :key="country.code" :value="country.code">
              {{ country.name }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="filter-field">Field</label>
          <select id="filter-field" v-model="filters.field">
            <option value="">Any field</option>
            <option v-for="[value, label] in FIELD_OPTIONS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="filter-degree">Degree level</label>
          <select id="filter-degree" v-model="filters.degree_level">
            <option value="">Any level</option>
            <option value="masters">Master's</option>
            <option value="phd">PhD</option>
            <option value="diploma">Diploma</option>
            <option value="certificate">Certificate</option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="filter-language">Language</label>
          <select id="filter-language" v-model="filters.language">
            <option value="">Any language</option>
            <option value="english">English</option>
            <option value="german">German</option>
            <option value="french">French</option>
            <option value="dutch">Dutch</option>
          </select>
        </div>
      </div>
      <div class="row-between" style="margin-top: 12px">
        <div class="row">
          <label for="filter-sort" class="small">Sort by</label>
          <select id="filter-sort" v-model="filters.sort" style="width: auto">
            <option v-for="[value, label] in SORT_OPTIONS" :key="value" :value="value">{{ label }}</option>
          </select>
          <select v-model="filters.order" aria-label="Sort direction" style="width: auto">
            <option value="asc">ascending</option>
            <option value="desc">descending</option>
          </select>
        </div>
        <button v-if="hasFilters" class="btn btn-sm" type="button" @click="clearFilters">Clear filters</button>
      </div>
    </section>

    <AsyncState
      :loading="results.loading.value"
      :error="results.error.value"
      :empty="!results.data.value?.items.length"
      empty-title="No programs match"
      empty-hint="Try removing a filter or searching for something broader."
      @retry="results.run"
    >
      <template #empty-action>
        <button class="btn" type="button" @click="clearFilters">Clear filters</button>
      </template>

      <div v-if="results.data.value" class="stack">
        <p class="small muted" style="margin: 0" aria-live="polite">
          {{ results.data.value.total_items }} programs · sorted by
          {{ SORT_OPTIONS.find(([v]) => v === filters.sort)?.[1] }} ({{ filters.order }})
        </p>
        <div class="grid">
          <ProgramCard v-for="program in results.data.value.items" :key="program.id" :program="program" />
        </div>
        <PaginationBar
          :page="results.data.value.page"
          :page-size="results.data.value.page_size"
          :total-items="results.data.value.total_items"
          :total-pages="results.data.value.total_pages"
          @update:page="setPage"
        />
      </div>
    </AsyncState>

    <p class="small muted">
      Not sure where to start? Browse
      <RouterLink to="/destinations">destination guides</RouterLink> for official visa/work rules and
      living-cost context by country and city.
    </p>
  </div>
</template>
