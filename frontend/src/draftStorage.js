const DRAFT_KEY = 'complaint:draft:v4';

function canUseSessionStorage() {
  return typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined';
}

export function readDraft() {
  if (!canUseSessionStorage()) return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) || '{}');
  } catch {
    return {};
  }
}

export function writeDraft(patch) {
  if (!canUseSessionStorage()) return {};
  const next = { ...readDraft(), ...patch, updatedAt: Date.now() };
  window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(next));
  return next;
}

export function clearDraft() {
  if (!canUseSessionStorage()) return;
  window.sessionStorage.removeItem(DRAFT_KEY);
}

export function readCachedResult(name, cacheKey) {
  const cache = readDraft()[name];
  if (!cache || cache.cacheKey !== cacheKey) return null;
  return cache.data || null;
}

export function writeCachedResult(name, cacheKey, data) {
  writeDraft({ [name]: { cacheKey, data } });
}
