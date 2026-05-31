<template>
  <a-layout class="app-shell">
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :width="248"
      theme="light"
      class="app-sider"
    >
      <div class="sider-brand">
        <div class="brand-logo">X</div>
        <div v-if="!collapsed" class="brand-copy">
          <div class="brand-title">{{ t('app.name') }}</div>
          <div class="brand-subtitle">{{ t('app.subtitle') }}</div>
        </div>
      </div>

      <a-menu
        :selected-keys="[selectedKey]"
        mode="inline"
        class="app-menu"
        @click="handleMenuClick"
      >
        <a-menu-item key="new-task">
          <plus-circle-outlined />
          <span class="menu-label">{{ t('nav.newTask') }}</span>
        </a-menu-item>
        <a-menu-item key="tasks">
          <deployment-unit-outlined />
          <span class="menu-label">{{ t('nav.tasks') }}</span>
        </a-menu-item>
        <a-menu-item key="dashboard">
          <dashboard-outlined />
          <span class="menu-label">{{ t('nav.dashboard') }}</span>
        </a-menu-item>
        <a-menu-item key="search">
          <search-outlined />
          <span class="menu-label">{{ t('nav.search') }}</span>
        </a-menu-item>
        <a-menu-item key="library">
          <video-camera-outlined />
          <span class="menu-label">{{ t('nav.library') }}</span>
        </a-menu-item>
        <a-menu-item key="user-feed">
          <user-outlined />
          <span class="menu-label">{{ t('nav.userFeed') }}</span>
        </a-menu-item>
        <a-menu-item key="home">
          <dashboard-outlined />
          <span class="menu-label">{{ t('nav.home') }}</span>
        </a-menu-item>
        <a-menu-item key="database">
          <database-outlined />
          <span class="menu-label">{{ t('nav.database') }}</span>
        </a-menu-item>
        <a-menu-item key="monitor">
          <line-chart-outlined />
          <span class="menu-label">{{ t('nav.monitor') }}</span>
        </a-menu-item>
        <a-menu-item key="settings">
          <setting-outlined />
          <span class="menu-label">{{ t('nav.settings') }}</span>
        </a-menu-item>
        <a-menu-item key="deployment">
          <cloud-server-outlined />
          <span class="menu-label">{{ t('nav.deployment') }}</span>
        </a-menu-item>
      </a-menu>

      <div v-if="!collapsed" class="sider-footer-card">
        <div class="sider-footer-title">{{ t('layout.currentStatus') }}</div>
        <div class="sider-footer-line">
          <span class="sider-footer-label">{{ t('layout.loginUser') }}</span>
          <strong class="sider-footer-value" :title="store.state.auth.username || t('common.notLoggedIn')">
            {{ store.state.auth.username || t('common.notLoggedIn') }}
          </strong>
        </div>
        <div class="sider-footer-line">
          <span class="sider-footer-label">{{ t('layout.activeTasks') }}</span>
          <strong class="sider-footer-value">{{ activeTaskCount }}</strong>
        </div>
        <div class="sider-footer-line">
          <span class="sider-footer-label">{{ t('layout.focusTask') }}</span>
          <strong class="sider-footer-value" :title="focusTaskText">
            {{ focusTaskText }}
          </strong>
        </div>
        <div class="sider-footer-line">
          <span class="sider-footer-label">{{ t('layout.latestScreenshot') }}</span>
          <strong class="sider-footer-value">{{ store.state.screenshot.url ? t('common.online') : t('common.idle') }}</strong>
        </div>
      </div>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="app-header">
        <div class="header-left">
          <div class="header-page-copy">
            <div class="header-page-title" :title="pageTitle">{{ pageTitle }}</div>
            <div class="header-page-subtitle" :title="pageSubtitle">{{ pageSubtitle }}</div>
          </div>
        </div>

        <div class="header-right">
          <a-input-search
            class="header-search"
            :placeholder="t('layout.searchPlaceholder')"
            allow-clear
            @search="handleSearch"
          />
          <a-badge :count="activeTaskCount" :number-style="{ backgroundColor: '#111111' }">
            <a-tag color="green">{{ t('layout.taskQueue') }}</a-tag>
          </a-badge>
          <a-button
            v-if="store.focusTask.value"
            class="header-focus-chip"
            @click="goToFocusTask"
            :title="focusTaskText"
          >
            <span class="header-focus-chip-label">{{ t('layout.currentTask') }}</span>
            <span class="header-focus-chip-value">{{ focusTaskText }}</span>
          </a-button>
          <a-dropdown>
            <a-button>
              {{ store.state.auth.username || 'admin' }}
              <down-outlined />
            </a-button>
            <template #overlay>
              <a-menu>
                <a-menu-item key="logout" @click="handleLogout">
                  <logout-outlined />
                  {{ t('layout.logout') }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import {
  CloudServerOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  DownOutlined,
  LineChartOutlined,
  LogoutOutlined,
  PlusCircleOutlined,
  SearchOutlined,
  SettingOutlined,
  UserOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons-vue';
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { t } from '../lib/i18n';
import { useWorkbenchStore } from '../store/workbench';

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();
const collapsed = ref(false);

const selectedKey = computed(() => {
  if (route.name === 'task-detail') {
    return 'tasks';
  }
  if (route.name === 'user-post' || route.name === 'user-video') {
    return 'user-feed';
  }
  return route.name || 'dashboard';
});
const focusTaskText = computed(() => {
  const task = store.focusTask.value;
  if (!task) {
    return t('layout.noTask');
  }

  return `@${task.username} · ${task.task_id}`;
});
const activeTaskCount = computed(() => {
  return store.displayTasks.value.filter((item) =>
    ['running', 'pending', 'paused', 'user_paused'].includes(item.status)
  ).length;
});

const titleMap = {
  home: ['page.home.title', 'page.home.subtitle'],
  dashboard: ['page.dashboard.title', 'page.dashboard.subtitle'],
  'new-task': ['page.newTask.title', 'page.newTask.subtitle'],
  tasks: ['page.tasks.title', 'page.tasks.subtitle'],
  'task-detail': ['page.taskDetail.title', 'page.taskDetail.subtitle'],
  'user-feed': ['page.userFeed.title', 'page.userFeed.subtitle'],
  'user-post': ['page.userPost.title', 'page.userPost.subtitle'],
  'user-video': ['page.userVideo.title', 'page.userVideo.subtitle'],
  search: ['page.search.title', 'page.search.subtitle'],
  library: ['page.library.title', 'page.library.subtitle'],
  database: ['page.database.title', 'page.database.subtitle'],
  monitor: ['page.monitor.title', 'page.monitor.subtitle'],
  settings: ['page.settings.title', 'page.settings.subtitle'],
  deployment: ['page.deployment.title', 'page.deployment.subtitle'],
};

const pageTitle = computed(() => t(titleMap[selectedKey.value]?.[0] || 'app.name'));
const pageSubtitle = computed(() => {
  const key = titleMap[selectedKey.value]?.[1];
  return key ? t(key) : '';
});

function handleMenuClick({ key }) {
  if (key === 'user-feed') {
    const href = router.resolve({
      name: 'user-feed-standalone',
      params: {},
    }).href;
    window.open(href, '_blank', 'noopener,noreferrer');
    return;
  }
  router.push({ name: key });
}

function handleSearch(value) {
  const keyword = String(value || '').trim();
  router.push({
    name: 'search',
    query: keyword ? { q: keyword } : {},
  });
}

function goToFocusTask() {
  if (!store.focusTask.value?.task_id) {
    return;
  }

  router.push({
    name: 'task-detail',
    params: { taskId: store.focusTask.value.task_id },
  });
}

async function handleLogout() {
  await store.logout();
  router.replace('/login');
}
</script>
