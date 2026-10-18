<template>
  <div class="page stack" style="max-width: 760px">
    <h1>Privacy</h1>
    <p class="muted">Plain-language summary of what this application stores and why.</p>

    <section class="card">
      <h2>What we store</h2>
      <ul class="stack-sm">
        <li><strong>Account:</strong> your email address and a salted password hash. Passwords are never stored or logged in plain text.</li>
        <li><strong>Profile:</strong> the answers you provide in onboarding (academics, English test, budget, destinations, intake). These drive eligibility, cost and matching computations only.</li>
        <li><strong>Your activity:</strong> saved programs, comparison sets, recommendation runs, cost/loan/ROI scenarios you create. Each run keeps a snapshot of the inputs used, so past results stay reproducible.</li>
        <li><strong>Administration:</strong> reviewers' fact decisions and system audit events (who changed what, when, with which request id). Audit entries are append-only.</li>
      </ul>
    </section>

    <section class="card">
      <h2>What we never do</h2>
      <ul class="stack-sm">
        <li>No selling or sharing your personal data with advertisers.</li>
        <li>No putting tokens or private data in URLs; sessions use HttpOnly cookies only.</li>
        <li>No hidden tracking - the app loads no third-party analytics in this release.</li>
        <li>No automated scraping of sources whose usage policy does not permit it; refresh jobs record retrieval metadata and never publish unreviewed values.</li>
      </ul>
    </section>

    <section class="card">
      <h2>Your controls</h2>
      <p>
        You can view your stored profile at any time under <RouterLink to="/profile">Profile</RouterLink>.
        Account deletion and data export are not enabled in this release; when they are, they will
        require identity verification and follow the documented retention policy.
      </p>
    </section>
  </div>
</template>
