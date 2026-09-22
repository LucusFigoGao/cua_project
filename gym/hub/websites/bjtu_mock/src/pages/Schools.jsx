import React from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import Breadcrumb from '../components/Breadcrumb';

export default function Schools() {
  const { state } = useApp();
  return (
    <div className="list-page">
      <Breadcrumb items={[{ label: '院系设置' }]} />
      <div className="wrap list-wrap">
        <div className="sec-title list-title">
          <h2>院系设置<span className="sec-en">SCHOOLS & DEPARTMENTS</span></h2>
          <span className="list-count">共 {state.schools.length} 个学院（部）</span>
        </div>
        <div className="school-grid">
          {state.schools.map((s) => (
            <Link className="school-card" key={s.id} to={`/schools/${s.id}`}>
              <div className="school-name">{s.name}</div>
              <div className="school-en">{s.en}</div>
              <div className="school-meta">创建于 {s.founded} 年　在校生约 {s.students} 人</div>
              <div className="school-chips">
                {s.disciplines.slice(0, 2).map((d) => <span className="disc-chip" key={d}>{d}</span>)}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
