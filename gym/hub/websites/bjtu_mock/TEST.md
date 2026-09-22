# 北京交通大学官网 Mock (bjtu_mock) — Test Report

> Round: 2 (final)
> Date: 2026-09-22
> Server: http://localhost:5188
> Tested by: playwright agent

## Summary

| Metric | Count |
|--------|-------|
| Routes tested | 32 (home, /news+detail, /notices+detail, /visit, /admission/inquiry, /search, /favorites, 7×/about, /schools+detail, 4×/education, 4×/research, 4×/admission, /go, /en, 404 + dropdown/link sweeps) |
| Elements tested | 383 checks (G1 95 · G2 43 · G3 31 · G4 28 · G5 19 · G6 27 · G7 32 · G8 57 · G9-R2 33 · G10 18) |
| ✅ Passed | 381 |
| ❌ Failed | 1 (BUG-001, found Round 1 → fixed + FIXED-VERIFIED Round 2) |
| ⚠️ Skipped (out of scope) | 1 (header 90→60px shrink = TODO P2 `[ ]`; observed height 170px, noted in Group 10, not a bug) |

**Bug counts: P0 = 0 · P1-functional = 0 · P1-VISUAL = 0 · P2 = 0 open** (Round 3 final; BUG-001/BUG-002 fixed+verified, AUDIT-011 FIXED-VERIFIED, no new bugs)

*(This file is written incrementally; sections appended as each page group completes.)*

---

## Group 1 — Homepage / Header / Footer / Dropdowns (DONE)

**Result: 94 checks passed, 1 failed (BUG-001).**

✅ Passing:
- Home renders; 0 console errors on `/`, all list pages visited in dropdown sweep except `/about/lingdao` (BUG-001)
- Carousel: 4 slides, left/right arrows advance, pager numbers 1–4 clickable (active turns gold), banner-track transform follows
- No dead links (`href="#"` / `javascript:`) anywhere on home
- Header utility pills 校友/访客及考生/教职工/学生/English → `/about/jianjie`, `/visit`, `/education/jixu`, `/education/benke`, `/en` — all correct, `?sid=` kept on every one
- Search overlay: opens on orange button, closes on Esc AND mask click; submit → `/search?q=校庆&sid=…`; scope radios honored (`&scope=新闻`)
- 8 nav items, all 7 dropdown bands appear on hover; **55 unique dropdown links all render real pages** (incl. all 23 school details, all channel sections, category-filtered lists)
- 4 更多 links (进入新闻网→/news, 教学科研→/news?category=教学科研, 菁菁校园→…, 通知公告→/notices) all navigate + keep sid
- 8 专题网站 tiles all route correctly (人才招聘→/notices?category=人事招聘 etc.) — sid re-appended by PreserveSid within ~500ms (transient drop then history-replace; final URL always carries sid)
- 4 quick-strip links (校园参观预约/招生咨询/站内搜索/我的收藏) → /visit, /admission/inquiry, /search, /favorites
- Home list rows (头条/notice/photo-strip) all link to real detail/list pages
- 9 footer links all route with correct params (意见箱 & 建言献策 → /admission/inquiry?cat=意见建议; 招生资讯网 → /admission → redirect /admission/bkzs ✅); footer contact + ICP lines present
- Logo → home; BackToTop appears after scroll & scrolls to top; header transparent on home → solid on scroll / solid on inner pages

### BUG-001 · P0 · React duplicate-key console.error on /about/lingdao

| Field | Value |
|-------|-------|
| Route | `/about/lingdao` (现任领导) |
| Element | leader card list |
| Action | Load page (reproduces on every render, ×3 observed) |
| Expected | 0 console errors on every page |
| Actual | `console.error: Encountered two children with the same key, '副校长'. …` |
| Console errors | React unique-key warning |
| Fix hint | `src/pages/About.jsx:100` uses `key={role}` but LEADERS data (line 34) has FOUR entries with role 副校长 → duplicate keys. Use `key={role + name}` or index. Other /about sections are clean. |
| ✅ FIXED (Round 2 verification) | Dev changed key to `` key={`${role}-${name}`} `` (About.jsx:100). Browser reload of `/about/lingdao?sid=pwFINAL2` (2026-09-22): **0 console errors**, all **8 leader cards** render incl. all **4 副校长** cards. FIXED-VERIFIED. |

---

## Group 2 — /news list + news detail (DONE)

**Result: 43 checks passed, 0 failed.** (One initial ❌ was a too-strict test expectation: 相关新闻 for `news_013` shows 4 links because its category 教学科研 has only 4 siblings — `slice(0,5)` behavior is correct. Verified via `/state`.)

✅ Passing:
- 7 category tabs (全部+6), each sets `?category=`, active styling, count line updates (6/6/5/5/5/5, 共32条); 全部 clears the param; `?sid=` survives every tab click
- Pagination: 10 rows/page; 下页/尾页/首页/上页/number buttons all work; 下页/尾页 disabled on last, 首页/上页 disabled on first; 共 N 条　M/K shown
- Row ☆ star: revealed on hover, toggles ☆→★→☆ with toasts 已收藏/已取消收藏
- Row click → `/news/:id`; breadcrumb band + working 新闻网 crumb link
- Detail: title, meta 时间/来源/浏览量, ≥3 body paragraphs, 相关新闻 list, prev/next navigate, newest article shows 「没有了」 at the end
- `news_013` 附件下载区 present; link `href=/files/att_n01?sid=…`; **real download event fired, saved bytes start `%PDF`, filename 智慧轨道交通前沿论坛日程安排.pdf** ✅
- Detail 收藏 button toggles with 已收藏/收藏 label
- Unknown id `/news/no_such_id` → 404 content; bogus category → 暂无相关新闻 empty state with working 返回 link
- 0 console errors across all /news + detail pages

---

## Group 3 — /notices list + notice detail + downloads (DONE)

**Result: 31 checks passed, 0 failed.** (One initial ❌ was a wrong test expectation: notice detail uses 上一条/下一条 labels — verified present and working, incl. 没有了 at the newest end.)

✅ Passing:
- 7 category pills; pill click filters list (招生考试 → 共6条), active styling, `?sid=` survives, url category param cleared (filter lives in state)
- Date-range: fill 日期起/止 + 查询 → 共12条, ALL visible rows within 2026-08-01..2026-09-30; 重置 → 共32条 + date inputs cleared; pill+date combo works (校园管理 × 2025-01..2026-03 → 共2条)
- Pagination 下页/尾页 (disabled at end) works; 📎 clip icons on rows with attachments (5 on page 1)
- Row star toggles ★/☆
- Notice detail (`notice_002`): meta 时间/发布单位/浏览量; 附件下载区 with `[PDF] 文件名 (88KB) 下载` layout; href `/files/att_…?sid=…`
- **Download click → real file saved: `%PDF` magic, 1511 bytes, filename 硕士研究生预报名流程说明.pdf matches on-page name** ✅
- Detail 收藏 button toggles 已收藏/收藏; 相关通知 list; unknown id → 404; 0 console errors

**curl /files evidence (sid=pwC):**
```
GET /files/att_001?sid=pwC → 200, Content-Type: application/pdf,
  Content-Disposition: attachment; filename="2026%E5%B9%B4….pdf"; filename*=UTF-8''…, Content-Length: 1511, bytes start "%PDF-1.4"
GET /files/att_002?sid=pwC → 200, Content-Type: application/msword, bytes = Word-compatible HTML (xmlns:w="urn:schemas-microsoft-com:office:word")
GET /files/att_zzz?sid=pwC → 404 {"error":"attachment not found: att_zzz"}
```

### BUG-002 · P2 · HEAD /files/:id returns SPA index.html instead of file headers

| Field | Value |
|-------|-------|
| Route | `/files/:attachmentId` |
| Action | `curl -I` (HEAD request) |
| Expected | Same headers as GET (or 405) |
| Actual | `Content-Type: text/html` (middleware only matches `req.method === 'GET'`, HEAD falls through to SPA) |
| Impact | Cosmetic — browsers download via GET, which is correct. Only affects HEAD-based probes. |
| Fix hint | `vite.config.js:223` — accept `GET|HEAD` for /files (optionally also /state, /go). |
| ✅ FIXED (Round 2 verification) | Middleware now matches `GET|HEAD` (vite.config.js:223). `curl -I "http://localhost:5188/files/att_001?sid=x"` → `200`, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="2026%E5%B9%B4….pdf"`, `Content-Length: 1511` — real file headers, NOT text/html. FIXED-VERIFIED. |

---

## Group 4 — /visit 参观预约 (DONE)

**Result: 28 checks passed, 0 failed.**

✅ Passing:
- 2 tabs (参观预约/我的预约) switch; 参观须知 panel renders (开放时间/携带证件/团体提前3日 bullets)
- Form pre-filled from currentUser (张伟)
- Validation: missing date → 请填写/请选择参观日期 + error toast 请检查表单填写内容; 证件号 `12345` → 18位 error; 电话 `99999` → 11位手机号 error; past date (2020-01-01) → date error; 人数 99 → 1-10 error; invalid inputs get red `.input-error` class
- Valid submit (威海校区/下午/4人/date=tomorrow) → toast 预约成功, **auto-switch to 我的预约**, table 3 rows (2 seed + new), new row shows 已预约 + all field values
- Cancel flow: 取消预约 → confirm modal (title 取消预约, shows BK id) → closes on Esc ✓ closes on mask ✓ → 确认取消 → toast 预约已取消, status tag → 已取消, cancel button removed; old 已取消 seed row has no action
- 清空重填 resets all fields; sid preserved; 0 console errors

---

## Group 5 — /admission/inquiry 招生咨询 (DONE)

**Result: 19 checks passed, 0 failed.**

✅ Passing:
- `?cat=意见建议` preselects the 咨询类别 select; sid + cat both kept in URL
- Validation: empty/<10-char message → 咨询内容不少于10字 error; char counter live-updates (「5 字」); empty name → error; contact `abc` → 手机号或邮箱 format error; email accepted
- Submit → toast 提交成功, auto-switch 我的咨询, new card at top with 意见建议 gold tag + 待回复 status + message text; baseline 已回复 card renders 回复： block
- message cleared post-submit; 清空重填 clears fields
- **Server state verified**: `/state?sid=pwE` → inquiries=2 (newest 待回复, category 意见建议) AND **feedback[] grew by 1** (意见建议 side-effect per SCHEMA) ✅
- 0 console errors

---

## Group 6 — /search 站内搜索 (DONE)

**Result: 27 checks passed, 0 failed.** (fresh sid `pwF`)

✅ Passing:
- Empty-query state: 最近搜索 shows 暂无搜索记录 (baseline `searchHistory=[]` verified via `/state`), 热门搜索 chips exactly 校庆/招生/参观/论坛
- Hot chip click → `/search?q=校庆&scope=全部&sid=pwF`; count line 为您找到 **9** 条 = seed truth (news 4 + notices 5, recomputed from `/state` with same title+summary+body matching)
- `<mark>` highlight: 15 marks on page, every mark text == query keyword
- Type chips per row (新闻 blue / 通知 gold) counts match seed exactly (4/5)
- Scope tabs: 新闻 → `scope=新闻` + count 4 + all chips 新闻; 通知 → count 5 + all chips 通知; 全部 → 9 again; active tab styling follows
- Result row click → `/news/news_001?sid=pwF` (href matches seeded link)
- Search-bar re-search (招生) → count 9 = seed (news 4 + notice 5)
- Direct URL `/search?q=论坛&scope=新闻` honored: count 2 = news-only matches; input pre-filled 论坛
- No-results state: `q=不存在zzz9` → 「未找到与"不存在zzz9"相关的内容」 + 建议尝试 chips (校庆/招生/参观/论坛); suggestion chip click re-runs (参观 → 7 = seed)
- Header overlay submit (q=参观, scope radio 通知) → `/search?q=参观&scope=通知&sid=pwF`, count 2 = notices-only 参观 matches
- History chips persisted across navigation: 8 chips newest-first exactly mirror `state.searchHistory` (`sh_*` ids, keyword+scope+resultCount fields, capped at 8); chip click re-runs that keyword+scope
- Dedupe: consecutive same (keyword, scope) not duplicated; same keyword with different scope logs separately (matches implementation — clicking 参观 twice at different scopes keeps both, correct per `logSearch` key)
- `?sid=` preserved on every URL (chip clicks, tabs, overlay submit, result navigation)
- **0 console errors** across all /search interactions

---

## Group 7 — /favorites 我的收藏 (DONE)

**Result: 32 checks passed, 0 failed.** (fresh sids `pwG` + `pwG2`; one initial ❌ was a test artifact — notice list row inner_text carries the 📎 icon which the favorites row title doesn't; re-verified clean on `pwG2`: starred notice title appears verbatim in 通知收藏)

✅ Passing:
- Baseline on fresh sid: 新闻收藏 1 row + 通知收藏 1 row (seeded `fav_0001`=news_002, `fav_0002`=notice_005), headers 「1 条收藏」, rows show title + 收藏时间 `2026-09-20 08:00` + 查看 + 取消收藏
- 查看 link → `/news/news_002?sid=pwG` (title link href identical)
- Star from /news list (first non-favorited row = news_013): hover reveals ☆ → click → toast 已收藏, ☆→★ + `.active`; **state sync**: that item's detail page shows 已收藏 label
- Favorite from detail (news_001): starts 收藏 → click → toast + 已收藏
- Star from /notices list (notice_002): toast 已收藏; title appears in 通知收藏 (verified on pwG2)
- Favorites page lists BOTH types: 新闻收藏 3 rows / 通知收藏 2 rows, headers 「3 条收藏」「2 条收藏」, all titles present
- **Survives reload** (server state): after F5 still 3+2; `/state?sid=pwG` favorites = 5 ids `[news_002, notice_005, news_013, news_001, notice_002]` — 3 news + 2 notice
- Remove from favorites page: 取消收藏 on news_002 row → toast 已取消收藏, row gone, 新闻收藏 → 2, server favorites → 4
- Remove all news favs → empty state 「暂无新闻收藏」 + 去逛逛 (href `/news`) navigates with sid; /news list then shows 0 active stars (reverse state sync)
- Remove from notice section (pwG2) → row removed, seed notice_005 remains
- `?sid=` preserved throughout; **0 console errors**

---

## Group 8 — Channel pages + 404 + /en (DONE)

**Result: 57 checks passed, 0 failed.** (fresh sid `pwH`; 5 initial ❌ were too-strict test expectations, re-verified correct: education sidebar labels are 本科生教育/研究生教育/留学生教育 — active highlight exact ✓; /research/zhuanhua+qikan bodies are 146/145 dense chars — full content confirmed: zhuanhua = 5 process steps 成果披露→收益分配 + 3 典型转化案例 cards; qikan = 3 journal cards 交通运输系统工程技术/北京交通大学学报/物流技术与应用研究 with 季刊/双月刊 tags + 查看征稿 links)

✅ Passing:
- `/about` → redirect `/about/jianjie?sid=pwH` (sid kept)
- All 7 /about sections (jianjie/zhangcheng/jigou/lingdao/lishi/biaoshi/fengguang): channel-title correct, exactly 1 sidebar item active per section, content markers present (jianjie 1896 stats · jigou 党群/行政/直属 · lishi timeline 1896→2026 · biaoshi 交大蓝+交大红 chips · fengguang gallery), no dead links, **0 console errors each**
- Sidebar = 7 items; `/about/bogus` → styled 404
- **/about/lingdao — BUG-001 REPRODUCED**: console error `Encountered two children with the same key … 副校长`; page still renders all 8 leader cards (4× 副校长, names 王知行/李交通/赵明德/钱清风/孙轨通/周信号/吴运筹/郑育才 in order) and NO other errors — nothing else broken
- `/schools`: grid = 23 unique `a.school-card` links + count line 「共 23 个学院（部）」; 0 errors, no dead links
- School detail `/schools/sch_03` (计算机与信息技术学院): EN name, intro, disciplines table, 院长/党委书记/创建年份/在校生 info cards, 联系电话 block, 相关新闻 link → `/news/news_013?sid=pwH`, 返回院系列表; 0 errors; `/schools/bogus` → 404
- `/education` → redirect `/education/benke?sid=`; 4 sections render (benke/yanjiusheng/jixu/liuxue), each with CTA link → `/admission/inquiry`, sidebar active correct, tables/program content, no dead links, 0 errors
- `/research` → redirect `/research/dongtai?sid=`; 4 sections render (dongtai/pingtai/zhuanhua/qikan), sidebar active correct, pingtai contains 轨道交通控制与安全 lab table, 0 errors
- `/admission` → redirect `/admission/bkzs?sid=`; 4 sections render (bkzs/yjszs/jiuye/chuangye), sidebar active, bkzs has 招生咨询 CTA + 3 notice links, 0 errors
- 404 (`/bogus-page-xyz-999`): band 「页面不存在」+ 404 explanation + links 首页/新闻网/通知公告; 新闻网 click → `/news?sid=pwH`
- `/en`: stub h1 "Beijing Jiaotong University" + exactly 5 links (`/`, `/news`, `/notices`, `/about/jianjie`, `/admission/bkzs`); News click → `/news?sid=`; 0 errors
- **Link sweep: all 59 unique internal hrefs collected across every channel page visited resolve to real pages (zero 404s)**
- Only console error in entire group = known BUG-001 on /about/lingdao

---

## Group 9 (Round 2) — Bug-fix verification + /go state pipeline + session isolation (DONE)

**Result: 33 checks passed, 0 failed.** (fresh sid `pwFINAL2`; isolation sid `pwISO2` curl-only)

### 9a. Bug-fix verification
- **BUG-001 (P0) FIXED-VERIFIED**: `/about/lingdao?sid=pwFINAL2` loaded in browser → **0 console errors** (was: duplicate-key `副校长` error ×3); all **8 leader cards** render, incl. all **4 副校长** cards. Source fix confirmed: `key={`${role}-${name}`}` (About.jsx:100). Marked in BUG-001 table above.
- **BUG-002 (P2) FIXED-VERIFIED**: `curl -I "http://localhost:5188/files/att_001?sid=x"` →
  ```
  HTTP/1.1 200 OK
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="2026%E5%B9%B4%E7%A0%94%E7%A9%B6%E7%94%9F%E6%8B%9B%E7%94%9F%E7%AE%80%E7%AB%A0.pdf"; filename*=UTF-8''…
  Content-Length: 1511
  Cache-Control: no-cache
  ```
  Real file headers, not `text/html`. Marked in BUG-002 table above.

### 9b. Full interaction pipeline in browser (sid=pwFINAL2, 11 steps)
1. Booking created via /visit (威海校区/下午/4人/2026-09-23) → toast 预约成功 + auto-switch 我的预约, row `BK202609220003 … 已预约`
2. Cancelled via 我的预约 → confirm modal → toast 预约已取消, row status → 已取消, action column → —
3. Inquiry submitted via /admission/inquiry (研究生招生, 13900139000, ≥10-char message) → toast 提交成功 + 我的咨询 card 待回复
4. News favorited from /news list: `news_013` → toast 已收藏 ★
5. Notice favorited from /notices list: `notice_002` → toast 已收藏 ★
6. Search 校庆 executed → 为您找到 **9** 条 (seed truth)
7. Notice pill 招生考试 clicked → active + list filtered 共 **6** 条
8. Attachment downloaded from /notices/notice_002 → real download event, `硕士研究生预报名流程说明.pdf`, bytes start `%PDF-`
9. SPA `/go` page (loaded via sessionStorage sid): `sid：pwFINAL2` shown, **7 tracked-key chips** (bookings/inquiries/favorites/downloads/searchHistory/noticeFilters/feedback), `<pre>` = valid JSON with initial_state+current_state+state_diff, diff-line lists all 6 changed keys, **copy button → 已复制**, **0 console errors**; server diff unchanged after visit (no baseline reset). Screenshot: `assets/test_screenshots/mock_go_page_r2.png`

### 9c. curl /go?sid=pwFINAL2 — state_diff evidence (trimmed)
```
$ curl -s "http://localhost:5188/go?sid=pwFINAL2"
state_diff keys == EXACTLY: ["bookings","downloads","favorites","inquiries","noticeFilters.category","searchHistory"]

bookings.old = [BK202609210001 已预约, BK202609100002 已取消]        (2 seed rows intact)
bookings.new = […2 seeds…, {"id":"BK202609220003","status":"已取消","visitDate":"2026-09-23",
                "timeSlot":"下午","campus":"威海校区","visitorCount":4,
                "purpose":"Round2状态管线验证参观","createdAt":"2026-09-22T02:24:57+08:00"}]   ← created+cancelled
inquiries.new += {"id":"IN202609220002","category":"研究生招生","status":"待回复",
                  "contact":"13900139000","message":"Round2验证：请问研究生招生复试…"}
favorites.old = [fav_0001, fav_0002]  →  favorites.new += (news, news_013) + (notice, notice_002)  ← exactly +2, ids match UI clicks
searchHistory.new = [{"id":"sh_099750","keyword":"校庆","scope":"全部","resultCount":9}]
downloads.new = [{"id":"dl_001","noticeId":"notice_002","fileName":"硕士研究生预报名流程说明.pdf","fileType":"pdf"}]
noticeFilters.category = {"old":"全部","new":"招生考试"}
```
All 6 required diff groups present and exactly match the UI actions. ✅

### 9d. Session isolation (sid=pwISO2, never loaded a page)
```
$ curl -s "http://localhost:5188/go?sid=pwISO2"
{"initial_state": null, "current_state": null, "state_diff": {}}
$ curl -s "http://localhost:5188/state?sid=pwISO2"
{}
```
pwFINAL2's mutations are invisible to pwISO2 → per-sid isolation confirmed. ✅

**Notes:** (1) `/go?sid=X` loaded directly as a URL returns the JSON API response by middleware design (`Accept: text/html` falls through to the SPA page only without `?sid=`; Go.jsx reads sid from sessionStorage) — the SPA inspector renders correctly when reached that way, verified in 9b step 9. Not a bug. (2) The SPA page visit used a pre-seeded localStorage context (add_init_script) so the client treated it as a refresh and did NOT re-POST the baseline — server diff verified unchanged afterwards.

---

## Group 10 (Round 2) — Visual token check vs DESIGN.md (DONE)

**Result: 17/18 computed-style checks passed; 0 visual bugs.** (sid `pwA`; screenshots in `assets/test_screenshots/*_r2.png`)

| Token (DESIGN.md) | Measured (computed style) | Verdict |
|---|---|---|
| Header 交大蓝 `#005bac` (scrolled/inner) | `.site-header.solid` bg = `rgb(0, 91, 172)` + shadow `0 2px 6px rgba(0,0,0,.4)` | ✅ |
| Nav hover gold top bar `4px #eea200` | `.nav-link::before` on hover = `rgb(238, 162, 0)`, height `4px` (also visible on active 通知公告 in list screenshot) | ✅ |
| Content column `1200px` | `.wrap` = `1200px` | ✅ |
| Banner carousel `≈2480:801 (3.1:1)`, border-bottom `6px #005bac`, arrows `40×40`, pager active gold | `1440×466` ratio **3.09**; border `6px rgb(0,91,172)`; arrows `[40,40]`; active pager color `rgb(238,162,0)` | ✅ |
| Notice date block `52×49` green numerals | `52×49`; strong `18px/700 Arial rgb(75,165,9)`, i `12px italic rgb(75,165,9)`, border-right `rgb(192,201,210)` | ✅ |
| Footer `#065eb1` | gradient starts `rgb(6, 94, 177)` (`linear-gradient(140deg, #065eb1, #04488a)`), padding-top 45px | ✅ |
| Pagination active `#005bac`/white | `rgb(0,91,172)` / `rgb(255,255,255)` | ✅ |
| Article title 22px/700; body 16px lh2 indent 2em; 附件 box dashed `#f7faff` | `22px/700`; `16px`, lh `32px`, indent `32px`; `dashed rgb(247,250,255)` | ✅ |
| Primary button `#005bac` white radius 3px | `rgb(0,91,172)/rgb(255,255,255)/3px` | ✅ |
| Header scrolled height ≈60px | **170px** — height shrink is TODO.md P2 item "Header shrink animation 90px→60px" = `[ ]` not started → out of scope, NOT a bug (solid color + shadow per P0 spec are correct) | ⚠️ out of scope |

Screenshots captured: `mock_home_top_r2.png`, `mock_home_scrolled_header_r2.png`, `mock_home_nav_hover_r2.png`, `mock_home_notices_r2.png`, `mock_footer_r2.png`, `mock_notices_list_r2.png`, `mock_notice_detail_r2.png`, `mock_visit_r2.png`, `mock_go_page_r2.png`.
Visual sanity read of home top + notices list: layout (fixed blue header / utility pills / breadcrumb band / filter bar / list rows / pagination), colors (交大蓝 chrome, gold active signals, green date numerals), and typography all match DESIGN.md and the reference captures; no mismatched palette or broken structure observed.

**0 visual bugs (no new BUG-00N entries).**

---

## Round History

### Round 1 → Round 2 (2026-09-22)
- BUG-001 (P0 · duplicate React key on /about/lingdao): ✅ FIXED-VERIFIED — 0 console errors, 8 leader cards render
- BUG-002 (P2 · HEAD /files returned text/html): ✅ FIXED-VERIFIED — `curl -I` returns `application/pdf` + attachment headers
- Regressions: none — Round 2 re-ran the full state pipeline (booking create+cancel, inquiry, 2 favorites, search, pill filter, download) on fresh sid `pwFINAL2`; `/go` diff exactly matches the 6 action groups; `/go?sid=pwISO2` + `/state?sid=pwISO2` confirm isolation; SPA `/go` inspector renders with copy button + 7 chips, 0 console errors
- New bugs found in Round 2: **none** (functional or visual)

**Remaining open items:** none in scope. Out-of-scope observations: header height shrink 90→60px (TODO P2, `[ ]`) — header shows solid `#005bac` + shadow but stays at full 170px height when scrolled; per instructions, unchecked P2 items are not reported as bugs.






---

## Round 3 — post-fix regression (2026-09-22, sid verB)

One batched headless script, fresh context: booking create → cancel via 我的预约 (已取消 rendered) · inquiry submit · news star + notice-detail favorite · search 校庆 · notices pill 招生考试 · attachment download (bytes start `%PDF`) · F5 ×1 on /notices (state intact). `/go?sid=verB` diff = exactly the 6 expected key groups (bookings 已取消 / inquiries +1 / favorites +2 / searchHistory 校庆 / downloads +1 / noticeFilters.category 招生考试). `/go?sid=verZ` → null/null/{} (isolation). Console errors: 0. AUDIT-011 repro on sid verA: fresh-context open of pre-mutated state → 0 `set` POSTs, 1 GET /state, diff byte-identical before/after — **FIXED-VERIFIED**.

**Round 3 verdict: 15/15 + 6/6 checks PASS · 0 new bugs · P0 = 0 · P1-functional = 0 · P1-VISUAL = 0 · P2 = 0 open.**

**Round 3 Task 3:** `/go?sid=verB` byte-identical (canonical JSON) before/after opening the `/go` SPA page (0 console errors) — page is read-only. `npm run build` ✅ (vite, 100ms, js 379.21 kB / gzip 120.12 kB, no warnings). Cleanup: verA/verB state files removed; server left running on :5188.
