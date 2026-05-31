<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="分片库数量" :value="summary.shard_count || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="媒体总条数" :value="summary.total_items || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="健康分片" :value="healthSummary.healthy_shards || 0" /></a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card><a-statistic title="总库体积" :value="summary.total_size_display || '0 B'" /></a-card>
      </a-col>
    </a-row>

    <a-card title="当前分片策略" class="panel-card">
      <a-space wrap>
        <a-tag color="green">固定桶分片 {{ summary.bucket_count || 0 }}</a-tag>
        <a-tag color="gold">旧版账号库 {{ summary.legacy_count || 0 }}</a-tag>
      </a-space>
      <div class="table-sub-note" style="margin-top: 10px">
        新写入的媒体会进入固定桶分片；旧的按账号单库仍然保留可读、可播、可备份。
      </div>
    </a-card>

    <a-card title="数据库管理动作" class="panel-card">
      <a-space wrap>
        <a-button type="primary" :href="buildDatabaseBackupUrl()" target="_blank">
          备份全部分片库
        </a-button>
        <a-button
          v-if="summary.legacy_count"
          type="primary"
          ghost
          :loading="store.state.loading.databaseMigrate"
          @click="migrateAllLegacy"
        >
          迁移全部旧版账号库
        </a-button>
        <a-button @click="reloadAll">刷新数据库状态</a-button>
      </a-space>
    </a-card>

    <a-card title="维护中心" class="panel-card" :loading="maintenanceLoading">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :md="8">
          <a-statistic
            title="缩略图覆盖率"
            :value="maintenanceReport.videos?.thumbnail_coverage ?? 100"
            suffix="%"
          />
          <div class="table-sub-note">
            缺少缩略图 {{ maintenanceReport.videos?.missing_thumbnails || 0 }} / {{ maintenanceReport.videos?.total || 0 }}
          </div>
        </a-col>
        <a-col :xs="24" :md="8">
          <a-statistic title="重复暂存文件" :value="maintenanceReport.duplicates?.active || 0" />
          <div class="table-sub-note">
            占用 {{ maintenanceReport.duplicates?.total_size_display || '0 B' }}
          </div>
        </a-col>
        <a-col :xs="24" :md="8">
          <a-statistic title="失败/取消任务" :value="maintenanceReport.tasks?.failed_or_cancelled || 0" />
          <div class="table-sub-note">用于后续失败重试中心和完整性报告。</div>
        </a-col>
      </a-row>
      <a-divider />
      <a-space wrap>
        <a-button
          type="primary"
          :loading="maintenanceActionLoading === 'thumbnails'"
          @click="backfillThumbnails"
        >
          补全历史视频缩略图
        </a-button>
        <a-button
          :loading="maintenanceActionLoading === 'duplicates'"
          @click="scanHistoricalDuplicates"
        >
          扫描历史重复文件
        </a-button>
        <a-button
          :loading="maintenanceActionLoading === 'task-links'"
          @click="backfillTaskLinks"
        >
          修复旧任务媒体关联
        </a-button>
        <a-button @click="loadMaintenanceReport">刷新维护报告</a-button>
      </a-space>
    </a-card>

    <a-card title="重复文件暂存区" class="panel-card" :loading="duplicateLoading">
      <div class="table-sub-note" style="margin-bottom: 12px">
        同一账号、同一帖子、同一媒体序号重复下载时，主媒体库只保留一份；多余实文件会放到这里，由你手动确认后删除。
      </div>
      <a-space wrap style="margin-bottom: 14px">
        <a-tag color="green">重复文件 {{ duplicateSummary.total || 0 }}</a-tag>
        <a-tag color="green">视频 {{ duplicateSummary.videos || 0 }}</a-tag>
        <a-tag color="gold">照片 {{ duplicateSummary.photos || 0 }}</a-tag>
        <a-tag>占用 {{ formatFileSize(duplicateSummary.total_size || 0) }}</a-tag>
        <a-button size="small" @click="loadDuplicates">刷新重复文件</a-button>
      </a-space>
      <a-table
        class="interactive-table"
        :columns="duplicateColumns"
        :data-source="duplicateRows"
        row-key="key"
        size="small"
        :pagination="{ pageSize: 6 }"
        :scroll="{ x: 1120 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'filename'">
            <div class="db-primary-text" :title="record.filename"><strong>{{ record.filename }}</strong></div>
            <div class="table-sub-note db-secondary-text" :title="record.path">{{ record.path }}</div>
          </template>
          <template v-else-if="column.key === 'username'">
            <strong>{{ `@${record.username}` }}</strong>
          </template>
          <template v-else-if="column.key === 'media_type'">
            <a-tag :color="record.media_type === 'video' ? 'green' : 'default'">
              {{ record.media_type === 'video' ? '视频' : '照片' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'size'">
            {{ formatFileSize(record.size) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button size="small" :href="encodeOutputPath(record.path)" target="_blank" :disabled="!record.exists">
                打开
              </a-button>
              <a-popconfirm
                title="只删除这个重复暂存文件，不会删除主媒体库里的视频/图片。确认删除吗？"
                ok-text="删除"
                cancel-text="取消"
                @confirm="deleteDuplicate(record)"
              >
                <a-button size="small" danger :disabled="!record.exists">删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty v-if="!duplicateRows.length" description="暂无重复暂存文件" />
    </a-card>

    <a-card title="数据库分片列表" class="panel-card" :loading="store.state.loading.database">
      <a-table class="interactive-table" :columns="columns" :data-source="shards" row-key="shard_key" :scroll="{ x: 1180 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'display_name'">
            <div class="db-primary-text" :title="record.display_name"><strong>{{ record.display_name }}</strong></div>
            <div class="table-sub-note">
              {{ record.shard_type === 'bucket' ? `覆盖 ${record.username_count || 0} 个账号` : '旧版单账号库' }}
            </div>
          </template>
          <template v-else-if="column.key === 'db_name'">
            <div class="db-primary-text" :title="record.db_name">{{ record.db_name }}</div>
            <div class="table-sub-note db-secondary-text" :title="record.db_path">{{ record.db_path }}</div>
          </template>
          <template v-else-if="column.key === 'usernames'">
            <a-space wrap class="tag-wrap-cluster">
              <a-tag v-for="name in (record.usernames || []).slice(0, 4)" :key="name" color="green">
                {{ `@${name}` }}
              </a-tag>
              <span v-if="(record.username_count || 0) > 4" class="table-sub-note">
                +{{ record.username_count - 4 }}
              </span>
            </a-space>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button size="small" @click="openDetail(record.shard_key)">详情</a-button>
              <a-button size="small" :href="buildDatabaseBackupUrl(record.shard_key)" target="_blank">备份</a-button>
              <a-button
                v-if="record.shard_type === 'legacy'"
                size="small"
                type="primary"
                ghost
                :loading="store.state.loading.databaseMigrate"
                @click="migrateLegacy(record.shard_key)"
              >
                迁移
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card title="按用户查看媒体总况" class="panel-card" :loading="store.state.loading.database">
          <a-table class="interactive-table" :columns="userColumns" :data-source="userRows" row-key="username" size="small" :pagination="{ pageSize: 8 }" :scroll="{ x: 760 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'username'">
                <strong>{{ `@${record.username}` }}</strong>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-button size="small" :href="buildDownloadAllUrl(record.username)" target="_blank">
                  导出用户包
                </a-button>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="12">
        <a-card title="按任务查看产物总况" class="panel-card" :loading="store.state.loading.database">
          <a-table class="interactive-table" :columns="taskColumns" :data-source="taskRows" row-key="task_id" size="small" :pagination="{ pageSize: 8 }" :scroll="{ x: 900 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'task_id'">
                <span class="value-wrap break-all" :title="record.task_id">{{ record.task_id }}</span>
              </template>
              <template v-else-if="column.key === 'username'">
                <strong>{{ `@${record.username}` }}</strong>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button size="small" type="link" @click="openTaskDetail(record.task_id)">详情</a-button>
                  <a-button size="small" :href="buildDownloadAllUrl(record.username, record.task_id)" target="_blank">
                    导出
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-card title="数据库健康检查" class="panel-card" :loading="store.state.loading.databaseHealth">
      <a-table class="interactive-table" :columns="healthColumns" :data-source="healthRows" row-key="shard_key" :pagination="false" :scroll="{ x: 760 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'display_name'">
            <strong class="db-primary-text" :title="record.display_name">{{ record.display_name }}</strong>
          </template>
          <template v-else-if="column.key === 'health_status'">
            <a-tag :color="record.health_status === 'healthy' ? 'green' : 'orange'">
              {{ record.health_status === 'healthy' ? '正常' : '告警' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      width="880"
      title="分片数据库详情"
      :destroy-on-close="false"
    >
      <a-spin :spinning="store.state.loading.databaseDetail">
        <template v-if="detail">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="分片">
              <span class="value-ellipsis" :title="detail.display_name">{{ detail.display_name }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="库文件">
              <span class="value-ellipsis" :title="detail.db_name">{{ detail.db_name }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="路径">
              <span class="value-wrap break-all" :title="detail.db_path">{{ detail.db_path }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="体积">{{ detail.size_display }}</a-descriptions-item>
            <a-descriptions-item label="更新时间">{{ detail.modified_at_display }}</a-descriptions-item>
            <a-descriptions-item label="完整性检查">{{ detail.integrity }}</a-descriptions-item>
            <a-descriptions-item label="分片类型">
              {{ detail.shard_type === 'bucket' ? '固定桶分片' : '旧版账号库' }}
            </a-descriptions-item>
            <a-descriptions-item label="账号数">{{ detail.username_count || 0 }}</a-descriptions-item>
          </a-descriptions>

          <a-divider />

          <a-card title="分片覆盖账号" class="panel-card">
            <a-space wrap class="tag-wrap-cluster">
              <a-tag v-for="name in detail.usernames || []" :key="name" color="green">
                {{ `@${name}` }}
              </a-tag>
            </a-space>
          </a-card>

          <a-divider />

          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :xl="12">
              <a-card title="表结构" class="panel-card">
                <a-collapse>
                  <a-collapse-panel v-for="tableName in detail.tables" :key="tableName" :header="tableName">
                    <a-table
                      :columns="schemaColumns"
                      :data-source="detail.schema?.[tableName] || []"
                      size="small"
                      :pagination="false"
                      row-key="name"
                    />
                  </a-collapse-panel>
                </a-collapse>
              </a-card>
            </a-col>

            <a-col :xs="24" :xl="12">
              <a-card title="最近媒体与标记" class="panel-card">
                <a-descriptions :column="1" size="small" bordered>
                  <a-descriptions-item label="收藏视频">{{ detail.annotation_stats?.favorites || 0 }}</a-descriptions-item>
                  <a-descriptions-item label="已看视频">{{ detail.annotation_stats?.watched || 0 }}</a-descriptions-item>
                  <a-descriptions-item label="稍后看">{{ detail.annotation_stats?.watch_later || 0 }}</a-descriptions-item>
                </a-descriptions>
                <a-divider />
                <a-list :data-source="detail.recent_media || []" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <a-list-item-meta
                        :title="item.name"
                        :description="`@${item.username} · ${item.media_type} · ${formatFileSize(item.size)}`"
                      />
                    </a-list-item>
                  </template>
                </a-list>
              </a-card>
            </a-col>
          </a-row>

          <a-divider />

          <a-card title="这个分片关联到的任务历史" class="panel-card">
            <a-table
              class="interactive-table"
              :columns="historyColumns"
              :data-source="detail.related_history || []"
              size="small"
              row-key="task_id"
              :pagination="{ pageSize: 6 }"
              :scroll="{ x: 620 }"
            />
          </a-card>
        </template>
      </a-spin>
    </a-drawer>
  </a-space>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { api, buildDatabaseBackupUrl, buildDownloadAllUrl } from '../lib/api';
import { encodeOutputPath, formatFileSize } from '../lib/formatters';
import { useWorkbenchStore } from '../store/workbench';

const store = useWorkbenchStore();
const router = useRouter();
const detailOpen = ref(false);
const duplicateLoading = ref(false);
const duplicateRows = ref([]);
const duplicateSummary = ref({});
const maintenanceLoading = ref(false);
const maintenanceActionLoading = ref('');
const maintenanceReport = ref({
  videos: {},
  duplicates: {},
  tasks: {},
});

const summary = computed(() => store.state.database.summary || {});
const shards = computed(() => store.state.database.shards || []);
const userRows = computed(() => store.state.database.users || []);
const taskRows = computed(() => store.state.database.tasks || []);
const healthSummary = computed(() => store.state.databaseHealth.summary || {});
const healthRows = computed(() => store.state.databaseHealth.shards || []);
const detail = computed(() => store.state.databaseDetail);

const columns = [
  { title: '分片', key: 'display_name', dataIndex: 'display_name', width: 180 },
  { title: '数据库文件', key: 'db_name', dataIndex: 'db_name' },
  { title: '账号', key: 'usernames', dataIndex: 'usernames', width: 220 },
  { title: '条目数', key: 'total_items', dataIndex: 'total_items', width: 100 },
  { title: '视频', key: 'videos', dataIndex: 'videos', width: 90 },
  { title: '照片', key: 'photos', dataIndex: 'photos', width: 90 },
  { title: '库大小', key: 'size_display', dataIndex: 'size_display', width: 120 },
  { title: '操作', key: 'actions', width: 160 },
];

const healthColumns = [
  { title: '分片', key: 'display_name', dataIndex: 'display_name', width: 180 },
  { title: '健康度', key: 'health_status', dataIndex: 'health_status', width: 100 },
  { title: '完整性', key: 'integrity', dataIndex: 'integrity', width: 140 },
  { title: '大小', key: 'size_display', dataIndex: 'size_display', width: 120 },
  { title: '更新时间', key: 'modified_at_display', dataIndex: 'modified_at_display' },
];

const userColumns = [
  { title: '用户', key: 'username', dataIndex: 'username', width: 160 },
  { title: '视频', key: 'videos', dataIndex: 'videos', width: 90 },
  { title: '照片', key: 'photos', dataIndex: 'photos', width: 90 },
  { title: '总条目', key: 'total_items', dataIndex: 'total_items', width: 100 },
  { title: '关联任务', key: 'task_count', dataIndex: 'task_count', width: 100 },
  { title: '总大小', key: 'total_size_display', dataIndex: 'total_size_display', width: 120 },
  { title: '最近更新', key: 'last_modified_display', dataIndex: 'last_modified_display' },
  { title: '操作', key: 'actions', width: 130 },
];

const taskColumns = [
  { title: '任务 ID', key: 'task_id', dataIndex: 'task_id', width: 240 },
  { title: '用户', key: 'username', dataIndex: 'username', width: 140 },
  { title: '视频', key: 'videos', dataIndex: 'videos', width: 90 },
  { title: '照片', key: 'photos', dataIndex: 'photos', width: 90 },
  { title: '文档', key: 'documents', dataIndex: 'documents', width: 90 },
  { title: '总条目', key: 'total_items', dataIndex: 'total_items', width: 100 },
  { title: '状态', key: 'status_text', dataIndex: 'status_text', width: 100 },
  { title: '总大小', key: 'total_size_display', dataIndex: 'total_size_display', width: 120 },
  { title: '最近更新', key: 'last_modified_display', dataIndex: 'last_modified_display', width: 170 },
  { title: '操作', key: 'actions', width: 150 },
];

const duplicateColumns = [
  { title: '文件', key: 'filename', dataIndex: 'filename', width: 320 },
  { title: '用户', key: 'username', dataIndex: 'username', width: 120 },
  { title: '类型', key: 'media_type', dataIndex: 'media_type', width: 90 },
  { title: 'Tweet ID', key: 'tweet_id', dataIndex: 'tweet_id', width: 180 },
  { title: '媒体序号', key: 'media_index', dataIndex: 'media_index', width: 90 },
  { title: '任务', key: 'task_id', dataIndex: 'task_id', width: 220 },
  { title: '大小', key: 'size', dataIndex: 'size', width: 100 },
  { title: '时间', key: 'created_at', dataIndex: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 150 },
];

const schemaColumns = [
  { title: '字段', key: 'name', dataIndex: 'name' },
  { title: '类型', key: 'type', dataIndex: 'type', width: 120 },
  { title: '非空', key: 'notnull', dataIndex: 'notnull', width: 80 },
  { title: '主键', key: 'pk', dataIndex: 'pk', width: 80 },
];

const historyColumns = [
  { title: '任务', key: 'task_id_short', dataIndex: 'task_id_short', width: 100 },
  { title: '状态', key: 'status_text', dataIndex: 'status_text', width: 100 },
  { title: '推文', key: 'tweets', dataIndex: 'tweets', width: 90 },
  { title: '视频', key: 'videos', dataIndex: 'videos', width: 90 },
  { title: '时间', key: 'timestamp', dataIndex: 'timestamp' },
];

async function reloadAll() {
  await Promise.all([
    store.loadDatabase(),
    store.loadDatabaseHealth(),
    loadDuplicates(),
    loadMaintenanceReport(),
  ]);
}

async function loadMaintenanceReport() {
  maintenanceLoading.value = true;
  try {
    maintenanceReport.value = await api.getAdminMaintenanceReport();
    return maintenanceReport.value;
  } catch (error) {
    message.error(error.message || '维护报告加载失败');
    return null;
  } finally {
    maintenanceLoading.value = false;
  }
}

async function backfillThumbnails() {
  maintenanceActionLoading.value = 'thumbnails';
  try {
    const payload = await api.backfillAdminThumbnails({ limit: 120 });
    maintenanceReport.value = payload.report || maintenanceReport.value;
    const result = payload.result || {};
    message.success(`缩略图补全完成：生成 ${result.generated || 0} 个，失败 ${result.failed || 0} 个`);
    await Promise.allSettled([store.loadDatabase({ force: true }), loadMaintenanceReport()]);
  } catch (error) {
    message.error(error.message || '缩略图补全失败');
  } finally {
    maintenanceActionLoading.value = '';
  }
}

async function scanHistoricalDuplicates() {
  maintenanceActionLoading.value = 'duplicates';
  try {
    const payload = await api.scanAdminDuplicates({ limit: 300 });
    maintenanceReport.value = payload.report || maintenanceReport.value;
    const result = payload.result || {};
    message.success(`历史重复扫描完成：导出 ${result.exported || 0} 个重复暂存文件`);
    await Promise.allSettled([loadDuplicates(), store.loadDatabase({ force: true }), loadMaintenanceReport()]);
  } catch (error) {
    message.error(error.message || '历史重复扫描失败');
  } finally {
    maintenanceActionLoading.value = '';
  }
}

async function backfillTaskLinks() {
  maintenanceActionLoading.value = 'task-links';
  try {
    const payload = await api.backfillAdminTaskLinks();
    maintenanceReport.value = payload.report || maintenanceReport.value;
    const linked = payload?.result?.linked || 0;
    message.success(`旧任务媒体关联修复完成：新增关联 ${linked} 条`);
    await Promise.allSettled([store.loadDatabase({ force: true }), loadMaintenanceReport()]);
  } catch (error) {
    message.error(error.message || '旧任务媒体关联修复失败');
  } finally {
    maintenanceActionLoading.value = '';
  }
}

async function loadDuplicates() {
  duplicateLoading.value = true;
  try {
    const payload = await api.getAdminDuplicates({ limit: 200 });
    duplicateRows.value = payload.items || [];
    duplicateSummary.value = payload.summary || {};
    return payload;
  } catch (error) {
    message.error(error.message || '重复文件列表加载失败');
    return null;
  } finally {
    duplicateLoading.value = false;
  }
}

async function deleteDuplicate(record) {
  if (!record?.id) {
    return;
  }
  try {
    await api.deleteAdminDuplicate(record.id, record.shard_key);
    message.success('重复暂存文件已删除，主媒体库不受影响');
    await loadDuplicates();
  } catch (error) {
    message.error(error.message || '重复文件删除失败');
  }
}

async function openDetail(shardKey) {
  try {
    const payload = await store.loadDatabaseDetail(shardKey);
    if (!payload) {
      message.warning('这个分片当前不存在');
      return;
    }
    detailOpen.value = true;
  } catch (error) {
    message.error(error.message || '分片详情加载失败');
  }
}

function openTaskDetail(taskId) {
  if (!taskId) {
    return;
  }
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

async function migrateLegacy(shardKey) {
  try {
    const payload = await store.migrateLegacyDatabase(shardKey);
    const moved = payload?.result?.usernames?.length
      ? payload.result.usernames.map((name) => `@${name}`).join('、')
      : '目标账号';
    message.success(`${moved} 已迁移到固定桶分片`);
    detailOpen.value = false;
  } catch (error) {
    message.error(error.message || '旧版账号库迁移失败');
  }
}

async function migrateAllLegacy() {
  try {
    const payload = await store.migrateLegacyDatabase();
    const count = payload?.result?.migrated_count || 0;
    message.success(`已完成 ${count} 个旧版账号库迁移`);
    detailOpen.value = false;
  } catch (error) {
    message.error(error.message || '批量迁移失败');
  }
}

onMounted(() => {
  reloadAll();
});
</script>
