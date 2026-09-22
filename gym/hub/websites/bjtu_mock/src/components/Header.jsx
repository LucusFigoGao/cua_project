import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { NEWS_CATEGORIES, NOTICE_CATEGORIES } from '../data/seed';
import SearchOverlay from './SearchOverlay';

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

function formatToday() {
  const d = new Date();
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日　${WEEKDAYS[d.getDay()]}`;
}

export function Wordmark({ className = 'wordmark' }) {
  return (
    <svg className={className} viewBox="0 0 228 61" role="img" aria-label="北京交通大学">
      <text x="0" y="30" fill="#ffffff" fontSize="27" fontWeight="700" fontFamily="'STKaiti','KaiTi','Microsoft YaHei',serif" letterSpacing="2">北京交通大学</text>
      <text x="1" y="50" fill="#ffffff" fontSize="10.5" fontFamily="Arial, sans-serif" letterSpacing="1.1">BEIJING JIAOTONG UNIVERSITY</text>
    </svg>
  );
}

export default function Header() {
  const { state } = useApp();
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const isHome = pathname === '/';

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    onScroll();
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const solid = !isHome || scrolled;

  const nav = [
    { label: '首页', to: '/', base: '/' },
    {
      label: '学校概况', to: '/about/jianjie', base: '/about',
      children: [
        ['学校简介', '/about/jianjie'], ['学校章程', '/about/zhangcheng'], ['机构设置', '/about/jigou'],
        ['现任领导', '/about/lingdao'], ['历史沿革', '/about/lishi'], ['学校标识', '/about/biaoshi'], ['校园风光', '/about/fengguang'],
      ],
    },
    {
      label: '院系设置', to: '/schools', base: '/schools',
      children: (state.schools || []).map((s) => [s.name, `/schools/${s.id}`]),
      columns: true,
    },
    {
      label: '教育教学', to: '/education/benke', base: '/education',
      children: [
        ['本科生教育', '/education/benke'], ['研究生教育', '/education/yanjiusheng'],
        ['继续教育', '/education/jixu'], ['留学生教育', '/education/liuxue'],
      ],
    },
    {
      label: '科学研究', to: '/research/dongtai', base: '/research',
      children: [
        ['科技动态', '/research/dongtai'], ['平台基地', '/research/pingtai'],
        ['成果转化', '/research/zhuanhua'], ['学术期刊', '/research/qikan'],
      ],
    },
    {
      label: '招生就业', to: '/admission/bkzs', base: '/admission',
      children: [
        ['本科生招生', '/admission/bkzs'], ['研究生招生', '/admission/yjszs'],
        ['就业服务', '/admission/jiuye'], ['创业指导', '/admission/chuangye'], ['招生咨询', '/admission/inquiry'],
      ],
    },
    {
      label: '新闻网', to: '/news', base: '/news',
      children: NEWS_CATEGORIES.map((c) => [c, `/news?category=${encodeURIComponent(c)}`]),
    },
    {
      label: '通知公告', to: '/notices', base: '/notices',
      children: NOTICE_CATEGORIES.map((c) => [c, `/notices?category=${encodeURIComponent(c)}`]),
    },
  ];

  return (
    <>
      <header className={`site-header ${solid ? 'solid' : 'transparent'}`}>
        <div className="wrap header-inner">
          <div className="utility-row">
            <div className="utility-left">
              <span className="utility-date">{formatToday()}</span>
            </div>
            <div className="utility-right">
              <Link className="pill" to="/about/jianjie">校友</Link>
              <Link className="pill" to="/visit">访客及考生</Link>
              <Link className="pill" to="/education/jixu">教职工</Link>
              <Link className="pill" to="/education/benke">学生</Link>
              <Link className="pill pill-en" to="/en">English</Link>
              <button type="button" className="search-btn" aria-label="站内搜索" onClick={() => setSearchOpen(true)}>
                <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="#fff" strokeWidth="2">
                  <circle cx="8.5" cy="8.5" r="5.5" />
                  <line x1="13" y1="13" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>
          <div className="brand-row">
            <Link to="/" className="brand-link" aria-label="返回首页">
              <Wordmark />
            </Link>
          </div>
          <nav className="main-nav" aria-label="主导航">
            <ul>
              {nav.map((item) => (
                <li className="nav-item" key={item.label}>
                  <Link
                    to={item.to}
                    className={`nav-link ${item.base === '/' ? pathname === '/' : pathname.startsWith(item.base) ? 'active' : ''}`}
                  >
                    {item.label}
                  </Link>
                  {item.children && item.children.length > 0 && (
                    <div className={`dropdown-band ${item.columns ? 'multi' : ''}`}>
                      <div className="wrap dropdown-inner">
                        {item.children.map(([label, to]) => (
                          <Link key={label + to} className="dropdown-link" to={to}>{label}</Link>
                        ))}
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      {searchOpen && <SearchOverlay onClose={() => setSearchOpen(false)} />}
    </>
  );
}
