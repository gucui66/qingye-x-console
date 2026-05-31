<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card class="panel-card">
      <a-row :gutter="[16, 16]" class="page-filter-row">
        <a-col :xs="24" :xl="18">
          <a-input-search
            v-model:value="keyword"
            class="page-filter-control"
            placeholder="搜索账号、任务、视频文件名、tweet id"
            enter-button="立即搜索"
            allow-clear
            @search="runSearch"
          />
        </a-col>
        <a-col :xs="24" :xl="6">
          <a-button block class="page-filter-control" @click="useCurrentFocus">
            搜索当前活动账号
          </a-button>
        </a-col>
      </a-row>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="8">
        <a-card><a-statistic title="媒体结果" :value="results.media?.length || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card><a-statistic title="任务结果" :value="(results.tasks?.length || 0) + (results.history?.length || 0)" /></a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card><a-statistic title="账号结果" :value="results.users?.length || 0" /></a-card>
      </a-col>
    </a-row>

    <a-card class="panel-card" :loading="store.state.loading.search">
      <a-tabs>
        <a-tab-pane key="media" tab="媒体结果">
          <a-table class="interactive-table" :columns="mediaColumns" :data-source="results.media || []" row-key="path" :scroll="{ x: 760 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <a :href="encodeOutputPath(record.path)" target="_blank" class="search-primary-link" :title="record.name">
                  {{ record.name }}
                </a>
                <div class="table-sub-note file-subline" :title="record.path">{{ record.path }}</div>
              </template>
              <template v-else-if="column.key === 'annotations'">
                <a-space wrap class="tag-wrap-cluster">
                  <a-tag v-if="record.annotations?.favorite" color="green">收藏</a-tag>
                  <a-tag v-if="record.annotations?.watched" color="green">已看</a-tag>
                  <a-tag v-if="record.annotations?.watch_later" color="gold">稍后看</a-tag>
                </a-space>
              </template>
              <template v-else-if="column.key === 'size'">
                {{ formatFileSize(record.size) }}
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="tasks" tab="任务结果">
          <a-table
            class="interactive-table"
            :columns="taskColumns"
            :data-source="taskRows"
            row-key="row_key"
            :custom-row="taskRow"
            :scroll="{ x: 760 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'task_id'">
                <a-button type="link" @click="goTask(record.task_id)">
                  {{ record.task_id }}
                </a-button>
              </template>
              <template v-else-if="column.key === 'error_message'">
                <span class="table-clamp-2" :title="record.error_message || '无'">
                  {{ record.error_message || '无' }}
                </span>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="users" tab="账号结果">
          <a-list :data-source="results.users || []">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="`@${item.username}`"
                  :description="item.diff ? `最近差异: 推文 ${item.diff.delta.tweets}, 视频 ${item.diff.delta.videos}, 照片 ${item.diff.delta.photos}` : '暂无差异记录'"
                />
                <template #actions>
                  <a-button size="small" @click="goLibrary(item.username)">资料库</a-button>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </a-space>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { encodeOutputPath, formatFileSize } from '../lib/formatters';
import { useWorkbenchStore } from '../store/workbench';

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();
const keyword = ref('');

const results = computed(() => store.state.search.results || {});
const taskRows = computed(() => [
  ...(results.value.tasks || []).map((item) => ({ ...item, row_key: `live_${item.task_id}` })),
  ...(results.value.history || []).map((item) => ({ ...item, row_key: `history_${item.task_id}` })),
]);

const mediaColumns = [
  { title: '文件名', key: 'name', dataIndex: 'name' },
  { title: '账号', key: 'username', dataIndex: 'username', width: 120 },
  { title: '类型', key: 'media_type', dataIndex: 'media_type', width: 90 },
  { title: '大小', key: 'size', dataIndex: 'size', width: 110 },
  { title: '状态', key: 'annotations', dataIndex: 'annotations', width: 180 },
];

const taskColumns = [
  { title: '任务 ID', key: 'task_id', dataIndex: 'task_id' },
  { title: '账号', key: 'username', dataIndex: 'username', width: 120 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 120 },
  { title: '错误', key: 'error_message', dataIndex: 'error_message' },
];

async function runSearch() {
  if (!String(keyword.value || '').trim()) {
    await store.loadSearch('');
    router.replace({
      name: 'search',
      query: {},
    });
    return;
  }
  await store.loadSearch(keyword.value);
  router.replace({
    name: 'search',
    query: keyword.value ? { q: keyword.value } : {},
  });
}

function useCurrentFocus() {
  const username = store.focusTask.value?.username || store.latestCompletedTask.value?.username;
  keyword.value = username || '';
  if (keyword.value) {
    runSearch();
    return;
  }
  message.info('当前没有可直接定位的活动账号');
}

function goLibrary(username) {
  router.push({
    name: 'library',
    query: { username },
  });
}

function goTask(taskId) {
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

function taskRow(record) {
  return {
    onClick: () => {
      goTask(record.task_id);
    },
  };
}

watch(
  () => route.query.q,
  (value) => {
    const normalized = String(value || '');
    if (normalized !== keyword.value) {
      keyword.value = normalized;
      store.loadSearch(normalized);
    }
  }
);

onMounted(() => {
  keyword.value = String(route.query.q || '');
  if (keyword.value) {
    runSearch();
  }
});
</script>
