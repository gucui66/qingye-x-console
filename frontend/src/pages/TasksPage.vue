<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card class="tasks-hero-card panel-card">
      <div class="tasks-hero-shell">
        <div class="tasks-hero-copy">
          <div class="login-kicker">{{ tm.kicker }}</div>
          <h2>{{ focusTaskHeroTitle }}</h2>
          <p>{{ focusTaskHeroSubtitle }}</p>
          <a-space wrap>
            <a-button type="primary" @click="goNewTask">
              {{ tm.newTask }}
            </a-button>
            <a-button @click="openFocusTaskDetail" :disabled="!store.focusTask.value?.task_id">
              {{ tm.openCurrent }}
            </a-button>
            <a-button @click="filterToFocusUser" :disabled="!store.focusTask.value?.username">
              {{ tm.focusCurrentAccount }}
            </a-button>
            <a-button @click="showActiveOnly">
              {{ tm.activeOnly }}
            </a-button>
          </a-space>
        </div>
        <div class="tasks-hero-stats">
          <div class="tasks-hero-stat">
            <span>{{ tm.focusAccount }}</span>
            <strong>{{ store.focusTask.value ? `@${store.focusTask.value.username}` : tm.noTask }}</strong>
          </div>
          <div class="tasks-hero-stat">
            <span>{{ tm.progress }}</span>
            <strong>{{ `${store.state.progress.percentage || 0}%` }}</strong>
          </div>
          <div class="tasks-hero-stat">
            <span>{{ tm.queueResults }}</span>
            <strong>{{ tm.count(filteredTasks.length) }}</strong>
          </div>
        </div>
      </div>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card metric-green">
          <div class="metric-label">{{ tm.activeTasks }}</div>
          <div class="metric-value">{{ stats.active }}</div>
          <div class="metric-foot">{{ tm.activeTasksHint }}</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">{{ tm.completed }}</div>
          <div class="metric-value">{{ stats.completed }}</div>
          <div class="metric-foot">{{ tm.completedHint }}</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">{{ tm.failedOrCancelled }}</div>
          <div class="metric-value">{{ stats.ended }}</div>
          <div class="metric-foot">{{ tm.failedHint }}</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12" :xl="6">
        <a-card class="metric-card">
          <div class="metric-label">{{ tm.latestCompletedAccount }}</div>
          <div class="metric-value metric-value-small">
            {{ store.latestCompletedTask.value ? `@${store.latestCompletedTask.value.username}` : '--' }}
          </div>
          <div class="metric-foot">
            {{ tm.latestCollected(store.latestCompletedTask.value?.results?.total_tweets || 0) }}
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24">
        <a-card v-if="failedTasks.length" :title="tm.repairCenter" class="panel-card tasks-repair-card">
          <a-space direction="vertical" size="middle" style="width: 100%">
            <div class="tasks-repair-head">
              <div class="tasks-repair-copy">
                <strong>{{ tm.failedFound(failedTasks.length) }}</strong>
                <span>{{ tm.repairHint }}</span>
              </div>
              <a-space wrap>
                <a-button size="small" @click="showEndedOnly">{{ tm.showFailedOnly }}</a-button>
                <a-button size="small" type="primary" ghost @click="retryAllFailed" :loading="retryingTaskId === '__all__'">
                  {{ tm.retryAll }}
                </a-button>
              </a-space>
            </div>

            <div class="tasks-repair-list">
              <div
                v-for="task in failedTasks"
                :key="task.task_id"
                class="tasks-repair-row"
              >
                <div class="tasks-repair-row-main">
                  <div class="tasks-repair-row-title">
                    <strong>{{ `@${task.username}` }}</strong>
                    <a-tag :color="tagColor(task.status)">{{ statusLabel(task.status) }}</a-tag>
                  </div>
                  <div class="tasks-repair-row-message" :title="task.error_message || task.progress_text || task.task_id">
                    {{ task.error_message || task.progress_text || task.task_id }}
                  </div>
                </div>
                <a-space wrap>
                  <a-button size="small" type="primary" @click="retryTask(task)" :loading="retryingTaskId === task.task_id">
                    {{ tm.retry }}
                  </a-button>
                  <a-button size="small" @click="goTaskDetail(task.task_id)">
                    {{ tm.detail }}
                  </a-button>
                  <a-button size="small" @click="goNewTask(task.username)">
                    {{ tm.createAgain }}
                  </a-button>
                  <a-button size="small" danger @click="confirmDelete(task.task_id)">
                    {{ tm.deleteRecord }}
                  </a-button>
                </a-space>
              </div>
            </div>
          </a-space>
        </a-card>

        <a-card :title="tm.workbench" class="panel-card">
          <a-space direction="vertical" size="middle" style="width: 100%">
            <div class="tasks-summary-strip">
              <div class="tasks-summary-pill">
                <span>{{ tm.currentFilter }}</span>
                <strong>{{ activeFilterLabel }}</strong>
              </div>
              <div class="tasks-summary-pill">
                <span>{{ tm.currentResults }}</span>
                <strong>{{ tm.count(filteredTasks.length) }}</strong>
              </div>
              <div class="tasks-summary-pill">
                <span>{{ tm.accountGroups }}</span>
                <strong>{{ tm.userCount(filteredTaskGroups.length) }}</strong>
              </div>
              <div class="tasks-summary-pill">
                <span>{{ tm.focusAccount }}</span>
                <strong :title="store.focusTask.value ? `@${store.focusTask.value.username}` : tm.noTask">
                  {{ store.focusTask.value ? `@${store.focusTask.value.username}` : tm.noTask }}
                </strong>
              </div>
            </div>

            <div class="tasks-quick-actions">
              <a-button type="primary" size="small" @click="goNewTask">
                {{ tm.newTask }}
              </a-button>
              <a-button size="small" @click="showActiveOnly">
                {{ tm.activeOnly }}
              </a-button>
              <a-button size="small" @click="filterToFocusUser" :disabled="!store.focusTask.value?.username">
                {{ tm.focusAccountOnly }}
              </a-button>
              <a-button size="small" @click="openLatestCompleted" :disabled="!store.latestCompletedTask.value?.username">
                {{ tm.openLatestLibrary }}
              </a-button>
              <a-button size="small" @click="resetTaskFilters">
                {{ tm.clearFilters }}
              </a-button>
              <a-button size="small" @click="expandAllGroups" :disabled="!filteredTaskGroups.length">
                {{ tm.expandAllUsers }}
              </a-button>
              <a-button size="small" @click="collapseAllGroups" :disabled="!filteredTaskGroups.length">
                {{ tm.collapseAllUsers }}
              </a-button>
            </div>

            <div class="tasks-batch-bar">
              <div class="tasks-batch-copy">
                <strong>{{ selectedTasks.length ? tm.selectedTasks(selectedTasks.length) : tm.batchReady }}</strong>
                <span>{{ selectedTasks.length ? batchSelectionSummary : tm.batchHint }}</span>
              </div>
              <a-space wrap>
                <a-button size="small" @click="selectVisibleTasks" :disabled="!filteredTasks.length">
                  {{ tm.selectVisible }}
                </a-button>
                <a-button size="small" @click="clearSelection" :disabled="!selectedTasks.length">
                  {{ tm.clearSelection }}
                </a-button>
                <a-button size="small" @click="batchPauseSelected" :disabled="!batchPauseIds.length">
                  {{ tm.batchPause }}
                </a-button>
                <a-button size="small" @click="batchResumeSelected" :disabled="!batchResumeIds.length">
                  {{ tm.batchResume }}
                </a-button>
                <a-button size="small" danger @click="batchCancelSelected" :disabled="!batchCancelableIds.length">
                  {{ tm.batchCancel }}
                </a-button>
                <a-button size="small" @click="batchDeleteSelected" :disabled="!batchDeleteIds.length">
                  {{ tm.batchDelete }}
                </a-button>
              </a-space>
            </div>

            <div class="tasks-toolbar">
              <a-segmented
                v-model:value="statusFilter"
                :options="statusOptions"
                block
                class="tasks-toolbar-filter"
              />
              <a-input-search
                v-model:value="keyword"
                allow-clear
                :placeholder="tm.searchPlaceholder"
                class="tasks-toolbar-search"
              />
            </div>

            <a-alert
              type="info"
              show-icon
              :message="tm.cardWorkflowTitle"
              :description="tm.cardWorkflowDesc"
            />

            <div v-if="filteredTaskGroups.length" class="task-group-board">
              <div v-for="group in filteredTaskGroups" :key="group.usernameKey" class="task-group-card panel-card">
                <div class="task-group-head">
                  <div class="task-group-copy">
                    <div style="display: flex; align-items: center; gap: 10px">
                      <button
                        type="button"
                        class="feed-inline-avatar"
                        @click.stop="goUserFeed(group.username)"
                      >
                        {{ String(group.username || '').slice(0, 1).toUpperCase() }}
                      </button>
                      <div class="task-group-user" :title="`@${group.username}`">{{ `@${group.username}` }}</div>
                    </div>
                    <div class="task-group-meta">
                      {{ tm.groupMeta(group.tasks.length, group.activeCount, group.completedCount) }}
                    </div>
                  </div>
                  <a-space wrap @click.stop>
                    <a-button size="small" type="primary" ghost @click="goNewTask(group.username)">
                      {{ tm.crawlAgain }}
                    </a-button>
                    <a-button size="small" @click="goLibrary(group.username)">
                      {{ tm.library }}
                    </a-button>
                    <a-button size="small" @click="toggleGroup(group.usernameKey)">
                      {{ isGroupExpanded(group.usernameKey) ? tm.collapseTasks : tm.expandTasks(group.tasks.length) }}
                    </a-button>
                  </a-space>
                </div>

                <div class="task-board">
                  <div
                    v-for="task in visibleGroupTasks(group)"
                    :key="task.task_id"
                    class="task-card"
                    :class="{ 'task-card-selected': selectedTaskIds.includes(task.task_id) }"
                    role="button"
                    tabindex="0"
                    @click="goTaskDetail(task.task_id)"
                    @keyup.enter="goTaskDetail(task.task_id)"
                    @keyup.space.prevent="goTaskDetail(task.task_id)"
                  >
                    <div class="task-card-head">
                      <div class="task-card-copy">
                        <div class="task-card-user" :title="`@${task.username}`">{{ `@${task.username}` }}</div>
                        <div class="task-card-meta" :title="task.task_id">
                          {{ task.task_id }}
                        </div>
                      </div>
                      <div class="task-card-tags">
                        <a-button
                          size="small"
                          class="task-card-selector"
                          @click.stop="toggleTaskSelection(task.task_id)"
                        >
                          {{ selectedTaskIds.includes(task.task_id) ? tm.selected : tm.select }}
                        </a-button>
                        <a-tag :color="tagColor(task.status)">
                          {{ statusLabel(task.status) }}
                        </a-tag>
                      </div>
                    </div>

                    <div class="task-card-stats">
                      <div class="task-stat-item">
                        <span>{{ tm.scraped }}</span>
                        <strong>{{ task.scraped_count || 0 }}</strong>
                      </div>
                      <div class="task-stat-item">
                        <span>{{ tm.target }}</span>
                        <strong>{{ task.max_tweets || '∞' }}</strong>
                      </div>
                      <div class="task-stat-item">
                        <span>{{ tm.videos }}</span>
                        <strong>{{ task.results?.videos || 0 }}</strong>
                      </div>
                      <div class="task-stat-item">
                        <span>{{ tm.photos }}</span>
                        <strong>{{ task.results?.photos || 0 }}</strong>
                      </div>
                    </div>

                    <a-progress
                      :percent="task.progress || 0"
                      size="small"
                      :stroke-color="{ '0%': '#9dd87f', '100%': '#4f9956' }"
                    />

                    <div class="task-card-status-line">
                      <span :title="task.progress_text || task.error_message || tm.openFullLogHint">
                        {{ task.progress_text || task.error_message || tm.openFullLogHint }}
                      </span>
                    </div>

                    <div class="task-card-foot">
                      <div class="task-card-time" :title="tm.createdAt(formatDateTime(task.created_at) || tm.unknown)">
                        {{ tm.createdAt(formatDateTime(task.created_at) || tm.unknown) }}
                      </div>
                      <a-space wrap class="task-card-actions" @click.stop>
                        <a-button
                          v-if="['running', 'pending'].includes(task.status)"
                          size="small"
                          @click="store.pauseTask(task.task_id)"
                        >
                          {{ tm.pause }}
                        </a-button>
                        <a-button
                          v-if="['paused', 'user_paused'].includes(task.status)"
                          size="small"
                          @click="store.resumeTask(task.task_id)"
                        >
                          {{ tm.resume }}
                        </a-button>
                        <a-button
                          v-if="['running', 'pending', 'paused', 'user_paused'].includes(task.status)"
                          danger
                          size="small"
                          @click="confirmCancel(task.task_id)"
                        >
                          {{ tm.cancel }}
                        </a-button>
                        <a-button
                          v-if="task.status === 'completed'"
                          size="small"
                          type="primary"
                          ghost
                          @click="goLibrary(task.username)"
                        >
                          {{ tm.library }}
                        </a-button>
                        <a-button
                          size="small"
                          @click="goTaskDetail(task.task_id)"
                        >
                          {{ tm.detail }}
                        </a-button>
                        <a-button
                          v-if="['completed', 'failed', 'cancelled'].includes(task.status)"
                          size="small"
                          @click="confirmDelete(task.task_id)"
                        >
                          {{ tm.delete }}
                        </a-button>
                      </a-space>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <a-empty v-else :description="tm.noFilteredTasks" />
          </a-space>
        </a-card>
      </a-col>
    </a-row>

  </a-space>
</template>

<script setup>
import { Modal, message } from 'ant-design-vue';
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { api } from '../lib/api';
import { formatDateTime } from '../lib/formatters';
import { currentLanguage } from '../lib/i18n';
import { useWorkbenchStore } from '../store/workbench';

const router = useRouter();
const store = useWorkbenchStore();

const statusFilter = ref('all');
const keyword = ref('');
const selectedTaskIds = ref([]);
const expandedGroupKeys = ref([]);
const retryingTaskId = ref('');

const taskMessages = {
  'zh-CN': {
    kicker: '任务指挥台',
    newTask: '新建爬取任务',
    openCurrent: '打开当前任务',
    focusCurrentAccount: '只看当前账号',
    activeOnly: '只看活跃任务',
    focusAccount: '焦点账号',
    noTask: '当前无任务',
    progress: '进度',
    queueResults: '队列结果',
    activeTasks: '活跃任务',
    activeTasksHint: '正在运行、排队或暂停中的任务',
    completed: '已完成',
    completedHint: '可以直接进入资料库查看结果',
    failedOrCancelled: '失败或取消',
    failedHint: '建议优先打开详情看截图和错误信息',
    latestCompletedAccount: '最近完成账号',
    latestCollected: (count) => `最近抓到 ${count} 条内容`,
    repairCenter: '异常任务处理中心',
    failedFound: (count) => `发现 ${count} 条失败或取消任务`,
    repairHint: '优先从这里重试、查看详情、重新创建或清理记录，不用在任务长列表里翻。',
    showFailedOnly: '只看异常任务',
    retryAll: '全部重试',
    retry: '重试',
    detail: '详情',
    createAgain: '再次创建',
    deleteRecord: '删除记录',
    workbench: '任务工作台',
    currentFilter: '当前筛选',
    currentResults: '当前结果',
    accountGroups: '账号分组',
    focusAccountOnly: '只看焦点账号',
    openLatestLibrary: '打开最近完成资料库',
    clearFilters: '清空筛选',
    expandAllUsers: '展开全部用户',
    collapseAllUsers: '收起全部用户',
    selectedTasks: (count) => `已选中 ${count} 条任务`,
    batchReady: '批量操作已就绪',
    batchHint: '先点任务卡右上角“选择”，再执行批量暂停、继续、取消或删除。',
    selectVisible: '全选当前结果',
    clearSelection: '清空选择',
    batchPause: '批量暂停',
    batchResume: '批量继续',
    batchCancel: '批量取消',
    batchDelete: '批量删除',
    searchPlaceholder: '搜索账号 / 任务 ID',
    cardWorkflowTitle: '任务交互已经改成卡片式工作流',
    cardWorkflowDesc: '点击任意任务卡都会立即进入任务详情，卡片底部保留快速操作。',
    groupMeta: (total, active, completed) => `共 ${total} 条任务，活跃 ${active} 条，已完成 ${completed} 条`,
    crawlAgain: '再次爬取',
    library: '资料库',
    collapseTasks: '收起任务',
    expandTasks: (count) => `展开全部 ${count} 条`,
    selected: '已选',
    select: '选择',
    scraped: '已抓取',
    target: '目标',
    videos: '视频',
    photos: '照片',
    openFullLogHint: '点击查看完整日志、截图和差异信息',
    createdAt: (time) => `创建于 ${time}`,
    unknown: '未知',
    pause: '暂停',
    resume: '继续',
    cancel: '取消',
    delete: '删除',
    noFilteredTasks: '当前筛选条件下没有任务',
    count: (count) => `${count} 条`,
    userCount: (count) => `${count} 个用户`,
    all: '全部',
    active: '活跃中',
    completedFilter: '已完成',
    ended: '失败/取消',
    allTasks: '全部任务',
    queueTitle: '任务队列与批量处理',
    focusTitle: (username) => `当前优先盯住 @${username}`,
    queueSubtitle: '这里专门看进度、筛选任务、处理暂停失败和批量操作；新建任务已经拆到独立入口。',
    runningSubtitle: '这个任务正在运行，建议优先打开详情盯截图和阶段变化。',
    noneSelected: '暂无已选任务',
    batchSummary: (pause, resume, cancel, remove) => `可暂停 ${pause} 条，可继续 ${resume} 条，可取消 ${cancel} 条，可删除 ${remove} 条`,
    pending: '等待中',
    running: '运行中',
    paused: '自动暂停',
    userPaused: '手动暂停',
    failed: '失败',
    cancelled: '已取消',
    batchSuccess: (message, count) => `${message}（${count} 条）`,
    batchPartial: (message, success, failed) => `${message}，成功 ${success} 条，失败 ${failed} 条`,
    batchFailed: (failed) => `批量操作失败，共 ${failed} 条未成功`,
    cancelTaskTitle: '取消任务',
    cancelTaskContent: '取消后这个任务会停止当前抓取流程，你确定要继续吗？',
    confirmCancel: '确认取消',
    thinkAgain: '再想想',
    taskCancelled: '任务已取消',
    deleteTaskTitle: '删除任务',
    deleteTaskContent: '删除后这条任务记录会从列表中移除，并清理这条任务自己的截图、文档快照和对应产物，确定继续吗？',
    confirmDelete: '确认删除',
    taskDeleted: '任务已删除',
    pauseDone: '批量暂停完成',
    resumeDone: '批量继续完成',
    taskRequeued: '任务已重新加入队列',
    retryFailed: '重试任务失败',
    retryDonePartial: (success, failed) => `重试完成：成功 ${success} 条，失败 ${failed} 条`,
    requeuedCount: (count) => `已重新加入队列：${count} 条`,
    batchCancelTitle: '批量取消任务',
    batchCancelContent: (count) => `将取消 ${count} 条任务，确定继续吗？`,
    batchCancelDone: '批量取消完成',
    batchDeleteTitle: '批量删除任务',
    batchDeleteContent: (count) => `将删除 ${count} 条已结束任务记录，并清理这些任务自己的产物，确定继续吗？`,
    batchDeleteDone: '批量删除完成',
  },
  en: {
    kicker: 'Task Command',
    newTask: 'New Crawl Task',
    openCurrent: 'Open current task',
    focusCurrentAccount: 'Current account only',
    activeOnly: 'Active tasks only',
    focusAccount: 'Focus account',
    noTask: 'No active task',
    progress: 'Progress',
    queueResults: 'Queue results',
    activeTasks: 'Active Tasks',
    activeTasksHint: 'Running, queued, or paused tasks',
    completed: 'Completed',
    completedHint: 'Open the library to review results',
    failedOrCancelled: 'Failed or Cancelled',
    failedHint: 'Open details first for screenshots and errors',
    latestCompletedAccount: 'Latest completed account',
    latestCollected: (count) => `${count} items collected recently`,
    repairCenter: 'Failure Recovery Center',
    failedFound: (count) => `${count} failed or cancelled tasks found`,
    repairHint: 'Retry, inspect details, recreate, or clean records here instead of digging through the full task list.',
    showFailedOnly: 'Failed only',
    retryAll: 'Retry all',
    retry: 'Retry',
    detail: 'Details',
    createAgain: 'Create again',
    deleteRecord: 'Delete record',
    workbench: 'Task Workbench',
    currentFilter: 'Current filter',
    currentResults: 'Current results',
    accountGroups: 'Account groups',
    focusAccountOnly: 'Focus account only',
    openLatestLibrary: 'Open latest library',
    clearFilters: 'Clear filters',
    expandAllUsers: 'Expand all users',
    collapseAllUsers: 'Collapse all users',
    selectedTasks: (count) => `${count} tasks selected`,
    batchReady: 'Batch actions ready',
    batchHint: 'Select task cards first, then pause, resume, cancel, or delete in batch.',
    selectVisible: 'Select visible',
    clearSelection: 'Clear selection',
    batchPause: 'Batch pause',
    batchResume: 'Batch resume',
    batchCancel: 'Batch cancel',
    batchDelete: 'Batch delete',
    searchPlaceholder: 'Search account / task ID',
    cardWorkflowTitle: 'Task interaction now uses a card workflow',
    cardWorkflowDesc: 'Click any task card to open details. Quick actions stay at the bottom of each card.',
    groupMeta: (total, active, completed) => `${total} tasks, ${active} active, ${completed} completed`,
    crawlAgain: 'Crawl again',
    library: 'Library',
    collapseTasks: 'Collapse tasks',
    expandTasks: (count) => `Expand all ${count}`,
    selected: 'Selected',
    select: 'Select',
    scraped: 'Scraped',
    target: 'Target',
    videos: 'Videos',
    photos: 'Photos',
    openFullLogHint: 'Open details for full logs, screenshots, and diffs',
    createdAt: (time) => `Created at ${time}`,
    unknown: 'Unknown',
    pause: 'Pause',
    resume: 'Resume',
    cancel: 'Cancel',
    delete: 'Delete',
    noFilteredTasks: 'No tasks match the current filters',
    count: (count) => `${count} items`,
    userCount: (count) => `${count} users`,
    all: 'All',
    active: 'Active',
    completedFilter: 'Completed',
    ended: 'Failed/Cancelled',
    allTasks: 'All tasks',
    queueTitle: 'Task Queue and Batch Operations',
    focusTitle: (username) => `Watching @${username}`,
    queueSubtitle: 'Track progress, filter tasks, handle paused or failed jobs, and run batch actions here.',
    runningSubtitle: 'This task is running. Open details to watch screenshots and stage changes.',
    noneSelected: 'No tasks selected',
    batchSummary: (pause, resume, cancel, remove) => `${pause} pausable, ${resume} resumable, ${cancel} cancellable, ${remove} deletable`,
    pending: 'Pending',
    running: 'Running',
    paused: 'Auto paused',
    userPaused: 'Paused',
    failed: 'Failed',
    cancelled: 'Cancelled',
    batchSuccess: (message, count) => `${message} (${count})`,
    batchPartial: (message, success, failed) => `${message}: ${success} succeeded, ${failed} failed`,
    batchFailed: (failed) => `Batch action failed for ${failed} tasks`,
    cancelTaskTitle: 'Cancel task',
    cancelTaskContent: 'This stops the current crawl flow. Continue?',
    confirmCancel: 'Cancel task',
    thinkAgain: 'Keep it',
    taskCancelled: 'Task cancelled',
    deleteTaskTitle: 'Delete task',
    deleteTaskContent: 'This removes the task record and cleans this task’s screenshots, snapshots, and outputs. Continue?',
    confirmDelete: 'Delete',
    taskDeleted: 'Task deleted',
    pauseDone: 'Batch pause complete',
    resumeDone: 'Batch resume complete',
    taskRequeued: 'Task requeued',
    retryFailed: 'Failed to retry task',
    retryDonePartial: (success, failed) => `Retry complete: ${success} succeeded, ${failed} failed`,
    requeuedCount: (count) => `${count} tasks requeued`,
    batchCancelTitle: 'Batch cancel tasks',
    batchCancelContent: (count) => `Cancel ${count} tasks. Continue?`,
    batchCancelDone: 'Batch cancel complete',
    batchDeleteTitle: 'Batch delete tasks',
    batchDeleteContent: (count) => `Delete ${count} ended task records and clean their outputs. Continue?`,
    batchDeleteDone: 'Batch delete complete',
  },
};

const tm = computed(() => taskMessages[currentLanguage.value] || taskMessages['zh-CN']);
const statusOptions = computed(() => [
  { label: tm.value.all, value: 'all' },
  { label: tm.value.active, value: 'active' },
  { label: tm.value.completedFilter, value: 'completed' },
  { label: tm.value.ended, value: 'ended' },
]);
const filterLabelMap = computed(() => ({
  all: tm.value.allTasks,
  active: tm.value.active,
  completed: tm.value.completedFilter,
  ended: tm.value.ended,
}));

const stats = computed(() => {
  const tasks = store.sortedTasks.value;
  return {
    active: tasks.filter((task) => ['running', 'pending', 'paused', 'user_paused'].includes(task.status)).length,
    completed: tasks.filter((task) => task.status === 'completed').length,
    ended: tasks.filter((task) => ['failed', 'cancelled'].includes(task.status)).length,
  };
});

const activeFilterLabel = computed(() => filterLabelMap.value[statusFilter.value] || tm.value.allTasks);
const focusTaskHeroTitle = computed(() => {
  if (!store.focusTask.value?.task_id) {
    return tm.value.queueTitle;
  }
  return tm.value.focusTitle(store.focusTask.value.username);
});

const focusTaskHeroSubtitle = computed(() => {
  if (!store.focusTask.value?.task_id) {
    return tm.value.queueSubtitle;
  }
  return store.state.progress.step || store.focusTask.value.progress_text || tm.value.runningSubtitle;
});

const filteredTasks = computed(() => {
  const normalizedKeyword = String(keyword.value || '').trim().toLowerCase();

  return store.sortedTasks.value.filter((task) => {
    if (statusFilter.value === 'active' && !['running', 'pending', 'paused', 'user_paused'].includes(task.status)) {
      return false;
    }
    if (statusFilter.value === 'completed' && task.status !== 'completed') {
      return false;
    }
    if (statusFilter.value === 'ended' && !['failed', 'cancelled'].includes(task.status)) {
      return false;
    }

    if (!normalizedKeyword) {
      return true;
    }

    return [task.username, task.task_id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalizedKeyword));
  });
});

const filteredTaskGroups = computed(() => {
  const grouped = new Map();

  filteredTasks.value.forEach((task) => {
    const username = task.username || 'unknown';
    const usernameKey = String(username).toLowerCase();
    if (!grouped.has(usernameKey)) {
      grouped.set(usernameKey, {
        username,
        usernameKey,
        tasks: [],
      });
    }
    grouped.get(usernameKey).tasks.push(task);
  });

  return Array.from(grouped.values()).map((group) => ({
    ...group,
    activeCount: group.tasks.filter((task) => ['running', 'pending', 'paused', 'user_paused'].includes(task.status)).length,
    completedCount: group.tasks.filter((task) => task.status === 'completed').length,
  }));
});

const selectedTasks = computed(() => {
  const selectedIdSet = new Set(selectedTaskIds.value);
  return store.sortedTasks.value.filter((task) => selectedIdSet.has(task.task_id));
});

const batchPauseIds = computed(() => selectedTasks.value
  .filter((task) => ['running', 'pending'].includes(task.status))
  .map((task) => task.task_id));

const batchResumeIds = computed(() => selectedTasks.value
  .filter((task) => ['paused', 'user_paused'].includes(task.status))
  .map((task) => task.task_id));

const batchCancelableIds = computed(() => selectedTasks.value
  .filter((task) => ['running', 'pending', 'paused', 'user_paused'].includes(task.status))
  .map((task) => task.task_id));

const batchDeleteIds = computed(() => selectedTasks.value
  .filter((task) => ['completed', 'failed', 'cancelled'].includes(task.status))
  .map((task) => task.task_id));
const failedTasks = computed(() => store.sortedTasks.value
  .filter((task) => ['failed', 'cancelled'].includes(task.status))
  .slice(0, 8));

const batchSelectionSummary = computed(() => {
  if (!selectedTasks.value.length) {
    return tm.value.noneSelected;
  }

  return tm.value.batchSummary(
    batchPauseIds.value.length,
    batchResumeIds.value.length,
    batchCancelableIds.value.length,
    batchDeleteIds.value.length
  );
});

watch(filteredTasks, (tasks) => {
  const visibleIds = new Set(tasks.map((task) => task.task_id));
  selectedTaskIds.value = selectedTaskIds.value.filter((taskId) => visibleIds.has(taskId));
});

watch(filteredTaskGroups, (groups) => {
  const existingKeys = new Set(groups.map((group) => group.usernameKey));
  expandedGroupKeys.value = expandedGroupKeys.value.filter((key) => existingKeys.has(key));
});

function statusLabel(status) {
  const labels = {
    pending: tm.value.pending,
    running: tm.value.running,
    paused: tm.value.paused,
    user_paused: tm.value.userPaused,
    completed: tm.value.completed,
    failed: tm.value.failed,
    cancelled: tm.value.cancelled,
  };
  return labels[status] || status;
}

function tagColor(status) {
  const colorMap = {
    pending: 'gold',
    running: 'green',
    paused: 'orange',
    user_paused: 'orange',
    completed: 'blue',
    failed: 'red',
    cancelled: 'default',
  };
  return colorMap[status] || 'default';
}

function goTaskDetail(taskId) {
  router.push({
    name: 'task-detail',
    params: { taskId },
  });
}

function goNewTask(username = '') {
  const targetUsername = typeof username === 'string' ? username : '';
  router.push({
    name: 'new-task',
    query: targetUsername ? { username: targetUsername } : {},
  });
}

function openFocusTaskDetail() {
  if (!store.focusTask.value?.task_id) {
    return;
  }
  goTaskDetail(store.focusTask.value.task_id);
}

function goLibrary(username) {
  router.push({
    name: 'library',
    query: { username },
  });
}

function goUserFeed(username) {
  const href = router.resolve({
    name: 'user-feed-standalone',
    params: { username },
  }).href;
  window.open(href, '_blank', 'noopener,noreferrer');
}

function toggleTaskSelection(taskId) {
  if (selectedTaskIds.value.includes(taskId)) {
    selectedTaskIds.value = selectedTaskIds.value.filter((value) => value !== taskId);
    return;
  }

  selectedTaskIds.value = [...selectedTaskIds.value, taskId];
}

function isGroupExpanded(usernameKey) {
  return expandedGroupKeys.value.includes(usernameKey);
}

function toggleGroup(usernameKey) {
  if (isGroupExpanded(usernameKey)) {
    expandedGroupKeys.value = expandedGroupKeys.value.filter((key) => key !== usernameKey);
    return;
  }

  expandedGroupKeys.value = [...expandedGroupKeys.value, usernameKey];
}

function visibleGroupTasks(group) {
  if (isGroupExpanded(group.usernameKey) || group.tasks.length <= 2) {
    return group.tasks;
  }

  return group.tasks.slice(0, 2);
}

function selectVisibleTasks() {
  selectedTaskIds.value = filteredTasks.value.map((task) => task.task_id);
}

function clearSelection() {
  selectedTaskIds.value = [];
}

async function runBatchAction(taskIds, action, successMessage) {
  if (!taskIds.length) {
    return;
  }

  const results = await Promise.allSettled(taskIds.map((taskId) => action(taskId)));
  const successCount = results.filter((item) => item.status === 'fulfilled').length;
  const failCount = results.length - successCount;
  selectedTaskIds.value = selectedTaskIds.value.filter((taskId) => !taskIds.includes(taskId));

  if (successCount && !failCount) {
    message.success(tm.value.batchSuccess(successMessage, successCount));
    return;
  }

  if (successCount) {
    message.warning(tm.value.batchPartial(successMessage, successCount, failCount));
    return;
  }

  message.error(tm.value.batchFailed(failCount));
}

function confirmCancel(taskId) {
  Modal.confirm({
    title: tm.value.cancelTaskTitle,
    content: tm.value.cancelTaskContent,
    okText: tm.value.confirmCancel,
    cancelText: tm.value.thinkAgain,
    async onOk() {
      await store.cancelTask(taskId);
      message.success(tm.value.taskCancelled);
    },
  });
}

function confirmDelete(taskId) {
  Modal.confirm({
    title: tm.value.deleteTaskTitle,
    content: tm.value.deleteTaskContent,
    okText: tm.value.confirmDelete,
    cancelText: tm.value.cancel,
    async onOk() {
      await store.deleteTask(taskId);
      message.success(tm.value.taskDeleted);
    },
  });
}

function showActiveOnly() {
  statusFilter.value = 'active';
}

function showEndedOnly() {
  statusFilter.value = 'ended';
}

function filterToFocusUser() {
  keyword.value = store.focusTask.value?.username || '';
}

function openLatestCompleted() {
  const username = store.latestCompletedTask.value?.username;
  if (!username) {
    return;
  }
  goLibrary(username);
}

function resetTaskFilters() {
  statusFilter.value = 'all';
  keyword.value = '';
  collapseAllGroups();
}

function expandAllGroups() {
  expandedGroupKeys.value = filteredTaskGroups.value.map((group) => group.usernameKey);
}

function collapseAllGroups() {
  expandedGroupKeys.value = [];
}

async function batchPauseSelected() {
  await runBatchAction(batchPauseIds.value, (taskId) => store.pauseTask(taskId), tm.value.pauseDone);
}

async function batchResumeSelected() {
  await runBatchAction(batchResumeIds.value, (taskId) => store.resumeTask(taskId), tm.value.resumeDone);
}

async function retryTask(task) {
  if (!task?.task_id || retryingTaskId.value) {
    return;
  }

  retryingTaskId.value = task.task_id;
  try {
    const result = await api.retryAdminTask(task.task_id);
    message.success(result.message || tm.value.taskRequeued);
    await store.loadTasks();
    await store.loadAdminOverview({ force: true, silent: true });
    if (result.task_id) {
      goTaskDetail(result.task_id);
    }
  } catch (error) {
    message.error(error.message || tm.value.retryFailed);
  } finally {
    retryingTaskId.value = '';
  }
}

async function retryAllFailed() {
  if (!failedTasks.value.length || retryingTaskId.value) {
    return;
  }

  retryingTaskId.value = '__all__';
  let successCount = 0;
  let failCount = 0;
  try {
    for (const task of failedTasks.value) {
      try {
        await api.retryAdminTask(task.task_id);
        successCount += 1;
      } catch (error) {
        failCount += 1;
      }
    }
    await store.loadTasks();
    await store.loadAdminOverview({ force: true, silent: true });
    if (failCount) {
      message.warning(tm.value.retryDonePartial(successCount, failCount));
    } else {
      message.success(tm.value.requeuedCount(successCount));
    }
  } finally {
    retryingTaskId.value = '';
  }
}

async function batchCancelSelected() {
  Modal.confirm({
    title: tm.value.batchCancelTitle,
    content: tm.value.batchCancelContent(batchCancelableIds.value.length),
    okText: tm.value.confirmCancel,
    cancelText: tm.value.thinkAgain,
    async onOk() {
      await runBatchAction(batchCancelableIds.value, (taskId) => store.cancelTask(taskId), tm.value.batchCancelDone);
    },
  });
}

async function batchDeleteSelected() {
  Modal.confirm({
    title: tm.value.batchDeleteTitle,
    content: tm.value.batchDeleteContent(batchDeleteIds.value.length),
    okText: tm.value.confirmDelete,
    cancelText: tm.value.cancel,
    async onOk() {
      await runBatchAction(batchDeleteIds.value, (taskId) => store.deleteTask(taskId), tm.value.batchDeleteDone);
    },
  });
}
</script>

<style scoped>
.tasks-hero-card {
  border: 1px solid #d7ebd2;
  background: linear-gradient(135deg, #f6fcf2 0%, #ffffff 58%, #eef8eb 100%);
}

.tasks-hero-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(240px, 0.9fr);
  gap: 20px;
  align-items: center;
}

.tasks-hero-copy h2 {
  margin: 6px 0 10px;
  font-size: 28px;
  line-height: 1.15;
  color: #102310;
}

.tasks-hero-copy p {
  margin: 0 0 16px;
  color: #526153;
}

.tasks-hero-stats {
  display: grid;
  gap: 12px;
}

.tasks-hero-stat {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #deeadb;
}

.tasks-hero-stat span {
  display: block;
  font-size: 12px;
  color: #5f6b63;
}

.tasks-hero-stat strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  color: #112212;
}

.tasks-repair-card {
  border: 1px solid #f0d6d6;
  background: linear-gradient(135deg, #fff8f8 0%, #ffffff 64%, #f8fbf8 100%);
}

.tasks-repair-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.tasks-repair-copy {
  display: grid;
  gap: 4px;
}

.tasks-repair-copy strong {
  color: #2a1414;
}

.tasks-repair-copy span {
  color: #6f625f;
}

.tasks-repair-list {
  display: grid;
  gap: 10px;
}

.tasks-repair-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px;
  border: 1px solid #eadada;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
}

.tasks-repair-row-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.tasks-repair-row-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tasks-repair-row-title strong {
  color: #111111;
}

.tasks-repair-row-message {
  max-width: 680px;
  overflow: hidden;
  color: #6a6762;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 960px) {
  .tasks-hero-shell {
    grid-template-columns: 1fr;
  }

  .tasks-repair-head,
  .tasks-repair-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .tasks-repair-row-message {
    max-width: 100%;
    white-space: normal;
  }
}
</style>
