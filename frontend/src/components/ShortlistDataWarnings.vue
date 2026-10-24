<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ warnings: string[]; demo?: boolean }>()

type WarningDetail = { code: string; title: string; detail: string; category: 'Costs' | 'Outcomes' | 'Matching' | 'Other' }
const captions: Record<string, Omit<WarningDetail, 'code'>> = {
  affordability_unavailable: { title: 'Budget fit cannot be calculated', detail: 'A complete total in your chosen currency is not available yet.', category: 'Costs' },
  living_unknown: { title: 'Living expenses are missing', detail: 'No living-cost figures are available for one or more programs.', category: 'Costs' },
  tuition_unknown: { title: 'Tuition fees are missing', detail: 'The catalogue has no usable tuition amount for one or more programs.', category: 'Costs' },
  no_cost_components: { title: 'Study cost breakdown is incomplete', detail: 'The estimate has no usable tuition or living-cost components; missing amounts are not treated as zero.', category: 'Costs' },
  outcomes_unavailable: { title: 'Graduate outcomes are unavailable', detail: 'Reliable employment or graduate-salary data is not available for these programs.', category: 'Outcomes' },
  no_budget_currency: { title: 'Budget currency is missing', detail: 'Select a currency in your profile to compare estimated costs.', category: 'Costs' },
  no_exact_degree_and_specialization_match_in_current_catalogue: { title: 'No exact degree and specialization match', detail: 'The current program catalogue has no entry matching both of your selections.', category: 'Matching' },
  desired_degree_title_missing_recomplete_profile_for_exact_matching: { title: 'Desired degree needs confirmation', detail: 'Reopen Academic Profile to select and save the full Master’s award title.', category: 'Matching' },
}
function label(code: string): WarningDetail {
  if (captions[code]) return { code, ...captions[code] }
  if (code.startsWith('no_fx_rate_')) return {
    code, title: 'Currency conversion unavailable',
    detail: 'A reference exchange rate is missing, so this amount cannot be compared with your budget.', category: 'Costs',
  }
  return {
    code,
    title: code.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    detail: 'This information could not be verified for the current recommendation run.',
    category: 'Other',
  }
}
const details = computed(() => [...new Set(props.warnings ?? [])].map(label))
</script>

<template>
  <section v-if="details.length || demo" class="data-health" aria-label="Recommendation data quality">
    <div v-if="demo" class="demo-alert" role="note">
      <span class="demo-indicator" aria-hidden="true">TEST</span>
      <span><strong>Fictional university data.</strong> Tuition and living-cost amounts, where shown, are synthetic examples for testing—not verified prices, quotes, or admissions information.</span>
    </div>
    <details v-if="details.length" class="quality-details">
      <summary>
        <span class="quality-summary-main"><span class="quality-icon" aria-hidden="true">ⓘ</span><strong>{{ details.length }} {{ details.length === 1 ? 'data note' : 'data notes' }}</strong><span class="quality-summary-note">See what's missing or estimated</span></span>
        <span class="quality-chevron" aria-hidden="true">⌄</span>
      </summary>
      <div class="quality-list">
        <article v-for="warning in details" :key="warning.code" class="quality-row">
          <span class="quality-category">{{ warning.category }}</span>
          <div><strong>{{ warning.title }}</strong><p>{{ warning.detail }}</p></div>
        </article>
      </div>
    </details>
  </section>
</template>

<style scoped>
.data-health { display: grid; gap: 10px; margin-bottom: 18px; min-width: 0; }
.demo-alert { display: flex; align-items: center; gap: 12px; border: 1px solid #c9e2d9; border-radius: 12px; background: #eaf7f2; padding: 12px 16px; color: #315e4e; font-size: .84rem; line-height: 1.5; }
.demo-alert strong { color: #155f48; }
.demo-indicator { flex: none; font-weight: 800; font-size: .68rem; letter-spacing: .065em; color: #fff; background: #07855b; border-radius: 6px; padding: 4px 8px; }
.quality-details { border: 1px solid #eedebd; background: #fffbf3; border-radius: 12px; color: #5f4c29; }
.quality-details summary { display: flex; align-items: center; justify-content: space-between; padding: 13px 16px; cursor: pointer; list-style: none; gap: 12px; }
.quality-details summary::-webkit-details-marker { display: none; }
.quality-summary-main { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; }
.quality-summary-main strong { font-size: .88rem; color: #76551d; }
.quality-summary-note { font-size: .78rem; color: #947d56; }
.quality-icon { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 7px; background: #f6e9ce; color: #85601e; font-size: 1rem; }
.quality-chevron { font-size: 1.2rem; color: #8f682e; transition: transform .18s; }
.quality-details[open] .quality-chevron { transform: rotate(180deg); }
.quality-list { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 0 18px; margin: 0 16px 16px; border-top: 1px solid #f0e4ce; }
.quality-row { display: grid; grid-template-columns: 80px minmax(0,1fr); gap: 10px; padding: 13px 2px; border-bottom: 1px solid #f0e4ce; min-width: 0; }
.quality-category { font-size: .7rem; text-transform: uppercase; letter-spacing: .055em; color: #967649; font-weight: 750; padding-top: 3px; }
.quality-row strong { display: block; font-size: .84rem; color: #59462b; }
.quality-row p { margin: 4px 0 0; font-size: .77rem; line-height: 1.55; color: #8a7553; }
@media (max-width: 650px) { .quality-list { grid-template-columns: 1fr; } .quality-row { grid-template-columns: 70px minmax(0,1fr); } .quality-summary-note { display: none; } .demo-alert { align-items: flex-start; } }
</style>
