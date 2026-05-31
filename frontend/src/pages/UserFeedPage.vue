<template>
  <a-spin :spinning="loading">
    <section class="x-feed-toolbar">
      <a-button v-if="isStandaloneMode" type="text" class="x-topbar-back" @click="goBackOrDashboard">
        {{ uf.back }}
      </a-button>
      <button type="button" class="x-profile-hero-avatar" @click="reload">
        <img v-if="profileAvatarSrc" :src="profileAvatarSrc" :alt="resolvedUsername || 'avatar'" />
        <span v-else>{{ avatarLetter }}</span>
      </button>
      <div class="x-feed-toolbar-copy">
        <div class="x-feed-toolbar-title">{{ resolvedUsername ? `@${resolvedUsername}` : uf.userHome }}</div>
        <div class="x-feed-toolbar-subtitle">
          {{ resolvedUsername ? uf.feedSubtitle(visibleFeedItems.length, filteredFeedItems.length, activeTabLabel, includeReplies) : uf.directorySubtitle(timelineUserCards.length) }}
          <a-tag v-if="usernameDirectoryRefreshing" color="processing" class="timeline-refresh-tag">{{ uf.syncing }}</a-tag>
        </div>
      </div>
      <a-segmented v-if="resolvedUsername" v-model:value="activeTab" :options="timelineOptions" class="x-profile-tabs" />
      <div v-if="resolvedUsername" class="x-feed-toolbar-replies">
        <span class="x-toolbar-label">{{ uf.replies }}</span>
        <a-switch v-model:checked="includeReplies" size="small" />
      </div>
      <a-select
        v-model:value="selectedUsername"
        class="x-feed-user-select"
        :placeholder="usernameDirectoryReady ? uf.switchUser : uf.loadingDirectory"
        :options="usernameSelectOptions"
        show-search
        :filter-option="filterUsernameOption"
        :loading="!usernameDirectoryReady"
        :disabled="!usernameDirectoryReady"
        @change="handleUsernameChange"
      />
      <a-space size="small">
        <a-button size="small" @click="openUsernameManager">{{ uf.manageUsernames }}</a-button>
        <a-button size="small" @click="openLibrary" :disabled="!resolvedUsername">{{ uf.library }}</a-button>
        <a-button size="small" type="primary" @click="openOriginalProfile" :disabled="!resolvedUsername">{{ uf.xProfile }}</a-button>
      </a-space>
    </section>

    <div class="x-profile-shell x-profile-shell-standalone">
      <main class="x-main-column x-main-column-standalone">
        <section class="x-stream-surface">
          <a-empty
            v-if="bootstrapping || !usernameDirectoryReady"
            :description="uf.loadingDirectoryWait"
          />
          <div
            v-else-if="!resolvedUsername"
            class="timeline-directory-shell"
          >
            <div class="timeline-directory-toolbar">
              <div class="timeline-directory-toolbar-copy">
                <strong>{{ timelineAccountFilterSummary }}</strong>
                <span>
                  {{ uf.directoryHint }}
                  <em v-if="usernameDirectoryRefreshing">{{ uf.syncHint }}</em>
                </span>
              </div>
              <a-segmented
                v-model:value="timelineAccountFilter"
                :options="timelineAccountFilterOptions"
                class="timeline-directory-filter"
              />
              <a-input-search
                v-model:value="timelineAccountKeyword"
                allow-clear
                :placeholder="uf.searchAccountsPlaceholder"
                class="timeline-directory-search"
              />
              <a-button size="small" @click="resetTimelineAccountFilters">
                {{ uf.clearFilters }}
              </a-button>
            </div>

            <div class="timeline-directory-grid">
              <button
                v-for="item in displayedTimelineUserCards"
                :key="item.normalized_username"
                type="button"
                class="timeline-directory-card"
                @click="openTimelineUser(item)"
              >
                <div class="timeline-directory-head">
                  <div class="timeline-directory-avatar">
                    <img v-if="item.avatar_url" :src="item.avatar_url" :alt="item.username" />
                    <span v-else>{{ String(item.display_name || item.username || 'X').slice(0, 1).toUpperCase() }}</span>
                  </div>
                  <div class="timeline-directory-copy">
                    <div class="timeline-directory-name">{{ item.display_name || item.author_name || item.username }}</div>
                    <div class="timeline-directory-handle">{{ `@${item.username}` }}</div>
                  </div>
                  <div class="timeline-directory-time">
                    <div class="timeline-directory-time-label">{{ uf.lastCollected }}</div>
                    <strong>{{ formatDateTime(item.last_crawled_at, uf.noCollectionRecord) }}</strong>
                  </div>
                </div>

                <div class="timeline-directory-stats">
                  <div class="timeline-directory-stat">{{ uf.latestCount(item.latest_task_tweets || item.latest_tweet_count || 0) }}</div>
                  <div class="timeline-directory-stat">{{ uf.totalCount(item.total_tweets_collected || item.latest_tweet_count || 0) }}</div>
                  <div class="timeline-directory-stat">{{ uf.photoCount(item.photos || 0) }}</div>
                  <div class="timeline-directory-stat">{{ uf.videoCount(item.videos || 0) }}</div>
                </div>

                <div class="timeline-directory-preview">
                  {{ item.latest_preview || uf.noPreview }}
                </div>
              </button>
              <a-empty v-if="!timelineUserCards.length" :description="uf.noAccounts" />
            </div>

            <div v-if="hasMoreTimelineUserCards" class="timeline-directory-load-more">
              <a-button block @click="loadMoreTimelineUserCards">
                {{ uf.loadMoreAccounts(remainingTimelineUserCards) }}
              </a-button>
            </div>
          </div>
          <div v-else-if="filteredFeedItems.length" class="x-stream-list">
            <article
              v-for="item in visibleFeedItems"
              :key="item.id"
              class="x-tweet-card"
              :class="{ 'x-tweet-card-active': selectedTweetId === String(item.id) }"
              role="button"
              tabindex="0"
              @click="openTweetDetail(item)"
              @keyup.enter="openTweetDetail(item)"
              @keyup.space.prevent="openTweetDetail(item)"
            >
              <div class="x-tweet-head">
                <button type="button" class="feed-inline-avatar" @click.stop="scrollToTop">
                  <img v-if="item.author_avatar_src || profileAvatarSrc" :src="item.author_avatar_src || profileAvatarSrc" :alt="item.author_username || item.username" />
                  <span v-else>{{ avatarLetter }}</span>
                </button>
                <div class="x-tweet-head-copy">
                  <div class="x-tweet-title-row">
                    <span class="x-tweet-name">{{ `@${item.author_username || item.username}` }}</span>
                    <a-tag color="green">{{ item.tab_source || uf.tweetStream }}</a-tag>
                    <a-tag v-if="item.content_edited" color="gold">{{ uf.edited }}</a-tag>
                  </div>
                  <div class="x-tweet-meta">
                    <span>{{ uf.publishTime(formatDateTime(item.publish_time || item.date, uf.publishUnknown)) }}</span>
                    <span>{{ uf.crawledTime(formatCrawledTime(item)) }}</span>
                    <span v-if="item.is_reply">{{ uf.replyPost }}</span>
                  </div>
                </div>
                <a-space wrap class="x-head-actions" @click.stop>
                  <a-button
                    v-if="item.url"
                    size="small"
                    type="text"
                    class="x-link-button"
                    @click="openOriginalTweet(item.url)"
                  >
                    {{ uf.originalPost }}
                  </a-button>
                  <a-button
                    size="small"
                    type="text"
                    class="x-link-button"
                    @click="openEditModal(item)"
                  >
                    {{ uf.edit }}
                  </a-button>
                  <a-button
                    size="small"
                    type="text"
                    class="x-link-button"
                    @click="openTweetDetail(item)"
                  >
                    {{ uf.quickDetail }}
                  </a-button>
                  <a-button
                    size="small"
                    type="text"
                    class="x-link-button"
                    @click="openTweetPage(item)"
                  >
                    {{ uf.standalonePage }}
                  </a-button>
                </a-space>
              </div>

              <div v-if="item.content" class="x-tweet-content">{{ item.content }}</div>
              <div v-else class="x-tweet-content x-tweet-content-muted">{{ uf.noContentMediaOnly }}</div>

              <div v-if="item.reply_context" class="x-reply-context">
                {{ uf.replyContext(item.reply_context) }}
              </div>

              <div v-if="item.local_videos?.length" class="x-media-grid x-media-grid-video">
                <div
                  v-for="(video, index) in item.local_videos"
                  :key="video.path"
                  class="x-video-tile"
                >
                  <button
                    v-if="!isInlineVideoLoaded(item, index)"
                    type="button"
                    class="x-video-placeholder"
                    :class="{ 'x-video-placeholder-has-thumb': video.thumbnail_src }"
                    :style="videoPlaceholderStyle(video)"
                    @click.stop="loadInlineVideo(item, index)"
                  >
                    <span v-if="video.thumbnail_src" class="x-video-thumb-shade"></span>
                    <span class="x-video-placeholder-icon">▶</span>
                    <span class="x-video-placeholder-copy">{{ uf.loadLocalVideoPreview }}</span>
                    <span class="x-video-placeholder-subcopy">{{ uf.videoLazyLoadHint }}</span>
                  </button>
                  <video
                    v-else
                    class="x-media-video"
                    controls
                    preload="metadata"
                    playsinline
                    :poster="video.thumbnail_src || undefined"
                    :src="encodeOutputPath(video.path)"
                    @click.stop
                  ></video>
                  <div class="x-video-tile-actions">
                    <a-button size="small" type="text" @click.stop="openVideoPage(item, index)">
                      {{ uf.standalonePlay }}
                    </a-button>
                    <a-popconfirm
                      :title="uf.hideVideoConfirm"
                      :ok-text="uf.hide"
                      :cancel-text="uf.cancel"
                      @confirm="hideFeedVideo(item, video)"
                    >
                      <a-button size="small" type="text" danger @click.stop>
                        {{ uf.hide }}
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>

              <div v-if="item.photos.length" class="x-media-grid x-media-grid-photo">
                <button
                  v-for="(photo, index) in item.photos"
                  :key="photo.key"
                  type="button"
                  class="x-media-photo-button"
                  @click.stop="openImagePreview(item.photos, index, item)"
                >
                  <img
                    class="x-media-photo"
                    :src="photo.src"
                    :alt="photo.alt"
                    loading="lazy"
                    decoding="async"
                  />
                </button>
              </div>

              <div
                v-else-if="item.remote_videos?.length"
                class="x-tweet-content x-tweet-content-muted x-remote-video-note"
              >
                {{ uf.remoteVideosFound(item.remote_videos.length) }}
              </div>

              <div class="x-tweet-actions">
                <div class="x-action-pill">{{ uf.replyCount(item.replies || 0) }}</div>
                <div class="x-action-pill">{{ uf.retweetCount(item.retweets || 0) }}</div>
                <div class="x-action-pill">{{ uf.likeCount(item.likes || 0) }}</div>
                <div class="x-action-pill">{{ uf.mediaCount(item.mediaCount) }}</div>
                <button
                  v-if="item.hidden_videos_count"
                  type="button"
                  class="x-action-pill x-action-pill-button"
                  @click.stop="restoreHiddenVideos(item)"
                >
                  {{ uf.restoreHiddenVideoCount(item.hidden_videos_count) }}
                </button>
              </div>
            </article>
            <div v-if="hasMoreFeedItems" class="x-load-more">
              <a-button block size="large" @click="loadMoreFeedItems">
                {{ uf.loadMorePosts(remainingFeedItems) }}
              </a-button>
            </div>
          </div>

          <a-empty v-else-if="resolvedUsername" :description="uf.noPosts" />
        </section>
      </main>

    </div>

    <a-drawer
      :open="Boolean(selectedItem)"
      :width="520"
      placement="right"
      class="x-detail-drawer"
      :body-style="{ padding: '0' }"
      destroy-on-close
      @close="clearSelectedItem"
    >
      <template #title>
        <span>{{ selectedItem ? `@${selectedItem.author_username || selectedItem.username}` : uf.postDetail }}</span>
      </template>

      <div v-if="selectedItem" class="x-detail-shell">
        <div class="x-detail-head">
          <div class="x-detail-avatar">
            <img v-if="selectedItem.author_avatar_src || profileAvatarSrc" :src="selectedItem.author_avatar_src || profileAvatarSrc" :alt="selectedItem.author_username || selectedItem.username" />
            <span v-else>{{ avatarLetter }}</span>
          </div>
          <div class="x-detail-head-copy">
            <div class="x-detail-title">{{ `@${selectedItem.author_username || selectedItem.username}` }}</div>
            <div class="x-detail-meta">
              <span>{{ uf.publishTime(formatDateTime(selectedItem.publish_time || selectedItem.date, uf.publishUnknown)) }}</span>
              <span>{{ uf.crawledTime(formatCrawledTime(selectedItem)) }}</span>
              <span>{{ selectedItem.tab_source || uf.tweetStream }}</span>
              <span v-if="selectedItem.content_edited">{{ uf.localEdited }}</span>
            </div>
          </div>
        </div>

        <div class="x-detail-copy">
          {{ selectedItem.content || uf.noContentMediaOnly }}
        </div>

        <div v-if="selectedItem.reply_context" class="x-detail-reply">
          {{ uf.replyContext(selectedItem.reply_context) }}
        </div>

        <div v-if="selectedItemVideos.length" class="x-detail-section">
          <div class="x-detail-section-title">{{ uf.videos }}</div>
          <div class="x-detail-video-grid">
            <div
              v-for="(video, index) in selectedItemVideos"
              :key="video.path"
              class="x-video-tile"
            >
              <button
                v-if="!isDetailVideoLoaded(selectedItem, index)"
                type="button"
                class="x-video-placeholder x-video-placeholder-detail"
                :class="{ 'x-video-placeholder-has-thumb': video.thumbnail_src }"
                :style="videoPlaceholderStyle(video)"
                @click="loadDetailVideo(selectedItem, index)"
              >
                <span v-if="video.thumbnail_src" class="x-video-thumb-shade"></span>
                <span class="x-video-placeholder-icon">▶</span>
                <span class="x-video-placeholder-copy">{{ uf.loadDetailVideo }}</span>
                <span class="x-video-placeholder-subcopy">{{ uf.detailVideoLazyHint }}</span>
              </button>
              <video
                v-else
                class="x-detail-video"
                controls
                preload="metadata"
                :poster="video.thumbnail_src || undefined"
                :src="encodeOutputPath(video.path)"
              ></video>
              <div class="x-video-tile-actions">
                <a-button size="small" type="text" @click="openVideoPage(selectedItem, index)">
                  {{ uf.standalonePlay }}
                </a-button>
                <a-popconfirm
                  :title="uf.hideVideoConfirm"
                  :ok-text="uf.hide"
                  :cancel-text="uf.cancel"
                  @confirm="hideFeedVideo(selectedItem, video)"
                >
                  <a-button size="small" type="text" danger>
                    {{ uf.hide }}
                  </a-button>
                </a-popconfirm>
              </div>
            </div>
          </div>
        </div>

        <div v-if="selectedItemPhotos.length" class="x-detail-section">
          <div class="x-detail-section-title">{{ uf.photos }}</div>
          <div class="x-detail-photo-grid">
            <button
              v-for="(photo, index) in selectedItemPhotos"
              :key="photo.key"
              type="button"
              class="x-detail-photo-button"
              @click="openImagePreview(selectedItemPhotos, index, selectedItem)"
            >
              <img
                class="x-detail-photo"
                :src="photo.src"
                :alt="photo.alt"
              />
            </button>
          </div>
        </div>

        <div
          v-else-if="selectedItem.remote_videos?.length"
          class="x-detail-note"
        >
          {{ uf.remoteVideosNotDownloaded(selectedItem.remote_videos.length) }}
        </div>

        <div class="x-detail-stats">
          <div class="x-detail-stat">
            <span>{{ uf.replies }}</span>
            <strong>{{ selectedItem.replies || 0 }}</strong>
          </div>
          <div class="x-detail-stat">
            <span>{{ uf.retweets }}</span>
            <strong>{{ selectedItem.retweets || 0 }}</strong>
          </div>
          <div class="x-detail-stat">
            <span>{{ uf.likes }}</span>
            <strong>{{ selectedItem.likes || 0 }}</strong>
          </div>
          <div class="x-detail-stat">
            <span>{{ uf.localMedia }}</span>
            <strong>{{ selectedItem.mediaCount }}</strong>
          </div>
        </div>

        <div class="x-detail-actions">
          <a-button @click="openEditModal(selectedItem)">{{ uf.editText }}</a-button>
          <a-popconfirm
            v-if="selectedItem.content_edited"
            :title="uf.restoreOriginalConfirm"
            :ok-text="uf.restore"
            :cancel-text="uf.cancel"
            @confirm="resetEditedContent(selectedItem)"
          >
            <a-button>{{ uf.restoreOriginal }}</a-button>
          </a-popconfirm>
          <a-button v-if="selectedItem.hidden_videos_count" @click="restoreHiddenVideos(selectedItem)">
            {{ uf.restoreHiddenVideos }}
          </a-button>
          <a-button @click="openLibrary">{{ uf.openLibrary }}</a-button>
          <a-button v-if="selectedItem.url" type="primary" @click="openOriginalTweet(selectedItem.url)">
            {{ uf.openOriginalPost }}
          </a-button>
          <a-button type="dashed" @click="openTweetPage(selectedItem)">
            {{ uf.standaloneDetail }}
          </a-button>
        </div>

        <div class="x-detail-nav">
          <a-button size="small" @click="openAdjacentDetail(-1)" :disabled="!hasPrevDetail">
            {{ uf.previous }}
          </a-button>
          <a-button size="small" @click="openAdjacentDetail(1)" :disabled="!hasNextDetail">
            {{ uf.next }}
          </a-button>
        </div>
      </div>
    </a-drawer>

    <a-modal
      :open="editState.open"
      :title="uf.editPostText"
      :ok-text="uf.saveText"
      :cancel-text="uf.cancel"
      :confirm-loading="editState.saving"
      @ok="saveEditedContent"
      @cancel="closeEditModal"
    >
      <div class="x-edit-modal-note">
        {{ uf.editNote }}
      </div>
      <a-textarea
        v-model:value="editState.content"
        class="x-edit-textarea"
        :rows="8"
        :maxlength="10000"
        show-count
        :placeholder="uf.editPlaceholder"
      />
    </a-modal>

    <a-modal
      :open="previewState.open"
      :footer="null"
      :width="1080"
      centered
      destroy-on-close
      class="x-preview-modal"
      @cancel="closeImagePreview"
    >
      <div v-if="currentPreviewImage" class="x-preview-modal-shell">
        <div class="x-preview-modal-top">
          <div class="x-preview-modal-title">
            {{ previewTitle }}
          </div>
          <div class="x-preview-modal-copy">
            {{ uf.imageIndex(previewState.index + 1, previewState.images.length) }}
          </div>
        </div>

        <div class="x-preview-stage">
          <a-button size="small" class="x-preview-nav" @click="shiftPreview(-1)" :disabled="previewState.images.length <= 1">
            {{ uf.previousImage }}
          </a-button>
          <img
            class="x-preview-main-image"
            :src="currentPreviewImage.src"
            :alt="currentPreviewImage.alt"
          />
          <a-button size="small" class="x-preview-nav" @click="shiftPreview(1)" :disabled="previewState.images.length <= 1">
            {{ uf.nextImage }}
          </a-button>
        </div>

        <div v-if="previewState.images.length > 1" class="x-preview-thumb-row">
          <button
            v-for="(photo, index) in previewState.images"
            :key="photo.key"
            type="button"
            class="x-preview-thumb-button"
            :class="{ 'x-preview-thumb-button-active': index === previewState.index }"
            @click="previewState.index = index"
          >
            <img class="x-preview-thumb" :src="photo.src" :alt="photo.alt" />
          </button>
        </div>
      </div>
    </a-modal>

    <a-modal
      :open="usernameManagerOpen"
      :title="uf.usernameManager"
      width="720px"
      :footer="null"
      @cancel="closeUsernameManager"
    >
      <div class="username-manager-shell">
        <a-input-search
          v-model:value="usernameManagerKeyword"
          allow-clear
          :placeholder="uf.searchUsernamePlaceholder"
          class="username-manager-search"
        />

        <div class="username-manager-list">
          <div
            v-for="item in filteredUsernameDirectoryItems"
            :key="item.normalized_username"
            class="username-manager-card"
          >
            <div class="username-manager-head">
              <div>
                <div class="username-manager-title">{{ item.display_name }}</div>
                <div class="username-manager-meta">@{{ item.username }} · {{ item.hidden ? uf.hidden : uf.visible }}</div>
              </div>
              <a-space size="small">
                <a-button
                  v-if="!item.hidden"
                  size="small"
                  danger
                  :loading="usernameManagerSavingKey === `${item.username}:hidden`"
                  @click="toggleUsernameHidden(item, true)"
                >
                  {{ uf.hide }}
                </a-button>
                <a-button
                  v-else
                  size="small"
                  type="primary"
                  ghost
                  :loading="usernameManagerSavingKey === `${item.username}:hidden`"
                  @click="toggleUsernameHidden(item, false)"
                >
                  {{ uf.restore }}
                </a-button>
                <a-button
                  size="small"
                  :loading="usernameManagerSavingKey === `${item.username}:reset`"
                  @click="resetUsernameEntry(item)"
                >
                  {{ uf.clearSettings }}
                </a-button>
              </a-space>
            </div>

            <div class="username-manager-form">
              <a-input
                v-model:value="usernameAliasDrafts[item.username]"
                :placeholder="uf.aliasPlaceholder"
              />
              <a-button
                size="small"
                type="primary"
                :loading="usernameManagerSavingKey === `${item.username}:alias`"
                @click="saveUsernameAlias(item)"
              >
                {{ uf.saveDisplayName }}
              </a-button>
            </div>
          </div>
          <a-empty v-if="!filteredUsernameDirectoryItems.length" :description="uf.noMatchedUsernames" />
        </div>
      </div>
    </a-modal>
  </a-spin>
</template>

<script setup>
import { useUserFeedPage } from '../composables/useUserFeedPage';

const {
  activeTab,
  activeTabLabel,
  avatarLetter,
  bootstrapping,
  clearSelectedItem,
  closeUsernameManager,
  closeEditModal,
  closeImagePreview,
  currentPreviewImage,
  displayedTimelineUserCards,
  editState,
  encodeOutputPath,
  filterUsernameOption,
  filteredFeedItems,
  filteredUsernameDirectoryItems,
  formatDateTime,
  formatCrawledTime,
  goBackOrDashboard,
  handleUsernameChange,
  hasMoreFeedItems,
  hasNextDetail,
  hasPrevDetail,
  hideFeedVideo,
  includeReplies,
  isDetailVideoLoaded,
  isInlineVideoLoaded,
  isStandaloneMode,
  loadDetailVideo,
  loadInlineVideo,
  loadMoreFeedItems,
  loadMoreTimelineUserCards,
  loading,
  openUsernameManager,
  openAdjacentDetail,
  openEditModal,
  openImagePreview,
  openLibrary,
  openOriginalProfile,
  openOriginalTweet,
  openTimelineUser,
  openTweetDetail,
  openTweetPage,
  openVideoPage,
  previewState,
  previewTitle,
  profileAvatarSrc,
  reload,
  remainingFeedItems,
  remainingTimelineUserCards,
  resetEditedContent,
  resolvedUsername,
  restoreHiddenVideos,
  resetUsernameEntry,
  resetTimelineAccountFilters,
  saveEditedContent,
  saveUsernameAlias,
  scrollToTop,
  selectedItem,
  selectedItemPhotos,
  selectedItemVideos,
  selectedTweetId,
  selectedUsername,
  shiftPreview,
  timelineOptions,
  timelineAccountFilter,
  timelineAccountFilterOptions,
  timelineAccountFilterSummary,
  timelineAccountKeyword,
  timelineUserCards,
  toggleUsernameHidden,
  uf,
  hasMoreTimelineUserCards,
  usernameAliasDrafts,
  usernameManagerKeyword,
  usernameManagerOpen,
  usernameManagerSavingKey,
  usernameSelectOptions,
  usernameDirectoryRefreshing,
  videoPlaceholderStyle,
  visibleFeedItems,
  usernameDirectoryReady,
} = useUserFeedPage();
</script>

<style scoped src="../styles/pages/user-feed-page.css"></style>
<style scoped>
.username-manager-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.username-manager-search {
  width: 100%;
}

.username-manager-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow: auto;
}

.username-manager-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 14px 16px;
  background: #fbfdf9;
}

.username-manager-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.username-manager-title {
  font-size: 16px;
  font-weight: 600;
  color: #112212;
}

.username-manager-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #5f6b63;
}

.username-manager-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-top: 12px;
}

.timeline-directory-shell {
  display: grid;
  gap: 16px;
}

.timeline-directory-toolbar {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(260px, 1.2fr) minmax(220px, 0.8fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid #dfe8df;
  border-radius: 18px;
  background: #ffffff;
}

.timeline-directory-toolbar-copy {
  display: grid;
  gap: 4px;
}

.timeline-directory-toolbar-copy strong {
  color: #112212;
}

.timeline-directory-toolbar-copy span {
  color: #5b685f;
  font-size: 12px;
}

.timeline-directory-toolbar-copy em {
  margin-left: 8px;
  color: #4f9956;
  font-style: normal;
  font-weight: 700;
}

.timeline-refresh-tag {
  margin-left: 8px;
}

.timeline-directory-filter {
  min-width: 0;
}

.timeline-directory-search {
  width: 100%;
}

.timeline-directory-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.timeline-directory-card {
  border: 1px solid #dfe8df;
  border-radius: 22px;
  background: linear-gradient(180deg, #ffffff, #f7fbf7);
  padding: 18px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 14px;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.timeline-directory-card:hover {
  transform: translateY(-2px);
  border-color: #9fd3ae;
  box-shadow: 0 18px 40px rgba(17, 17, 17, 0.07);
}

.timeline-directory-head {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
}

.timeline-directory-avatar {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: #eaf6ec;
  color: #153b1b;
  font-weight: 700;
}

.timeline-directory-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.timeline-directory-copy {
  min-width: 0;
}

.timeline-directory-name {
  font-size: 18px;
  font-weight: 700;
  color: #112212;
}

.timeline-directory-handle {
  margin-top: 4px;
  color: #5b685f;
  font-size: 13px;
}

.timeline-directory-time {
  text-align: right;
  font-size: 12px;
  color: #5b685f;
}

.timeline-directory-time strong {
  display: block;
  margin-top: 4px;
  color: #112212;
  font-size: 13px;
}

.timeline-directory-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.timeline-directory-stat {
  padding: 8px 10px;
  border-radius: 999px;
  background: #eef8f0;
  color: #204228;
  font-size: 12px;
}

.timeline-directory-preview {
  color: #233128;
  line-height: 1.6;
  font-size: 14px;
  min-height: 44px;
}

.timeline-directory-load-more {
  margin-top: 14px;
}

@media (max-width: 720px) {
  .username-manager-head,
  .username-manager-form {
    display: flex;
    flex-direction: column;
  }

  .timeline-directory-toolbar {
    grid-template-columns: 1fr;
  }

  .timeline-directory-head {
    grid-template-columns: 56px minmax(0, 1fr);
  }

  .timeline-directory-time {
    grid-column: 1 / -1;
    text-align: left;
  }
}
</style>
