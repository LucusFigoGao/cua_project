# Research Assets — bjtu_mock (北京交通大学官网 www.bjtu.edu.cn)

## App overview

Mock of the official portal of Beijing Jiaotong University (北京交通大学). A content-heavy
Chinese university website: fixed blue header with mega-dropdowns over a full-bleed photo
carousel, dense news/notice lists, channel pages, and service forms. UI language:
**Simplified Chinese only**. Brand: 交大蓝 `#005bac` + gold `#eea200` accents (see DESIGN.md).

Research method: the live site was fetched directly with `curl` (homepage HTML, `/tzgg/index.htm`
notice list, a notice article detail, `css/css2019/style.css`, `css/css2019/index.css`), so all
navigation structure, section order, pagination patterns and design tokens below are extracted
from the **real site**, not guessed. Bing image search did NOT return usable UI screenshots of
this site (it returns generic Beijing photos / stock templates), therefore the visual ground
truth for the dev agent = real CSS tokens (DESIGN.md) + real site images in `screenshots/`
(real white logo, 4 real carousel banners, footer logo) + the layout descriptions below.

## Screenshots inventory (`assets/screenshots/`)

| File | What it is | Use |
|---|---|---|
| `real_logo.png` | REAL site header logo, 228×61, **white-on-transparent** wordmark | reference for wordmark proportions; recreate as SVG/text, do not embed |
| `real_footer_logo.png` | REAL footer wordmark (white) | same |
| `real_banner_01.jpg` | REAL carousel banner 2480×801 — deep-red 130th-anniversary art, gold calligraphy | reference: banner aspect ≈3.1:1, red+gold celebratory style |
| `real_banner_02.jpg` … `real_banner_04.jpg` | REAL carousel banners (campus/architecture photography style) | reference: photographic blue/green campus slides |
| `北京交通大学官网首页_01..06.*` | Bing results — generic Beijing city photos (CCTV tower, Forbidden City), **NOT site UI** | ignore for layout; usable only as mood for campus photography |

Notes: the image-search skill initially failed (icrawler missing → recursion error); after
`pip3 install icrawler` it ran but Bing has no real UI screenshots of bjtu.edu.cn indexed.
The 4 `real_*` banners + 2 logos are the authoritative visual references. Mock banners must be
**synthetic** (CSS gradients/SVG scenes with invented slogans), same aspect & palette family.

## Real site structure (extracted 2026-09)

### Header (all pages)
- Top utility bar, right-aligned pills (`#004d92`, radius 15px): 校友 | 访客及考生 | 教职工 | 学生 | English + orange search block (`#f6ad3c` 32×32).
- Main nav (46px; transparent `#004e91`@60% over banner on home; solid `#005bac` 60px + shadow when scrolled / on inner pages), white bold 16px items with gold 4px hover bar and `#cce1fa`@80% dropdown bands:
  首页 · 学校概况(学校简介/学校章程/机构设置/现任领导/历任领导/历史沿革/领导题词/基本数据/学校标识/校园风光) · 院系设置(23 学院 list) · 招生就业(本科生招生/研究生招生/来华留学生招生/继续教育招生/本科生就业/研究生就业/创业指导) · 教学培养(本科生/研究生/继续教育/留学生) · 科学研究(科技动态/平台基地/成果转化/学术期刊) · 合作交流 · 学科师资 · 信息资源.
- **Mock nav (per product spec)**: 首页, 学校概况, 院系设置, 教育教学, 科学研究, 招生就业, 新闻网, 通知公告 — keep real dropdown contents where they map (学校概况/院系设置/科学研究/招生就业), 新闻网 dropdown = news categories, 通知公告 dropdown = notice categories.

### Homepage section order (real)
1. Banner carousel (flexslider: 40×40 side arrows `#005bac`@60%→`#00a2e6` hover; bottom-center paging bar 170×24 `#005bac`@60% radius 8px8px0 0, numbers white, active gold).
2. **交大头条 Top News** — left: 2 featured items with green date stack (DD 18px / YYYY 12px `#4ba509`) + title + 1-line summary; right: 6-row title+date list; header row has 「进入新闻网」 link; rule `1px #005bac`.
3. **教学科研 Research** — `listTitle01` (h2 20px + gray Arial EN span, right 「更多」) + 5 rows.
4. **菁菁校园 Viewpoint** — featured image card w/ summary + 5 rows.
5. **通知公告 Notice** — 5 rows, each with 52×49 green date block (`border-right 1px #c0c9d2`) left of the title.
6. **光影交大 CAMPUS LIFE** — centered white-on-band title (h2 24px + EN 14px @50%) + horizontal photo strip.
7. **专题网站** — quick-link tile grid (人才招聘/信息公开/招生资讯网/研究生招生专题网/校友网/基金会/校园信息门户 …).
8. Footer (`#065eb1` w/ photo overlay): 意见箱|建言献策|知行论坛|官方微博|官方微信 columns, address 「地址：北京市海淀区上园村3号北京交通大学　邮编：100044」, 京ICP备/京公网安备 lines, centered footer wordmark.

### 通知公告 list page (real `/tzgg/index.htm`)
Breadcrumb 「您所在的位置：首页 - 通知公告」; left sidebar (channel title + 3 sub-entries);
right list rows `YYYY/MM/DD + title`, 20/page; pagination `1 2 3 4 5 下一页 尾页`.
Mock: 10/page, add category pills + date-range inputs (stateful filter), favorites star per row.

### 新闻网 (real news.bjtu.edu.cn)
Own nav: 首页/交大要闻/校园时讯/教学科研/合作交流/院部采风/菁菁校园/校友动态/媒体交大/交大人物/学术文化/校媒直通/光影交大/校史长廊/下载专区/联系我们.
List: title + 「2026年09月21日」 below it, 30/page, pager 「共11244条 1/375 首页 上页 下页 尾页 页」.
Mock renders as a section of the main site with category tabs; date format `YYYY-MM-DD` right-aligned.

### Article detail (real)
Centered title (22px bold) → centered meta 「时间：2026-06-10」 (+来源/浏览量) → hairline →
body 16px line-height 2, `text-indent:2em` paragraphs → 「附件：」 block with `.docx/.pdf`
links (real site serves `/docs/...docx`) → prev/next. Mock adds 收藏 button + real downloads.

## Personas & workflows (training focus)
1. ** prospective student/parent**: reads 新闻网/通知公告, filters 招生考试 notices by date, downloads 招生简章 attachment, submits 招生咨询, favorites articles.
2. **visitor**: 校园参观预约 (create → view 我的预约 → cancel), reads 参观须知 notice.
3. **researcher/alumni**: site-wide search (keyword → scoped results → history chips), browses 学术研究/科研管理 notices.

## Feature list (priority)
- P0: shell (header+dropdowns+search overlay, footer, breadcrumb), routing, session state infra (/post /state /go, secureMockApiPlugin), seed corpus, design tokens.
- P1: homepage all blocks; 新闻网 list+detail; 通知公告 list (category+date filter)+detail w/ **real attachment downloads**; **校园参观预约 CRUD**; **招生咨询 form + 我的咨询**; **站内搜索 + history**; **收藏 + 我的收藏**; channel pages (学校概况/院系设置/教育教学/科学研究/招生就业) with real content depth.
- P2: header scroll shrink, carousel autoplay/pause+keyboard, 光影交大 lightbox, view-count increment, mobile ≤1200px collapse, /en stub page, print styles, footer 意见箱 form binding.

## Data model overview
See `data_model.md`: entities currentUser, NewsItem(32), NoticeItem(32 w/ attachments), School(23),
Booking, Inquiry, Favorite, SearchEntry, DownloadLog, noticeFilters, feedback.
State sync: localStorage `bjtu_mock_state_<sid>` / `bjtu_mock_initial_state_<sid>` + server
`.mock-states/<sid>.json`; `/go?sid=` diffs initial vs current (arrays diff whole).

## Out of scope (and why)
- Auth/login (public site; app starts as guest with pre-filled `currentUser` profile).
- Real subdomain sites (zsw/gs/job/lib…) — replaced by in-app channel pages, no dead links.
- Real network/emails/uploads — downloads are locally generated blobs; forms store locally.
- WeChat QR real scans — QR blocks render as decorative SVG placeholders labeled 官方微信/微博 linking to nothing external (route to /about/contacts info instead).
