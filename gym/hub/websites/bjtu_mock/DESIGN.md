# Design System — 北京交通大学官网 (bjtu.edu.cn) Mock

> Source of truth: extracted from the live site's own CSS (`/css/css2019/style.css`, `/css/css2019/index.css`, fetched 2026-09) plus reference assets in `assets/screenshots/` (real logo + real carousel banners downloaded from www.bjtu.edu.cn).
> All UI text is Simplified Chinese (简体中文). Numbers/dates/English subtitles use Arial.

## 1. Visual Theme & Atmosphere

A classic Chinese public-university portal: wide (1200px) centered content column over white, a full-bleed photo banner carousel behind a translucent blue navigation bar, dense text lists with small colored date blocks, and a deep-blue photographic footer. The identity color is **交大蓝 (Jiaoda Blue)** — a saturated institutional blue (`#005bac`) — used for nav, links, rules and section accents, with **gold (`#eea200`)** as the active/hover signal and **green (`#4ba509`)** reserved for date numerals. Anniversary/celebration banners may be deep red with gold calligraphy (see `real_banner_01.jpg`), but the chrome (nav/footer/links) stays blue.

Typography is system Chinese sans (Microsoft YaHei / PingFang fallback) at a small base size (14px), with bold 16–24px section headings accompanied by letter-spaced English subtitles in gray Arial. The overall feel is information-dense, formal, and static — no rounded cards, minimal shadows, hairline rules everywhere.

## 2. Color Palette & Roles

### Primary (交大蓝 family)
- **Jiaoda Blue / Primary Brand** (`#005bac`): main nav background (scrolled/inner pages), links, "更多/more" links, list rule under 头条 dates, banner bottom border, pagination active page, primary buttons.
- **Nav Overlay Blue** (`#004e91` @ 60% opacity): main nav bar sitting on top of the homepage banner carousel.
- **Top-utility Pill Blue** (`#004d92`): background of the small pill links (校友/访客及考生/教职工/学生) in the top utility bar.
- **Deep Blue** (`#004480`): link hover / pressed, table header backgrounds.
- **Footer Blue** (`#065eb1`): footer background base color (real site overlays a campus photo; mock may use a blue gradient + subtle photo-less texture).

### Accent
- **Gold** (`#eea200`): 4px top bar on hovered/active nav item, active carousel paging number, highlight marks.
- **Amber** (`#f6ad3c`): search button block (32×32) in top utility bar.
- **Red** (`#fe5635`, alt `#e74155`): "NEW/HOT" tags, form validation error text, cancel/删除 actions.
- **Green** (`#4ba509`): ALL date numerals (头条 date stack, notice date block) — Arial, italic in date blocks.

### Interactive / secondary blues
- **Sky** (`#00a2e6`): carousel arrow hover.
- **Cyan rule** (`#00a4db`): 3px underline of `listTitle03` section headings.
- **Bright blue** (`#1e7fd6`): secondary link/hover in lists.
- **Go-top blue** (`#2378c3`): back-to-top floating button.
- **Sub-nav tint** (`#cce1fa` @ 80%): dropdown menu background.

### Surface, text & borders
- **Background** (`#ffffff`): page base.
- **Section tint** (`#f7faff` / `#edf5fa`): alternating light-blue section bands (quick links, galleries).
- **Neutral tint** (`#f7f7f7`): table striping, breadcrumb band.
- **Text Primary** (`#333333`), **Text Secondary** (`#666666`), **Text Muted** (`#999999` — English subtitles, meta lines).
- **Border** (`#c0c9d2`): date-block right border, table borders; **Hairline** (`#e5e5e5`): list separators.

### Status
- **Success** (`#4ba509`), **Warning** (`#eea200`), **Error** (`#e74155`).

## 3. Typography Rules

Base: `font-family: 'Microsoft YaHei', 'PingFang SC', SimSun, SimHei, 'STHeiti Light', STHeiti, 'Lucida Grande', Tahoma, Arial, Helvetica, sans-serif;` body `font-size: 14px; color: #333;`
Numerals/dates/English subtitles: `Arial`.

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|------|------|------|--------|-------------|----------------|
| Banner slogan (overlay) | Microsoft YaHei | 40–48px | 700 | 1.3 | 2px |
| Page/Channel title (inner h1) | Microsoft YaHei | 26px | 700 | 1.5 | 1px |
| Article title | Microsoft YaHei | 22px | 700 | 1.6 | 0.5px |
| Section heading h2 (listTitle01) | Microsoft YaHei | 20px | 700 | 1.5 | 0.5px |
| Section heading EN subtitle | Arial | 16px (14px on bands) | 400 | 1.5 | 1px, color #999 |
| Band heading (光影交大, listTitle02) | Microsoft YaHei | 24px white | 700 | 1.5 | 0.6px |
| Nav item | Microsoft YaHei | 16px | 700 | 46px/60px | 1px |
| List row title | Microsoft YaHei | 14px | 400 (700 on hover) | 2.4 (≈34px row) | 0 |
| Date numeral (strong) | Arial | 18px (16px responsive) | 700 | 1 | 0, color #4ba509 |
| Date year / small (span, i) | Arial | 12–13px | 400 | 1 | 0, color #4ba509 (italic in blocks) |
| Meta line (时间/来源/浏览量) | Microsoft YaHei | 12–13px | 400 | 2 | 0, color #999 |
| Body paragraph (article) | Microsoft YaHei/SimSun | 16px | 400 | 2.0 | 0, indent 2em |
| Footer text | Microsoft YaHei | 12px | 400 | 1.5–36px lines | 0, color #fff |
| Breadcrumb | Microsoft YaHei | 13px | 400 | 40px | 0, color #666 |

## 4. Spacing & Layout

- **Content column**: `width: 1200px; margin: 0 auto;` (page background white; sections full-bleed with inner 1200px wrapper).
- **Top utility bar**: height ≈44px; pills `height: 25px; border-radius: 15px; padding: 0 10px; margin: 0 4px;` search button `32×32, border-radius 5px`.
- **Header**: `position: fixed; top: 0;` homepage = transparent over banner (nav `height: 46px`, bg `#004e91` @60%); scrolled/inner pages = solid `#005bac`, `height: 60px`, `box-shadow: 0 2px 6px rgba(0,0,0,.4)`.
- **Logo**: white wordmark, ≈228×61 (see `assets/screenshots/real_logo.png` — white-on-transparent; recreate as inline SVG/text wordmark "北京交通大学 BEIJING JIAOTONG UNIVERSITY" in white, do NOT embed the copyrighted PNG).
- **Banner carousel**: `max-width: 1920px; margin: 90px auto 0; border-bottom: 6px solid #005bac;` slide aspect ≈ 2480×801 (≈3.1:1); arrows `40×40` at mid-height, `#005bac` @60% → hover `#00a2e6`; paging bar bottom-center `170×24`, `#005bac` @60%, `border-radius: 8px 8px 0 0`, numbers 12px white, active `#eea200`.
- **Section vertical rhythm**: section padding `25px 0` (title block `padding: 20–25px 0`), list row height 34–38px.
- **Two-column inner pages**: left sidebar 220–260px (channel nav), right content fluid; gap 30–40px.
- **Card/box gap**: 20–30px; **border radius**: 0–5px (institutional, sharp); pills 15px; buttons 3–4px.
- **Footer**: `padding: 45px 0;` bg `#065eb1`; left info block line-height 36px; right QR column; centered footer wordmark ≈314px wide.
- **Back-to-top**: fixed, `bottom: 40px; right: 20px; 50×50; #2378c3; color #fff; font-size 26px`.

## 5. Component Patterns

- **Nav item (top level)**: `color:#fff; font-size:16px; font-weight:700; line-height:46px; display:block; height:46px;` hover/active: `li:before` gold bar `height:4px; background:#eea200;` + background lightens (`#cce1fa` wash expands).
- **Dropdown (sub-nav)**: full-width band under header, `background:#cce1fa` @80%; links `color:#4c4c4c; padding:5px 15px; line-height:23px; font-size:14px;` hover `color:#005bac`.
- **Top utility pill**: `background:#004d92; color:#fff; font-weight:700; font-size:14px; height:25px; line-height:23px; border-radius:15px; padding:0 10px;` hover `background:#005bac`.
- **Search button**: `32×32; background:#f6ad3c; border-radius:5px; color:#fff;` opens a centered search overlay (input 28px height, white bg, blue submit).
- **Section title (listTitle01)**: `h2 20px #333` + `<span>` English subtitle `Arial 16px #999 margin-left:8px`; right-floated `更多 >` link `color:#005bac; font-weight:700;` underline rule where used: `border-bottom:1px solid #005bac; height:34px; line-height:34px`.
- **Section title (listTitle03)**: inline-block `h2 18px` with `border-bottom:3px solid #00a4db; padding-bottom:8px; min-width:100px`.
- **头条 date stack (list-date01)**: `strong 18px` day + `span 12px` year, both `#4ba509` Arial, `padding-right:12px`, row rule `border-bottom:1px solid #005bac`.
- **Notice date block (list-date05)**: `52×49px; border-right:1px solid #c0c9d2; float:left;` `strong 18px bold` day + `i 13px italic` year-month, green `#4ba509`, Arial.
- **List row**: `li { line-height:34px; border-bottom:1px dashed #e5e5e5 (or none); }` title link `#333`, hover `#005bac` + bold; leading bullet `•/▪` or `·` in `#005bac`; right-aligned date `#999 Arial 13px` on list pages.
- **Button (primary)**: `background:#005bac; color:#fff; border:none; padding:8px 24px; font-size:14px; border-radius:3px; cursor:pointer;` hover `#004480`. **Button (secondary/ghost)**: `background:#fff; color:#005bac; border:1px solid #005bac;` hover bg `#edf5fa`. **Danger**: `#e74155` border/text for 取消/删除.
- **Input / select / textarea**: `height:34px; border:1px solid #c0c9d2; border-radius:3px; padding:0 10px; font-size:14px; color:#333; background:#fff;` focus `border-color:#005bac; outline:none; box-shadow:0 0 0 2px rgba(0,91,172,.15)`. Error state: `border-color:#e74155` + message `12px #e74155` below.
- **Pagination**: inline boxes `min-width:32px; height:32px; line-height:30px; border:1px solid #c0c9d2; margin:0 3px; color:#333;` current page `background:#005bac; color:#fff; border-color:#005bac;` hover `color:#005bac; border-color:#005bac`; labels 首页/上页/下页/尾页 + numbers + `共 N 条  M/K` gray text.
- **Breadcrumb band**: `background:#f7f7f7 (or photo band on inner pages); height:40–46px;` text `您所在的位置：首页 > 栏目` 13px `#666`, links `#005bac`.
- **Sidebar channel nav**: header block `background:#005bac; color:#fff; padding:12px 15px; font-size:18px; font-weight:700;` items `border:1px solid #e5e5e5; border-top:none; padding:10px 15px; color:#333;` active/hover `background:#edf5fa; color:#005bac; font-weight:700;`.
- **Article block**: centered `h1 22px`; centered meta `12–13px #999` (`时间：YYYY-MM-DD　来源：XXX　浏览量：N`); hairline; body `16px line-height:2 text-indent:2em`; 附件 box: `background:#f7faff; border:1px dashed #c0c9d2; padding:12px 16px;` paperclip + file links `#005bac` with `[PDF]`/`[DOC]` tag chips and size; prev/next row `13px #666` links blue.
- **Favorite (收藏) star**: outline star/☆ `#999` 16px on row hover; favorited = filled ★ `#eea200`; tooltip `收藏`/`已收藏`.
- **Modal (confirm cancel/删除)**: centered white box `width:420px; border-radius:4px; box-shadow:0 4px 20px rgba(0,0,0,.25);` title bar `#005bac` white text or plain with hairline; buttons primary + danger; closes on Esc and mask click.
- **Toast**: top-center pill `background:rgba(0,0,0,.75); color:#fff; padding:8px 20px; border-radius:4px;` auto-hide 2s (success green left-border / error red).
- **Footer**: bg `#065eb1`; columns: left contact block (`地址：…　邮编：…　京ICP备…` 12px white, line-height 36px → use 24px), middle wordmark, right QR/links; bottom copyright line `12px rgba(255,255,255,.8)`.

## 6. Shadow & Elevation

- Header (scrolled): `0 2px 6px rgba(0,0,0,0.4)`.
- Dropdown band: `0 4px 10px rgba(0,0,0,0.15)`.
- Modal: `0 4px 20px rgba(0,0,0,0.25)`; mask `rgba(0,0,0,0.5)`.
- Cards/blocks: **none** (flat, hairline borders) — do not add Material-style elevation.
- Back-to-top / toast: `0 2px 8px rgba(0,0,0,0.2)`.

## 7. Page-by-page structure (see assets/README.md §Layouts for full detail)

1. **首页 `/`**: fixed transparent header over carousel → 交大头条 Top News (2 featured w/ date stack + 6-row list + 进入新闻网) → 教学科研 Research (5 rows) → 菁菁校园 Viewpoint (featured image card + 5 rows) → 通知公告 Notice (5 rows w/ 52×49 date blocks) → 光影交大 CAMPUS LIFE band (photo strip) → 专题网站 quick-links grid → footer.
2. **新闻网 `/news`**: breadcrumb + category tabs (交大要闻/校园时讯/教学科研/合作交流/菁菁校园/媒体交大) + list (title left, date right, 10/page) + pagination; row hover shows ☆ favorite.
3. **新闻详情 `/news/:id`**: title, meta, body, 收藏 button, 附件 (if any), prev/next, 相关新闻 list.
4. **通知公告 `/notices`**: breadcrumb + filter bar (category pills + 日期起/止 + 查询/重置) + list w/ date + pagination; favorites.
5. **通知详情 `/notices/:id`**: title, meta (时间/发布单位/浏览量), body, **附件下载区** (real downloads), 收藏, prev/next.
6. **Channel pages** `/about*`, `/schools*`, `/education*`, `/research*`, `/admission*`: breadcrumb + left sidebar channel nav + rich static content (tables, leader lists, school grid, program cards).
7. **服务 pages**: `/visit` (校园参观预约 form + 我的预约), `/admission/inquiry` (招生咨询 form + 我的咨询), `/search` (站内搜索), `/favorites` (我的收藏).
8. **`/go`**: JSON state inspector.
