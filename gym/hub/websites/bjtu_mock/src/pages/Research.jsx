import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import ChannelLayout from '../components/ChannelLayout';
import NotFound from './NotFound';

const SIDEBAR = [
  ['科技动态', '/research/dongtai'],
  ['平台基地', '/research/pingtai'],
  ['成果转化', '/research/zhuanhua'],
  ['学术期刊', '/research/qikan'],
];

const LABS = [
  ['轨道交通控制与安全国家重点实验室', '国家级', '列车运行控制、安全检测与应急指挥'],
  ['铁路智能运输系统研究中心', '省部级', '运输组织优化与智能调度'],
  ['城市交通信息工程研究中心', '省部级', '城市交通大数据与信号控制'],
  ['新能源电力装备研究院', '校级', '牵引供电与储能技术'],
  ['智慧高铁协同创新中心', '省部级', '高速列车智能运维'],
];

const CASES = [
  ['列车智能调度系统', '已在多条城市轨道交通线路部署，提升早晚高峰运力调配效率。'],
  ['轨道缺陷智能检测装备', '服务于多条干线铁路的夜间天窗检修作业。'],
  ['车站客流预警平台', '在大型枢纽车站试用，支撑大客流组织决策。'],
];

const JOURNALS = [
  ['《交通运输系统工程技术》', '季刊', '刊载交通运输系统工程领域原创成果'],
  ['《北京交通大学学报》', '双月刊', '综合理工类学报，收录我校各学科论文'],
  ['《物流技术与应用研究》', '季刊', '聚焦物流系统与供应链管理的学术刊物'],
];

function Dongtai() {
  const { state } = useApp();
  const rows = [...state.news].filter((n) => n.category === '教学科研').sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, 6);
  return (
    <div>
      <ul className="plain-list">
        {rows.map((n) => (
          <li key={n.id}>
            <Link to={`/news/${n.id}`}>{n.title}</Link>
            <span className="row-date">{n.date}</span>
          </li>
        ))}
      </ul>
      <Link className="more-link" to="/news?category=教学科研">查看更多科技动态 &gt;</Link>
    </div>
  );
}

const SECTIONS = {
  dongtai: ['科技动态', <Dongtai key="d" />],
  pingtai: ['平台基地', (
    <table className="data-table" key="p">
      <thead><tr><th>平台名称</th><th>级别</th><th>研究方向</th></tr></thead>
      <tbody>
        {LABS.map((l) => <tr key={l[0]}><td>{l[0]}</td><td>{l[1]}</td><td>{l[2]}</td></tr>)}
      </tbody>
    </table>
  )],
  zhuanhua: ['成果转化', (
    <div className="rich-text" key="z">
      <div className="step-flow">
        {['成果披露', '评估定价', '协议签署', '产业化实施', '收益分配'].map((s, i) => (
          <span className="step" key={s}><em>{i + 1}</em>{s}</span>
        ))}
      </div>
      <h3 className="sub-head">典型转化案例</h3>
      <ul className="case-list">
        {CASES.map(([t, d]) => (
          <li key={t}><strong>{t}</strong><p>{d}</p></li>
        ))}
      </ul>
    </div>
  )],
  qikan: ['学术期刊', (
    <div className="journal-grid" key="q">
      {JOURNALS.map(([name, cycle, desc]) => (
        <div className="journal-card" key={name}>
          <h3>{name}</h3>
          <span className="disc-chip">{cycle}</span>
          <p>{desc}</p>
          <Link className="more-link" to="/notices?category=科研管理">查看征稿与资助通知 &gt;</Link>
        </div>
      ))}
    </div>
  )],
};

export default function Research() {
  const { section } = useParams();
  const entry = SECTIONS[section];
  if (!entry) return <NotFound />;
  const [title, body] = entry;
  return (
    <ChannelLayout
      title="科学研究"
      en="RESEARCH"
      crumb={[{ label: '科学研究', to: '/research/dongtai' }, { label: title }]}
      sidebar={SIDEBAR.map(([label, to]) => ({ label, to }))}
    >
      <h2 className="channel-title">{title}</h2>
      {body}
    </ChannelLayout>
  );
}
