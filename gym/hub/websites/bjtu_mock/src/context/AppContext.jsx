import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import {
  getSessionId, fetchCustomState, initializeData, saveState, initialKey,
} from '../utils/dataManager';

const AppContext = createContext(null);

const nowIso = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}+08:00`;
};

export function AppProvider({ children }) {
  const sidRef = useRef(getSessionId());
  const initStarted = useRef(false);

  const [state, setState] = useState(() => {
    const sid = sidRef.current;
    const isRefresh = localStorage.getItem(initialKey(sid)) !== null;
    if (isRefresh) return initializeData(sid);
    if (!sid) return initializeData(sid, null);
    return null;
  });

  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    // initStarted guard: under StrictMode the effect is double-invoked; only the
    // first run may perform the GET /state → decide → maybe-POST-set bootstrap,
    // so at most one decision path runs and no baseline POST can slip through.
    if (state !== null || initStarted.current) return;
    initStarted.current = true;
    const sid = sidRef.current;
    fetchCustomState(sid)
      .catch(() => null)
      .then((custom) => initializeData(sid, custom))
      .then((data) => setState(data));
  }, [state]);

  const updateState = useCallback((updater) => {
    setState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater };
      saveState(next, sidRef.current);
      return next;
    });
  }, []);

  const showToast = useCallback((message, type = 'success', duration = 2000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
  }, []);

  const addBooking = useCallback((booking) => {
    const d = new Date();
    const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
    updateState((prev) => {
      const seq = String(prev.bookings.length + 1).padStart(4, '0');
      const record = {
        id: `BK${ymd}${seq}`,
        status: '已预约',
        createdAt: nowIso(),
        ...booking,
      };
      return { ...prev, bookings: [...prev.bookings, record] };
    });
  }, [updateState]);

  const cancelBooking = useCallback((id) => {
    updateState((prev) => ({
      ...prev,
      bookings: prev.bookings.map((b) => (b.id === id ? { ...b, status: '已取消' } : b)),
    }));
  }, [updateState]);

  const addInquiry = useCallback((inquiry) => {
    updateState((prev) => {
      const d = new Date();
      const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
      const record = {
        id: `IN${ymd}${String(prev.inquiries.length + 1).padStart(4, '0')}`,
        submittedAt: nowIso(),
        status: '待回复',
        reply: '',
        ...inquiry,
      };
      const next = { ...prev, inquiries: [record, ...prev.inquiries] };
      if (record.category === '意见建议') {
        next.feedback = [
          { id: `FB${ymd}${String(prev.feedback.length + 1).padStart(4, '0')}`, content: record.message, contact: record.contact, createdAt: record.submittedAt },
          ...prev.feedback,
        ];
      }
      return next;
    });
  }, [updateState]);

  const toggleFavorite = useCallback((targetType, targetId, title) => {
    // Compute next-state deterministically from the current rendered state so the
    // returned flag (used for the toast label) never depends on React eagerly
    // evaluating the updater below. Mirrors isFavorited's source of truth.
    const added = !state.favorites.some(
      (f) => f.targetType === targetType && f.targetId === targetId,
    );
    updateState((prev) => {
      const exists = prev.favorites.find((f) => f.targetType === targetType && f.targetId === targetId);
      if (exists) {
        return { ...prev, favorites: prev.favorites.filter((f) => f.id !== exists.id) };
      }
      const fav = {
        id: `fav_${String(prev.favorites.length + 1).padStart(4, '0')}_${Date.now().toString().slice(-4)}`,
        targetType,
        targetId,
        title,
        createdAt: nowIso(),
      };
      return { ...prev, favorites: [...prev.favorites, fav] };
    });
    return added;
  }, [updateState, state]);

  const removeFavorite = useCallback((targetType, targetId) => {
    updateState((prev) => ({
      ...prev,
      favorites: prev.favorites.filter((f) => !(f.targetType === targetType && f.targetId === targetId)),
    }));
  }, [updateState]);

  const logSearch = useCallback((keyword, scope, resultCount) => {
    updateState((prev) => {
      if (prev.searchHistory[0] && prev.searchHistory[0].keyword === keyword && prev.searchHistory[0].scope === scope) {
        return prev;
      }
      const entry = {
        id: `sh_${Date.now().toString().slice(-6)}`,
        keyword,
        scope,
        resultCount,
        timestamp: nowIso(),
      };
      return { ...prev, searchHistory: [entry, ...prev.searchHistory].slice(0, 8) };
    });
  }, [updateState]);

  const logDownload = useCallback((parentId, att) => {
    updateState((prev) => ({
      ...prev,
      downloads: [
        ...prev.downloads,
        {
          id: `dl_${String(prev.downloads.length + 1).padStart(3, '0')}`,
          noticeId: parentId,
          fileName: att.fileName,
          fileType: att.fileType,
          timestamp: nowIso(),
        },
      ],
    }));
  }, [updateState]);

  const setNoticeFilters = useCallback((filters) => {
    updateState((prev) => ({ ...prev, noticeFilters: { ...prev.noticeFilters, ...filters } }));
  }, [updateState]);

  const addFeedback = useCallback((feedback) => {
    updateState((prev) => ({
      ...prev,
      feedback: [{ id: `FB${Date.now().toString().slice(-6)}`, createdAt: nowIso(), ...feedback }, ...prev.feedback],
    }));
  }, [updateState]);

  const isFavorited = useCallback(
    (targetType, targetId) =>
      !!state && state.favorites.some((f) => f.targetType === targetType && f.targetId === targetId),
    [state],
  );

  if (!state) {
    return (
      <div className="app-loading">加载中...</div>
    );
  }

  return (
    <AppContext.Provider
      value={{
        state, updateState, showToast, sid: sidRef.current,
        addBooking, cancelBooking, addInquiry, toggleFavorite, removeFavorite,
        logSearch, logDownload, setNoticeFilters, addFeedback, isFavorited,
      }}
    >
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>{t.message}</div>
        ))}
      </div>
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
