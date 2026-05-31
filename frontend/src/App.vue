<template>
  <a-config-provider :theme="themeConfig" :locale="antdLocale">
    <router-view />
  </a-config-provider>
</template>

<script setup>
import enUS from 'ant-design-vue/es/locale/en_US';
import zhCN from 'ant-design-vue/es/locale/zh_CN';
import { theme } from 'ant-design-vue';
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { currentLanguage, isEnglish } from './lib/i18n';
import { useWorkbenchStore } from './store/workbench';

const router = useRouter();
const route = useRoute();
const store = useWorkbenchStore();
const antdLocale = computed(() => (isEnglish.value ? enUS : zhCN));
const appFontFamily = computed(() => (
  isEnglish.value
    ? 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    : 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
));

const themeConfig = computed(() => ({
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#16a34a',
    colorSuccess: '#16a34a',
    colorInfo: '#16a34a',
    colorLink: '#111111',
    colorText: '#111111',
    colorTextSecondary: '#53605a',
    colorTextTertiary: '#6f7a73',
    colorBgBase: '#ffffff',
    colorBgLayout: '#f7faf7',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBorder: '#dfe8df',
    colorBorderSecondary: '#e7eee7',
    borderRadius: 18,
    fontFamily: appFontFamily.value,
  },
  components: {
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#ffffff',
      bodyBg: '#f7faf7',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: '#ecfdf3',
      itemSelectedColor: '#111111',
      itemHoverColor: '#111111',
      itemHoverBg: '#f2f7f2',
      itemBorderRadius: 999,
    },
    Card: {
      borderRadiusLG: 22,
      boxShadowTertiary: '0 16px 40px rgba(17, 17, 17, 0.05)',
    },
    Button: {
      borderRadius: 999,
      controlHeight: 38,
    },
    Table: {
      headerBg: '#f8fbf8',
      rowHoverBg: '#f1f8f2',
    },
    Tabs: {
      itemSelectedColor: '#111111',
      inkBarColor: '#16a34a',
    },
  },
}));

function syncRouteAccess() {
  const requiresAuth = route.meta?.requiresAuth;
  const isPublic = route.meta?.public;
  const redirectPath = typeof route.query?.redirect === 'string' && route.query.redirect.startsWith('/')
    ? route.query.redirect
    : '/dashboard';

  if (!store.state.authReady) {
    return;
  }

  if (requiresAuth && !store.state.auth.loggedIn) {
    router.replace({
      path: '/login',
      query: {
        redirect: route.fullPath,
      },
    });
    return;
  }

  if (isPublic && store.state.auth.loggedIn) {
    router.replace(redirectPath);
  }
}

onMounted(async () => {
  await store.initializeWorkbench({
    lightweight: Boolean(route.meta?.standalone),
  });
  syncRouteAccess();
});

watch(
  () => [route.fullPath, store.state.auth.loggedIn, store.state.authReady],
  () => {
    syncRouteAccess();
  }
);

watch(
  currentLanguage,
  (language) => {
    document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN';
    document.documentElement.dataset.language = language;
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  store.disposeWorkbench();
});
</script>
