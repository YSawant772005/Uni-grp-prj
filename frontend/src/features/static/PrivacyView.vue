<template>
  <main id="privacy-top" class="ulg-legal ulg-privacy">
    <section class="ulg-hero" aria-labelledby="privacy-heading">
      <div class="ulg-hero-copy">
        <p class="ulg-eyebrow"><span class="ulg-status-dot" /> UNISHORTLIST / YOUR DATA</p>
        <h1 id="privacy-heading">Your privacy, <span>made clear.</span></h1>
        <p class="ulg-lead">Plain-language summary of what this application stores and why.</p>
        <div class="ulg-hero-links">
          <a class="ulg-button ulg-button-primary" href="#privacy-stored">Explore the policy <span aria-hidden="true">↗</span></a>
          <RouterLink class="ulg-button ulg-button-outline" to="/profile">View your profile <span aria-hidden="true">→</span></RouterLink>
        </div>
      </div>
      <div class="ulg-hero-art" aria-hidden="true">
        <div class="ulg-orbit ulg-orbit-outer" />
        <div class="ulg-orbit ulg-orbit-inner" />
        <div class="ulg-float ulg-float-main"><span class="ulg-shield">✓</span><strong>Privacy first</strong><small>Understand how your data is used</small></div>
        <div class="ulg-float ulg-float-one"><span>◈</span> Your information</div>
        <div class="ulg-float ulg-float-two"><span>✓</span> Your controls</div>
      </div>
    </section>

    <div class="ulg-quick-notes" aria-label="Privacy overview">
      <div class="ulg-quick-note"><span class="ulg-quick-icon">01</span><div><strong>What you share</strong><small>Account, profile and activity</small></div></div>
      <div class="ulg-quick-note"><span class="ulg-quick-icon">02</span><div><strong>What we don't do</strong><small>No advertiser data sales</small></div></div>
      <div class="ulg-quick-note"><span class="ulg-quick-icon">03</span><div><strong>Your controls</strong><small>Review your profile details</small></div></div>
    </div>

    <div class="ulg-layout">
      <aside class="ulg-sidebar" aria-label="Privacy sections">
        <div class="ulg-sidebar-inner">
          <p class="ulg-side-label">ON THIS PAGE</p>
          <nav class="ulg-side-nav" aria-label="Privacy policy table of contents">
            <a href="#privacy-stored"><span>01</span> What we store</a>
            <a href="#privacy-never"><span>02</span> What we never do</a>
            <a href="#privacy-controls"><span>03</span> Your controls</a>
          </nav>
          <div class="ulg-sidebar-help">
            <span class="ulg-side-help-symbol" aria-hidden="true">✦</span>
            <strong>Keep your details current</strong>
            <p>Review the answers that help power your study-abroad experience.</p>
            <RouterLink to="/profile">Open profile <span aria-hidden="true">→</span></RouterLink>
          </div>
        </div>
      </aside>

      <div class="ulg-content">
        <div class="ulg-intro">
          <span class="ulg-mini-eyebrow">THE ESSENTIALS</span>
          <h2>A clearer view of your information</h2>
          <p>Jump between sections or read from top to bottom.</p>
        </div>

        <section id="privacy-stored" class="ulg-card" aria-labelledby="privacy-stored-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">01</span><div><p class="ulg-section-kicker">INFORMATION</p><h2 id="privacy-stored-heading">What we store</h2></div></div>
          <ul class="ulg-feature-list">
            <li><strong>Account:</strong> your email address and a salted password hash. Passwords are never stored or logged in plain text.</li>
            <li><strong>Profile:</strong> the answers you provide in onboarding (academics, English test, budget, destinations, intake). These drive eligibility, cost and matching computations only.</li>
            <li><strong>Your activity:</strong> saved programs, comparison sets, recommendation runs, cost/loan/ROI scenarios you create. Each run keeps a snapshot of the inputs used, so past results stay reproducible.</li>
            <li><strong>Administration:</strong> reviewers' fact decisions and system audit events (who changed what, when, with which request id). Audit entries are append-only.</li>
          </ul>
        </section>

        <section id="privacy-never" class="ulg-card" aria-labelledby="privacy-never-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">02</span><div><p class="ulg-section-kicker">OUR BOUNDARIES</p><h2 id="privacy-never-heading">What we never do</h2></div></div>
          <ul class="ulg-feature-list ulg-check-list">
            <li>No selling or sharing your personal data with advertisers.</li>
            <li>No putting tokens or private data in URLs; sessions use HttpOnly cookies only.</li>
            <li>No hidden tracking - the app loads no third-party analytics in this release.</li>
            <li>No automated scraping of sources whose usage policy does not permit it; refresh jobs record retrieval metadata and never publish unreviewed values.</li>
          </ul>
        </section>

        <section id="privacy-controls" class="ulg-card" aria-labelledby="privacy-controls-heading">
          <div class="ulg-card-title-row"><span class="ulg-section-icon" aria-hidden="true">03</span><div><p class="ulg-section-kicker">YOUR CHOICES</p><h2 id="privacy-controls-heading">Your controls</h2></div></div>
          <p>
            You can view your stored profile at any time under <RouterLink to="/profile">Profile</RouterLink>.
            Account deletion and data export are not enabled in this release; when they are, they will
            require identity verification and follow the documented retention policy.
          </p>
          <div class="ulg-inline-action"><RouterLink to="/profile">Review your stored profile <span aria-hidden="true">↗</span></RouterLink></div>
        </section>

        <div class="ulg-bottom-bar"><span>UniShortlist · Privacy</span><a href="#privacy-top">Back to top ↑</a></div>
      </div>
    </div>
  </main>
</template>

<style src="./legal-pages.css"></style>
