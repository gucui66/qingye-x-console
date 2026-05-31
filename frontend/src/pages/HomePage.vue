<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card :bordered="false" class="home-hero-card">
      <div class="home-hero">
        <div class="home-hero-copy">
          <div class="login-kicker">Qingye Local Console</div>
          <h1>快捷导航与资料入口</h1>
          <p>
            这里不再重复展示总览数据，主要只做跳转和常用入口。
            想先开任务就进新建爬取任务，想看运行状态就进运行总览，想找账号就从这里直接跳。
          </p>
          <a-space wrap>
            <a-button type="primary" size="large" @click="goTo('new-task')">
              新建爬取任务
            </a-button>
            <a-button size="large" @click="goTo('dashboard')">
              打开运行总览
            </a-button>
            <a-button size="large" @click="goTo('library')">
              打开视频中心
            </a-button>
          </a-space>
        </div>

        <div class="home-hero-panel">
          <div class="home-hero-panel-title">当前状态</div>
          <div class="home-hero-panel-line">
            <span>登录用户</span>
            <strong>{{ store.state.auth.username || 'admin' }}</strong>
          </div>
          <div class="home-hero-panel-line">
            <span>活动任务</span>
            <strong>{{ summary.active_tasks || 0 }}</strong>
          </div>
          <div class="home-hero-panel-line">
            <span>总账号数</span>
            <strong>{{ summary.total_users || 0 }}</strong>
          </div>
          <div class="home-hero-panel-line">
            <span>存储体积</span>
            <strong>{{ summary.total_storage_display || '0 B' }}</strong>
          </div>
        </div>
      </div>
    </a-card>

    <a-card title="常用账号入口">
      <a-space wrap>
        <a-button
          v-for="item in quickUsers"
          :key="item.normalized_username"
          @click="openUserFeed(item.username)"
        >
          {{ item.alias ? `${item.display_name} · @${item.username}` : `@${item.username}` }}
        </a-button>
      </a-space>
      <a-empty v-if="!quickUsers.length" description="暂时还没有可用账号" />
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card metric-green">
          <div class="metric-label">任务总数</div>
          <div class="metric-value">{{ summary.total_tasks || 0 }}</div>
          <div class="metric-foot">所有历史任务、完成任务和失败记录</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">活动任务</div>
          <div class="metric-value">{{ summary.active_tasks || 0 }}</div>
          <div class="metric-foot">正在抓取、等待和暂停中的任务</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">成功率</div>
          <div class="metric-value">{{ `${summary.success_rate || 0}%` }}</div>
          <div class="metric-foot">最近一批任务的成功比例</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">上次运行</div>
          <div class="metric-value metric-value-small">{{ summary.last_run || '--' }}</div>
          <div class="metric-foot">最近一次任务更新时间</div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="15">
        <a-card title="快速入口">
          <div class="home-quick-grid">
            <button type="button" class="home-quick-card" @click="goTo('new-task')">
              <strong>新建爬取任务</strong>
              <span>单独填写账号、数量、下载选项和抓取方式</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('tasks')">
              <strong>任务管理</strong>
              <span>继续任务、取消任务、筛选队列、查看任务详情</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('library')">
              <strong>视频中心</strong>
              <span>看视频、看图片、收藏、标记已看、写备注</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('database')">
              <strong>数据库管理</strong>
              <span>看固定桶分片、旧版账号库、健康检查、结构、备份和容量</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('search')">
              <strong>全局搜索</strong>
              <span>按账号、任务、媒体、历史记录快速检索</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('monitor')">
              <strong>系统监控</strong>
              <span>观察截图、目录体积、日志和运行状态</span>
            </button>
            <button type="button" class="home-quick-card" @click="goTo('deployment')">
              <strong>部署与迁移</strong>
              <span>看本地部署、Docker 使用和迁移方案</span>
            </button>
          </div>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="9">
        <a-card title="实时截图">
          <img
            v-if="store.state.screenshot.url"
            :src="store.state.screenshot.url"
            alt="实时截图"
            class="dashboard-screenshot"
          />
          <a-empty v-else description="当前没有可展示的 Selenium 截图" />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card title="最近失败任务">
          <a-list :data-source="recentFailures" item-layout="horizontal">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="`@${item.username}`"
                  :description="`${item.status_text} · ${item.timestamp}`"
                />
                <template #actions>
                  <a-button type="link" @click="goTask(item.task_id)">查看</a-button>
                </template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="!recentFailures.length" description="最近没有失败任务" />
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="12">
        <a-card title="资料库概览">
          <a-table
            class="interactive-table"
            :columns="libraryColumns"
            :data-source="libraries"
            :pagination="{ pageSize: 6 }"
            row-key="username"
            size="small"
            :custom-row="libraryRow"
          />
        </a-card>
      </a-col>
    </a-row>
  </a-space>
</template>

<script setup>
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { useWorkbenchStore } from '../store/workbench';

const router = useRouter();
const store = useWorkbenchStore();

const summary = computed(() => store.state.adminOverview.summary || {});
const recentFailures = computed(() => store.state.adminOverview.recent_failures || []);
const libraries = computed(() => store.state.adminOverview.libraries || []);
const quickUsers = computed(() => (store.state.usernameDirectory.items || []).filter((item) => !item.hidden).slice(0, 8));

const libraryColumns = [
  { title: '账号', dataIndex: 'username', key: 'username' },
  { title: '视频', dataIndex: 'videos', key: 'videos', width: 90 },
  { title: '照片', dataIndex: 'photos', key: 'photos', width: 90 },
  { title: '总文件', dataIndex: 'total_files', key: 'total_files', width: 100 },
  { title: '最近更新时间', dataIndex: 'last_modified_display', key: 'last_modified_display' },
];

function goTo(name) {
  router.push({ name });
}

function goTask(taskId) {
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

function openUserFeed(username) {
  const href = router.resolve({
    name: 'user-feed-standalone',
    params: { username },
  }).href;
  window.open(href, '_blank', 'noopener,noreferrer');
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

onMounted(() => {
  store.loadAdminOverview({ silent: true });
  store.loadUsernameDirectory({ silent: true });
});
</script>
