import React from 'react';
import { useApp } from '../context/AppContext';

export default function FavStar({ type, id, title, className = '' }) {
  const { isFavorited, toggleFavorite, showToast } = useApp();
  const active = isFavorited(type, id);
  return (
    <button
      type="button"
      className={`fav-star ${active ? 'active' : ''} ${className}`}
      title={active ? '已收藏' : '收藏'}
      aria-label={active ? '取消收藏' : '收藏'}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const added = toggleFavorite(type, id, title);
        showToast(added ? '已收藏' : '已取消收藏', added ? 'success' : 'info');
      }}
    >
      {active ? '★' : '☆'}
    </button>
  );
}
