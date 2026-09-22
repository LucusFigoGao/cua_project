import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { NOTICE_CATEGORIES } from '../data/seed';
import { useSidSearchParams } from '../utils/sidParams';
import Breadcrumb from '../components/Breadcrumb';
import Pagination from '../components/Pagination';
import FavStar from '../components/FavStar';

const PAGE_SIZE = 10;
const BASELINE = { category: '全部', dateFrom: '', dateTo: '' };

export default function NoticeList() {
  const { state, setNoticeFilters } = useApp();
  const [searchParams, setSearchParams] = useSidSearchParams();

  // ?category= from footer / quick links / dropdowns is view-local only:
  // noticeFilters is persisted to server state exclusively by explicit user
  // filter actions (查询 / 重置 / pill clicks), never by pure navigation.
  const urlCat = searchParams.get('category');
  const storedFilters = state.noticeFilters || BASELINE;
  const filters = useMemo(
    () => (urlCat ? { ...storedFilters, category: urlCat } : storedFilters),
    [urlCat, storedFilters],
  );

  const [draftCat, setDraftCat] = useState(filters.category);
  const [draftFrom, setDraftFrom] = useState(filters.dateFrom);
  const [draftTo, setDraftTo] = useState(filters.dateTo);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setDraftCat(filters.category);
    setDraftFrom(filters.dateFrom);
    setDraftTo(filters.dateTo);
  }, [filters.category, filters.dateFrom, filters.dateTo]);

  useEffect(() => {
    setPage(1);
  }, [urlCat]);

  const filtered = useMemo(() => {
    const list = [...state.notices].sort((a, b) => (a.date < b.date ? 1 : -1));
    return list.filter((n) => {
      if (filters.category !== '全部' && n.category !== filters.category) return false;
      if (filters.dateFrom && n.date < filters.dateFrom) return false;
      if (filters.dateTo && n.date > filters.dateTo) return false;
      return true;
    });
  }, [state.notices, filters]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const rows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const apply = () => {
    setNoticeFilters({ category: draftCat, dateFrom: draftFrom, dateTo: draftTo });
    setPage(1);
    setSearchParams({});
  };

  const reset = () => {
    setNoticeFilters({ ...BASELINE });
    setDraftCat(BASELINE.category);
    setDraftFrom('');
    setDraftTo('');
    setPage(1);
    setSearchParams({});
  };

  const pickCat = (cat) => {
    setDraftCat(cat);
    setNoticeFilters({ category: cat });
    setPage(1);
    setSearchParams({});
  };

  return (
    <div className="list-page">
      <Breadcrumb items={[{ label: '通知公告' }]} />
      <div className="wrap list-wrap">
        <div className="sec-title list-title">
          <h2>通知公告<span className="sec-en">NOTICE</span></h2>
          <span className="list-count">共 {filtered.length} 条</span>
        </div>

        <div className="filter-bar">
          <div className="filter-pills">
            {['全部', ...NOTICE_CATEGORIES].map((c) => (
              <button type="button" key={c} className={`filter-pill ${filters.category === c ? 'active' : ''}`} onClick={() => pickCat(c)}>
                {c}
              </button>
            ))}
          </div>
          <div className="filter-dates">
            <label>日期起<input type="date" value={draftFrom} max="2026-12-31" onChange={(e) => setDraftFrom(e.target.value)} /></label>
            <label>日期止<input type="date" value={draftTo} max="2026-12-31" onChange={(e) => setDraftTo(e.target.value)} /></label>
            <button type="button" className="btn-primary" onClick={apply}>查询</button>
            <button type="button" className="btn-ghost" onClick={reset}>重置</button>
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="empty-state">
            <p>暂无符合条件的通知</p>
            <button type="button" className="btn-ghost" onClick={reset}>重置筛选条件</button>
          </div>
        ) : (
          <ul className="list-rows">
            {rows.map((n) => (
              <li className="list-row" key={n.id}>
                <span className="bullet">▪</span>
                <Link className="row-title" to={`/notices/${n.id}`}>
                  {n.title}
                  {n.attachments && n.attachments.length > 0 && <span className="clip-icon" title="含附件">📎</span>}
                </Link>
                <FavStar type="notice" id={n.id} title={n.title} className="row-star" />
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
