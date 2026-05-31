<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="活动任务" :value="system.runtime?.active_tasks || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="队列长度" :value="system.runtime?.queue_size || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="数据目录体积" :value="system.storage?.data_size_display || '0 B'" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="输出目录体积" :value="system.storage?.output_size_display || '0 B'" /></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="11">
        <a-card title="运行时信息" class="panel-card" :loading="store.state.loading.system">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="Python">{{ system.runtime?.python || '-' }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ system.runtime?.platform || '-' }}</a-descriptions-item>
            <a-descriptions-item label="主机">{{ system.runtime?.hostname || '-' }}</a-descriptions-item>
            <a-descriptions-item label="工作线程">{{ system.runtime?.max_workers || 0 }}</a-descriptions-item>
            <a-descriptions-item label="截图目录">
              <span class="value-wrap break-all" :title="system.storage?.screenshots_dir || '-'">
                {{ system.storage?.screenshots_dir || '-' }}
              </span>
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="13">
        <a-card title="任务健康度" class="panel-card" :loading="store.state.loading.system">
          <a-row :gutter="[12, 12]">
            <a-col :span="8"><a-statistic title="历史总数" :value="system.history?.total || 0" /></a-col>
            <a-col :span="8"><a-statistic title="已完成" :value="system.history?.completed || 0" /></a-col>
            <a-col :span="8"><a-statistic title="失败/取消" :value="system.history?.failed || 0" /></a-col>
          </a-row>
          <a-divider />
          <a-list :data-source="activityRows" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta
                  :title="`@${item.username}`"
                  :description="`推文 ${deltaText(item.delta?.tweets)}，视频 ${deltaText(item.delta?.videos)}，照片 ${deltaText(item.delta?.photos)}`"
                />
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>

    <a-card title="系统日志镜像" class="panel-card">
      <div class="dashboard-log-panel">
        <div v-for="(entry, index) in recentLogs" :key="`${entry.time}-${index}`" class="dashboard-log-item">
          <span class="dashboard-log-time">{{ entry.time }}</span>
          <span class="dashboard-log-text value-wrap break-all" :title="entry.message">{{ entry.message }}</span>
        </div>
      </div>
    </a-card>
  </a-space>
</template>

<script setup>
import { computed, onMounted } from 'vue';

import { useWorkbenchStore } from '../store/workbench';

const store = useWorkbenchStore();

const system = computed(() => store.state.system || {
  runtime: {},
  storage: {},
  history: {},
  activity: [],
});
const activityRows = computed(() => system.value.activity || []);
const recentLogs = computed(() => store.state.logs.slice(-24).reverse());

function deltaText(value) {
  const number = Number(value || 0);
  if (number > 0) {
    return `+${number}`;
  }
  return `${number}`;
}

onMounted(() => {
  store.loadSystem();
});
</script>
