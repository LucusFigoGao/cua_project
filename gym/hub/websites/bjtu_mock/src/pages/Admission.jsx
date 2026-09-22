import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import ChannelLayout from '../components/ChannelLayout';
import NotFound from './NotFound';

const SIDEBAR = [
  ['本科生招生', '/admission/bkzs'],
  ['研究生招生', '/admission/yjszs'],
  ['就业服务', '/admission/jiuye'],
  ['创业指导', '/admission/chuangye'],
  ['招生咨询', '/admission/inquiry'],
];

const EMPLOYERS = [
  '中国国家铁路集团有限公司', '中国中车集团', '中国通号集团', '北京市地铁运营有限公司',
  '华为技术有限公司', '中兴通讯', '国家电网有限公司', '中国建设银行', '比亚迪股份有限公司', '京东集团',
];

function NoticeLinks({ category, count = 3 }) {
  const { state } = useApp();
  const rows = state.notices.filter((n) => n.category === category).sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, count);
  return (
    <ul className="plain-list">
      {rows.map((n) => (
        <li key={n.id}>
          <Link to={`/notices/${n.id}`}>{n.title}</Link>
          <span className="row-date">{n.date}</span>
        </li>
      ))}
    </ul>
  );
}

const SECTIONS = {
  bkzs: ['本科生招生', (
    <div className="rich-text">
      <p>学校本科招生实行统招批次、强基计划、国家专项、高校专项等多种类型。录取遵循“分数优先、遵循志愿”原则，大类招生专业入校后按培养方案分流。</p>
      <p>招生政策要点：平行志愿投档比例不超过105%；体检标准执行国家统一规定；入学后符合条件的学生可申请转专业与辅修学位。</p>
      <h3 className="sub-head">招生考试相关通知</h3>
      <NoticeLinks category="招生考试" />
      <div className="cta-band">
        <span>报考政策一对一答疑</span>
        <Link className="btn-primary" to="/admission/inquiry">招生咨询</Link>
      </div>
    </div>
  )],
  yjszs: ['研究生招生', (
    <div className="rich-text">
      <p>硕士研究生招生含全国统考、推荐免试与单独考试；博士研究生招生实行“申请—考核”制。招生专业目录与简章由研究生院统一发布。</p>
      <h3 className="sub-head">研究生招考通知</h3>
      <NoticeLinks category="招生考试" count={4} />
      <div className="cta-band">
        <span>导师方向与复试政策咨询</span>
        <Link className="btn-primary" to="/admission/inquiry">招生咨询</Link>
      </div>
    </div>
  )],
  jiuye: ['就业服务', (
    <div className="rich-text">
      <p>学校毕业生就业率连续多年保持在95%以上，约六成毕业生进入轨道交通、信息技术与金融服务等重点行业，深造率接近55%。</p>
      <table className="data-table">
        <thead><tr><th>指标</th><th>2026届</th></tr></thead>
        <tbody>
          <tr><td>毕业去向落实率</td><td>96.2%</td></tr>
          <tr><td>深造率（国内+出境）</td><td>54.8%</td></tr>
          <tr><td>重点行业就业占比</td><td>61.5%</td></tr>
        </tbody>
      </table>
      <h3 className="sub-head">主要雇主（合成示意）</h3>
      <div className="school-chips">
        {EMPLOYERS.map((e) => <span className="disc-chip" key={e}>{e}</span>)}
      </div>
    </div>
  )],
  chuangye: ['创业指导', (
    <div className="rich-text">
      <p>创业学院统筹全校创新创业教育，运营校内创客空间约3000平方米，设有种子基金与导师工作室，常年开设创业基础课程与路演训练营。</p>
      <ul className="case-list">
        <li><strong>双创赛事</strong><p>组织“互联网+”“挑战杯”等赛事校内选拔，近三届获国家级奖项二十余项。</p></li>
        <li><strong>孵化服务</strong><p>为在校生团队提供工商注册、知识产权与融资对接等一站式服务。</p></li>
      </ul>
      <div className="cta-band">
        <span>创业政策咨询通道</span>
        <Link className="btn-primary" to="/admission/inquiry?cat=其他">提交咨询</Link>
      </div>
    </div>
  )],
};

export default function Admission() {
  const { section } = useParams();
  const entry = SECTIONS[section];
  if (!entry) return <NotFound />;
  const [title, body] = entry;
  return (
    <ChannelLayout
      title="招生就业"
      en="ADMISSION & CAREER"
      crumb={[{ label: '招生就业', to: '/admission/bkzs' }, { label: title }]}
      sidebar={SIDEBAR.map(([label, to]) => ({ label, to }))}
    >
      <h2 className="channel-title">{title}</h2>
      {body}
    </ChannelLayout>
  );
}
