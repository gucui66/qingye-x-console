import { computed, reactive, watch } from 'vue';
import { io } from 'socket.io-client';

import { api } from '../lib/api';
import { sortTasks, groupTasksForDisplay, pickFocusTask, shouldShowTaskScreenshot } from '../lib/tasks';
import {
  createAdminOverviewState,
  createDatabaseState,
  createLibraryState,
  createMediaCenterState,
  createSearchState,
  createWorkbenchState,
} from './workbench-state';

const state = reactive(createWorkbenchState());
const USERNAME_DIRECTORY_STORAGE_KEY = 'qingye:username-directory-cache';
const USERNAME_DIRECTORY_STORAGE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const TASK_POLL_INTERVAL_MS = 10000;
const TASK_POLL_HIDDEN_INTERVAL_MS = 45000;

let socket = null;
let tasksPollTimer = null;
let screenshotTimer = null;
let visibilityHandlerBound = false;
let tasksRequest = null;
let adminOverviewRequest = null;
let usernameDirectoryRequest = null;
let systemRequest = null;
let databaseRequest = null;
let adminOverviewLoadedAt = 0;
let usernameDirectoryLoadedAt = 0;
let usernameDirectoryHydrated = false;
let systemLoadedAt = 0;
let databaseLoadedAt = 0;
let mediaRequest = null;
let mediaRequestKey = '';
let taskDetailRequest = null;
let taskDetailRequestKey = '';
const libraryRequests = new Map();
const searchRequests = new Map();
let libraryRequestToken = 0;
let searchRequestToken = 0;
let mediaRequestToken = 0;
let taskDetailRequestToken = 0;

function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', {
    hour12: false,
  });
}

function pushLog(message, level = 'info', timestamp = null) {
  state.logs.push({
    time: timestamp || nowTime(),
    message,
    level,
  });

  if (state.logs.length > 600) {
    state.logs.splice(0, state.logs.length - 600);
  }
}

function clearLogs() {
  state.logs = [
    {
      time: '--:--:--',
      message: '日志已清空',
      level: 'info',
    },
  ];
}

function readUsernameDirectoryCache() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null;
  }

  try {
    const payload = JSON.parse(window.localStorage.getItem(USERNAME_DIRECTORY_STORAGE_KEY) || 'null');
    if (!payload || !Array.isArray(payload.items)) {
      return null;
    }
    if (Date.now() - Number(payload.cachedAt || 0) > USERNAME_DIRECTORY_STORAGE_TTL_MS) {
      return null;
    }
    return payload;
  } catch (error) {
    return null;
  }
}

function writeUsernameDirectoryCache(items = []) {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    window.localStorage.setItem(USERNAME_DIRECTORY_STORAGE_KEY, JSON.stringify({
      cachedAt: Date.now(),
      items,
    }));
  } catch (error) {
    // 本地缓存只是首屏加速，写入失败时不影响真实接口数据。
  }
}

function hydrateUsernameDirectoryCache() {
  if (usernameDirectoryHydrated || state.usernameDirectory.items.length) {
    return false;
  }

  usernameDirectoryHydrated = true;
  const cached = readUsernameDirectoryCache();
  if (!cached) {
    return false;
  }

  state.usernameDirectory.items = sortUsernameDirectoryItems(cached.items);
  usernameDirectoryLoadedAt = Number(cached.cachedAt || Date.now());
  return true;
}

function compareUsernameDirectoryItems(a, b) {
  const hiddenDelta = Number(Boolean(a.hidden)) - Number(Boolean(b.hidden));
  if (hiddenDelta !== 0) {
    return hiddenDelta;
  }

  const crawledDelta = Number(b.last_crawled_ts || 0) - Number(a.last_crawled_ts || 0);
  if (crawledDelta !== 0) {
    return crawledDelta;
  }

  return String(a.display_name || a.username || '').localeCompare(String(b.display_name || b.username || ''), 'zh-CN');
}

function sortUsernameDirectoryItems(items = []) {
  return [...items].sort(compareUsernameDirectoryItems);
}

function syncProgressFromTask(task) {
  if (!task) {
    state.progress.text = '准备中...';
    state.progress.step = '';
    state.progress.percentage = 0;
    return;
  }

  const current = task.scraped_count || 0;
  const total = task.max_tweets || task.total || 0;
  state.progress.text = total ? `${current} / ${total}` : `${current} / ∞`;
  state.progress.step = `当前任务: @${task.username} (${task.status})`;
  state.progress.percentage = task.progress || 0;
}

function connectSocket() {
  if (socket) {
    return;
  }

  socket = io();
  socket.on('connected', () => {
    pushLog('已连接到服务器', 'success');
  });
  socket.on('log', (payload) => {
    pushLog(payload.message, payload.level, payload.timestamp);
  });
  socket.on('progress', (payload) => {
    state.progress.percentage = payload.percentage || 0;
    if (payload.current && payload.total) {
      state.progress.text = `${payload.current} / ${payload.total}`;
    }
    if (payload.step) {
      state.progress.step = payload.step;
    }
  });
}

function disconnectSocket() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

function stopTaskPolling() {
  if (tasksPollTimer) {
    window.clearInterval(tasksPollTimer);
    tasksPollTimer = null;
  }
}

function startTaskPolling() {
  stopTaskPolling();
  // 任务进度主要靠 Socket 推送；轮询只做兜底，避免多个后台标签页同时高频请求。
  const intervalMs = document.hidden ? TASK_POLL_HIDDEN_INTERVAL_MS : TASK_POLL_INTERVAL_MS;
  tasksPollTimer = window.setInterval(() => {
    loadTasks();
  }, intervalMs);
}

function refreshScreenshot(taskId) {
  if (!taskId) {
    return;
  }

  const probeUrl = `/static/screenshots/${encodeURIComponent(taskId)}/latest.png?t=${Date.now()}`;
  const probeImage = new Image();

  probeImage.onload = () => {
    state.screenshot.url = probeUrl;
    state.screenshot.unavailable = false;
  };

  probeImage.onerror = () => {
    state.screenshot.url = '';
    state.screenshot.unavailable = true;
  };

  probeImage.src = probeUrl;
}

function stopScreenshotRefresh() {
  if (screenshotTimer) {
    window.clearInterval(screenshotTimer);
    screenshotTimer = null;
  }
  state.screenshot.taskId = null;
  state.screenshot.url = '';
  state.screenshot.unavailable = false;
}

function startScreenshotRefresh(taskId) {
  if (!taskId) {
    stopScreenshotRefresh();
    return;
  }

  if (state.screenshot.taskId === taskId && screenshotTimer) {
    refreshScreenshot(taskId);
    return;
  }

  stopScreenshotRefresh();
  state.screenshot.taskId = taskId;
  refreshScreenshot(taskId);
  const intervalMs = document.hidden ? 10000 : 3000;
  screenshotTimer = window.setInterval(() => {
    refreshScreenshot(taskId);
  }, intervalMs);
}

function handleVisibilityChange() {
  if (tasksPollTimer) {
    startTaskPolling();
  }

  if (state.screenshot.taskId) {
    startScreenshotRefresh(state.screenshot.taskId);
  }
}

const sortedTasks = computed(() => sortTasks(state.tasks));
const displayTasks = computed(() => groupTasksForDisplay(sortedTasks.value));
const focusTask = computed(() => pickFocusTask(displayTasks.value));
const latestCompletedTask = computed(() => {
  return sortedTasks.value.find((task) => task.status === 'completed' && task.results) || null;
});
const usernameDirectoryItems = computed(() => state.usernameDirectory.items || []);
const usernameOptions = computed(() => {
  return usernameDirectoryItems.value
    .filter((item) => !item.hidden)
    .map((item) => item.username);
});

watch(
  focusTask,
  (task) => {
    syncProgressFromTask(task);

    if (shouldShowTaskScreenshot(task)) {
      startScreenshotRefresh(task.task_id);
      return;
    }

    stopScreenshotRefresh();
  },
  { immediate: true }
);

async function refreshSession() {
  state.loading.auth = true;
  try {
    const payload = await api.getUserStatus();
    state.auth.loggedIn = Boolean(payload.logged_in);
    state.auth.username = payload.username || '';
    state.auth.isAdmin = Boolean(payload.is_admin);
  } catch (error) {
    state.auth.loggedIn = false;
    state.auth.username = '';
    state.auth.isAdmin = false;
  } finally {
    state.authReady = true;
    state.loading.auth = false;
  }
}

async function login(credentials) {
  const payload = await api.login(credentials);
  state.auth.loggedIn = true;
  state.auth.username = credentials.username;
  state.auth.isAdmin = payload.role === 'admin';
  pushLog('✅ 登录成功', 'success');
  Promise.allSettled([loadTasks(), loadAdminOverview(), loadUsernameDirectory(), loadSystem()]);
  return payload;
}

async function logout() {
  await api.logout();
  state.auth.loggedIn = false;
  state.auth.isAdmin = false;
  state.auth.username = '';
  state.adminOverview = createAdminOverviewState();
  state.adminFiles = {};
  state.database = createDatabaseState();
  state.databaseHealth = createDatabaseState();
  state.databaseDetail = null;
  state.config = null;
  state.library = createLibraryState();
  state.mediaCenter = createMediaCenterState();
  state.usernameDirectory = { items: [] };
  state.system = null;
  state.search = createSearchState();
  state.taskDetail = null;
  pushLog('✅ 已退出登录', 'info');
}

async function loadTasks() {
  if (state.authReady && !state.auth.loggedIn) {
    state.tasks = [];
    return state.tasks;
  }

  if (tasksRequest) {
    return tasksRequest;
  }

  state.loading.tasks = true;
  tasksRequest = (async () => {
    try {
      const payload = await api.getTasks();
      state.tasks = Array.isArray(payload) ? payload : [];
      return state.tasks;
    } finally {
      state.loading.tasks = false;
      tasksRequest = null;
    }
  })();

  return tasksRequest;
}

async function startScrape(payload) {
  const result = await api.startScrape(payload);

  if (result.existing_task) {
    pushLog(`ℹ️ ${result.message || '该用户已有进行中的任务'}`, 'info');
  } else {
    pushLog(`✅ 任务已添加到队列: ${result.task_id || ''}`, 'success');
    pushLog('任务将自动执行，你可以继续添加其他任务', 'info');
  }

  await loadTasks();
  await loadUsernameDirectory({ silent: true, force: true });
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function createTask(payload) {
  return startScrape(payload);
}

async function pauseTask(taskId) {
  const result = await api.pauseTask(taskId);
  pushLog(`⏸️ 任务已暂停: ${taskId}`, 'warning');
  await loadTasks();
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function resumeTask(taskId) {
  const result = await api.resumeTask(taskId);
  pushLog(`▶️ 任务已继续: ${taskId}`, 'success');
  await loadTasks();
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function cancelTask(taskId) {
  const result = await api.cancelTask(taskId);
  pushLog(`❌ 任务已取消: ${taskId}`, 'error');
  await loadTasks();
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function deleteTask(taskId) {
  const result = await api.deleteTask(taskId);
  pushLog(`🗑️ 任务记录已删除: ${taskId}`, 'info');
  await loadTasks();
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function loadAdminOverview(options = {}) {
  if (!state.auth.isAdmin) {
    return null;
  }

  if (!options.force && state.adminOverview.summary && Date.now() - adminOverviewLoadedAt < 4000) {
    return state.adminOverview;
  }

  if (adminOverviewRequest) {
    return adminOverviewRequest;
  }

  if (!options.silent) {
    state.loading.overview = true;
  }

  adminOverviewRequest = (async () => {
    try {
      const payload = await api.getAdminOverview();
      state.adminOverview = payload;
      adminOverviewLoadedAt = Date.now();
      return payload;
    } finally {
      state.loading.overview = false;
      adminOverviewRequest = null;
    }
  })();

  return adminOverviewRequest;
}

async function loadUsernameDirectory(options = {}) {
  if (!state.auth.isAdmin) {
    return { items: [] };
  }

  const hydratedFromCache = hydrateUsernameDirectoryCache();

  if (!options.force && state.usernameDirectory.items.length && Date.now() - usernameDirectoryLoadedAt < 15000) {
    return state.usernameDirectory;
  }

  if (usernameDirectoryRequest) {
    return usernameDirectoryRequest;
  }

  if (options.allowStale && state.usernameDirectory.items.length && !options.force) {
    usernameDirectoryRequest = (async () => {
      try {
        state.loading.usernameDirectory = true;
        const payload = await api.getAdminUsernames(true);
        state.usernameDirectory.items = sortUsernameDirectoryItems(payload.items || []);
        usernameDirectoryLoadedAt = Date.now();
        writeUsernameDirectoryCache(state.usernameDirectory.items);
        return state.usernameDirectory;
      } catch (error) {
        pushLog(`用户名目录后台刷新失败: ${error.message || error}`, 'warning');
        return state.usernameDirectory;
      } finally {
        state.loading.usernameDirectory = false;
        usernameDirectoryRequest = null;
      }
    })();

    return state.usernameDirectory;
  }

  if (!options.silent || !hydratedFromCache) {
    state.loading.usernameDirectory = true;
  }

  usernameDirectoryRequest = (async () => {
    try {
      const payload = await api.getAdminUsernames(true);
      state.usernameDirectory.items = sortUsernameDirectoryItems(payload.items || []);
      usernameDirectoryLoadedAt = Date.now();
      writeUsernameDirectoryCache(state.usernameDirectory.items);
      return state.usernameDirectory;
    } finally {
      state.loading.usernameDirectory = false;
      usernameDirectoryRequest = null;
    }
  })();

  return usernameDirectoryRequest;
}

async function loadAdminFiles() {
  if (!state.auth.isAdmin) {
    return {};
  }

  state.loading.adminFiles = true;
  try {
    const payload = await api.getAdminFiles();
    state.adminFiles = payload || {};
    return state.adminFiles;
  } finally {
    state.loading.adminFiles = false;
  }
}

async function loadLibrary(username = null, taskId = null) {
  const requestKey = JSON.stringify({
    username: username || null,
    taskId: taskId || null,
  });
  if (libraryRequests.has(requestKey)) {
    return libraryRequests.get(requestKey);
  }

  state.loading.library = true;
  const token = ++libraryRequestToken;
  const request = (async () => {
    try {
      const payload = await api.getFiles(username, taskId);
      if (token === libraryRequestToken) {
        state.library.username = username;
        state.library.taskId = taskId;
        state.library.files = {
          videos: payload.videos || [],
          photos: payload.photos || [],
          documents: payload.documents || [],
        };
      }
      return state.library.files;
    } finally {
      if (token === libraryRequestToken) {
        state.loading.library = false;
      }
      libraryRequests.delete(requestKey);
    }
  })();

  libraryRequests.set(requestKey, request);
  return request;
}

async function loadMediaCenter(filters = {}) {
  if (!state.auth.isAdmin) {
    return null;
  }

  state.mediaCenter.filters = {
    ...state.mediaCenter.filters,
    ...filters,
  };

  const requestKey = JSON.stringify(state.mediaCenter.filters);
  if (mediaRequest && mediaRequestKey === requestKey) {
    return mediaRequest;
  }

  state.loading.media = true;
  mediaRequestKey = requestKey;
  const token = ++mediaRequestToken;
  mediaRequest = (async () => {
    try {
      const payload = await api.getAdminMedia(state.mediaCenter.filters);
      if (mediaRequestKey === requestKey && token === mediaRequestToken) {
        state.mediaCenter.summary = payload.summary || null;
        state.mediaCenter.items = payload.items || [];
      }
      return payload;
    } finally {
      if (mediaRequestKey === requestKey && token === mediaRequestToken) {
        state.loading.media = false;
        mediaRequest = null;
      }
    }
  })();

  return mediaRequest;
}

async function updateMediaAnnotation(payload, options = {}) {
  const result = await api.updateMediaAnnotation(payload);
  const item = result?.item;
  if (!item) {
    return result;
  }

  function replaceItemInList(list) {
    return (list || []).map((entry) => {
      const sameShard = entry.shard_key || item.shard_key
        ? entry.shard_key === item.shard_key
        : true;
      if (
        entry.storage_backend === 'sqlite'
        && entry.id === item.id
        && entry.media_type === item.media_type
        && entry.username === item.username
        && sameShard
      ) {
        return item;
      }
      return entry;
    });
  }

  state.mediaCenter.items = replaceItemInList(state.mediaCenter.items);
  state.library.files = {
    videos: replaceItemInList(state.library.files.videos),
    photos: replaceItemInList(state.library.files.photos),
    documents: state.library.files.documents,
  };
  if (!options.skipOverviewRefresh) {
    await loadAdminOverview({ silent: true, force: true });
  }
  return result;
}

async function updateUsernameDirectoryEntry(username, payload = {}) {
  const result = await api.updateAdminUsername(username, payload);
  const item = result?.item;
  if (!item) {
    return result;
  }

  const nextItems = [...(state.usernameDirectory.items || [])];
  const index = nextItems.findIndex((entry) => entry.normalized_username === item.normalized_username);
  if (index >= 0) {
    nextItems.splice(index, 1, item);
  } else {
    nextItems.push(item);
  }
  nextItems.sort(compareUsernameDirectoryItems);
  state.usernameDirectory.items = nextItems;
  usernameDirectoryLoadedAt = Date.now();
  writeUsernameDirectoryCache(nextItems);
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function loadTaskDetail(taskId) {
  if (!taskId) {
    taskDetailRequestToken += 1;
    taskDetailRequestKey = '';
    taskDetailRequest = null;
    state.taskDetail = null;
    return null;
  }

  if (taskDetailRequest && taskDetailRequestKey === taskId) {
    return taskDetailRequest;
  }

  state.loading.taskDetail = true;
  taskDetailRequestKey = taskId;
  const token = ++taskDetailRequestToken;
  taskDetailRequest = (async () => {
    try {
      const payload = await api.getAdminTaskDetail(taskId);
      if (taskDetailRequestKey === taskId && token === taskDetailRequestToken) {
        state.taskDetail = payload;
      }
      return payload;
    } finally {
      if (taskDetailRequestKey === taskId && token === taskDetailRequestToken) {
        state.loading.taskDetail = false;
        taskDetailRequest = null;
      }
    }
  })();

  return taskDetailRequest;
}

async function loadSearch(query) {
  if (!state.auth.isAdmin) {
    return null;
  }

  if (!String(query || '').trim()) {
    searchRequestToken += 1;
    state.search.query = '';
    state.search.results = {
      media: [],
      tasks: [],
      history: [],
      users: [],
    };
    return state.search.results;
  }

  const requestKey = String(query || '').trim();
  if (searchRequests.has(requestKey)) {
    return searchRequests.get(requestKey);
  }

  state.loading.search = true;
  const token = ++searchRequestToken;
  const request = (async () => {
    try {
      const payload = await api.searchAdmin(query);
      if (token === searchRequestToken) {
        state.search.query = query;
        state.search.results = payload;
      }
      return payload;
    } finally {
      if (token === searchRequestToken) {
        state.loading.search = false;
      }
      searchRequests.delete(requestKey);
    }
  })();

  searchRequests.set(requestKey, request);
  return request;
}

async function loadSystem(options = {}) {
  if (!state.auth.isAdmin) {
    return null;
  }

  if (!options.force && state.system && Date.now() - systemLoadedAt < 5000) {
    return state.system;
  }

  if (systemRequest) {
    return systemRequest;
  }

  state.loading.system = true;
  systemRequest = (async () => {
    try {
      const payload = await api.getAdminSystem();
      state.system = payload;
      systemLoadedAt = Date.now();
      return payload;
    } finally {
      state.loading.system = false;
      systemRequest = null;
    }
  })();

  return systemRequest;
}

async function loadDiff(username) {
  if (!state.auth.isAdmin || !username) {
    return null;
  }
  return api.getAdminDiff(username);
}

async function loadDatabase(options = {}) {
  if (!state.auth.isAdmin) {
    return null;
  }

  if (!options.force && state.database.summary && Date.now() - databaseLoadedAt < 5000) {
    return state.database;
  }

  if (databaseRequest) {
    return databaseRequest;
  }

  state.loading.database = true;
  databaseRequest = (async () => {
    try {
      const payload = await api.getAdminDatabase();
      state.database = payload;
      databaseLoadedAt = Date.now();
      return payload;
    } finally {
      state.loading.database = false;
      databaseRequest = null;
    }
  })();

  return databaseRequest;
}

async function loadDatabaseHealth() {
  if (!state.auth.isAdmin) {
    return null;
  }

  state.loading.databaseHealth = true;
  try {
    const payload = await api.getAdminDatabaseHealth();
    state.databaseHealth = payload;
    return payload;
  } finally {
    state.loading.databaseHealth = false;
  }
}

async function loadDatabaseDetail(username) {
  if (!state.auth.isAdmin || !username) {
    state.databaseDetail = null;
    return null;
  }

  state.loading.databaseDetail = true;
  try {
    const payload = await api.getAdminDatabaseShardDetail(username);
    state.databaseDetail = payload;
    return payload;
  } finally {
    state.loading.databaseDetail = false;
  }
}

async function migrateLegacyDatabase(shardKey = null) {
  if (!state.auth.isAdmin) {
    return null;
  }

  state.loading.databaseMigrate = true;
  try {
    const payload = await api.migrateLegacyDatabase(shardKey ? { shard_key: shardKey } : {});
    pushLog(`🗄️ ${payload.message || '旧版账号库迁移完成'}`, 'success');
    await Promise.allSettled([
      loadDatabase({ force: true }),
      loadDatabaseHealth(),
      loadAdminOverview({ silent: true, force: true }),
      loadLibrary(state.library.username, state.library.taskId),
    ]);
    return payload;
  } finally {
    state.loading.databaseMigrate = false;
  }
}

async function loadConfig() {
  if (!state.auth.isAdmin) {
    return null;
  }

  state.loading.config = true;
  try {
    const payload = await api.getAdminConfig();
    state.config = payload;
    return payload;
  } finally {
    state.loading.config = false;
  }
}

async function saveConfig(payload) {
  const result = await api.updateAdminConfig(payload);
  pushLog(`⚙️ ${result.message || '配置已更新'}`, 'success');
  await loadConfig();
  await loadAdminOverview({ silent: true, force: true });
  return result;
}

async function changePassword(payload) {
  const result = await api.changeAdminPassword(payload);
  pushLog(`🔐 ${result.message || '密码已修改'}`, 'success');
  return result;
}

async function initializeWorkbench(options = {}) {
  const lightweight = Boolean(options.lightweight);
  if (!state.initialized) {
    if (!visibilityHandlerBound) {
      document.addEventListener('visibilitychange', handleVisibilityChange);
      visibilityHandlerBound = true;
    }
    state.initialized = true;
  }

  if (!lightweight) {
    connectSocket();
    startTaskPolling();
  }

  await refreshSession();
  if (state.auth.loggedIn && !lightweight) {
    await loadTasks();
  }
  if (state.auth.isAdmin) {
    await Promise.allSettled([
      loadUsernameDirectory({ silent: true }),
    ]);
  }
}

function disposeWorkbench() {
  stopTaskPolling();
  stopScreenshotRefresh();
  disconnectSocket();
  if (visibilityHandlerBound) {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    visibilityHandlerBound = false;
  }
  state.initialized = false;
}

export function useWorkbenchStore() {
  return {
    state,
    sortedTasks,
    displayTasks,
    focusTask,
    latestCompletedTask,
    usernameDirectoryItems,
    usernameOptions,
    initializeWorkbench,
    disposeWorkbench,
    refreshSession,
    login,
    logout,
    loadTasks,
    loadAdminOverview,
    loadUsernameDirectory,
    loadAdminFiles,
    loadLibrary,
    loadMediaCenter,
    updateMediaAnnotation,
    updateUsernameDirectoryEntry,
    loadTaskDetail,
    loadSearch,
    loadSystem,
    loadDiff,
    loadDatabase,
    loadDatabaseHealth,
    loadDatabaseDetail,
    migrateLegacyDatabase,
    loadConfig,
    saveConfig,
    changePassword,
    createTask,
    startScrape,
    startScreenshotRefresh,
    stopScreenshotRefresh,
    pauseTask,
    resumeTask,
    cancelTask,
    deleteTask,
    pushLog,
    clearLogs,
  };
}
