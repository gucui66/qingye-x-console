<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card class="panel-card">
      <a-row :gutter="[16, 16]" align="middle" class="page-filter-row">
        <a-col :xs="24" :lg="8">
          <a-select
            v-model:value="selectedUsername"
            class="page-filter-control"
            style="width: 100%"
            placeholder="选择账号资料库"
            :options="usernameSelectOptions"
            @change="reloadLibrary"
          />
        </a-col>
        <a-col :xs="24" :lg="6">
          <a-input-search
            v-model:value="keyword"
            class="page-filter-control"
            placeholder="搜索文件名 / tweet id"
            allow-clear
          />
        </a-col>
        <a-col :xs="24" :lg="5">
          <a-select v-model:value="statusFilter" class="page-filter-control" style="width: 100%" :options="statusOptions" />
        </a-col>
        <a-col :xs="24" :lg="5">
          <a-select v-model:value="sortBy" class="page-filter-control" style="width: 100%" :options="sortOptions" />
        </a-col>
      </a-row>
      <div v-if="selectedTaskId" class="table-sub-note" style="margin-top: 12px">
        当前正在查看任务产物：<strong>{{ selectedTaskId }}</strong>
      </div>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="8">
        <a-card class="panel-card"><a-statistic title="视频" :value="videos.length" /></a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card class="panel-card"><a-statistic title="收藏视频" :value="favoriteVideos.length" /></a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card class="panel-card"><a-statistic title="异常视频" :value="anomalyCount" /></a-card>
      </a-col>
    </a-row>

    <a-card class="panel-card" :loading="store.state.loading.library">
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="videos" tab="视频中心">
          <div class="library-summary-strip">
            <div class="tasks-summary-pill">
              <span>当前资料库</span>
              <strong :title="selectedUsername ? `@${selectedUsername}` : '全部账号资料'">
                {{ selectedUsername ? `@${selectedUsername}` : '全部账号资料' }}
              </strong>
            </div>
            <button
              v-if="selectedUsername"
              type="button"
              class="feed-inline-avatar"
              @click="goUserFeed(selectedUsername)"
            >
              {{ String(selectedUsername || '').slice(0, 1).toUpperCase() }}
            </button>
            <div v-if="selectedTaskId" class="tasks-summary-pill">
              <span>当前任务</span>
              <strong :title="selectedTaskId">{{ selectedTaskId }}</strong>
            </div>
            <div class="tasks-summary-pill">
              <span>当前排序</span>
              <strong>{{ activeSortLabel }}</strong>
            </div>
            <div class="tasks-summary-pill">
              <span>当前筛选</span>
              <strong>{{ activeStatusLabel }}</strong>
            </div>
          </div>

          <div class="tasks-quick-actions">
            <a-button size="small" @click="selectPrevVideo" :disabled="!previousVideo">上一个视频</a-button>
            <a-button size="small" @click="selectNextVideo" :disabled="!nextVideo">下一个视频</a-button>
            <a-button size="small" @click="jumpToFirstUnwatched" :disabled="!firstUnwatchedVideo">
              第一个未看
            </a-button>
            <a-button size="small" @click="showFavoritesOnly">
              只看收藏
            </a-button>
            <a-button size="small" @click="clearLibraryFilters">
              清空筛选
            </a-button>
          </div>

          <div class="library-current-strip" v-if="selectedVideo">
            <div class="tasks-summary-pill">
              <span>当前选中</span>
              <strong :title="selectedVideo.name">{{ selectedVideo.name }}</strong>
            </div>
            <div class="tasks-summary-pill">
              <span>来源账号</span>
              <strong :title="selectedVideo.username ? `@${selectedVideo.username}` : '全部资料'">
                {{ selectedVideo.username ? `@${selectedVideo.username}` : '全部资料' }}
              </strong>
            </div>
            <div class="tasks-summary-pill">
              <span>观看状态</span>
              <strong>{{ selectedVideo.annotations?.watched ? '已看' : '未看' }}</strong>
            </div>
          </div>

          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :xl="12">
              <a-table
                class="interactive-table"
                :columns="videoColumns"
                :data-source="videos"
                :pagination="{ pageSize: 8 }"
                :row-class-name="rowClassName"
                row-key="path"
                :custom-row="videoRow"
                :scroll="{ x: 720 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <div class="library-file-name" :title="record.name">{{ record.name }}</div>
                    <div class="table-sub-note file-subline" :title="record.tweet_id || record.path">
                      {{ record.tweet_id || record.path }}
                    </div>
                  </template>
                  <template v-else-if="column.key === 'flags'">
                    <a-space wrap>
                      <a-tag v-if="record.annotations?.favorite" color="green">收藏</a-tag>
                      <a-tag v-if="record.annotations?.watched" color="green">已看</a-tag>
                      <a-tag v-if="record.annotations?.watch_later" color="gold">稍后看</a-tag>
                    </a-space>
                  </template>
                  <template v-else-if="column.key === 'size'">
                    {{ formatFileSize(record.size) }}
                  </template>
                  <template v-else-if="column.key === 'modified_at'">
                    {{ formatVideoDate(record.modified_at) }}
                  </template>
                </template>
              </a-table>
            </a-col>

            <a-col :xs="24" :xl="12">
              <a-card class="video-preview-pane panel-card library-preview-card">
                <template #title>
                  <div class="preview-title-wrap">
                    <div class="preview-title" :title="selectedVideo?.name || '视频预览'">
                      {{ selectedVideo?.name || '视频预览' }}
                    </div>
                    <div v-if="selectedVideo" class="preview-subtitle" :title="selectedVideo.tweet_id || selectedVideo.path">
                      {{ selectedVideo.tweet_id || selectedVideo.path }}
                    </div>
                  </div>
                </template>
                <template v-if="selectedVideo">
                  <video
                    ref="videoRef"
                    :key="selectedVideo.path"
                    class="library-video-player"
                    controls
                    preload="metadata"
                    :poster="buildThumbnailSrc(selectedVideo) || undefined"
                    :src="encodeOutputPath(selectedVideo.path)"
                    @pause="persistPlayback"
                    @ended="markWatched"
                  ></video>

                  <a-space wrap style="margin-bottom: 16px">
                    <a-button @click="selectPrevVideo" :disabled="!previousVideo">上一个</a-button>
                    <a-button @click="selectNextVideo" :disabled="!nextVideo">下一个</a-button>
                    <a-button type="primary" :href="encodeOutputPath(selectedVideo.path)" target="_blank">
                      打开播放
                    </a-button>
                    <a-button :href="encodeOutputPath(selectedVideo.path)" download>
                      下载
                    </a-button>
                    <a-button
                      v-if="selectedVideo.tweet_url"
                      :href="selectedVideo.tweet_url"
                      target="_blank"
                    >
                      来源推文
                    </a-button>
                  </a-space>

                  <a-space wrap style="margin-bottom: 16px">
                    <a-button size="small" @click="toggleAnnotation('favorite', !selectedVideo.annotations?.favorite)" :disabled="!canAnnotate">
                      {{ selectedVideo.annotations?.favorite ? '取消收藏' : '加入收藏' }}
                    </a-button>
                    <a-button size="small" @click="toggleAnnotation('watched', !selectedVideo.annotations?.watched)" :disabled="!canAnnotate">
                      {{ selectedVideo.annotations?.watched ? '标记未看' : '标记已看' }}
                    </a-button>
                    <a-button size="small" @click="toggleAnnotation('watch_later', !selectedVideo.annotations?.watch_later)" :disabled="!canAnnotate">
                      {{ selectedVideo.annotations?.watch_later ? '移出稍后看' : '加入稍后看' }}
                    </a-button>
                  </a-space>

                  <a-descriptions :column="1" size="small" bordered>
                    <a-descriptions-item label="账号">
                      <span class="value-ellipsis" :title="selectedVideo.username ? `@${selectedVideo.username}` : '全部资料'">
                        {{ selectedVideo.username ? `@${selectedVideo.username}` : '全部资料' }}
                      </span>
                    </a-descriptions-item>
                    <a-descriptions-item label="大小">
                      {{ formatFileSize(selectedVideo.size) }}
                    </a-descriptions-item>
                    <a-descriptions-item label="更新时间">
                      {{ formatVideoDate(selectedVideo.modified_at) }}
                    </a-descriptions-item>
                    <a-descriptions-item label="观看次数">
                      {{ selectedVideo.annotations?.play_count || 0 }}
                    </a-descriptions-item>
                    <a-descriptions-item label="播放进度">
                      {{ `${Math.floor(selectedVideo.annotations?.last_position || 0)} 秒` }}
                    </a-descriptions-item>
                    <a-descriptions-item label="标签">
                      <a-space wrap class="tag-wrap-cluster">
                        <a-tag v-for="tag in selectedVideo.annotations?.tags || []" :key="tag" color="green">{{ tag }}</a-tag>
                        <span v-if="!(selectedVideo.annotations?.tags || []).length">暂无</span>
                      </a-space>
                    </a-descriptions-item>
                  </a-descriptions>

                  <a-form layout="vertical" style="margin-top: 16px">
                    <a-form-item label="标签（逗号分隔）">
                      <a-input v-model:value="noteForm.tags" :disabled="!canAnnotate" />
                    </a-form-item>
                    <a-form-item label="备注">
                      <a-textarea v-model:value="noteForm.note" :rows="4" :disabled="!canAnnotate" />
                    </a-form-item>
                    <a-button type="primary" @click="saveNote" :disabled="!canAnnotate">
                      保存备注
                    </a-button>
                  </a-form>
                </template>
                <a-empty v-else description="左边选一个视频，就会在这里直接预览" />
              </a-card>
            </a-col>
          </a-row>
        </a-tab-pane>

        <a-tab-pane key="photos" tab="照片">
          <a-row :gutter="[16, 16]">
            <a-col v-for="photo in photos" :key="photo.path" :xs="24" :sm="12" :lg="8" :xl="6">
              <a-card hoverable>
                <template #cover>
                  <a-image :src="encodeOutputPath(photo.path)" :alt="photo.name" />
                </template>
                <a-card-meta :title="photo.name" :description="formatFileSize(photo.size)" />
              </a-card>
            </a-col>
          </a-row>
          <a-empty v-if="!photos.length" description="暂无照片" />
        </a-tab-pane>

        <a-tab-pane key="documents" tab="文档">
          <a-table class="interactive-table" :columns="documentColumns" :data-source="documents" row-key="path" :scroll="{ x: 640 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="library-file-name" :title="record.name">{{ record.name }}</div>
                <div class="table-sub-note file-subline" :title="record.path">{{ record.path }}</div>
              </template>
              <template v-else-if="column.key === 'size'">
                {{ formatFileSize(record.size) }}
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button
                    v-if="record.name.endsWith('.html')"
                    size="small"
                    :href="buildDocumentViewUrl(record.path)"
                    target="_blank"
                  >
                    查看
                  </a-button>
                  <a-button size="small" :href="encodeOutputPath(record.path)" download>
                    下载
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </a-space>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  buildDocumentViewUrl,
  buildThumbnailSrc,
  encodeOutputPath,
  formatFileSize,
  formatVideoDate,
} from '../lib/formatters';
import { useWorkbenchStore } from '../store/workbench';

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();
const videoRef = ref(null);

const activeTab = ref('videos');
const selectedUsername = ref(null);
const selectedTaskId = ref(null);
const keyword = ref('');
const statusFilter = ref('all');
const sortBy = ref('latest');
const selectedVideoPath = ref('');
const noteForm = reactive({
  tags: '',
  note: '',
});

const videoColumns = [
  { title: '文件名', key: 'name', dataIndex: 'name' },
  { title: '状态', key: 'flags', width: 180 },
  { title: '大小', key: 'size', dataIndex: 'size', width: 110 },
  { title: '更新时间', key: 'modified_at', dataIndex: 'modified_at', width: 150 },
];

const documentColumns = [
  { title: '文件名', key: 'name', dataIndex: 'name' },
  { title: '大小', key: 'size', dataIndex: 'size', width: 120 },
  { title: '操作', key: 'actions', width: 180 },
];

const usernameSelectOptions = computed(() => [
  {
    label: '全部账号资料',
    value: null,
  },
  ...(store.usernameDirectoryItems.value || [])
    .filter((item) => !item.hidden)
    .map((item) => ({
      label: item.alias ? `${item.display_name} · @${item.username}` : `@${item.username}`,
      value: item.username,
    })),
]);

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '收藏', value: 'favorite' },
  { label: '已看', value: 'watched' },
  { label: '稍后看', value: 'watch_later' },
  { label: '异常', value: 'anomaly' },
];

const sortOptions = [
  { label: '按最新时间', value: 'latest' },
  { label: '按文件大小', value: 'largest' },
  { label: '按播放次数', value: 'plays' },
];

const sortLabelMap = {
  latest: '按最新时间',
  largest: '按文件大小',
  plays: '按播放次数',
};

const statusLabelMap = {
  all: '全部状态',
  favorite: '收藏',
  watched: '已看',
  watch_later: '稍后看',
  anomaly: '异常',
};

function matchesKeyword(file) {
  if (!keyword.value.trim()) {
    return true;
  }

  const haystack = `${file.name || ''} ${file.username || ''} ${file.path || ''} ${file.tweet_id || ''}`.toLowerCase();
  return haystack.includes(keyword.value.trim().toLowerCase());
}

function matchesStatus(file) {
  const annotations = file.annotations || {};
  if (statusFilter.value === 'favorite') {
    return Boolean(annotations.favorite);
  }
  if (statusFilter.value === 'watched') {
    return Boolean(annotations.watched);
  }
  if (statusFilter.value === 'watch_later') {
    return Boolean(annotations.watch_later);
  }
  if (statusFilter.value === 'anomaly') {
    return file.size < 300 * 1024 || !file.tweet_url;
  }
  return true;
}

function sortFiles(list) {
  const rows = [...list];
  if (sortBy.value === 'largest') {
    rows.sort((a, b) => (b.size || 0) - (a.size || 0));
  } else if (sortBy.value === 'plays') {
    rows.sort((a, b) => (b.annotations?.play_count || 0) - (a.annotations?.play_count || 0));
  } else {
    rows.sort((a, b) => (b.modified_at || 0) - (a.modified_at || 0));
  }
  return rows;
}

const videos = computed(() => sortFiles((store.state.library.files.videos || []).filter((file) => matchesKeyword(file) && matchesStatus(file))));
const photos = computed(() => (store.state.library.files.photos || []).filter(matchesKeyword));
const documents = computed(() => (store.state.library.files.documents || []).filter(matchesKeyword));

const selectedVideo = computed(() => {
  return videos.value.find((item) => item.path === selectedVideoPath.value) || videos.value[0] || null;
});
const favoriteVideos = computed(() => videos.value.filter((item) => item.annotations?.favorite));
const anomalyCount = computed(() => videos.value.filter((item) => item.size < 300 * 1024 || !item.tweet_url).length);
const activeSortLabel = computed(() => sortLabelMap[sortBy.value] || '按最新时间');
const activeStatusLabel = computed(() => statusLabelMap[statusFilter.value] || '全部状态');
const selectedIndex = computed(() => videos.value.findIndex((item) => item.path === selectedVideoPath.value));
const previousVideo = computed(() => selectedIndex.value > 0 ? videos.value[selectedIndex.value - 1] : null);
const nextVideo = computed(() => selectedIndex.value >= 0 && selectedIndex.value < videos.value.length - 1 ? videos.value[selectedIndex.value + 1] : null);
const firstUnwatchedVideo = computed(() => videos.value.find((item) => !item.annotations?.watched) || null);
const canAnnotate = computed(() => selectedVideo.value?.storage_backend === 'sqlite');

watch(videos, (nextVideos) => {
  if (!nextVideos.length) {
    selectedVideoPath.value = '';
    return;
  }
  if (!nextVideos.find((item) => item.path === selectedVideoPath.value)) {
    selectedVideoPath.value = nextVideos[0].path;
  }
}, { immediate: true });

watch(selectedVideo, (video) => {
  noteForm.tags = (video?.annotations?.tags || []).join(', ');
  noteForm.note = video?.annotations?.note || '';
});

watch(
  () => route.query.username,
  async (value) => {
    const nextUsername = typeof value === 'string' ? value : null;
    const nextTaskId = typeof route.query.task_id === 'string' ? route.query.task_id : null;
    if (nextUsername === selectedUsername.value && nextTaskId === selectedTaskId.value) {
      return;
    }
    selectedUsername.value = nextUsername;
    selectedTaskId.value = nextTaskId;
    await reloadLibrary();
  }
);

async function reloadLibrary() {
  await store.loadLibrary(selectedUsername.value, selectedTaskId.value);
}

function videoRow(record) {
  return {
    onClick: () => {
      selectedVideoPath.value = record.path;
    },
  };
}

function rowClassName(record) {
  return record.path === selectedVideoPath.value ? 'library-selected-row' : '';
}

async function toggleAnnotation(field, value) {
  if (!selectedVideo.value || !canAnnotate.value) {
    return;
  }
  await store.updateMediaAnnotation({
    username: selectedVideo.value.username,
    media_type: selectedVideo.value.media_type,
    media_id: selectedVideo.value.id,
    [field]: value,
  });
  message.success('视频状态已更新');
  await reloadLibrary();
}

async function saveNote() {
  if (!selectedVideo.value || !canAnnotate.value) {
    return;
  }
  await store.updateMediaAnnotation({
    username: selectedVideo.value.username,
    media_type: selectedVideo.value.media_type,
    media_id: selectedVideo.value.id,
    tags: noteForm.tags,
    note: noteForm.note,
  });
  message.success('备注已保存');
  await reloadLibrary();
}

function selectPrevVideo() {
  if (previousVideo.value) {
    selectedVideoPath.value = previousVideo.value.path;
  }
}

function selectNextVideo() {
  if (nextVideo.value) {
    selectedVideoPath.value = nextVideo.value.path;
  }
}

function jumpToFirstUnwatched() {
  if (firstUnwatchedVideo.value) {
    selectedVideoPath.value = firstUnwatchedVideo.value.path;
  }
}

function showFavoritesOnly() {
  statusFilter.value = 'favorite';
}

function clearLibraryFilters() {
  keyword.value = '';
  statusFilter.value = 'all';
  sortBy.value = 'latest';
}

function goUserFeed(username) {
  const href = router.resolve({
    name: 'user-feed-standalone',
    params: { username },
  }).href;
  window.open(href, '_blank', 'noopener,noreferrer');
}

async function persistPlayback() {
  if (!selectedVideo.value || !canAnnotate.value || !videoRef.value) {
    return;
  }
  await store.updateMediaAnnotation({
    username: selectedVideo.value.username,
    media_type: selectedVideo.value.media_type,
    media_id: selectedVideo.value.id,
    last_position: videoRef.value.currentTime || 0,
    play_count: (selectedVideo.value.annotations?.play_count || 0) + 1,
    last_played_at: new Date().toISOString(),
  });
}

async function markWatched() {
  if (!selectedVideo.value || !canAnnotate.value || !videoRef.value) {
    return;
  }
  await store.updateMediaAnnotation({
    username: selectedVideo.value.username,
    media_type: selectedVideo.value.media_type,
    media_id: selectedVideo.value.id,
    watched: true,
    last_position: videoRef.value.duration || videoRef.value.currentTime || 0,
    play_count: (selectedVideo.value.annotations?.play_count || 0) + 1,
    last_played_at: new Date().toISOString(),
  });
  await reloadLibrary();
}

onMounted(async () => {
  if (!store.state.adminOverview.libraries.length) {
    await store.loadAdminOverview({ silent: true });
  }

  selectedUsername.value = typeof route.query.username === 'string' ? route.query.username : null;
  selectedTaskId.value = typeof route.query.task_id === 'string' ? route.query.task_id : null;
  await reloadLibrary();
});
</script>

<style scoped>
.library-video-player {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: min(62vh, 620px);
  border-radius: 22px;
  background: #101c13;
  object-fit: contain;
}

.library-preview-card {
  overflow: hidden;
}
</style>
