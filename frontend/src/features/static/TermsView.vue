<template>
  <div class="page stack" style="max-width: 760px">
    <h1>Terms and limitations</h1>
    <p class="muted">Read this before relying on anything this tool tells you.</p>

    <section class="card">
      <h2>Decision support, not decisions</h2>
      <p>
        This is an evidence-first decision-support tool. It does <strong>not</strong> guarantee or
        imply admission, scholarship awards, visa approval, employment, salary levels or return on
        investment. Tiers ("Ambitious", "Target", "Safer-fit") describe how your profile compares to
        published requirements and preferences - they are not admission probabilities.
      </p>
    </section>

    <section class="card">
      <h2>Data quality is visible, not implied</h2>
      <ul class="stack-sm">
        <li>Facts carry a status: <em>verified</em>, <em>unverified</em>, <em>estimated</em>, <em>stale</em>, <em>conflicted</em> or <em>unavailable</em>.</li>
        <li>Unknown values are shown as "Not available" and excluded from totals - never displayed as zero.</li>
        <li>Money facts keep their currency, time period, academic year/intake and source. Conversions show the rate, its date and its source.</li>
        <li>Some catalogue entries in this deployment are clearly labelled synthetic demo fixtures (example.invalid domains). They are for demonstration only.</li>
      </ul>
    </section>

    <section class="card">
      <h2>Tools are illustrative</h2>
      <p>
        Cost estimates combine published facts with stated assumptions; loan scenarios are
        illustrative amortization schedules and not financial advice - approval and terms are never
        guaranteed. ROI views report evidence scope (program, institution, subject, country or broad
        benchmark) and say "no positive surplus" or "unknown" rather than inventing a payback period.
      </p>
    </section>

    <section class="card">
      <h2>Sources and automated refresh</h2>
      <p>
        Only sources whose recorded usage policy permits automated fetching are refreshed, retrieval
        metadata is stored, and no fetched value is published without passing validation and the
        human review queue. Every review action and administrative change is recorded in an
        append-only audit log.
      </p>
    </section>
  </div>
</template>
