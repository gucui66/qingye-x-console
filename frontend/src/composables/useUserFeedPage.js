import { message } from 'ant-design-vue';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { api } from '../lib/api';
import { encodeOutputPath, formatDateTime } from '../lib/formatters';
import { currentLanguage } from '../lib/i18n';
import { USER_FEED_LIMIT, prepareFeedPayload, resolveFeedVideoRouteKey } from '../lib/user-feed';
import { useWorkbenchStore } from '../store/workbench';
import { useImagePreview } from './useImagePreview';
import { useUsernameOptions } from './useUsernameOptions';

const INITIAL_VISIBLE_ITEMS = 50;
const VISIBLE_ITEM_STEP = 50;
const INITIAL_VISIBLE_ACCOUNTS = 40;
const VISIBLE_ACCOUNT_STEP = 40;

const userFeedMessages = {
  'zh-CN': {
    all: '全部',
    videos: '视频',
    photos: '图片',
    text: '正文',
    allWithCount: (count) => `全部 ${count}`,
    recentWithCount: (count) => `近 30 天 ${count}`,
    videosWithCount: (count) => `有视频 ${count}`,
    photosWithCount: (count) => `有图片 ${count}`,
    mediaOnlyWithCount: (count) => `仅媒体库 ${count}`,
    accountSummary: (visible, total) => `${visible} / ${total} 个账号`,
    imagePreview: '图片预览',
    crawledUnknown: '采集时间未知',
    batch: '批次',
    mediaFile: '媒体文件',
    loadFailed: '用户主页加载失败',
    missingPostInfo: '缺少推文信息，无法保存',
    contentSaved: '正文已保存为本地覆盖',
    contentSaveFailed: '正文保存失败',
    originalRestored: '已恢复原始正文',
    restoreOriginalFailed: '恢复原文失败',
    missingVideoInfo: '缺少视频信息，无法隐藏',
    videoHidden: '已从时间流隐藏该视频，文件仍保留',
    hideVideoFailed: '隐藏视频失败',
    hiddenVideosRestored: '已恢复这条推文隐藏的视频',
    restoreHiddenVideosFailed: '恢复隐藏视频失败',
    aliasSaved: '显示名已保存',
    aliasSaveFailed: '保存显示名失败',
    usernameHidden: '用户名已隐藏',
    usernameVisible: '用户名已恢复显示',
    hideUsernameFailed: '隐藏用户名失败',
    restoreUsernameFailed: '恢复用户名失败',
    usernameSettingsCleared: '已清空这个用户名的自定义设置',
    clearSettingsFailed: '清空设置失败',
    back: '← 返回',
    userHome: '用户主页',
    feedSubtitle: (visible, total, tab, replies) => `${visible} / ${total} 条 · ${tab} · ${replies ? '含回复' : '隐藏回复'}`,
    directorySubtitle: (count) => `${count} 个已采集账号 · 按最近采集时间排序`,
    syncing: '后台同步中',
    replies: '回复',
    retweets: '转推',
    likes: '喜欢',
    switchUser: '切换用户',
    loadingDirectory: '正在加载用户目录...',
    manageUsernames: '管理用户名',
    library: '资料库',
    xProfile: 'X 主页',
    loadingDirectoryWait: '正在加载用户名目录，请稍等',
    directoryHint: '按最近采集时间排列，先筛账号再进入详情。',
    syncHint: '正在同步最新账号目录，不影响浏览。',
    searchAccountsPlaceholder: '搜索账号、昵称或预览内容',
    clearFilters: '清空筛选',
    lastCollected: '最近采集',
    noCollectionRecord: '暂无采集记录',
    latestCount: (count) => `本次 ${count}`,
    totalCount: (count) => `累计 ${count}`,
    photoCount: (count) => `图片 ${count}`,
    videoCount: (count) => `视频 ${count}`,
    noPreview: '最近采集内容暂无预览',
    noAccounts: '当前筛选下没有可展示账号',
    loadMoreAccounts: (count) => `加载更多 ${count} 个账号`,
    tweetStream: '推文流',
    edited: '已编辑',
    publishUnknown: '发布时间未知',
    publishTime: (time) => `发布时间：${time}`,
    crawledTime: (time) => `采集时间：${time}`,
    replyPost: '回复贴文',
    originalPost: '原贴文',
    edit: '编辑',
    quickDetail: '快速详情',
    standalonePage: '独立页',
    noContentMediaOnly: '这条内容没有抓到正文，当前以媒体为主展示。',
    replyContext: (text) => `回复上下文：${text}`,
    loadLocalVideoPreview: '点击加载本地视频预览',
    videoLazyLoadHint: '不提前创建播放器，列表会更流畅',
    standalonePlay: '独立播放',
    hideVideoConfirm: '仅从时间流隐藏这个视频，不会删除文件。确定隐藏吗？',
    hide: '隐藏',
    cancel: '取消',
    remoteVideosFound: (count) => `识别到 ${count} 个远程视频，但本地暂时还没有落盘文件。`,
    replyCount: (count) => `${count} 回复`,
    retweetCount: (count) => `${count} 转推`,
    likeCount: (count) => `${count} 喜欢`,
    mediaCount: (count) => `${count} 媒体资源`,
    restoreHiddenVideoCount: (count) => `已隐藏 ${count} 个视频 · 恢复`,
    loadMorePosts: (count) => `加载更多 ${count} 条`,
    noPosts: '这个用户当前还没有可展示的贴文流内容',
    postDetail: '贴文详情',
    localEdited: '本地已编辑',
    loadDetailVideo: '点击加载详情视频',
    detailVideoLazyHint: '详情抽屉打开时不会自动抢占带宽',
    remoteVideosNotDownloaded: (count) => `这条内容识别到了 ${count} 个远程视频，但本地还没有下载文件。`,
    localMedia: '本地媒体',
    editText: '编辑正文',
    restoreOriginalConfirm: '删除本地文字覆盖，恢复原始抓取正文？',
    restore: '恢复',
    restoreOriginal: '恢复原文',
    restoreHiddenVideos: '恢复隐藏视频',
    openLibrary: '打开资料库',
    openOriginalPost: '打开原贴文',
    standaloneDetail: '独立详情页',
    previous: '上一条',
    next: '下一条',
    editPostText: '编辑推文正文',
    saveText: '保存文字',
    editNote: '这里保存的是本地覆盖文字，不会改动原始抓取缓存；清空后保存会让这条推文显示为空正文。',
    editPlaceholder: '输入要在用户时间流展示的正文',
    imageIndex: (current, total) => `第 ${current} / ${total} 张`,
    previousImage: '上一张',
    nextImage: '下一张',
    usernameManager: '用户名管理',
    searchUsernamePlaceholder: '搜索用户名或显示名',
    hidden: '已隐藏',
    visible: '显示中',
    clearSettings: '清空设置',
    aliasPlaceholder: '自定义显示名，不填就继续用原用户名',
    saveDisplayName: '保存显示名',
    noMatchedUsernames: '没有匹配到用户名',
  },
  en: {
    all: 'All',
    videos: 'Videos',
    photos: 'Photos',
    text: 'Text',
    allWithCount: (count) => `All ${count}`,
    recentWithCount: (count) => `Last 30 days ${count}`,
    videosWithCount: (count) => `With videos ${count}`,
    photosWithCount: (count) => `With photos ${count}`,
    mediaOnlyWithCount: (count) => `Media library only ${count}`,
    accountSummary: (visible, total) => `${visible} / ${total} accounts`,
    imagePreview: 'Image Preview',
    crawledUnknown: 'Collection time unknown',
    batch: 'batch',
    mediaFile: 'media file',
    loadFailed: 'Failed to load user timeline',
    missingPostInfo: 'Missing post information. Cannot save.',
    contentSaved: 'Text saved as a local override',
    contentSaveFailed: 'Failed to save text',
    originalRestored: 'Original text restored',
    restoreOriginalFailed: 'Failed to restore original text',
    missingVideoInfo: 'Missing video information. Cannot hide.',
    videoHidden: 'Video hidden from timeline. The file is still kept.',
    hideVideoFailed: 'Failed to hide video',
    hiddenVideosRestored: 'Hidden videos restored for this post',
    restoreHiddenVideosFailed: 'Failed to restore hidden videos',
    aliasSaved: 'Display name saved',
    aliasSaveFailed: 'Failed to save display name',
    usernameHidden: 'Username hidden',
    usernameVisible: 'Username restored',
    hideUsernameFailed: 'Failed to hide username',
    restoreUsernameFailed: 'Failed to restore username',
    usernameSettingsCleared: 'Custom settings cleared for this username',
    clearSettingsFailed: 'Failed to clear settings',
    back: '← Back',
    userHome: 'User Timeline',
    feedSubtitle: (visible, total, tab, replies) => `${visible} / ${total} posts · ${tab} · ${replies ? 'with replies' : 'replies hidden'}`,
    directorySubtitle: (count) => `${count} collected accounts · sorted by latest collection time`,
    syncing: 'Syncing',
    replies: 'Replies',
    retweets: 'Reposts',
    likes: 'Likes',
    switchUser: 'Switch user',
    loadingDirectory: 'Loading user directory...',
    manageUsernames: 'Manage usernames',
    library: 'Library',
    xProfile: 'X Profile',
    loadingDirectoryWait: 'Loading the username directory. Please wait.',
    directoryHint: 'Sorted by latest collection time. Filter an account, then open its timeline.',
    syncHint: 'Syncing the latest account directory. Browsing is not blocked.',
    searchAccountsPlaceholder: 'Search account, name, or preview',
    clearFilters: 'Clear filters',
    lastCollected: 'Last collected',
    noCollectionRecord: 'No collection record',
    latestCount: (count) => `Latest ${count}`,
    totalCount: (count) => `Total ${count}`,
    photoCount: (count) => `Photos ${count}`,
    videoCount: (count) => `Videos ${count}`,
    noPreview: 'No recent preview available',
    noAccounts: 'No accounts match the current filters',
    loadMoreAccounts: (count) => `Load ${count} more accounts`,
    tweetStream: 'Post stream',
    edited: 'Edited',
    publishUnknown: 'Publish time unknown',
    publishTime: (time) => `Published: ${time}`,
    crawledTime: (time) => `Collected: ${time}`,
    replyPost: 'Reply post',
    originalPost: 'Original post',
    edit: 'Edit',
    quickDetail: 'Quick details',
    standalonePage: 'Standalone page',
    noContentMediaOnly: 'No text was captured for this post. Showing media-first content.',
    replyContext: (text) => `Reply context: ${text}`,
    loadLocalVideoPreview: 'Load local video preview',
    videoLazyLoadHint: 'Players are created on demand so the list stays smooth',
    standalonePlay: 'Standalone player',
    hideVideoConfirm: 'Hide this video from the timeline only. The file will not be deleted. Continue?',
    hide: 'Hide',
    cancel: 'Cancel',
    remoteVideosFound: (count) => `${count} remote videos detected, but no local files are available yet.`,
    replyCount: (count) => `${count} replies`,
    retweetCount: (count) => `${count} reposts`,
    likeCount: (count) => `${count} likes`,
    mediaCount: (count) => `${count} media`,
    restoreHiddenVideoCount: (count) => `${count} hidden videos · restore`,
    loadMorePosts: (count) => `Load ${count} more posts`,
    noPosts: 'This user has no timeline posts to display yet',
    postDetail: 'Post Details',
    localEdited: 'Locally edited',
    loadDetailVideo: 'Load detail video',
    detailVideoLazyHint: 'The detail drawer will not pre-load video bandwidth',
    remoteVideosNotDownloaded: (count) => `${count} remote videos were detected for this post, but no local files are downloaded yet.`,
    localMedia: 'Local media',
    editText: 'Edit text',
    restoreOriginalConfirm: 'Remove the local text override and restore the original captured text?',
    restore: 'Restore',
    restoreOriginal: 'Restore original',
    restoreHiddenVideos: 'Restore hidden videos',
    openLibrary: 'Open library',
    openOriginalPost: 'Open original post',
    standaloneDetail: 'Standalone detail',
    previous: 'Previous',
    next: 'Next',
    editPostText: 'Edit Post Text',
    saveText: 'Save text',
    editNote: 'This saves a local text override only. It does not modify the original crawl cache. Saving empty text will make this post display without body text.',
    editPlaceholder: 'Enter the text to display in User Timeline',
    imageIndex: (current, total) => `${current} / ${total}`,
    previousImage: 'Previous image',
    nextImage: 'Next image',
    usernameManager: 'Username Manager',
    searchUsernamePlaceholder: 'Search username or display name',
    hidden: 'Hidden',
    visible: 'Visible',
    clearSettings: 'Clear settings',
    aliasPlaceholder: 'Custom display name. Leave empty to keep the original username.',
    saveDisplayName: 'Save display name',
    noMatchedUsernames: 'No usernames matched',
  },
};

export function useUserFeedPage() {
  const route = useRoute();
  const router = useRouter();
  const store = useWorkbenchStore();

  const loading = ref(false);
  const bootstrapping = ref(false);
  const selectedUsername = ref('');
  const activeTab = ref('all');
  const timelineAccountFilter = ref('all');
  const timelineAccountKeyword = ref('');
  const includeReplies = ref(true);
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
  const loadedVideoKeys = reactive({});
  const visibleItemCount = ref(INITIAL_VISIBLE_ITEMS);
  const visibleTimelineAccountCount = ref(INITIAL_VISIBLE_ACCOUNTS);
  const usernameManagerOpen = ref(false);
  const usernameManagerKeyword = ref('');
  const usernameManagerSavingKey = ref('');
  const usernameAliasDrafts = reactive({});
  const editState = reactive({
    open: false,
    saving: false,
    username: '',
    tweetId: '',
    content: '',
  });
  let reloadRequestToken = 0;

  const uf = computed(() => userFeedMessages[currentLanguage.value] || userFeedMessages['zh-CN']);
  const timelineOptions = computed(() => [
    { label: uf.value.all, value: 'all' },
    { label: uf.value.videos, value: 'videos' },
    { label: uf.value.photos, value: 'photos' },
    { label: uf.value.text, value: 'text' },
  ]);
  const routeUsername = computed(() => String(route.params.username || route.query.username || '').trim());
  const selectedTweetId = computed(() => String(route.query.post || '').trim());
  const isStandaloneMode = computed(() => Boolean(route.meta?.standalone));
  const resolvedUsername = computed(() => String(payload.value.username || routeUsername.value || selectedUsername.value || '').trim());
  const avatarLetter = computed(() => resolvedUsername.value.slice(0, 1).toUpperCase() || 'X');
  const preparedPayload = computed(() => prepareFeedPayload(payload.value));
  const feedItems = computed(() => preparedPayload.value.items || []);
  const profileAvatarSrc = computed(() => String(payload.value.profile?.avatar_url || '').trim());
  const { filterUsernameOption, usernameSelectOptions } = useUsernameOptions(store);
  const usernameDirectoryItems = computed(() => store.usernameDirectoryItems.value || []);
  const usernameDirectoryReady = computed(() => {
    return store.state.authReady
      && (!store.state.loading.usernameDirectory || Boolean(usernameDirectoryItems.value.length));
  });
  const usernameDirectoryRefreshing = computed(() => {
    return store.state.loading.usernameDirectory && Boolean(usernameDirectoryItems.value.length);
  });
  const visibleTimelineUserCards = computed(() => {
    return (usernameDirectoryItems.value || []).filter((item) => !item.hidden);
  });
  const timelineAccountFilterOptions = computed(() => {
    const items = visibleTimelineUserCards.value;
    const recentThreshold = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return [
      { label: uf.value.allWithCount(items.length), value: 'all' },
      { label: uf.value.recentWithCount(items.filter((item) => Number(item.last_crawled_ts || 0) * 1000 >= recentThreshold).length), value: 'recent' },
      { label: uf.value.videosWithCount(items.filter((item) => Number(item.videos || 0) > 0).length), value: 'videos' },
      { label: uf.value.photosWithCount(items.filter((item) => Number(item.photos || 0) > 0).length), value: 'photos' },
      {
        label: uf.value.mediaOnlyWithCount(items.filter((item) =>
          Number(item.latest_tweet_count || 0) <= 0
          && (Number(item.videos || 0) + Number(item.photos || 0)) > 0
        ).length),
        value: 'media_only',
      },
    ];
  });
  const timelineUserCards = computed(() => {
    const keyword = String(timelineAccountKeyword.value || '').trim().toLowerCase();
    const recentThreshold = Date.now() - 30 * 24 * 60 * 60 * 1000;

    return visibleTimelineUserCards.value.filter((item) => {
      if (keyword) {
        const matched = [
          item.username,
          item.display_name,
          item.author_name,
          item.alias,
          item.latest_preview,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword));
        if (!matched) {
          return false;
        }
      }

      if (timelineAccountFilter.value === 'recent') {
        return Number(item.last_crawled_ts || 0) * 1000 >= recentThreshold;
      }
      if (timelineAccountFilter.value === 'videos') {
        return Number(item.videos || 0) > 0;
      }
      if (timelineAccountFilter.value === 'photos') {
        return Number(item.photos || 0) > 0;
      }
      if (timelineAccountFilter.value === 'media_only') {
        return Number(item.latest_tweet_count || 0) <= 0
          && (Number(item.videos || 0) + Number(item.photos || 0)) > 0;
      }
      return true;
    });
  });
  const timelineAccountFilterSummary = computed(() => {
    return uf.value.accountSummary(timelineUserCards.value.length, visibleTimelineUserCards.value.length);
  });
  const displayedTimelineUserCards = computed(() => {
    // 账号目录可能随着历史任务变多而变大，首页先分批渲染，避免首屏 DOM 太重。
    return timelineUserCards.value.slice(0, visibleTimelineAccountCount.value);
  });
  const hasMoreTimelineUserCards = computed(() => displayedTimelineUserCards.value.length < timelineUserCards.value.length);
  const remainingTimelineUserCards = computed(() => Math.max(0, timelineUserCards.value.length - displayedTimelineUserCards.value.length));
  const filteredUsernameDirectoryItems = computed(() => {
    const keyword = String(usernameManagerKeyword.value || '').trim().toLowerCase();
    return usernameDirectoryItems.value.filter((item) => {
      if (!keyword) {
        return true;
      }
      return [
        item.username,
        item.display_name,
        item.alias,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    });
  });

  const filteredFeedItems = computed(() => {
    return feedItems.value.filter((item) => {
      if (!includeReplies.value && item.is_reply) {
        return false;
      }

      if (activeTab.value === 'videos') {
        return item.hasVideos;
      }
      if (activeTab.value === 'photos') {
        return item.hasPhotos;
      }
      if (activeTab.value === 'text') {
        return item.hasText;
      }
      return true;
    });
  });
  const visibleFeedItems = computed(() => filteredFeedItems.value.slice(0, visibleItemCount.value));
  const hasMoreFeedItems = computed(() => visibleFeedItems.value.length < filteredFeedItems.value.length);
  const remainingFeedItems = computed(() => Math.max(0, filteredFeedItems.value.length - visibleFeedItems.value.length));

  const detailTimeline = computed(() => {
    if (selectedTweetId.value && filteredFeedItems.value.some((item) => String(item.id) === selectedTweetId.value)) {
      return filteredFeedItems.value;
    }
    return feedItems.value;
  });

  const selectedItem = computed(() => {
    return feedItems.value.find((item) => String(item.id) === selectedTweetId.value) || null;
  });

  const selectedItemIndex = computed(() => {
    return detailTimeline.value.findIndex((item) => String(item.id) === selectedTweetId.value);
  });

  const hasPrevDetail = computed(() => selectedItemIndex.value > 0);
  const hasNextDetail = computed(() => selectedItemIndex.value >= 0 && selectedItemIndex.value < detailTimeline.value.length - 1);
  const selectedItemPhotos = computed(() => selectedItem.value?.photos || []);
  const selectedItemVideos = computed(() => selectedItem.value?.local_videos || []);

  const activeTabLabel = computed(() => {
    return timelineOptions.value.find((item) => item.value === activeTab.value)?.label || uf.value.all;
  });

  async function ensureFeedBootstrap() {
    if (!store.state.authReady) {
      await store.refreshSession();
    }

    if (!isStandaloneMode.value && !routeUsername.value && !store.sortedTasks.value.length) {
      await store.loadTasks();
    }

    if (store.state.auth.isAdmin && !store.usernameDirectoryItems.value?.length) {
      await store.loadUsernameDirectory({ silent: true, allowStale: true });
    }
  }

  const previewTitle = computed(() => {
    if (!resolvedUsername.value) {
      return uf.value.imagePreview;
    }
    return `@${resolvedUsername.value} · ${uf.value.imagePreview}`;
  });

  function videoTileKey(scope, item, index) {
    const id = String(item?.id || item?.tweet_id || 'tweet');
    const video = item?.local_videos?.[index];
    const routeKey = String(video?.route_key || resolveFeedVideoRouteKey(item, index));
    return `${scope}:${id}:${routeKey}`;
  }

  function isInlineVideoLoaded(item, index) {
    return Boolean(loadedVideoKeys[videoTileKey('inline', item, index)]);
  }

  function isDetailVideoLoaded(item, index) {
    return Boolean(loadedVideoKeys[videoTileKey('detail', item, index)]);
  }

  function loadInlineVideo(item, index) {
    loadedVideoKeys[videoTileKey('inline', item, index)] = true;
  }

  function loadDetailVideo(item, index) {
    loadedVideoKeys[videoTileKey('detail', item, index)] = true;
  }

  function resetLoadedVideos() {
    Object.keys(loadedVideoKeys).forEach((key) => {
      delete loadedVideoKeys[key];
    });
  }

  function resetVisibleFeed() {
    visibleItemCount.value = INITIAL_VISIBLE_ITEMS;
  }

  function loadMoreFeedItems() {
    visibleItemCount.value += VISIBLE_ITEM_STEP;
  }

  function resetVisibleTimelineAccounts() {
    visibleTimelineAccountCount.value = INITIAL_VISIBLE_ACCOUNTS;
  }

  function loadMoreTimelineUserCards() {
    visibleTimelineAccountCount.value += VISIBLE_ACCOUNT_STEP;
  }

  function resetTimelineAccountFilters() {
    timelineAccountFilter.value = 'all';
    timelineAccountKeyword.value = '';
  }

  function videoPlaceholderStyle(video = {}) {
    if (!video.thumbnail_src) {
      return {};
    }
    return {
      backgroundImage: `linear-gradient(180deg, rgba(12, 24, 14, 0.1), rgba(12, 24, 14, 0.58)), url("${video.thumbnail_src}")`,
    };
  }

  function formatCrawledTime(item = {}) {
    const value = formatDateTime(item.crawled_at, uf.value.crawledUnknown);
    if (!item.crawled_at) {
      return value;
    }
    // 后端会标记采集时间来源，避免把批次时间误读成单条推文的精确采集时间。
    if (item.crawled_at_source === 'raw_file') {
      return currentLanguage.value === 'en' ? `${value} (${uf.value.batch})` : `${value}（${uf.value.batch}）`;
    }
    if (item.crawled_at_source === 'media_file') {
      return currentLanguage.value === 'en' ? `${value} (${uf.value.mediaFile})` : `${value}（${uf.value.mediaFile}）`;
    }
    return value;
  }

  function buildUserFeedRoute(queryOverrides = {}, usernameOverride = null) {
    const username = String(usernameOverride || resolvedUsername.value || routeUsername.value || '').trim();
    const query = {
      ...route.query,
      ...queryOverrides,
    };

    Object.keys(query).forEach((key) => {
      if (query[key] === undefined || query[key] === null || query[key] === '') {
        delete query[key];
      }
    });

    return {
      name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
      params: username ? { username } : {},
      query,
    };
  }

  async function reload(options = {}) {
    bootstrapping.value = true;
    await ensureFeedBootstrap();

    const currentUsername = routeUsername.value.trim();
    if (!currentUsername) {
      selectedUsername.value = '';
      payload.value = {
        username: '',
        source_file: '',
        items: [],
        summary: {},
      };
      bootstrapping.value = false;
      return;
    }

    const requestToken = ++reloadRequestToken;
    loading.value = true;
    try {
      selectedUsername.value = currentUsername;
      await store.loadUsernameDirectory({ silent: true, allowStale: true });
      const nextPayload = await api.getAdminUserFeed(currentUsername, USER_FEED_LIMIT, {
        force: Boolean(options.force),
      });
      if (requestToken !== reloadRequestToken) {
        return;
      }
      payload.value = nextPayload;
    } catch (error) {
      if (requestToken !== reloadRequestToken) {
        return;
      }
      message.error(error.message || uf.value.loadFailed);
    } finally {
      if (requestToken === reloadRequestToken) {
        loading.value = false;
      }
      bootstrapping.value = false;
    }
  }

  function syncUsernameAliasDrafts() {
    usernameDirectoryItems.value.forEach((item) => {
      if (!(item.username in usernameAliasDrafts)) {
        usernameAliasDrafts[item.username] = item.alias || '';
      }
    });
  }

  function openEditModal(item) {
    if (!item?.id) {
      return;
    }
    editState.username = item.username || resolvedUsername.value;
    editState.tweetId = String(item.id);
    editState.content = item.content || '';
    editState.open = true;
  }

  function closeEditModal() {
    if (editState.saving) {
      return;
    }
    editState.open = false;
    editState.username = '';
    editState.tweetId = '';
    editState.content = '';
  }

  async function saveEditedContent() {
    if (!editState.username || !editState.tweetId) {
      message.error(uf.value.missingPostInfo);
      return;
    }

    editState.saving = true;
    try {
      await api.updateUserFeedPostContent(editState.username, editState.tweetId, editState.content);
      message.success(uf.value.contentSaved);
      editState.open = false;
      await reload({ force: true });
    } catch (error) {
      message.error(error.message || uf.value.contentSaveFailed);
    } finally {
      editState.saving = false;
    }
  }

  async function resetEditedContent(item) {
    const username = item?.username || resolvedUsername.value;
    const tweetId = String(item?.id || '');
    if (!username || !tweetId) {
      return;
    }

    try {
      await api.resetUserFeedPostContent(username, tweetId);
      message.success(uf.value.originalRestored);
      await reload({ force: true });
    } catch (error) {
      message.error(error.message || uf.value.restoreOriginalFailed);
    }
  }

  async function hideFeedVideo(item, video) {
    const username = item?.username || resolvedUsername.value;
    const tweetId = String(item?.id || '');
    if (!username || !tweetId || !video) {
      message.error(uf.value.missingVideoInfo);
      return;
    }

    try {
      await api.hideUserFeedVideo(username, tweetId, {
        media_id: video.id,
        media_index: video.media_index,
        path: video.path,
        name: video.name,
      });
      message.success(uf.value.videoHidden);
      resetLoadedVideos();
      await reload({ force: true });
    } catch (error) {
      message.error(error.message || uf.value.hideVideoFailed);
    }
  }

  async function restoreHiddenVideos(item) {
    const username = item?.username || resolvedUsername.value;
    const tweetId = String(item?.id || '');
    if (!username || !tweetId) {
      return;
    }

    try {
      await api.restoreUserFeedVideos(username, tweetId);
      message.success(uf.value.hiddenVideosRestored);
      resetLoadedVideos();
      await reload({ force: true });
    } catch (error) {
      message.error(error.message || uf.value.restoreHiddenVideosFailed);
    }
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

  function openOriginalProfile() {
    if (!resolvedUsername.value) {
      return;
    }
    window.open(`https://x.com/${resolvedUsername.value}`, '_blank', 'noopener,noreferrer');
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

  function handleUsernameChange(username) {
    if (!username) {
      return;
    }
    router.push({
      name: isStandaloneMode.value ? 'user-feed-standalone' : 'user-feed',
      params: { username },
    });
  }

  function openTimelineUser(item) {
    const username = item?.username || item;
    if (!username) {
      return;
    }
    handleUsernameChange(username);
  }

  async function openUsernameManager() {
    await store.loadUsernameDirectory({ silent: true, force: true });
    syncUsernameAliasDrafts();
    usernameManagerOpen.value = true;
  }

  function closeUsernameManager() {
    usernameManagerOpen.value = false;
    usernameManagerKeyword.value = '';
  }

  async function saveUsernameAlias(item) {
    const username = item?.username;
    if (!username) {
      return;
    }

    usernameManagerSavingKey.value = `${username}:alias`;
    try {
      await store.updateUsernameDirectoryEntry(username, {
        alias: usernameAliasDrafts[username] || '',
      });
      message.success(uf.value.aliasSaved);
    } catch (error) {
      message.error(error.message || uf.value.aliasSaveFailed);
    } finally {
      usernameManagerSavingKey.value = '';
    }
  }

  async function toggleUsernameHidden(item, hidden) {
    const username = item?.username;
    if (!username) {
      return;
    }

    usernameManagerSavingKey.value = `${username}:hidden`;
    try {
      await store.updateUsernameDirectoryEntry(username, { hidden });
      message.success(hidden ? uf.value.usernameHidden : uf.value.usernameVisible);
      if (hidden && resolvedUsername.value === username) {
        const nextVisible = store.usernameOptions.value.find((entry) => entry !== username);
        if (nextVisible) {
          handleUsernameChange(nextVisible);
        }
      }
    } catch (error) {
      message.error(error.message || (hidden ? uf.value.hideUsernameFailed : uf.value.restoreUsernameFailed));
    } finally {
      usernameManagerSavingKey.value = '';
    }
  }

  async function resetUsernameEntry(item) {
    const username = item?.username;
    if (!username) {
      return;
    }

    usernameManagerSavingKey.value = `${username}:reset`;
    try {
      await store.updateUsernameDirectoryEntry(username, { reset: true });
      usernameAliasDrafts[username] = '';
      message.success(uf.value.usernameSettingsCleared);
    } catch (error) {
      message.error(error.message || uf.value.clearSettingsFailed);
    } finally {
      usernameManagerSavingKey.value = '';
    }
  }

  function openTweetDetail(item) {
    if (!item?.id) {
      return;
    }
    router.replace(buildUserFeedRoute({ post: String(item.id) }, item.username));
  }

  function openTweetPage(item) {
    if (!item?.id) {
      return;
    }
    router.push({
      name: isStandaloneMode.value ? 'user-post-standalone' : 'user-post',
      params: {
        username: item.username || resolvedUsername.value,
        tweetId: String(item.id),
      },
    });
  }

  function openVideoPage(item, videoIndex = 0) {
    if (!item?.id) {
      return;
    }
    const routeKey = resolveFeedVideoRouteKey(item, videoIndex);
    router.push({
      name: isStandaloneMode.value ? 'user-video-standalone' : 'user-video',
      params: {
        username: item.username || resolvedUsername.value,
        tweetId: String(item.id),
        videoIndex: String(routeKey),
      },
    });
  }

  function clearSelectedItem() {
    router.replace(buildUserFeedRoute({ post: undefined }));
  }

  function openAdjacentDetail(delta) {
    if (selectedItemIndex.value < 0) {
      return;
    }
    const target = detailTimeline.value[selectedItemIndex.value + delta];
    if (!target) {
      return;
    }
    openTweetDetail(target);
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  watch(
    () => [route.params.username, route.query.username],
    () => {
      resetVisibleFeed();
      resetLoadedVideos();
      reload();
    }
  );

  watch(usernameDirectoryItems, () => {
    syncUsernameAliasDrafts();
  }, { immediate: true });

  watch(
    () => [activeTab.value, includeReplies.value],
    () => {
      resetVisibleFeed();
      resetLoadedVideos();
    }
  );

  watch(
    () => [timelineAccountFilter.value, timelineAccountKeyword.value],
    () => {
      resetVisibleTimelineAccounts();
    }
  );

  onMounted(() => {
    reload();
  });

  return {
    activeTab,
    activeTabLabel,
    uf,
    avatarLetter,
    clearSelectedItem,
    closeUsernameManager,
    closeEditModal,
    closeImagePreview,
    currentPreviewImage,
    editState,
    encodeOutputPath,
    filterUsernameOption,
    displayedTimelineUserCards,
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
    bootstrapping,
    openUsernameManager,
    openAdjacentDetail,
    openEditModal,
    openImagePreview,
    openLibrary,
    openOriginalProfile,
    openOriginalTweet,
    openTweetDetail,
    openTweetPage,
    openTimelineUser,
    openVideoPage,
    previewState,
    previewTitle,
    profileAvatarSrc,
    reload,
    remainingFeedItems,
    resetEditedContent,
    remainingTimelineUserCards,
    resolvedUsername,
    restoreHiddenVideos,
    saveEditedContent,
    scrollToTop,
    selectedItem,
    selectedItemPhotos,
    selectedItemVideos,
    selectedTweetId,
    selectedUsername,
    shiftPreview,
    resetUsernameEntry,
    resetTimelineAccountFilters,
    saveUsernameAlias,
    timelineAccountFilter,
    timelineAccountFilterOptions,
    timelineAccountFilterSummary,
    timelineAccountKeyword,
    timelineOptions,
    toggleUsernameHidden,
    hasMoreTimelineUserCards,
    usernameSelectOptions,
    usernameAliasDrafts,
    usernameDirectoryItems,
    usernameDirectoryReady,
    usernameDirectoryRefreshing,
    timelineUserCards,
    usernameManagerKeyword,
    usernameManagerOpen,
    usernameManagerSavingKey,
    videoPlaceholderStyle,
    visibleFeedItems,
  };
}
