<script setup lang="ts">
import { computed } from 'vue';
import type { NodeProps } from '@vue-flow/core';
import type { CanvasGroupNodeData } from '../canvasParser';

const props = defineProps<NodeProps<CanvasGroupNodeData>>();

const colorBandClass = computed(() => colorClassFor(props.data.color));

function colorClassFor(color?: string): string {
  switch (color) {
    case '1':
      return 'arc-canvas-band--red';
    case '2':
      return 'arc-canvas-band--orange';
    case '3':
      return 'arc-canvas-band--yellow';
    case '4':
      return 'arc-canvas-band--green';
    case '5':
      return 'arc-canvas-band--cyan';
    case '6':
      return 'arc-canvas-band--purple';
    default:
      return 'arc-canvas-band--neutral';
  }
}
</script>

<template>
  <div class="arc-canvas-group-node" :class="colorBandClass">
    <div class="arc-canvas-group-node__label">{{ props.data.label }}</div>
  </div>
</template>
