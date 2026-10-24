<script setup lang="ts">
import { ref } from 'vue'

// Lightweight CSS 3D campus: no WebGL, third-party downloads, or extra dependencies.
const tiltX = ref(0)
const tiltY = ref(0)
function onPointerMove(event: PointerEvent) {
  if (event.pointerType !== 'mouse' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  tiltX.value = ((event.clientY - rect.top) / rect.height - .5) * -9
  tiltY.value = ((event.clientX - rect.left) / rect.width - .5) * 17
}
function reset() { tiltX.value = 0; tiltY.value = 0 }
</script>

<template>
  <div class="dcampus-root">
    <div class="campus-visual" role="img" @pointermove="onPointerMove" @pointerleave="reset" :style="{ '--campus-rotate-x': `${tiltX}deg`, '--campus-rotate-y': `${tiltY}deg` }" aria-label="Animated three-dimensional university campus model with floating academic profile, eligibility and comparison cards">
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
            <span><strong>Explore your future</strong><small>Your journey starts here</small></span>
          </div>
          <div class="campus-chip campus-chip-eligibility" aria-hidden="true">
            <span class="campus-chip-icon campus-chip-icon-check">✓</span>
            <span><strong>See your progress</strong><small>Clear next steps</small></span>
          </div>
          <div class="campus-chip campus-chip-compare" aria-hidden="true">
            <span class="campus-chip-icon campus-chip-icon-blue">⇄</span>
            <span><strong>Your university shortlist</strong><small>Find your best fit</small></span>
          </div>
          <span class="campus-spark campus-spark-one" aria-hidden="true">✧</span>
          <span class="campus-spark campus-spark-two" aria-hidden="true">✦</span>
          <span class="campus-spark campus-spark-three" aria-hidden="true">✧</span>
          <span class="campus-visual-footnote">MOVE YOUR CURSOR TO EXPLORE · 3D CAMPUS</span>
        </div>
  </div>
</template>

<style scoped>
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

/* Dashboard 3D model: scaled diorama from UniShortlist's existing brand scene. */
.dcampus-root { height: 292px; width:100%; position:relative; isolation:isolate; pointer-events:auto; }
.dcampus-root .campus-visual { position:absolute; top:50%; left:50%; width:485px; height:450px; max-width:none; transform:translate(-50%,-50%) scale(.73); transform-origin:center; }
.dcampus-root .campus-model { transition:transform .25s ease-out; transform:translate(-50%,-50%) rotateX(var(--campus-rotate-x, 0deg)) rotateY(var(--campus-rotate-y, 0deg)); }
.dcampus-root .campus-chip { min-width:0; padding:10px 12px; border-radius:13px; box-shadow:0 15px 34px #2359411f; }
.dcampus-root .campus-chip-program { top:7%; left:0; }
.dcampus-root .campus-chip-eligibility { top:18%; right:-2%; }
.dcampus-root .campus-chip-compare { bottom:10%; right:0; }
.dcampus-root .campus-visual-footnote { bottom:2px; right:8%; letter-spacing:.1em; font-size:.63rem; font-weight:750; }
.dcampus-root .campus-aura-one { width:75%; }
.dcampus-root .campus-aura-two { width:90%; }
@media (max-width:1200px) {.dcampus-root .campus-visual { transform:translate(-50%,-50%) scale(.62); }}
@media (max-width:820px) {.dcampus-root {height:260px}.dcampus-root .campus-visual { transform:translate(-50%,-50%) scale(.62); }}
@media (max-width:460px) {.dcampus-root {height:220px}.dcampus-root .campus-visual { transform:translate(-50%,-50%) scale(.48); }}
@media (prefers-reduced-motion:reduce) {
 .dcampus-root .campus-float-architecture,.dcampus-root .campus-grad-cap,.dcampus-root .campus-chip,.dcampus-root .campus-spark { animation:none!important; }
 .dcampus-root .campus-model { transition:none!important; }
}
</style>
