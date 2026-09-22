import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { NEWS_CATEGORIES } from '../data/seed';
import { useSidSearchParams } from '../utils/sidParams';
import Breadcrumb from '../components/Breadcrumb';
import Pagination from '../components/Pagination';
import FavStar from '../components/FavStar';

const PAGE_SIZE = 10;

export default function NewsList() {
  const { state } = useApp();
  const [searchParams, setSearchParams] = useSidSearchParams();
  const category = searchParams.get('category') || '全部';
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const list = [...state.news].sort((a, b) => (a.date < b.date ? 1 : -1));
    return category === '全部' ? list : list.filter((n) => n.category === category);
  }, [state.news, category]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const rows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const pickCategory = (cat) => {
    setPage(1);
    if (cat === '全部') setSearchParams({});
    else setSearchParams({ category: cat });
  };

  return (
    <div className="list-page">
      <Breadcrumb items={[{ label: '新闻网' }]} />
      <div className="wrap list-wrap">
        <div className="sec-title list-title">
          <h2>新闻网<span className="sec-en">NEWS</span></h2>
          <span className="list-count">共 {filtered.length} 条</span>
        </div>
        <div className="cat-tabs">
          {['全部', ...NEWS_CATEGORIES].map((c) => (
            <button
              type="button"
              key={c}
              className={`cat-tab ${category === c ? 'active' : ''}`}
              onClick={() => pickCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
        {rows.length === 0 ? (
          <div className="empty-state">
            <p>暂无相关新闻</p>
            <Link className="btn-ghost" to="/news">返回新闻首页</Link>
          </div>
        ) : (
          <ul className="list-rows">
            {rows.map((n) => (
              <li className="list-row" key={n.id}>
                <span className="bullet">▪</span>
                <Link className="row-title" to={`/news/${n.id}`}>
                  {n.isTop && <em className="top-tag">头条</em>}
                  {n.title}
                </Link>
                <FavStar type="news" id={n.id} title={n.title} className="row-star" />
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
        )}
        <Pagination page={safePage} pageCount={pageCount} total={filtered.length} pageSize={PAGE_SIZE} onChange={setPage} />
      </div>
    </div>
  );
}
