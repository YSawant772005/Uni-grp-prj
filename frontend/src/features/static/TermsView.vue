<template>
  <main id="terms-top" class="ulg-legal ulg-terms">
    <section class="ulg-hero" aria-labelledby="terms-heading">
      <div class="ulg-hero-copy">
        <p class="ulg-eyebrow"><span class="ulg-status-dot" /> UNISHORTLIST / IMPORTANT INFORMATION</p>
        <h1 id="terms-heading">Know the details. <span>Decide with confidence.</span></h1>
        <p class="ulg-lead">Read this before relying on anything this tool tells you.</p>
        <div class="ulg-hero-links">
          <a class="ulg-button ulg-button-primary" href="#terms-decisions">Read the limitations <span aria-hidden="true">↗</span></a>
          <RouterLink class="ulg-button ulg-button-outline" to="/discover">Explore programs <span aria-hidden="true">→</span></RouterLink>
        </div>
      </div>
      <div class="ulg-hero-art" aria-hidden="true">
        <div class="ulg-orbit ulg-orbit-outer" />
        <div class="ulg-orbit ulg-orbit-inner" />
        <div class="ulg-float ulg-float-main"><span class="ulg-shield">≋</span><strong>Evidence first</strong><small>Clear facts, visible limitations</small></div>
        <div class="ulg-float ulg-float-one"><span>✦</span> Know the evidence</div>
        <div class="ulg-float ulg-float-two"><span>✓</span> Check the source</div>
      </div>
    </section>

    <div class="ulg-quick-notes" aria-label="Terms overview">
      <div class="ulg-quick-note"><span class="ulg-quick-icon">01</span><div><strong>No admission guarantees</strong><small>Support for decisions, not promises</small></div></div>
      <div class="ulg-quick-note"><span class="ulg-quick-icon">02</span><div><strong>Visible data quality</strong><small>Evidence is labeled clearly</small></div></div>
      <div class="ulg-quick-note"><span class="ulg-quick-icon">03</span><div><strong>Illustrative estimates</strong><small>Costs and ROI are not predictions</small></div></div>
    </div>

    <div class="ulg-layout">
      <aside class="ulg-sidebar" aria-label="Terms and limitations sections">
        <div class="ulg-sidebar-inner">
          <p class="ulg-side-label">ON THIS PAGE</p>
          <nav class="ulg-side-nav" aria-label="Terms and limitations table of contents">
            <a href="#terms-decisions"><span>01</span> Decision support</a>
            <a href="#terms-data"><span>02</span> Data quality</a>
            <a href="#terms-tools"><span>03</span> Illustrative tools</a>
            <a href="#terms-sources"><span>04</span> Sources and review</a>
          </nav>
          <div class="ulg-sidebar-help">
            <span class="ulg-side-help-symbol" aria-hidden="true">✦</span>
            <strong>Use evidence thoughtfully</strong>
            <p>Review eligibility and cost information before making study decisions.</p>
            <RouterLink to="/discover">Browse programs <span aria-hidden="true">→</span></RouterLink>
          </div>
        </div>
      </aside>

      <div class="ulg-content">
        <div class="ulg-intro">
          <span class="ulg-mini-eyebrow">HOW TO USE UNISHORTLIST</span>
          <h2>Helpful tools. Clear expectations.</h2>
          <p>Understand how recommendations, estimated costs, and evidence should be interpreted.</p>
        </div>

        <section id="terms-decisions" class="ulg-card" aria-labelledby="terms-decisions-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">01</span><div><p class="ulg-section-kicker">DECISION SUPPORT</p><h2 id="terms-decisions-heading">Decision support, not decisions</h2></div></div>
          <p>
            This is an evidence-first decision-support tool. It does <strong>not</strong> guarantee or
            imply admission, scholarship awards, visa approval, employment, salary levels or return on
            investment. Tiers ("Ambitious", "Target", "Safer-fit") describe how your profile compares to
            published requirements and preferences - they are not admission probabilities.
          </p>
          <div class="ulg-note"><span aria-hidden="true">!</span> Fit tiers compare available evidence; they are not admission probabilities.</div>
        </section>

        <section id="terms-data" class="ulg-card" aria-labelledby="terms-data-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">02</span><div><p class="ulg-section-kicker">DATA TRANSPARENCY</p><h2 id="terms-data-heading">Data quality is visible, not implied</h2></div></div>
          <ul class="ulg-feature-list">
            <li>Facts carry a status: <em>verified</em>, <em>unverified</em>, <em>estimated</em>, <em>stale</em>, <em>conflicted</em> or <em>unavailable</em>.</li>
            <li>Unknown values are shown as "Not available" and excluded from totals - never displayed as zero.</li>
            <li>Money facts keep their currency, time period, academic year/intake and source. Conversions show the rate, its date and its source.</li>
            <li>Some catalogue entries in this deployment are clearly labelled synthetic demo fixtures (example.invalid domains). They are for demonstration only.</li>
          </ul>
        </section>

        <section id="terms-tools" class="ulg-card" aria-labelledby="terms-tools-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">03</span><div><p class="ulg-section-kicker">ESTIMATES AND SCENARIOS</p><h2 id="terms-tools-heading">Tools are illustrative</h2></div></div>
          <p>
            Cost estimates combine published facts with stated assumptions; loan scenarios are
            illustrative amortization schedules and not financial advice - approval and terms are never
            guaranteed. ROI views report evidence scope (program, institution, subject, country or broad
            benchmark) and say "no positive surplus" or "unknown" rather than inventing a payback period.
          </p>
        </section>

        <section id="terms-sources" class="ulg-card" aria-labelledby="terms-sources-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">04</span><div><p class="ulg-section-kicker">VERIFICATION</p><h2 id="terms-sources-heading">Sources and automated refresh</h2></div></div>
          <p>
            Only sources whose recorded usage policy permits automated fetching are refreshed, retrieval
            metadata is stored, and no fetched value is published without passing validation and the
            human review queue. Every review action and administrative change is recorded in an
            append-only audit log.
          </p>
        </section>

        <div class="ulg-bottom-bar"><span>UniShortlist · Terms and limitations</span><a href="#terms-top">Back to top ↑</a></div>
      </div>
    </div>
  </main>
</template>

<style src="./legal-pages.css"></style>
