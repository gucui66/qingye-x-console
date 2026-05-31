import { toTimestamp } from './formatters';

export const taskDisplayPriority = {
  running: 6,
  pending: 5,
  paused: 4,
  user_paused: 3,
  completed: 2,
  failed: 1,
  cancelled: 0,
};

const STATUS_META = {
  pending: { color: '#d39b3f', text: '等待中' },
  running: { color: 'var(--primary-color)', text: '运行中' },
  paused: { color: '#d39b3f', text: '已暂停' },
  user_paused: { color: '#d39b3f', text: '手动暂停' },
  completed: { color: 'var(--success-color)', text: '已完成' },
  failed: { color: 'var(--error-color)', text: '失败' },
  cancelled: { color: 'var(--secondary-color)', text: '已取消' },
};

export function getTaskStatusMeta(status) {
  return STATUS_META[status] || { color: '#657786', text: status || '未知' };
}

export function sortTasks(tasks = []) {
  return [...tasks].sort((left, right) => toTimestamp(right?.created_at) - toTimestamp(left?.created_at));
}

export function groupTasksForDisplay(tasks = []) {
  const grouped = new Map();
  const activeStatuses = ['running', 'pending', 'paused', 'user_paused'];

  tasks.forEach((task) => {
    const usernameKey = String(task?.username || '').toLowerCase();
    if (!grouped.has(usernameKey)) {
      grouped.set(usernameKey, []);
    }
    grouped.get(usernameKey).push(task);
  });

  return Array.from(grouped.values())
    .map((group) => {
      const sortedByTime = [...group].sort(
        (left, right) => toTimestamp(right?.created_at) - toTimestamp(left?.created_at)
      );

      const activeGroup = sortedByTime
        .filter((task) => activeStatuses.includes(task?.status))
        .sort((left, right) => {
          const priorityDiff =
            (taskDisplayPriority[right?.status] || 0) -
            (taskDisplayPriority[left?.status] || 0);

          if (priorityDiff !== 0) {
            return priorityDiff;
          }

          return toTimestamp(right?.created_at) - toTimestamp(left?.created_at);
        });

      return {
        ...(activeGroup[0] || sortedByTime[0]),
        hidden_history_count: Math.max(0, group.length - 1),
      };
    })
    .sort((left, right) => toTimestamp(right?.created_at) - toTimestamp(left?.created_at));
}

export function pickFocusTask(tasks = []) {
  return (
    tasks.find((task) => ['running', 'pending', 'paused', 'user_paused'].includes(task?.status)) ||
    tasks.find((task) => task?.status === 'completed') ||
    tasks[0] ||
    null
  );
}

export function shouldShowTaskScreenshot(task) {
  return (
    task?.options?.scrape_method === 'selenium' &&
    ['pending', 'running', 'paused', 'user_paused'].includes(task?.status)
  );
}
