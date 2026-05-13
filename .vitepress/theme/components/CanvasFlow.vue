<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useVueFlow, VueFlow, type NodeMouseEvent } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { getCanvasDocument, getCanvasEntry } from '../canvasRegistry';
import {
  parseCanvas,
  type CanvasGroupNodeData,
  type CanvasTextNodeData,
} from '../canvasParser';
import { renderCanvasText } from '../canvasMarkdown';
import { spreadLayout } from '../canvasLayout';
import CanvasGroupNode from './CanvasGroupNode.vue';
import CanvasTextNode from './CanvasTextNode.vue';

const props = withDefaults(
  defineProps<{
    canvasId: string;
    height?: string;
  }>(),
  {
    height: '78vh',
  },
);

const nodeTypes = {
  canvasText: CanvasTextNode,
  canvasGroup: CanvasGroupNode,
};

const DOCS_SPREAD_FACTOR = 1.18;

const flowId = `arc-doc-canvas-${props.canvasId}`;
const { fitView, zoomIn, zoomOut } = useVueFlow(flowId);

const document = computed(() => getCanvasDocument(props.canvasId));
const entry = computed(() => getCanvasEntry(props.canvasId));

const layoutMode = ref<'original' | 'spread'>('original');
const selectedId = ref<string | null>(null);
const boardElement = ref<HTMLElement | null>(null);
const isFullscreen = ref(false);

const parsedCanvas = computed(() =>
  document.value ? parseCanvas(document.value) : null,
);
const spreadCanvas = computed(() =>
  parsedCanvas.value
    ? spreadLayout(
        parsedCanvas.value.nodes,
        parsedCanvas.value.edges,
        DOCS_SPREAD_FACTOR,
      )
    : null,
);
const activeCanvas = computed(() =>
  layoutMode.value === 'spread' ? spreadCanvas.value : parsedCanvas.value,
);
const flowNodes = computed(() => activeCanvas.value?.nodes ?? []);
const flowEdges = computed(() => activeCanvas.value?.edges ?? []);
const flowKey = computed(() => `${props.canvasId}:${layoutMode.value}`);

const selectedSourceNode = computed(
  () =>
    document.value?.nodes.find((node) => node.id === selectedId.value) ?? null,
);

const selectedNodeTitle = computed(() => {
  if (!selectedSourceNode.value) {
    return null;
  }

  if (selectedSourceNode.value.type === 'group') {
    return selectedSourceNode.value.label ?? 'Group';
  }

  const firstLine = (selectedSourceNode.value.text ?? '')
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean);

  return (firstLine ?? selectedSourceNode.value.id)
    .replace(/^#+\s*/, '')
    .replace(/^\*\*(.*)\*\*$/, '$1')
    .replace(/^`(.*)`$/, '$1');
});

const selectedNodeKind = computed(() => selectedSourceNode.value?.type ?? null);
const selectedNodePreview = computed(() =>
  selectedSourceNode.value?.type === 'text'
    ? renderCanvasText(selectedSourceNode.value.text ?? '')
    : '',
);

watch(
  document,
  (nextDocument) => {
    layoutMode.value = 'original';
    selectedId.value =
      nextDocument?.nodes.find((node) => node.type === 'text')?.id ?? null;
  },
  { immediate: true },
);

function handleNodeClick(event: NodeMouseEvent) {
  if (event.node.type === 'canvasGroup') {
    return;
  }

  selectedId.value = event.node.id;
}

function toggleLayout() {
  layoutMode.value = layoutMode.value === 'spread' ? 'original' : 'spread';
}

function handleZoomIn() {
  void zoomIn();
}

function handleZoomOut() {
  void zoomOut();
}

function handleFitView() {
  void fitView({ padding: 0.2 });
}

function syncFullscreenState() {
  if (typeof window === 'undefined') {
    return;
  }

  isFullscreen.value = window.document.fullscreenElement === boardElement.value;
}

async function toggleFullscreen() {
  if (typeof window === 'undefined' || !boardElement.value) {
    return;
  }

  if (window.document.fullscreenElement === boardElement.value) {
    await window.document.exitFullscreen();
    return;
  }

  await boardElement.value.requestFullscreen();
}

onMounted(() => {
  if (typeof window === 'undefined') {
    return;
  }

  syncFullscreenState();
  window.document.addEventListener('fullscreenchange', syncFullscreenState);
});

onBeforeUnmount(() => {
  if (typeof window === 'undefined') {
    return;
  }

  window.document.removeEventListener('fullscreenchange', syncFullscreenState);
});

const nodeCount = computed(() => parsedCanvas.value?.nodes.length ?? 0);
const edgeCount = computed(() => parsedCanvas.value?.edges.length ?? 0);
</script>

<template>
  <div v-if="entry && document && activeCanvas" class="arc-canvas-shell">
    <aside class="arc-canvas-sidebar">
      <div class="arc-canvas-sidebar__intro">
        <h3>{{ entry.title }}</h3>
        <p>{{ entry.summary }}</p>
        <p class="arc-canvas-help">
          Drag to pan, use the controls to zoom or fit the board, and use the
          spread toggle to open up dense canvases without losing their original
          orientation.
        </p>
      </div>

      <div class="arc-canvas-sidebar__details">
        <div class="arc-canvas-meta">
          <div class="arc-canvas-meta-row">
            <strong>Canvas id</strong>
            <span
              ><code>{{ canvasId }}</code></span
            >
          </div>
          <div class="arc-canvas-meta-row">
            <strong>Layout</strong>
            <span>{{ layoutMode === 'spread' ? 'Spread' : 'Original' }}</span>
          </div>
          <div class="arc-canvas-meta-row">
            <strong>Graph size</strong>
            <span>{{ nodeCount }} nodes · {{ edgeCount }} edges</span>
          </div>
        </div>
      </div>

      <template v-if="selectedSourceNode && selectedNodeTitle">
        <div class="arc-canvas-sidebar__selection">
          <h4>Selected node</h4>
          <div class="arc-canvas-meta-row">
            <strong>Id</strong>
            <span
              ><code>{{ selectedSourceNode.id }}</code></span
            >
          </div>
          <div class="arc-canvas-meta-row">
            <strong>Kind</strong>
            <span>{{ selectedNodeKind }}</span>
          </div>
          <div class="arc-canvas-meta-row">
            <strong>Title</strong>
            <span>{{ selectedNodeTitle }}</span>
          </div>
          <div
            v-if="selectedNodePreview"
            class="arc-canvas-selected-preview"
            v-html="selectedNodePreview" />
        </div>
      </template>
    </aside>

    <div ref="boardElement" class="arc-canvas-board" :style="{ height }">
      <div class="arc-canvas-toolbar">
        <div class="arc-canvas-toolbar__group arc-canvas-toolbar__group--icons">
          <button
            class="arc-canvas-toolbar__icon-button"
            type="button"
            aria-label="Zoom in"
            title="Zoom in"
            @click="handleZoomIn">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 3v10M3 8h10" />
            </svg>
          </button>
          <button
            class="arc-canvas-toolbar__icon-button"
            type="button"
            aria-label="Zoom out"
            title="Zoom out"
            @click="handleZoomOut">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 8h10" />
            </svg>
          </button>
          <button
            class="arc-canvas-toolbar__icon-button"
            type="button"
            aria-label="Fit view"
            title="Fit view"
            @click="handleFitView">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 6V3h3M10 3h3v3M13 10v3h-3M6 13H3v-3" />
            </svg>
          </button>
          <button
            class="arc-canvas-toolbar__icon-button"
            type="button"
            :aria-label="isFullscreen ? 'Exit full screen' : 'Full screen'"
            :title="isFullscreen ? 'Exit full screen' : 'Full screen'"
            :aria-pressed="isFullscreen"
            @click="toggleFullscreen">
            <svg v-if="!isFullscreen" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M6 3H3v3M10 3h3v3M13 10v3h-3M6 13H3v-3" />
            </svg>
            <svg v-else viewBox="0 0 16 16" aria-hidden="true">
              <path d="M6 6H3V3M10 6h3V3M13 10v3h-3M6 10H3v3" />
            </svg>
          </button>
        </div>

        <div class="arc-canvas-toolbar__group">
          <button
            class="arc-canvas-toolbar__button"
            type="button"
            :aria-pressed="layoutMode === 'spread'"
            :title="
              layoutMode === 'spread'
                ? 'Return to the original canvas layout'
                : 'Spread nodes outward for more room'
            "
            @click="toggleLayout">
            {{ layoutMode === 'spread' ? 'Original' : 'Spread' }}
          </button>
        </div>
      </div>

      <VueFlow
        :id="flowId"
        :key="flowKey"
        class="arc-flow-diagram"
        :nodes="flowNodes"
        :edges="flowEdges"
        :node-types="nodeTypes"
        :fit-view-on-init="true"
        :fit-view-options="{ padding: 0.2 }"
        :min-zoom="0.1"
        :max-zoom="1.6"
        :nodes-draggable="false"
        :nodes-connectable="false"
        :elements-selectable="true"
        @node-click="handleNodeClick">
        <Background :gap="16" :size="1" color="rgba(100, 116, 139, 0.16)" />
      </VueFlow>
    </div>
  </div>

  <div v-else class="arc-canvas-empty">
    Unable to load the requested canvas.
  </div>
</template>
