<script setup lang="ts">
import { useData } from 'vitepress';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

const surfaceElement = ref<HTMLElement | null>(null);
const { isDark } = useData();

const surfaceSrc = computed(
  () =>
    `https://cdn.21st.dev/sshahaider/dotted-surface/default/bundle.1757222194600.html?theme=${
      isDark.value ? 'dark' : 'light'
    }&dark=${isDark.value ? 'true' : 'false'}`,
);

let resizeObserver: ResizeObserver | undefined;
let frameId = 0;

function readCssPixels(variableName: string): number {
  if (typeof window === 'undefined') {
    return 0;
  }

  const value = window
    .getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim();
  const parsed = Number.parseFloat(value);

  return Number.isFinite(parsed) ? parsed : 0;
}

function measureSurfaceHeight() {
  const surface = surfaceElement.value;
  const home = surface?.closest('.VPHome') as HTMLElement | null;

  if (!surface || !home) {
    return;
  }

  const cutoff = home.querySelector<HTMLElement>('#start-here');
  const navOffset =
    readCssPixels('--vp-nav-height') + readCssPixels('--vp-layout-top-height');

  if (!cutoff) {
    surface.style.setProperty(
      '--arc-home-surface-height',
      `calc(clamp(620px, 88vh, 980px) + ${navOffset}px)`,
    );
    return;
  }

  const homeRect = home.getBoundingClientRect();
  const cutoffRect = cutoff.getBoundingClientRect();
  const height = Math.max(cutoffRect.top - homeRect.top + navOffset - 24, 620);

  surface.style.setProperty('--arc-home-surface-height', `${height}px`);
}

function scheduleMeasure() {
  if (typeof window === 'undefined') {
    return;
  }

  window.cancelAnimationFrame(frameId);
  frameId = window.requestAnimationFrame(() => {
    measureSurfaceHeight();
  });
}

onMounted(async () => {
  await nextTick();
  scheduleMeasure();

  window.addEventListener('resize', scheduleMeasure);

  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      scheduleMeasure();
    });

    const home = surfaceElement.value?.closest('.VPHome') as HTMLElement | null;

    if (home) {
      resizeObserver.observe(home);
    }
  }
});

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.cancelAnimationFrame(frameId);
    window.removeEventListener('resize', scheduleMeasure);
  }

  resizeObserver?.disconnect();
});
</script>

<template>
  <div ref="surfaceElement" class="arc-home-surface" aria-hidden="true">
    <iframe
      class="arc-home-surface__frame"
      :src="surfaceSrc"
      title="Decorative dotted surface background"
      loading="eager"
      sandbox="allow-scripts allow-same-origin"
      scrolling="no"
      tabindex="-1" />
  </div>
</template>
