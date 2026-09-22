import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import Breadcrumb from './Breadcrumb';

export default function ChannelLayout({ title, en, sidebar, children, crumb }) {
  const { pathname, search } = useLocation();
  return (
    <div className="channel-page">
      <Breadcrumb items={crumb} />
      <div className="wrap channel-grid">
        <aside className="channel-side">
          <div className="side-head">
            <h2>{title}</h2>
            <span>{en}</span>
          </div>
          <ul className="side-list">
            {sidebar.map((it) => {
              const active = it.to === pathname + (it.search || '') || (it.to === pathname && (!it.search || it.search === search));
              return (
                <li key={it.label}>
                  <Link className={`side-link ${active ? 'active' : ''}`} to={{ pathname: it.to, search: it.search || '' }}>
                    {it.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </aside>
        <section className="channel-body">{children}</section>
      </div>
    </div>
  );
}
