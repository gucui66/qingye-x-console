<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <section class="new-task-hero">
      <div class="new-task-hero-copy">
        <div class="login-kicker">{{ nt.kicker }}</div>
        <h2>{{ nt.title }}</h2>
        <p>{{ nt.subtitle }}</p>
      </div>
      <div class="new-task-hero-status">
        <span>{{ resolvedUsername ? nt.targetAccount : nt.activeTasks }}</span>
        <strong>{{ resolvedUsername ? `@${resolvedUsername}` : activeTaskCount }}</strong>
        <a-button size="small" @click="goTasks">{{ nt.viewQueue }}</a-button>
      </div>
    </section>

    <a-row :gutter="[16, 16]" align="stretch">
      <a-col :xs="24" :xl="15">
        <a-card class="panel-card new-task-form-card" :title="nt.taskParams">
          <a-form :model="form" layout="vertical" @finish="submitTask">
            <a-row :gutter="[16, 0]">
              <a-col :xs="24" :md="10">
                <a-form-item :label="nt.inputMethod">
                  <a-segmented
                    v-model:value="form.inputType"
                    :options="[
                      { label: nt.username, value: 'username' },
                      { label: nt.profileUrl, value: 'url' }
                    ]"
                    block
                  />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="14">
                <a-form-item v-if="form.inputType === 'username'" :label="nt.username">
                  <a-input
                    v-model:value="form.username"
                    size="large"
                    :placeholder="nt.usernamePlaceholder"
                    @press-enter="submitTask"
                  />
                </a-form-item>

                <a-form-item v-else :label="nt.profileUrl">
                  <a-input
                    v-model:value="form.profileUrl"
                    size="large"
                    :placeholder="nt.profilePlaceholder"
                    @press-enter="submitTask"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <div v-if="resolvedUsername" class="new-task-resolved-line">
              <span>{{ nt.resolvedAccount }}</span>
              <strong>{{ `@${resolvedUsername}` }}</strong>
              <a-button type="link" size="small" :href="targetProfileUrl" target="_blank">
                {{ nt.openXProfile }}
              </a-button>
            </div>

            <a-alert
              v-if="activeDuplicateTask"
              class="new-task-duplicate-alert"
              type="warning"
              show-icon
              :message="duplicateAlertMessage"
              :description="duplicateAlertDescription"
            />

            <a-form-item :label="nt.preset">
              <div class="new-task-preset-grid">
                <button
                  v-for="preset in taskPresets"
                  :key="preset.key"
                  type="button"
                  class="new-task-preset-card"
                  :class="{ 'new-task-preset-card-active': activePresetKey === preset.key }"
                  @click="applyTaskPreset(preset)"
                >
                  <strong>{{ preset.label }}</strong>
                  <span>{{ preset.description }}</span>
                </button>
              </div>
            </a-form-item>

            <a-row :gutter="[16, 0]">
              <a-col :xs="24" :md="8">
                <a-form-item :label="nt.maxTweets">
                  <a-input-number v-model:value="form.maxTweets" :min="1" size="large" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item :label="nt.scrapeMethod">
                  <a-radio-group v-model:value="form.scrapeMethod" class="new-task-radio-row">
                    <a-radio-button value="api">API</a-radio-button>
                    <a-radio-button value="selenium">Selenium</a-radio-button>
                  </a-radio-group>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item v-if="form.scrapeMethod === 'selenium'" :label="nt.seleniumMode">
                  <a-segmented
                    v-model:value="form.seleniumBehaviorMode"
                    :options="seleniumBehaviorOptions"
                    block
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item :label="nt.downloadOptions">
              <div class="new-task-download-grid">
                <label class="new-task-check-card">
                  <a-checkbox v-model:checked="form.downloadVideos">{{ nt.downloadVideos }}</a-checkbox>
                  <span>{{ nt.downloadVideosHelp }}</span>
                </label>
                <label class="new-task-check-card">
                  <a-checkbox v-model:checked="form.downloadPhotos">{{ nt.downloadPhotos }}</a-checkbox>
                  <span>{{ nt.downloadPhotosHelp }}</span>
                </label>
                <label class="new-task-check-card">
                  <a-checkbox v-model:checked="form.downloadReplies">{{ nt.collectReplies }}</a-checkbox>
                  <span>{{ nt.collectRepliesHelp }}</span>
                </label>
              </div>
            </a-form-item>

            <div class="new-task-action-bar">
              <a-button size="large" @click="resetTaskDefaults">
                {{ nt.resetConfig }}
              </a-button>
              <a-button size="large" @click="checkCurrentAccount" :loading="checkingCurrent" :disabled="!canSubmit">
                {{ nt.checkAccount }}
              </a-button>
              <a-button size="large" @click="addCurrentDraft" :disabled="!canSubmit">
                {{ nt.addDraft }}
              </a-button>
              <a-button size="large" @click="previewProfile" :loading="previewing" :disabled="!canSubmit">
                {{ nt.previewProfile }}
              </a-button>
              <a-button type="primary" size="large" :loading="submitting" :disabled="!canSubmit" @click="submitTask">
                {{ submitButtonText }}
              </a-button>
            </div>
          </a-form>
        </a-card>

        <a-card class="panel-card new-task-draft-card" :title="nt.draftQueue">
          <div class="new-task-bulk-box">
            <textarea
              v-model="bulkUsernames"
              class="new-task-bulk-input"
              :placeholder="nt.bulkPlaceholder"
            />
            <a-space wrap>
              <a-button @click="addBulkDrafts" :disabled="!bulkUsernames.trim()">
                {{ nt.addBulkDrafts }}
              </a-button>
              <a-button @click="checkAllDrafts" :loading="checkingDrafts" :disabled="!draftTasks.length">
                {{ nt.checkAll }}
              </a-button>
              <a-button type="primary" @click="createDraftTasks" :loading="creatingDrafts" :disabled="!creatableDrafts.length">
                {{ nt.createBatch }} {{ creatableDrafts.length || '' }}
              </a-button>
              <a-button @click="clearFinishedDrafts" :disabled="!finishedDrafts.length">
                {{ nt.clearFinished }}
              </a-button>
              <a-button danger @click="clearDrafts" :disabled="!draftTasks.length">
                {{ nt.clearDrafts }}
              </a-button>
            </a-space>
          </div>

          <div v-if="draftTasks.length" class="new-task-draft-list">
            <div
              v-for="draft in draftTasks"
              :key="draft.id"
              class="new-task-draft-row"
              :class="`new-task-draft-row-${draft.status}`"
            >
              <div class="new-task-draft-main">
                <strong>{{ `@${draft.username}` }}</strong>
                <span>{{ draft.message || draftConfigLabel(draft) }}</span>
              </div>
              <a-space wrap>
                <a-tag :color="draftStatusColor(draft.status)">
                  {{ draftStatusLabel(draft.status) }}
                </a-tag>
                <a-button size="small" @click="checkDraft(draft)" :loading="draft.status === 'checking'">
                  {{ nt.check }}
                </a-button>
                <a-button
                  v-if="draft.taskId"
                  size="small"
                  @click="goTaskDetail(draft.taskId)"
                >
                  {{ nt.openTask }}
                </a-button>
                <a-button size="small" @click="removeDraft(draft.id)">
                  {{ nt.remove }}
                </a-button>
              </a-space>
            </div>
          </div>
          <a-empty v-else :description="nt.noDrafts" />
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="9">
        <a-space direction="vertical" size="large" style="width: 100%">
          <a-card class="panel-card" :title="nt.beforeSubmit">
            <div class="new-task-summary">
              <div class="new-task-summary-row">
                <span>{{ nt.summaryAccount }}</span>
                <strong>{{ resolvedUsername ? `@${resolvedUsername}` : nt.waitingInput }}</strong>
              </div>
              <div class="new-task-summary-row">
                <span>{{ nt.summaryCount }}</span>
                <strong>{{ maxTweetsLabel }}</strong>
              </div>
              <div class="new-task-summary-row">
                <span>{{ nt.summaryMethod }}</span>
                <strong>{{ taskModeLabel }}</strong>
              </div>
              <div class="new-task-summary-row">
                <span>{{ nt.summaryDownloads }}</span>
                <strong>{{ selectedDownloadLabels }}</strong>
              </div>
              <div class="new-task-summary-row">
                <span>{{ nt.summaryCheck }}</span>
                <strong>{{ currentCheckLabel }}</strong>
              </div>
            </div>
            <a-button
              v-if="activeDuplicateTask"
              block
              type="primary"
              ghost
              @click="goTaskDetail(activeDuplicateTask.task_id)"
            >
              {{ nt.openExistingActiveTask }}
            </a-button>
          </a-card>

          <a-card class="panel-card" :title="nt.quickPick">
            <div class="new-task-chip-section">
              <span>{{ nt.recentTasks }}</span>
              <div class="new-task-chip-grid">
                <a-button
                  v-for="item in recentUserChips"
                  :key="`recent:${item}`"
                  size="small"
                  @click="fillUsername(item)"
                >
                  {{ `@${item}` }}
                </a-button>
              </div>
            </div>
            <div class="new-task-chip-section">
              <span>{{ nt.accountDirectory }}</span>
              <div class="new-task-chip-grid">
                <a-button
                  v-for="item in directoryQuickUsers"
                  :key="`directory:${item.normalized_username}`"
                  size="small"
                  @click="fillUsername(item.username)"
                >
                  {{ item.alias ? `${item.display_name} · @${item.username}` : `@${item.username}` }}
                </a-button>
              </div>
            </div>
            <a-empty
              v-if="!recentUserChips.length && !directoryQuickUsers.length"
              :description="nt.noQuickUsers"
            />
          </a-card>

          <a-card class="panel-card" :title="nt.afterCreateTitle">
            <a-list size="small">
              <a-list-item v-for="item in nt.afterCreateItems" :key="item">{{ item }}</a-list-item>
            </a-list>
          </a-card>

          <a-card class="panel-card" :title="nt.recentTasks">
            <a-list v-if="recentTasks.length" size="small" :data-source="recentTasks">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <button type="button" class="new-task-link" @click="goTaskDetail(item.task_id)">
                        {{ `@${item.username}` }}
                      </button>
                    </template>
                    <template #description>
                      {{ `${statusLabel(item.status)} · ${formatDateTime(item.created_at) || nt.unknownTime}` }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
            <a-empty v-else :description="nt.noTaskRecords" />
          </a-card>
        </a-space>
      </a-col>
    </a-row>

    <a-modal v-model:open="previewModalOpen" :title="nt.profilePreview" :footer="null">
      <a-spin :spinning="previewing">
        <a-result
          v-if="previewData"
          status="success"
          :title="`@${previewData.username}`"
          :sub-title="previewData.message"
        >
          <template #extra>
            <a-space>
              <a-button type="primary" :href="previewData.profile_url" target="_blank">
                {{ nt.openTwitter }}
              </a-button>
              <a-button :href="previewData.x_url" target="_blank">
                {{ nt.openX }}
              </a-button>
            </a-space>
          </template>
        </a-result>
      </a-spin>
    </a-modal>
  </a-space>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { api } from '../lib/api';
import { extractUsernameFromUrl, formatDateTime } from '../lib/formatters';
import { currentLanguage } from '../lib/i18n';
import { useWorkbenchStore } from '../store/workbench';

const router = useRouter();
const route = useRoute();
const store = useWorkbenchStore();
const TASK_DEFAULTS_STORAGE_KEY = 'qingye:new-task-defaults';
const TASK_DRAFTS_STORAGE_KEY = 'qingye:new-task-drafts';
let storageWarningShown = false;

const newTaskMessages = {
  'zh-CN': {
    kicker: '创建爬取任务',
    title: '新建爬取任务',
    subtitle: '把账号、采集数量、下载内容和 Selenium 行为集中在一个页面确认，提交后直接进入任务详情盯进度。',
    targetAccount: '即将采集账号',
    activeTasks: '当前活跃任务',
    viewQueue: '查看任务队列',
    taskParams: '任务参数',
    inputMethod: '输入方式',
    username: '用户名',
    profileUrl: '主页链接',
    usernamePlaceholder: '输入用户名、@用户名，或直接粘贴 X 主页链接',
    profilePlaceholder: 'https://twitter.com/username 或 https://x.com/username',
    resolvedAccount: '已解析账号',
    openXProfile: '打开 X 主页',
    duplicateMessage: (username) => `@${username} 已有进行中的任务`,
    duplicateDescription: (task, status) => `任务 ${task} 当前状态：${status}。继续点击主按钮会直接打开这条任务。`,
    preset: '采集模板',
    maxTweets: '最大推文数',
    scrapeMethod: '抓取方式',
    seleniumMode: 'Selenium 行为模式',
    downloadOptions: '下载选项',
    downloadVideos: '下载视频',
    downloadVideosHelp: '把本地可播放视频保存进媒体库',
    downloadPhotos: '下载照片',
    downloadPhotosHelp: '同步保存推文图片和预览素材',
    collectReplies: '收集回复',
    collectRepliesHelp: '需要更完整上下文时打开',
    resetConfig: '重置配置',
    checkAccount: '检查账号',
    addDraft: '加入草稿',
    previewProfile: '预览主页',
    draftQueue: '任务草稿队列',
    bulkPlaceholder: '批量粘贴账号或主页链接，一行一个，例如：\npap8630\nhttps://x.com/MasterTopkr',
    addBulkDrafts: '批量加入草稿',
    checkAll: '检查全部',
    createBatch: '批量创建',
    clearFinished: '清理已完成',
    clearDrafts: '清空草稿',
    check: '检查',
    openTask: '打开任务',
    remove: '移除',
    noDrafts: '还没有草稿，可以先加入一个账号或批量粘贴账号',
    beforeSubmit: '提交前确认',
    summaryAccount: '目标账号',
    waitingInput: '等待输入',
    summaryCount: '采集数量',
    summaryMethod: '采集方式',
    summaryDownloads: '下载内容',
    summaryCheck: '账号检查',
    openExistingActiveTask: '打开已有进行中任务',
    quickPick: '快速选择账号',
    recentTasks: '最近任务',
    accountDirectory: '账号目录',
    noQuickUsers: '暂无可快速选择的账号',
    afterCreateTitle: '创建后会发生什么',
    afterCreateItems: [
      '任务会进入队列，并自动开始执行。',
      '如果同账号已有进行中任务，会直接定位到原任务。',
      '提交成功后会跳到任务详情页，看截图、日志和阶段进度。',
      '完成后可以从视频中心或用户时间流继续浏览结果。',
    ],
    unknownTime: '时间未知',
    noTaskRecords: '当前还没有任务记录',
    profilePreview: '主页预览',
    openTwitter: '打开 Twitter',
    openX: '打开 X',
    balanced: '均衡',
    stable: '稳定',
    human: '拟人',
    presetBalanced: '均衡采集',
    presetBalancedDesc: '常规账号默认选择，采正文、视频、图片和回复。',
    presetMedia: '媒体优先',
    presetMediaDesc: '重点保存视频和图片，少抓回复，适合资料整理。',
    presetQuick: '快速试抓',
    presetQuickDesc: '先抓 20 条正文，不下载媒体，适合验证账号。',
    presetFull: '完整归档',
    presetFullDesc: '稳定模式采集，保留媒体和回复，适合认真入库。',
    unlimited: '不限制',
    countSuffix: '条',
    textOnly: '只采集正文',
    start: '开始爬取',
    openExisting: '打开已有任务',
    notChecked: '未检查',
  },
  en: {
    kicker: 'Create Crawl Task',
    title: 'New Crawl Task',
    subtitle: 'Confirm the account, crawl volume, media downloads, and Selenium behavior in one focused workflow.',
    targetAccount: 'Target account',
    activeTasks: 'Active tasks',
    viewQueue: 'View task queue',
    taskParams: 'Task Parameters',
    inputMethod: 'Input method',
    username: 'Username',
    profileUrl: 'Profile URL',
    usernamePlaceholder: 'Enter username, @username, or paste an X profile URL',
    profilePlaceholder: 'https://twitter.com/username or https://x.com/username',
    resolvedAccount: 'Resolved account',
    openXProfile: 'Open X profile',
    duplicateMessage: (username) => `@${username} already has an active task`,
    duplicateDescription: (task, status) => `Task ${task} is currently ${status}. Clicking the main button will open it directly.`,
    preset: 'Crawl preset',
    maxTweets: 'Max posts',
    scrapeMethod: 'Crawl method',
    seleniumMode: 'Selenium behavior',
    downloadOptions: 'Download options',
    downloadVideos: 'Download videos',
    downloadVideosHelp: 'Save playable local videos into the media library',
    downloadPhotos: 'Download photos',
    downloadPhotosHelp: 'Save post images and preview assets',
    collectReplies: 'Collect replies',
    collectRepliesHelp: 'Enable this when you need fuller context',
    resetConfig: 'Reset',
    checkAccount: 'Check account',
    addDraft: 'Add draft',
    previewProfile: 'Preview profile',
    draftQueue: 'Draft Queue',
    bulkPlaceholder: 'Paste accounts or profile URLs, one per line, for example:\npap8630\nhttps://x.com/MasterTopkr',
    addBulkDrafts: 'Add drafts',
    checkAll: 'Check all',
    createBatch: 'Create batch',
    clearFinished: 'Clear finished',
    clearDrafts: 'Clear drafts',
    check: 'Check',
    openTask: 'Open task',
    remove: 'Remove',
    noDrafts: 'No drafts yet. Add one account or paste accounts in bulk.',
    beforeSubmit: 'Before Submit',
    summaryAccount: 'Target account',
    waitingInput: 'Waiting for input',
    summaryCount: 'Crawl volume',
    summaryMethod: 'Crawl method',
    summaryDownloads: 'Downloads',
    summaryCheck: 'Account check',
    openExistingActiveTask: 'Open active task',
    quickPick: 'Quick Pick',
    recentTasks: 'Recent Tasks',
    accountDirectory: 'Account Directory',
    noQuickUsers: 'No quick-pick accounts yet',
    afterCreateTitle: 'What happens after creation',
    afterCreateItems: [
      'The task enters the queue and starts automatically.',
      'If the same account already has an active task, the existing task opens instead.',
      'After creation, you will land on the task detail page for screenshots, logs, and progress.',
      'When complete, continue browsing results in Media Library or User Timeline.',
    ],
    unknownTime: 'Unknown time',
    noTaskRecords: 'No task records yet',
    profilePreview: 'Profile Preview',
    openTwitter: 'Open Twitter',
    openX: 'Open X',
    balanced: 'Balanced',
    stable: 'Stable',
    human: 'Human-like',
    presetBalanced: 'Balanced crawl',
    presetBalancedDesc: 'Default for regular accounts: text, videos, photos, and replies.',
    presetMedia: 'Media first',
    presetMediaDesc: 'Prioritize videos and photos, with fewer replies, for library curation.',
    presetQuick: 'Quick test',
    presetQuickDesc: 'Fetch 20 text posts without media to validate an account quickly.',
    presetFull: 'Full archive',
    presetFullDesc: 'Stable mode with media and replies for serious archiving.',
    unlimited: 'Unlimited',
    countSuffix: 'posts',
    textOnly: 'Text only',
    start: 'Start crawl',
    openExisting: 'Open existing task',
    notChecked: 'Not checked',
  },
};

const nt = computed(() => newTaskMessages[currentLanguage.value] || newTaskMessages['zh-CN']);

const defaultTaskForm = {
  inputType: 'username',
  username: '',
  profileUrl: '',
  maxTweets: null,
  scrapeMethod: 'selenium',
  seleniumBehaviorMode: 'balanced',
  downloadVideos: true,
  downloadPhotos: true,
  downloadReplies: true,
};

const form = reactive({ ...defaultTaskForm });

const submitting = ref(false);
const previewing = ref(false);
const checkingCurrent = ref(false);
const checkingDrafts = ref(false);
const creatingDrafts = ref(false);
const previewModalOpen = ref(false);
const previewData = ref(null);
const activePresetKey = ref('balanced');
const bulkUsernames = ref('');
const currentCheck = ref({
  username: '',
  status: 'idle',
  message: '',
});
const draftTasks = ref([]);

const seleniumBehaviorOptions = computed(() => [
  { label: nt.value.balanced, value: 'balanced' },
  { label: nt.value.stable, value: 'stable' },
  { label: nt.value.human, value: 'human' },
]);

const taskPresets = computed(() => [
  {
    key: 'balanced',
    label: nt.value.presetBalanced,
    description: nt.value.presetBalancedDesc,
    values: {
      maxTweets: null,
      scrapeMethod: 'selenium',
      seleniumBehaviorMode: 'balanced',
      downloadVideos: true,
      downloadPhotos: true,
      downloadReplies: true,
    },
  },
  {
    key: 'media',
    label: nt.value.presetMedia,
    description: nt.value.presetMediaDesc,
    values: {
      maxTweets: null,
      scrapeMethod: 'selenium',
      seleniumBehaviorMode: 'stable',
      downloadVideos: true,
      downloadPhotos: true,
      downloadReplies: false,
    },
  },
  {
    key: 'quick',
    label: nt.value.presetQuick,
    description: nt.value.presetQuickDesc,
    values: {
      maxTweets: 20,
      scrapeMethod: 'selenium',
      seleniumBehaviorMode: 'balanced',
      downloadVideos: false,
      downloadPhotos: false,
      downloadReplies: false,
    },
  },
  {
    key: 'full',
    label: nt.value.presetFull,
    description: nt.value.presetFullDesc,
    values: {
      maxTweets: null,
      scrapeMethod: 'selenium',
      seleniumBehaviorMode: 'stable',
      downloadVideos: true,
      downloadPhotos: true,
      downloadReplies: true,
    },
  },
]);

const activeTaskCount = computed(() => {
  return store.displayTasks.value.filter((item) =>
    ['running', 'pending', 'paused', 'user_paused'].includes(item.status)
  ).length;
});

const recentTasks = computed(() => store.sortedTasks.value.slice(0, 5));
const recentUserChips = computed(() => {
  const usernames = [];
  store.sortedTasks.value.forEach((task) => {
    const username = String(task.username || '').trim();
    if (username && !usernames.some((item) => item.toLowerCase() === username.toLowerCase())) {
      usernames.push(username);
    }
  });
  return usernames.slice(0, 6);
});
const directoryQuickUsers = computed(() => {
  const recentSet = new Set(recentUserChips.value.map((item) => item.toLowerCase()));
  return (store.usernameDirectoryItems.value || [])
    .filter((item) => !item.hidden && !recentSet.has(String(item.username || '').toLowerCase()))
    .slice(0, 8);
});
const resolvedUsername = computed(() => resolveUsername());
const canSubmit = computed(() => Boolean(resolvedUsername.value));
const targetProfileUrl = computed(() => `https://x.com/${resolvedUsername.value || ''}`);
const activeDuplicateTask = computed(() => {
  return findActiveDuplicateTask(resolvedUsername.value);
});
const taskModeLabel = computed(() => {
  if (form.scrapeMethod === 'api') {
    return 'API';
  }
  const mode = seleniumBehaviorOptions.value.find((item) => item.value === form.seleniumBehaviorMode)?.label || nt.value.balanced;
  return `Selenium · ${mode}`;
});
const maxTweetsLabel = computed(() => form.maxTweets ? `${form.maxTweets} ${nt.value.countSuffix}` : nt.value.unlimited);
const selectedDownloadLabels = computed(() => {
  const labels = [];
  if (form.downloadVideos) {
    labels.push(nt.value.downloadVideos);
  }
  if (form.downloadPhotos) {
    labels.push(nt.value.downloadPhotos);
  }
  if (form.downloadReplies) {
    labels.push(nt.value.collectReplies);
  }
  return labels.length ? labels.join(currentLanguage.value === 'en' ? ', ' : '、') : nt.value.textOnly;
});
const currentCheckLabel = computed(() => {
  if (!resolvedUsername.value) {
    return nt.value.waitingInput;
  }
  if (currentCheck.value.username !== resolvedUsername.value) {
    return nt.value.notChecked;
  }
  return currentCheck.value.message || draftStatusLabel(currentCheck.value.status);
});
const creatableDrafts = computed(() => draftTasks.value.filter((draft) =>
  !['created', 'creating', 'duplicate'].includes(draft.status)
));
const finishedDrafts = computed(() => draftTasks.value.filter((draft) =>
  ['created', 'duplicate'].includes(draft.status)
));
const submitButtonText = computed(() => {
  if (activeDuplicateTask.value) {
    return nt.value.openExisting;
  }
  if (resolvedUsername.value) {
    return `${nt.value.start} @${resolvedUsername.value}`;
  }
  return nt.value.start;
});
const duplicateAlertMessage = computed(() => nt.value.duplicateMessage(resolvedUsername.value));
const duplicateAlertDescription = computed(() => nt.value.duplicateDescription(
  activeDuplicateTask.value?.task_id || '',
  activeDuplicateTask.value ? statusLabel(activeDuplicateTask.value.status) : ''
));

function resolveUsername() {
  if (form.inputType === 'username') {
    const rawValue = String(form.username || '').trim();
    return (extractUsernameFromUrl(rawValue) || rawValue)
      .replace(/^@+/, '')
      .replace(/[/?#].*$/, '')
      .trim();
  }
  return extractUsernameFromUrl(form.profileUrl || '');
}

function normalizeDraftUsername(value) {
  return (extractUsernameFromUrl(value) || String(value || ''))
    .trim()
    .replace(/^@+/, '')
    .replace(/[/?#].*$/, '')
    .trim();
}

function statusLabel(status) {
  const labels = currentLanguage.value === 'en'
    ? {
      pending: 'Pending',
      running: 'Running',
      paused: 'Auto paused',
      user_paused: 'Paused',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Cancelled',
    }
    : {
      pending: '等待中',
      running: '运行中',
      paused: '自动暂停',
      user_paused: '手动暂停',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    };
  return labels[status] || status;
}

function fillUsername(username) {
  const value = normalizeDraftUsername(username);
  if (!value) {
    return;
  }
  form.inputType = 'username';
  form.username = value;
}

function applyTaskPreset(preset) {
  if (!preset?.values) {
    return;
  }
  activePresetKey.value = preset.key;
  Object.assign(form, preset.values);
}

function buildDraftConfig() {
  return {
    maxTweets: form.maxTweets,
    scrapeMethod: form.scrapeMethod,
    seleniumBehaviorMode: form.seleniumBehaviorMode,
    downloadVideos: form.downloadVideos,
    downloadPhotos: form.downloadPhotos,
    downloadReplies: form.downloadReplies,
    presetKey: activePresetKey.value,
    modeLabel: taskModeLabel.value,
    maxTweetsLabel: maxTweetsLabel.value,
    downloadLabels: selectedDownloadLabels.value,
  };
}

function draftConfigLabel(draft) {
  return `${draft.config.maxTweetsLabel} · ${draft.config.modeLabel} · ${draft.config.downloadLabels}`;
}

function findActiveDuplicateTask(username) {
  const normalized = String(username || '').toLowerCase();
  if (!normalized) {
    return null;
  }
  return store.sortedTasks.value.find((task) => {
    return String(task.username || '').toLowerCase() === normalized
      && ['running', 'pending', 'paused', 'user_paused'].includes(task.status);
  }) || null;
}

function upsertDraft(username, config = buildDraftConfig()) {
  const normalized = normalizeDraftUsername(username);
  if (!normalized) {
    return false;
  }

  const existing = draftTasks.value.find((draft) => draft.username.toLowerCase() === normalized.toLowerCase());
  if (existing) {
    existing.config = config;
    existing.status = existing.status === 'created' ? 'ready' : existing.status;
    existing.message = currentLanguage.value === 'en' ? 'Updated to current configuration' : '已更新为当前配置';
    return true;
  }

  draftTasks.value = [
    ...draftTasks.value,
    {
      id: `${normalized}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
      username: normalized,
      config,
      status: 'ready',
      message: currentLanguage.value === 'en' ? 'Waiting for check' : '等待检查',
      taskId: '',
    },
  ];
  return true;
}

function addCurrentDraft() {
  if (!resolvedUsername.value) {
    message.warning(currentLanguage.value === 'en' ? 'Enter a valid username or profile URL' : '请输入有效的用户名或主页链接');
    return;
  }
  if (upsertDraft(resolvedUsername.value)) {
    message.success(currentLanguage.value === 'en' ? `Added draft: @${resolvedUsername.value}` : `已加入草稿：@${resolvedUsername.value}`);
  }
}

function addBulkDrafts() {
  const values = String(bulkUsernames.value || '')
    .split(/[\n,，\s]+/)
    .map((item) => normalizeDraftUsername(item))
    .filter(Boolean);
  const uniqueValues = [...new Set(values.map((item) => item.toLowerCase()))]
    .map((lowercase) => values.find((item) => item.toLowerCase() === lowercase));

  let added = 0;
  uniqueValues.forEach((username) => {
    if (upsertDraft(username)) {
      added += 1;
    }
  });
  bulkUsernames.value = '';
  message.success(currentLanguage.value === 'en' ? `Added ${added} drafts` : `已加入 ${added} 个草稿`);
}

function removeDraft(draftId) {
  draftTasks.value = draftTasks.value.filter((draft) => draft.id !== draftId);
}

function clearDrafts() {
  draftTasks.value = [];
}

function clearFinishedDrafts() {
  draftTasks.value = draftTasks.value.filter((draft) => !['created', 'duplicate'].includes(draft.status));
}

function serializeDraft(draft) {
  const transientStatus = ['checking', 'creating'].includes(draft.status);
  return {
    id: draft.id,
    username: draft.username,
    config: draft.config,
    status: transientStatus ? 'ready' : draft.status,
    message: transientStatus ? (currentLanguage.value === 'en' ? 'Waiting for check' : '等待检查') : draft.message,
    taskId: draft.taskId || '',
  };
}

function loadDraftQueue() {
  try {
    const rawValue = window.localStorage.getItem(TASK_DRAFTS_STORAGE_KEY);
    const items = rawValue ? JSON.parse(rawValue) : [];
    if (!Array.isArray(items)) {
      return;
    }
    draftTasks.value = items
      .map((item) => ({
        id: item.id || `${item.username}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
        username: normalizeDraftUsername(item.username),
        config: {
          ...buildDraftConfig(),
          ...(item.config || {}),
        },
        status: item.status || 'ready',
        message: item.message || (currentLanguage.value === 'en' ? 'Waiting for check' : '等待检查'),
        taskId: item.taskId || '',
      }))
      .filter((item) => item.username);
  } catch (error) {
    window.localStorage.removeItem(TASK_DRAFTS_STORAGE_KEY);
  }
}

function persistDraftQueue() {
  const items = draftTasks.value.map((draft) => serializeDraft(draft));
  try {
    window.localStorage.setItem(TASK_DRAFTS_STORAGE_KEY, JSON.stringify(items));
  } catch (error) {
    if (!storageWarningShown) {
      storageWarningShown = true;
      message.warning(currentLanguage.value === 'en' ? 'Browser storage is unavailable. Drafts will not be saved automatically.' : '浏览器本地存储不可用，任务草稿不会自动保存');
    }
  }
}

function draftStatusLabel(status) {
  const labels = currentLanguage.value === 'en'
    ? {
      idle: 'Not checked',
      ready: 'Ready',
      checking: 'Checking',
      ok: 'Can create',
      duplicate: 'Existing task',
      error: 'Error',
      creating: 'Creating',
      created: 'Created',
    }
    : {
      idle: '未检查',
      ready: '待检查',
      checking: '检查中',
      ok: '可创建',
      duplicate: '已有任务',
      error: '异常',
      creating: '创建中',
      created: '已创建',
    };
  return labels[status] || status;
}

function draftStatusColor(status) {
  const colors = {
    ready: 'default',
    checking: 'processing',
    ok: 'green',
    duplicate: 'orange',
    error: 'red',
    creating: 'blue',
    created: 'blue',
  };
  return colors[status] || 'default';
}

async function checkDraft(draft) {
  if (!draft?.username) {
    return draft;
  }

  const duplicate = findActiveDuplicateTask(draft.username);
  if (duplicate) {
    draft.status = 'duplicate';
    draft.taskId = duplicate.task_id;
    draft.message = currentLanguage.value === 'en'
      ? `Existing active task: ${statusLabel(duplicate.status)}`
      : `已有进行中任务：${statusLabel(duplicate.status)}`;
    return draft;
  }

  draft.status = 'checking';
  draft.message = currentLanguage.value === 'en' ? 'Checking account' : '正在检查账号';
  try {
    const payload = await api.previewProfile(draft.username);
    draft.status = 'ok';
    draft.message = payload?.user?.message || (currentLanguage.value === 'en' ? 'Account format is valid' : '账号格式可用');
    draft.taskId = '';
  } catch (error) {
    draft.status = 'error';
    draft.message = error.message || (currentLanguage.value === 'en' ? 'Account check failed' : '账号检查失败');
  }
  return draft;
}

async function checkCurrentAccount() {
  if (!resolvedUsername.value) {
    message.warning(currentLanguage.value === 'en' ? 'Enter a valid username or profile URL' : '请输入有效的用户名或主页链接');
    return;
  }
  checkingCurrent.value = true;
  const draft = {
    username: resolvedUsername.value,
    status: 'ready',
    message: '',
    taskId: '',
  };
  try {
    await checkDraft(draft);
    currentCheck.value = {
      username: resolvedUsername.value,
      status: draft.status,
      message: draft.message,
    };
    if (draft.status === 'ok') {
      message.success(currentLanguage.value === 'en' ? `@${resolvedUsername.value} check passed` : `@${resolvedUsername.value} 检查通过`);
    } else if (draft.status === 'duplicate') {
      message.warning(currentLanguage.value === 'en' ? `@${resolvedUsername.value} already has an active task` : `@${resolvedUsername.value} 已有进行中任务`);
    }
  } finally {
    checkingCurrent.value = false;
  }
}

async function checkAllDrafts() {
  if (!draftTasks.value.length) {
    return;
  }
  checkingDrafts.value = true;
  try {
    for (const draft of draftTasks.value) {
      if (draft.status !== 'created') {
        await checkDraft(draft);
      }
    }
  } finally {
    checkingDrafts.value = false;
  }
}

async function createDraftTasks() {
  if (!creatableDrafts.value.length || creatingDrafts.value) {
    return;
  }

  creatingDrafts.value = true;
  let created = 0;
  let skipped = 0;
  let failed = 0;
  try {
    for (const draft of creatableDrafts.value) {
      const duplicate = findActiveDuplicateTask(draft.username);
      if (duplicate) {
        draft.status = 'duplicate';
        draft.taskId = duplicate.task_id;
        draft.message = currentLanguage.value === 'en'
          ? `Existing active task: ${statusLabel(duplicate.status)}`
          : `已有进行中任务：${statusLabel(duplicate.status)}`;
        skipped += 1;
        continue;
      }

      draft.status = 'creating';
      draft.message = currentLanguage.value === 'en' ? 'Creating task' : '正在创建任务';
      try {
        const payload = await store.createTask({
          username: draft.username,
          max_tweets: draft.config.maxTweets,
          scrape_method: draft.config.scrapeMethod,
          selenium_behavior_mode: draft.config.seleniumBehaviorMode,
          download_videos: draft.config.downloadVideos,
          download_photos: draft.config.downloadPhotos,
          download_replies: draft.config.downloadReplies,
        });
        draft.taskId = payload.task_id || '';
        if (payload.existing_task) {
          draft.status = 'duplicate';
          draft.message = currentLanguage.value === 'en' ? 'Existing active task' : '已有进行中任务';
          skipped += 1;
        } else {
          draft.status = 'created';
          draft.message = currentLanguage.value === 'en' ? 'Task added to queue' : '任务已加入队列';
          created += 1;
        }
      } catch (error) {
        draft.status = 'error';
        draft.message = error.message || (currentLanguage.value === 'en' ? 'Creation failed' : '创建失败');
        failed += 1;
      }
    }
    message.success(currentLanguage.value === 'en'
      ? `Batch complete: ${created} created, ${skipped} skipped, ${failed} failed`
      : `批量创建完成：新建 ${created} 个，跳过 ${skipped} 个，失败 ${failed} 个`);
  } finally {
    creatingDrafts.value = false;
  }
}

function taskPresetMatches(preset) {
  return Boolean(preset?.values)
    && form.maxTweets === preset.values.maxTweets
    && form.scrapeMethod === preset.values.scrapeMethod
    && form.seleniumBehaviorMode === preset.values.seleniumBehaviorMode
    && form.downloadVideos === preset.values.downloadVideos
    && form.downloadPhotos === preset.values.downloadPhotos
    && form.downloadReplies === preset.values.downloadReplies;
}

function syncActivePresetKey() {
  activePresetKey.value = taskPresets.value.find((preset) => taskPresetMatches(preset))?.key || 'custom';
}

function applyStoredTaskDefaults() {
  try {
    const rawValue = window.localStorage.getItem(TASK_DEFAULTS_STORAGE_KEY);
    const payload = rawValue ? JSON.parse(rawValue) : {};
    Object.assign(form, {
      ...defaultTaskForm,
      ...payload,
      username: '',
      profileUrl: '',
    });
    activePresetKey.value = payload.presetKey || 'custom';
  } catch (error) {
    window.localStorage.removeItem(TASK_DEFAULTS_STORAGE_KEY);
  }
}

function persistTaskDefaults() {
  const payload = {
    maxTweets: form.maxTweets,
    scrapeMethod: form.scrapeMethod,
    seleniumBehaviorMode: form.seleniumBehaviorMode,
    downloadVideos: form.downloadVideos,
    downloadPhotos: form.downloadPhotos,
    downloadReplies: form.downloadReplies,
    presetKey: activePresetKey.value,
  };
  try {
    window.localStorage.setItem(TASK_DEFAULTS_STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    if (!storageWarningShown) {
      storageWarningShown = true;
      message.warning(currentLanguage.value === 'en' ? 'Browser storage is unavailable. Defaults will not be saved automatically.' : '浏览器本地存储不可用，任务默认配置不会自动保存');
    }
  }
}

function resetTaskDefaults() {
  window.localStorage.removeItem(TASK_DEFAULTS_STORAGE_KEY);
  Object.assign(form, {
    ...defaultTaskForm,
    username: form.username,
    profileUrl: form.profileUrl,
    inputType: form.inputType,
  });
  activePresetKey.value = 'balanced';
}

async function previewProfile() {
  const username = resolvedUsername.value;
  if (!username) {
    message.warning(currentLanguage.value === 'en' ? 'Enter a valid username or profile URL' : '请输入有效的用户名或主页链接');
    return;
  }

  previewing.value = true;
  previewModalOpen.value = true;
  previewData.value = null;
  try {
    const payload = await api.previewProfile(username);
    previewData.value = payload.user;
  } catch (error) {
    message.error(error.message || (currentLanguage.value === 'en' ? 'Preview failed' : '预览失败'));
  } finally {
    previewing.value = false;
  }
}

async function submitTask() {
  if (submitting.value) {
    return;
  }

  const username = resolvedUsername.value;
  if (!username) {
    message.warning(currentLanguage.value === 'en' ? 'Enter a valid username or profile URL' : '请输入有效的用户名或主页链接');
    return;
  }

  if (activeDuplicateTask.value?.task_id) {
    message.info(currentLanguage.value === 'en' ? `@${username} already has an active task. Opening it now.` : `@${username} 已有进行中的任务，已为你打开原任务`);
    goTaskDetail(activeDuplicateTask.value.task_id);
    return;
  }

  submitting.value = true;
  try {
    const payload = await store.createTask({
      username,
      max_tweets: form.maxTweets,
      scrape_method: form.scrapeMethod,
      selenium_behavior_mode: form.seleniumBehaviorMode,
      download_videos: form.downloadVideos,
      download_photos: form.downloadPhotos,
      download_replies: form.downloadReplies,
    });

    if (payload.existing_task) {
      message.info(currentLanguage.value === 'en' ? `@${username} already has an active task. Opening it now.` : `@${username} 已有进行中的任务，已为你定位到原任务`);
      goTaskDetail(payload.task_id);
      return;
    }

    message.success(currentLanguage.value === 'en' ? `Task created: @${username}` : `任务已创建：@${username}`);
    form.username = '';
    form.profileUrl = '';
    goTaskDetail(payload.task_id);
  } catch (error) {
    message.error(error.message || (currentLanguage.value === 'en' ? 'Task creation failed' : '创建任务失败'));
  } finally {
    submitting.value = false;
  }
}

function goTaskDetail(taskId) {
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

function goTasks() {
  router.push({ name: 'tasks' });
}

onMounted(() => {
  applyStoredTaskDefaults();
  loadDraftQueue();
  const queryUsername = String(route.query.username || route.query.user || '').trim();
  if (queryUsername) {
    fillUsername(queryUsername);
  }
});

watch(
  () => resolvedUsername.value,
  () => {
    currentCheck.value = {
      username: '',
      status: 'idle',
      message: '',
    };
  }
);

watch(
  () => [
    form.maxTweets,
    form.scrapeMethod,
    form.seleniumBehaviorMode,
    form.downloadVideos,
    form.downloadPhotos,
    form.downloadReplies,
  ],
  () => {
    syncActivePresetKey();
    persistTaskDefaults();
  }
);

watch(
  draftTasks,
  () => {
    persistDraftQueue();
  },
  { deep: true }
);
</script>

<style scoped>
.new-task-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 260px);
  gap: 18px;
  align-items: stretch;
  padding: 24px;
  border: 1px solid #d7ebd2;
  border-radius: 22px;
  background: linear-gradient(135deg, #f3faef 0%, #ffffff 60%, #eef8eb 100%);
}

.new-task-hero-copy h2 {
  margin: 6px 0 10px;
  font-size: 32px;
  line-height: 1.1;
  color: #102310;
}

.new-task-hero-copy p {
  max-width: 760px;
  margin: 0;
  color: #526153;
}

.new-task-hero-status {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid #dcebdd;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.new-task-hero-status span {
  font-size: 12px;
  color: #5f6b63;
}

.new-task-hero-status strong {
  font-size: 34px;
  line-height: 1;
  color: #102310;
}

.new-task-form-card :deep(.ant-card-head-title) {
  font-size: 18px;
}

.new-task-resolved-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: -4px 0 16px;
  padding: 10px 12px;
  border: 1px solid #dfe8df;
  border-radius: 12px;
  background: #f8fbf8;
}

.new-task-resolved-line span {
  color: #667268;
}

.new-task-resolved-line strong {
  color: #102310;
}

.new-task-duplicate-alert {
  margin-bottom: 16px;
}

.new-task-preset-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.new-task-preset-card {
  display: flex;
  min-height: 104px;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid #dfe8df;
  border-radius: 14px;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.new-task-preset-card:hover,
.new-task-preset-card-active {
  border-color: #9bd088;
  background: #f3faef;
  transform: translateY(-1px);
}

.new-task-preset-card strong {
  color: #102310;
}

.new-task-preset-card span {
  color: #647067;
  line-height: 1.45;
}

.new-task-radio-row {
  width: 100%;
}

.new-task-radio-row :deep(label) {
  width: 50%;
  text-align: center;
}

.new-task-download-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.new-task-check-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 94px;
  padding: 14px;
  border: 1px solid #dfe8df;
  border-radius: 14px;
  background: #f8fbf8;
  cursor: pointer;
}

.new-task-check-card span {
  color: #647067;
}

.new-task-summary {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.new-task-summary-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #edf2ed;
}

.new-task-summary-row:last-child {
  border-bottom: 0;
}

.new-task-summary-row span {
  color: #667268;
}

.new-task-summary-row strong {
  max-width: 62%;
  text-align: right;
  color: #102310;
}

.new-task-chip-section {
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
}

.new-task-chip-section:last-child {
  margin-bottom: 0;
}

.new-task-chip-section > span {
  font-size: 12px;
  color: #667268;
}

.new-task-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.new-task-chip-grid :deep(.ant-btn) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.new-task-action-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

.new-task-draft-card {
  margin-top: 16px;
}

.new-task-bulk-box {
  display: grid;
  gap: 12px;
}

.new-task-bulk-input {
  width: 100%;
  min-height: 96px;
  resize: vertical;
  padding: 12px;
  border: 1px solid #dfe8df;
  border-radius: 14px;
  background: #f8fbf8;
  color: #102310;
  font: inherit;
  line-height: 1.5;
}

.new-task-bulk-input:focus {
  border-color: #9bd088;
  outline: none;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.1);
}

.new-task-draft-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.new-task-draft-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid #dfe8df;
  border-radius: 14px;
  background: #ffffff;
}

.new-task-draft-row-ok {
  border-color: #9bd088;
  background: #f6fcf2;
}

.new-task-draft-row-error {
  border-color: #f0b4b4;
  background: #fff8f8;
}

.new-task-draft-row-created {
  border-color: #b9d4ff;
  background: #f7fbff;
}

.new-task-draft-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.new-task-draft-main strong {
  color: #102310;
}

.new-task-draft-main span {
  color: #647067;
}

.new-task-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: #111111;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 900px) {
  .new-task-hero {
    grid-template-columns: 1fr;
  }

  .new-task-download-grid {
    grid-template-columns: 1fr;
  }

  .new-task-preset-grid {
    grid-template-columns: 1fr;
  }

  .new-task-action-bar {
    flex-direction: column;
  }

  .new-task-draft-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .new-task-resolved-line,
  .new-task-summary-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .new-task-summary-row strong {
    max-width: 100%;
    text-align: left;
  }
}
</style>
