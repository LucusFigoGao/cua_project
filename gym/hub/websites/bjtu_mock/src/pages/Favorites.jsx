import React from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import Breadcrumb from '../components/Breadcrumb';

export default function Favorites() {
  const { state, removeFavorite, showToast } = useApp();
  const newsFavs = state.favorites.filter((f) => f.targetType === 'news');
  const noticeFavs = state.favorites.filter((f) => f.targetType === 'notice');

  const Section = ({ title, count, list, type, emptyTo, emptyLabel }) => (
    <div className="fav-section">
      <div className="sec-title">
        <h2>{title}<span className="sec-en">{count} 条收藏</span></h2>
      </div>
      {list.length === 0 ? (
        <div className="empty-state inline">
          <p>暂无{title}</p>
          <Link className="btn-ghost" to={emptyTo}>{emptyLabel}</Link>
        </div>
      ) : (
        <ul className="fav-list">
          {list.map((f) => (
            <li className="fav-row" key={f.id}>
              <Link className="row-title" to={`/${type === 'news' ? 'news' : 'notices'}/${f.targetId}`}>{f.title}</Link>
              <span className="row-date">{f.createdAt.slice(0, 16).replace('T', ' ')}</span>
              <Link className="btn-ghost sm" to={`/${type === 'news' ? 'news' : 'notices'}/${f.targetId}`}>查看</Link>
              <button
                type="button"
                className="btn-danger-ghost sm"
                onClick={() => { removeFavorite(f.targetType, f.targetId); showToast('已取消收藏', 'info'); }}
              >
                取消收藏
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div className="fav-page">
      <Breadcrumb items={[{ label: '我的收藏' }]} />
      <div className="wrap fav-wrap">
        <div className="sec-title list-title">
          <h2>我的收藏<span className="sec-en">FAVORITES</span></h2>
        </div>
        <Section title="新闻收藏" count={newsFavs.length} list={newsFavs} type="news" emptyTo="/news" emptyLabel="去逛逛" />
        <Section title="通知收藏" count={noticeFavs.length} list={noticeFavs} type="notice" emptyTo="/notices" emptyLabel="去逛逛" />
      </div>
    </div>
  );
}
