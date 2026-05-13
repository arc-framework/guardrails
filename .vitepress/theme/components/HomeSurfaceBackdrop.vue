<script setup lang="ts">
import {
  mountSurfaceBackground,
  type SurfaceBackgroundConfig,
  type SurfaceBackgroundControls,
} from '../../../shared/visuals/dottedSurface';
import { useData } from 'vitepress';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const surfaceElement = ref<HTMLElement | null>(null);
const surfaceCanvas = ref<HTMLCanvasElement | null>(null);
const { isDark } = useData();

let resizeObserver: ResizeObserver | undefined;
let measureFrameId = 0;
let resizeSurfaceCanvas = () => {};
let surfaceControls: DottedSurfaceControls | undefined;

function getDocsSurfaceConfig(): SurfaceBackgroundConfig {
  return {
    amplitude: 10,
    density: 0.72,
    opacity: 0.7,
    style: 'mesh',
    theme: isDark.value ? 'dark' : 'light',
  };
}

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
  const divider =
    cutoff.previousElementSibling instanceof HTMLElement &&
    cutoff.previousElementSibling.tagName === 'HR'
      ? cutoff.previousElementSibling
      : cutoff;
  const dividerRect = divider.getBoundingClientRect();
  const boundary = divider === cutoff ? dividerRect.top : dividerRect.bottom;
  const height = Math.max(boundary - homeRect.top + navOffset, 620);

  surface.style.setProperty('--arc-home-surface-height', `${height}px`);
}

function scheduleMeasure() {
  if (typeof window === 'undefined') {
    return;
  }

  window.cancelAnimationFrame(measureFrameId);
  measureFrameId = window.requestAnimationFrame(() => {
    measureSurfaceHeight();
    resizeSurfaceCanvas();
  });
}

function initializeSurfaceCanvas() {
  const canvas = surfaceCanvas.value;

  if (typeof window === 'undefined' || !canvas) {
    return () => {};
  }

  surfaceControls = mountSurfaceBackground(canvas, getDocsSurfaceConfig);
  resizeSurfaceCanvas = surfaceControls.resize;

  return () => {
    surfaceControls?.destroy();
    surfaceControls = undefined;
    resizeSurfaceCanvas = () => {};
  };
}

watch(isDark, () => {
  surfaceControls?.redraw();
});

onMounted(async () => {
  await nextTick();
  scheduleMeasure();
  initializeSurfaceCanvas();

  window.addEventListener('resize', scheduleMeasure);

  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      scheduleMeasure();
    });

    const home = surfaceElement.value?.closest('.VPHome') as HTMLElement | null;

    if (home) {
      resizeObserver.observe(home);
      resizeObserver.observe(surfaceElement.value!);
    }
  }
});

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.cancelAnimationFrame(measureFrameId);
    window.removeEventListener('resize', scheduleMeasure);
  }

  resizeObserver?.disconnect();
  surfaceControls?.destroy();
  surfaceControls = undefined;
});
</script>

<template>
  <div ref="surfaceElement" class="arc-home-surface" aria-hidden="true">
    <canvas ref="surfaceCanvas" class="arc-home-surface__canvas" />
  </div>
</template>
