export function extractUsernameFromUrl(url) {
  try {
    const value = String(url || '').trim();
    const patterns = [
      /twitter\.com\/([^/?#]+)/i,
      /x\.com\/([^/?#]+)/i,
    ];

    for (const pattern of patterns) {
      const match = value.match(pattern);
      if (match) {
        return match[1].replace(/^@+/, '');
      }
    }
  } catch (error) {
    console.error('URL 解析失败:', error);
  }

  return null;
}

export function formatFileSize(bytes) {
  const size = Number(bytes || 0);
  if (!Number.isFinite(size) || size <= 0) {
    return '0 B';
  }

  const unitStep = 1024;
  const units = ['B', 'KB', 'MB', 'GB'];
  const unitIndex = Math.min(
    Math.floor(Math.log(size) / Math.log(unitStep)),
    units.length - 1
  );

  return `${Math.round((size / unitStep ** unitIndex) * 100) / 100} ${units[unitIndex]}`;
}

export function encodeOutputPath(path) {
  const value = String(path || '').replace(/^\/+/, '');
  const encoded = value
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/');

  return `/output/${encoded}`;
}

export function buildThumbnailSrc(item = {}) {
  if (item.thumbnail_path) {
    return encodeOutputPath(item.thumbnail_path);
  }
  return item.thumbnail_url || '';
}

export function buildDocumentViewUrl(path) {
  const encoded = String(path || '')
    .replace(/^\/+/, '')
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/');

  return `/view/${encoded}`;
}

export function formatVideoDate(timestamp) {
  if (!timestamp) {
    return '时间未知';
  }

  const rawValue = Number(timestamp);
  const normalized = rawValue > 10 ** 12 ? rawValue : rawValue * 1000;

  try {
    return new Date(normalized).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (error) {
    return '时间未知';
  }
}

export function formatDateTime(value, fallback = '暂无') {
  if (!value) {
    return fallback;
  }

  try {
    return new Date(value).toLocaleString('zh-CN', {
      hour12: false,
    });
  } catch (error) {
    return fallback;
  }
}

export function toTimestamp(value) {
  if (!value) {
    return 0;
  }

  try {
    return new Date(value).getTime();
  } catch (error) {
    return 0;
  }
}
