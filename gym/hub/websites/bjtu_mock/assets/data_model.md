# Data Model — bjtu_mock (北京交通大学官网)

All content is **SYNTHETIC** (invented titles, bodies, names). Dates spread around 2025-10 → 2026-09 (today ≈ 2026-09-21).

State lives in `localStorage` (session-scoped keys) AND syncs to the vite server per `sid` so `GET /go?sid=...` returns `{initial_state, current_state, state_diff}`.
Baseline rule: on first load for a sid, client POSTs `/post?sid=` `{action:'set', state}` (creates initial baseline); every mutation POSTs `{action:'set_current', state}` (see 12306_mock `dataManager.js` pattern).

---

## Top-level state shape (`createInitialData()`)

```js
{
  currentUser: { ... },        // pre-filled visitor profile (no auth)
  news: [ NewsItem x 32 ],
  notices: [ NoticeItem x 32 ],
  schools: [ School x 23 ],
  bookings: [ Booking x 2 ],          // seeded: 1 已预约 (future date), 1 已取消 (past)
  inquiries: [ Inquiry x 1 ],         // seeded: 1 已回复
  favorites: [ Favorite x 2 ],        // seeded: 1 news + 1 notice
  searchHistory: [ SearchEntry x 0 ], // empty at baseline
  downloads: [ DownloadLog x 0 ],     // empty at baseline
  noticeFilters: { category: '全部', dateFrom: '', dateTo: '' },
  feedback: [],                       // 意见箱/建言献策 submissions (footer links)
}
```

`state_diff` shows up as whole-array replacements (e.g. `bookings`, `favorites`, `downloads`, `searchHistory`, `noticeFilters.*`) — arrays diff by value, which is fine and readable.

---

## Entities

### currentUser
```js
{ name: '张伟', idType: '身份证', idNumber: '110101199001011234',
  phone: '13800005678', email: 'zhangwei@example.com', role: '访客' }
```
Used to pre-fill 参观预约 / 咨询 forms (editable by user).

### NewsItem (§News)
```js
{
  id: 'news_001',
  title: '我校轨道交通控制团队在智能调度领域取得重要进展',   // synthetic
  category: '交大要闻',   // one of NEWS_CATEGORIES
  date: '2026-09-18',            // ISO; list shows YYYY-MM-DD / 头条 shows DD + YYYY stack
  source: '新闻网',              // or 学院名 e.g. '交通运输学院'
  author: '通讯员 王小明',        // optional, '' allowed
  summary: '一段 40-80 字的导语……',
  body: ['第一段……', '第二段……', '第三段……'],   // 3-6 paragraphs, each 60-150 字
  views: 1284,
  isTop: true,                   // shows in 首页 交大头条 featured slot
  attachments: []                // usually []; a few news may carry [{...Attachment}]
}
```
NEWS_CATEGORIES = ['交大要闻','校园时讯','教学科研','合作交流','菁菁校园','媒体交大']

### NoticeItem (§Notices)
```js
{
  id: 'notice_001',
  title: '关于2026年国庆节期间校园参观预约开放时间的通知',
  category: '校园管理',          // one of NOTICE_CATEGORIES
  date: '2026-09-15',
  department: '学校办公室',       // 发布单位
  body: ['……', '……'],
  views: 3560,
  attachments: [ Attachment, ... ]   // 0-3 items; ~12 of 32 notices have ≥1
}
```
NOTICE_CATEGORIES = ['招生考试','教务教学','人事招聘','科研管理','校园管理','校庆活动']

### Attachment (§Attachments)
```js
{ id: 'att_001', fileName: '2026年校园参观预约须知.pdf',
  fileType: 'pdf',               // 'pdf' | 'doc'
  sizeKb: 186 }
```
Delivery: `GET /files/:id` (vite middleware) **generates real bytes on the fly**:
- `pdf` → minimal valid PDF 1.4 (catalog/page/content stream with the file name as text), `Content-Type: application/pdf`
- `doc` → Word-compatible HTML document, `Content-Type: application/msword`
Both with `Content-Disposition: attachment; filename="<percent-encoded fileName>"`.
Client also logs a DownloadLog and increments the parent notice's `downloadCount`-ish signal via `downloads[]` (keep notices array stable; do NOT mutate notice objects on download — the downloads log is the diff signal).

### School (§Schools)
```js
{ id: 'sch_01', name: '交通运输学院', en: 'School of Traffic and Transportation',
  url: 'trans',              // symbolic; mock renders /schools/:id
  founded: 1921,
  dean: '李某某',             // synthetic names
  students: 2600,
  intro: '60-120 字 synthetic 学院简介……',
  disciplines: ['交通运输工程（国家双一流学科）','系统科学','物流工程'] }
```
23 schools, names may mirror the real college list (institution names are factual), intros synthetic.

### Booking (§Bookings) — 校园参观预约
```js
{
  id: 'BK202609210001',          // BK + YYYYMMDD + seq
  visitorName: '张伟',
  idType: '身份证',
  idNumber: '110101199001011234',
  phone: '13800005678',
  visitDate: '2026-09-28',       // must be >= today
  timeSlot: '上午',              // '上午' | '下午'
  campus: '主校区',              // '主校区' | '威海校区'
  visitorCount: 3,               // 1..10
  purpose: '校园参观',            // free text optional
  status: '已预约',               // '已预约' | '已取消'
  createdAt: '2026-09-21T10:24:00+08:00'
}
```
Validation: name required; idNumber 18 chars (digits + X) or warning; visitDate required & not past; visitorCount 1-10 integer; phone 11 digits. Errors inline red `#e74155`.
Cancel: confirm modal → status='已取消' (kept in list, gray tag).

### Inquiry (§Inquiries) — 招生咨询 / 意见箱
```js
{
  id: 'IN202609210001',
  name: '张伟', contact: '13800005678',   // phone or email
  category: '本科招生',   // ['本科招生','研究生招生','留学生招生','继续教育','意见建议','其他']
  message: '请问2027年本科招生专业目录何时发布？……',
  submittedAt: '2026-09-19T09:12:00+08:00',
  status: '已回复',          // '待回复' | '已回复'
  reply: '您好，专业目录预计于2027年6月发布，请关注招生资讯网。——招生办'  // '' when 待回复
}
```
Footer 意见箱/建言献策 submit with category '意见建议' into the same array.

### Favorite (§Favorites)
```js
{ id: 'fav_0001', targetType: 'news' | 'notice', targetId: 'news_003',
  title: '……(snapshot for list rendering)', createdAt: '2026-09-20T08:00:00+08:00' }
```
Toggle from: news list row star, notice list row star, detail page 收藏 button. `/favorites` lists both types grouped with jump links + 取消收藏.

### SearchEntry (§Search)
```js
{ id: 'sh_001', keyword: '校庆', scope: '全部',   // '全部'|'新闻'|'通知'
  resultCount: 7, timestamp: '2026-09-21T11:02:00+08:00' }
```
Max 8, newest first; rendered as recent-search chips on `/search` empty state.

### DownloadLog (§Downloads)
```js
{ id: 'dl_001', noticeId: 'notice_004', fileName: '….pdf',
  fileType: 'pdf', timestamp: '2026-09-21T11:05:00+08:00' }
```

### noticeFilters
`{ category: '全部', dateFrom: '', dateTo: '' }` — bound to the 通知公告 filter bar; persisted so /go diff proves filtering happened. Reset button restores baseline.

---

## Relationships
- `Favorite.targetId` → `news[].id` | `notices[].id`
- `Attachment` embedded in `notices[].attachments` / `news[].attachments`
- `DownloadLog.noticeId` → `notices[].id`
- `Booking`, `Inquiry` standalone (owned implicitly by `currentUser`)
- `NewsItem.category` ∈ NEWS_CATEGORIES; `NoticeItem.category` ∈ NOTICE_CATEGORIES

---

## Seed corpus spec (createInitialData)

- **news: 32 items** — ≥5 per category; dates 2026-06-01 → 2026-09-21 (≥8 within last 7 days so homepage looks live); 4 with `isTop:true` for 交大头条 featured slots; bodies 3-5 synthetic paragraphs each (realistic university register: 会议/论坛/签约/表彰/调研/赛事/开放日); 2 items carry attachments.
- **notices: 32 items** — ≥4 per category; dates 2025-10 → 2026-09 (enough spread for date-range filtering exercises, incl. ≥6 older than 2026-01); **12 with attachments** (mix pdf/doc, 1-3 files); include ≥3 招生考试 notices mentioning 附件 (招生简章/报名表), ≥2 人事招聘 (招聘公告 w/ 报名表.doc), ≥2 校园管理 (参观/后勤), ≥2 校庆活动.
- **schools: 23** (real college names OK, synthetic intros/deans).
- **bookings: 2** (BK…0001 已预约 future date 主校区 3人; BK…0002 已取消 past date).
- **inquiries: 1** (已回复, category 本科招生).
- **favorites: 2** (news_002, notice_005).
- **searchHistory: []**, **downloads: []**, **feedback: []**.

Keyword coverage guarantee: seed ≥4 items whose titles contain 「校庆」, ≥3 containing 「招生」, ≥3 containing 「参观」, ≥2 containing 「论坛」 so search tasks have hits; also ensure ≥1 notice in every category within 2026-08..2026-09 and ≥1 per category before 2026-03 so date-range + category combos always yield results.

---

## /go diff expectations (verifier cheat-sheet)

| User action | state_diff keys |
|---|---|
| 提交参观预约 | `bookings` (array grows) |
| 取消预约 | `bookings` (status flip) |
| 提交招生咨询/意见 | `inquiries` (or `feedback`) |
| 收藏/取消收藏 | `favorites` |
| 下载附件 | `downloads` |
| 站内搜索 | `searchHistory` |
| 通知筛选 | `noticeFilters.category` / `.dateFrom` / `.dateTo` |
