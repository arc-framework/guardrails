import { NolebaseBreadcrumbs } from '@nolebase/vitepress-plugin-breadcrumbs/client';
import { NolebaseGitChangelogPlugin } from '@nolebase/vitepress-plugin-git-changelog/client';
import '@nolebase/vitepress-plugin-git-changelog/client/style.css';
import 'virtual:group-icons.css';
import { defineClientComponent } from 'vitepress';
import DefaultTheme from 'vitepress/theme-without-fonts';
import { h } from 'vue';
import DocGitMetaBar from './components/DocGitMetaBar.vue';
import HomeHeroWidget from './components/HomeHeroWidget.vue';
import HomeSurfaceBackdrop from './components/HomeSurfaceBackdrop.vue';
import SidebarToggle from './components/SidebarToggle.vue';
import './custom.css';

const CanvasFlow = defineClientComponent(
  () => import('./components/CanvasFlow.vue'),
);
const showHomeHeroWidget = false;

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('CanvasFlow', CanvasFlow);
    app.use(NolebaseGitChangelogPlugin, {
      hideContributorsHeader: true,
      hideChangelogHeader: true,
      hideChangelogNoChangesText: true,
    });
  },
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'doc-before': () => h(NolebaseBreadcrumbs),
      'doc-footer-before': () => h(DocGitMetaBar),
      'home-hero-before': () => h(HomeSurfaceBackdrop),
      ...(showHomeHeroWidget
        ? {
            'home-hero-image': () => h(HomeHeroWidget),
          }
        : {}),
      'nav-bar-content-after': () => h(SidebarToggle),
    });
  },
};
