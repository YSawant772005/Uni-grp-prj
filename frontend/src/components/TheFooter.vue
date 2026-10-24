<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const year = new Date().getFullYear()
</script>

<template>
  <footer class="site-footer" aria-label="UniShortlist footer">
    <div class="footer-content">
      <div class="footer-grid">
        <div class="footer-about">
          <RouterLink class="footer-brand" to="/" aria-label="UniShortlist home">
            <span class="footer-mark" aria-hidden="true">U</span>
            <span>UniShortlist</span>
          </RouterLink>
          <p class="footer-description">
            Find Master's programs that fit your goals, compare the details, and make informed
            study-abroad decisions with evidence you can check.
          </p>
          <div class="footer-trust"><span class="footer-trust-icon" aria-hidden="true">✓</span> Built for clarity, not promises</div>
        </div>

        <nav class="footer-section" aria-label="Explore UniShortlist">
          <h2>Explore</h2>
          <RouterLink to="/discover">Find universities</RouterLink>
          <RouterLink to="/compare">Compare programs</RouterLink>
          <RouterLink to="/destinations">Study destinations</RouterLink>
        </nav>

        <nav class="footer-section" aria-label="Planning tools">
          <h2>Plan your journey</h2>
          <RouterLink to="/finance">Study costs</RouterLink>
          <RouterLink to="/scholarships">Scholarships</RouterLink>
          <RouterLink to="/loans">Education loans</RouterLink>
          <RouterLink to="/roi">Career and ROI</RouterLink>
        </nav>

        <nav class="footer-section" aria-label="Account and resources">
          <h2>{{ auth.isAuthenticated ? 'Your account' : 'Get started' }}</h2>
          <template v-if="auth.isAuthenticated">
            <RouterLink to="/shortlist">My shortlists</RouterLink>
            <RouterLink to="/saved">Saved programs</RouterLink>
            <RouterLink to="/profile">My profile</RouterLink>
          </template>
          <template v-else>
            <RouterLink to="/signup">Create an account</RouterLink>
            <RouterLink to="/login">Log in</RouterLink>
          </template>
          <RouterLink to="/privacy">Privacy policy</RouterLink>
          <RouterLink to="/terms">Terms & limitations</RouterLink>
        </nav>
      </div>

      <div class="footer-disclaimer">
        <span class="footer-info-icon" aria-hidden="true">i</span>
        <p>
          UniShortlist provides guidance, not guarantees of admission, scholarships, visas,
          employment or financial outcomes. Information may be verified, estimated, stale or
          unavailable—check the source and status before deciding.
        </p>
      </div>

      <div class="footer-bottom">
        <span>© {{ year }} UniShortlist. All rights reserved.</span>
        <span class="footer-bottom-links">
          <RouterLink to="/privacy">Privacy</RouterLink>
          <span class="footer-separator" aria-hidden="true">·</span>
          <RouterLink to="/terms">Terms & limitations</RouterLink>
        </span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.site-footer {
  margin: 0;
  padding: 0;
  width: 100%;
  border-top: 0;
  background: #103c31;
  color: #effcf5;
  overflow: hidden;
}
.footer-content {
  width: 100%;
  padding: 54px clamp(22px, 3.2vw, 72px) 24px;
  box-sizing: border-box;
}
.footer-grid {
  display: grid;
  grid-template-columns: minmax(270px, 1.7fr) repeat(3, minmax(135px, 1fr));
  gap: clamp(24px, 3.6vw, 72px);
  align-items: start;
  padding-bottom: 39px;
}
.footer-about { min-width: 0; max-width: 430px; }
.footer-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: 1.22rem;
  line-height: 1.3;
  font-weight: 850;
  letter-spacing: -.028em;
  color: #fff;
  text-decoration: none;
}
.footer-brand:hover { color: #fff; text-decoration: none; }
.footer-mark {
  width: 39px;
  height: 39px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 1.18rem;
  font-weight: 850;
  color: #fff;
  background: #0c996e;
  box-shadow: 0 7px 18px #04251c55;
}
.footer-description {
  max-width: 390px;
  margin: 18px 0 16px;
  color: #c3ded1;
  line-height: 1.72;
  font-size: .93rem;
}
.footer-trust {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 9px 13px;
  border: 1px solid #54847488;
  border-radius: 999px;
  color: #dcfbed;
  font-size: .76rem;
  font-weight: 650;
  line-height: 1.35;
  background: #ffffff0b;
}
.footer-trust-icon { color: #68dcab; font-size: 1rem; }
.footer-section {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
.footer-section h2 {
  margin: 5px 0 8px;
  color: #fff;
  line-height: 1.45;
  font-size: .91rem;
  font-weight: 800;
  letter-spacing: .005em;
}
.footer-section a {
  color: #c5ddce;
  font-size: .88rem;
  line-height: 1.4;
  text-decoration: none;
  transition: color .18s ease, transform .18s ease;
}
.footer-section a:hover { color: #fff; transform: translateX(3px); text-decoration: none; }
.footer-section a:focus-visible,
.footer-bottom a:focus-visible,
.footer-brand:focus-visible { outline: 2px solid #8ee6c1; outline-offset: 4px; }
.footer-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  margin: 0;
  padding: 19px 21px;
  border-radius: 13px;
  border: 1px solid #547c6f66;
  background: #ffffff0b;
  color: #c6e0d1;
}
.footer-disclaimer p { margin: 0; line-height: 1.6; font-size: .82rem; max-width: 1100px; }
.footer-info-icon {
  flex: 0 0 18px;
  height: 18px;
  border: 1px solid #7ccaa4;
  color: #9fe6c1;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-family: Georgia, serif;
  font-style: italic;
  line-height: 1;
  margin-top: 2px;
}
.footer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px 32px;
  flex-wrap: wrap;
  padding-top: 22px;
  margin-top: 23px;
  border-top: 1px solid #ffffff26;
  color: #b9d5c7;
  font-size: .78rem;
}
.footer-bottom-links { display: flex; flex-wrap: wrap; align-items: center; gap: 13px; }
.footer-bottom a { color: #d5eee0; text-decoration: none; }
.footer-bottom a:hover { color: #fff; text-decoration: underline; }
.footer-separator { color: #8ea99b; }
@media (max-width: 1000px) {
  .footer-grid { grid-template-columns: minmax(225px, 1.5fr) repeat(2, minmax(135px, 1fr)); gap: 32px; }
  .footer-grid .footer-section:last-child { grid-column: 2 / 4; }
}
@media (max-width: 680px) {
  .footer-content { padding-top: 40px; }
  .footer-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 32px 24px; padding-bottom: 29px; }
  .footer-about { grid-column: 1 / -1; max-width: 500px; }
  .footer-grid .footer-section:last-child { grid-column: auto; }
  .footer-section h2 { margin: 0 0 4px; }
  .footer-disclaimer { padding: 15px 14px; }
}
@media (max-width: 375px) {
  .footer-grid { grid-template-columns: 1fr; }
  .footer-about { grid-column: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .footer-section a { transition: none; }
}
</style>
