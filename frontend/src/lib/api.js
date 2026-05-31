const feedCache = new Map();
const FEED_CACHE_TTL_MS = 3000;

async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  let body = options.body;

  if (body != null && !(body instanceof FormData) && typeof body !== 'string') {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }

  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers,
    body,
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      (typeof payload === 'string' ? payload : null) ||
      payload?.error ||
      payload?.message ||
      `请求失败 (${response.status})`;

    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

function buildUserFeedCacheKey(username, limit) {
  return `${String(username || '').trim().toLowerCase()}::${Number(limit || 120)}`;
}

function clearUserFeedCache(username = null) {
  if (!username) {
    feedCache.clear();
    return;
  }

  const normalized = String(username || '').trim().toLowerCase();
  for (const key of feedCache.keys()) {
    if (key.startsWith(`${normalized}::`)) {
      feedCache.delete(key);
    }
  }
}

export const api = {
  getUserStatus() {
    return request('/api/user/status');
  },

  login(credentials) {
    return request('/api/user/login', {
      method: 'POST',
      body: credentials,
    });
  },

  logout() {
    return request('/api/user/logout', {
      method: 'POST',
    });
  },

  previewProfile(username) {
    return request('/api/preview-profile', {
      method: 'POST',
      body: { username },
    });
  },

  startScrape(payload) {
    return request('/api/scrape', {
      method: 'POST',
      body: payload,
    });
  },

  getTasks() {
    return request('/api/tasks');
  },

  pauseTask(taskId) {
    return request(`/api/tasks/${encodeURIComponent(taskId)}/pause`, {
      method: 'POST',
    });
  },

  resumeTask(taskId) {
    return request(`/api/tasks/${encodeURIComponent(taskId)}/resume`, {
      method: 'POST',
    });
  },

  cancelTask(taskId) {
    return request(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: 'POST',
    });
  },

  deleteTask(taskId) {
    return request(`/api/tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    });
  },

  getFiles(username = null, taskId = null) {
    const search = new URLSearchParams();
    if (username) {
      search.set('username', username);
    }
    if (taskId) {
      search.set('task_id', taskId);
    }
    const query = search.toString();
    return request(`/api/files${query ? `?${query}` : ''}`);
  },

  getAdminOverview() {
    return request('/api/admin/overview');
  },

  getAdminUsernames(includeHidden = true) {
    return request(`/api/admin/usernames?include_hidden=${includeHidden ? 'true' : 'false'}`);
  },

  updateAdminUsername(username, payload = {}) {
    return request(`/api/admin/usernames/${encodeURIComponent(username)}`, {
      method: 'POST',
      body: payload,
    });
  },

  getAdminFiles() {
    return request('/api/admin/files');
  },

  getAdminMedia(params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        search.set(key, value);
      }
    });
    const query = search.toString();
    return request(`/api/admin/media${query ? `?${query}` : ''}`);
  },

  updateMediaAnnotation(payload) {
    return request('/api/admin/media/annotation', {
      method: 'POST',
      body: payload,
    }).then((result) => {
      clearUserFeedCache(payload?.username);
      return result;
    });
  },

  getAdminDuplicates(params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        search.set(key, value);
      }
    });
    const query = search.toString();
    return request(`/api/admin/duplicates${query ? `?${query}` : ''}`);
  },

  deleteAdminDuplicate(duplicateId, shardKey = null) {
    const search = new URLSearchParams();
    if (shardKey) {
      search.set('shard_key', shardKey);
    }
    const query = search.toString();
    return request(`/api/admin/duplicates/${encodeURIComponent(duplicateId)}${query ? `?${query}` : ''}`, {
      method: 'DELETE',
    });
  },

  getAdminTaskDetail(taskId) {
    return request(`/api/admin/task-detail/${encodeURIComponent(taskId)}`);
  },

  retryAdminTask(taskId, payload = {}) {
    return request(`/api/admin/tasks/${encodeURIComponent(taskId)}/retry`, {
      method: 'POST',
      body: payload,
    });
  },

  getAdminUserFeed(username, limit = 120, options = {}) {
    const cacheKey = buildUserFeedCacheKey(username, limit);
    const now = Date.now();

    if (!options.force) {
      const cached = feedCache.get(cacheKey);
      if (cached && cached.payload && now - cached.loadedAt < FEED_CACHE_TTL_MS) {
        return Promise.resolve(cached.payload);
      }
      if (cached?.promise) {
        return cached.promise;
      }
    }

    const promise = request(`/api/admin/feed/${encodeURIComponent(username)}?limit=${encodeURIComponent(limit)}`)
      .then((payload) => {
        feedCache.set(cacheKey, {
          payload,
          loadedAt: Date.now(),
          promise: null,
        });
        return payload;
      })
      .catch((error) => {
        feedCache.delete(cacheKey);
        throw error;
      });

    feedCache.set(cacheKey, {
      payload: null,
      loadedAt: now,
      promise,
    });
    return promise;
  },

  updateUserFeedPostContent(username, tweetId, content) {
    return request(`/api/admin/feed/${encodeURIComponent(username)}/posts/${encodeURIComponent(tweetId)}/content`, {
      method: 'POST',
      body: { content },
    }).then((result) => {
      clearUserFeedCache(username);
      return result;
    });
  },

  resetUserFeedPostContent(username, tweetId) {
    return request(`/api/admin/feed/${encodeURIComponent(username)}/posts/${encodeURIComponent(tweetId)}/content/reset`, {
      method: 'POST',
    }).then((result) => {
      clearUserFeedCache(username);
      return result;
    });
  },

  hideUserFeedVideo(username, tweetId, video = {}) {
    return request(`/api/admin/feed/${encodeURIComponent(username)}/posts/${encodeURIComponent(tweetId)}/videos/hide`, {
      method: 'POST',
      body: video,
    }).then((result) => {
      clearUserFeedCache(username);
      return result;
    });
  },

  restoreUserFeedVideos(username, tweetId) {
    return request(`/api/admin/feed/${encodeURIComponent(username)}/posts/${encodeURIComponent(tweetId)}/videos/restore`, {
      method: 'POST',
    }).then((result) => {
      clearUserFeedCache(username);
      return result;
    });
  },

  searchAdmin(query) {
    const keyword = encodeURIComponent(query || '');
    return request(`/api/admin/search?q=${keyword}`);
  },

  getAdminSystem() {
    return request('/api/admin/system');
  },

  getAdminDiff(username) {
    return request(`/api/admin/diff/${encodeURIComponent(username)}`);
  },

  getAdminDatabase() {
    return request('/api/admin/database');
  },

  getAdminDatabaseHealth() {
    return request('/api/admin/database/health');
  },

  getAdminMaintenanceReport() {
    return request('/api/admin/maintenance/report');
  },

  backfillAdminThumbnails(payload = {}) {
    return request('/api/admin/maintenance/backfill-thumbnails', {
      method: 'POST',
      body: payload,
    });
  },

  scanAdminDuplicates(payload = {}) {
    return request('/api/admin/maintenance/scan-duplicates', {
      method: 'POST',
      body: payload,
    });
  },

  backfillAdminTaskLinks() {
    return request('/api/admin/maintenance/backfill-task-links', {
      method: 'POST',
    });
  },

  getAdminDatabaseShardDetail(shardKey) {
    return request(`/api/admin/database/shards/${encodeURIComponent(shardKey)}`);
  },

  migrateLegacyDatabase(payload = {}) {
    return request('/api/admin/database/migrate-legacy', {
      method: 'POST',
      body: payload,
    });
  },

  getAdminConfig() {
    return request('/api/admin/config');
  },

  updateAdminConfig(payload) {
    return request('/api/admin/config', {
      method: 'POST',
      body: payload,
    });
  },

  changeAdminPassword(payload) {
    return request('/api/admin/change-password', {
      method: 'POST',
      body: payload,
    });
  },
};

export function buildDownloadAllUrl(username = null, taskId = null) {
  const search = new URLSearchParams();
  if (username) {
    search.set('username', username);
  }
  if (taskId) {
    search.set('task_id', taskId);
  }
  const query = search.toString();
  return `/api/download-all${query ? `?${query}` : ''}`;
}

export function buildDatabaseBackupUrl(shardKey = null) {
  return shardKey
    ? `/api/admin/database/backup?shard_key=${encodeURIComponent(shardKey)}`
    : '/api/admin/database/backup';
}
