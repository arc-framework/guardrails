<script setup lang="ts">
import { NolebaseGitContributors } from '@nolebase/vitepress-plugin-git-changelog/client';
import { useChangelog } from '@nolebase/vitepress-plugin-git-changelog/client/composables/changelog';
import { computed, onMounted } from 'vue';

const MAX_VISIBLE_COMMITS = 10;
const { commits, useHmr } = useChangelog();

const visibleCommits = computed(() =>
  commits.value.slice(0, MAX_VISIBLE_COMMITS),
);
const hiddenCommitCount = computed(() =>
  Math.max(commits.value.length - visibleCommits.value.length, 0),
);

function authorNames(commit: (typeof visibleCommits.value)[number]): string {
  const names = commit.authors.map((author) => author.name).filter(Boolean);

  return names.join(', ');
}

onMounted(() => {
  useHmr();
});
</script>

<template>
  <section class="arc-doc-history-bar" aria-label="Page history">
    <div class="arc-doc-history-bar__contributors">
      <span class="arc-doc-history-bar__label">Contributors</span>
      <NolebaseGitContributors />
    </div>

    <div class="arc-doc-history-bar__history">
      <details class="arc-doc-history-dropdown">
        <summary class="arc-doc-history-bar__link">View full history</summary>

        <div class="arc-doc-history-dropdown__panel">
          <div class="arc-doc-history-dropdown__header">
            <span class="arc-doc-history-dropdown__title">Recent changes</span>
            <span
              v-if="hiddenCommitCount > 0"
              class="arc-doc-history-dropdown__count">
              Latest {{ visibleCommits.length }} of {{ commits.length }}
            </span>
          </div>

          <ol
            v-if="visibleCommits.length > 0"
            class="arc-doc-history-dropdown__list">
            <li
              v-for="commit in visibleCommits"
              :key="commit.hash"
              class="arc-doc-history-dropdown__item">
              <code class="arc-doc-history-dropdown__hash">{{
                commit.hash.slice(0, 7)
              }}</code>
              <div class="arc-doc-history-dropdown__body">
                <div class="arc-doc-history-dropdown__message">
                  {{ commit.message }}
                </div>
                <div
                  v-if="authorNames(commit)"
                  class="arc-doc-history-dropdown__authors">
                  {{ authorNames(commit) }}
                </div>
              </div>
            </li>
          </ol>

          <p v-else class="arc-doc-history-dropdown__empty">
            No recent changes
          </p>
        </div>
      </details>
    </div>
  </section>
</template>
