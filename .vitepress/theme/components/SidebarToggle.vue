<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const STORAGE_KEY = 'arc-guardrails-docs-sidebar-collapsed'
const collapsed = ref(false)

function applyState(value) {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.classList.toggle('sidebar-collapsed', value)
}

function toggleSidebar() {
  collapsed.value = !collapsed.value
}

onMounted(() => {
  try {
    collapsed.value = window.localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    collapsed.value = false
  }
  applyState(collapsed.value)
})

watch(collapsed, (value) => {
  applyState(value)
  try {
    window.localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    // Ignore storage failures.
  }
})

const buttonLabel = computed(() =>
  collapsed.value ? 'Show sidebar' : 'Hide sidebar',
)
</script>

<template>
  <button
    class="arc-doc-sidebar-toggle"
    type="button"
    :aria-label="buttonLabel"
    :aria-pressed="collapsed"
    @click="toggleSidebar"
  >
    <span class="arc-doc-sidebar-toggle__icon" aria-hidden="true">≡</span>
    <span class="arc-doc-sidebar-toggle__text">{{ buttonLabel }}</span>
  </button>
</template>