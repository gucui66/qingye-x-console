<template>
  <a-spin :spinning="loading">
    <section v-if="isStandaloneMode" class="post-standalone-topbar">
      <div class="post-standalone-topbar-main">
        <a-button type="text" @click="goBackOrDashboard">← 返回</a-button>
        <div class="post-standalone-copy">
          <div class="post-standalone-title">{{ resolvedUsername ? `@${resolvedUsername}` : '贴文详情' }}</div>
          <div class="post-standalone-subtitle">
            {{ currentItem ? `当前媒体 ${mediaCount(currentItem)} 个` : '独立贴文页' }} · {{ currentItem?.is_reply ? '回复贴文' : '主贴文' }}
          </div>
        </div>
        <a-space wrap>
          <a-button size="small" @click="goBackToFeed" :disabled="!resolvedUsername">用户主页</a-button>
          <a-button size="small" type="primary" @click="openLibrary" :disabled="!resolvedUsername">资料库</a-button>
        </a-space>
      </div>
    </section>

    <div class="post-page-shell">
      <aside class="post-page-left">
        <section class="post-side-card">
          <div class="post-side-title">切换用户</div>
          <a-select
            v-model:value="selectedUsername"
            style="width: 100%"
            placeholder="选择一个用户主页"
            :options="usernameSelectOptions"
            show-search
            :filter-option="filterUsernameOption"
            @change="handleUsernameChange"
          />
          <div class="post-side-help">切换用户后会返回该用户的主页时间流，避免旧贴文 ID 与新用户不匹配。</div>
        </section>

        <section class="post-side-card post-author-card">
          <div class="post-author-avatar">{{ avatarLetter }}</div>
          <div class="post-author-name">{{ resolvedUsername ? `@${resolvedUsername}` : '贴文详情' }}</div>
          <div class="post-author-subtitle">{{ summary.tweets || 0 }} 条贴文 · {{ summary.videos || 0 }} 个视频 · {{ summary.photos || 0 }} 张图片</div>

          <div class="post-author-meta">
            <div class="post-author-row">
              <span>来源文件</span>
              <strong :title="sourceFile || '本地媒体兜底'">{{ sourceFile || '本地媒体兜底' }}</strong>
            </div>
            <div class="post-author-row">
              <span>最近抓取</span>
              <strong>{{ latestTimeLabel }}</strong>
            </div>
          </div>

          <div class="post-author-actions">
            <a-button block @click="goBackToFeed" :disabled="!resolvedUsername">返回用户主页</a-button>
            <a-button type="primary" block @click="openLibrary" :disabled="!resolvedUsername">打开资料库</a-button>
          </div>
        </section>
      </aside>

      <main class="post-page-main">
        <section class="post-hero-card">
          <div class="post-hero-top">
            <div>
              <div class="post-hero-title">单条贴文详情</div>
              <div class="post-hero-subtitle">从用户主页进入的独立详情页，更接近 X 官方的“贴文展开”体验。</div>
            </div>
            <a-space wrap>
              <a-button @click="goBackToFeed" :disabled="!resolvedUsername">返回主页</a-button>
              <a-button v-if="currentItem?.url" type="primary" @click="openOriginalTweet(currentItem.url)">
                打开原贴文
              </a-button>
            </a-space>
          </div>

          <div class="post-hero-strip">
            <div class="post-hero-pill">
              <span>当前贴文 ID</span>
              <strong :title="tweetId">{{ tweetId || '未指定' }}</strong>
            </div>
            <div class="post-hero-pill">
              <span>本地媒体</span>
              <strong>{{ currentItem ? mediaCount(currentItem) : 0 }}</strong>
            </div>
            <div class="post-hero-pill">
              <span>是否回复</span>
              <strong>{{ currentItem?.is_reply ? '是' : '否' }}</strong>
            </div>
          </div>
        </section>

        <section v-if="currentItem" class="post-detail-card">
          <div class="post-detail-head">
            <div class="post-detail-avatar">{{ avatarLetter }}</div>
            <div class="post-detail-copy">
              <div class="post-detail-name">{{ `@${currentItem.author_username || currentItem.username}` }}</div>
              <div class="post-detail-meta">
                <span>{{ formatDateTime(currentItem.date, '时间未知') }}</span>
                <span>{{ currentItem.tab_source || '推文流' }}</span>
                <span v-if="currentItem.is_reply">回复贴文</span>
              </div>
            </div>
          </div>

          <div class="post-detail-content">
            {{ currentItem.content || '这条内容没有抓到正文，当前以媒体为主展示。' }}
          </div>

          <div v-if="currentItem.reply_context" class="post-detail-reply">
            回复上下文：{{ currentItem.reply_context }}
          </div>

          <div v-if="currentItem.local_videos?.length" class="post-video-grid">
            <div
              v-for="(video, index) in currentItem.local_videos"
              :key="video.path"
              class="post-video-tile"
            >
              <button
                v-if="!isVideoLoaded(currentItem, index)"
                type="button"
                class="post-video-placeholder"
                :class="{ 'post-video-placeholder-has-thumb': video.thumbnail_src }"
                :style="videoPlaceholderStyle(video)"
                @click="loadVideo(currentItem, index)"
              >
                <span v-if="video.thumbnail_src" class="post-video-thumb-shade"></span>
                <span class="post-video-placeholder-icon">▶</span>
                <span class="post-video-placeholder-copy">点击加载视频预览</span>
                <span class="post-video-placeholder-subcopy">独立详情页也不会自动抢占带宽</span>
              </button>
              <video
                v-else
                class="post-video"
                controls
                preload="metadata"
                playsinline
                :poster="video.thumbnail_src || undefined"
                :src="encodeOutputPath(video.path)"
              ></video>
              <div class="post-video-tile-actions">
                <a-button size="small" type="text" @click="openVideoPage(currentItem, index)">
                  独立播放
                </a-button>
              </div>
            </div>
          </div>

          <div v-if="currentPhotos.length" class="post-photo-grid">
            <button
              v-for="(photo, index) in currentPhotos"
              :key="photo.key"
              type="button"
              class="post-photo-button"
              @click="openImagePreview(currentPhotos, index)"
            >
              <img class="post-photo" :src="photo.src" :alt="photo.alt" loading="lazy" decoding="async" />
            </button>
          </div>

          <div v-else-if="currentItem.remote_videos?.length" class="post-detail-note">
            识别到 {{ currentItem.remote_videos.length }} 个远程视频，但本地暂时没有下载文件。
          </div>

          <div class="post-stat-grid">
            <div class="post-stat-card">
              <span>回复</span>
              <strong>{{ currentItem.replies || 0 }}</strong>
            </div>
            <div class="post-stat-card">
              <span>转推</span>
              <strong>{{ currentItem.retweets || 0 }}</strong>
            </div>
            <div class="post-stat-card">
              <span>喜欢</span>
              <strong>{{ currentItem.likes || 0 }}</strong>
            </div>
            <div class="post-stat-card">
              <span>媒体</span>
              <strong>{{ mediaCount(currentItem) }}</strong>
            </div>
          </div>

          <div class="post-detail-actions">
            <a-button @click="openSibling(-1)" :disabled="!prevItem">上一条</a-button>
            <a-button @click="openSibling(1)" :disabled="!nextItem">下一条</a-button>
            <a-button type="dashed" @click="goBackToFeed">回到时间流</a-button>
            <a-button
              v-if="currentItem.local_videos?.length"
              type="primary"
              ghost
              @click="openVideoPage(currentItem, 0)"
            >
              打开视频独立页
            </a-button>
          </div>
        </section>

        <section v-else class="post-detail-card">
          <a-empty description="当前贴文不存在，可能是旧链接或该用户数据已经变化。" />
          <div class="post-missing-actions">
            <a-button type="primary" @click="goBackToFeed" :disabled="!resolvedUsername">返回用户主页</a-button>
          </div>
        </section>
      </main>

      <aside class="post-page-right">
        <section class="post-side-card">
          <div class="post-side-title">相邻导航</div>
          <div class="post-nav-grid">
            <button
              type="button"
              class="post-nav-card"
              :disabled="!prevItem"
              @click="openSibling(-1)"
            >
              <span class="post-nav-label">上一条</span>
              <strong>{{ prevItem ? previewText(prevItem) : '没有了' }}</strong>
            </button>
            <button
              type="button"
              class="post-nav-card"
              :disabled="!nextItem"
              @click="openSibling(1)"
            >
              <span class="post-nav-label">下一条</span>
              <strong>{{ nextItem ? previewText(nextItem) : '没有了' }}</strong>
            </button>
          </div>
        </section>

        <section class="post-side-card">
          <div class="post-side-title">关联内容区</div>
          <div v-if="relatedItems.length" class="post-related-list">
            <button
              v-for="item in relatedItems"
              :key="item.id"
              type="button"
              class="post-related-item"
              @click="openPost(item)"
            >
              <div class="post-related-time">{{ formatDateTime(item.date, '时间未知') }}</div>
              <div class="post-related-text">{{ previewText(item) }}</div>
            </button>
          </div>
          <a-empty v-else description="暂无相关贴文" />
        </section>
      </aside>
    </div>

    <a-modal
      :open="previewState.open"
      :footer="null"
      :width="1040"
      centered
      destroy-on-close
      class="post-preview-modal"
      @cancel="closeImagePreview"
    >
      <div v-if="currentPreviewImage" class="post-preview-shell">
        <div class="post-preview-top">
          <div class="post-preview-title">{{ `@${resolvedUsername || 'user'} · 图片预览` }}</div>
          <div class="post-preview-copy">第 {{ previewState.index + 1 }} / {{ previewState.images.length }} 张</div>
        </div>

        <div class="post-preview-stage">
          <a-button size="small" @click="shiftPreview(-1)" :disabled="previewState.images.length <= 1">上一张</a-button>
          <img class="post-preview-main" :src="currentPreviewImage.src" :alt="currentPreviewImage.alt" />
          <a-button size="small" @click="shiftPreview(1)" :disabled="previewState.images.length <= 1">下一张</a-button>
        </div>

        <div v-if="previewState.images.length > 1" class="post-preview-thumb-row">
          <button
            v-for="(photo, index) in previewState.images"
            :key="photo.key"
            type="button"
            class="post-preview-thumb-button"
            :class="{ 'post-preview-thumb-button-active': index === previewState.index }"
            @click="previewState.index = index"
          >
            <img class="post-preview-thumb" :src="photo.src" :alt="photo.alt" />
          </button>
        </div>
      </div>
    </a-modal>
  </a-spin>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { api } from '../lib/api';
import { encodeOutputPath, formatDateTime } from '../lib/formatters';
import { USER_FEED_LIMIT, prepareFeedPayload, resolveFeedVideoRouteKey } from '../lib/user-feed';
import { useWorkbenchStore } from '../store/workbench';

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();

const loading = ref(false);
const selectedUsername = ref('');
const payload = ref({
  username: '',
  source_file: '',
  items: [],
  summary: {},
});
const previewState = reactive({
  open: false,
  images: [],
  index: 0,
});
const loadedVideoKeys = reactive({});
let reloadRequestToken = 0;

const routeUsername = computed(() => String(route.params.username || '').trim());
const tweetId = computed(() => String(route.params.tweetId || '').trim());
const isStandaloneMode = computed(() => Boolean(route.meta?.standalone));
const resolvedUsername = computed(() => String(payload.value.username || routeUsername.value || selectedUsername.value || '').trim());
const avatarLetter = computed(() => resolvedUsername.value.slice(0, 1).toUpperCase() || 'X');
const preparedPayload = computed(() => prepareFeedPayload(payload.value));
const feedItems = computed(() => preparedPayload.value.items || []);
const summary = computed(() => preparedPayload.value.summary || {});
const sourceFile = computed(() => payload.value.source_file || '');
const usernameSelectOptions = computed(() =>
  (store.usernameDirectoryItems.value || [])
    .filter((item) => !item.hidden)
    .map((item) => ({
      label: item.alias ? `${item.display_name} · @${item.username}` : `@${item.username}`,
      value: item.username,
    }))
);

const currentIndex = computed(() => feedItems.value.findIndex((item) => String(item.id) === tweetId.value));
const currentItem = computed(() => feedItems.value[currentIndex.value] || null);
const prevItem = computed(() => (currentIndex.value > 0 ? feedItems.value[currentIndex.value - 1] : null));
const nextItem = computed(() => (
  currentIndex.value >= 0 && currentIndex.value < feedItems.value.length - 1
    ? feedItems.value[currentIndex.value + 1]
    : null
));
const relatedItems = computed(() => feedItems.value.filter((item) => String(item.id) !== tweetId.value).slice(0, 6));
const currentPhotos = computed(() => currentItem.value?.photos || []);
const latestTimeLabel = computed(() => formatDateTime(feedItems.value[0]?.date, '暂无'));
const currentPreviewImage = computed(() => previewState.images[previewState.index] || null);

function filterUsernameOption(input, option) {
  const keyword = String(input || '').trim().toLowerCase();
  const label = String(option?.label || '').toLowerCase();
  const value = String(option?.value || '').toLowerCase();
  return label.includes(keyword) || value.includes(keyword);
}

function videoTileKey(item, index) {
  const id = String(item?.id || item?.tweet_id || 'tweet');
  const video = item?.local_videos?.[index];
  const routeKey = String(video?.route_key || resolveFeedVideoRouteKey(item, index));
  return `${id}:${routeKey}`;
}

function isVideoLoaded(item, index) {
  return Boolean(loadedVideoKeys[videoTileKey(item, index)]);
}

function loadVideo(item, index) {
  loadedVideoKeys[videoTileKey(item, index)] = true;
}

function videoPlaceholderStyle(video = {}) {
  if (!video.thumbnail_src) {
    return {};
  }
  return {
    backgroundImage: `linear-gradient(180deg, rgba(12, 24, 14, 0.1), rgba(12, 24, 14, 0.58)), url("${video.thumbnail_src}")`,
  };
}

function resetLoadedVideos() {
  Object.keys(loadedVideoKeys).forEach((key) => {
    delete loadedVideoKeys[key];
  });
}

async function ensureUsernamesLoaded() {
  if (!store.state.authReady) {
    await store.refreshSession();
  }
  if (!isStandaloneMode.value && !routeUsername.value && !store.sortedTasks.value.length) {
    await store.loadTasks();
  }
  if (store.state.auth.isAdmin && !store.usernameDirectoryItems.value?.length) {
    await store.loadUsernameDirectory({ silent: true });
  }
}

async function reload() {
  if (!routeUsername.value) {
    await ensureUsernamesLoaded();
    const fallback = (store.latestCompletedTask.value?.username || store.usernameOptions.value?.[0] || '').trim();
    if (fallback) {
      router.replace({
        name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
        params: { username: fallback },
      });
    }
    return;
  }

  const requestToken = ++reloadRequestToken;
  loading.value = true;
  try {
    await ensureUsernamesLoaded();
    selectedUsername.value = routeUsername.value;
    const nextPayload = await api.getAdminUserFeed(routeUsername.value, USER_FEED_LIMIT);
    if (requestToken !== reloadRequestToken) {
      return;
    }
    payload.value = nextPayload;
  } catch (error) {
    if (requestToken !== reloadRequestToken) {
      return;
    }
    message.error(error.message || '贴文详情加载失败');
  } finally {
    if (requestToken === reloadRequestToken) {
      loading.value = false;
    }
  }
}

function mediaCount(item) {
  return item?.mediaCount || 0;
}

function previewText(item) {
  return String(item?.previewText || '').slice(0, 46) || `媒体贴文 · ${mediaCount(item)} 个资源`;
}

function goBackToFeed() {
  if (!resolvedUsername.value) {
    return;
  }
  router.push({
    name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
    params: { username: resolvedUsername.value },
  });
}

function openLibrary() {
  if (!resolvedUsername.value) {
    return;
  }
  router.push({
    name: 'library',
    query: { username: resolvedUsername.value },
  });
}

function openOriginalTweet(url) {
  if (!url) {
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

function goBackOrDashboard() {
  if (window.history.length > 1) {
    router.back();
    return;
  }
  router.push({ name: 'dashboard' });
}

function openSibling(delta) {
  const target = delta < 0 ? prevItem.value : nextItem.value;
  if (!target) {
    return;
  }
  openPost(target);
}

function openPost(item) {
  if (!item?.id || !resolvedUsername.value) {
    return;
  }
  router.push({
    name: isStandaloneMode.value ? 'user-post-standalone' : 'user-post',
    params: {
      username: resolvedUsername.value,
      tweetId: String(item.id),
    },
  });
}

function openVideoPage(item, videoIndex = 0) {
  if (!item?.id || !resolvedUsername.value) {
    return;
  }
  const routeKey = resolveFeedVideoRouteKey(item, videoIndex);
  router.push({
    name: isStandaloneMode.value ? 'user-video-standalone' : 'user-video',
    params: {
      username: resolvedUsername.value,
      tweetId: String(item.id),
      videoIndex: String(routeKey),
    },
  });
}

function handleUsernameChange(username) {
  if (!username) {
    return;
  }
  router.push({
    name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
    params: { username },
  });
}

function openImagePreview(images, index = 0) {
  previewState.images = Array.isArray(images) ? images.slice() : [];
  previewState.index = Math.max(0, Math.min(index, previewState.images.length - 1));
  previewState.open = previewState.images.length > 0;
}

function closeImagePreview() {
  previewState.open = false;
  previewState.images = [];
  previewState.index = 0;
}

function shiftPreview(step) {
  if (!previewState.images.length) {
    return;
  }
  const total = previewState.images.length;
  previewState.index = (previewState.index + step + total) % total;
}

watch(
  () => route.params.username,
  () => {
    resetLoadedVideos();
    reload();
  }
);

watch(
  () => tweetId.value,
  () => {
    resetLoadedVideos();
  }
);

watch(
  () => [tweetId.value, payload.value.username, feedItems.value.length, loading.value],
  () => {
    if (loading.value) {
      return;
    }
    if (!tweetId.value || !routeUsername.value) {
      return;
    }
    if (String(payload.value.username || '').trim() !== routeUsername.value) {
      return;
    }
    if (feedItems.value.length && !currentItem.value) {
      message.warning('当前贴文不存在，已回到用户主页');
      router.replace({
        name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
        params: { username: routeUsername.value },
      });
    }
  }
);

onMounted(() => {
  reload();
});
</script>

<style scoped src="../styles/pages/user-post-page.css"></style>
