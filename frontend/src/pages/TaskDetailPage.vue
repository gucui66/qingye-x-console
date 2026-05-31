<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card class="panel-card" :loading="store.state.loading.taskDetail">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :xl="8">
          <div class="detail-identity-card">
            <div class="metric-label">任务 ID</div>
            <div class="detail-task-id" :title="task?.task_id || route.params.taskId">
              {{ task?.task_id || route.params.taskId }}
            </div>
          </div>
        </a-col>
        <a-col :xs="24" :sm="12" :xl="4">
          <a-statistic title="推文数" :value="results.total_tweets || task?.scraped_count || historyEntry?.total_tweets || 0" />
        </a-col>
        <a-col :xs="24" :sm="12" :xl="4">
          <a-statistic title="视频" :value="results.videos || historyEntry?.videos || 0" />
        </a-col>
        <a-col :xs="24" :sm="12" :xl="4">
          <a-statistic title="照片" :value="results.photos || historyEntry?.photos || 0" />
        </a-col>
        <a-col :xs="24" :sm="12" :xl="4">
          <a-statistic title="状态" :value="statusLabel(task?.status || historyEntry?.status)" />
        </a-col>
      </a-row>
    </a-card>

    <a-card class="panel-card task-monitor-card" :loading="store.state.loading.taskDetail">
      <div class="task-monitor-shell">
        <div class="task-monitor-copy">
          <div class="login-kicker">Task Monitor</div>
          <h2>{{ monitorTitle }}</h2>
          <p>{{ monitorSubtitle }}</p>
          <a-progress
            :percent="progressPercent"
            :stroke-color="{ '0%': '#9dd87f', '100%': '#4f9956' }"
          />
          <div class="task-monitor-meta">
            <span>{{ `状态：${statusLabel(task?.status || historyEntry?.status)}` }}</span>
            <span>{{ `进度：${progressPercent}%` }}</span>
            <span>{{ `截图：${screenshots.length} 张` }}</span>
          </div>
          <a-space wrap>
            <a-button
              v-if="['running', 'pending'].includes(task?.status)"
              @click="pauseCurrentTask"
            >
              暂停
            </a-button>
            <a-button
              v-if="['paused', 'user_paused'].includes(task?.status)"
              type="primary"
              @click="resumeCurrentTask"
            >
              继续
            </a-button>
            <a-button
              v-if="['running', 'pending', 'paused', 'user_paused'].includes(task?.status)"
              danger
              @click="cancelCurrentTask"
            >
              取消
            </a-button>
            <a-button
              v-if="integrity.can_retry"
              danger
              :loading="retryLoading"
              @click="retryTask"
            >
              重试
            </a-button>
            <a-button @click="goNewTask(task?.username || historyEntry?.username)">
              再次爬取
            </a-button>
            <a-button @click="openUserTimeline" :disabled="!(task?.username || historyEntry?.username)">
              用户时间流
            </a-button>
            <a-button @click="reload">
              刷新详情
            </a-button>
          </a-space>
        </div>

        <div class="task-monitor-shot">
          <img
            v-if="store.state.screenshot.url"
            :src="store.state.screenshot.url"
            alt="实时截图"
          />
          <a-empty v-else description="暂无实时截图" />
        </div>
      </div>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="11">
        <a-card title="任务概况" class="panel-card" :loading="store.state.loading.taskDetail">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="账号">
              <span class="value-ellipsis" :title="task?.username ? `@${task.username}` : '未知'">
                {{ task?.username ? `@${task.username}` : '未知' }}
              </span>
            </a-descriptions-item>
            <a-descriptions-item label="创建时间">
              {{ formatDateTime(task?.created_at || historyEntry?.created_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="完成时间">
              {{ formatDateTime(task?.completed_at || historyEntry?.completed_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="错误信息">
              <span class="value-wrap break-all" :title="task?.error_message || historyEntry?.error_message || '无'">
                {{ task?.error_message || historyEntry?.error_message || '无' }}
              </span>
            </a-descriptions-item>
            <a-descriptions-item label="抓取方式">
              {{ task?.options?.scrape_method || '未知' }}
            </a-descriptions-item>
            <a-descriptions-item v-if="task?.options?.scrape_method === 'selenium'" label="行为模式">
              {{ seleniumBehaviorLabel(task?.options?.selenium_behavior_mode) }}
            </a-descriptions-item>
            <a-descriptions-item label="下载选项">
              视频 {{ task?.options?.download_videos ? '开' : '关' }} / 照片 {{ task?.options?.download_photos ? '开' : '关' }} / 回复 {{ task?.options?.download_replies ? '开' : '关' }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="13">
        <a-card title="最近一次差异" class="panel-card" :loading="store.state.loading.taskDetail">
          <template v-if="diff">
            <a-alert
              type="success"
              show-icon
              :message="`@${diff.username} 最近一次抓取差异`"
              :description="`推文 ${deltaText(diff.delta.tweets)}，视频 ${deltaText(diff.delta.videos)}，照片 ${deltaText(diff.delta.photos)}`"
            />
            <a-descriptions :column="2" size="small" bordered style="margin-top: 16px">
              <a-descriptions-item label="当前任务">{{ diff.current?.task_id_short || '-' }}</a-descriptions-item>
              <a-descriptions-item label="上一轮任务">{{ diff.previous?.task_id_short || '无' }}</a-descriptions-item>
              <a-descriptions-item label="当前时间">{{ diff.current?.timestamp || '暂无' }}</a-descriptions-item>
              <a-descriptions-item label="上一轮时间">{{ diff.previous?.timestamp || '暂无' }}</a-descriptions-item>
            </a-descriptions>
          </template>
          <a-empty v-else description="这个账号还没有足够的历史任务可以比较" />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24">
        <a-card title="本次任务产物" class="panel-card" :loading="store.state.loading.taskDetail">
          <a-row :gutter="[16, 16]" style="margin-bottom: 16px">
            <a-col :xs="24" :md="6">
              <a-statistic title="视频产物" :value="artifacts.summary?.videos || 0" />
            </a-col>
            <a-col :xs="24" :md="6">
              <a-statistic title="照片产物" :value="artifacts.summary?.photos || 0" />
            </a-col>
            <a-col :xs="24" :md="6">
              <a-statistic title="文档快照" :value="artifacts.summary?.documents || 0" />
            </a-col>
            <a-col :xs="24" :md="6">
              <a-statistic title="媒体总大小" :value="artifacts.summary?.total_media_size_display || '0 B'" />
            </a-col>
          </a-row>
          <a-space wrap style="margin-bottom: 16px">
            <a-button
              type="primary"
              @click="router.push({ name: 'library', query: { username: task?.username, task_id: currentTaskId } })"
            >
              打开这个任务的资料库
            </a-button>
            <a-button :href="downloadUrl" target="_blank">
              导出任务资料包
            </a-button>
            <a-button
              v-if="integrity.can_retry"
              danger
              :loading="retryLoading"
              @click="retryTask"
            >
              重试这个任务
            </a-button>
          </a-space>
          <a-tabs>
            <a-tab-pane key="task-videos" :tab="`视频 (${artifacts.videos?.length || 0})`">
              <a-table :columns="artifactColumns" :data-source="artifacts.videos || []" row-key="path" size="small" :pagination="{ pageSize: 5 }" :scroll="{ x: 700 }">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <span class="value-wrap break-all" :title="record.name">{{ record.name }}</span>
                  </template>
                  <template v-else-if="column.key === 'size'">
                    {{ formatFileSize(record.size) }}
                  </template>
                  <template v-else-if="column.key === 'actions'">
                    <a-space>
                      <a-button size="small" :href="encodeOutputPath(record.path)" target="_blank">打开</a-button>
                      <a-button size="small" :href="encodeOutputPath(record.path)" download>下载</a-button>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
            <a-tab-pane key="task-photos" :tab="`照片 (${artifacts.photos?.length || 0})`">
              <a-table :columns="artifactColumns" :data-source="artifacts.photos || []" row-key="path" size="small" :pagination="{ pageSize: 5 }" :scroll="{ x: 700 }">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <span class="value-wrap break-all" :title="record.name">{{ record.name }}</span>
                  </template>
                  <template v-else-if="column.key === 'size'">
                    {{ formatFileSize(record.size) }}
                  </template>
                  <template v-else-if="column.key === 'actions'">
                    <a-space>
                      <a-button size="small" :href="encodeOutputPath(record.path)" target="_blank">打开</a-button>
                      <a-button size="small" :href="encodeOutputPath(record.path)" download>下载</a-button>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
            <a-tab-pane key="task-docs" :tab="`文档 (${artifacts.documents?.length || 0})`">
              <a-table :columns="documentColumns" :data-source="artifacts.documents || []" row-key="path" size="small" :pagination="{ pageSize: 5 }" :scroll="{ x: 700 }">
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <span class="value-wrap break-all" :title="record.name">{{ record.name }}</span>
                  </template>
                  <template v-else-if="column.key === 'size'">
                    {{ formatFileSize(record.size) }}
                  </template>
                  <template v-else-if="column.key === 'actions'">
                    <a-space>
                      <a-button v-if="record.name?.endsWith('.html')" size="small" :href="buildDocumentViewUrl(record.path)" target="_blank">查看</a-button>
                      <a-button size="small" :href="encodeOutputPath(record.path)" download>下载</a-button>
                    </a-space>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="14">
        <a-card title="任务完整性检查" class="panel-card" :loading="store.state.loading.taskDetail" style="margin-bottom: 16px">
          <a-alert
            :type="integrityAlertType"
            show-icon
            :message="`当前状态：${integrity.health_text || '未知'}`"
            :description="integritySummaryText"
          />
          <a-row :gutter="[12, 12]" style="margin-top: 16px">
            <a-col :xs="12" :md="6">
              <a-statistic title="记录视频" :value="integrity.counts?.expected_videos || 0" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic title="可用视频" :value="integrity.counts?.stored_videos || 0" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic title="缺缩略图" :value="integrity.counts?.missing_thumbnails || 0" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic title="重复暂存" :value="integrity.counts?.duplicates || 0" />
            </a-col>
          </a-row>
          <a-list v-if="integrity.issues?.length" :data-source="integrity.issues" size="small" style="margin-top: 12px">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :title="item.title" :description="item.description" />
                <template #actions>
                  <a-tag :color="item.level === 'error' ? 'red' : item.level === 'warning' ? 'gold' : 'green'">
                    {{ item.level }}
                  </a-tag>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

        <a-card title="截图时间线" class="panel-card" :loading="store.state.loading.taskDetail">
          <a-timeline v-if="screenshots.length">
            <a-timeline-item v-for="item in screenshots" :key="item.url" color="green">
              <div class="timeline-shot-copy">
                <strong>{{ item.name }}</strong>
                <div class="table-sub-note">{{ item.modified_at_display }}</div>
              </div>
              <img :src="item.url" :alt="item.name" class="timeline-shot-image" />
            </a-timeline-item>
          </a-timeline>
          <a-empty v-else description="这个任务没有保存截图" />
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="10">
        <a-card title="同账号相关任务" class="panel-card" :loading="store.state.loading.taskDetail">
          <a-table
            class="interactive-table"
            :columns="historyColumns"
            :data-source="relatedHistory"
            :pagination="false"
            row-key="task_id"
            size="small"
            :custom-row="historyRow"
            :scroll="{ x: 560 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'task_id'">
                <a-button type="link" @click="goTask(record.task_id)">
                  {{ record.task_id_short }}
                </a-button>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </a-space>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Modal, message } from 'ant-design-vue';
import { useRoute, useRouter } from 'vue-router';

import { api, buildDownloadAllUrl } from '../lib/api';
import { buildDocumentViewUrl, encodeOutputPath, formatDateTime, formatFileSize } from '../lib/formatters';
import { useWorkbenchStore } from '../store/workbench';

const route = useRoute();
const router = useRouter();
const store = useWorkbenchStore();

const taskDetail = computed(() => store.state.taskDetail || {});
const task = computed(() => taskDetail.value.task || {});
const historyEntry = computed(() => taskDetail.value.history_entry || {});
const results = computed(() => task.value.results || {});
const artifacts = computed(() => taskDetail.value.artifacts || { summary: {}, videos: [], photos: [], documents: [] });
const screenshots = computed(() => taskDetail.value.screenshots || []);
const relatedHistory = computed(() => taskDetail.value.related_history || []);
const diff = computed(() => taskDetail.value.diff || null);
const currentTaskId = computed(() => task.value.task_id || historyEntry.value.task_id || route.params.taskId);
const integrity = computed(() => taskDetail.value.integrity || { counts: {}, issues: [], health: 'ok', health_text: '完整' });
const retryLoading = ref(false);
let detailRefreshTimer = null;
const downloadUrl = computed(() => buildDownloadAllUrl(task.value.username || historyEntry.value.username, currentTaskId.value));
const progressPercent = computed(() => Number(task.value.progress || historyEntry.value.progress || 0));
const monitorTitle = computed(() => {
  const username = task.value.username || historyEntry.value.username;
  if (username) {
    return `@${username} · ${statusLabel(task.value.status || historyEntry.value.status)}`;
  }
  return statusLabel(task.value.status || historyEntry.value.status);
});
const monitorSubtitle = computed(() => {
  if (task.value.progress_text) {
    return task.value.progress_text;
  }
  if (task.value.error_message || historyEntry.value.error_message) {
    return task.value.error_message || historyEntry.value.error_message;
  }
  if (['running', 'pending', 'paused', 'user_paused'].includes(task.value.status)) {
    return store.state.progress.step || '任务正在队列中，等待下一次进度事件。';
  }
  return '任务已经结束，可以查看产物、完整性和截图时间线。';
});
const shouldAutoRefreshDetail = computed(() => {
  return ['running', 'pending', 'paused', 'user_paused'].includes(task.value.status);
});
const integrityAlertType = computed(() => {
  const map = {
    ok: 'success',
    info: 'info',
    warning: 'warning',
    error: 'error',
  };
  return map[integrity.value.health] || 'info';
});
const integritySummaryText = computed(() => {
  const counts = integrity.value.counts || {};
  if (!integrity.value.issues?.length) {
    return '任务记录、媒体产物和截图时间线目前没有明显异常。';
  }
  return `推文 ${counts.scraped_tweets || 0} 条，缺失视频 ${counts.missing_videos || 0} 个，缺失照片 ${counts.missing_photos || 0} 个，缺少缩略图 ${counts.missing_thumbnails || 0} 个。`;
});

const historyColumns = [
  { title: '任务', key: 'task_id', dataIndex: 'task_id', width: 100 },
  { title: '状态', key: 'status_text', dataIndex: 'status_text', width: 100 },
  { title: '推文', key: 'tweets', dataIndex: 'tweets', width: 90 },
  { title: '视频', key: 'videos', dataIndex: 'videos', width: 90 },
  { title: '时间', key: 'timestamp', dataIndex: 'timestamp' },
];

const artifactColumns = [
  { title: '文件', key: 'name', dataIndex: 'name' },
  { title: 'Tweet ID', key: 'tweet_id', dataIndex: 'tweet_id', width: 160 },
  { title: '大小', key: 'size', dataIndex: 'size', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
];

const documentColumns = [
  { title: '文档', key: 'name', dataIndex: 'name' },
  { title: '大小', key: 'size', dataIndex: 'size', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
];

function statusLabel(value) {
  const map = {
    pending: '等待中',
    running: '运行中',
    paused: '自动暂停',
    user_paused: '手动暂停',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return map[value] || value || '未知';
}

function seleniumBehaviorLabel(value) {
  const map = {
    balanced: '均衡',
    stable: '稳定',
    human: '拟人',
  };
  return map[value] || '均衡';
}

function deltaText(value) {
  const number = Number(value || 0);
  if (number > 0) {
    return `+${number}`;
  }
  return `${number}`;
}

async function reload() {
  try {
    await store.loadTaskDetail(route.params.taskId);
  } catch (error) {
    store.pushLog(`任务详情加载失败: ${error.message || '未知错误'}`, 'error');
  }
}

function startDetailMonitoring() {
  if (currentTaskId.value) {
    store.startScreenshotRefresh(currentTaskId.value);
  }
  stopDetailPolling();
  if (shouldAutoRefreshDetail.value) {
    detailRefreshTimer = window.setInterval(() => {
      reload();
    }, 5000);
  }
}

function stopDetailPolling() {
  if (detailRefreshTimer) {
    window.clearInterval(detailRefreshTimer);
    detailRefreshTimer = null;
  }
}

function goTask(taskId) {
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

function historyRow(record) {
  return {
    onClick: () => {
      goTask(record.task_id);
    },
  };
}

async function retryTask() {
  if (!currentTaskId.value) {
    return;
  }
  retryLoading.value = true;
  try {
    const result = await api.retryAdminTask(currentTaskId.value);
    message.success(result.message || '任务已重新加入队列');
    await store.loadTasks();
    await store.loadAdminOverview({ force: true, silent: true });
    if (result.task_id) {
      router.push({ name: 'task-detail', params: { taskId: result.task_id } });
    }
  } catch (error) {
    message.error(error.message || '重试任务失败');
  } finally {
    retryLoading.value = false;
  }
}

async function pauseCurrentTask() {
  if (!currentTaskId.value) {
    return;
  }
  await store.pauseTask(currentTaskId.value);
  await reload();
}

async function resumeCurrentTask() {
  if (!currentTaskId.value) {
    return;
  }
  await store.resumeTask(currentTaskId.value);
  await reload();
}

function cancelCurrentTask() {
  if (!currentTaskId.value) {
    return;
  }
  Modal.confirm({
    title: '取消任务',
    content: '取消后这个任务会停止当前抓取流程，你确定要继续吗？',
    okText: '确认取消',
    cancelText: '再想想',
    async onOk() {
      await store.cancelTask(currentTaskId.value);
      message.success('任务已取消');
      await reload();
    },
  });
}

function goNewTask(username) {
  router.push({
    name: 'new-task',
    query: username ? { username } : {},
  });
}

function openUserTimeline() {
  const username = task.value.username || historyEntry.value.username;
  if (!username) {
    return;
  }
  const href = router.resolve({
    name: 'user-feed-standalone',
    params: { username },
  }).href;
  window.open(href, '_blank', 'noopener,noreferrer');
}

watch(
  () => route.params.taskId,
  () => {
    reload();
    startDetailMonitoring();
  }
);

watch(
  () => task.value.status,
  () => {
    startDetailMonitoring();
  }
);

onMounted(() => {
  reload();
  startDetailMonitoring();
});

onBeforeUnmount(() => {
  stopDetailPolling();
  store.stopScreenshotRefresh();
});
</script>

<style scoped>
.task-monitor-card {
  border: 1px solid #d7ebd2;
  background: linear-gradient(135deg, #f6fcf2 0%, #ffffff 62%, #eef8eb 100%);
}

.task-monitor-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.9fr);
  gap: 18px;
  align-items: stretch;
}

.task-monitor-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}

.task-monitor-copy h2 {
  margin: 4px 0 0;
  color: #102310;
  font-size: 28px;
  line-height: 1.15;
}

.task-monitor-copy p {
  margin: 0;
  color: #526153;
}

.task-monitor-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-monitor-meta span {
  padding: 6px 10px;
  border: 1px solid #dcebdd;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #526153;
  font-size: 12px;
}

.task-monitor-shot {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid #dcebdd;
  border-radius: 16px;
  background: #f8fbf8;
}

.task-monitor-shot img {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 320px;
  object-fit: contain;
}

@media (max-width: 960px) {
  .task-monitor-shell {
    grid-template-columns: 1fr;
  }
}
</style>
