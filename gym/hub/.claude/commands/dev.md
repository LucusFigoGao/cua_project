# Mock Application Development Workflow

You are now in **Mock Development Mode** for browser-agent training sandbox applications.

## Architecture: Three Parallel Workstreams

This workflow uses **three specialized agents** working in parallel:

```
┌─────────────────────────────────────────────────────────────┐
│                     MAIN AGENT (You)                        │
│                    UI Development                           │
│         Fix buttons, forms, navigation, styling             │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐     ┌───────────────────┐
│  PLAYWRIGHT       │     │  STATE            │
│  SUBAGENT         │     │  SUBAGENT         │
│                   │     │                   │
│  • UI Testing     │     │  • /go endpoint   │
│  • Screenshots    │     │  • Data structure │
│  • Interaction    │     │  • State tracking │
│    verification   │     │  • Diff computing │
└───────────────────┘     └───────────────────┘
```

## Workflow Steps

### Phase 1: Initial Analysis

**Step 1.1: Start the dev server**
```bash
npm run dev -- --port 5180
```
Note the actual port if different.

**Step 1.2: Launch BOTH subagents in parallel**

Use the Task tool to spawn both subagents simultaneously:

```
SUBAGENT 1 - Playwright UI Analysis:
Task(subagent_type="Explore", prompt="
  You are the Playwright Testing Subagent.

  1. Use Playwright Skill to explore http://localhost:[PORT]
  2. Screenshot the main page and all accessible routes
  3. Test ALL interactive elements:
     - Click every button and note if it responds
     - Test every form input
     - Test every link/navigation
     - Test hover states
  4. Document findings:
     - WORKING: [list of working features]
     - BROKEN: [list of broken features with details]
     - MISSING: [expected features not present]
  5. Save screenshots to /tmp/[app_name]-analysis/
")

SUBAGENT 2 - State Management Analysis:
Task(subagent_type="Explore", prompt="
  You are the State Management Subagent.

  1. Analyze the codebase for state management:
     - Check src/context/, src/store/, src/store.js
     - Identify the pattern (Context/Redux/Zustand)

  2. Check if /go endpoint exists:
     - Look in App.jsx for /go route
     - Check for StateInspector or Go component

  3. If /go endpoint is MISSING or INCOMPLETE:
     - Copy template from .claude/templates/stateTracker.js to src/utils/
     - Copy template from .claude/templates/Go.jsx to src/pages/
     - Customize for this app's state management
     - Add route to App.jsx

  4. If /go endpoint EXISTS:
     - Verify it returns { initial_state, current_state, state_diff }
     - Check if state tracking is complete
     - Fix any issues

  5. Report:
     - State management pattern used
     - /go endpoint status (created/updated/verified)
     - List of state fields being tracked
")
```

### Phase 2: Planning (After Subagent Reports)

Wait for both subagents to complete, then:

1. **Review Playwright report** - List of UI issues
2. **Review State report** - /go endpoint status and data structure

3. **Create prioritized TODO list**:
   - P0: Critical functionality (buttons don't work, forms broken)
   - P1: State tracking issues (/go endpoint incomplete)
   - P2: UI polish (hover states, transitions)
   - P3: Edge cases

### Phase 3: Development Loop

For each issue in the TODO list:

**Main Agent (You):**
1. Implement the fix in the codebase
2. Mark the fix as ready for testing

**Then spawn Playwright Subagent to verify:**
```
Task(subagent_type="Explore", prompt="
  Test the fix for [SPECIFIC ISSUE]:
  1. Open http://localhost:[PORT]
  2. Navigate to [SPECIFIC LOCATION]
  3. Perform [SPECIFIC ACTION]
  4. Verify:
     - Expected behavior occurs
     - No console errors
     - State updated correctly (check /go)
  5. Take before/after screenshots
  6. Report: PASS or FAIL with details
")
```

**If the fix involves state changes, also spawn State Subagent:**
```
Task(subagent_type="Explore", prompt="
  Verify state tracking for [SPECIFIC FEATURE]:
  1. Visit /go endpoint
  2. Check initial_state contains [EXPECTED FIELDS]
  3. Perform action that should change state
  4. Revisit /go endpoint
  5. Verify state_diff shows the change correctly
  6. Report: PASS or FAIL with JSON samples
")
```

### Phase 4: Final Validation

After all fixes, run comprehensive validation with both subagents:

```
FINAL Playwright Validation:
Task(subagent_type="Explore", prompt="
  Comprehensive UI test for [APP_NAME]:
  1. Test ALL buttons - each should have a response
  2. Test ALL forms - should validate and submit
  3. Test ALL navigation - should change views
  4. Test state persistence - refresh page, state should persist
  5. Generate final test report with screenshots
")

FINAL State Validation:
Task(subagent_type="Explore", prompt="
  Comprehensive state test for [APP_NAME]:
  1. Clear session (fresh start)
  2. Visit /go - capture initial_state
  3. Perform 5-10 typical user actions
  4. Visit /go - verify state_diff is accurate
  5. Verify all important state fields are tracked
  6. Generate state coverage report
")
```

## Template Files Location

When the State Subagent needs to implement /go endpoint:

- **State Tracker Utility**: `.claude/templates/stateTracker.js` → copy to `src/utils/stateTracker.js`
- **Go Component**: `.claude/templates/Go.jsx` → copy to `src/pages/Go.jsx`

## Important Notes

- **Always run subagents in parallel** when they don't depend on each other
- **Main agent focuses on code changes**, subagents handle testing
- **State subagent has write permission** for /go endpoint implementation
- **Playwright subagent is read-only** for testing
- **Check /go endpoint frequently** during development
- **Keep screenshots organized** in /tmp/[app_name]-[date]/

## Quick Reference: Subagent Prompts

### Quick UI Test
```
Task(subagent_type="Explore", prompt="
  Quick UI test: Click [ELEMENT] at http://localhost:[PORT]
  and verify it [EXPECTED BEHAVIOR]. Screenshot before/after.
")
```

### Quick State Test
```
Task(subagent_type="Explore", prompt="
  Quick state test: Check /go at http://localhost:[PORT]
  and verify [FIELD] changes from [OLD] to [NEW] after [ACTION].
")
```

### Implement /go Endpoint
```
Task(subagent_type="Explore", prompt="
  Implement /go endpoint for [APP_NAME]:
  1. Copy .claude/templates/stateTracker.js to src/utils/
  2. Copy .claude/templates/Go.jsx to src/pages/
  3. Customize for [CONTEXT/REDUX/ZUSTAND] pattern
  4. Add route to App.jsx
  5. Test and verify JSON output
")
```

## Autonomous Mode (YOLO)

When launched via `parallel-dev.sh`, you should work fully autonomously:

1. **DO NOT ASK** for user confirmation - just proceed
2. **Dev server is already running** - check the port from your launch prompt
3. **Execute all phases** without stopping for approval
4. **Make all necessary code changes** directly
5. **Run verification tests** after each fix
6. **Generate a final summary** when complete

### Autonomous Execution Flow

```
START → Detect Port → Launch Subagents → Wait for Reports →
Create TODO → Fix Issues One by One → Verify Each Fix →
Final Validation → Update CLAUDE.md → COMPLETE
```

### Auto-Detect Running Mock

Check the prompt context for:
- Port number (e.g., "http://localhost:5180")
- Mock name (e.g., "github_mock")

If not provided, detect from current directory:
```bash
basename $(pwd) | grep -oP '.*(?=_mock)'
```

## Start Now

**If in autonomous mode**: Begin immediately with Phase 1 using the port from your launch prompt.

**If in interactive mode**: Ask user to start the dev server, then launch both subagents in parallel to analyze the current state of this mock application.

---

# Session-Based State Isolation (Multi-Tenant) Development Spec

## Overview

Each mock application supports **session-based state isolation** so that multiple users/machines (A, B, C...) can access the same host machine without interfering with each other's state. This is achieved through a `?sid=xxx` URL parameter that routes to per-session server files and per-session localStorage keys.

### Deployment Scenario

```
┌──────────┐                          ┌──────────────────────┐
│ Machine A │───┐                     │   Host Machine       │
│ browser   │   │                     │   (Public IP)        │
└──────────┘   │                     │                      │
┌──────────┐   │  ?sid=session_A     │  ┌────────────────┐  │
│ Machine B │───┼──────────────────────▶│  Vite Dev Server │  │
│ browser   │   │  ?sid=session_B     │  │  (port 5180+)   │  │
└──────────┘   │                     │  │                  │  │
┌──────────┐   │  ?sid=session_C     │  │  .mock-states/   │  │
│ Machine C │───┘                     │  │  ├─session_A.json│  │
│ browser   │                         │  │  ├─session_B.json│  │
└──────────┘                          │  │  └─session_C.json│  │
                                      │  └────────────────┘  │
                                      └──────────────────────┘
```

### Workflow

1. **Script runs first**: `launch_task.sh` starts dev servers + POSTs initial state with `?sid=xxx`
2. **Browser opens second**: User opens `http://host:PORT?sid=xxx` → app fetches custom state from server → renders modified data
3. **Refresh works**: State survives page refresh via localStorage with session-specific keys
4. **Isolation guaranteed**: Each session has its own server file + its own localStorage keys

## Files That Need Modification (4 files per mock)

When adding session isolation to a new mock app, you must modify these 4 files:

### File 1: `vite.config.js` — Server-Side Session Storage

**What to change**: Convert from single `.mock-state.json` to per-session directory `.mock-states/`.

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

// === SESSION-BASED STATE STORAGE ===
const STATE_DIR = path.join(process.cwd(), '.mock-states')

if (!fs.existsSync(STATE_DIR)) {
  fs.mkdirSync(STATE_DIR, { recursive: true })
}

function getStateFile(sid) {
  if (!sid) return path.join(process.cwd(), '.mock-state.json')
  // Sanitize sid to prevent path traversal attacks
  const safeSid = sid.replace(/[^a-zA-Z0-9_-]/g, '')
  return path.join(STATE_DIR, `${safeSid}.json`)
}

function readState(sid) {
  try {
    const file = getStateFile(sid)
    if (fs.existsSync(file)) {
      return JSON.parse(fs.readFileSync(file, 'utf-8'))
    }
  } catch (e) {
    console.error('Error reading state file:', e)
  }
  return null
}

function writeState(sid, state) {
  try {
    fs.writeFileSync(getStateFile(sid), JSON.stringify(state, null, 2))
    return true
  } catch (e) {
    console.error('Error writing state file:', e)
    return false
  }
}

function clearState(sid) {
  try {
    const file = getStateFile(sid)
    if (fs.existsSync(file)) { fs.unlinkSync(file) }
    return true
  } catch (e) { return false }
}

// Parse ?sid=xxx from URL query string
function parseQuery(url) {
  const idx = url.indexOf('?')
  if (idx === -1) return {}
  const params = {}
  url.substring(idx + 1).split('&').forEach(pair => {
    const [k, v] = pair.split('=')
    if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || '')
  })
  return params
}

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'mock-api',
      configureServer(server) {
        // POST /post?sid=xxx - Set initial state data
        server.middlewares.use('/post', async (req, res, next) => {
          if (req.method !== 'POST') return next()
          const query = parseQuery(req.url || '')
          const sid = query.sid || null

          let body = ''
          for await (const chunk of req) { body += chunk }

          try {
            const data = JSON.parse(body)
            const action = data.action || 'set'

            if (action === 'reset') {
              clearState(sid)
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ success: true, sid, message: 'State reset.' }))
              return
            }
            if (action === 'set') {
              const currentState = readState(sid) || {}
              const newState = data.merge ? deepMerge(currentState, data.state) : data.state
              writeState(sid, newState)
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ success: true, sid, message: 'State updated.', state: newState }))
              return
            }
            res.statusCode = 400
            res.end(JSON.stringify({ error: 'Unknown action' }))
          } catch (e) {
            res.statusCode = 400
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ error: e.message }))
          }
        })

        // GET /state?sid=xxx - Get stored state
        server.middlewares.use('/state', (req, res, next) => {
          if (req.method !== 'GET') return next()
          const query = parseQuery(req.url || '')
          const sid = query.sid || null
          const state = readState(sid)

          res.setHeader('Content-Type', 'application/json')
          res.setHeader('Cache-Control', 'no-cache, no-store')
          res.end(JSON.stringify({
            stored_state: state,
            has_custom_state: state !== null,
            sid
          }))
        })
      }
    }
  ],
  // ... rest of config
})

function deepMerge(target, source) {
  const result = { ...target }
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(result[key] || {}, source[key])
    } else {
      result[key] = source[key]
    }
  }
  return result
}
```

**Key points:**
- `?sid=xxx` parameter on both `/post` and `/state` endpoints
- Sid is sanitized to alphanumeric + `_` + `-` only (prevents path traversal)
- Without `?sid`, falls back to single `.mock-state.json` (backward compatible)
- `Cache-Control: no-cache` on `/state` to prevent stale reads

### File 2: `src/utils/dataManager.js` — Session-Aware Data Management

**What to add** (at the top of the file, before existing functions):

```javascript
const BASE_STORAGE_KEY = 'appNameState';      // e.g. 'slackCloneState'
const BASE_INITIAL_KEY = 'appNameInitialState'; // e.g. 'slackCloneInitialState'

// Session-specific localStorage keys
function storageKey(sid) {
  return sid ? `${BASE_STORAGE_KEY}_${sid}` : BASE_STORAGE_KEY;
}
function initialKey(sid) {
  return sid ? `${BASE_INITIAL_KEY}_${sid}` : BASE_INITIAL_KEY;
}

// Read sid from URL ?sid= or sessionStorage (survives SPA navigation + refresh)
export const getSessionId = () => {
  const params = new URLSearchParams(window.location.search);
  const urlSid = params.get('sid');
  if (urlSid) {
    sessionStorage.setItem('mock_sid', urlSid);
    return urlSid;
  }
  return sessionStorage.getItem('mock_sid') || null;
};

// Fetch custom state from server (async!)
export const fetchCustomState = async (sid = null) => {
  try {
    const url = sid ? `/state?sid=${encodeURIComponent(sid)}` : '/state';
    const response = await fetch(url);
    if (response.ok) {
      const data = await response.json();
      if (data.has_custom_state && data.stored_state) {
        return data.stored_state;
      }
    }
  } catch (e) {
    console.log('No custom state available');
  }
  return null;
};

// Save to session-specific localStorage
export const saveState = (state, sid = null) => {
  localStorage.setItem(storageKey(sid), JSON.stringify(state));
};
```

**Modify `initializeData`** to accept `sid` and `customState`:

```javascript
export const initializeData = (sid = null, customState = null) => {
  const sk = storageKey(sid);
  const ik = initialKey(sid);

  // Case 1: Custom state provided (first load with session)
  if (customState) {
    const initialData = deepMergeWithDefaults(createInitialData(), customState);
    localStorage.setItem(sk, JSON.stringify(initialData));
    localStorage.setItem(ik, JSON.stringify(initialData));
    return initialData;
  }

  // Case 2: Existing data in localStorage (refresh case)
  const stored = localStorage.getItem(sk);
  if (stored) {
    if (!localStorage.getItem(ik)) {
      localStorage.setItem(ik, stored);
    }
    return JSON.parse(stored);
  }

  // Case 3: No data at all → create defaults
  const initialData = createInitialData();
  localStorage.setItem(sk, JSON.stringify(initialData));
  localStorage.setItem(ik, JSON.stringify(initialData));
  return initialData;
};
```

**Add deep merge utility**:

```javascript
function deepMergeWithDefaults(defaults, custom) {
  if (!custom) return defaults;
  const result = { ...defaults };
  for (const key in custom) {
    if (custom[key] !== null && custom[key] !== undefined) {
      if (typeof custom[key] === 'object' && !Array.isArray(custom[key]) && typeof defaults[key] === 'object') {
        result[key] = deepMergeWithDefaults(defaults[key], custom[key]);
      } else {
        // Arrays and primitives: custom state REPLACES default
        result[key] = custom[key];
      }
    }
  }
  return result;
}
```

**Key points:**
- Arrays are REPLACED, not merged (e.g., `messages.engineering` replaces entirely)
- Objects are recursively merged (e.g., `messages` object: only specified channel keys are overridden)
- `getSessionId()` reads URL first → saves to `sessionStorage` → subsequent calls read from `sessionStorage`
- `fetchCustomState()` is async — it fetches from the server's `/state?sid=xxx` endpoint

### File 3: `src/context/AppContext.jsx` (or equivalent state provider) — Session-Aware Init Logic

**Critical pattern**: Check localStorage BEFORE calling `initializeData()` to distinguish first-load vs refresh.

```javascript
import { initializeData, getInitialState, fetchCustomState, getSessionId, saveState } from '../utils/dataManager';

export const AppProvider = ({ children }) => {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);

  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;

    const sid = sidRef.current;

    if (sid) {
      // ⚠️ CRITICAL: Check localStorage BEFORE initializeData
      // initializeData() writes defaults to localStorage, which would mask this check
      const sessionKey = `appNameInitialState_${sid}`;
      const isRefresh = localStorage.getItem(sessionKey) !== null;

      if (isRefresh) {
        // Refresh: use existing localStorage (preserves agent's in-session changes)
        const data = initializeData(sid);
        setState(data);
        setLoading(false);
      } else {
        // First load: async fetch custom state from server, then initialize
        fetchCustomState(sid).then(customState => {
          const data = initializeData(sid, customState);
          setState(data);
          setLoading(false);
        });
      }
    } else {
      // No sid: backward compatible (no session isolation)
      const data = initializeData();
      setState(data);
      setLoading(false);
    }
  }, []);

  // updateState must save to session-specific localStorage
  const updateState = (updates) => {
    setState(prev => {
      const newState = { ...prev, ...updates };
      saveState(newState, sidRef.current);
      return newState;
    });
  };

  // ... rest of context provider
};
```

**Key points:**
- `initDone` ref prevents double-init in React Strict Mode
- `sidRef` captures the session ID once on mount
- First-load detection reads `localStorage.getItem(sessionKey)` BEFORE any call to `initializeData()`
- First load is ASYNC (fetches from server) — `loading` state prevents rendering until data arrives
- Refresh is SYNC (reads from localStorage) — instant render

### File 4: `src/App.jsx` — Preserve `?sid=` in React Router Redirects

**Problem**: React Router's `<Navigate to="/some/path" />` strips query parameters. When a user visits `/?sid=xxx`, the redirect to `/channel/general` loses `?sid`.

**Solution**: Custom `RedirectWithQuery` component.

```javascript
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from 'react-router-dom';

// Preserve query params (e.g. ?sid=xxx) when redirecting
function RedirectWithQuery({ to }) {
  const [searchParams] = useSearchParams();
  const query = searchParams.toString();
  return <Navigate to={query ? `${to}?${query}` : to} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            {/* Use RedirectWithQuery instead of Navigate */}
            <Route index element={<RedirectWithQuery to="/channel/general" />} />
            <Route path="channel/:channelId" element={<ChannelView />} />
            {/* ... other routes */}
          </Route>
        </Routes>
      </AppProvider>
    </BrowserRouter>
  );
}
```

**Key points:**
- Replace ALL `<Navigate to="..." />` index redirects with `<RedirectWithQuery to="..." />`
- `useSearchParams()` captures the current URL's query parameters
- This ensures `?sid=xxx` (and any other query params) survive the redirect

## Common Pitfalls and Bugs

### Pitfall 1: First-Load Detection Fails (Always Thinks It's Refresh)

**Symptom**: Custom state from POST never loads; app always shows default data.

**Root Cause**: `initializeData()` is called BEFORE checking localStorage. The function writes default data to localStorage on its first call, so the "isRefresh" check always finds existing data.

**Fix**: Check `localStorage.getItem(sessionKey)` BEFORE calling `initializeData()`:
```javascript
// ✅ CORRECT ORDER
const isRefresh = localStorage.getItem(sessionKey) !== null;
if (isRefresh) {
  initializeData(sid);  // reads existing localStorage
} else {
  fetchCustomState(sid).then(custom => initializeData(sid, custom));
}

// ❌ WRONG ORDER
const data = initializeData(sid);  // writes defaults → now localStorage has data!
const isRefresh = localStorage.getItem(sessionKey) !== null;  // ALWAYS true!
```

### Pitfall 2: `?sid=` Lost After React Router Navigation

**Symptom**: User opens `http://localhost:5180?sid=test123` → URL becomes `http://localhost:5180/channel/general` (no sid) → refresh loads wrong data.

**Root Cause**: React Router's `<Navigate to="/channel/general" replace />` discards query params.

**Fix**: Use `RedirectWithQuery` component (see File 4 above) AND persist sid in `sessionStorage`:
```javascript
// In getSessionId():
const urlSid = params.get('sid');
if (urlSid) {
  sessionStorage.setItem('mock_sid', urlSid);  // survives SPA navigation + refresh
  return urlSid;
}
return sessionStorage.getItem('mock_sid') || null;  // fallback
```

### Pitfall 3: CSS Class Name Collisions

**Symptom**: Thread panel content displays horizontally or wrong styling.

**Root Cause**: Parent component and child component both use the same CSS class name (e.g., `.thread-replies`), and the parent's `display: inline-flex` overrides the child's intended layout.

**Fix**: Use unique class names. E.g., rename the container to `.thread-replies-list` in ThreadPanel, keeping `.thread-replies` for the button in Message.

### Pitfall 4: Thread Crash on Null Replies

**Symptom**: `TypeError: Cannot read properties of undefined (reading 'length')`.

**Root Cause**: Code like `message.threadId ? [] : ...` returns `[]` (truthy), then `[].replies.length` crashes because arrays don't have a `replies` property.

**Fix**: Return `null` instead of `[]` and add null-safe checks:
```javascript
// ✅ Correct
const threadReplies = message.threadId ? null :
  Object.values(state.threads || {}).find(t => t.parentMessageId === message.messageId);
const replyCount = threadReplies && threadReplies.replies ? threadReplies.replies.length : 0;

// ❌ Wrong
const threadReplies = message.threadId ? [] :
  Object.values(state.threads || {}).find(t => t.parentMessageId === message.messageId);
const replyCount = threadReplies.replies.length;  // crashes when threadReplies is []
```

### Pitfall 5: Thread Actions Show Inside Thread Panel

**Symptom**: "Reply in thread" button appears on messages already inside the thread panel, creating nested thread opening.

**Fix**: Add `isInThread` prop to Message component:
```javascript
// In Message.jsx
function Message({ message, channelId, dmId, isInThread = false }) {
  // ...
  {!isInThread && <button onClick={handleReplyInThread}>💬 Reply</button>}
  {replyCount > 0 && !isInThread && <button className="thread-replies">...</button>}
}

// In ThreadPanel.jsx
<Message message={parentMessage} isInThread={true} />
{threadMessages.map(msg => <Message key={msg.messageId} message={msg} isInThread={true} />)}
```

## Deep Merge Strategy

When custom state is merged with default app data:

| Data Type | Merge Strategy | Example |
|-----------|---------------|---------|
| **Objects** | Recursive merge (custom keys override, other keys preserved) | `messages: { engineering: [...] }` only replaces `engineering`, keeps `general` etc. |
| **Arrays** | Complete replacement (custom array replaces default) | `messages.engineering: [...]` replaces all engineering messages |
| **Primitives** | Direct override | `currentUser.status: "busy"` overrides default |
| **Null/Undefined** | Skipped (default preserved) | `channels: null` keeps default channels |

## Task JSON POST Format

The launch script POSTs to each mock's `/post?sid=xxx` endpoint with this format:

```json
{
  "action": "set",
  "state": {
    "messages": {
      "engineering": [
        {
          "messageId": "msg_sprint_1",
          "senderId": "user_3",
          "content": "Sprint planning poll: Which features should we prioritize?",
          "timestamp": "2024-01-15T10:00:00Z",
          "reactions": [
            { "emoji": "1️⃣", "users": ["user_1", "user_4"] },
            { "emoji": "2️⃣", "users": ["user_2"] }
          ]
        }
      ]
    }
  },
  "merge": true
}
```

**Key**: `"merge": true` enables deep merge with existing defaults. Without it, the state completely replaces.

## Launch Script Usage

The task launcher script is at `/Users/bowen/Downloads/Projects/OSWorld-Task/launch_task.sh`:

```bash
# Auto-generate session ID:
./launch_task.sh tasks/task_1_slack_calendar_sprint_planning.json

# Specify session ID:
./launch_task.sh tasks/task_1_slack_calendar_sprint_planning.json --sid my-test-session
```

**What it does:**
1. Parses task JSON → identifies required mock apps (from `post[].type` fields)
2. Starts each mock's Vite dev server on sequential ports (5180, 5181, ...)
3. Waits for all servers to be ready (`curl` health check)
4. POSTs initial state to each server's `/post?sid=xxx` endpoint
5. Prints browser URLs with `?sid=xxx` for the user to open
6. Ctrl+C stops all servers

## Checklist: Adding Session Isolation to a New Mock

When you need to add session isolation to a mock that doesn't have it yet:

- [ ] **vite.config.js**: Add `.mock-states/` directory pattern, `parseQuery()`, session-aware `/post` and `/state` endpoints
- [ ] **src/utils/dataManager.js**: Add `storageKey(sid)`, `initialKey(sid)`, `getSessionId()`, `fetchCustomState()`, `saveState(state, sid)`, modify `initializeData(sid, customState)`, add `deepMergeWithDefaults()`
- [ ] **src/context/AppContext.jsx** (or state provider): Add session-aware init logic with BEFORE-check pattern, use `saveState(newState, sidRef.current)` in `updateState`
- [ ] **src/App.jsx**: Replace `<Navigate>` index redirects with `<RedirectWithQuery>` component
- [ ] **Test**: POST data with `?sid=test`, open in incognito with `?sid=test`, verify state changes visible, refresh and verify state persists
- [ ] **Add `.mock-states/` to .gitignore** if not already there
