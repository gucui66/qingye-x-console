<template>
  <a-spin :spinning="loading">
    <section v-if="isStandaloneMode" class="video-standalone-topbar">
      <div class="video-standalone-topbar-main">
        <a-button type="text" @click="goBackOrDashboard">← 返回</a-button>
        <div class="video-standalone-copy">
          <div class="video-standalone-title">{{ resolvedUsername ? `@${resolvedUsername}` : '视频播放页' }}</div>
          <div class="video-standalone-subtitle">
            {{ currentEntry ? `视频 ${currentIndex + 1} / ${videoEntries.length}` : '独立视频播放' }}
          </div>
        </div>
        <a-space wrap>
          <a-select
            v-if="usernameSelectOptions.length"
            :value="resolvedUsername || undefined"
            size="small"
            style="width: 180px"
            placeholder="切换用户"
            :options="usernameSelectOptions"
            show-search
            :filter-option="filterUsernameOption"
            @change="handleUsernameChange"
          />
          <a-button size="small" @click="goBackToFeed" :disabled="!resolvedUsername">用户主页</a-button>
          <a-button size="small" type="primary" @click="openLibrary" :disabled="!resolvedUsername">资料库</a-button>
        </a-space>
      </div>
      <div class="video-standalone-toolbar">
        <a-space wrap>
          <a-button size="small" @click="toggleMute">
            {{ playbackPrefs.muted ? '取消静音' : '静音' }}
          </a-button>
          <a-button size="small" @click="toggleTheater">
            {{ playbackPrefs.theater ? '退出影院' : '影院模式' }}
          </a-button>
          <a-switch v-model:checked="playbackPrefs.autoplayNext" size="small" />
          <span class="video-toolbar-inline-text">播完自动下一条</span>
        </a-space>
        <a-space wrap>
          <span class="video-toolbar-inline-text">倍速</span>
          <a-select
            :value="String(playbackPrefs.playbackRate)"
            size="small"
            style="width: 100px"
            :options="rateOptions"
            @change="setPlaybackRate"
          />
          <span class="video-toolbar-inline-text">{{ currentEntry ? resumeHint : '等待视频加载' }}</span>
        </a-space>
      </div>
    </section>

    <div
      ref="fullscreenShellRef"
      class="video-page-shell"
      :class="{
        'video-page-shell-theater': playbackPrefs.theater,
        'video-page-shell-fullscreen': fullscreenState.active,
      }"
    >
      <main class="video-main-column">
        <section class="video-player-card" :class="{ 'video-player-card-theater': playbackPrefs.theater }">
          <div class="video-player-top">
            <div>
              <div class="video-player-title">独立视频播放页</div>
              <div class="video-player-subtitle">更接近 X 官方媒体浏览方式，聚焦观看当前视频并保留上下文。</div>
            </div>
            <a-space wrap>
              <a-button @click="goBackToFeed" :disabled="!resolvedUsername">返回主页</a-button>
              <a-button @click="openPostPage(currentEntry?.item)" :disabled="!currentEntry">贴文详情</a-button>
              <a-button v-if="currentEntry?.item?.url" type="primary" @click="openOriginalTweet(currentEntry.item.url)">
                打开原贴文
              </a-button>
            </a-space>
          </div>

          <div v-if="currentEntry" class="video-player-stage" :class="{ 'video-player-stage-theater': playbackPrefs.theater }">
            <video
              :key="currentEntry.key"
              ref="playerRef"
              class="video-player-element"
              controls
              autoplay
              preload="auto"
              playsinline
              :muted="playbackPrefs.muted"
              :poster="buildThumbnailSrc(currentEntry.video) || undefined"
              :src="encodeOutputPath(currentEntry.video.path)"
              @loadedmetadata="handleLoadedMetadata"
              @canplay="clearVideoError"
              @timeupdate="handleTimeUpdate"
              @pause="handlePause"
              @play="handlePlay"
              @ended="handleEnded"
              @error="handleVideoError"
            ></video>
            <div v-if="playbackState.loadError" class="video-player-error">
              <strong>视频加载失败</strong>
              <span>{{ playbackState.loadError }}</span>
            </div>
          </div>
          <a-empty v-else description="当前视频不存在，可能已经被移除或链接已过期。" />

          <div class="video-player-toolbar">
            <a-button size="small" @click="openSibling(-1)" :disabled="!prevEntry">上一个视频</a-button>
            <a-button size="small" @click="openSibling(1)" :disabled="!nextEntry">下一个视频</a-button>
            <div class="video-player-toolbar-note">
              {{ currentEntry ? `${currentEntry.video.name || '本地视频'} · ${formatDateTime(currentEntry.item.date, '时间未知')} · ${progressText}` : '等待加载视频' }}
            </div>
            <a-space wrap class="video-player-toolbar-actions">
              <a-button size="small" @click="toggleFullscreen" :disabled="!currentEntry">
                {{ fullscreenState.active ? '退出全屏' : '全屏' }}
              </a-button>
              <a-button size="small" @click="openPictureInPicture" :disabled="!pipSupported || !currentEntry">画中画</a-button>
            </a-space>
          </div>
        </section>

        <section v-if="currentEntry" class="video-info-card">
          <div class="video-author-row">
            <div class="video-author-avatar">{{ avatarLetter }}</div>
            <div class="video-author-copy">
              <div class="video-author-title">{{ `@${currentEntry.item.author_username || currentEntry.item.username}` }}</div>
              <div class="video-author-meta">
                <span>{{ formatDateTime(currentEntry.item.date, '时间未知') }}</span>
                <span>{{ currentEntry.item.tab_source || '推文流' }}</span>
                <span v-if="currentEntry.item.is_reply">回复贴文</span>
              </div>
            </div>
          </div>

          <div class="video-tweet-content">
            {{ currentEntry.item.content || '这条内容没有抓到正文，当前以视频内容为主展示。' }}
          </div>

          <div v-if="currentEntry.item.reply_context" class="video-reply-context">
            回复上下文：{{ currentEntry.item.reply_context }}
          </div>

          <div class="video-stat-grid">
            <div class="video-stat-card">
              <span>回复</span>
              <strong>{{ currentEntry.item.replies || 0 }}</strong>
            </div>
            <div class="video-stat-card">
              <span>转推</span>
              <strong>{{ currentEntry.item.retweets || 0 }}</strong>
            </div>
            <div class="video-stat-card">
              <span>喜欢</span>
              <strong>{{ currentEntry.item.likes || 0 }}</strong>
            </div>
            <div class="video-stat-card">
              <span>同贴文视频数</span>
              <strong>{{ currentTweetVideos.length }}</strong>
            </div>
            <div class="video-stat-card">
              <span>播放次数</span>
              <strong>{{ currentAnnotations.play_count || 0 }}</strong>
            </div>
            <div class="video-stat-card">
              <span>续播位置</span>
              <strong>{{ lastPositionText }}</strong>
            </div>
            <div class="video-stat-card">
              <span>文件大小</span>
              <strong>{{ currentVideoSize }}</strong>
            </div>
            <div class="video-stat-card">
              <span>状态</span>
              <strong>{{ currentAnnotations.watched ? '已看' : '未看' }}</strong>
            </div>
          </div>

          <div class="video-action-row">
            <a-button size="small" @click="toggleAnnotation('favorite', !currentAnnotations.favorite)" :disabled="!canAnnotateCurrentVideo">
              {{ currentAnnotations.favorite ? '取消收藏' : '加入收藏' }}
            </a-button>
            <a-button size="small" @click="toggleAnnotation('watch_later', !currentAnnotations.watch_later)" :disabled="!canAnnotateCurrentVideo">
              {{ currentAnnotations.watch_later ? '移出稍后看' : '加入稍后看' }}
            </a-button>
            <a-button size="small" type="primary" ghost @click="markCurrentWatched" :disabled="!canAnnotateCurrentVideo">
              标记已看
            </a-button>
          </div>
        </section>
      </main>

      <aside class="video-right-rail">
        <section
          class="video-side-card video-side-card-playlist"
          :class="{ 'video-side-card-playlist-collapsed': fullscreenState.active && !fullscreenState.playlistOpen }"
        >
          <div class="video-side-head">
            <div class="video-side-title">播放列表</div>
            <a-space size="small">
              <span v-if="videoEntries.length" class="video-side-meta">{{ currentEntry ? `${currentIndex + 1} / ${videoEntries.length}` : `${videoEntries.length} 条` }}</span>
              <a-button v-if="fullscreenState.active" size="small" @click="toggleFullscreenPlaylist">
                {{ fullscreenState.playlistOpen ? '收起' : '展开' }}
              </a-button>
            </a-space>
          </div>
          <div v-if="fullscreenState.active && !fullscreenState.playlistOpen" class="video-side-collapsed-note">
            全屏下可随时展开列表并切换其他视频。
          </div>
          <div v-else-if="videoEntries.length" ref="playlistRef" class="video-playlist">
            <button
              v-for="(entry, index) in videoEntries"
              :key="entry.key"
              type="button"
              class="video-playlist-item"
              :class="{ 'video-playlist-item-active': currentEntry?.key === entry.key }"
              @click="openEntry(entry)"
            >
              <div class="video-playlist-media">
                <div v-if="buildThumbnailSrc(entry.video)" class="video-playlist-thumb-shell">
                  <img class="video-playlist-thumb" :src="buildThumbnailSrc(entry.video)" :alt="entry.video.name || `视频 ${index + 1}`" loading="lazy" decoding="async" />
                </div>
                <div v-else class="video-playlist-thumb-shell video-playlist-thumb-shell-fallback">视频</div>
                <div class="video-playlist-copy">
                  <div class="video-playlist-index">视频 {{ index + 1 }}</div>
                  <div class="video-playlist-title">{{ previewText(entry.item) }}</div>
                  <div class="video-playlist-time">{{ formatDateTime(entry.item.date, '时间未知') }}</div>
                  <div class="video-playlist-flags">
                    <a-tag v-if="entry.video.annotations?.favorite" color="green">收藏</a-tag>
                    <a-tag v-if="entry.video.annotations?.watched" color="green">已看</a-tag>
                    <a-tag v-if="entry.video.annotations?.watch_later" color="gold">稍后看</a-tag>
                    <span v-if="entry.video.annotations?.last_position" class="video-playlist-progress">
                      续播 {{ formatDuration(entry.video.annotations.last_position) }}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          </div>
          <a-empty v-else description="当前账号还没有本地视频" />
        </section>

        <section v-if="!fullscreenState.active" class="video-side-card">
          <div class="video-side-title">同贴文媒体</div>
          <div v-if="currentPhotos.length" class="video-photo-grid">
            <button
              v-for="(photo, index) in currentPhotos"
              :key="photo.key"
              type="button"
              class="video-photo-button"
              @click="openImagePreview(currentPhotos, index)"
            >
              <img class="video-photo" :src="photo.src" :alt="photo.alt" loading="lazy" decoding="async" />
            </button>
          </div>
          <a-empty v-else description="这条贴文没有图片附件" />
        </section>
      </aside>
    </div>

    <a-modal
      :open="previewState.open"
      :footer="null"
      :width="1040"
      centered
      destroy-on-close
      class="video-preview-modal"
      @cancel="closeImagePreview"
    >
      <div v-if="currentPreviewImage" class="video-preview-shell">
        <div class="video-preview-top">
          <div class="video-preview-title">{{ `@${resolvedUsername || 'user'} · 图片预览` }}</div>
          <div class="video-preview-copy">第 {{ previewState.index + 1 }} / {{ previewState.images.length }} 张</div>
        </div>

        <div class="video-preview-stage">
          <a-button size="small" @click="shiftPreview(-1)" :disabled="previewState.images.length <= 1">上一张</a-button>
          <img class="video-preview-main" :src="currentPreviewImage.src" :alt="currentPreviewImage.alt" />
          <a-button size="small" @click="shiftPreview(1)" :disabled="previewState.images.length <= 1">下一张</a-button>
        </div>
      </div>
    </a-modal>
  </a-spin>
</template>

<script setup>
import { useUserVideoPage } from '../composables/useUserVideoPage';

const {
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
} = useUserVideoPage();
</script>

<style scoped src="../styles/pages/user-video-page.css"></style>
