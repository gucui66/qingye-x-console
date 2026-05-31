export const DEFAULT_PLAYER_PREFS = {
  muted: false,
  theater: false,
  autoplayNext: true,
  playbackRate: 1,
};

const PLAYER_PREFS_KEY = 'x-feed-video-player-prefs';
const VALID_RATES = [0.75, 1, 1.25, 1.5, 2];

export function normalizePlaybackRate(value) {
  const numeric = Number(value || 1);
  if (!Number.isFinite(numeric)) {
    return 1;
  }

  if (VALID_RATES.includes(numeric)) {
    return numeric;
  }

  return 1;
}

export function readPlayerPrefs() {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_PLAYER_PREFS };
  }

  try {
    const raw = window.localStorage.getItem(PLAYER_PREFS_KEY);
    if (!raw) {
      return { ...DEFAULT_PLAYER_PREFS };
    }

    const parsed = JSON.parse(raw);
    return {
      muted: Boolean(parsed?.muted),
      theater: Boolean(parsed?.theater),
      autoplayNext: parsed?.autoplayNext !== false,
      playbackRate: normalizePlaybackRate(parsed?.playbackRate),
    };
  } catch (error) {
    return { ...DEFAULT_PLAYER_PREFS };
  }
}

export function writePlayerPrefs(prefs = {}) {
  if (typeof window === 'undefined') {
    return;
  }

  const payload = {
    muted: Boolean(prefs?.muted),
    theater: Boolean(prefs?.theater),
    autoplayNext: prefs?.autoplayNext !== false,
    playbackRate: normalizePlaybackRate(prefs?.playbackRate),
  };

  try {
    window.localStorage.setItem(PLAYER_PREFS_KEY, JSON.stringify(payload));
  } catch (error) {
    // ignore local persistence errors
  }
}

export function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds || 0) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function isEditableTarget(target) {
  if (!target || typeof target !== 'object') {
    return false;
  }

  const tagName = String(target.tagName || '').toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || Boolean(target.isContentEditable);
}
