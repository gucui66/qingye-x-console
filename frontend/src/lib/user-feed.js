import { encodeOutputPath, toTimestamp } from './formatters';

export const USER_FEED_LIMIT = 1000;

function normalizeVideoAnnotations(annotations = {}) {
  return {
    favorite: Boolean(annotations.favorite),
    watched: Boolean(annotations.watched),
    watch_later: Boolean(annotations.watch_later),
    tags: Array.isArray(annotations.tags) ? annotations.tags : [],
    note: typeof annotations.note === 'string' ? annotations.note : '',
    last_position: Number(annotations.last_position || 0) || 0,
    play_count: Number(annotations.play_count || 0) || 0,
    last_played_at: annotations.last_played_at || null,
    annotation_updated_at: annotations.annotation_updated_at || null,
  };
}

function buildVideoThumbnailSrc(video = {}, fallback = {}) {
  if (video.thumbnail_path) {
    return encodeOutputPath(video.thumbnail_path);
  }
  return video.thumbnail_url || fallback.thumbnail_url || fallback.preview_image_url || '';
}

function normalizeMediaIndex(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function hashRouteValue(value = '') {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash) + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

export function buildFeedVideoRouteKey(video = {}, fallbackIndex = 0) {
  const mediaIndex = normalizeMediaIndex(video?.media_index);
  if (mediaIndex !== null) {
    return `m${mediaIndex}`;
  }

  const mediaId = String(video?.id || '').trim();
  if (mediaId) {
    return `d${mediaId}`;
  }

  const path = String(video?.path || '').trim();
  if (path) {
    return `p${hashRouteValue(path)}`;
  }

  return `i${fallbackIndex}`;
}

export function resolveFeedVideoRouteKey(item = {}, videoIndex = 0) {
  const video = item?.local_videos?.[videoIndex];
  return buildFeedVideoRouteKey(video, videoIndex);
}

export function buildFeedPhotos(item) {
  const localPhotos = (item?.local_photos || []).map((photo) => ({
    key: photo.path,
    src: encodeOutputPath(photo.path),
    alt: photo.name || item?.id || 'photo',
  }));

  if (localPhotos.length) {
    return localPhotos;
  }

  return (item?.remote_photos || []).map((photo, index) => ({
    key: photo.url || `${item?.id || 'tweet'}:remote:${index}`,
    src: photo.url,
    alt: item?.id || 'photo',
  }));
}

export function countFeedMedia(item) {
  return Math.max(item?.local_videos?.length || 0, item?.remote_videos?.length || 0) + buildFeedPhotos(item).length;
}

export function buildFeedPreviewText(item, fallback = '媒体贴文') {
  const text = String(item?.content || '').trim();
  if (text) {
    return text;
  }

  const mediaCount = countFeedMedia(item);
  return mediaCount ? `${fallback} · ${mediaCount} 个资源` : fallback;
}

export function decorateFeedItem(item) {
  const photos = buildFeedPhotos(item);
  const remoteVideos = item?.remote_videos || [];
  const localVideos = (item?.local_videos || []).map((video, index) => {
    const mediaIndex = normalizeMediaIndex(video?.media_index);
    const remoteFallback = remoteVideos.find((remoteVideo) => (
      normalizeMediaIndex(remoteVideo?.media_index) === (mediaIndex ?? index)
    )) || remoteVideos[index] || {};
    return {
      ...video,
      media_index: mediaIndex ?? index,
      route_key: buildFeedVideoRouteKey(video, index),
      thumbnail_src: buildVideoThumbnailSrc(video, remoteFallback),
      annotations: normalizeVideoAnnotations(video?.annotations || {}),
    };
  });
  const hasLocalVideos = localVideos.length > 0;
  const hasRemoteVideos = Boolean(item?.remote_videos?.length);
  const hasVideos = hasLocalVideos || hasRemoteVideos;
  const hasPhotos = photos.length > 0;
  const hasText = Boolean(String(item?.content || '').trim());
  const mediaCount = Math.max(localVideos.length, item?.remote_videos?.length || 0) + photos.length;

  return {
    ...item,
    author_avatar_src: item?.author_avatar_url || '',
    photos,
    local_videos: localVideos,
    hasLocalVideos,
    hasRemoteVideos,
    hasVideos,
    hasPhotos,
    hasText,
    mediaCount,
    previewText: buildFeedPreviewText(item),
    publishTimestamp: toTimestamp(item?.publish_time || item?.date),
    crawledTimestamp: toTimestamp(item?.crawled_at),
    sortTimestamp: toTimestamp(item?.publish_time || item?.date || item?.crawled_at),
  };
}

export function prepareFeedPayload(payload = {}) {
  const items = (payload?.items || []).map((item) => decorateFeedItem(item));
  const summary = {
    tweets: payload?.summary?.tweets ?? items.length,
    videos: payload?.summary?.videos ?? items.reduce((total, item) => total + Math.max(item.local_videos.length, item.remote_videos?.length || 0), 0),
    photos: payload?.summary?.photos ?? items.reduce((total, item) => total + item.photos.length, 0),
  };

  return {
    ...payload,
    items,
    summary,
  };
}

export function buildFeedVideoEntries(items = []) {
  const rows = [];
  for (const item of items) {
    (item?.local_videos || []).forEach((video, index) => {
      rows.push({
        key: `${item.id}:${video.route_key || buildFeedVideoRouteKey(video, index)}`,
        tweetId: String(item.id),
        videoIndex: video.route_key || buildFeedVideoRouteKey(video, index),
        numericVideoIndex: index,
        item,
        video,
      });
    });
  }
  return rows;
}

export function findFeedVideoEntryIndex(entries = [], tweetId, routeToken = '') {
  const normalizedTweetId = String(tweetId || '').trim();
  if (!normalizedTweetId) {
    return -1;
  }

  const normalizedToken = String(routeToken || '').trim();
  const tweetEntries = entries.filter((entry) => entry.tweetId === normalizedTweetId);
  if (!tweetEntries.length) {
    return -1;
  }

  if (!normalizedToken) {
    return entries.findIndex((entry) => entry.key === tweetEntries[0].key);
  }

  const exactMatchIndex = entries.findIndex((entry) => (
    entry.tweetId === normalizedTweetId
      && String(entry.videoIndex || '').trim() === normalizedToken
  ));
  if (exactMatchIndex >= 0) {
    return exactMatchIndex;
  }

  if (!/^\d+$/.test(normalizedToken)) {
    return -1;
  }

  const legacyIndex = Number.parseInt(normalizedToken, 10);
  const mediaIndexMatch = entries.findIndex((entry) => (
    entry.tweetId === normalizedTweetId
      && normalizeMediaIndex(entry.video?.media_index) === legacyIndex
  ));
  if (mediaIndexMatch >= 0) {
    return mediaIndexMatch;
  }

  return entries.findIndex((entry) => (
    entry.tweetId === normalizedTweetId
      && entry.numericVideoIndex === legacyIndex
  ));
}
