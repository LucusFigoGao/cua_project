import React, { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import Breadcrumb from '../components/Breadcrumb';
import NotFound from './NotFound';

export default function SchoolDetail() {
  const { id } = useParams();
  const { state } = useApp();
  const school = state.schools.find((s) => s.id === id);

  const related = useMemo(() => {
    if (!school) return [];
    const keyword = school.name.replace(/（.*?）/g, '').replace(/学院|学部|部$/g, '').slice(0, 2);
    const hits = state.news.filter((n) => n.title.includes(keyword) || (n.summary || '').includes(keyword));
    return (hits.length >= 3 ? hits : state.news.filter((n) => n.category === '教学科研')).slice(0, 4);
  }, [school, state.news]);

  if (!school) return <NotFound />;

  return (
    <div className="list-page">
      <Breadcrumb items={[{ label: '院系设置', to: '/schools' }, { label: school.name }]} />
      <div className="wrap detail-wrap">
        <h2 className="channel-title">{school.name}</h2>
        <div className="school-en big">{school.en}</div>
        <div className="rich-text">
          <p>{school.intro}</p>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>学科方向</th><th>说明</th></tr>
          </thead>
          <tbody>
            {school.disciplines.map((d, i) => (
              <tr key={d}>
                <td>{d}</td>
                <td>{i === 0 ? '核心学科方向，设有本科至博士完整培养体系' : '特色方向，与核心学科交叉融合培养'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="info-cards">
          <div className="info-card"><span className="muted">院长</span><strong>{school.dean}</strong></div>
          <div className="info-card"><span className="muted">党委书记</span><strong>{school.dean.slice(0, 1)}守正</strong></div>
          <div className="info-card"><span className="muted">创建年份</span><strong>{school.founded}</strong></div>
          <div className="info-card"><span className="muted">在校生</span><strong>{school.students} 人</strong></div>
        </div>
        <div className="contact-block">
          <p>联系电话：010-5168 8000（合成）　邮箱：{school.id}@bjtu.example.edu.cn</p>
          <p>办公地址：北京市海淀区上园村3号　邮编：100044</p>
        </div>
        <div className="related-block">
          <h3>相关新闻</h3>
          <ul className="plain-list">
            {related.map((n) => (
              <li key={n.id}>
                <Link to={`/news/${n.id}`}>{n.title}</Link>
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
          <Link className="more-link" to="/schools">返回院系列表 &gt;</Link>
        </div>
      </div>
    </div>
  );
}
