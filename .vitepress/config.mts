import { defineConfig } from 'vitepress';

const base = process.env.DOCS_BASE || '/';

export default defineConfig({
  title: 'arc-guardrails',
  description:
    'Protocol-driven guardrails for LLM applications, with a reusable Python SDK, transport-neutral service surface, and operator-facing flow tooling.',
  lang: 'en-US',
  base,
  cleanUrls: true,
  srcDir: 'docs/vitepress',
  lastUpdated: true,

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
    socialLinks: [],

    lastUpdated: {
      text: 'Last updated',
    },

    footer: {
      message: 'Open source documentation built with VitePress.',
    },
  },

  markdown: {
    lineNumbers: true,
  },

  ignoreDeadLinks: true,
});
