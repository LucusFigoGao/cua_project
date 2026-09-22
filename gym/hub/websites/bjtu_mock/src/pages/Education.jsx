import React from 'react';
import { Link, useParams } from 'react-router-dom';
import ChannelLayout from '../components/ChannelLayout';
import NotFound from './NotFound';

const SIDEBAR = [
  ['本科生教育', '/education/benke'],
  ['研究生教育', '/education/yanjiusheng'],
  ['继续教育', '/education/jixu'],
  ['留学生教育', '/education/liuxue'],
];

const MAJORS = [
  ['交通运输', '国家级一流专业', '四年'], ['物流工程', '国家级一流专业', '四年'],
  ['计算机科学与技术', '国家级一流专业', '四年'], ['通信工程', '国家级一流专业', '四年'],
  ['电气工程及其自动化', '国家级一流专业', '四年'], ['土木工程', '国家级一流专业', '四年'],
  ['机械工程', '省级一流专业', '四年'], ['经济学', '省级一流专业', '四年'],
  ['软件工程', '特色专业', '四年'], ['人工智能', '新工科专业', '四年'],
];

const DISCIPLINES = [
  ['系统科学', 'A-', '一级学科博士点'],
  ['交通运输工程', 'A-', '国家双一流学科'],
  ['信息与通信工程', 'B+', '一级学科博士点'],
  ['计算机科学与技术', 'B+', '一级学科硕士点'],
  ['管理科学与工程', 'B+', '一级学科博士点'],
  ['土木工程', 'B', '一级学科硕士点'],
];

const CONT_PROGRAMS = [
  ['铁道交通运营管理', '高起专', '2.5年'],
  ['会计学', '专升本', '2.5年'],
  ['计算机科学与技术', '专升本', '2.5年'],
  ['工商管理', '高起本', '5年'],
];

const INTL_PROGRAMS = [
  ['交通运输工程（英文授课）', '本科', '4年'],
  ['计算机科学与技术（英文授课）', '硕士', '2-3年'],
  ['工商管理（英文授课）', '硕士', '2年'],
  ['汉语进修', '非学历', '0.5-1年'],
];

function Cta() {
  return (
    <div className="cta-band">
      <span>对报考和培养有疑问？</span>
      <Link className="btn-primary" to="/admission/inquiry">前往招生咨询</Link>
    </div>
  );
}

const SECTIONS = {
  benke: ['本科生教育', (
    <div className="rich-text">
      <p>学校现有83个本科专业，覆盖工、管、经、理、文、法、哲等学科门类。本科教育实施“宽口径、厚基础、重实践、求创新”的培养模式，推行大类招生与通识教育，设有詹天佑学院本博贯通试点班。</p>
      <table className="data-table">
        <thead><tr><th>专业名称</th><th>专业层次</th><th>学制</th></tr></thead>
        <tbody>
          {MAJORS.map((m) => <tr key={m[0]}><td>{m[0]}</td><td>{m[1]}</td><td>{m[2]}</td></tr>)}
        </tbody>
      </table>
      <p>培养模式：一年级实施大类培养，二年级按志愿与成绩结合原则进行专业分流；全程实施导师制、学分制与创新创业学分认定。</p>
      <Cta />
    </div>
  )],
  yanjiusheng: ['研究生教育', (
    <div className="rich-text">
      <p>学校拥有博士学位一级学科授权点17个、硕士学位一级学科授权点34个，博士后科研流动站17个。研究生教育突出科教融合与产教融合，实施学术型与专业型分类培养。</p>
      <table className="data-table">
        <thead><tr><th>学科名称</th><th>评估结果</th><th>学位点类型</th></tr></thead>
        <tbody>
          {DISCIPLINES.map((d) => <tr key={d[0]}><td>{d[0]}</td><td>{d[1]}</td><td>{d[2]}</td></tr>)}
        </tbody>
      </table>
      <Cta />
    </div>
  )],
  jixu: ['继续教育', (
    <div className="rich-text">
      <p>远程与继续教育学院面向铁路行业与社会开展学历继续教育与非学历培训，学习形式以网络学习为主、面授为辅。</p>
      <table className="data-table">
        <thead><tr><th>专业</th><th>层次</th><th>学制</th></tr></thead>
        <tbody>
          {CONT_PROGRAMS.map((p) => <tr key={p[0]}><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td></tr>)}
        </tbody>
      </table>
      <Cta />
    </div>
  )],
  liuxue: ['留学生教育', (
    <div className="rich-text">
      <p>国际教育学院负责来华留学生的招生、培养与管理，现有学历生与非学历进修生覆盖百余个国家和地区，提供中国政府奖学金、北京市奖学金与校长奖学金申请通道。</p>
      <table className="data-table">
        <thead><tr><th>项目</th><th>层次</th><th>学制</th></tr></thead>
        <tbody>
          {INTL_PROGRAMS.map((p) => <tr key={p[0]}><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td></tr>)}
        </tbody>
      </table>
      <p>申请须知：本科项目须提交学历证明与语言能力证明；英文授课项目须提供英语能力证明或参加学校面试。</p>
      <Cta />
    </div>
  )],
};

export default function Education() {
  const { section } = useParams();
  const entry = SECTIONS[section];
  if (!entry) return <NotFound />;
  const [title, body] = entry;
  return (
    <ChannelLayout
      title="教育教学"
      en="EDUCATION"
      crumb={[{ label: '教育教学', to: '/education/benke' }, { label: title }]}
      sidebar={SIDEBAR.map(([label, to]) => ({ label, to }))}
    >
      <h2 className="channel-title">{title}</h2>
      {body}
    </ChannelLayout>
  );
}
