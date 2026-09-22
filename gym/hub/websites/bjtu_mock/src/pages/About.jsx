import React from 'react';
import { useParams } from 'react-router-dom';
import ChannelLayout from '../components/ChannelLayout';
import { PhotoTile } from '../components/SvgArt';
import NotFound from './NotFound';

const SIDEBAR = [
  ['学校简介', '/about/jianjie', 'jianjie'],
  ['学校章程', '/about/zhangcheng', 'zhangcheng'],
  ['机构设置', '/about/jigou', 'jigou'],
  ['现任领导', '/about/lingdao', 'lingdao'],
  ['历史沿革', '/about/lishi', 'lishi'],
  ['学校标识', '/about/biaoshi', 'biaoshi'],
  ['校园风光', '/about/fengguang', 'fengguang'],
];

const STATS = [
  ['创建年份', '1896年（前身北京铁路管理传习所）'],
  ['办学定位', '教育部直属全国重点大学、“双一流”建设高校'],
  ['学院设置', '23个学院（部）'],
  ['本科专业', '83个'],
  ['在校学生', '约34000人'],
  ['教职工', '约3100人'],
];

const UNITS = [
  ['党群部门', '纪委办公室、党委组织部、党委宣传部、党委统战部、机关党委'],
  ['行政机构', '学校办公室、发展规划处、人事处、教务处、科学研究院、学生工作部、国际合作交流处、财务处、审计处、后勤保障处'],
  ['直属单位', '图书馆、信息中心、校史馆、档案馆、出版社、后勤服务产业集团'],
];

const LEADERS = [
  ['党委书记', '王知行'], ['校长', '李交通'], ['党委副书记', '赵明德'], ['党委副书记、纪委书记', '钱清风'],
  ['副校长', '孙轨通'], ['副校长', '周信号'], ['副校长', '吴运筹'], ['副校长', '郑育才'],
];

const TIMELINE = [
  ['1896', '清政府创办北京铁路管理传习所，为中国近代铁路管理教育之始。'],
  ['1921', '与上海、唐山两校合并组建交通大学，设北京学校。'],
  ['1923', '更名为北京交通大学，学科体系逐步完备。'],
  ['1952', '院系调整，成为培养铁道运输管理人才的重要基地。'],
  ['1970', '迁址河北，后于1979年恢复北京办学。'],
  ['1996', '建校一百周年，启用新版校徽与校训标识。'],
  ['2003', '恢复北京交通大学校名，进入国家重点建设高校行列。'],
  ['2017', '入选国家“双一流”建设高校名单。'],
  ['2026', '迎来建校130周年，全面推进智慧交通特色世界一流大学建设。'],
];

function Jianjie() {
  return (
    <div className="rich-text">
      <p>北京交通大学是教育部直属，教育部、交通运输部、北京市人民政府和中国国家铁路集团有限公司共建的全国重点大学，是国家“双一流”建设高校。学校历史源远流长，其前身可追溯至1896年清政府创办的北京铁路管理传习所，是中国近代铁路管理、电信教育的重要发祥地。</p>
      <p>学校秉承“知行”校训，坚持“育人为本、德育为先、能力为重、全面发展”的教育理念，形成了以信息、管理等学科为优势，以交通科学与技术为特色，工、管、经、理、文、法、哲等多学科协调发展的学科体系。</p>
      <p>学校设有23个学院（部），开办83个本科专业；拥有多个国家及省部级科研平台，在轨道交通控制、运输组织、信息安全等领域取得了一系列重要成果，为国家铁路事业和经济社会发展培养了大批骨干人才。</p>
      <p>面向未来，学校坚持以学科建设为龙头，以人才培养为根本，深入实施质量提升、人才强校、创新驱动、国际化发展等战略，努力建设特色鲜明世界一流大学。</p>
      <table className="data-table stats-table">
        <tbody>
          {STATS.map(([k, v]) => (
            <tr key={k}><th>{k}</th><td>{v}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Zhangcheng() {
  return (
    <div className="rich-text">
      <p>（摘录）第一章　总则　第一条　为保障学校依法办学和自主管理，依据《中华人民共和国教育法》《中华人民共和国高等教育法》等法律，结合学校实际，制定本章程。</p>
      <p>第二条　学校名称为北京交通大学，简称北京交大；英文译名为 Beijing Jiaotong University。学校法定住所为北京市海淀区上园村3号。</p>
      <p>第三条　学校以人才培养、科学研究、社会服务、文化传承创新和国际交流合作为基本职能，坚持社会主义办学方向，落实立德树人根本任务。</p>
      <p>第四条　学校校训为“知行”。学校弘扬“饮水思源、爱国荣校”的办学传统，倡导严谨治学、求实创新的校风学风。</p>
      <p>第二章　学校职能　第五条　学校以全日制学历教育为主，同时开展继续教育与中外合作办学；教育层次涵盖本科、硕士、博士研究生教育。</p>
      <p>第六条　学校依法确定和调整学历教育修业年限，实行学分制；对完成学业且达到学位授予标准者，依法颁发学历证书并授予学位。</p>
    </div>
  );
}

function Jigou() {
  return (
    <div className="rich-text">
      <table className="data-table">
        <thead><tr><th>类别</th><th>单位</th></tr></thead>
        <tbody>
          {UNITS.map(([k, v]) => (
            <tr key={k}><th>{k}</th><td>{v}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="muted note">注：以上为合成示意名单，仅用于沙箱环境展示。</p>
    </div>
  );
}

function Lingdao() {
  return (
    <div className="leader-grid">
      {LEADERS.map(([role, name]) => (
        <div className="leader-card" key={`${role}-${name}`}>
          <div className="leader-avatar">{name.slice(0, 1)}</div>
          <div className="leader-name">{name}</div>
          <div className="leader-role">{role}</div>
        </div>
      ))}
      <p className="muted note wide">注：以上姓名为合成内容，仅用于沙箱环境展示。</p>
    </div>
  );
}

function Lishi() {
  return (
    <ul className="timeline">
      {TIMELINE.map(([year, text]) => (
        <li className="timeline-item" key={year}>
          <span className="timeline-year">{year}</span>
          <p>{text}</p>
        </li>
      ))}
    </ul>
  );
}

function Biaoshi() {
  return (
    <div className="rich-text">
      <p>学校标识以“交大蓝”为主色，校徽主体为齿轮、铁砧、书本与“BJTU”绶带组合，象征工程实践与知行合一的办学传统。本页展示为合成示意图，非官方矢量文件。</p>
      <div className="color-chips">
        <div className="color-chip"><span className="swatch" style={{ background: '#005bac' }} /><span>交大蓝 #005bac</span></div>
        <div className="color-chip"><span className="swatch" style={{ background: '#e74155' }} /><span>交大红 #e74155</span></div>
        <div className="color-chip"><span className="swatch" style={{ background: '#eea200' }} /><span>校庆金 #eea200</span></div>
      </div>
      <p>官方微博、官方微信等新媒体矩阵入口见页脚链接；校园影像资料可在“校园风光”栏目浏览。</p>
    </div>
  );
}

function Fengguang() {
  return (
    <div className="gallery-grid">
      {[0, 1, 2, 3, 4, 5, 0, 1].map((v, i) => (
        <PhotoTile key={i} index={v} />
      ))}
    </div>
  );
}

const SECTIONS = {
  jianjie: ['学校简介', Jianjie],
  zhangcheng: ['学校章程', Zhangcheng],
  jigou: ['机构设置', Jigou],
  lingdao: ['现任领导', Lingdao],
  lishi: ['历史沿革', Lishi],
  biaoshi: ['学校标识', Biaoshi],
  fengguang: ['校园风光', Fengguang],
};

export default function About() {
  const { section } = useParams();
  const entry = SECTIONS[section];
  if (!entry) return <NotFound />;
  const [title, Body] = entry;
  return (
    <ChannelLayout
      title="学校概况"
      en="ABOUT BJTU"
      crumb={[{ label: '学校概况', to: '/about/jianjie' }, { label: title }]}
      sidebar={SIDEBAR.map(([label, to, key]) => ({ label, to, search: '', activeKey: key }))}
    >
      <h2 className="channel-title">{title}</h2>
      <Body />
    </ChannelLayout>
  );
}
