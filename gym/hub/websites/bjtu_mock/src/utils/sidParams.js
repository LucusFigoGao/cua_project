// sidParams.js — helpers that keep ?sid= on the URL across client-side navigation.
import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getSessionId } from './dataManager';

const collect = (target, updates) => {
  for (const [key, value] of Object.entries(updates || {})) {
    if (value === null || value === undefined) continue;
    target.set(key, value);
  }
};

// Drop-in replacement for useSearchParams: the setter rebuilds the query from
// `updates` while preserving the current ?sid= (falling back to the session sid).
export function useSidSearchParams() {
  const [searchParams, setSearchParams] = useSearchParams();
  const setSidSearchParams = useCallback(
    (updates, opts) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams();
        collect(next, updates);
        const sid = prev.get('sid') || getSessionId();
        if (sid) next.set('sid', sid);
        return next;
      }, opts);
    },
    [setSearchParams],
  );
  return [searchParams, setSidSearchParams];
}

// Builds `${path}?query` that always carries the session sid (for navigate() calls).
export function buildSidUrl(path, updates = {}) {
  const sp = new URLSearchParams();
  collect(sp, updates);
  const sid = getSessionId();
  if (sid) sp.set('sid', sid);
  const qs = sp.toString();
  return qs ? `${path}?${qs}` : path;
}
