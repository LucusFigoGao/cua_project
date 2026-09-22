import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useSidSearchParams } from '../utils/sidParams';
import Breadcrumb from '../components/Breadcrumb';

const HOT = ['校庆', '招生', '参观', '论坛'];

function Highlight({ text, keyword }) {
  if (!keyword) return <>{text}</>;
  const parts = String(text).split(keyword);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((p, i) => (
        <React.Fragment key={i}>
          {p}
          {i < parts.length - 1 && <mark>{keyword}</mark>}
        </React.Fragment>
      ))}
    </>
  );
}

export default function SearchPage() {
  const { state, logSearch } = useApp();
  const [searchParams, setSearchParams] = useSidSearchParams();
  const q = searchParams.get('q') || '';
  const scope = searchParams.get('scope') || '全部';
  const [input, setInput] = useState(q);

  useEffect(() => { setInput(q); }, [q]);

  const results = useMemo(() => {
    if (!q) return { news: [], notices: [] };
    const kw = q.toLowerCase();
    const match = (item) =>
      [item.title, item.summary || '', ...(item.body || [])].join('\n').toLowerCase().includes(kw);
    return {
      news: scope === '通知' ? [] : state.news.filter(match),
      notices: scope === '新闻' ? [] : state.notices.filter(match),
    };
  }, [q, scope, state.news, state.notices]);

  const total = results.news.length + results.notices.length;

  useEffect(() => {
    if (q) logSearch(q, scope, total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, scope]);

  const run = (keyword, nextScope = scope) => {
    const kw = keyword.trim();
    if (!kw) return;
    setSearchParams({ q: kw, scope: nextScope });
  };

  const grouped = [
    ...results.news.map((n) => ({ type: '新闻', item: n, to: `/news/${n.id}` })),
    ...results.notices.map((n) => ({ type: '通知', item: n, to: `/notices/${n.id}` })),
  ].sort((a, b) => (a.item.date < b.item.date ? 1 : -1));

  return (
    <div className="search-page">
      <Breadcrumb items={[{ label: '站内搜索' }]} />
      <div className="wrap search-wrap">
        <div className="sec-title list-title">
          <h2>站内搜索<span className="sec-en">SEARCH</span></h2>
        </div>
        <form
          className="search-bar"
          onSubmit={(e) => { e.preventDefault(); run(input); }}
        >
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="请输入关键词，如：校庆、招生、参观、论坛" />
          <button type="submit" className="btn-primary">搜索</button>
        </form>
        <div className="cat-tabs">
          {['全部', '新闻', '通知'].map((s) => (
            <button type="button" key={s} className={`cat-tab ${scope === s ? 'active' : ''}`} onClick={() => (q ? run(q, s) : setSearchParams({ scope: s }))}>
              {s}
            </button>
          ))}
        </div>

        {!q ? (
          <div className="search-empty">
            <div className="chip-row">
              <span className="muted">最近搜索：</span>
              {state.searchHistory.length === 0 && <span className="muted">暂无搜索记录</span>}
              {state.searchHistory.map((h) => (
                <button key={h.id} type="button" className="hot-chip" onClick={() => run(h.keyword, h.scope)}>{h.keyword}</button>
              ))}
            </div>
            <div className="chip-row">
              <span className="muted">热门搜索：</span>
              {HOT.map((k) => (
                <button key={k} type="button" className="hot-chip gold" onClick={() => run(k)}>{k}</button>
              ))}
            </div>
          </div>
        ) : total === 0 ? (
          <div className="empty-state">
            <p>未找到与“{q}”相关的内容</p>
            <div className="suggest-list">
              <span className="muted">建议尝试：</span>
              {HOT.map((k) => (
                <button key={k} type="button" className="hot-chip" onClick={() => run(k)}>{k}</button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <p className="search-count">为您找到 <strong>{total}</strong> 条相关内容</p>
            <ul className="search-results">
              {grouped.map(({ type, item, to }) => (
                <li className="search-result" key={item.id}>
                  <span className={`type-chip ${type === '新闻' ? 'blue' : 'gold'}`}>{type}</span>
                  <Link className="result-title" to={to}>
                    <Highlight text={item.title} keyword={q} />
                  </Link>
                  <p className="result-summary"><Highlight text={item.summary || (item.body || [])[0] || ''} keyword={q} /></p>
                  <div className="result-meta">
                    <span>{item.date}</span>
                    <span>{type === '新闻' ? item.category : item.category}</span>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
