import React from 'react';
import { Link } from 'react-router-dom';

export default function Breadcrumb({ items = [] }) {
  return (
    <div className="breadcrumb-band">
      <div className="wrap breadcrumb">
        <span>您所在的位置：</span>
        <Link to="/">首页</Link>
        {items.map((it, i) => (
          <span key={it.label + i}>
            <span className="crumb-sep">&gt;</span>
            {it.to ? <Link to={it.to}>{it.label}</Link> : <span className="crumb-current">{it.label}</span>}
          </span>
        ))}
      </div>
    </div>
  );
}
