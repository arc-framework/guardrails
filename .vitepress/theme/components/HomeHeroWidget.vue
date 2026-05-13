<script setup lang="ts">
const surfaceChips = ['Core contracts', 'Runtime library', 'Service boundary'];
const stats = [
  { label: '12', detail: 'pipeline stages' },
  { label: '3', detail: 'package surfaces' },
  { label: '5+', detail: 'inspector families' },
];
</script>

<template>
  <div class="arc-home-hero-widget">
    <div class="arc-home-widget-shell arc-home-widget-shell--hero">
      <div class="arc-home-hero-widget__frame">
        <div class="arc-home-hero-widget__eyebrow">Policy-aware runtime</div>

        <div class="arc-home-hero-widget__mark-wrap" aria-hidden="true">
          <div class="arc-home-hero-widget__halo" />
          <svg
            class="arc-home-hero-mark"
            viewBox="0 0 24 24"
            role="img"
            aria-label="arc-guard shield brand">
            <rect
              width="24"
              height="24"
              rx="6"
              fill="hsl(var(--vp-c-neutral-inverse, 0 0% 98%))" />
            <path
              d="M12 4 L19 7 L19 12 C19 16 16 19 12 20 C8 19 5 16 5 12 L5 7 Z"
              fill="rgba(15, 23, 42, 0.94)" />
            <path
              d="M9 12 L11 14 L15 10"
              fill="none"
              stroke="rgba(255, 255, 255, 0.94)"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round" />
          </svg>
        </div>

        <div class="arc-home-hero-widget__chips">
          <span
            v-for="surface in surfaceChips"
            :key="surface"
            class="arc-home-chip arc-home-chip--accent">
            {{ surface }}
          </span>
        </div>

        <div class="arc-home-hero-widget__stats">
          <div
            v-for="stat in stats"
            :key="stat.detail"
            class="arc-home-hero-stat">
            <strong>{{ stat.label }}</strong>
            <span>{{ stat.detail }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
