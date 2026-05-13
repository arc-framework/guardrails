import { generateBreadcrumbsData } from '@nolebase/vitepress-plugin-breadcrumbs/vitepress';
import { GitChangelog } from '@nolebase/vitepress-plugin-git-changelog/vite';
import { defineConfig } from 'vitepress';
import {
  groupIconMdPlugin,
  groupIconVitePlugin,
} from 'vitepress-plugin-group-icons';
import llmstxt from 'vitepress-plugin-llms';

const base = process.env.DOCS_BASE || '/';
const repoUrl = 'https://github.com/arc-framework/guardrails';
const docsBranch = 'main';
const siteUrl = 'https://arc-framework.github.io/guardrails/';

export default defineConfig({
  title: 'arc-guardrails',
  description:
    'Protocol-driven guardrails for LLM applications, with a reusable Python SDK, transport-neutral service surface, and operator-facing flow tooling.',
  lang: 'en-US',
  base,
  cleanUrls: true,
  srcDir: 'docs/vitepress',
  lastUpdated: true,
  sitemap: {
    hostname: siteUrl,
  },
  transformPageData(pageData, context) {
    generateBreadcrumbsData(pageData, context);
  },

  themeConfig: {
    logo: '/logo-mark.svg',
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/guide/' },
      { text: 'Reference', link: '/reference/' },
      { text: 'Canvases', link: '/canvases/' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/guide/' },
            { text: 'Architecture', link: '/guide/architecture' },
            { text: 'Pipeline', link: '/guide/pipeline' },
            { text: 'Setup', link: '/guide/setup' },
            { text: 'Extension Patterns', link: '/guide/extensions' },
          ],
        },
      ],
      '/reference/': [
        {
          text: 'Reference',
          collapsed: false,
          items: [
            { text: 'Reference Index', link: '/reference/' },
            { text: 'Packages', link: '/reference/packages' },
            { text: 'API Service', link: '/reference/api' },
            { text: 'Observability', link: '/reference/observability' },
            {
              text: 'Detection Coverage',
              link: '/reference/detection-coverage',
            },
            { text: 'Technology Stack', link: '/reference/technology-stack' },
            { text: 'Public Surface', link: '/reference/public-surface' },
          ],
        },
      ],
      '/canvases/': [
        {
          text: 'Canvases',
          collapsed: false,
          items: [
            { text: 'Canvas Gallery', link: '/canvases/' },
            {
              text: 'Pipeline Swimlane',
              link: '/canvases/pipeline-swimlane',
            },
            {
              text: 'Request Decision Tree',
              link: '/canvases/request-flow-tree',
            },
            { text: 'Detailed Request Flow', link: '/canvases/request-flow' },
            {
              text: 'Benign Request DAG',
              link: '/canvases/request-dag-benign',
            },
            { text: 'PII Redaction DAG', link: '/canvases/request-dag-pii' },
            {
              text: 'Blocked Request DAG',
              link: '/canvases/request-dag-block',
            },
          ],
        },
      ],
    },

    search: { provider: 'local' },
    outline: { level: [2, 3] },
    socialLinks: [{ icon: 'github', link: repoUrl }],

    editLink: {
      pattern: `${repoUrl}/edit/${docsBranch}/docs/vitepress/:path`,
      text: 'Edit this page on GitHub',
    },

    lastUpdated: {
      text: 'Last updated',
      formatOptions: {
        dateStyle: 'medium',
        timeStyle: 'short',
      },
    },

    footer: {
      message: 'Open source but Use responsibly 🛡️',
    },
  },

  markdown: {
    lineNumbers: true,
    config(md) {
      md.use(groupIconMdPlugin);
    },
  },

  vite: {
    optimizeDeps: {
      exclude: ['@nolebase/vitepress-plugin-breadcrumbs/client'],
    },
    ssr: {
      noExternal: ['@nolebase/vitepress-plugin-breadcrumbs'],
    },
    plugins: [
      GitChangelog({ repoURL: () => repoUrl }),
      groupIconVitePlugin(),
      llmstxt(),
    ],
  },

  ignoreDeadLinks: true,
});
