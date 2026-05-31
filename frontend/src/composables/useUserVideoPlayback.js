import { message } from 'ant-design-vue';
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

import {
  DEFAULT_PLAYER_PREFS,
  formatDuration,
  isEditableTarget,
  normalizePlaybackRate,
  readPlayerPrefs,
  writePlayerPrefs,
} from '../lib/video-player';

export function useUserVideoPlayback({
  currentAnnotations,
  currentEntry,
  nextEntry,
  openEntry,
  patchUpdatedVideoItem,
  store,
}) {
  const playerRef = ref(null);
  const playlistRef = ref(null);
  const fullscreenShellRef = ref(null);
  const playbackPrefs = reactive({
    ...DEFAULT_PLAYER_PREFS,
    ...readPlayerPrefs(),
  });
  const playbackState = reactive({
    currentTime: 0,
    duration: 0,
    lastPersistedTime: 0,
    lastPersistedKey: '',
    playedKey: '',
    loadError: '',
  });
  const fullscreenState = reactive({
    active: false,
    playlistOpen: true,
  });
  let persistTimer = null;

  const progressText = computed(() => (
    currentEntry.value
      ? `${formatDuration(playbackState.currentTime)} / ${formatDuration(playbackState.duration)}`
      : '等待加载视频'
  ));
  const resumeHint = computed(() => {
    const lastPosition = Number(currentAnnotations.value.last_position || 0) || 0;
    if (lastPosition > 0) {
      return `可从 ${formatDuration(lastPosition)} 继续播放`;
    }
    return '第一次播放';
  });
  const lastPositionText = computed(() => formatDuration(currentAnnotations.value.last_position || 0));
  const pipSupported = computed(() => (
    Boolean(playerRef.value)
    && typeof document !== 'undefined'
    && Boolean(document.pictureInPictureEnabled)
    && typeof playerRef.value.requestPictureInPicture === 'function'
  ));

  async function persistBeforeNavigation() {
    await flushPlaybackProgress({ force: true, silent: true });
  }

  function clearPersistTimer() {
    if (persistTimer) {
      window.clearTimeout(persistTimer);
      persistTimer = null;
    }
  }

  function applyPlayerPrefs() {
    if (!playerRef.value) {
      return;
    }

    playerRef.value.muted = playbackPrefs.muted;
    playerRef.value.playbackRate = normalizePlaybackRate(playbackPrefs.playbackRate);
  }

  async function persistAnnotation(extra = {}, options = {}) {
    const entry = currentEntry.value;
    if (!entry?.video?.id || !entry.video.username) {
      return;
    }

    const player = playerRef.value;
    const currentTime = extra.last_position ?? player?.currentTime ?? playbackState.currentTime ?? 0;
    const payloadData = {
      username: entry.video.username,
      media_type: entry.video.media_type || 'video',
      media_id: entry.video.id,
      shard_key: entry.video.shard_key || null,
      last_position: Math.max(0, currentTime || 0),
      last_played_at: extra.last_played_at || new Date().toISOString(),
      ...extra,
    };

    try {
      const result = await store.updateMediaAnnotation(payloadData, { skipOverviewRefresh: true });
      if (result?.item) {
        patchUpdatedVideoItem(result.item);
      }
      playbackState.lastPersistedKey = entry.key;
      playbackState.lastPersistedTime = payloadData.last_position || 0;
    } catch (error) {
      if (!options.silent) {
        message.error(error.message || '视频播放记录保存失败');
      }
    }
  }

  function schedulePersist(force = false) {
    clearPersistTimer();
    persistTimer = window.setTimeout(() => {
      void flushPlaybackProgress({ force, silent: true });
    }, force ? 120 : 1200);
  }

  async function flushPlaybackProgress(options = {}) {
    const entry = currentEntry.value;
    const player = playerRef.value;
    if (!entry?.video?.id || !player) {
      return;
    }

    const currentTime = Math.max(0, player.currentTime || playbackState.currentTime || 0);
    const shouldSkip = !options.force
      && playbackState.lastPersistedKey === entry.key
      && Math.abs(currentTime - playbackState.lastPersistedTime) < 8
      && !options.markWatched
      && !options.incrementPlayCount;

    if (shouldSkip) {
      return;
    }

    const annotationPayload = {
      last_position: options.markWatched ? (player.duration || currentTime || 0) : currentTime,
    };

    if (options.incrementPlayCount) {
      annotationPayload.play_count = (Number(currentAnnotations.value.play_count || 0) || 0) + 1;
    }

    if (options.markWatched) {
      annotationPayload.watched = true;
    }

    await persistAnnotation(annotationPayload, { silent: options.silent });
  }

  function setPlaybackRate(value) {
    playbackPrefs.playbackRate = normalizePlaybackRate(value);
  }

  function toggleMute() {
    playbackPrefs.muted = !playbackPrefs.muted;
  }

  function toggleTheater() {
    playbackPrefs.theater = !playbackPrefs.theater;
  }

  async function toggleFullscreen() {
    const target = fullscreenShellRef.value;
    if (!target?.requestFullscreen) {
      return;
    }

    try {
      const currentFullscreenElement = document.fullscreenElement;
      if (currentFullscreenElement && (currentFullscreenElement === target || target.contains(currentFullscreenElement))) {
        await document.exitFullscreen();
        return;
      }

      fullscreenState.playlistOpen = true;
      await target.requestFullscreen();
    } catch (error) {
      message.warning('当前环境不支持全屏播放');
    }
  }

  function toggleFullscreenPlaylist() {
    fullscreenState.playlistOpen = !fullscreenState.playlistOpen;
  }

  function scrollActivePlaylistItemIntoView() {
    nextTick(() => {
      const container = playlistRef.value;
      if (!container) {
        return;
      }

      const activeItem = container.querySelector('.video-playlist-item-active');
      if (activeItem && typeof activeItem.scrollIntoView === 'function') {
        activeItem.scrollIntoView({
          block: 'nearest',
          inline: 'nearest',
          behavior: 'smooth',
        });
      }
    });
  }

  async function openPictureInPicture() {
    if (!pipSupported.value || !playerRef.value) {
      return;
    }

    try {
      await playerRef.value.requestPictureInPicture();
    } catch (error) {
      message.warning('当前环境暂不支持画中画');
    }
  }

  async function toggleAnnotation(key, value) {
    if (!currentEntry.value?.video?.id) {
      return;
    }
    await persistAnnotation({ [key]: value });
  }

  async function markCurrentWatched() {
    await flushPlaybackProgress({ force: true, markWatched: true });
  }

  function handleLoadedMetadata() {
    const player = playerRef.value;
    if (!player) {
      return;
    }

    playbackState.loadError = '';
    applyPlayerPrefs();
    playbackState.duration = Number(player.duration || 0) || 0;
    const lastPosition = Number(currentAnnotations.value.last_position || 0) || 0;
    if (lastPosition > 3 && playbackState.duration > lastPosition + 2) {
      player.currentTime = lastPosition;
      playbackState.currentTime = lastPosition;
      return;
    }
    playbackState.currentTime = Number(player.currentTime || 0) || 0;
  }

  function clearVideoError() {
    playbackState.loadError = '';
  }

  function handleVideoError() {
    const player = playerRef.value;
    const errorCode = player?.error?.code;
    const fallback = currentEntry.value?.video?.path
      ? `请检查本地文件是否存在，或浏览器是否支持这个视频编码：${currentEntry.value.video.path}`
      : '没有拿到本地视频路径，请回到用户主页重新进入。';
    const reasonMap = {
      1: '加载被中断。',
      2: '网络或本地服务连接中断。',
      3: '视频文件可能损坏，浏览器无法解码。',
      4: '浏览器不支持该视频格式或文件地址不可访问。',
    };
    playbackState.loadError = reasonMap[errorCode] ? `${reasonMap[errorCode]} ${fallback}` : fallback;
  }

  function handleTimeUpdate() {
    const player = playerRef.value;
    if (!player) {
      return;
    }
    playbackState.currentTime = Number(player.currentTime || 0) || 0;
    playbackState.duration = Number(player.duration || 0) || playbackState.duration;
    if (Math.abs(playbackState.currentTime - playbackState.lastPersistedTime) >= 12) {
      schedulePersist(false);
    }
  }

  function handlePause() {
    schedulePersist(true);
  }

  function handlePlay() {
    if (!currentEntry.value) {
      return;
    }
    if (playbackState.playedKey === currentEntry.value.key) {
      return;
    }
    playbackState.playedKey = currentEntry.value.key;
    void flushPlaybackProgress({ force: true, incrementPlayCount: true, silent: true });
  }

  async function handleEnded() {
    await flushPlaybackProgress({ force: true, markWatched: true, silent: true });
    if (playbackPrefs.autoplayNext && nextEntry.value) {
      openEntry(nextEntry.value);
    }
  }

  function handleWindowKeydown(event) {
    if (isEditableTarget(event.target) || !playerRef.value || !currentEntry.value) {
      return;
    }

    const key = String(event.key || '').toLowerCase();
    if (key === ' ' || key === 'spacebar') {
      event.preventDefault();
      if (playerRef.value.paused) {
        void playerRef.value.play();
      } else {
        playerRef.value.pause();
      }
      return;
    }

    if (key === 'arrowright') {
      event.preventDefault();
      playerRef.value.currentTime = Math.min((playerRef.value.currentTime || 0) + 5, playerRef.value.duration || Infinity);
      return;
    }

    if (key === 'arrowleft') {
      event.preventDefault();
      playerRef.value.currentTime = Math.max((playerRef.value.currentTime || 0) - 5, 0);
      return;
    }

    if (key === 'm') {
      event.preventDefault();
      toggleMute();
      return;
    }

    if (key === 'f') {
      event.preventDefault();
      void toggleFullscreen();
      return;
    }

    if (key === 'p') {
      event.preventDefault();
      void openPictureInPicture();
      return;
    }

    if (key === 'l' && fullscreenState.active) {
      event.preventDefault();
      toggleFullscreenPlaylist();
      return;
    }

    if (key === 'n' && nextEntry.value) {
      event.preventDefault();
      openEntry(nextEntry.value);
    }
  }

  function handleFullscreenChange() {
    const activeElement = document.fullscreenElement;
    const target = fullscreenShellRef.value;
    fullscreenState.active = Boolean(activeElement && target && (activeElement === target || target.contains(activeElement)));
    if (!fullscreenState.active) {
      fullscreenState.playlistOpen = true;
    }
  }

  function handleBeforeUnload() {
    clearPersistTimer();
    void flushPlaybackProgress({ force: true, silent: true });
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      clearPersistTimer();
      void flushPlaybackProgress({ force: true, silent: true });
    }
  }

  watch(
    () => [playbackPrefs.muted, playbackPrefs.theater, playbackPrefs.autoplayNext, playbackPrefs.playbackRate],
    () => {
      writePlayerPrefs(playbackPrefs);
      applyPlayerPrefs();
    }
  );

  watch(
    () => currentEntry.value?.key,
    () => {
      clearPersistTimer();
      playbackState.currentTime = 0;
      playbackState.duration = 0;
      playbackState.playedKey = '';
      playbackState.lastPersistedKey = '';
      playbackState.lastPersistedTime = 0;
      playbackState.loadError = '';
      scrollActivePlaylistItemIntoView();
    }
  );

  watch(
    () => [fullscreenState.active, fullscreenState.playlistOpen],
    ([active, open]) => {
      if (!active || open) {
        scrollActivePlaylistItemIntoView();
      }
    }
  );

  onMounted(() => {
    window.addEventListener('keydown', handleWindowKeydown);
    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleWindowKeydown);
    window.removeEventListener('beforeunload', handleBeforeUnload);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    document.removeEventListener('fullscreenchange', handleFullscreenChange);
    clearPersistTimer();
  });

  return {
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
  };
}
