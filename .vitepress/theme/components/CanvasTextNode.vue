<script setup lang="ts">
import { computed } from 'vue';
import { Handle, Position, type NodeProps } from '@vue-flow/core';
import { renderCanvasText } from '../canvasMarkdown';
import type { CanvasTextNodeData } from '../canvasParser';

const props = defineProps<NodeProps<CanvasTextNodeData>>();

const sides = [
  { id: 'top', position: Position.Top },
  { id: 'right', position: Position.Right },
  { id: 'bottom', position: Position.Bottom },
  { id: 'left', position: Position.Left },
] as const;

const colorBandClass = computed(() => colorClassFor(props.data.color));
const renderedText = computed(() => renderCanvasText(props.data.text));
const isSelected = computed(() => props.selected === true);

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
  <div
    class="arc-canvas-text-node"
    :class="[
      colorBandClass,
      isSelected ? 'arc-canvas-text-node--selected' : '',
    ]">
    <template v-for="side in sides" :key="side.id">
      <Handle
        type="source"
        :id="`out-${side.id}`"
        :position="side.position"
        class="arc-canvas-handle"
        :connectable="false" />
      <Handle
        type="target"
        :id="`in-${side.id}`"
        :position="side.position"
        class="arc-canvas-handle"
        :connectable="false" />
    </template>

    <div class="arc-canvas-text-node__content" v-html="renderedText" />
  </div>
</template>
