import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="nf-page">
      <div className="nf-band">
        <h1>页面不存在</h1>
        <p>您访问的页面可能已删除或地址有误（404）</p>
      </div>
      <div className="wrap nf-links">
        <Link className="btn-primary" to="/">首页</Link>
        <Link className="btn-ghost" to="/news">新闻网</Link>
        <Link className="btn-ghost" to="/notices">通知公告</Link>
      </div>
    </div>
  );
}
