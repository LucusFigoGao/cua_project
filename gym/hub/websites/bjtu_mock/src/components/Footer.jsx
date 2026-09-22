import React from 'react';
import { Link } from 'react-router-dom';
import { Wordmark } from './Header';

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="wrap footer-grid">
        <div className="footer-contact">
          <p>地址：北京市海淀区上园村3号北京交通大学</p>
          <p>邮编：100044　电话：010-51688114</p>
          <p>版权所有：北京交通大学信息中心</p>
        </div>
        <div className="footer-mark">
          <Wordmark className="wordmark footer-wordmark" />
        </div>
        <div className="footer-links">
          <div className="footer-col">
            <Link to="/admission/inquiry?cat=意见建议">意见箱</Link>
            <Link to="/admission/inquiry?cat=意见建议">建言献策</Link>
            <Link to="/news?category=菁菁校园">知行论坛</Link>
          </div>
          <div className="footer-col">
            <Link to="/admission">招生资讯网</Link>
            <Link to="/notices?category=校园管理">信息公开</Link>
            <Link to="/news?category=校园时讯">校友网</Link>
          </div>
          <div className="footer-col">
            <Link to="/about/biaoshi">官方微博</Link>
            <Link to="/about/biaoshi">官方微信</Link>
            <Link to="/about/jianjie">校园信息门户</Link>
          </div>
        </div>
      </div>
      <div className="wrap footer-bottom">
        <span>京ICP备12010520号-2　京公网安备 110402430068号（合成备案信息）</span>
      </div>
    </footer>
  );
}
