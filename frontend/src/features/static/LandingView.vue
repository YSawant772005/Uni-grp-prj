<script setup lang="ts">
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()

const principles = [
  {
    title: 'Fit, with reasons',
    body: 'Shortlist runs group programs into Ambitious, Target and Safer-fit tiers and explain every score, concern and missing input. Tiers are a fit heuristic, never an admission probability.',
  },
  {
    title: 'Affordability you can trace',
    body: 'Full-degree cost models show tuition, fees, living expenses and conversions separately - with currency, period, academic year and the source behind each number.',
  },
  {
    title: 'Funding, honestly matched',
    body: 'Scholarship matching checks published rules against your profile and shows which rules passed, failed or could not be verified. No award is ever promised.',
  },
  {
    title: 'Career evidence in scope',
    body: 'Outcome metrics arrive with cohort, year, sample size and population scope, so you can see exactly how far the evidence reaches before you trust it.',
  },
  {
    title: 'Sources on every fact',
    body: 'Each material fact links to its evidence: source, retrieval time, verification state and whether the value is official, estimated, user-provided or unavailable.',
  },
  {
    title: 'Unknown stays unknown',
    body: 'Missing data is labelled "Not available" - it is never shown as zero and never silently blended into totals.',
  },
]
</script>

<template>
  <div class="page stack">
    <section class="hero">
      <h1>Build a Master's shortlist you can defend - with evidence attached</h1>
      <p>
        UniShortlist helps Indian applicants compare international Master's programs on eligibility,
        fit, cost, funding and career outcomes. Every number carries its source and its uncertainty,
        so you can trust what you decide on.
      </p>
      <div class="row" style="margin-top: 18px">
        <RouterLink v-if="!auth.isAuthenticated" to="/signup" class="btn btn-primary">
          Create your free profile
        </RouterLink>
        <RouterLink v-else to="/onboarding" class="btn btn-primary">Finish your profile</RouterLink>
        <RouterLink to="/discover" class="btn">Explore programs</RouterLink>
        <RouterLink v-if="!auth.isAuthenticated" to="/login" class="btn btn-quiet">Log in</RouterLink>
      </div>
    </section>

    <section class="grid" style="margin-top: 8px">
      <article v-for="item in principles" :key="item.title" class="card">
        <h3>{{ item.title }}</h3>
        <p class="small muted" style="margin: 0">{{ item.body }}</p>
      </article>
    </section>

    <section class="card">
      <h2>How it works</h2>
      <ol class="stack-sm" style="padding-left: 20px">
        <li><strong>Answer eight quick questions</strong> - degree, field, destinations, academics, English test, budget and intake. You can resume any time.</li>
        <li><strong>Generate a shortlist</strong> - programs are grouped by fit with explanations, concerns and the information that could change the result.</li>
        <li><strong>Verify what matters</strong> - open any program to inspect requirements, fees, intakes and the evidence behind each fact.</li>
        <li><strong>Model your finances</strong> - low/base/high cost scenarios, scholarship matching, loan EMI schedules and career-evidence views.</li>
      </ol>
    </section>

    <section class="banner banner-info">
      <strong>What this tool does not do:</strong> it does not guarantee admission, scholarships,
      visas, jobs, salaries or return on investment, and it is not immigration or financial advice.
      Catalogue facts are versioned and reviewed by humans; some values are estimates or may be
      stale - each one says so. Read the
      <RouterLink to="/terms">terms and limitations</RouterLink>.
    </section>
  </div>
</template>
