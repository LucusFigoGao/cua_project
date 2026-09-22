import React from 'react';

export default function Pagination({ page, pageCount, total, onChange, pageSize = 10 }) {
  if (pageCount <= 0) return null;
  const pages = [];
  const start = Math.max(1, Math.min(page - 2, pageCount - 4));
  const end = Math.min(pageCount, start + 4);
  for (let i = start; i <= end; i += 1) pages.push(i);

  return (
    <div className="pagination">
      <span className="page-total">共 {total} 条　{page}/{pageCount}</span>
      <button type="button" className="page-btn" disabled={page === 1} onClick={() => onChange(1)}>首页</button>
      <button type="button" className="page-btn" disabled={page === 1} onClick={() => onChange(page - 1)}>上页</button>
      {pages.map((p) => (
        <button
          type="button"
          key={p}
          className={`page-btn page-num ${p === page ? 'current' : ''}`}
          onClick={() => onChange(p)}
        >
          {p}
        </button>
      ))}
      <button type="button" className="page-btn" disabled={page === pageCount} onClick={() => onChange(page + 1)}>下页</button>
      <button type="button" className="page-btn" disabled={page === pageCount} onClick={() => onChange(pageCount)}>尾页</button>
      <span className="page-size">每页 {pageSize} 条</span>
    </div>
  );
}
