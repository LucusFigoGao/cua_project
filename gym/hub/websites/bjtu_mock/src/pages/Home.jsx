import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { BannerSlide, CampusThumb, PhotoTile } from '../components/SvgArt';

const SLIDES = [
  { variant: 1, slogan: '知行致远　交通强国', sub: '庆祝北京交通大学建校一百三十周年' },
  { variant: 2, slogan: '智慧交通　引领未来', sub: '轨道交通智能运维高端论坛 2026 在我校举行' },
  { variant: 3, slogan: '菁菁校园　桃李芬芳', sub: '2026年校园开放日欢迎您预约参观' },
  { variant: 4, slogan: '学以致用　知行合一', sub: '新学期 新征程 欢迎新同学加入交大大家庭' },
];

const SPECIAL_TILES = [
  ['人才招聘', '/notices?category=人事招聘'],
  ['信息公开', '/notices?category=校园管理'],
  ['招生资讯网', '/admission/bkzs'],
  ['研究生招生', '/admission/yjszs'],
  ['校友网', '/news?category=校园时讯'],
  ['教育基金会', '/notices?category=校庆活动'],
  ['校园信息门户', '/about/jianjie'],
  ['校庆专题网', '/about/lishi'],
];

function SectionTitle({ zh, en, more }) {
  return (
    <div className="sec-title">
      <h2>{zh}<span className="sec-en">{en}</span></h2>
      {more && <Link className="more-link" to={more}>更多 &gt;</Link>}
    </div>
  );
}

export default function Home() {
  const { state } = useApp();
  const [slide, setSlide] = useState(0);
  const paused = useRef(false);

  useEffect(() => {
    const timer = setInterval(() => {
      if (!paused.current) setSlide((s) => (s + 1) % SLIDES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const news = useMemo(() => [...state.news].sort((a, b) => (a.date < b.date ? 1 : -1)), [state.news]);
  const featured = news.filter((n) => n.isTop).slice(0, 2);
  const headRows = news.filter((n) => !featured.includes(n)).slice(0, 6);
  const research = news.filter((n) => n.category === '教学科研').slice(0, 5);
  const campus = news.filter((n) => n.category === '菁菁校园');
  const campusFeature = campus[0];
  const campusRows = campus.slice(1, 6);
  const notices = useMemo(() => [...state.notices].sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, 5), [state.notices]);

  return (
    <div className="home-page">
      <div
        className="banner"
        onMouseEnter={() => { paused.current = true; }}
        onMouseLeave={() => { paused.current = false; }}
      >
        <div className="banner-track" style={{ transform: `translateX(-${slide * 100}%)` }}>
          {SLIDES.map((s, i) => (
            <BannerSlide key={s.slogan} variant={s.variant} slogan={s.slogan} sub={s.sub} />
          ))}
        </div>
        <button type="button" className="banner-arrow left" aria-label="上一张" onClick={() => setSlide((s) => (s - 1 + SLIDES.length) % SLIDES.length)}>‹</button>
        <button type="button" className="banner-arrow right" aria-label="下一张" onClick={() => setSlide((s) => (s + 1) % SLIDES.length)}>›</button>
        <div className="banner-pager">
          {SLIDES.map((s, i) => (
            <button type="button" key={i} className={`pager-num ${i === slide ? 'active' : ''}`} onClick={() => setSlide(i)}>{i + 1}</button>
          ))}
        </div>
      </div>

      <div className="wrap home-section">
        <div className="sec-title head-title">
          <h2>交大头条<span className="sec-en">TOP NEWS</span></h2>
          <Link className="more-link" to="/news">进入新闻网 &gt;</Link>
        </div>
        <div className="head-grid">
          <div className="head-featured">
            {featured.map((n) => (
              <div className="head-feat-item" key={n.id}>
                <div className="date-stack">
                  <strong>{n.date.slice(8, 10)}</strong>
                  <span>{n.date.slice(0, 4)}</span>
                </div>
                <div className="head-feat-text">
                  <Link to={`/news/${n.id}`}>{n.title}</Link>
                  <p>{n.summary}</p>
                </div>
              </div>
            ))}
          </div>
          <ul className="head-list">
            {headRows.map((n) => (
              <li key={n.id}>
                <Link to={`/news/${n.id}`}>{n.title}</Link>
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="wrap home-section two-col">
        <div className="col">
          <SectionTitle zh="教学科研" en="RESEARCH" more="/news?category=教学科研" />
          <ul className="plain-list">
            {research.map((n) => (
              <li key={n.id}>
                <Link to={`/news/${n.id}`}>{n.title}</Link>
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="col">
          <SectionTitle zh="菁菁校园" en="VIEWPOINT" more="/news?category=菁菁校园" />
          {campusFeature && (
            <div className="viewpoint-card">
              <Link to={`/news/${campusFeature.id}`} className="viewpoint-thumb"><CampusThumb /></Link>
              <div className="viewpoint-text">
                <Link to={`/news/${campusFeature.id}`}>{campusFeature.title}</Link>
                <p>{campusFeature.summary}</p>
              </div>
            </div>
          )}
          <ul className="plain-list">
            {campusRows.map((n) => (
              <li key={n.id}>
                <Link to={`/news/${n.id}`}>{n.title}</Link>
                <span className="row-date">{n.date}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="wrap home-section">
        <SectionTitle zh="通知公告" en="NOTICE" more="/notices" />
        <ul className="notice-home-list">
          {notices.map((n) => (
            <li key={n.id}>
              <div className="notice-date-block">
                <strong>{n.date.slice(8, 10)}</strong>
                <i>{n.date.slice(0, 7)}</i>
              </div>
              <Link to={`/notices/${n.id}`}>{n.title}</Link>
            </li>
          ))}
        </ul>
      </div>

      <div className="campus-life-band">
        <div className="wrap">
          <div className="band-title">
            <h2>光影交大</h2>
            <span>CAMPUS LIFE</span>
          </div>
          <div className="photo-strip">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Link key={i} to="/news?category=菁菁校园" className="photo-strip-item">
                <PhotoTile index={i} />
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="wrap home-section">
        <SectionTitle zh="专题网站" en="SPECIAL SITES" />
        <div className="special-grid">
          {SPECIAL_TILES.map(([label, to]) => (
            <Link key={label} className="special-tile" to={to}>{label}</Link>
          ))}
        </div>
      </div>

      <div className="quick-strip">
        <div className="wrap quick-grid">
          <Link className="quick-item" to="/visit"><span className="quick-icon">参</span>校园参观预约</Link>
          <Link className="quick-item" to="/admission/inquiry"><span className="quick-icon">咨</span>招生咨询</Link>
          <Link className="quick-item" to="/search"><span className="quick-icon">搜</span>站内搜索</Link>
          <Link className="quick-item" to="/favorites"><span className="quick-icon">藏</span>我的收藏</Link>
        </div>
      </div>
    </div>
  );
}
