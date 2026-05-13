<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core';

export interface CanvasNodeData {
  title: string;
  body: string;
  tone: string;
  kind: 'text' | 'group';
}

defineProps<NodeProps<CanvasNodeData>>();
</script>

<template>
  <div
    class="arc-canvas-node"
    :class="[
      data.kind === 'group' ? 'arc-canvas-node--group' : '',
      selected ? 'arc-canvas-node--selected' : '',
    ]">
    <strong class="arc-canvas-node__title">{{ data.title }}</strong>
    <p v-if="data.body" class="arc-canvas-node__body">{{ data.body }}</p>
  </div>
</template>
