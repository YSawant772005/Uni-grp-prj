<script setup lang="ts">
defineProps<{ mode: 'login' | 'signup' }>()
</script>

<template>
  <div class="auth-page" :class="{ 'auth-page-centered-login': mode === 'login', 'auth-page-centered-signup': mode === 'signup' }">
    <div class="auth-orb auth-orb-one" aria-hidden="true" />
    <div class="auth-orb auth-orb-two" aria-hidden="true" />
    <div class="auth-frame">
      <aside class="auth-story" aria-label="About UniShortlist">
        <div class="auth-story-content">
          <div class="auth-story-tag"><span class="auth-sparkle" aria-hidden="true">✦</span> YOUR STUDY ABROAD COMPANION</div>
          <h2>Big dreams deserve<br /><em>clear directions.</em></h2>
          <p class="auth-story-lead">
            Explore Master's programs, understand your options, and bring every decision into focus.
          </p>

          <div class="auth-illustration" aria-hidden="true">
            <div class="auth-illustration-glow" />
            <div class="auth-map-card">
              <div class="auth-map-top"><span class="auth-map-logo">U<span>.</span></span><span class="auth-map-dots">•••</span></div>
              <div class="auth-map-heading">Your next chapter</div>
              <div class="auth-map-track"><span class="auth-map-dot" /><span class="auth-map-line" /><span class="auth-map-pin">✦</span></div>
              <div class="auth-map-caption">Start here <span>→</span> Find your fit</div>
            </div>
            <div class="auth-float-card auth-float-one"><span class="auth-float-icon">✓</span><span><strong>Explore your fit</strong><small>Know what matters</small></span></div>
            <div class="auth-float-card auth-float-two"><span class="auth-float-icon auth-float-icon-blue">✳</span><span><strong>Compare with clarity</strong><small>Beyond just rankings</small></span></div>
          </div>

          <div class="auth-story-bottom">
            <span class="auth-story-line" />
            <span>Thoughtful choices. Brighter possibilities.</span>
          </div>
        </div>
      </aside>

      <section class="auth-panel" :aria-label="mode === 'login' ? 'Log in to UniShortlist' : 'Create your UniShortlist account'">
        <div class="auth-panel-inner">
          <div class="auth-mobile-tag"><span aria-hidden="true">✦</span> UNI SHORTLIST</div>
          <slot />
        </div>
      </section>
    </div>
    <p class="auth-page-footnote">Your next step, on your terms. <RouterLink to="/privacy">Privacy</RouterLink> · <RouterLink to="/terms">Terms</RouterLink></p>
  </div>
</template>

<style scoped>
.auth-page {
  --auth-green: #0b795a;
  --auth-forest: #17312c;
  --auth-text: #51675e;
  background: radial-gradient(circle at 6% 7%, #d9efe2 0, transparent 31%), radial-gradient(circle at 97% 86%, #d4f2e4 0, transparent 30%), #f5faf6;
  color: var(--auth-forest);
  isolation: isolate;
  min-height: calc(100vh - 76px);
  padding: clamp(24px, 3.2vw, 52px) 24px 18px;
  position: relative;
  overflow: hidden;
}
.auth-orb { position: absolute; z-index: -1; border: 1px solid #bfe6d2; border-radius: 100%; pointer-events: none; }
.auth-orb-one { width: 330px; height: 330px; top: -205px; right: -120px; }
.auth-orb-two { width: 270px; height: 270px; bottom: -210px; left: -120px; }
.auth-frame {
  display: grid;
  grid-template-columns: minmax(0, .94fr) minmax(0, 1.06fr);
  margin: 0 auto;
  max-width: 1090px;
  min-height: 638px;
  border: 1px solid #d9e7dd;
  border-radius: 26px;
  background: white;
  overflow: hidden;
  box-shadow: 0 30px 90px #23533c15, 0 6px 26px #1a513d0a;
}
.auth-story { background: linear-gradient(146deg, #0c775a 0%, #075841 65%, #104536 100%); color: white; position: relative; overflow: hidden; }
.auth-story::before { content: ''; position: absolute; width: 460px; height: 460px; border-radius: 50%; background: #ffffff0a; top: -260px; right: -230px; border: 1px solid #ffffff1b; }
.auth-story::after { content: ''; position: absolute; width: 400px; height: 400px; border-radius: 50%; bottom: -330px; left: -140px; border: 1px solid #ffffff23; }
.auth-story-content { position: relative; z-index: 1; display: flex; flex-direction: column; height: 100%; padding: 46px 42px 30px; }
.auth-story-tag { display: flex; align-items: center; gap: 11px; letter-spacing: .15em; font-size: .66rem; font-weight: 800; color: #d5f9e2; }
.auth-sparkle { color: #c8f4a5; font-size: 1.15rem; }
.auth-story h2 { font-size: clamp(2.4rem, 3.4vw, 3.7rem); line-height: 1.13; letter-spacing: -.053em; margin: 33px 0 17px; font-weight: 800; }
.auth-story h2 em { color: #b9f4b8; font-style: normal; }
.auth-story-lead { color: #d3f2e6; line-height: 1.75; font-size: .93rem; max-width: 345px; }
.auth-illustration { position: relative; flex: 1; min-height: 235px; width: 100%; margin: 10px 0 0; display: grid; place-items: center; }
.auth-illustration-glow { position: absolute; width: 275px; height: 185px; border-radius: 50%; background: #9ae6c52e; filter: blur(35px); }
.auth-map-card { position: relative; width: min(82%, 286px); transform: rotate(-5deg); background: #fff; box-shadow: 0 17px 52px #022d2080; border-radius: 17px; padding: 19px 23px 22px; color: #17312c; }
.auth-map-top { display: flex; justify-content: space-between; align-items: center; }
.auth-map-logo { background: #e5f6ed; color: #0b795a; border-radius: 8px; display: grid; place-items: center; width: 32px; height: 32px; font-weight: 900; }
.auth-map-logo span { color: #74c99c; }
.auth-map-dots { color: #a7b9ae; letter-spacing: .1em; }
.auth-map-heading { font-weight: 800; letter-spacing: -.035em; font-size: 1.18rem; margin-top: 12px; }
.auth-map-track { display: flex; align-items: center; margin-top: 24px; margin-bottom: 19px; }
.auth-map-dot { width: 14px; height: 14px; border-radius: 100%; background: #0b795a; border: 4px solid #ceefdc; box-sizing: content-box; }
.auth-map-line { flex: 1; border-top: 2px dashed #9fcbad; }
.auth-map-pin { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 12px; background: #e3f7e9; color: #138567; font-size: 1.4rem; }
.auth-map-caption { display: flex; justify-content: space-between; color: #688379; font-size: .74rem; font-weight: 700; }
.auth-map-caption span { color: #0b795a; }
.auth-float-card { position: absolute; display: flex; align-items: center; gap: 9px; padding: 10px 12px; background: white; border-radius: 12px; box-shadow: 0 12px 35px #01382945; color: #17312c; animation: authFloat 6s ease-in-out infinite; }
.auth-float-card strong, .auth-float-card small { display: block; white-space: nowrap; }
.auth-float-card strong { font-size: .7rem; }
.auth-float-card small { font-size: .65rem; color: #82938a; margin-top: 1px; }
.auth-float-one { top: 10px; right: -16px; transform: rotate(5deg); }
.auth-float-two { bottom: 9px; left: -19px; animation-delay: -3s; }
.auth-float-icon { color: #0b795a; background: #e3f8ed; border-radius: 9px; width: 29px; height: 29px; display: grid; place-items: center; font-size: 1rem; font-weight: 800; }
.auth-float-icon-blue { background: #eaf4ff; color: #457fbe; }
.auth-story-bottom { display: flex; align-items: center; gap: 12px; font-size: .72rem; color: #c0ecd8; margin-top: 18px; }
.auth-story-line { width: 30px; border-top: 2px solid #a0e9b5; }
.auth-panel { display: grid; align-items: center; background: white; }
.auth-panel-inner { width: 100%; max-width: 530px; margin: auto; padding: 50px clamp(27px, 4vw, 65px); box-sizing: border-box; }
.auth-mobile-tag { display: none; }
.auth-page-footnote { color: #6b8178; text-align: center; margin: 20px 0 0; font-size: .75rem; }
.auth-page-footnote a { color: #205b45; text-decoration: underline; text-underline-offset: 3px; }
@keyframes authFloat { 0%, 100% { translate: 0 0; } 50% { translate: 0 -8px; } }
@media (max-width: 900px) {
  .auth-frame { grid-template-columns: minmax(0, .78fr) minmax(0, 1.22fr); }
  .auth-story-content { padding: 40px 26px 25px; }
  .auth-story h2 { font-size: 2.25rem; }
  .auth-float-one { right: -8px; }
  .auth-float-two { left: -9px; }
  .auth-panel-inner { padding: 40px 30px; box-sizing: border-box; }
}
@media (max-width: 720px) {
  .auth-page { padding: 16px 12px 15px; }
  .auth-frame { grid-template-columns: minmax(0, 1fr); max-width: 520px; border-radius: 20px; min-height: 0; }
  .auth-story { display: none; }
  .auth-panel-inner { padding: 34px 25px 40px; }
  .auth-mobile-tag { display: flex; align-items: center; gap: 8px; margin-bottom: 18px; font-weight: 800; color: #0b795a; letter-spacing: .13em; font-size: .67rem; }
  .auth-mobile-tag span { font-size: 1.1rem; }
}
@media (prefers-reduced-motion: reduce) { .auth-float-card { animation: none; } }

/* UNISHORTLIST CENTERED LOGIN START
   This styling applies only when AuthShell mode === 'login'.
   Signup retains its two-column layout and existing appearance. */
.auth-page.auth-page-centered-login {
  --centered-ink: #143a2f;
  --centered-green: #087f5d;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  min-height: max(660px, calc(100dvh - 75px));
  padding: clamp(28px, 5vh, 55px) 18px 22px;
  background:
    radial-gradient(circle at 15% 22%, #d6f5e4 0, transparent 29%),
    radial-gradient(circle at 88% 78%, #daf4e9 0, transparent 35%),
    linear-gradient(150deg, #f4fbf7 0%, #eaf8f0 100%);
}
.auth-page-centered-login .auth-frame {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  width: min(100%, 515px);
  max-width: 515px;
  min-height: 0;
  margin: auto;
  border: 1px solid #d9eae1;
  border-radius: 25px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 25px 65px #154c3524, 0 3px 12px #154c3509;
  animation: centeredLoginEnter .48s ease-out both;
}
.auth-page-centered-login .auth-story {
  display: none;
}
.auth-page-centered-login .auth-panel {
  display: block;
  min-width: 0;
  background: #fff;
}
.auth-page-centered-login .auth-panel-inner {
  box-sizing: border-box;
  width: 100%;
  max-width: 515px;
  margin: auto;
  padding: clamp(30px, 4vw, 47px) clamp(24px, 4vw, 44px) 37px;
}
.auth-page-centered-login .auth-mobile-tag {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 0 0 16px;
  color: #0b795a;
  font-size: .68rem;
  font-weight: 850;
  letter-spacing: .13em;
}
.auth-page-centered-login .auth-mobile-tag span {
  font-size: 1.14rem;
}
.auth-page-centered-login .auth-page-footnote {
  position: relative;
  z-index: 1;
  margin-top: 18px;
  color: #648777;
  line-height: 1.5;
}
.auth-page-centered-login .auth-orb-one {
  top: -220px;
  right: -110px;
}
.auth-page-centered-login .auth-orb-two {
  bottom: -185px;
  left: -100px;
}
@keyframes centeredLoginEnter {
  from { opacity: 0; transform: translateY(20px) scale(.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (max-width: 600px) {
  .auth-page.auth-page-centered-login {
    justify-content: center;
    min-height: max(580px, calc(100dvh - 68px));
    padding: 20px 12px;
  }
  .auth-page-centered-login .auth-frame {
    width: 100%;
    border-radius: 20px;
  }
  .auth-page-centered-login .auth-panel-inner {
    padding: 28px 22px 30px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .auth-page-centered-login .auth-frame { animation: none; }
}
/* UNISHORTLIST CENTERED LOGIN END */


/* UNISHORTLIST CENTERED SIGNUP START
   Register page only. The login layout and auth/redirect logic are unchanged. */
.auth-page.auth-page-centered-signup {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: max(790px, calc(100dvh - 75px));
  padding: clamp(25px, 4.5vh, 50px) 16px 24px;
  background:
    radial-gradient(circle at 10% 16%, #d9f5e6 0, transparent 30%),
    radial-gradient(circle at 87% 80%, #def7e9 0, transparent 34%),
    linear-gradient(140deg, #f8fdfa, #eaf8f0);
}
.auth-page-centered-signup .auth-frame {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  width: min(100%, 570px);
  max-width: 570px;
  min-height: 0;
  margin: auto;
  border: 1px solid #d4e9dd;
  border-radius: 24px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 26px 70px #184a351d, 0 6px 18px #184a350b;
  animation: centeredSignupEnter .48s cubic-bezier(.19,.9,.34,1) both;
}
.auth-page-centered-signup .auth-story { display: none; }
.auth-page-centered-signup .auth-panel {
  display: block;
  min-width: 0;
  background: #fff;
}
.auth-page-centered-signup .auth-panel-inner {
  box-sizing: border-box;
  width: 100%;
  max-width: 570px;
  margin: 0 auto;
  padding: clamp(25px, 3.5vw, 38px) clamp(22px, 4vw, 43px) 29px;
}
.auth-page-centered-signup .auth-mobile-tag {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 0 0 15px;
  font-size: .68rem;
  font-weight: 850;
  letter-spacing: .13em;
  color: #097b5e;
}
.auth-page-centered-signup .auth-mobile-tag span { font-size: 1.14rem; }
.auth-page-centered-signup .auth-page-footnote {
  position: relative;
  z-index: 1;
  margin: 17px 0 0;
  line-height: 1.5;
  color: #648777;
}
.auth-page-centered-signup .auth-orb-one { top: -195px; right: -100px; }
.auth-page-centered-signup .auth-orb-two { bottom: -190px; left: -95px; }
@keyframes centeredSignupEnter {
  from { opacity: 0; transform: translateY(19px) scale(.987); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (max-width: 600px) {
  .auth-page.auth-page-centered-signup {
    min-height: max(710px, calc(100dvh - 68px));
    padding: 18px 12px;
  }
  .auth-page-centered-signup .auth-frame { width: 100%; border-radius: 19px; }
  .auth-page-centered-signup .auth-panel-inner { padding: 25px 20px 27px; }
}
@media (prefers-reduced-motion: reduce) {
  .auth-page-centered-signup .auth-frame { animation: none; }
}
/* UNISHORTLIST CENTERED SIGNUP END */

</style>
