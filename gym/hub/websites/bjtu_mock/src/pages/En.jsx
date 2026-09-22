import React from 'react';
import { Link } from 'react-router-dom';

export default function En() {
  return (
    <div className="en-page">
      <div className="wrap en-wrap">
        <h1>Beijing Jiaotong University</h1>
        <p className="en-sub">Official Portal (Sandbox Mock) — Simplified Chinese edition is the primary site.</p>
        <div className="en-links">
          <Link className="btn-primary" to="/">Home (Chinese)</Link>
          <Link className="btn-ghost" to="/news">News</Link>
          <Link className="btn-ghost" to="/notices">Notices</Link>
          <Link className="btn-ghost" to="/about/jianjie">About</Link>
          <Link className="btn-ghost" to="/admission/bkzs">Admissions</Link>
        </div>
        <p className="muted">Founded in 1896, BJTU is a national key university featuring transportation science and engineering. This English stub routes back to the Chinese portal.</p>
      </div>
    </div>
  );
}
