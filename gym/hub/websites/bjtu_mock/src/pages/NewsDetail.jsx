import React, { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import Breadcrumb from '../components/Breadcrumb';
import FavStar from '../components/FavStar';
import AttachmentBox from '../components/AttachmentBox';
import NotFound from './NotFound';

export default function NewsDetail() {
  const { id } = useParams();
  const { state, isFavorited } = useApp();
  const item = state.news.find((n) => n.id === id);
  const [viewBump] = useState(1);

  const related = useMemo(
    () => (item ? state.news.filter((n) => n.category === item.category && n.id !== item.id).slice(0, 5) : []),
    [state.news, item],
  );

  if (!item) return <NotFound />;

  const list = [...state.news].sort((a, b) => (a.date < b.date ? 1 : -1));
  const idx = list.findIndex((n) => n.id === item.id);
  const sameCat = list.filter((n) => n.category === item.category);
  const catIdx = sameCat.findIndex((n) => n.id === item.id);
  const prev = sameCat[catIdx + 1];
  const next = sameCat[catIdx - 1];

  return (
    <div className="detail-page">
      <Breadcrumb items={[{ label: '新闻网', to: '/news' }, { label: item.category, to: `/news?category=${encodeURIComponent(item.category)}` }, { label: '正文' }]} />
      <div className="wrap article-wrap">
        <h1 className="article-title">{item.title}</h1>
        <div className="article-meta">
          时间：{item.date}　来源：{item.source}　浏览量：{item.views + viewBump}
        </div>
        <div className="article-body">
          {item.body.map((p, i) => <p key={i}>{p}</p>)}
        </div>
        {item.attachments && item.attachments.length > 0 && (
          <AttachmentBox parentId={item.id} attachments={item.attachments} />
        )}
        <div className="article-actions">
          <FavStar type="news" id={item.id} title={item.title} className="fav-button" />
          <span className="fav-button-label">{isFavorited('news', item.id) ? '已收藏' : '收藏'}</span>
        </div>
        <div className="pn-row">
          <span>上一篇：{prev ? <Link to={`/news/${prev.id}`}>{prev.title}</Link> : <span className="pn-none">没有了</span>}</span>
          <span>下一篇：{next ? <Link to={`/news/${next.id}`}>{next.title}</Link> : <span className="pn-none">没有了</span>}</span>
        </div>
        <div className="related-block">
          <h3>相关新闻</h3>
          <ul className="plain-list">
            {related.map((n) => (
              <li key={n.id}>
                <Link to={`/news/${n.id}`}>{n.title}</Link>
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
