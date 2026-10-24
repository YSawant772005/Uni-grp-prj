<script setup lang="ts">
import { onMounted as landingPremiumMounted, onBeforeUnmount as landingPremiumBeforeUnmount } from 'vue'
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const startPath = computed(() => (auth.isAuthenticated ? '/onboarding' : '/signup'))
const startLabel = computed(() => (auth.isAuthenticated ? 'Continue your profile' : 'Start your shortlist'))

const steps = [
  {
    number: '01',
    title: 'Tell us about you',
    description: 'Add your academics, target countries, preferred field, budget and intake. Save your progress as you go.',
    tag: 'Your profile',
  },
  {
    number: '02',
    title: 'Explore your fit',
    description: 'Review program matches with clear eligibility checks, fit explanations and what still needs verification.',
    tag: 'Your matches',
  },
  {
    number: '03',
    title: 'Plan the bigger picture',
    description: 'Compare options side by side, explore scholarships and understand the total cost before you decide.',
    tag: 'Your decision',
  },
]

const features = [
  {
    icon: '◎',
    tone: 'mint',
    title: 'Meaningful program matches',
    description: 'See why a program fits your profile, not just another list of university names.',
    to: '/discover',
    link: 'Discover programs',
  },
  {
    icon: '✓',
    tone: 'blue',
    title: 'Eligibility, made clear',
    description: 'Understand published requirements, conditional checks and missing information.',
    to: '/discover',
    link: 'Explore requirements',
  },
  {
    icon: '≋',
    tone: 'amber',
    title: 'See the full cost',
    description: 'Look beyond tuition with living costs, currencies and scenario-based estimates.',
    to: '/finance',
    link: 'Explore costs',
  },
  {
    icon: '✳',
    tone: 'violet',
    title: 'Scholarship guidance',
    description: 'Review funding criteria and where eligibility is confirmed, conditional or unknown.',
    to: '/scholarships',
    link: 'Explore scholarships',
  },
  {
    icon: '⇄',
    tone: 'peach',
    title: 'Side-by-side comparisons',
    description: 'Keep the factors that matter to you visible when weighing different programs.',
    to: '/compare',
    link: 'Compare programs',
  },
  {
    icon: '↗',
    tone: 'sky',
    title: 'Outcomes in context',
    description: 'Explore career evidence and financial scenarios with limitations clearly labelled.',
    to: '/roi',
    link: 'Explore outcomes',
  },
]

const destinations = [
  { flag: '🇺🇸', country: 'United States', caption: 'Explore US study options', code: 'US', tint: 'rose' },
  { flag: '🇬🇧', country: 'United Kingdom', caption: 'Explore UK study options', code: 'GB', tint: 'sky' },
  { flag: '🇩🇪', country: 'Germany', caption: 'Explore German study options', code: 'DE', tint: 'amber' },
  { flag: '🇨🇦', country: 'Canada', caption: 'Explore Canadian study options', code: 'CA', tint: 'mint' },
]

// UNISHORTLIST_LANDING_FLOAT_V2: progressive motion enhancement, no API or routing changes.
let landingPremiumTeardown: (() => void) | undefined

landingPremiumMounted(() => {
  const page = document.querySelector<HTMLElement>('.landing-page')
  if (!page || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

  const elements = page.querySelectorAll<HTMLElement>(
    '.landing-section-head, .landing-step-card, .landing-feature-card, .landing-destination-card, .landing-trust-art, .landing-trust-copy, .landing-final-cta',
  )
  let observer: IntersectionObserver | undefined
  if ('IntersectionObserver' in window) {
    observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        entry.target.classList.add('landing-upgrade-visible')
        observer?.unobserve(entry.target)
      }
    }, { threshold: 0.08, rootMargin: '0px 0px -15px 0px' })
    elements.forEach((element) => {
      element.classList.add('landing-upgrade-reveal')
      observer?.observe(element)
    })
  }

  const visual = page.querySelector<HTMLElement>('.campus-visual')
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches
  const move = (event: PointerEvent) => {
    if (!visual) return
    const rect = visual.getBoundingClientRect()
    const x = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width - 0.5) * 2))
    const y = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height - 0.5) * 2))
    visual.style.setProperty('--landing-tilt-x', `${(-y * 5.5).toFixed(2)}deg`)
    visual.style.setProperty('--landing-tilt-y', `${(x * 7).toFixed(2)}deg`)
    visual.style.setProperty('--landing-light-x', `${((x + 1) * 50).toFixed(1)}%`)
    visual.style.setProperty('--landing-light-y', `${((y + 1) * 50).toFixed(1)}%`)
  }
  const reset = () => {
    if (!visual) return
    visual.style.setProperty('--landing-tilt-x', '0deg')
    visual.style.setProperty('--landing-tilt-y', '0deg')
    visual.style.setProperty('--landing-light-x', '50%')
    visual.style.setProperty('--landing-light-y', '50%')
  }
  if (visual && finePointer) {
    visual.addEventListener('pointermove', move)
    visual.addEventListener('pointerleave', reset)
  }
  landingPremiumTeardown = () => {
    observer?.disconnect()
    if (visual && finePointer) {
      visual.removeEventListener('pointermove', move)
      visual.removeEventListener('pointerleave', reset)
    }
  }
})

landingPremiumBeforeUnmount(() => landingPremiumTeardown?.())

</script>

<template>
  <div class="landing-page">
    <section class="landing-hero" aria-labelledby="landing-heading">
      <div class="landing-container landing-hero-layout">
        <div class="landing-hero-copy">
          <p class="landing-eyebrow"><span class="landing-eyebrow-dot" /> YOUR FUTURE, A LITTLE CLEARER</p>
          <h1 id="landing-heading">
            Your next chapter starts with the <span>right university.</span>
          </h1>
          <p class="landing-lead">
            Finding a Master's abroad shouldn't feel like a guessing game. Explore programs,
            understand your fit and make decisions with the evidence in front of you.
          </p>
          <div class="landing-actions">
            <RouterLink :to="startPath" class="landing-button landing-button-primary">
              {{ startLabel }} <span aria-hidden="true">↗</span>
            </RouterLink>
            <RouterLink to="/discover" class="landing-button landing-button-secondary">
              Explore programs <span aria-hidden="true">→</span>
            </RouterLink>
          </div>
          <div class="landing-assurance" aria-label="What makes UniShortlist different">
            <span><span aria-hidden="true">✓</span> Transparent matching</span>
            <span><span aria-hidden="true">✓</span> Costs in context</span>
            <span><span aria-hidden="true">✓</span> Sources you can check</span>
          </div>
        </div>

        <!-- Decorative CSS 3D campus. All claims below describe platform features, not live university results. -->
        <div class="campus-visual" role="img" aria-label="Animated three-dimensional university campus model with floating academic profile, eligibility and comparison cards">
          <div class="campus-aura campus-aura-one" aria-hidden="true"></div>
          <div class="campus-aura campus-aura-two" aria-hidden="true"></div>
          <div class="campus-line campus-line-left" aria-hidden="true"></div>
          <div class="campus-line campus-line-right" aria-hidden="true"></div>

          <div class="campus-model" aria-hidden="true">
            <div class="campus-floor-shadow"></div>
            <div class="campus-island"></div>
            <div class="campus-island-rim"></div>
            <div class="campus-float-architecture">
              <div class="campus-architecture">
                <div class="campus-sidewall">
                  <span class="campus-side-window"></span>
                  <span class="campus-side-window"></span>
                </div>
                <div class="campus-topwall"></div>
                <div class="campus-facade">
                  <div class="campus-pediment"><span class="campus-pediment-emblem">✦</span></div>
                  <div class="campus-architrave"></div>
                  <div class="campus-pillars">
                    <span class="campus-pillar"></span>
                    <span class="campus-pillar"></span>
                    <span class="campus-door"><span></span></span>
                    <span class="campus-pillar"></span>
                    <span class="campus-pillar"></span>
                  </div>
                  <div class="campus-steps"><span></span><span></span><span></span></div>
                </div>
              </div>
              <div class="campus-grad-cap">
                <svg viewBox="0 0 100 88" fill="none" aria-hidden="true"><path d="M50 8 4 30l46 22 46-22L50 8Z" fill="#0B8260" stroke="#075B47" stroke-width="3" stroke-linejoin="round"/><path d="M23 43v18c0 10 14 17 27 17s27-7 27-17V43L50 57 23 43Z" fill="#0C644F"/><path d="M95 30v26" stroke="#D5A444" stroke-width="4" stroke-linecap="round"/><circle cx="95" cy="62" r="6" fill="#EDC46F"/></svg>
              </div>
            </div>
          </div>

          <div class="campus-chip campus-chip-program" aria-hidden="true">
            <span class="campus-chip-icon">▤</span>
            <span><strong>Find Master's programs</strong><small>Explore study options abroad</small></span>
          </div>
          <div class="campus-chip campus-chip-eligibility" aria-hidden="true">
            <span class="campus-chip-icon campus-chip-icon-check">✓</span>
            <span><strong>Understand eligibility</strong><small>Requirements made clear</small></span>
          </div>
          <div class="campus-chip campus-chip-compare" aria-hidden="true">
            <span class="campus-chip-icon campus-chip-icon-blue">⇄</span>
            <span><strong>Compare & shortlist</strong><small>Make an informed decision</small></span>
          </div>
          <span class="campus-spark campus-spark-one" aria-hidden="true">✧</span>
          <span class="campus-spark campus-spark-two" aria-hidden="true">✦</span>
          <span class="campus-spark campus-spark-three" aria-hidden="true">✧</span>
          <span class="campus-visual-footnote">Your university journey, made clearer.</span>
        </div>
      </div>
    </section>

    <div class="landing-benefit-strip">
      <div class="landing-container landing-benefits">
        <p><span aria-hidden="true">✳</span><strong>Built around your goals</strong><small>Not a one-size-fits-all list</small></p>
        <p><span aria-hidden="true">◈</span><strong>Clarity over claims</strong><small>Assumptions made visible</small></p>
        <p><span aria-hidden="true">⊙</span><strong>Evidence in every detail</strong><small>Know what has been verified</small></p>
      </div>
    </div>

    <section id="how-it-works" class="landing-section landing-container" aria-labelledby="landing-how-heading">
      <div class="landing-section-head landing-section-head-centered">
        <p class="landing-kicker">SIMPLE BY DESIGN</p>
        <h2 id="landing-how-heading">Big decisions, <span>small clear steps.</span></h2>
        <p>From "where do I begin?" to a shortlist you actually understand.</p>
      </div>
      <div class="landing-step-grid">
        <article v-for="(step, index) in steps" :key="step.number" class="landing-step-card">
          <div class="landing-step-card-top"><span>{{ step.number }}</span><span v-if="index < steps.length - 1" class="landing-step-arrow" aria-hidden="true">→</span></div>
          <div class="landing-step-icon" aria-hidden="true">
            <svg v-if="index === 0" viewBox="0 0 48 48" fill="none"><rect x="12" y="9" width="24" height="30" rx="5" /><circle cx="24" cy="21" r="4" /><path d="M17 32c1.4-4 12.6-4 14 0" /></svg>
            <svg v-else-if="index === 1" viewBox="0 0 48 48" fill="none"><rect x="7" y="12" width="34" height="26" rx="6" /><path d="M14 20h15M14 27h10M14 33h7" /><circle cx="35" cy="29" r="7" fill="currentColor" stroke="none" /><path d="m32 29 2 2 4-4" stroke="white" /></svg>
            <svg v-else viewBox="0 0 48 48" fill="none"><rect x="7" y="10" width="34" height="28" rx="5" /><path d="M14 20h20M14 27h11M29 29l3 3 6-7" /></svg>
          </div>
          <p class="landing-step-tag">{{ step.tag }}</p>
          <h3>{{ step.title }}</h3>
          <p>{{ step.description }}</p>
        </article>
      </div>
    </section>

    <section id="features" class="landing-feature-wrap" aria-labelledby="landing-features-heading">
      <div class="landing-container landing-section">
        <div class="landing-section-head landing-feature-heading">
          <div><p class="landing-kicker">ALL THE TOOLS, ONE PLACE</p><h2 id="landing-features-heading">A better way to <span>choose what's next.</span></h2></div>
          <p>Every part of your study-abroad decision matters. Here's how UniShortlist helps you look at the full picture.</p>
        </div>
        <div class="landing-feature-grid">
          <article v-for="feature in features" :key="feature.title" class="landing-feature-card">
            <span class="landing-feature-icon" :class="`landing-tone-${feature.tone}`" aria-hidden="true">{{ feature.icon }}</span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.description }}</p>
            <RouterLink :to="feature.to">{{ feature.link }} <span aria-hidden="true">↗</span></RouterLink>
          </article>
        </div>
      </div>
    </section>

    <section id="destinations" class="landing-section landing-container" aria-labelledby="landing-destinations-heading">
      <div class="landing-section-head landing-destination-heading">
        <div><p class="landing-kicker">THINKING BEYOND BORDERS?</p><h2 id="landing-destinations-heading">Explore where your <span>future could take you.</span></h2></div>
        <RouterLink class="landing-text-link" to="/destinations">See all destinations <span aria-hidden="true">→</span></RouterLink>
      </div>
      <div class="landing-destinations-grid">
        <RouterLink v-for="country in destinations" :key="country.code" class="landing-destination-card" :class="`landing-country-${country.tint}`" :to="`/destinations/${country.code}`">
          <span class="landing-country-flag" aria-hidden="true">{{ country.flag }}</span>
          <span class="landing-country-info"><strong>{{ country.country }}</strong><small>{{ country.caption }}</small></span>
          <span class="landing-country-arrow" aria-hidden="true">↗</span>
        </RouterLink>
      </div>
      <p class="landing-destination-note">Destination information depends on currently reviewed catalogue data. Requirements and policies may change.</p>
    </section>

    <section class="landing-container landing-trust-section" aria-labelledby="landing-trust-heading">
      <div class="landing-trust-art" aria-hidden="true">
        <div class="landing-trust-symbol">✳</div>
        <div class="landing-trust-document"><span /><span /><span /><div>✓ <small>Source attached</small></div></div>
      </div>
      <div class="landing-trust-copy">
        <p class="landing-kicker">CONFIDENCE COMES FROM CONTEXT</p>
        <h2 id="landing-trust-heading">No magic promises.<br /><span>Just better information.</span></h2>
        <p>We believe students deserve to know where a recommendation comes from, what it means and what's still uncertain.</p>
        <ul>
          <li><span aria-hidden="true">✓</span> Clear explanations of program fit and eligibility</li>
          <li><span aria-hidden="true">✓</span> Visible sources, estimates and missing information</li>
          <li><span aria-hidden="true">✓</span> Transparent cost and funding considerations</li>
        </ul>
        <RouterLink to="/discover" class="landing-text-link">See how program discovery works <span aria-hidden="true">→</span></RouterLink>
      </div>
    </section>

    <section class="landing-container landing-final-wrap" aria-labelledby="landing-final-heading">
      <div class="landing-final-cta">
        <div class="landing-final-glow" aria-hidden="true" />
        <p class="landing-kicker">IT STARTS WITH ONE STEP</p>
        <h2 id="landing-final-heading">Your future is worth<br /><span>exploring thoughtfully.</span></h2>
        <p>Build a profile, discover your options and make your next move with confidence.</p>
        <RouterLink :to="startPath" class="landing-button landing-button-light">{{ startLabel }} <span aria-hidden="true">↗</span></RouterLink>
      </div>
      <p class="landing-disclaimer">
        UniShortlist is a decision-support tool, not an admissions or financial adviser. It does not guarantee admissions, scholarships, visas, employment or return on investment. Some catalogue records may be illustrative or incomplete. <RouterLink to="/terms">Read the terms and limitations</RouterLink>.
      </p>
    </section>
  </div>
</template>

<style scoped>
.landing-page { --lp-green: #0b795a; --lp-dark: #17312c; --lp-muted: #667773; color: var(--lp-dark); background: #fff; overflow: clip; }
.landing-container { width: 100%; max-width: none; margin: 0; padding-inline: clamp(20px, 3.2vw, 70px); box-sizing: border-box; }
#how-it-works, #features, #destinations { scroll-margin-top: 95px; }
.landing-hero { background: radial-gradient(ellipse at 83% 30%, #d7eee4 0, transparent 43%), linear-gradient(125deg, #f8fcf9 0%, #edf8f2 100%); position: relative; }
.landing-hero-layout { min-height: 632px; display: grid; grid-template-columns: 1.05fr .95fr; align-items: center; gap: 38px; padding-block: 70px 92px; }
.landing-hero-copy { position: relative; z-index: 2; }
.landing-eyebrow, .landing-kicker { font-weight: 800; color: var(--lp-green); font-size: .72rem; letter-spacing: .15em; line-height: 1.7; margin: 0 0 20px; }
.landing-eyebrow { display: flex; align-items: center; gap: 9px; }
.landing-eyebrow-dot { display: inline-block; width: 8px; height: 8px; border-radius: 100%; background: #18a479; box-shadow: 0 0 0 5px #daf2e9; margin-right: 6px; }
.landing-hero h1 { font-size: clamp(2.8rem, 4.3vw, 4.85rem); font-weight: 800; letter-spacing: -.067em; line-height: 1.08; margin: 0 0 24px; max-width: 660px; }
.landing-hero h1 span, .landing-section-head h2 span, .landing-trust-copy h2 span { color: var(--lp-green); }
.landing-lead { font-size: 1.05rem; line-height: 1.83; max-width: 505px; color: #50655f; margin: 0; }
.landing-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 32px; }
.landing-button { min-height: 52px; display: inline-flex; justify-content: center; align-items: center; gap: 24px; padding: 12px 23px; font-size: .93rem; font-weight: 750; border-radius: 11px; transition: transform .18s ease, background .18s ease, box-shadow .18s ease; }
.landing-button:hover { text-decoration: none; transform: translateY(-2px); }
.landing-button span { font-size: 1.2rem; line-height: 1; font-weight: 500; }
.landing-button-primary { color: #fff; background: var(--lp-green); box-shadow: 0 9px 23px #0b795a27; }
.landing-button-primary:hover { background: #075a44; color: #fff; box-shadow: 0 12px 27px #0b795a35; }
.landing-button-secondary { color: var(--lp-dark); background: #fff; border: 1px solid #d1e2d8; }
.landing-button-secondary:hover { background: #f8fff9; color: var(--lp-dark); }
.landing-assurance { display: flex; flex-wrap: wrap; column-gap: 20px; row-gap: 8px; margin-top: 29px; color: #49675d; font-size: .79rem; font-weight: 600; }
.landing-assurance > span { display: inline-flex; gap: 6px; align-items: center; }
.landing-assurance > span > span { color: var(--lp-green); font-weight: 900; }
/* The campus is a CSS 3D architectural diorama, purpose-built for the university discovery theme. */
.campus-visual { position:relative; width:100%; min-width:0; height:570px; isolation:isolate; display:grid; place-items:center; perspective:1050px; }
.campus-aura { position:absolute; border:1px solid rgba(27,145,104,.19); border-radius:50%; pointer-events:none; }
.campus-aura-one { width:min(85%,530px); aspect-ratio:1; background:radial-gradient(circle,#d5f1e444,transparent 68%); }
.campus-aura-two { width:min(105%,655px); aspect-ratio:1; opacity:.65; }
.campus-line { position:absolute; border:1px dashed rgba(18,149,108,.24); width:55%; height:165px; border-radius:50%; pointer-events:none; }
.campus-line-left { transform:rotate(-30deg); }
.campus-line-right { transform:rotate(36deg); }
.campus-model { position:absolute; width:410px; height:385px; left:50%; top:48%; transform:translate(-50%,-50%); transform-style:preserve-3d; }
.campus-floor-shadow { position:absolute; left:50%; top:310px; width:335px; height:88px; transform:translateX(-50%); border-radius:50%; background:rgba(28,95,68,.22); filter:blur(25px); }
.campus-island { position:absolute; z-index:1; left:50%; top:232px; width:345px; height:192px; transform:translateX(-50%) rotateX(63deg) rotateZ(-12deg); border-radius:34%; background:linear-gradient(145deg,#ddf7e9 10%,#80caaa 75%,#42a77c); border:6px solid #b5e8d0; box-shadow:0 20px 0 #6bac8f,0 28px 0 #468f73,0 44px 34px rgba(37,100,77,.22); }
.campus-island-rim { position:absolute; z-index:1; left:50%; top:289px; width:255px; height:83px; transform:translateX(-50%) rotateX(62deg); border:2px dashed rgba(255,255,255,.68); border-radius:50%; }
.campus-float-architecture { position:absolute; left:50%; top:17px; z-index:2; width:320px; height:300px; transform:translateX(-50%); transform-style:preserve-3d; animation:campusBob 6s ease-in-out infinite; }
.campus-architecture { position:absolute; left:46px; top:92px; width:225px; height:204px; transform:rotateY(-24deg) rotateX(-6deg); transform-style:preserve-3d; filter:drop-shadow(20px 20px 15px rgba(35,106,73,.15)); }
.campus-facade { position:absolute; width:224px; height:160px; left:0; top:20px; z-index:3; transform:translateZ(43px); background:linear-gradient(145deg,#fffefa 0%,#e8f4ec 58%,#c6dfd1 100%); border:2px solid #d3e9dd; border-radius:3px 3px 4px 4px; box-shadow:inset 0 0 0 5px rgba(255,255,255,.45),0 9px 0 #a4cbb6; }
.campus-pediment { position:absolute; left:-10px; right:-10px; top:-61px; height:64px; clip-path:polygon(50% 0,100% 84%,100% 100%,0 100%,0 84%); background:linear-gradient(170deg,#e6f8ed,#69b995); box-shadow:inset 0 -8px 0 rgba(8,100,68,.24); display:grid; place-items:center; }
.campus-pediment-emblem { margin-top:22px; color:#126f51; font-size:1.5rem; }
.campus-architrave { position:absolute; left:-8px; right:-8px; top:0; height:12px; background:linear-gradient(#e0f4e9,#94c7ad); box-shadow:0 6px 0 #c5e2d1; }
.campus-pillars { position:absolute; inset:20px 10px 0; display:flex; align-items:flex-end; justify-content:space-around; gap:3px; }
.campus-pillar { width:23px; height:120px; border-radius:4px 4px 2px 2px; background:linear-gradient(90deg,#8fc3a9 0%,#ffffff 33%,#edf9f1 61%,#94c6ab 100%); box-shadow:-2px 0 0 #a4d0ba,2px 0 0 #8fbca6; position:relative; }
.campus-pillar::before,.campus-pillar::after { content:''; position:absolute; left:-5px; width:33px; height:9px; background:linear-gradient(#fff,#cde3d6); border:1px solid #a6cab6; border-radius:2px; }
.campus-pillar::before { top:-8px; }.campus-pillar::after { bottom:-2px; }
.campus-door { align-self:flex-end; width:45px; height:75px; border-radius:22px 22px 2px 2px; background:linear-gradient(90deg,#164f42,#2b7961 51%,#124738); border:5px solid #a6c8b7; box-shadow:inset 0 0 0 3px #2e8667; display:flex; align-items:flex-end; padding:0 7px; }
.campus-door span { display:block; height:100%; width:1px; background:#8dcdb0; margin:0 auto; }
.campus-sidewall { position:absolute; left:224px; top:20px; width:86px; height:160px; transform-origin:left center; transform:rotateY(90deg) translateZ(0); background:linear-gradient(125deg,#b0d3bf,#5f9e80); border:2px solid #8fbba4; display:flex; justify-content:space-evenly; align-items:center; }
.campus-side-window { width:19px; height:44px; border:4px solid #d3efdc; border-radius:10px 10px 2px 2px; background:#418b70; }
.campus-topwall { position:absolute; left:0; top:20px; width:224px; height:86px; transform-origin:top center; transform:rotateX(90deg); background:linear-gradient(130deg,#e9faef,#8bcbaa); }
.campus-steps { position:absolute; z-index:4; left:50%; bottom:-13px; width:105px; height:17px; transform:translateX(-50%); background:linear-gradient(#ecfff4,#bdd8c8); border:2px solid #a7cdb9; box-shadow:0 9px 0 #9ebfac,0 13px 0 #e3f4e8; }
.campus-grad-cap { position:absolute; z-index:6; left:50%; top:3px; width:113px; height:99px; transform:translateX(-50%) rotate(-6deg); filter:drop-shadow(8px 14px 8px rgba(14,93,70,.23)); animation:campusCapFloat 4s ease-in-out infinite; }
.campus-grad-cap svg { width:100%; height:100%; }
.campus-chip { position:absolute; z-index:5; display:flex; gap:10px; align-items:center; min-width:210px; padding:13px 14px; border:1px solid #daeadf; background:rgba(255,255,255,.95); box-shadow:0 18px 33px rgba(20,83,56,.14); border-radius:15px; animation:campusChipFloat 5.6s ease-in-out infinite; backdrop-filter:blur(8px); }
.campus-chip-program { top:12%; left:1%; transform:rotate(-4deg); }
.campus-chip-eligibility { top:28%; right:0; transform:rotate(4deg); animation-delay:-2.4s; }
.campus-chip-compare { bottom:15%; right:4%; transform:rotate(-2deg); animation-delay:-3.2s; }
.campus-chip-icon { display:grid; place-items:center; flex:none; width:41px; height:41px; background:#e6f5ee; color:#0b815c; border-radius:11px; font-size:1.35rem; font-weight:800; }
.campus-chip-icon-check { background:#dff7e6; color:#058a59; }
.campus-chip-icon-blue { background:#e9f1ff; color:#3a77aa; }
.campus-chip strong,.campus-chip small { display:block; }
.campus-chip strong { font-size:.78rem; color:#19483a; line-height:1.3; }
.campus-chip small { font-size:.67rem; color:#789184; margin-top:4px; line-height:1.3; }
.campus-spark { position:absolute; color:#14a477; font-size:1.6rem; animation:campusSpark 3.4s ease-in-out infinite; pointer-events:none; }
.campus-spark-one { top:17%; right:17%; }.campus-spark-two { left:14%; bottom:21%; color:#d5a853; animation-delay:-1s; }.campus-spark-three { right:27%; bottom:12%; animation-delay:-2.4s; }
.campus-visual-footnote { position:absolute; right:3%; bottom:0; font-size:.69rem; letter-spacing:.05em; color:#73998a; }
@keyframes campusBob { 0%,100% { translate:0 0; } 50% { translate:0 -12px; } }
@keyframes campusCapFloat { 0%,100% { translate:0 0; } 50% { translate:0 -13px; } }
@keyframes campusChipFloat { 0%,100% { translate:0 0; } 50% { translate:0 -10px; } }
@keyframes campusSpark { 0%,100% { opacity:.45; scale:1; } 50% { opacity:1; scale:1.25; } }
.landing-benefit-strip { background: #fff; border-bottom: 1px solid #e8efeb; box-shadow: 0 9px 22px #143e2410; }
.landing-benefits { display: grid; grid-template-columns: repeat(3, 1fr); align-items: center; padding-block: 27px; }
.landing-benefits p { display: grid; grid-template-columns: 42px auto; column-gap: 13px; row-gap: 3px; align-items: center; padding: 0 26px; margin: 0; }
.landing-benefits p + p { border-left: 1px solid #e6efea; }
.landing-benefits p > span { grid-row: span 2; color: var(--lp-green); background: #e9f7ee; border-radius: 12px; font-size: 1.5rem; display: grid; place-items: center; height: 42px; }
.landing-benefits strong { font-size: .84rem; }
.landing-benefits small { font-size: .73rem; color: #75857e; }
.landing-section { padding-block: 107px; }
.landing-section-head { margin-bottom: 42px; }
.landing-section-head-centered { text-align: left; }
.landing-section-head .landing-kicker { margin-bottom: 11px; }
.landing-section-head h2, .landing-trust-copy h2 { font-size: clamp(1.9rem, 3vw, 2.85rem); letter-spacing: -.05em; line-height: 1.2; margin: 0; }
.landing-section-head > p:not(.landing-kicker), .landing-section-head > div + p { color: var(--lp-muted); font-size: .95rem; line-height: 1.75; margin: 16px 0 0; max-width: 570px; }
.landing-step-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.landing-step-card { border: 1px solid #e7eee9; border-radius: 18px; padding: 27px; background: #fff; box-shadow: 0 10px 36px #14351a08; transition: transform .2s ease, box-shadow .2s ease; }
.landing-step-card:hover { transform: translateY(-4px); box-shadow: 0 15px 35px #14351a12; }
.landing-step-card-top { display: flex; justify-content: space-between; align-items: center; font-weight: 900; color: #8eb5a5; font-size: .83rem; }
.landing-step-arrow { color: #a8bbaf; font-size: 1.4rem; }
.landing-step-icon { display: grid; place-items: center; width: 65px; height: 65px; margin: 17px 0 23px; color: var(--lp-green); border-radius: 17px; background: #e5f5eb; }
.landing-step-card:nth-child(2) .landing-step-icon { color: #3875ac; background: #e7f0fb; }
.landing-step-card:nth-child(3) .landing-step-icon { color: #956a25; background: #fbf2df; }
.landing-step-icon svg { width: 42px; height: 42px; stroke: currentColor; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.landing-step-tag { color: var(--lp-green); text-transform: uppercase; font-size: .68rem; letter-spacing: .12em; font-weight: 800; margin-bottom: 7px; }
.landing-step-card h3 { font-size: 1.22rem; letter-spacing: -.02em; margin-bottom: 10px; }
.landing-step-card > p:last-child { margin: 0; color: #697a71; font-size: .86rem; line-height: 1.75; }
.landing-feature-wrap { background: #f6faf8; }
.landing-feature-wrap .landing-section { padding-block: 97px 107px; }
.landing-feature-heading, .landing-destination-heading { display: flex; justify-content: space-between; align-items: end; gap: 30px; }
.landing-feature-heading > div { max-width: 560px; }
.landing-feature-heading > p { margin: 0 0 3px !important; max-width: 360px !important; }
.landing-feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 17px; }
.landing-feature-card { background: #fff; border: 1px solid #e5eee8; border-radius: 16px; padding: 26px 26px 23px; display: flex; flex-direction: column; min-height: 259px; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }
.landing-feature-card:hover { border-color: #b3d6c5; box-shadow: 0 18px 28px #1b452c0d; transform: translateY(-3px); }
.landing-feature-icon { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 12px; color: #138762; font-size: 1.9rem; line-height: 1; margin-bottom: 20px; }
.landing-tone-mint { background: #e5f8ed; color: #10815b; }
.landing-tone-blue { background: #e8f1ff; color: #4173b5; }
.landing-tone-amber { background: #fff5dc; color: #aa8124; }
.landing-tone-violet { background: #f0eaff; color: #8360b8; }
.landing-tone-peach { background: #fff0e9; color: #bf795a; }
.landing-tone-sky { background: #e6f7fa; color: #3e8d9f; }
.landing-feature-card h3 { font-size: 1.12rem; letter-spacing: -.015em; margin: 0 0 9px; }
.landing-feature-card > p { color: #6b7a72; font-size: .85rem; line-height: 1.7; margin-bottom: 22px; }
.landing-feature-card > a { font-weight: 800; font-size: .78rem; color: var(--lp-green); margin-top: auto; display: inline-flex; gap: 9px; align-items: center; }
.landing-feature-card > a:hover { text-decoration: underline; }
.landing-destination-heading > div { max-width: 600px; }
.landing-text-link { color: var(--lp-green); font-size: .84rem; font-weight: 800; white-space: nowrap; display: inline-flex; align-items: center; gap: 12px; }
.landing-destinations-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
.landing-destination-card { border: 1px solid #e8efea; border-radius: 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 14px; padding: 23px 19px; min-height: 139px; background: #faf8f5; transition: transform .18s ease, box-shadow .18s ease; color: var(--lp-dark); }
.landing-destination-card:hover { transform: translateY(-4px); box-shadow: 0 12px 26px #25463517; text-decoration: none; }
.landing-country-rose { background: #fff7f4; }
.landing-country-sky { background: #f3f9fd; }
.landing-country-amber { background: #fffbef; }
.landing-country-mint { background: #f2fbf6; }
.landing-country-flag { border-radius: 10px; background: #ffffffce; width: 50px; height: 50px; display: grid; place-items: center; font-size: 2rem; box-shadow: 0 3px 12px #2845240e; }
.landing-country-info { flex: 1; }
.landing-country-info strong, .landing-country-info small { display: block; }
.landing-country-info strong { font-size: .93rem; white-space: nowrap; }
.landing-country-info small { color: #7b8981; font-size: .72rem; margin-top: 4px; }
.landing-country-arrow { margin-left: auto; color: var(--lp-green); font-size: 1.2rem; }
.landing-destination-note { color: #89978c; font-size: .76rem; text-align: center; margin: 20px 0 0; }
.landing-trust-section { background: linear-gradient(115deg, #eaf6ef, #f8fbf6); border-radius: 22px; display: grid; grid-template-columns: 1fr 1.15fr; align-items: center; gap: 66px; padding: 62px 70px; margin-bottom: 105px; }
.landing-trust-art { min-height: 305px; display: grid; place-items: center; position: relative; }
.landing-trust-symbol { position: absolute; font-size: 14rem; line-height: 1; color: #c8e9d5; top: 6px; left: 18px; }
.landing-trust-document { position: relative; width: 247px; min-height: 230px; transform: rotate(-7deg); background: #fff; border-radius: 15px; padding: 36px 24px; box-shadow: 0 18px 40px #38634222; }
.landing-trust-document > span { display: block; width: 80%; height: 10px; margin-bottom: 15px; border-radius: 4px; background: #e5eee7; }
.landing-trust-document > span:nth-child(2) { width: 65%; }
.landing-trust-document > span:nth-child(3) { width: 90%; }
.landing-trust-document div { font-size: 1.1rem; font-weight: 900; color: #087855; background: #dcf5e6; padding: 13px; margin-top: 23px; border-radius: 9px; }
.landing-trust-document small { font-size: .77rem; }
.landing-trust-copy .landing-kicker { margin-bottom: 14px; }
.landing-trust-copy > p:not(.landing-kicker) { color: #687971; line-height: 1.75; font-size: .93rem; margin-top: 21px; max-width: 435px; }
.landing-trust-copy ul { padding: 0; margin: 22px 0 25px; list-style: none; display: grid; gap: 12px; }
.landing-trust-copy li { display: flex; align-items: baseline; gap: 10px; font-size: .85rem; color: #375547; }
.landing-trust-copy li span { color: var(--lp-green); font-weight: 900; }
.landing-final-wrap { margin-bottom: 35px; }
.landing-final-cta { background: linear-gradient(130deg, #145f4c, #083e33); border-radius: 23px; color: #fff; text-align: center; padding: 75px 24px 78px; position: relative; overflow: hidden; }
.landing-final-cta > *:not(.landing-final-glow) { position: relative; z-index: 1; }
.landing-final-glow { position: absolute; width: 580px; height: 580px; border: 1px solid #6cbca44d; border-radius: 50%; right: -160px; top: -250px; box-shadow: 0 0 0 80px #ffffff06, 0 0 0 160px #ffffff05; }
.landing-final-cta .landing-kicker { color: #97dfbb; margin-bottom: 16px; }
.landing-final-cta h2 { font-size: clamp(2rem, 3.45vw, 3.25rem); line-height: 1.2; letter-spacing: -.055em; margin: 0 0 18px; }
.landing-final-cta h2 span { color: #a7e8c7; }
.landing-final-cta > p:not(.landing-kicker) { color: #d0e4d9; font-size: .93rem; margin: 0 auto 26px; max-width: 470px; }
.landing-button-light { background: #fff; color: #125c47; min-height: 49px; }
.landing-button-light:hover { background: #eaf8ef; color: #125c47; }
.landing-disclaimer { color: #7c8982; font-size: .73rem; line-height: 1.65; text-align: center; max-width: 870px; margin: 23px auto 0; }
.landing-disclaimer a { color: #1b7055; text-decoration: underline; }
@media (max-width: 1050px) {
  .landing-hero-layout { gap: 8px; }
  .landing-destinations-grid { grid-template-columns: repeat(2, 1fr); }
  .landing-benefits p { padding-inline: 14px; }
}
@media (max-width: 1050px) and (min-width: 781px) {
  .campus-visual { height:515px; }
  .campus-chip { min-width:0; padding:11px 12px; }
}
@media (max-width: 780px) {
  .landing-container { width: 100%; padding-inline: 22px; }
  .landing-hero-layout { grid-template-columns: 1fr; min-height: 0; padding-block: 64px 82px; gap: 35px; }
  .landing-hero-copy { text-align: left; }
  .campus-visual { height:495px; max-width:720px; margin-inline:auto; }
  .landing-eyebrow, .landing-actions, .landing-assurance { justify-content: flex-start; }
  .landing-hero h1, .landing-lead { margin-inline: 0; }
  .landing-hero h1 { font-size: clamp(2.9rem, 7.2vw, 4rem); }
  .landing-benefits { grid-template-columns: 1fr; padding-block: 15px; }
  .landing-benefits p { padding: 13px 12px; }
  .landing-benefits p + p { border-left: 0; border-top: 1px solid #e6efea; }
  .landing-section { padding-block: 77px; }
  .landing-step-grid { grid-template-columns: 1fr; gap: 14px; }
  .landing-step-card { padding: 23px; }
  .landing-step-icon { margin-block: 10px 16px; }
  .landing-step-arrow { display: none; }
  .landing-feature-heading, .landing-destination-heading { display: block; }
  .landing-feature-heading > p { max-width: 500px !important; margin: 18px 0 0 !important; }
  .landing-feature-grid { grid-template-columns: repeat(2, 1fr); }
  .landing-destination-heading .landing-text-link { margin-top: 22px; }
  .landing-trust-section { grid-template-columns: 1fr; gap: 10px; padding: 45px 34px; margin-bottom: 75px; }
  .landing-trust-art { min-height: 215px; }
  .landing-trust-symbol { font-size: 11rem; left: 20%; top: -20px; }
  .landing-trust-document { transform: rotate(-5deg) scale(.75); }
}
@media (max-width: 480px) {
  .landing-container { width: 100%; padding-inline: 16px; }
  .landing-hero-layout { padding-block: 49px 66px; }
  .campus-visual { height:375px; }
  .campus-model { transform:translate(-50%,-49%) scale(.77); }
  .campus-aura-one { width:95%; }
  .campus-chip { min-width:0; padding:8px; gap:6px; border-radius:10px; }
  .campus-chip-program { left:0; top:2%; }
  .campus-chip-eligibility { right:0; top:21%; }
  .campus-chip-compare { right:1%; bottom:11%; }
  .campus-chip-icon { width:28px; height:28px; font-size:1rem; border-radius:8px; }
  .campus-chip strong { font-size:.6rem; }
  .campus-chip small { font-size:.51rem; }
  .campus-visual-footnote { right:1%; font-size:.57rem; }
  .landing-hero h1 { font-size: clamp(2.5rem, 11vw, 3.3rem); }
  .landing-lead { font-size: .92rem; }
  .landing-actions { flex-direction: column; align-items: stretch; }
  .landing-button { width: 100%; justify-content: space-between; }
  .landing-step-grid, .landing-feature-grid, .landing-destinations-grid { grid-template-columns: 1fr; }
  .landing-feature-card { min-height: 0; }
  .landing-destination-card { min-height: 105px; }
  .landing-trust-section { padding: 32px 21px 41px; }
  .landing-trust-symbol { left: 6%; }
  .landing-final-cta { padding: 54px 22px; }
}
@media (prefers-reduced-motion: reduce) {
  .landing-page *, .landing-page *::before, .landing-page *::after { transition: none !important; animation:none !important; }
}
</style>

<style scoped>
/* UNISHORTLIST_LANDING_FLOAT_V2
   A scoped and non-destructive visual enhancement; preserve all original content and routes.
*/
.landing-page {
  --lp-green: #087e60;
  --lp-dark: #153a30;
  --landing-premium-shadow: 0 22px 60px rgba(11, 82, 57, .10);
  isolation: isolate;
}

/* Immersive yet readable gradient, with moving light in the hero. */
.landing-hero {
  isolation: isolate;
  overflow: hidden;
  background:
    radial-gradient(ellipse 44% 52% at 87% 35%, rgba(82, 201, 146, .26), transparent 72%),
    radial-gradient(ellipse 36% 48% at 12% 91%, rgba(169, 229, 192, .28), transparent 75%),
    linear-gradient(112deg, #f8fcfa 4%, #f0fbf4 46%, #e6f8ee 100%);
}
.landing-hero::before {
  content: '';
  position: absolute;
  width: min(68vw, 920px);
  aspect-ratio: 1;
  right: -21%;
  top: -42%;
  border-radius: 50%;
  border: 1px solid rgba(10, 135, 94, .12);
  box-shadow: 0 0 0 80px rgba(41, 161, 109, .035), 0 0 0 160px rgba(41, 161, 109, .025);
  pointer-events: none;
  animation: landingPremiumHalo 22s ease-in-out infinite alternate;
}
.landing-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
  width: 330px;
  height: 330px;
  left: -200px;
  bottom: -190px;
  border-radius: 50%;
  border: 1px solid rgba(6, 124, 87, .10);
  box-shadow: 0 0 0 55px rgba(12, 147, 105, .035);
}
.landing-hero-layout {
  position: relative;
  z-index: 1;
  min-height: 660px;
  gap: clamp(16px, 3vw, 46px);
}
.landing-hero-copy { animation: landingPremiumIntro .75s both; }
.landing-eyebrow {
  width: fit-content;
  border: 1px solid rgba(6, 137, 97, .15);
  background: rgba(255, 255, 255, .75);
  border-radius: 999px;
  padding: 9px 15px;
  box-shadow: 0 9px 28px rgba(18, 98, 67, .07);
  backdrop-filter: blur(9px);
}
.landing-eyebrow-dot { animation: landingPremiumDot 2.7s ease-out infinite; }
.landing-hero h1 {
  font-size: clamp(2.7rem, 4.4vw, 5.1rem);
  letter-spacing: -.068em;
  font-weight: 860;
  text-wrap: balance;
  max-width: 730px;
  margin-bottom: 23px;
}
.landing-hero h1 span {
  background: linear-gradient(105deg, #075e46 5%, #0aa67a 55%, #187e62 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.landing-lead { color: #537368; line-height: 1.85; max-width: 550px; }
.landing-actions { margin-top: 31px; }
.landing-button {
  border-radius: 14px;
  letter-spacing: -.01em;
  transition: transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s ease, background .25s ease, border-color .25s ease;
}
.landing-button-primary {
  background: linear-gradient(135deg, #07936b, #09694f);
  border: 1px solid rgba(5, 104, 72, .24);
  box-shadow: 0 16px 33px rgba(7, 114, 78, .22);
}
.landing-button-primary:hover, .landing-button-primary:focus-visible {
  background: linear-gradient(135deg, #07865f, #075640);
  box-shadow: 0 21px 37px rgba(6, 111, 76, .28);
  transform: translateY(-4px);
}
.landing-button-secondary {
  background: rgba(255, 255, 255, .88);
  border: 1px solid #cde5d7;
  box-shadow: 0 8px 22px rgba(28, 84, 56, .05);
}
.landing-button-secondary:hover, .landing-button-secondary:focus-visible {
  transform: translateY(-4px);
  background: #fff;
  box-shadow: 0 16px 30px rgba(28, 84, 56, .11);
}
.landing-assurance > span > span {
  display: inline-grid;
  place-items: center;
  width: 21px;
  height: 21px;
  background: #d8f5e4;
  border-radius: 50%;
}

/* Make the existing university CSS 3D diorama feel responsive to the pointer. */
.campus-visual {
  animation: landingPremiumSceneIn .9s .12s both;
  transform-style: preserve-3d;
}
.campus-visual::before {
  content: '';
  position: absolute;
  inset: 9% 6%;
  pointer-events: none;
  border-radius: 50%;
  background: radial-gradient(circle at var(--landing-light-x, 50%) var(--landing-light-y, 50%), rgba(48, 200, 132, .18), rgba(31, 175, 112, .055) 45%, transparent 70%);
  filter: blur(13px);
  transition: opacity .3s ease;
}
.campus-aura-one {
  border: 1px solid rgba(21, 169, 119, .26);
  box-shadow: inset 0 0 42px rgba(11, 163, 108, .065);
  animation: landingPremiumAura 7.5s ease-in-out infinite alternate;
}
.campus-aura-two {
  border: 1px dashed rgba(18, 143, 101, .22);
  animation: landingPremiumAuraOuter 23s linear infinite;
}
.campus-line-left { animation: landingPremiumLineL 14s ease-in-out infinite alternate; }
.campus-line-right { animation: landingPremiumLineR 17s ease-in-out infinite alternate; }
.campus-model {
  will-change: transform;
  transition: transform .2s cubic-bezier(.22,.8,.32,1);
}
.campus-floor-shadow { filter: blur(31px); opacity: .85; }
.campus-float-architecture { animation-duration: 5.2s; }
.campus-grad-cap { animation-duration: 3.8s; }
.campus-chip {
  background: rgba(255, 255, 255, .92);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(216, 237, 225, .95);
  box-shadow: 0 24px 52px rgba(20, 87, 57, .16), inset 0 1px 0 rgba(255, 255, 255, .95);
  border-radius: 17px;
  transition: box-shadow .25s ease, border-color .25s ease, filter .25s ease;
}
.campus-chip:hover {
  border-color: rgba(47, 170, 113, .5);
  box-shadow: 0 29px 57px rgba(14, 91, 61, .2);
  filter: saturate(1.08);
}
.campus-chip-program { animation-duration: 5.2s; }
.campus-chip-eligibility { animation-duration: 6.2s; }
.campus-chip-compare { animation-duration: 5.8s; }
.campus-spark { text-shadow: 0 4px 16px rgba(13, 143, 101, .28); }

/* The rest of the page: cleaner surfaces, stronger visual hierarchy, subtle lift. */
.landing-benefit-strip {
  position: relative;
  z-index: 2;
  box-shadow: 0 14px 40px rgba(24, 74, 50, .055);
}
.landing-benefits p > span {
  box-shadow: inset 0 0 0 1px rgba(33, 147, 102, .08);
  transition: transform .25s ease, background .25s ease;
}
.landing-benefits p:hover > span { transform: translateY(-3px) rotate(-5deg); background: #dff8e9; }
.landing-section-head h2, .landing-trust-copy h2 { letter-spacing: -.052em; text-wrap: balance; }
.landing-step-grid, .landing-feature-grid, .landing-destinations-grid { align-items: stretch; }
.landing-step-card,
.landing-feature-card,
.landing-destination-card {
  position: relative;
  overflow: hidden;
  border-radius: 21px;
  border-color: #dcece2;
  box-shadow: 0 12px 28px rgba(20, 82, 49, .055);
  transition: transform .32s cubic-bezier(.2,.8,.2,1), box-shadow .32s ease, border-color .32s ease;
}
.landing-step-card::before,
.landing-feature-card::before,
.landing-destination-card::before {
  content: '';
  position: absolute;
  height: 4px;
  top: 0;
  left: 20px;
  right: 20px;
  background: linear-gradient(90deg, transparent, rgba(25, 189, 123, .7), transparent);
  opacity: 0;
  transform: scaleX(.45);
  transition: opacity .3s ease, transform .3s ease;
  pointer-events: none;
}
.landing-step-card:hover,
.landing-feature-card:hover,
.landing-destination-card:hover {
  transform: translateY(-8px);
  border-color: #a7d8be;
  box-shadow: 0 25px 48px rgba(10, 83, 52, .13);
}
.landing-step-card:hover::before,
.landing-feature-card:hover::before,
.landing-destination-card:hover::before { opacity: 1; transform: scaleX(1); }
.landing-step-icon {
  border-radius: 21px;
  box-shadow: inset 0 0 0 1px rgba(19, 126, 90, .07);
  transition: transform .35s ease;
}
.landing-step-card:hover .landing-step-icon { transform: rotate(-7deg) scale(1.07); }
.landing-feature-wrap {
  background:
    radial-gradient(circle at 3% 15%, rgba(46, 170, 112, .07), transparent 25%),
    linear-gradient(180deg, #f7fbf8, #f1f8f3);
}
.landing-feature-card {
  background: linear-gradient(156deg, #fff, #fcfffd);
  min-height: 265px;
}
.landing-feature-icon {
  border-radius: 16px;
  transition: transform .3s ease;
}
.landing-feature-card:hover .landing-feature-icon { transform: translateY(-3px) rotate(-8deg); }
.landing-feature-card > a span, .landing-text-link span {
  transition: translate .22s ease;
}
.landing-feature-card:hover > a span, .landing-text-link:hover span { translate: 3px -2px; }
.landing-destination-card {
  padding: 25px 21px;
  border-color: #e1ebe4;
}
.landing-country-flag {
  transition: transform .35s cubic-bezier(.25,.8,.25,1);
  box-shadow: 0 10px 24px rgba(20, 71, 50, .09);
}
.landing-destination-card:hover .landing-country-flag { transform: rotate(-9deg) scale(1.12); }
.landing-trust-section {
  position: relative;
  overflow: hidden;
  border: 1px solid #d1e9db;
  box-shadow: var(--landing-premium-shadow);
  background: linear-gradient(128deg, #e3f7eb 0%, #f6fcf8 55%, #eaf9ef 100%);
}
.landing-trust-symbol { animation: landingPremiumTrustSpin 26s linear infinite; }
.landing-trust-document { animation: landingPremiumDocument 7s ease-in-out infinite; }
.landing-final-cta {
  border: 1px solid rgba(129, 218, 173, .18);
  box-shadow: 0 23px 60px rgba(8, 78, 57, .18);
  background: radial-gradient(circle at 78% 18%, rgba(56, 159, 113, .32), transparent 40%), linear-gradient(125deg, #13634f, #064636 72%, #04392e);
}
.landing-final-glow { animation: landingPremiumHalo 19s ease-in-out infinite alternate; }
.landing-final-cta .landing-button-light:hover { transform: translateY(-4px); box-shadow: 0 16px 30px rgba(0, 0, 0, .15); }

/* Entrance motion is opt-in after mounting and leaves all content visible in no-JS/reduced-motion modes. */
.landing-upgrade-reveal { opacity: 0; transform: translateY(27px) scale(.988); transition: opacity .7s ease, transform .7s cubic-bezier(.19,1,.22,1); }
.landing-upgrade-reveal.landing-upgrade-visible { opacity: 1; transform: none; }
.landing-step-card:nth-child(2), .landing-feature-card:nth-child(2), .landing-destination-card:nth-child(2) { transition-delay: 65ms; }
.landing-step-card:nth-child(3), .landing-feature-card:nth-child(3), .landing-destination-card:nth-child(3) { transition-delay: 120ms; }

@keyframes landingPremiumIntro { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
@keyframes landingPremiumSceneIn { from { opacity: 0; transform: translateY(20px) scale(.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes landingPremiumHalo { from { translate: 0 0; scale: 1; } to { translate: -24px 28px; scale: 1.1; } }
@keyframes landingPremiumDot { 0%, 100% { box-shadow: 0 0 0 5px #daf2e9; } 55% { box-shadow: 0 0 0 10px rgba(16, 173, 115, .06); } }
@keyframes landingPremiumAura { 0%,100% { transform: scale(.965); opacity: .68; } 50% { transform: scale(1.045); opacity: 1; } }
@keyframes landingPremiumAuraOuter { from { transform: rotate(0); } to { transform: rotate(360deg); } }
@keyframes landingPremiumLineL { from { transform: rotate(-30deg) scale(.92); } to { transform: rotate(-16deg) scale(1.06); } }
@keyframes landingPremiumLineR { from { transform: rotate(36deg) scale(.97); } to { transform: rotate(25deg) scale(1.06); } }
@keyframes landingPremiumTrustSpin { from { rotate: -8deg; } to { rotate: 352deg; } }
@keyframes landingPremiumDocument { 0%, 100% { translate: 0 0; } 50% { translate: 0 -10px; } }

@media (min-width: 781px) and (hover: hover) and (pointer: fine) {
  .campus-model {
    transform: translate(-50%, -50%) rotateX(var(--landing-tilt-x, 0deg)) rotateY(var(--landing-tilt-y, 0deg));
  }
}
@media (max-width: 1050px) {
  .landing-hero h1 { font-size: clamp(2.6rem, 4.3vw, 4.4rem); }
}
@media (max-width: 780px) {
  .landing-hero-layout { min-height: 0; }
  .landing-hero::before { width: 620px; right: -360px; top: -240px; }
  .landing-hero h1 { font-size: clamp(2.65rem, 7.2vw, 4rem); }
  .landing-eyebrow { margin-inline: 0; }
  .landing-step-card:hover, .landing-feature-card:hover, .landing-destination-card:hover { transform: translateY(-3px); }
  .landing-trust-section { box-shadow: 0 12px 30px rgba(14, 89, 55, .07); }
}
@media (max-width: 480px) {
  .landing-hero h1 { font-size: clamp(2.4rem, 10.2vw, 3.25rem); }
  .landing-eyebrow { max-width: 100%; font-size: .65rem; }
  .landing-hero::before { opacity: .65; }
  .campus-visual::before { opacity: .55; }
  .landing-trust-section { border-radius: 18px; }
}
@media (prefers-reduced-motion: reduce) {
  .landing-page *, .landing-page *::before, .landing-page *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
  .landing-upgrade-reveal, .landing-upgrade-reveal.landing-upgrade-visible { opacity: 1 !important; transform: none !important; }
  .campus-model { will-change: auto; }
}

</style>
