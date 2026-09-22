import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildSidUrl } from '../utils/sidParams';

export default function SearchOverlay({ onClose }) {
  const [q, setQ] = useState('');
  const [scope, setScope] = useState('全部');
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    inputRef.current && inputRef.current.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const submit = (e) => {
    e.preventDefault();
    const keyword = q.trim();
    if (!keyword) return;
    navigate(buildSidUrl('/search', { q: keyword, scope }));
    onClose();
  };

  return (
    <div className="overlay-mask" onClick={onClose} role="dialog" aria-modal="true" aria-label="站内搜索">
      <div className="search-overlay" onClick={(e) => e.stopPropagation()}>
        <form className="search-overlay-form" onSubmit={submit}>
          <input
            ref={inputRef}
            className="search-overlay-input"
            type="text"
            value={q}
            placeholder="请输入搜索关键词，如：校庆、招生、参观"
            onChange={(e) => setQ(e.target.value)}
          />
          <button type="submit" className="btn-primary">搜索</button>
        </form>
        <div className="search-overlay-scopes">
          {['全部', '新闻', '通知'].map((s) => (
            <label key={s} className="scope-radio">
              <input type="radio" name="scope" checked={scope === s} onChange={() => setScope(s)} />
              <span>{s}</span>
            </label>
          ))}
        </div>
        <div className="search-overlay-hots">
          <span className="muted">热门词：</span>
          {['校庆', '招生', '参观', '论坛'].map((k) => (
            <button key={k} type="button" className="hot-chip" onClick={() => { setQ(k); }}>{k}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
