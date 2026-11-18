<template>
  <div class="ridge" aria-hidden="true">
    <svg viewBox="0 0 1440 520" preserveAspectRatio="none">
      <defs>
        <linearGradient id="nr-m0" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#3d4f74" /><stop offset="1" stop-color="#222c42" />
        </linearGradient>
        <linearGradient id="nr-m1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2d3b58" /><stop offset="1" stop-color="#1a2334" />
        </linearGradient>
        <linearGradient id="nr-m2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#212b41" /><stop offset="1" stop-color="#141b28" />
        </linearGradient>
        <linearGradient id="nr-m3" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#141a26" /><stop offset="1" stop-color="#0e1118" />
        </linearGradient>
      </defs>
      <path fill="url(#nr-m0)" opacity=".32" style="--pa-depth:6px"
        d="M0,268 C140,208 280,252 420,196 C560,142 700,226 840,180 C980,136 1120,220 1260,170 C1340,142 1400,186 1440,168 L1440,520 L0,520 Z" />
      <path fill="url(#nr-m1)" opacity=".58" style="--pa-depth:12px"
        d="M0,352 C120,296 240,340 360,290 C480,240 600,318 720,270 C840,224 960,306 1080,262 C1200,222 1320,300 1440,258 L1440,520 L0,520 Z" />
      <path fill="url(#nr-m2)" opacity=".95" style="--pa-depth:22px"
        d="M0,436 C140,378 280,420 420,360 C560,302 700,386 840,330 C980,278 1120,368 1260,322 C1340,296 1400,348 1440,330 L1440,520 L0,520 Z" />
      <path fill="url(#nr-m3)" style="--pa-depth:36px"
        d="M0,492 C160,448 320,478 480,430 C640,384 800,452 960,406 C1120,362 1280,444 1440,398 L1440,520 L0,520 Z" />
    </svg>
    <div class="mist"></div>
    <div class="ridge-top"></div>
    <div class="ridge-fade"></div>
  </div>
</template>

<script setup lang="ts">
/* 夜色山水层：纯装饰，绝对定位由父级容器控制覆盖范围 */
</script>

<style scoped>
.ridge {
  position: absolute; left: -2%; right: -2%;
  pointer-events: none;
}
.ridge svg { width: 100%; height: 100%; display: block; overflow: visible; }
.ridge path { transform: translateX(calc(var(--mx, 0) * var(--pa-depth, 0px))); }
.mist {
  position: absolute; left: -4%; right: -4%; top: 4%; height: 34%;
  background:
    radial-gradient(48% 100% at 22% 100%, rgba(143, 163, 189, 0.13), transparent 70%),
    radial-gradient(52% 100% at 68% 100%, rgba(143, 163, 189, 0.10), transparent 70%);
  transform: translateX(calc(var(--mx, 0) * 14px));
}
.ridge-top {
  position: absolute; left: 0; right: 0; top: -1px; height: 22%;
  background: linear-gradient(0deg, transparent, var(--paper) 90%);
}
.ridge-fade {
  position: absolute; left: 0; right: 0; bottom: -1px; height: 68%;
  background: linear-gradient(180deg, transparent, var(--paper) 82%);
}
@media (prefers-reduced-motion: no-preference) {
  .fx .ridge { animation: nr-rise 1.5s .4s cubic-bezier(.2, .7, .2, 1) both; }
  .fx .mist { animation: nr-mist 2.2s 1s both, nr-drift 30s 2.5s ease-in-out infinite alternate; }
}
@keyframes nr-rise {
  from { transform: translateY(56px); }
  to { transform: translateY(0); }
}
@keyframes nr-mist { from { opacity: 0; } to { opacity: 1; } }
@keyframes nr-drift {
  from { margin-left: -1.6%; }
  to { margin-left: 1.6%; }
}
</style>
