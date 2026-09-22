import React from 'react';

// Synthetic banner scenes (CSS gradient + SVG line art). No copyrighted assets.
const SCENES = {
  1: { bg: 'linear-gradient(120deg,#7d0d0d 0%,#a51b10 45%,#c8410f 100%)', accent: '#f4c76a', sky: '#8f1210' },
  2: { bg: 'linear-gradient(120deg,#041f4b 0%,#0a3d85 55%,#0f63b8 100%)', accent: '#7fd4ff', sky: '#062a63' },
  3: { bg: 'linear-gradient(120deg,#14532d 0%,#2f7a45 55%,#79a86a 100%)', accent: '#ffe9a8', sky: '#1d6b3f' },
  4: { bg: 'linear-gradient(120deg,#232a5c 0%,#5b3a8e 55%,#b06ab3 100%)', accent: '#ffd9a0', sky: '#2b3a67' },
};

function Skyline({ accent, variant }) {
  return (
    <svg className="scene-skyline" viewBox="0 0 1200 160" preserveAspectRatio="none" aria-hidden="true">
      <g fill="none" stroke={accent} strokeOpacity="0.55" strokeWidth="2">
        {variant % 2 === 1 ? (
          <>
            <path d="M60 160 V90 h60 V60 h40 V90 h60 V160" />
            <path d="M300 160 V70 h30 V40 h20 V70 h30 V160" />
            <path d="M480 160 V100 h90 V55 h50 V100 h90 V160" />
            <path d="M800 160 V80 h45 V50 h45 V80 h45 V160" />
            <path d="M1020 160 V95 h70 V65 h50 V95 h40 V160" />
          </>
        ) : (
          <>
            <path d="M80 160 V75 h50 V45 h40 V75 h50 V160" />
            <path d="M330 160 V95 h80 V60 h60 V95 h80 V160" />
            <path d="M680 160 V70 h35 V35 h25 V70 h35 V160" />
            <path d="M880 160 V100 h100 V70 h60 V100 h80 V160" />
          </>
        )}
        <line x1="0" y1="159" x2="1200" y2="159" />
      </g>
    </svg>
  );
}

export function BannerSlide({ variant = 1, slogan, sub }) {
  const scene = SCENES[variant] || SCENES[1];
  return (
    <div className="banner-slide" style={{ background: scene.bg }}>
      <Skyline accent={scene.accent} variant={variant} />
      <div className="banner-text">
        <div className="banner-slogan" style={{ color: variant === 1 ? '#f6d78b' : '#ffffff' }}>{slogan}</div>
        <div className="banner-sub">{sub}</div>
      </div>
    </div>
  );
}

const TILE_SCENES = [
  { label: '主楼', bg: 'linear-gradient(160deg,#0a3d85,#1e7fd6)' },
  { label: '图书馆', bg: 'linear-gradient(160deg,#134e78,#3f8fbf)' },
  { label: '体育馆', bg: 'linear-gradient(160deg,#14532d,#4ba509)' },
  { label: '银杏大道', bg: 'linear-gradient(160deg,#8a5a00,#eea200)' },
  { label: '明湖', bg: 'linear-gradient(160deg,#0b4e63,#00a4db)' },
  { label: '校门', bg: 'linear-gradient(160deg,#5c1a1a,#c0392b)' },
];

export function PhotoTile({ index = 0 }) {
  const scene = TILE_SCENES[index % TILE_SCENES.length];
  return (
    <div className="photo-tile" style={{ background: scene.bg }}>
      <svg viewBox="0 0 200 130" preserveAspectRatio="none" aria-hidden="true">
        <g fill="none" stroke="#ffffff" strokeOpacity="0.65" strokeWidth="2">
          <path d="M40 120 V60 h30 V40 h30 V60 h30 V120" />
          <path d="M140 120 V75 h30 V120" />
          <line x1="10" y1="120" x2="190" y2="120" />
        </g>
      </svg>
      <span className="photo-tile-label">{scene.label}</span>
    </div>
  );
}

export function CampusThumb() {
  return (
    <svg className="campus-thumb" viewBox="0 0 300 180" aria-hidden="true">
      <rect width="300" height="180" fill="#dcebf8" />
      <rect y="120" width="300" height="60" fill="#9cc4e4" />
      <g fill="#005bac" fillOpacity="0.85">
        <rect x="40" y="60" width="60" height="60" />
        <rect x="120" y="40" width="50" height="80" />
        <rect x="190" y="70" width="70" height="50" />
      </g>
      <g fill="#4ba509" fillOpacity="0.8">
        <circle cx="30" cy="115" r="14" />
        <circle cx="110" cy="118" r="12" />
        <circle cx="275" cy="116" r="13" />
      </g>
      <circle cx="250" cy="35" r="16" fill="#eea200" fillOpacity="0.9" />
    </svg>
  );
}
