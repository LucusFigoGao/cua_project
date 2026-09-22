// dataManager.js — state init, session-scoped localStorage, server sync

import { createInitialData } from '../data/seed';

const BASE_KEY = 'bjtu_mock_state';
const BASE_INITIAL_KEY = 'bjtu_mock_initial_state';

export const getSessionId = () => {
  const params = new URLSearchParams(window.location.search);
  const sid = params.get('sid');
  if (sid) {
    sessionStorage.setItem('bjtu_mock_sid', sid);
    return sid;
  }
  return sessionStorage.getItem('bjtu_mock_sid') || null;
};

export const storageKey = (sid) => (sid ? `${BASE_KEY}_${sid}` : BASE_KEY);
export const initialKey = (sid) => (sid ? `${BASE_INITIAL_KEY}_${sid}` : BASE_INITIAL_KEY);

export const fetchCustomState = async (sid) => {
  if (!sid) return null;
  try {
    const res = await fetch(`/state?sid=${encodeURIComponent(sid)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data && Object.keys(data).length > 0 ? data : null;
  } catch {
    return null;
  }
};

export function deepMerge(base, override) {
  if (!override) return base;
  const result = { ...base };
  for (const key of Object.keys(override)) {
    if (override[key] === null || override[key] === undefined) continue;
    if (Array.isArray(override[key])) {
      result[key] = override[key];
    } else if (
      typeof override[key] === 'object' &&
      typeof base[key] === 'object' &&
      base[key] !== null &&
      !Array.isArray(base[key])
    ) {
      result[key] = deepMerge(base[key], override[key]);
    } else {
      result[key] = override[key];
    }
  }
  return result;
}

export { createInitialData };

export function loadState(sid = null) {
  try {
    const raw = localStorage.getItem(storageKey(sid));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveState(state, sid = null) {
  try {
    localStorage.setItem(storageKey(sid), JSON.stringify(state));
  } catch (e) {
    console.warn('saveState localStorage failed:', e);
  }
  const effectiveSid = sid || 'default';
  fetch(`/post?sid=${encodeURIComponent(effectiveSid)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'set_current', state }),
  }).catch(() => {});
}

export function initializeData(sid = null, customState = null) {
  const defaultData = createInitialData();
  const hasServerState = !!(customState && Object.keys(customState).length > 0);
  const merged = hasServerState ? deepMerge(defaultData, customState) : defaultData;

  const stateKey = storageKey(sid);
  const initKey = initialKey(sid);

  const isFirstLoad = !localStorage.getItem(initKey);
  if (isFirstLoad) {
    localStorage.setItem(initKey, JSON.stringify(merged));
    // POST the baseline ONLY when the server has no state for this sid.
    // If the server already holds state (e.g. harness-injected via set + set_current),
    // adopt it as both current and initial — re-POSTing `set` would clobber the
    // server's initial_state with the already-mutated current and wipe state_diff.
    if (!hasServerState) {
      const effectiveSid = sid || 'default';
      fetch(`/post?sid=${encodeURIComponent(effectiveSid)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set', state: merged }),
      }).catch(() => {});
    }
  }

  const existing = loadState(sid);
  if (existing) return existing;

  localStorage.setItem(stateKey, JSON.stringify(merged));
  return merged;
}
