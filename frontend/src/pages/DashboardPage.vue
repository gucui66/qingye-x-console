<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card class="dashboard-hero panel-card" :loading="store.state.loading.overview">
      <div class="dashboard-hero-copy">
        <div class="login-kicker">Workbench Overview</div>
        <h2>今天的工作台概览</h2>
        <p>把活跃任务、媒体资料、失败记录和系统日志放在一块看，适合先判断“现在最该处理什么”。</p>
      </div>
      <div class="dashboard-hero-stats">
        <div class="dashboard-hero-stat">
          <span>焦点任务</span>
          <strong :title="store.focusTask.value ? `@${store.focusTask.value.username}` : '当前没有活动任务'">
            {{ store.focusTask.value ? `@${store.focusTask.value.username}` : '当前没有活动任务' }}
          </strong>
        </div>
        <div class="dashboard-hero-stat">
          <span>成功率</span>
          <strong>{{ `${summary.success_rate || 0}%` }}</strong>
        </div>
        <div class="dashboard-hero-stat">
          <span>最近运行</span>
          <strong :title="summary.last_run || '暂无'">{{ summary.last_run || '暂无' }}</strong>
        </div>
      </div>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card metric-green panel-card">
          <div class="metric-label">账号数</div>
          <div class="metric-value">{{ summary.total_users || 0 }}</div>
          <div class="metric-foot">已建立资料库或数据库分片的账号</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card panel-card">
          <div class="metric-label">任务总数</div>
          <div class="metric-value">{{ summary.total_tasks || 0 }}</div>
          <div class="metric-foot">含历史任务与失败记录</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card panel-card">
          <div class="metric-label">活动任务</div>
          <div class="metric-value">{{ summary.active_tasks || 0 }}</div>
          <div class="metric-foot">运行中、等待中、暂停中</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card panel-card">
          <div class="metric-label">总存储体积</div>
          <div class="metric-value metric-value-small">{{ summary.total_storage_display || '0 B' }}</div>
          <div class="metric-foot">视频、照片与文档总和</div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="15">
        <a-card title="当前运行快照" class="panel-card" :loading="store.state.loading.tasks">
          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :lg="12">
              <div class="focus-task-box">
                <div class="focus-task-head">
                  <div>
                    <div class="focus-task-user">
                      {{ store.focusTask.value ? `@${store.focusTask.value.username}` : '当前没有活动任务' }}
                    </div>
                    <div class="focus-task-status">
                      {{ store.focusTask.value ? store.focusTask.value.status : 'idle' }}
                    </div>
                  </div>
                  <a-tag color="green">{{ `${store.state.progress.percentage}%` }}</a-tag>
                </div>

                <a-progress
                  :percent="store.state.progress.percentage"
                  :stroke-color="{ '0%': '#8ccd75', '100%': '#4e9655' }"
                />

                <a-descriptions size="small" :column="1" bordered>
                  <a-descriptions-item label="进度文字">
                    {{ store.state.progress.text }}
                  </a-descriptions-item>
                  <a-descriptions-item label="当前阶段">
                    {{ store.state.progress.step || '等待任务启动' }}
                  </a-descriptions-item>
                  <a-descriptions-item label="上次运行">
                    {{ summary.last_run || '暂无' }}
                  </a-descriptions-item>
                  <a-descriptions-item label="成功率">
                    {{ `${summary.success_rate || 0}%` }}
                  </a-descriptions-item>
                </a-descriptions>
              </div>
            </a-col>

            <a-col :xs="24" :lg="12">
              <div class="screenshot-card">
                <div class="panel-title">浏览器实时截图</div>
                <img
                  v-if="store.state.screenshot.url"
                  :src="store.state.screenshot.url"
                  alt="实时截图"
                  class="dashboard-screenshot"
                />
                <a-empty
                  v-else
                  description="当前没有可展示的 Selenium 截图"
                />
              </div>
            </a-col>
          </a-row>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="9">
        <a-card title="最近失败或取消" class="panel-card" :loading="store.state.loading.overview">
          <a-list :data-source="recentFailures" item-layout="horizontal">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="`@${item.username}`"
                  :description="`${item.status_text} · ${item.timestamp}`"
                />
                <template #actions>
                  <a-button size="small" type="link" @click="goTaskDetail(item.task_id)">详情</a-button>
                  <a-button
                    v-if="['failed', 'cancelled'].includes(item.status)"
                    size="small"
                    type="link"
                    :loading="retryingTaskId === item.task_id"
                    @click="retryFailure(item)"
                  >
                    重试
                  </a-button>
                  <a-tag color="red">{{ item.task_id_short }}</a-tag>
                </template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="!recentFailures.length" description="最近没有失败任务" />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="14">
        <a-card title="活动任务列表" class="panel-card" :loading="store.state.loading.overview">
          <a-table
            class="interactive-table"
            :columns="taskColumns"
            :data-source="liveTasks"
            :pagination="false"
            row-key="task_id"
            size="middle"
            :custom-row="taskRow"
            :scroll="{ x: 620 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'username'">
                <strong>{{ `@${record.username}` }}</strong>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'running' ? 'green' : 'gold'">
                  {{ record.status_text }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'progress'">
                <a-progress :percent="record.progress || 0" size="small" />
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="10">
        <a-card title="运行日志" class="panel-card">
          <div class="dashboard-log-panel">
            <div
              v-for="(entry, index) in recentLogs"
              :key="`${entry.time}-${index}`"
              class="dashboard-log-item"
            >
              <span class="dashboard-log-time">{{ entry.time }}</span>
              <span class="dashboard-log-text">{{ entry.message }}</span>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card title="视频中心快照" class="panel-card" :loading="store.state.loading.overview">
          <a-list :data-source="mediaSnapshot.items || []">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="item.name"
                  :description="`@${item.username} · ${item.annotations?.favorite ? '已收藏' : '普通'} · ${item.annotations?.watched ? '已看' : '未看'}`"
                />
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="!(mediaSnapshot.items || []).length" description="暂无视频快照" />
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="12">
        <a-card title="系统建议" class="panel-card">
          <a-list bordered>
            <a-list-item>历史视频缺缩略图时，去数据库管理的维护中心点“补全历史视频缩略图”。</a-list-item>
            <a-list-item>重复暂存文件会保留给你手动删除，主媒体库不会被自动误删。</a-list-item>
            <a-list-item>失败/取消任务会进入完整性提醒，后续可以继续扩展成失败重试中心。</a-list-item>
            <a-list-item>数据库管理页支持健康检查、结构查看、重复扫描和一键备份。</a-list-item>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="14">
        <a-card title="快捷动作" class="panel-card">
          <div class="quick-action-grid">
            <button type="button" class="quick-action-card" @click="router.push({ name: 'new-task' })">
              <strong>新建爬取任务</strong>
              <span>单独确认账号、数量、下载内容和采集方式。</span>
            </button>
            <button type="button" class="quick-action-card" @click="router.push({ name: 'tasks' })">
              <strong>进入任务管理</strong>
              <span>筛选活跃任务、处理失败任务和批量操作。</span>
            </button>
            <button
              type="button"
              class="quick-action-card"
              @click="openFocusTask"
            >
              <strong>打开当前焦点任务</strong>
              <span>{{ focusTaskCaption }}</span>
            </button>
            <button
              type="button"
              class="quick-action-card"
              @click="openFocusLibrary"
            >
              <strong>查看当前账号资料库</strong>
              <span>{{ focusLibraryCaption }}</span>
            </button>
            <button type="button" class="quick-action-card" @click="router.push({ name: 'database' })">
              <strong>进入数据库管理</strong>
              <span>查看分片健康度、体积和最近变化。</span>
            </button>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="10">
        <a-card title="异常提醒" class="panel-card">
          <a-list :data-source="alertItems" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :title="item.title" :description="item.description" />
                <template #actions>
                  <a-tag :color="item.color">{{ item.level }}</a-tag>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <a-card title="资料库概览" class="panel-card" :loading="store.state.loading.overview">
      <a-table
        class="interactive-table"
        :columns="libraryColumns"
        :data-source="libraries"
        :pagination="{ pageSize: 8 }"
        row-key="username"
        :custom-row="libraryRow"
        :scroll="{ x: 760 }"
      />
    </a-card>
  </a-space>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { useRouter } from 'vue-router';

import { api } from '../lib/api';
import { useWorkbenchStore } from '../store/workbench';

const router = useRouter();
const store = useWorkbenchStore();
const retryingTaskId = ref('');

const summary = computed(() => store.state.adminOverview.summary || {});
const liveTasks = computed(() => store.state.adminOverview.live_tasks || []);
const libraries = computed(() => store.state.adminOverview.libraries || []);
const recentFailures = computed(() => store.state.adminOverview.recent_failures || []);
const mediaSnapshot = computed(() => store.state.adminOverview.media_snapshot || { items: [] });
const maintenance = computed(() => store.state.adminOverview.maintenance || { videos: {}, duplicates: {}, tasks: {} });
const recentLogs = computed(() => store.state.logs.slice(-18).reverse());
const alertItems = computed(() => {
  const alerts = [];

  if ((summary.value?.active_tasks || 0) > 0) {
    alerts.push({
      title: '当前存在进行中的任务',
      description: `现在有 ${summary.value.active_tasks} 条活跃任务，建议优先关注截图和进度变化。`,
      level: '处理中',
      color: 'processing',
      priority: 3,
    });
  }

  if ((recentFailures.value || []).length) {
    alerts.push({
      title: '最近存在失败或取消记录',
      description: `最近有 ${(recentFailures.value || []).length} 条异常任务，建议优先检查任务详情和截图时间线。`,
      level: '高优先级',
      color: 'red',
      priority: 4,
    });
  }

  if ((maintenance.value?.videos?.missing_thumbnails || 0) > 0) {
    alerts.push({
      title: '存在缺少缩略图的视频',
      description: `还有 ${maintenance.value.videos.missing_thumbnails} 个历史视频没有预览图，可在数据库维护中心一键补全。`,
      level: '可优化',
      color: 'gold',
      priority: 3,
    });
  }

  if ((maintenance.value?.duplicates?.active || 0) > 0) {
    alerts.push({
      title: '重复暂存区有待处理文件',
      description: `当前有 ${maintenance.value.duplicates.active} 个重复文件，占用 ${maintenance.value.duplicates.total_size_display || '0 B'}。`,
      level: '待整理',
      color: 'orange',
      priority: 3,
    });
  }

  if ((mediaSnapshot.value?.items || []).length) {
    alerts.push({
      title: '媒体中心有最新内容',
      description: `最近快照里有 ${(mediaSnapshot.value.items || []).length} 条媒体记录，可以直接回看或整理。`,
      level: '可处理',
      color: 'green',
      priority: 2,
    });
  }

  if (!alerts.length) {
    alerts.push({
      title: '当前没有明显异常',
      description: '系统状态比较平稳，可以继续发起新任务或整理资料库。',
      level: '正常',
      color: 'default',
      priority: 1,
    });
  }

  return alerts.sort((left, right) => right.priority - left.priority);
});
const focusTaskCaption = computed(() => {
  if (!store.focusTask.value?.task_id) {
    return '当前没有活动任务可直接打开。';
  }

  return `直接进入 ${store.focusTask.value.task_id} 的详情页。`;
});
const focusLibraryCaption = computed(() => {
  const username = store.focusTask.value?.username || libraries.value?.[0]?.username;
  if (!username) {
    return '当前没有可直接定位的资料库账号。';
  }

  return `跳到 @${username} 的资料库视图。`;
});

const taskColumns = [
  { title: '账号', dataIndex: 'username', key: 'username' },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '已抓取', dataIndex: 'scraped_count', key: 'scraped_count', width: 100 },
  { title: '目标', dataIndex: 'max_tweets', key: 'max_tweets', width: 100 },
  { title: '进度', dataIndex: 'progress', key: 'progress' },
];

const libraryColumns = [
  { title: '账号', dataIndex: 'username', key: 'username' },
  { title: '视频', dataIndex: 'videos', key: 'videos', width: 90 },
  { title: '照片', dataIndex: 'photos', key: 'photos', width: 90 },
  { title: '文档', dataIndex: 'documents', key: 'documents', width: 90 },
  { title: '总文件', dataIndex: 'total_files', key: 'total_files', width: 100 },
  { title: '体积', dataIndex: 'total_size_display', key: 'total_size_display', width: 120 },
  { title: '最近更新时间', dataIndex: 'last_modified_display', key: 'last_modified_display' },
];

function taskRow(record) {
  return {
    onClick: () => {
      router.push({
        name: 'task-detail',
        params: { taskId: record.task_id },
      });
    },
  };
}

function goTaskDetail(taskId) {
  if (!taskId) {
    return;
  }
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

async function retryFailure(item) {
  if (!item?.task_id) {
    return;
  }
  retryingTaskId.value = item.task_id;
  try {
    const result = await api.retryAdminTask(item.task_id);
    message.success(result.message || '任务已重新加入队列');
    await store.loadTasks();
    await store.loadAdminOverview({ force: true, silent: true });
    if (result.task_id) {
      goTaskDetail(result.task_id);
    }
  } catch (error) {
    message.error(error.message || '重试任务失败');
  } finally {
    retryingTaskId.value = '';
  }
}

function libraryRow(record) {
  return {
    onClick: () => {
      router.push({
        name: 'library',
        query: { username: record.username },
      });
    },
  };
}

function openFocusTask() {
  if (!store.focusTask.value?.task_id) {
    router.push({ name: 'new-task' });
    return;
  }

  router.push({
    name: 'task-detail',
    params: { taskId: store.focusTask.value.task_id },
  });
}

function openFocusLibrary() {
  const username = store.focusTask.value?.username || libraries.value?.[0]?.username;
  router.push({
    name: 'library',
    query: username ? { username } : {},
  });
}

onMounted(() => {
  store.loadAdminOverview();
});
</script>
