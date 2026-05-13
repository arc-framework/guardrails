import { defineClientComponent } from 'vitepress';
import DefaultTheme from 'vitepress/theme-without-fonts';
import { h } from 'vue';
import SidebarToggle from './components/SidebarToggle.vue';
import './custom.css';

const CanvasFlow = defineClientComponent(
  () => import('./components/CanvasFlow.vue'),
);

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('CanvasFlow', CanvasFlow);
  },
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(SidebarToggle),
    });
  },
};
