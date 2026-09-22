import React, { useEffect, useState } from 'react';
import { getSessionId } from '../utils/dataManager';
import { computeDiff } from '../utils/stateTracker';

const TRACKED_KEYS = [
  'bookings（校园参观预约）',
  'inquiries（招生咨询/意见）',
  'favorites（收藏）',
  'downloads（附件下载记录）',
  'searchHistory（站内搜索记录）',
  'noticeFilters（通知公告筛选）',
  'feedback（意见箱留言）',
];

export default function Go() {
  const [payload, setPayload] = useState(null);
  const [copied, setCopied] = useState(false);
  const sid = getSessionId() || 'default';

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`/go?sid=${encodeURIComponent(sid)}`);
        const data = await res.json();
        if (alive) setPayload(data);
      } catch {
        if (alive) setPayload({ initial_state: null, current_state: null, state_diff: {} });
      }
    };
    load();
    const timer = setInterval(load, 3000);
    return () => { alive = false; clearInterval(timer); };
  }, [sid]);

  const text = payload ? JSON.stringify(payload, null, 2) : '加载中...';

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const diffKeys = payload && payload.state_diff ? Object.keys(payload.state_diff) : [];

  return (
    <div className="go-page">
      <div className="go-bar">
        <span className="go-title">状态检查器 /go</span>
        <span className="go-sid">sid：{sid}</span>
        <span className="go-diff">state_diff 键：{diffKeys.length ? diffKeys.join('、') : '（无变更）'}</span>
        <button type="button" className="btn-primary go-copy" onClick={copy}>
          {copied ? '已复制' : '复制 JSON'}
        </button>
      </div>
      <div className="go-keys">
        <span>跟踪字段：</span>
        {TRACKED_KEYS.map((k) => <span key={k} className="go-key-chip">{k}</span>)}
      </div>
      <pre className="go-pre">{text}</pre>
    </div>
  );
}
