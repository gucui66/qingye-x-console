import { message } from 'ant-design-vue';
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { api } from '../lib/api';
import { buildThumbnailSrc, encodeOutputPath, formatDateTime, formatFileSize } from '../lib/formatters';
import { USER_FEED_LIMIT, buildFeedVideoEntries, findFeedVideoEntryIndex, prepareFeedPayload } from '../lib/user-feed';
import { useWorkbenchStore } from '../store/workbench';
import { useImagePreview } from './useImagePreview';
import { useUsernameOptions } from './useUsernameOptions';
import { useUserVideoPlayback } from './useUserVideoPlayback';

const rateOptions = [
  { label: '0.75x', value: '0.75' },
  { label: '1.0x', value: '1' },
  { label: '1.25x', value: '1.25' },
  { label: '1.5x', value: '1.5' },
  { label: '2.0x', value: '2' },
];

export function useUserVideoPage() {
  const route = useRoute();
  const router = useRouter();
  const store = useWorkbenchStore();

  const loading = ref(false);
  const payload = ref({
    username: '',
    source_file: '',
    items: [],
    summary: {},
  });
  const {
    closeImagePreview,
    currentPreviewImage,
    openImagePreview,
    previewState,
    shiftPreview,
  } = useImagePreview();
  let reloadRequestToken = 0;

  const routeUsername = computed(() => String(route.params.username || '').trim());
  const tweetId = computed(() => String(route.params.tweetId || '').trim());
  const rawVideoIndex = computed(() => String(route.params.videoIndex || '').trim());
  const isStandaloneMode = computed(() => Boolean(route.meta?.standalone));
  const resolvedUsername = computed(() => String(payload.value.username || routeUsername.value || '').trim());
  const avatarLetter = computed(() => resolvedUsername.value.slice(0, 1).toUpperCase() || 'X');
  const preparedPayload = computed(() => prepareFeedPayload(payload.value));
  const feedItems = computed(() => preparedPayload.value.items || []);
  const { filterUsernameOption, usernameSelectOptions } = useUsernameOptions(store);

  const videoEntries = computed(() => buildFeedVideoEntries(feedItems.value));
  const currentIndex = computed(() => {
    return findFeedVideoEntryIndex(videoEntries.value, tweetId.value, rawVideoIndex.value);
  });
  const currentEntry = computed(() => videoEntries.value[currentIndex.value] || null);
  const prevEntry = computed(() => (currentIndex.value > 0 ? videoEntries.value[currentIndex.value - 1] : null));
  const nextEntry = computed(() => (
    currentIndex.value >= 0 && currentIndex.value < videoEntries.value.length - 1
      ? videoEntries.value[currentIndex.value + 1]
      : null
  ));
  const currentTweetVideos = computed(() => (
    currentEntry.value
      ? videoEntries.value.filter((entry) => entry.tweetId === currentEntry.value.tweetId)
      : []
  ));
  const currentPhotos = computed(() => currentEntry.value?.item?.photos || []);
  const currentAnnotations = computed(() => currentEntry.value?.video?.annotations || {});
  const canAnnotateCurrentVideo = computed(() => Boolean(currentEntry.value?.video?.id));
  const currentVideoSize = computed(() => formatFileSize(currentEntry.value?.video?.size || 0));
  const {
    clearVideoError,
    formatDuration,
    fullscreenShellRef,
    fullscreenState,
    handleEnded,
    handleLoadedMetadata,
    handlePause,
    handlePlay,
    handleTimeUpdate,
    handleVideoError,
    lastPositionText,
    markCurrentWatched,
    openPictureInPicture,
    persistBeforeNavigation,
    playbackPrefs,
    playbackState,
    playerRef,
    pipSupported,
    playlistRef,
    progressText,
    resumeHint,
    setPlaybackRate,
    toggleAnnotation,
    toggleFullscreen,
    toggleFullscreenPlaylist,
    toggleMute,
    toggleTheater,
  } = useUserVideoPlayback({
    currentAnnotations,
    currentEntry,
    nextEntry,
    openEntry,
    patchUpdatedVideoItem,
    store,
  });

  async function ensureVideoBootstrap() {
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

  async function ensureUsernamesLoaded() {
    await ensureVideoBootstrap();
  }

  function feedRouteName() {
    return isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed';
  }

  function postRouteName() {
    return isStandaloneMode.value ? 'user-post-standalone' : 'user-post';
  }

  function videoRouteName() {
    return isStandaloneMode.value ? 'user-video-standalone' : 'user-video';
  }

  async function reload() {
    if (!routeUsername.value) {
      await ensureUsernamesLoaded();
      const fallback = (store.latestCompletedTask.value?.username || store.usernameOptions.value?.[0] || '').trim();
      if (fallback) {
        router.replace({
          name: feedRouteName(),
          params: { username: fallback },
        });
      }
      return;
    }

    const requestToken = ++reloadRequestToken;
    loading.value = true;
    try {
      await ensureUsernamesLoaded();
      const nextPayload = await api.getAdminUserFeed(routeUsername.value, USER_FEED_LIMIT);
      if (requestToken !== reloadRequestToken) {
        return;
      }
      payload.value = nextPayload;
    } catch (error) {
      if (requestToken !== reloadRequestToken) {
        return;
      }
      message.error(error.message || '视频播放页加载失败');
    } finally {
      if (requestToken === reloadRequestToken) {
        loading.value = false;
      }
    }
  }

  function previewText(item) {
    return String(item?.previewText || '').slice(0, 52) || `媒体贴文 · ${item?.local_videos?.length || 0} 个视频`;
  }

  async function goBackOrDashboard() {
    await persistBeforeNavigation();
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.push({ name: 'dashboard' });
  }

  async function goBackToFeed() {
    if (!resolvedUsername.value) {
      return;
    }
    await persistBeforeNavigation();
    router.push({
      name: feedRouteName(),
      params: { username: resolvedUsername.value },
    });
  }

  async function openLibrary() {
    if (!resolvedUsername.value) {
      return;
    }
    await persistBeforeNavigation();
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

  async function openPostPage(item) {
    if (!item?.id || !resolvedUsername.value) {
      return;
    }
    await persistBeforeNavigation();
    router.push({
      name: postRouteName(),
      params: {
        username: resolvedUsername.value,
        tweetId: String(item.id),
      },
    });
  }

  async function handleUsernameChange(username) {
    if (!username) {
      return;
    }
    await persistBeforeNavigation();
    router.push({
      name: feedRouteName(),
      params: { username },
    });
  }

  async function openEntry(entry) {
    if (!entry || !resolvedUsername.value) {
      return;
    }
    if (currentEntry.value?.key && currentEntry.value.key !== entry.key) {
      await persistBeforeNavigation();
    }
    router.replace({
      name: videoRouteName(),
      params: {
        username: resolvedUsername.value,
        tweetId: entry.tweetId,
        videoIndex: String(entry.videoIndex),
      },
    });
  }

  function openSibling(delta) {
    const target = delta < 0 ? prevEntry.value : nextEntry.value;
    if (!target) {
      return;
    }
    void openEntry(target);
  }

  function patchUpdatedVideoItem(updated) {
    if (!updated?.id) {
      return;
    }

    function isSameVideo(video) {
      if (video.id !== updated.id || video.media_type !== updated.media_type) {
        return false;
      }
      if (video.shard_key || updated.shard_key) {
        return video.shard_key === updated.shard_key;
      }
      return video.username === updated.username;
    }

    payload.value = {
      ...payload.value,
      items: (payload.value.items || []).map((item) => ({
        ...item,
        local_videos: (item.local_videos || []).map((video) => (
          isSameVideo(video)
            ? {
                ...video,
                ...updated,
                annotations: updated.annotations || video.annotations || {},
              }
            : video
        )),
      })),
    };
  }

  watch(
    () => route.params.username,
    () => {
      reload();
    }
  );

  watch(
    () => [tweetId.value, rawVideoIndex.value, feedItems.value.length, loading.value],
    () => {
      if (loading.value || !routeUsername.value) {
        return;
      }

      if (!videoEntries.value.length) {
        message.warning('这个账号当前没有本地视频，已回到用户主页');
        router.replace({
          name: feedRouteName(),
          params: { username: routeUsername.value },
        });
        return;
      }

      if (!currentEntry.value) {
        const fallbackSameTweet = videoEntries.value.find((entry) => entry.tweetId === tweetId.value);
        if (fallbackSameTweet) {
          router.replace({
            name: videoRouteName(),
            params: {
              username: routeUsername.value,
              tweetId: fallbackSameTweet.tweetId,
              videoIndex: String(fallbackSameTweet.videoIndex),
            },
          });
          return;
        }

        message.warning('当前视频不存在，已回到贴文详情页');
        router.replace({
          name: postRouteName(),
          params: {
            username: routeUsername.value,
            tweetId: tweetId.value,
          },
        });
      }
    }
  );

  onMounted(() => {
    reload();
  });

  return {
    avatarLetter,
    buildThumbnailSrc,
    canAnnotateCurrentVideo,
    clearVideoError,
    closeImagePreview,
    currentAnnotations,
    currentEntry,
    currentIndex,
    currentPhotos,
    currentPreviewImage,
    currentTweetVideos,
    currentVideoSize,
    encodeOutputPath,
    filterUsernameOption,
    formatDateTime,
    formatDuration,
    fullscreenShellRef,
    fullscreenState,
    goBackOrDashboard,
    goBackToFeed,
    handleEnded,
    handleLoadedMetadata,
    handlePause,
    handlePlay,
    handleTimeUpdate,
    handleUsernameChange,
    handleVideoError,
    isStandaloneMode,
    lastPositionText,
    loading,
    markCurrentWatched,
    nextEntry,
    openEntry,
    openImagePreview,
    openLibrary,
    openOriginalTweet,
    openPictureInPicture,
    openPostPage,
    openSibling,
    playbackPrefs,
    playbackState,
    playerRef,
    pipSupported,
    playlistRef,
    prevEntry,
    previewState,
    previewText,
    progressText,
    rateOptions,
    resolvedUsername,
    resumeHint,
    setPlaybackRate,
    shiftPreview,
    toggleAnnotation,
    toggleFullscreen,
    toggleFullscreenPlaylist,
    toggleMute,
    toggleTheater,
    usernameSelectOptions,
    videoEntries,
  };
}
