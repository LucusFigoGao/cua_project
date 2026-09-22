# 北京交通大学官网 Mock (bjtu_mock) — TODO

> Status: DEV ROUND 2 COMPLETE (AUDIT round 1 P1 fixes done: AUDIT-001/002/003 + P2 AUDIT-007)
> Last updated by: dev agent, 2026-09-21
> Research: `assets/README.md` | Data model: `assets/data_model.md` | Style guide: `DESIGN.md`
> Reference patterns: `websites/12306_mock/` (vite.config.js, src/utils/dataManager.js, src/pages/Go.jsx, SCHEMA.md) and `shared/secureMockApiPlugin.mjs`
> Dev server port: **5188** | UI language: **Simplified Chinese (all visible text)** | ALL seed content SYNTHETIC

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Done

---

## P0 — Core Shell & Infra
<!-- Without these the app cannot render or be verified. Implement first, in order. -->

- [x] **Scaffold**: `npm create vite@latest` react template inside `websites/bjtu_mock/` (keep existing assets/), `npm i react react-dom react-router-dom`; `vite.config.js` sets `server.port = 5188`, `server.host = true`, `preview.port 5188`.
- [x] **vite.config.js session infra** (copy the pattern from `websites/12306_mock/vite.config.js` verbatim in structure): import `secureMockApiPlugin` from `../../shared/secureMockApiPlugin.mjs` as FIRST plugin, then a local `mock-api` plugin with `configureServer` + `configurePreviewServer` implementing, with `sid` sanitized via `sid.replace(/[^a-zA-Z0-9_-]/g,'')` and per-sid files under `.mock-states/`:
  - `POST /post?sid=` body `{action:'set'|'set_current'|'reset', state}` → `set` writes `{initial_state: state, current_state: state}` (baseline before first mutation), `set_current` updates only `current_state`, `reset` restores `current_state = initial_state`.
  - `GET /state?sid=` → returns `current_state` object (or `{}`), `Cache-Control: no-cache`.
  - `GET /go?sid=` → `{initial_state, current_state, state_diff}` with recursive `computeDiff` (copy from 12306 config).
- [x] **Attachment file server** (same middleware): `GET /files/:attachmentId` looks the attachment up from the session's current_state (`notices[].attachments` / `news[].attachments`), generates bytes on the fly and responds with real download headers:
  - `fileType:'pdf'` → hand-built minimal valid PDF 1.4 (objects: Catalog/Pages/Page/Font/Content stream showing the fileName + 北京交通大学 synthetic notice title), `Content-Type: application/pdf`;
  - `fileType:'doc'` → Word-compatible HTML (`<html xmlns:w="urn:schemas-microsoft-com:office:word">…`), `Content-Type: application/msword`;
  - both with `Content-Disposition: attachment; filename="<encodeURIComponent(fileName)>"`. Unknown id → 404 JSON. Downloads must actually deliver a file the browser saves.
- [x] **dataManager.js** (`src/utils/dataManager.js`): copy 12306 pattern — `BASE_KEY='bjtu_mock_state'`, `BASE_INITIAL_KEY='bjtu_mock_initial_state'`, `getSessionId()` (URL `?sid=` → `sessionStorage['bjtu_mock_sid']`), `storageKey/initialKey(sid)`, `fetchCustomState(sid)`, `deepMerge`, `loadState`, `saveState(state, sid)` (localStorage + `POST /post?sid=` `{action:'set_current', state}`), `initializeData(sid, customState)` which on FIRST load (no initial key) POSTs `{action:'set', state: merged}` with `sid || 'default'` to create the server baseline, plus `createInitialData()` per `assets/data_model.md`.
- [x] **AppContext.jsx**: session-aware provider exactly per `.claude/commands/dev.md` spec — `initDone` ref, `sidRef`, refresh-vs-first-load check reading `localStorage.getItem(initialKey(sid))` BEFORE `initializeData`, async `fetchCustomState` on first load with `loading` gate, `updateState(updates)` = setState + `saveState(newState, sidRef.current)`; expose helpers `addBooking, cancelBooking, addInquiry, toggleFavorite, logSearch, logDownload, setNoticeFilters, addFeedback`.
- [x] **Routing** (`src/App.jsx`, BrowserRouter): `/` home; `/news` + `/news/:id`; `/notices` + `/notices/:id`; `/about` + `/about/:section` (sections: jianjie|zhangcheng|jigou|lingdao|lishi|biaoshi|fengguang); `/schools` + `/schools/:id`; `/education` + `/education/:section` (benke|yanjiusheng|jixu|liuxue); `/research` + `/research/:section` (dongtai|pingtai|zhuanhua|qikan); `/admission` + `/admission/:section` (bkzs|yjszs|jiuye|chuangye) ; `/admission/inquiry` 招生咨询; `/visit` 校园参观预约 (+ tab 我的预约); `/search`; `/favorites`; `/go`; `*` → styled 404 with links home. Index redirects use `RedirectWithQuery` (preserve `?sid=`) per dev.md File 4. ScrollToTop on route change.
- [x] **Go.jsx** (`/go` route): pretty-printed JSON of `{initial_state, current_state, state_diff}` fetched from server `/go?sid=` (read sid from sessionStorage), with copy button; also list tracked keys (bookings/inquiries/favorites/downloads/searchHistory/noticeFilters).
- [x] **Layout shell** (`components/Header.jsx`, `Footer.jsx`, `Breadcrumb.jsx`, `BackToTop.jsx`, `SearchOverlay.jsx`):
  - Header fixed: top utility row (pills 校友/访客及考生/教职工/学生 → route to `/about/jianjie`, `/visit`, `/education/jixu`, `/education/benke`; English → `/en` stub page P2; orange 32×32 search button opens SearchOverlay) + white wordmark logo (inline SVG text 「北京交通大学 / BEIJING JIAOTONG UNIVERSITY」 white, ≈228×61) + main nav 8 items 首页/学校概况/院系设置/教育教学/科学研究/招生就业/新闻网/通知公告 with hover gold 4px top bar and `#cce1fa`@80% dropdown bands (contents per assets/README §Header; every dropdown link routes to a real page/tab — no `javascript:void(0)`, no dead links).
  - Scroll behavior: after 60px scroll header becomes solid `#005bac` height 60px + shadow (home starts transparent over carousel; inner pages always solid).
  - SearchOverlay: centered modal (input + scope radio 全部/新闻/通知 + submit) → navigate `/search?q=…&scope=…`; closes on Esc/mask.
  - Footer `#065eb1`: left contact block (地址：北京市海淀区上园村3号北京交通大学　邮编：100044　电话：010-51688114 synthetic OK), middle wordmark, right link columns (意见箱→`/admission/inquiry?cat=意见建议`, 建言献策 same, 招生资讯网→`/admission`, 信息公开→`/notices?category=校园管理`, 校友网→`/news?category=校友动态`-like tab, 校园信息门户→toast-free real route `/about/jianjie`), bottom copyright synthetic 「北京交通大学信息中心 版权所有」+ 京ICP备12010520号-2 style line (synthetic number OK).
  - Breadcrumb band on every non-home page: 「您所在的位置：首页 > X > Y」 with working links.
  - BackToTop floating 50×50 `#2378c3` appears after 300px scroll.
- [x] **Global CSS** (`src/index.css`): tokens from DESIGN.md §2-4 (CSS vars: `--bjtu-blue:#005bac; --navy:#004480; --nav-overlay:#004e91; --pill:#004d92; --footer:#065eb1; --gold:#eea200; --amber:#f6ad3c; --green:#4ba509; --sky:#00a2e6; --cyan:#00a4db; --subnav:#cce1fa; --red:#e74155; --text:#333; --muted:#999; --border:#c0c9d2; --hairline:#e5e5e5; --tint:#f7faff;`), 1200px `.wrap`, fonts, buttons/inputs/pagination/list-row/sidebar classes per DESIGN.md §5. No gray disabled placeholders anywhere.
- [x] **Seed data** `createInitialData()` per `assets/data_model.md` §Seed corpus spec: 32 synthetic news (≥5/category, dates 2026-06→2026-09-21, 4 `isTop`), 32 synthetic notices (≥4/category, 2025-10→2026-09, 12 with 1-3 attachments pdf/doc), 23 schools, bookings×2, inquiries×1, favorites×2, searchHistory [], downloads [], feedback [], noticeFilters baseline. Keyword guarantees: ≥4 titles contain 校庆, ≥3 招生, ≥3 参观, ≥2 论坛.
- [x] `.gitignore`: add `.mock-states/`, `node_modules/`, `dist/`.

## P1 — Primary Features (stateful, verifiable via /go)

- [x] **首页 Home**: (a) banner carousel 4 synthetic slides (CSS gradient scenes + slogan text e.g. 「知行致远 交通强国」; aspect 2480:801; autoplay 5s, arrows 40×40 `#005bac`@60% hover `#00a2e6`, bottom paging bar numbers, active gold; pause on hover); (b) 交大头条 Top News block: 2 featured (green date stack DD/YYYY + title + summary) + right 6-row list + 「进入新闻网」→ `/news`; (c) 教学科研 Research 5 rows + 更多 → `/news?category=教学科研`; (d) 菁菁校园 Viewpoint featured card (synthetic SVG campus thumb + summary) + 5 rows + 更多 → `/news?category=菁菁校园`; (e) 通知公告 Notice 5 rows with 52×49 green date blocks + 更多 → `/notices`; (f) 光影交大 CAMPUS LIFE band (centered white title + 6 synthetic SVG photo tiles, click → lightbox P2 or route to `/news?category=菁菁校园`); (g) 专题网站 tile grid 8 tiles each routing (人才招聘→`/notices?category=人事招聘`, 信息公开→`/notices?category=校园管理`, 招生资讯网→`/admission`, 研究生招生→`/admission/yjszs`, 校友网→`/news?category=校友动态`… map each to a real route); (h) quick-service strip with 校园参观预约 → `/visit`, 招生咨询 → `/admission/inquiry`, 站内搜索 → `/search`, 我的收藏 → `/favorites`. Every 「更多」 and tile must navigate.
- [x] **新闻网 list `/news`**: breadcrumb; category tabs (全部/交大要闻/校园时讯/教学科研/合作交流/菁菁校园/媒体交大) as blue underline tabs bound to `?category=`; list rows = bullet + title (hover blue+bold) + right date `YYYY-MM-DD` + hover-revealed ☆ favorite toggle; 10/page pagination (首页/上页/numbers/下页/尾页 + 共N条); empty state 「暂无相关新闻」 with link back; rows link to `/news/:id`.
- [x] **新闻详情 `/news/:id`**: centered 22px title; meta 「时间：…　来源：…　浏览量：N」 (views increment once per session open, not persisted to avoid diff noise — keep in component state only); body paragraphs 16px lh2 indent 2em; 收藏 button (☆/★ gold, toggles `favorites`, toast 已收藏/已取消收藏); 附件 block if any (same download flow as notices); prev/next within category (disabled-look replaced by 「没有了」 plain text when at ends); 相关新闻 5 links (same category).
- [x] **通知公告 list `/notices`**: breadcrumb; **filter bar**: category pills (全部 + 6 NOTICE_CATEGORIES), 日期起/止 `<input type=date>`, 查询 button (applies → writes `noticeFilters` to state + filters list + resets page to 1), 重置 button (restores baseline filters); also accepts `?category=` from footer/quick links; list rows with date + title + paperclip icon when attachments exist + ☆ favorite; 10/page pagination with count line; results count text 「共 N 条」.
- [x] **通知公告详情 `/notices/:id`**: title, meta 「时间：…　发布单位：…　浏览量：…」, body, **附件下载区**: dashed `#f7faff` box listing each attachment as link `[PDF] 文件名 (186KB) 下载` → `href=/files/:attId` (real server download) AND onClick logs DownloadLog to state (so /go shows it); 收藏 button; prev/next; 相关通知 5 links.
- [x] **校园参观预约 `/visit`**: two tabs 参观预约 / 我的预约. Form fields: 参观人姓名*, 证件类型 select(身份证/护照/军官证), 证件号码* (18位校验), 联系电话* (11位), 参观日期* (date, min=today), 时段 radio 上午/下午, 校区 select 主校区/威海校区, 人数 number 1-10, 参观目的 textarea(optional); inline red error text under invalid fields on submit; on success: push Booking (status 已预约, id BK+date+seq), toast 预约成功, switch to 我的预约 tab. 须知 panel (synthetic bullets: 开放时间/携带证件/团体须提前3日). 我的预约: table 预约号/参观人/日期/时段/校区/人数/状态/操作; 状态 tag green 已预约 / gray 已取消; 操作 取消预约 (only when 已预约 and date ≥ today) → confirm modal → status 已取消 + toast; empty state with 去预约 button. All mutations via updateState → /go diff `bookings`.
- [x] **招生咨询 `/admission/inquiry`**: tabs 我要咨询 / 我的咨询. Form: 姓名*, 联系方式* (手机或邮箱 format check), 咨询类别 select (本科招生/研究生招生/留学生招生/继续教育/意见建议/其他; preselect via `?cat=`), 咨询内容* textarea ≥10字 counter; submit → Inquiry {status 待回复}; toast 提交成功. 我的咨询: cards list 类别 tag/时间/内容/状态 (待回复 amber / 已回复 green) + reply block when present; empty state. Footer 意见箱/建言献策 link here with `?cat=意见建议`.
- [x] **站内搜索 `/search`**: reads `?q=&scope=`; search box at top (re-searchable); scope tabs 全部/新闻/通知; matches title+summary+body (case-insensitive, includes); results grouped with type chip (新闻 blue / 通知 gold-outline), title highlight `<mark>` gold-bg, date + category, click → detail; result count 「为您找到 N 条相关内容」; logs SearchEntry on each submit (dedupe consecutive same query); empty query state shows recent-search chips from `searchHistory` (click chip re-runs) + hot keywords chips (校庆/招生/参观/论坛) ; no-results state 「未找到与“X”相关的内容」 + suggestions list.
- [x] **收藏 `/favorites`**: two sections 新闻收藏 / 通知收藏 (grouped by targetType); rows title + 收藏时间 + 查看(link) + 取消收藏(danger ghost button, removes + toast); counts in section headers; empty states with 去逛逛 links to `/news` `/notices`.
- [x] **Channel pages** (breadcrumb + left sidebar nav + content; sidebar items highlight active; ALL sidebar/footer/dropdown entries route here):
  - `/about/:section`: 学校简介 (synthetic 800字 history + stats table 建校1896/双一流/23学院/83专业), 学校章程 (excerpt paragraphs), 机构设置 (table 党群/行政/直属 units synthetic), 现任领导 (card grid 姓名+职务 synthetic), 历史沿革 (timeline 1896→2026 synthetic milestones), 学校标识 (logo description + color chips 交大蓝/交大红), 校园风光 (SVG tile gallery).
  - `/schools` grid of 23 school cards (name, EN, founded, disciplines chips) → `/schools/:id` detail (intro, disciplines table, 院长/党委书记 synthetic, contact block, 相关链接 → its news filtered by title keyword).
  - `/education/:section`: 本科生 (专业 list table + 培养模式), 研究生 (学科评估 table + 学位点), 继续教育 (programs), 留学生 (programs + admission notes) — each with a CTA link to `/admission/inquiry`.
  - `/research/:section`: 科技动态 (links into `/news?category=教学科研` style list embed), 平台基地 (table of synthetic labs: 轨道交通控制与安全国家重点实验室 etc.), 成果转化 (process steps + synthetic cases), 学术期刊 (3 journal cards).
  - `/admission/:section`: 本科生招生 (policy summary + CTA 招生咨询 + links to 招生考试 notices), 研究生招生, 就业服务 (stats + synthetic employer list), 创业指导 (program intro).
- [x] **404 page**: blue band 「页面不存在」 + links 首页/新闻网/通知公告.
- [x] **QA pass** (playwright or manual): click EVERY nav item, dropdown link, footer link, 更多, tile, pagination page, tab, star, download, form submit/cancel; verify `/go?sid=test` diff after: create booking, cancel booking, submit inquiry, favorite news, favorite notice, download attachment, search, set notice filters. Fix any dead control.

## Audit Round 1 Fixes (AUDIT.md, 2026-09-21)

- [x] **AUDIT-001 (P1)**: `?sid=` preserved across ALL client-side navigation — new `src/utils/sidParams.js` (`useSidSearchParams` hook + `buildSidUrl`), applied in `NewsList.jsx`, `NoticeList.jsx`, `SearchPage.jsx`, `SearchOverlay.jsx`; plus global `PreserveSid` guard in `App.jsx` that re-appends `?sid=` (history replace) after any navigation that drops it (covers header dropdown / footer / home-tile `<Link to="...?category=X">`). Live-verified: pill click → `/notices?sid=…`, overlay search → `/search?q=…&scope=…&sid=…`, Link tile → `/notices?category=…&sid=…`.
- [x] **AUDIT-002 (P1)**: arriving at `/notices?category=X` from a pure navigation link is now view-local only (merged display filter from URL param) — `noticeFilters` is persisted to server state exclusively on explicit user filter actions (查询 / 重置 / pill clicks). Live-verified: URL-param arrival → `state_diff` empty; pill click → `noticeFilters.category` in diff.
- [x] **AUDIT-003 (P1)**: `toggleFavorite` computes `added` deterministically from the current rendered state before dispatching (no reliance on React eager updater evaluation); toast label always matches the transition the user saw. Live-verified both directions incl. rapid consecutive clicks.
- [x] **AUDIT-007 (P2, cheap)**: header utility date now derived from `new Date()` (`formatToday()` in `Header.jsx`) instead of hardcoded 2026年9月21日.

## P2 — Depth & Polish

- [ ] Carousel: keyboard ←/→, swipe, pause-on-hover, slide caption bar; lazy synthetic SVG scenes (主楼/图书馆/体育馆/银杏大道).
- [ ] 光影交大 lightbox modal (Esc/mask close, prev/next arrows).
- [ ] Header shrink animation 90px→60px with logo fade (already solid on inner pages).
- [ ] Mobile/narrow (≤1200px → 960px column; ≤768px hamburger menu with accordion subnav; single-column home blocks).
- [x] `/en` stub: simple English landing (About/News/Notices links back to zh routes) so top-bar English is not dead.
- [ ] Article 打印 button (window.print with print CSS) + 分享 local dialog (copy-link to clipboard, toast 链接已复制).
- [ ] Notice list sort toggle 按时间/按浏览量.
- [ ] View-count persistence: increment `news[].views`/`notices[].views` once per item per session (adds diff signal; acceptable).
- [ ] Breadcrumb photo band variant on channel pages (blue gradient + faint SVG campus outline).
- [ ] Toast system polish (success green bar / error red bar left edge), focus-visible outlines for a11y.

## Data Seed (implement in createInitialData())

- [x] news: 32 records — ≥5 per NEWS_CATEGORIES; 4 `isTop`; dates 2026-06-01→2026-09-21 (≥8 in last 7 days); bodies 3-5 synthetic paragraphs; 2 with attachments; keyword coverage 校庆≥4/招生≥3/参观≥3/论坛≥2 (see data_model.md §Seed corpus spec).
- [x] notices: 32 records — ≥4 per NOTICE_CATEGORIES; dates 2025-10→2026-09 (≥6 before 2026-01, ≥6 in 2026-08/09); 12 with attachments (mix pdf/doc, 1-3 each); ensure every category has ≥1 item in 2026-08..09 AND ≥1 before 2026-03 (date-range+category combos always non-empty).
- [x] schools: 23 records (real college names, synthetic intros/deans/disciplines).
- [x] bookings: 2 (one 已预约 future 主校区 3人; one 已取消 past) — gives cancel-flow + list realism.
- [x] inquiries: 1 (已回复 with reply text) — shows 我的咨询 reply rendering.
- [x] favorites: 2 (1 news + 1 notice) — 我的收藏 page non-empty at baseline.
- [x] searchHistory: 0, downloads: 0, feedback: 0 (clean diff baseline); noticeFilters baseline 全部/''/''.
- [x] currentUser: 张伟 profile per data_model.md (pre-fills forms).

## Out of Scope

- Authentication / login (public portal; starts as guest with pre-filled `currentUser`; no login UI at all).
- Real subdomain sites (zsw/gs/job/lib/intl…) — replaced by in-app channel pages.
- Real network calls, emails, uploads — downloads are server-generated blobs; forms persist locally.
- Embedding real copyrighted site images (logo/banners) in the app — recreate synthetic equivalents; real files stay in assets/screenshots as reference only.
- English full site (only `/en` stub in P2).
- Do NOT implement gray/disabled placeholder menu items; every visible control must act.
