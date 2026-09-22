# BJTU Mock (北京交通大学官网) — Audit Report

> Round: 1
> Date: 2026-09-21
> Audited by: audit agent

## Summary

| Category | Issues |
|----------|--------|
| Dead handlers / stubs | 0 |
| Missing state tracking | 0 |
| Data pipeline gaps | 0 |
| State-diff noise / coherence | 3 (P1) |
| Minor code quality / polish | 7 (P2) |
| **Total** | **10** |

**P0 = 0 · P1 = 3 · P2 = 7.** `npm run build` passes (57 modules, no warnings). No `onClick={() => {}}`, no `alert()`, no `console.log`, no `href="#"`, no `javascript:void(0)`, no TODO/FIXME/placeholder strings anywhere in `src/`. Every nav item, dropdown link (all 8 bands incl. 23-school grid), footer link, home tile, 更多 link, pagination control, tab, star, download, and both forms is wired to a real route or a real state mutation. All TODO.md `[x]` items verified present, including the `[x]` P2 `/en` stub.

## Live Pipeline Verification (evidence)

Dev server started on port 5188 (`npm run dev`), all requests via curl/node fetch:

1. `GET /go?sid=audit1` (fresh) → `{initial_state:null, current_state:null, state_diff:{}}` ✅
2. `POST /post?sid=audit1 {action:'set', state:createInitialData()}` → `{ok:true}`; `/go` after: `initial === current`, `state_diff = {}` ✅
3. `GET /state?sid=audit1` → all 11 keys (`currentUser, news, notices, schools, bookings, inquiries, favorites, searchHistory, downloads, feedback, noticeFilters`) ✅
4. `POST {action:'set_current'}` with mutated state → `GET /go?sid=audit1` `state_diff` keys: `bookings | inquiries | favorites | searchHistory | downloads | feedback | noticeFilters.category | noticeFilters.dateFrom | noticeFilters.dateTo` — every tracked mutation visible ✅
5. **sid isolation**: `GET /go?sid=audit2` → `initial:null, current:null, diff:{}`; `/state?sid=audit2` → `{}`; `.mock-states/` contained only `audit1.json` ✅
6. `POST {action:'reset'}` → `state_diff` back to 0 keys ✅
7. `GET /files/att_013?sid=audit1` → 200, `application/pdf`, magic bytes `%PDF-1.4`, `Content-Disposition: attachment; filename*=UTF-8''…` ✅; `att_002` → `application/msword` HTML ✅; news attachment `att_n01` → 200 ✅; unknown id → 404 JSON ✅
8. **Real UI round-trip (Playwright)**: home renders with 0 console errors; `/visit?sid=auditui` form submit → toast 预约成功, tab switch 我的预约, 3 rows; server `/go?sid=auditui` diff: `bookings` old 2 → new 3 with full record; cancel via confirm modal → server diff shows `status:'已取消'` ✅

## P0 — Dead/Broken Code

None found.

## P1 — Coherence / State-Signal Issues

### AUDIT-001 · `?sid=` wiped from URL by in-page interactions
- **Files**: `src/pages/NewsList.jsx:28-29` (`setSearchParams({})` / `{category}`), `src/pages/NoticeList.jsx:56,65,72` (`setSearchParams({})` in apply/reset/pickCat), `src/pages/SearchPage.jsx:54,78` (`setSearchParams({q,scope})`), `src/components/SearchOverlay.jsx:21` (`navigate('/search?q=…')`)
- **Issue**: these calls replace the whole query string, dropping `?sid=`. Same-tab sessions survive via `sessionStorage` fallback, but the visible URL no longer round-trips the session — copying/reopening the URL (or any new-tab flow) silently falls back to the `default` session and writes to the wrong state file. Contradicts the dev.md "preserve ?sid=" intent (RedirectWithQuery does this correctly for index redirects).
- **Fix**: merge `sid` back in, e.g. `setSearchParams(prev => { prev.set('category', c); return prev; })` and append `&sid=` in SearchOverlay's navigate when `getSessionId()` is non-null.

### AUDIT-002 · Pure navigation mutates `noticeFilters` (state_diff noise)
- **File**: `src/pages/NoticeList.jsx:23-31`
- **Issue**: arriving at `/notices?category=X` from a footer/dropdown/home tile link calls `setNoticeFilters({category:X})` → POSTs `set_current` → `noticeFilters.category` shows up in `/go` `state_diff` even though the agent only navigated. An RL verifier checking "did the agent set the 招生考试 filter?" gets a false positive from clicking any nav link that carries `?category=`.
- **Fix**: treat `?category=` as view-local state (useState initialized from the URL param) and write `noticeFilters` only on explicit 查询/重置/pill clicks — or keep behavior but document it in SCHEMA.md as an intentional signal (currently documented in the Observable State Changes table as a known source).

### AUDIT-003 · `toggleFavorite` toast label relies on eager state evaluation
- **Files**: `src/context/AppContext.jsx:94-112`, `src/components/FavStar.jsx:16-17`
- **Issue**: `added` is mutated inside the `setState` updater and read synchronously after. This is only correct when React eagerly evaluates the updater (empty update queue). With a pending update (fast double-click, concurrent render batching) the updater is deferred → `added` stays `false` → toast says 已取消收藏 when the item was actually added. State itself is always correct; only the feedback label can lie.
- **Fix**: compute `exists` from the current `state` (already in scope via `isFavorited`) before dispatching, and return that.

## P2 — Minor Issues

### AUDIT-004 · Side effect (`saveState`) inside setState updater
- **File**: `src/context/AppContext.jsx:36-42` — `updateState` calls `saveState` (localStorage write + fetch POST) inside the updater function. Under StrictMode the updater is double-invoked → every mutation fires 2 identical `set_current` POSTs (idempotent, but violates React updater purity and doubles traffic). Move `saveState` into a `useEffect` on `state` or compute next state outside the updater.

### AUDIT-005 · Hard browser navigation to `/go?sid=X` returns raw JSON, not the styled inspector
- **File**: `vite.config.js:207-219` — middleware falls through to the SPA only when `sid` is absent. Typing `http://localhost:5188/go?sid=audit1` in the address bar shows bare JSON instead of `Go.jsx` (copy button + tracked-keys chips). Programmatic access is correct as-is; consider falling through when `Accept: text/html` AND `Sec-Fetch-Mode: navigate` regardless of sid.

### AUDIT-006 · `downloads[].noticeId` also stores news ids
- **File**: `src/context/AppContext.jsx:144` — downloading an attachment from a news article logs it under `noticeId`. Field name is misleading but schema-stable; do NOT rename (backward compat). Documented in SCHEMA.md.

### AUDIT-007 · Hardcoded header date
- **File**: `src/components/Header.jsx:83` — `2026年9月21日　星期一` is static. Should derive from `new Date()` (matches seed-data "today" convention while staying correct if the clock moves).

### AUDIT-008 · `addFeedback` exported but never invoked from UI
- **File**: `src/context/AppContext.jsx:157-162` — `feedback` is only written through `addInquiry`'s 意见建议 branch (which is correct per TODO: footer 意见箱 routes to `/admission/inquiry?cat=意见建议`). `addFeedback` is dead code; remove or keep deliberately.

### AUDIT-009 · Post-`reset` staleness with reused sid + warm localStorage
- Pattern-inherent (same as 12306_mock): after `POST {action:'reset'}`, a browser tab that already has `bjtu_mock_initial_state_<sid>` in localStorage keeps its local copy and will re-push it on the next `set_current`. Mitigation is operational: **use a fresh sid per episode** (documented in SCHEMA.md). No code change required unless harness reuse of sids is planned.

### AUDIT-010 · Minor CSS deviations from DESIGN.md
- `src/index.css:66-69` pill: `font-size:13px; padding:0 12px` vs spec `14px; padding:0 10px`; dropdown band `rgba(204,225,250,.92)` vs spec `#cce1fa @80%`; banner slides fixed `460px` height instead of the 2480:801 (≈3.1:1) aspect. Core tokens all match: `--bjtu-blue:#005bac`, `--navy:#004480`, `--nav-overlay:#004e91`, `--pill:#004d92`, `--footer:#065eb1`, `--gold:#eea200`, `--amber:#f6ad3c`, `--green:#4ba509`, `--sky:#00a2e6`, `--cyan:#00a4db`, `--subnav:#cce1fa`, `--red:#e74155`, back-to-top `50×50 #2378c3 bottom:40 right:20`, shadows per §6. Non-token colors are justified (go-page dark theme, gradients, hover shades).

## SANDBOX_COMPLETENESS_GUIDE.md Acceptance Check

| Criterion | Status |
|-----------|--------|
| First screen matches real product entry (university portal home w/ carousel + 头条 + lists) | ✅ |
| No clickable placeholders | ✅ (grep + code read: none) |
| No gray disabled graveyard items | ✅ (only state-dependent pagination `disabled`) |
| Core create/cancel/search/filter flows work | ✅ (live-verified booking create/cancel, search, notice filters) |
| File download surfaces work | ✅ (real generated PDF/DOC bytes, correct disposition; live-verified) |
| Dialogs open/close (mouse + Esc) | ✅ Modal + SearchOverlay: mask click + Escape handlers present |
| Mutations persist & appear in `/go` diff for active sid | ✅ (live evidence above) |
| `npm run build` passes | ✅ |
| Schema backward compat | ✅ (first release; SCHEMA.md now documents it) |
| Browser QA ≥3 workflows | ⚠️ audit verified booking create + booking cancel + home/news render; full sweep belongs to playwright agent |

## Data Pipeline Status

| Component | Status | Notes |
|-----------|--------|-------|
| dataManager.js | ✅ | sid URL→sessionStorage, per-sid keys, first-load `set` baseline, `set_current` sync — matches 12306 pattern |
| AppContext state sync | ✅ | every mutation helper → `updateState` → `saveState` → server; see AUDIT-003/004 for edge polish |
| vite.config.js /post | ✅ | set / set_current / reset verified live; sid sanitized; unknown action → 400 |
| vite.config.js /state | ✅ | returns raw current_state, no-cache |
| vite.config.js /go | ✅ | `{initial_state, current_state, state_diff}` recursive diff verified live |
| /files/:attId | ✅ | PDF/DOC generated on the fly, 404 JSON for unknown ids, sid fallback to default |
| Session isolation (?sid=) | ✅ | audit2 saw nothing from audit1; only per-sid files on disk |
| .initial.json handling | ✅ | single-file `{initial_state, current_state}` variant per 12306 convention; `set` writes both, `set_current` never clobbers initial |
| secureMockApiPlugin | ✅ | registered first; transparent unless `CUA_GYM_HARDENED=1` |
| SCHEMA.md accuracy | ✅ | created this round from actual `createInitialData()` + live endpoint behavior |

## SCHEMA.md Updates

**CREATED** `websites/bjtu_mock/SCHEMA.md` (did not exist). Follows slack_mock format: Base URL / Go / Inject / Reset / State-read / Files endpoints, full state-key table with field shapes and enums, default IDs, minimal inject example with merge semantics (arrays replace, objects merge; fresh sid per episode), and the Observable State Changes table mapping all 9 mutating UI actions (+2 explicit no-signal actions) to `state_diff` paths.

---

# Round 2 — Final Verification

> Round: 2
> Date: 2026-09-22
> Audited by: audit agent (final verification pass)
> Server: reused running dev server on :5188 (healthy, HTTP 200)

## Summary

| Category | Round 1 | Round 2 status |
|----------|---------|----------------|
| P0 | 0 | **1 NEW (AUDIT-011 — fresh-context reload wipes pre-injected state_diff)** |
| P1 | 3 (AUDIT-001/002/003) | **0 — all 3 FIXED, empirically re-verified** |
| P2 | 7 (AUDIT-004…010) | 6 open, intentionally deferred (AUDIT-007 FIXED) |
| Playwright bugs | — | BUG-001 / BUG-002 fixes spot-checked, confirmed |
| `npm run build` | ✅ | ✅ (58 modules, no warnings, 99ms) |

**Final counts: P0 = 1 · P1 = 0.** The single P0 is a data-pipeline defect that only manifests in the canonical gym flow (inject → first browser open); it was invisible to Round-2 playwright testing because that run pre-seeded localStorage (TEST.md §9b note 2), which takes the `isRefresh` path and never re-POSTs the baseline.

## P0 — NEW

### AUDIT-011 · First open in a fresh browser context re-baselines the server and WIPES an existing `state_diff`
- **Files**: `src/utils/dataManager.js:80-106` (`initializeData`), `src/context/AppContext.jsx:27-34` (bootstrap effect), `vite.config.js:171-172` (`set` handler)
- **Severity**: P0 — silent destruction of the RL reward signal for the standard setup-gen pattern (`POST set` baseline + `POST set_current` task mutations, then agent's browser opens `?sid=`).

**Exact repro (verified live 2026-09-22, sid `auditfinal`):**
```
1. POST /post?sid=auditfinal {"action":"set","state":<createInitialData() seed>}          → {ok:true}
2. POST /post?sid=auditfinal {"action":"set_current","state":<seed + 3rd booking
   BK202609220009 已预约>}                                                                 → {ok:true}
3. GET /go?sid=auditfinal → state_diff = { bookings: {old:[2 rows], new:[3 rows incl. BK202609220009]} }   ← diff present ✅
4. Open http://localhost:5188/?sid=auditfinal in a FRESH browser context (empty
   localStorage/sessionStorage), wait for full render.
   Network capture: GET /state?sid=auditfinal ×2 (StrictMode) → then
   POST /post?sid=auditfinal {"action":"set", state.bookings.length=3}   ← MUTATED state re-POSTed as baseline
5. GET /go?sid=auditfinal →
     state_diff keys: []                     ← WIPED ❌
     initial_state.bookings: 3 (BK202609210001, BK202609100002, BK202609220009)
     current_state.bookings: 3 (identical — JSON-equal)
```
Reproduced a second time on sid `auditr2`: a pill-click diff (`noticeFilters.category 全部→教务教学`) created by one browser session was erased when the same sid was opened in a second fresh context — server file afterwards showed `initial_state.noticeFilters.category = 教务教学` (re-baselined onto the mutation).

**Root cause (two compounding layers):**
1. **Client** — `initializeData(sid, customState)` (`dataManager.js:90-99`): `isFirstLoad = !localStorage.getItem(initKey)` is true for *every* fresh browser context, even when `fetchCustomState` just proved the server already holds state for this sid. It then unconditionally POSTs `{action:'set', state: merged}` where `merged = deepMerge(createInitialData(), serverCurrentState)` — i.e. the **already-mutated** state.
2. **Server** — `vite.config.js` `/post` handler: `action === 'set'` does `stored = { initial_state: state, current_state: state }`, **unconditionally clobbering the existing `initial_state`**. (Audit spec: "`set` writes initial on first call only".) Net effect: `initial := mutated current` → `state_diff = {}`.

**What is NOT affected:** F5 / same-context reloads are safe — verified (sid `auditr4`): pill-click diff `noticeFilters.category {old:全部, new:招生考试}` survived two consecutive reloads; reload fires **zero** `/post` requests (`isRefresh` → localStorage path). Only the *first* open per browser context wipes.

**Recommended fix (report-only; no code changed by audit):**
- **Client (primary)**: in `initializeData`, skip the baseline `set` POST when the server already has state — e.g. only POST `set` when `customState` is null/empty; when `customState` came from `/state`, adopt it (seed localStorage from `merged`) without re-baselining. Matches the contract "GET /state first, adopt existing server state".
- **Server (hardening)**: make `set` preserve an existing `initial_state` (write initial only when the session file / `initial_state` is absent), per the audit spec. This also protects against any other accidental re-`set` path.
- Note: the `12306_mock` reference implementation shares the same client pattern (`dataManager.js:826-835`) and the same server `set` semantics — the defect is pattern-inherited, not unique to bjtu_mock. Flag to orchestrator for cross-site review; out of scope here.

**Harness workaround until fixed:** open the app in the agent's browser context *first* (baseline lock), and inject `set_current` mutations only afterwards — but beware the open tab will clobber injections on its next mutation (its localStorage copy is stale, cf. AUDIT-009). Practically: **fix the code**; there is no clean operational workaround.

## Round-1 issue re-verification

| Issue | Round-2 status | Evidence |
|-------|----------------|----------|
| AUDIT-001 · `?sid=` dropped by in-page interactions | ✅ **FIXED** | New `src/utils/sidParams.js`: `useSidSearchParams()` (rebuilds query while preserving `sid` from prev params or `getSessionId()`) + `buildSidUrl()` for `navigate()`. Adopted in NewsList, NoticeList, SearchPage, SearchOverlay. Live (sid `auditr2`): notices pill click → `/notices?sid=auditr2`; news tab → `/news?category=校园时讯&sid=auditr2`; overlay submit → `/search?q=校庆&scope=全部&sid=auditr2`; scope tab → `/search?q=校庆&scope=新闻&sid=auditr2` — sid present on every URL |
| AUDIT-002 · pure navigation mutates `noticeFilters` | ✅ **FIXED** | `NoticeList.jsx:17-40`: `?category=` is view-local (useMemo over URL param); `setNoticeFilters` only in `apply`/`reset`/`pickCat`. Live (fresh sid `auditr3`, instrumented): arrival at `/notices?category=招生考试&sid=auditr3` → renders filtered 共6条 + active pill, **`state_diff = {}`**; explicit pill click 教务教学 → **`state_diff = {noticeFilters.category: {old:全部, new:教务教学}}`** ✅. SCHEMA.md Observable-State-Changes table updated accordingly |
| AUDIT-003 · toast label relies on eager setState evaluation | ✅ **FIXED** | `AppContext.jsx:94-116`: `added` computed from rendered `state.favorites` **before** dispatch, returned deterministically (updater no longer mutates closure var). Live: star click → toast `已收藏`; second click → `已取消收藏` |
| AUDIT-007 · hardcoded header date | ✅ **FIXED** | `Header.jsx:7-12`: `formatToday()` derives `YYYY年M月D日　星期X` from `new Date()` via WEEKDAYS table |
| AUDIT-004 · saveState inside setState updater (StrictMode double POST) | ⚠️ still open (P2, deferred) | Confirmed in `auditr3` network log: pill click fired `set_current` ×2 (t=2312/2314ms), both 200, idempotent |
| AUDIT-005 / 006 / 008 / 009 / 010 | ⚠️ still open (P2, intentionally deferred) | No regressions observed; 009 partially superseded by AUDIT-011 (fresh-context first-open is now the documented hazard, SCHEMA.md warns) |

## Playwright bug-fix spot checks

| Bug | Status | Evidence |
|-----|--------|----------|
| BUG-001 · duplicate React key on `/about/lingdao` | ✅ FIXED | `About.jsx:100` → `key={`${role}-${name}`}`; live fresh-context load: **8 leader cards, 0 console errors** (whole session incl. notices/news/search/home/lingdao) |
| BUG-002 · HEAD `/files/:id` returned SPA HTML | ✅ FIXED | `vite.config.js:223` matches `GET\|HEAD`, `:245` suppresses body for HEAD. `curl -I /files/att_001?sid=auditr3` → `200`, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename=…`, `Content-Length: 1511`; unknown id → `404` |

## F5 / same-context reload verification (task 1b, second half)

sid `auditr4`, fresh context: load `/notices?sid=auditr4` (bootstrap `set` locks baseline) → pill click 招生考试 → diff `{noticeFilters.category: 全部→招生考试}` → **F5 ×2** → diff identical after each reload; total `/post` traffic across both reloads: **0** (only the initial `set` + 2× StrictMode `set_current` from the click). Same-context reloads preserve `state_diff`. ✅

## Build

`npm run build` → ✅ vite v8.3.0, 58 modules transformed, `dist/assets/index-*.js` 379.17 kB (gzip 120.09 kB), no warnings/errors.

## SCHEMA.md updates (Round 2)

1. Observable State Changes: `noticeFilters` row now says explicit actions only (查询/重置/pill click); added explicit **no-state-change** row for pure `?category=` arrival (AUDIT-002 fix).
2. Minimal-inject notes: bootstrap behavior rewritten from verified evidence (fresh-context first open = one `set` POST; same-context F5 = zero POSTs, diff survives) + ⚠️ warning documenting **AUDIT-011** (pre-injected diff wiped on first fresh-context open) with pointer to this file.

## Cleanup

Removed audit test-session files from `.mock-states/`: `auditfinal.json`, `auditr2.json`, `auditr3.json`, `auditr4.json`, plus stale `devcheck.json`. Dev server left **RUNNING** on :5188.

## Remaining open issues after Round 2

- **P0: AUDIT-011** (fresh-context first-open re-baseline / diff wipe) → must be fixed by dev, then re-verified with the repro above (expect `state_diff` preserved after fresh-context load).
- **P2 (deferred, intentional)**: AUDIT-004, 005, 006, 008, 009, 010.
- **P1: none.**

**Final counts: P0 = 1 · P1 = 0 · P2 = 6 open (deferred).**

---

# Round 3 — AUDIT-011 fix verification (2026-09-22)

## AUDIT-011 · fresh-context re-baseline wipes /go state_diff → **FIXED-VERIFIED** ✅

Original Round 2 entry kept above unchanged. Independent repro re-run after dev fix (`src/utils/dataManager.js` + `AppContext.jsx`: baseline `set` POST only when GET /state is empty; StrictMode `initStarted` single-run guard):

1. Deleted stale `.mock-states/verA.json`; via curl: POST `/post?sid=verA` `{action:'set', state:createInitialData() seed}` then `{action:'set_current', state: seed + extra booking BK202609229999 (已预约, 2026-10-10 上午)}`.
2. GET `/go?sid=verA` → `state_diff.bookings` shows `BK202609210001/BK202609100002 → +BK202609229999`. ✅
3. Headless Chromium, **fresh browser context**, opened `http://localhost:5188/?sid=verA`, captured all network traffic to `/post` and `/state`, waited for full render (networkidle + 2s).
4. Assertions: **action:'set' POSTs = 0** ✅ · **GET /state = exactly 1** ✅ · set_current POSTs on load = 0 ✅ (StrictMode guard held; bootstrap GET single-run).
5. GET `/go?sid=verA` after browser open → `state_diff` **byte-identical** to step 2 (canonical JSON compare). ✅ Pre-injected diff survives first fresh-context open.

Script verdict: `TASK1 PASS` (6/6 checks).

**AUDIT-011: FIXED-VERIFIED.**

## Round 3 — post-fix UI regression (sid verB)

Single batched headless-Chromium script (fresh context), full action walk:

| Step | Result |
|---|---|
| `/visit` create booking (2026-10-05 上午, 2人) → 我的预约 → 取消预约 (modal 确认取消) → row shows 已取消 | ✅ |
| `/admission/inquiry` submit (message ≥10 chars, 提交咨询) | ✅ |
| `/news` star one item (`.row-star[aria-label=收藏]`) | ✅ |
| notice detail favorite (`.fav-button[aria-label=收藏]`) | ✅ |
| `/search` query 校庆 (搜索) | ✅ |
| `/notices` pill 招生考试 → `.filter-pill.active` | ✅ |
| attachment download accepted → first 4 bytes = `%PDF` | ✅ |
| F5 ×1 on `/notices` → page + pill state intact | ✅ |

`curl /go?sid=verB` → `state_diff` keys exactly: `bookings, downloads, favorites, inquiries, noticeFilters.category, searchHistory` — bookings contains the 2026-10-05 booking with status **已取消** ✅ · inquiries **+1** ✅ · favorites **+2** ✅ · searchHistory contains **校庆** ✅ · downloads **+1** ✅ · `noticeFilters.category` → **招生考试** ✅.
Isolation: `/go?sid=verZ` → `initial_state=null, current_state=null, state_diff={}` ✅. Console errors: **0** ✅.

Script verdict: `TASK2 PASS` (15/15 checks). No new bugs; AUDIT-011 fix introduced no regressions.

## Round 3 — /go page non-interference + build (Task 3)

- `curl /go?sid=verB` (saved `/tmp/go_verB_before.json`) → opened SPA `/go?sid=verB` in fresh headless context (rendered, 0 console errors) → `curl` again → **canonical JSON identical** before/after. `/go` page is strictly read-only, no state interference. ✅
- `npm run build` → ✅ vite built in 100ms: `dist/index.html` 0.70 kB, `index-CYLli_FR.css` 26.55 kB (gzip 5.97), `index-C_TBZAWZ.js` 379.21 kB (gzip 120.12). No warnings/errors.

## Round 3 final counts

**P0 = 0 open** (AUDIT-011 FIXED-VERIFIED) · **P1 = 0 open** · **P2 deferred list unchanged** (AUDIT-004, 005, 006, 008, 009, 010 — intentional, deferred).

Cleanup: `.mock-states/verA.json` + `verB.json` deleted. Dev server left **RUNNING** on :5188.
