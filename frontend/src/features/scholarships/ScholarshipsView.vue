<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { catalog } from '../../services/api/catalog'
import { finance } from '../../services/api/finance'
import { useAsync } from '../../composables/useAsync'
import { useDebouncedValue } from '../../composables/useDebouncedValue'
import { useAuthStore } from '../../stores/auth'
import { formatMoney, formatDate, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import type { ScholarshipDetail } from '../../types/api'

const route = useRoute()
const auth = useAuthStore()

type Tab = 'scholarships' | 'funding' | 'matches'
const activeTab = ref<Tab>((['scholarships', 'funding', 'matches'] as string[]).includes(String(route.query.tab)) ? (String(route.query.tab) as Tab) : 'scholarships')
const search = ref(typeof route.query.q === 'string' ? route.query.q : '')
const country = ref(typeof route.query.country === 'string' ? route.query.country : '')
const fundingType = ref('')
const page = ref(1)
const debouncedSearch = useDebouncedValue(search, 350)

const countriesState = useAsync(() => catalog.countries(), { immediate: true })

const scholarships = useAsync(
  () =>
    activeTab.value === 'scholarships'
      ? catalog.scholarships({ q: debouncedSearch.value.trim() || undefined, country: country.value || undefined, page: page.value, page_size: 10 })
      : Promise.resolve(null),
  { immediate: true },
)

const funding = useAsync(
  () =>
    activeTab.value === 'funding'
      ? catalog.funding({ opportunity_type: fundingType.value || undefined, q: debouncedSearch.value.trim() || undefined, country: country.value || undefined, page: page.value, page_size: 10 })
      : Promise.resolve(null),
  { immediate: true },
)

const matches = useAsync(
  () => (activeTab.value === 'matches' ? finance.scholarshipMatches() : Promise.resolve(null)),
  { immediate: true },
)

watch([activeTab, debouncedSearch, country, fundingType], () => {
  page.value = 1
})
watch([activeTab, page, debouncedSearch, country, fundingType], () => {
  void scholarships.run()
  void funding.run()
  if (activeTab.value === 'matches') void matches.run()
})

function selectTab(tab: Tab) {
  activeTab.value = tab
}

// -------------------------------------------------------------- expandable detail

const expanded = ref<string | null>(null)
const detail = useAsync(
  () => (expanded.value ? catalog.scholarship(expanded.value) : Promise.resolve(null)),
  { immediate: false },
)

function toggleDetail(id: string) {
  if (expanded.value === id) {
    expanded.value = null
    return
  }
  expanded.value = id
  void detail.run()
}

function amountText(s: { amount: { min: number | null; max: number | null; currency: string; status: string } }): string {
  const { min, max, currency } = s.amount
  if (min === null && max === null) return 'Not published'
  if (min !== null && max !== null && min !== max) return `${formatMoney(min, currency)} - ${formatMoney(max, currency)}`
  return formatMoney(min ?? max, currency)
}

function rules(detailItem: ScholarshipDetail | null): { label: string; expectation: string }[] {
  if (!detailItem) return []
  return detailItem.eligibility_rules.map((rule) => ({
    label: humanize(rule.rule_key),
    expectation: `${humanize(rule.operator)} ${typeof rule.expected_value === 'object' ? JSON.stringify(rule.expected_value) : String(rule.expected_value ?? '')}${rule.is_mandatory ? ' (mandatory)' : ''}`,
  }))
}

const FUNDING_TYPES = ['grant', 'fellowship', 'exam_scheme', 'government_scheme', 'other']
</script>

<template>
  <div class="stack">
    <div>
      <h1>Scholarships and funding</h1>
      <p class="muted small" style="margin: 0">
        Catalogue of scholarships and funding opportunities with published rules, deadlines and
        sources. Matching checks those rules against your profile - it is evidence, not a promise.
      </p>
    </div>

    <div class="tabs" role="tablist" aria-label="Funding sections">
      <button type="button" role="tab" :aria-selected="activeTab === 'scholarships'" @click="selectTab('scholarships')">
        Scholarships
      </button>
      <button type="button" role="tab" :aria-selected="activeTab === 'funding'" @click="selectTab('funding')">
        Funding opportunities
      </button>
      <button type="button" role="tab" :aria-selected="activeTab === 'matches'" @click="selectTab('matches')">
        Match my profile
      </button>
    </div>

    <!-- filters -->
    <section v-if="activeTab !== 'matches'" class="card">
      <div class="grid">
        <div class="field" style="margin-bottom: 0">
          <label for="fund-q">Search</label>
          <input id="fund-q" v-model="search" type="search" placeholder="Name or provider…" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label for="fund-country">Country</label>
          <select id="fund-country" v-model="country">
            <option value="">Any country</option>
            <option v-for="item in countriesState.data.value?.items ?? []" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </div>
        <div v-if="activeTab === 'funding'" class="field" style="margin-bottom: 0">
          <label for="fund-type">Type</label>
          <select id="fund-type" v-model="fundingType">
            <option value="">Any type</option>
            <option v-for="type in FUNDING_TYPES" :key="type" :value="type">{{ humanize(type) }}</option>
          </select>
        </div>
      </div>
    </section>

    <!-- matches tab -->
    <section v-if="activeTab === 'matches'" class="stack">
      <div v-if="!auth.isAuthenticated" class="banner banner-info">
        <RouterLink :to="{ path: '/login', query: { redirect: route.fullPath } }">Log in</RouterLink>
        with a completed profile to check published scholarship rules against your answers.
      </div>
      <AsyncState
        v-else
        :loading="matches.loading.value"
        :error="matches.error.value"
        :empty="!matches.data.value?.items.length"
        empty-title="No scholarships to match"
        empty-hint="The catalogue has no scholarships yet - check back after the next data refresh."
        @retry="matches.run"
      >
        <div v-if="matches.data.value" class="stack">
          <p class="banner banner-info" style="margin: 0">{{ matches.data.value.note }}</p>
          <article v-for="match in matches.data.value.items" :key="match.scholarship_id" class="card stack-sm">
            <div class="row-between">
              <h3 style="margin: 0">{{ match.name }}</h3>
              <StatusBadge :status="match.match_status" />
            </div>
            <p class="small muted" style="margin: 0">
              {{ match.provider_name }} · {{ amountText({ amount: { ...match.amount, status: 'unknown' } }) }}
              <template v-if="match.deadline"> · deadline {{ formatDate(match.deadline) }}</template>
            </p>
            <ul class="timeline" style="margin: 4px 0 0">
              <li v-for="outcome in match.outcomes" :key="outcome.rule">
                <div class="row">
                  <StatusBadge :status="outcome.status" />
                  <strong class="small">{{ humanize(outcome.rule) }}</strong>
                </div>
                <p class="small muted" style="margin: 2px 0">{{ outcome.explanation }}</p>
              </li>
            </ul>
            <div v-if="match.unverified.length" class="row">
              <span v-for="item in match.unverified" :key="item" class="badge badge-info">
                unverified: {{ humanize(item) }}
              </span>
            </div>
            <a v-if="match.official_url" class="btn btn-sm" :href="match.official_url" target="_blank" rel="noopener noreferrer">
              Official source ↗
            </a>
          </article>
        </div>
      </AsyncState>
    </section>

    <!-- scholarships tab -->
    <AsyncState
      v-else-if="activeTab === 'scholarships'"
      :loading="scholarships.loading.value"
      :error="scholarships.error.value"
      :empty="!scholarships.data.value?.items.length"
      empty-title="No scholarships match"
      empty-hint="Try a different search term or clear the country filter."
      @retry="scholarships.run"
    >
      <div v-if="scholarships.data.value" class="stack">
        <article v-for="item in scholarships.data.value.items" :key="item.id" class="card stack-sm">
          <div class="row-between">
            <h3 style="margin: 0">{{ item.name }}</h3>
            <StatusBadge :status="item.status" />
          </div>
          <p class="small muted" style="margin: 0">
            {{ item.provider_name }}
            <template v-if="item.country_code"> · {{ item.country_code }}</template>
            <template v-if="item.award_type"> · {{ humanize(item.award_type) }}</template>
            <template v-if="item.renewable"> · renewable</template>
            <template v-if="item.deadline"> · deadline {{ formatDate(item.deadline) }}</template>
          </p>
          <p class="small" style="margin: 0">
            <strong>Award:</strong> {{ amountText({ amount: { ...item.amount } }) }}
          </p>
          <div class="row">
            <button class="btn btn-sm" type="button" @click="toggleDetail(item.id)">
              {{ expanded === item.id ? 'Hide eligibility' : 'Show eligibility rules' }}
            </button>
            <a v-if="item.official_url" class="btn btn-sm btn-quiet" :href="item.official_url" target="_blank" rel="noopener noreferrer">
              Official source ↗
            </a>
          </div>
          <div v-if="expanded === item.id" class="card card-flat">
            <AsyncState :loading="detail.loading.value" :error="detail.error.value" :empty="!detail.data.value" @retry="detail.run">
              <div v-if="detail.data.value" class="stack-sm">
                <div class="table-wrap">
                  <table class="data">
                    <thead>
                      <tr>
                        <th>Rule</th>
                        <th>Published expectation</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="rule in rules(detail.data.value)" :key="rule.label">
                        <td>{{ rule.label }}</td>
                        <td class="small">{{ rule.expectation }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p v-if="detail.data.value.linked_program_ids.length" class="small muted" style="margin: 0">
                  Linked programmes: {{ detail.data.value.linked_program_ids.length }}
                </p>
                <p class="small muted" style="margin: 0">
                  Rules are published criteria - always confirm on the official page before applying.
                </p>
              </div>
            </AsyncState>
          </div>
        </article>
        <PaginationBar
          :page="scholarships.data.value.page"
          :page-size="scholarships.data.value.page_size"
          :total-items="scholarships.data.value.total_items"
          :total-pages="scholarships.data.value.total_pages"
          @update:page="(next) => (page = next)"
        />
      </div>
    </AsyncState>

    <!-- funding tab -->
    <AsyncState
      v-else
      :loading="funding.loading.value"
      :error="funding.error.value"
      :empty="!funding.data.value?.items.length"
      empty-title="No funding opportunities match"
      empty-hint="Try a different filter."
      @retry="funding.run"
    >
      <div v-if="funding.data.value" class="stack">
        <article v-for="item in funding.data.value.items" :key="item.id" class="card stack-sm">
          <div class="row-between">
            <h3 style="margin: 0">{{ item.name }}</h3>
            <StatusBadge :status="item.status" />
          </div>
          <p class="small muted" style="margin: 0">
            {{ item.provider_name }} · {{ humanize(item.opportunity_type) }}
            <template v-if="item.deadline"> · deadline {{ formatDate(item.deadline) }}</template>
          </p>
          <p v-if="item.award_summary" class="small" style="margin: 0">{{ item.award_summary }}</p>
          <p class="small muted" style="margin: 0">
            Eligible: {{ item.eligible_countries.join(', ') || 'various' }} · levels:
            {{ item.study_levels.map(humanize).join(', ') || 'various' }}
          </p>
          <a v-if="item.official_url" class="btn btn-sm" :href="item.official_url" target="_blank" rel="noopener noreferrer">
            Official source ↗
          </a>
        </article>
        <PaginationBar
          :page="funding.data.value.page"
          :page-size="funding.data.value.page_size"
          :total-items="funding.data.value.total_items"
          :total-pages="funding.data.value.total_pages"
          @update:page="(next) => (page = next)"
        />
      </div>
    </AsyncState>

    <p class="small muted">
      Matching and catalogue data reflect published rules at the last review - deadlines move and
      criteria change. Treat every result as a starting point for your own verification.
    </p>
  </div>
</template>
