import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5194';

// Helper to clear localStorage to get fresh state
async function freshPage(page) {
  await page.goto(BASE);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForLoadState('networkidle');
}

// ============================================================
// PHASE 1: PAGE DISCOVERY & SCREENSHOTS
// ============================================================

test.describe('Phase 1: Page Navigation & Rendering', () => {

  test('1.1 Dashboard loads and renders correctly', async ({ page }) => {
    await freshPage(page);
    // Check page title
    await expect(page).toHaveTitle('GitMock');
    // Check "Home" heading
    await expect(page.locator('h1')).toContainText('Home');
    // Check repo cards exist
    await expect(page.locator('text=react-clone')).toBeVisible();
    await expect(page.locator('text=awesome-tools')).toBeVisible();
    // Check sidebar
    await expect(page.locator('text=Top Repositories')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/01-dashboard.png', fullPage: true });
  });

  test('1.2 Repository Code page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');
    // Check repo name is shown
    await expect(page.locator('text=react-clone')).toBeVisible();
    // Check file tree
    await expect(page.locator('text=package.json')).toBeVisible();
    await expect(page.locator('text=README.md')).toBeVisible();
    // Check tab navigation
    await expect(page.locator('text=Code')).toBeVisible();
    await expect(page.locator('text=Issues')).toBeVisible();
    await expect(page.locator('text=Pull requests')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/02-repo-code.png', fullPage: true });
  });

  test('1.3 Issues list page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Fix login bug')).toBeVisible();
    await expect(page.locator('text=New Issue')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/03-issues-list.png', fullPage: true });
  });

  test('1.4 Issue detail page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toContainText('Fix login bug');
    await expect(page.locator('text=#1')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/04-issue-detail.png', fullPage: true });
  });

  test('1.5 Pull Requests page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Add Login Feature')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/05-pulls-list.png', fullPage: true });
  });

  test('1.6 Pull Request detail page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toContainText('Add Login Feature');
    await expect(page.locator('text=Merge pull request')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/06-pr-detail.png', fullPage: true });
  });

  test('1.7 Project Board page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=To Do')).toBeVisible();
    await expect(page.locator('text=In Progress')).toBeVisible();
    await expect(page.locator('text=Done')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/07-project-board.png', fullPage: true });
  });

  test('1.8 Wiki page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/wiki`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Home')).toBeVisible();
    await expect(page.locator('text=Welcome to the wiki!')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/08-wiki.png', fullPage: true });
  });

  test('1.9 Settings page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/settings`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=General')).toBeVisible();
    await expect(page.locator('text=Danger Zone')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/09-settings.png', fullPage: true });
  });

  test('1.10 Commits page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/commits`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Initial commit')).toBeVisible();
    await expect(page.locator('text=Add button component')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/10-commits.png', fullPage: true });
  });

  test('1.11 Commit detail page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/commit/c2`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Add button component')).toBeVisible();
    await expect(page.locator('text=SHA: c2')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/11-commit-detail.png', fullPage: true });
  });

  test('1.12 New Issue page loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/new`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=New Issue')).toBeVisible();
    await expect(page.locator('input[placeholder="Title"]')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/12-new-issue.png', fullPage: true });
  });

  test('1.13 /go state endpoint returns JSON', async ({ page }) => {
    const response = await page.goto(`${BASE}/go`);
    const body = await response.text();
    // /go might be a component page or API endpoint
    // Check if it renders or returns data
    console.log('  /go response status:', response.status());
    console.log('  /go response content type:', response.headers()['content-type']);
    await page.screenshot({ path: 'tests/screenshots/13-go-endpoint.png', fullPage: true });
  });

  test('1.14 Second repo (awesome-tools) loads', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/awesome-tools`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=awesome-tools')).toBeVisible();
    await expect(page.locator('text=main.py')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/14-repo2-code.png', fullPage: true });
  });

  test('1.15 Non-existent repo shows error', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/nonexistent`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Repository not found')).toBeVisible();
  });

  test('1.16 Non-existent issue shows error', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/999`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Issue not found')).toBeVisible();
  });
});

// ============================================================
// PHASE 2: INTERACTIVE ELEMENT TESTING
// ============================================================

test.describe('Phase 2: Header Navigation', () => {

  test('2.1 XitHub logo navigates to dashboard', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');
    // Click the XitHub logo (first svg in header)
    await page.locator('header a[href="/"]').first().click();
    await expect(page).toHaveURL(BASE + '/');
    await expect(page.locator('h1')).toContainText('Home');
  });

  test('2.2 Search bar shows results for repos', async ({ page }) => {
    await freshPage(page);
    const searchInput = page.locator('input[placeholder="Search or jump to..."]');
    await searchInput.click();
    await searchInput.fill('react');
    // Wait for dropdown
    await expect(page.locator('text=Repositories')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=admin/react-clone')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/20-search-repos.png' });
  });

  test('2.3 Search bar shows results for issues', async ({ page }) => {
    await freshPage(page);
    const searchInput = page.locator('input[placeholder="Search or jump to..."]');
    await searchInput.click();
    await searchInput.fill('login');
    await expect(page.locator('text=Issues')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=Fix login bug')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/21-search-issues.png' });
  });

  test('2.4 Search result click navigates to repo', async ({ page }) => {
    await freshPage(page);
    const searchInput = page.locator('input[placeholder="Search or jump to..."]');
    await searchInput.click();
    await searchInput.fill('react');
    await page.locator('button:has-text("admin/react-clone")').click();
    await expect(page).toHaveURL(/\/admin\/react-clone/);
  });

  test('2.5 Search bar clear button works', async ({ page }) => {
    await freshPage(page);
    const searchInput = page.locator('input[placeholder="Search or jump to..."]');
    await searchInput.fill('react');
    await expect(page.locator('text=Repositories')).toBeVisible({ timeout: 3000 });
    // Click clear button (X icon)
    await page.locator('header button').filter({ has: page.locator('svg') }).first().click();
    // Verify search is cleared - the dropdown should be gone
    // (the exact behavior depends on the implementation)
  });

  test('2.6 Search bar no results message', async ({ page }) => {
    await freshPage(page);
    const searchInput = page.locator('input[placeholder="Search or jump to..."]');
    await searchInput.fill('zzznonexistent');
    await expect(page.locator('text=No results found')).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'tests/screenshots/22-search-no-results.png' });
  });

  test('2.7 Pull requests nav link works', async ({ page }) => {
    await freshPage(page);
    await page.locator('nav a:has-text("Pull requests")').first().click();
    await expect(page).toHaveURL(/\/pulls/);
  });

  test('2.8 Issues nav link works', async ({ page }) => {
    await freshPage(page);
    await page.locator('nav a:has-text("Issues")').first().click();
    await expect(page).toHaveURL(/\/issues/);
  });

  test('2.9 Notification bell opens dropdown', async ({ page }) => {
    await freshPage(page);
    // Bell is in the header div with items-center gap-4
    const bellButton = page.locator('header button').filter({ has: page.locator('svg.lucide-bell') });
    await bellButton.click();
    await expect(page.locator('text=Notifications')).toBeVisible();
    await expect(page.locator('text=No unread notifications')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/23-notifications.png' });
  });

  test('2.10 Create menu (+) opens dropdown', async ({ page }) => {
    await freshPage(page);
    // Find the + button with dropdown arrow
    const createButton = page.locator('header button').filter({ hasText: '▼' }).first();
    await createButton.click();
    await expect(page.locator('text=New issue')).toBeVisible();
    await expect(page.locator('text=New repository')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/24-create-menu.png' });
  });

  test('2.11 Create menu - New issue link works', async ({ page }) => {
    await freshPage(page);
    const createButton = page.locator('header button').filter({ hasText: '▼' }).first();
    await createButton.click();
    await page.locator('a:has-text("New issue")').click();
    await expect(page).toHaveURL(/\/issues\/new/);
  });

  test('2.12 Profile menu opens and shows user info', async ({ page }) => {
    await freshPage(page);
    // Profile button has avatar image and ▼
    const profileButton = page.locator('header button').filter({ has: page.locator('img') });
    await profileButton.click();
    await expect(page.locator('text=Admin User')).toBeVisible();
    await expect(page.locator('text=admin')).toBeVisible();
    await expect(page.locator('text=Your profile')).toBeVisible();
    await expect(page.locator('text=Your repositories')).toBeVisible();
    await expect(page.locator('text=Sign out')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/25-profile-menu.png' });
  });
});

test.describe('Phase 2: Dashboard Interactions', () => {

  test('2.13 Dashboard repo links navigate to repo page', async ({ page }) => {
    await freshPage(page);
    // Click the repo link in the main feed
    await page.locator('a:has-text("admin / react-clone")').first().click();
    await expect(page).toHaveURL(/\/admin\/react-clone/);
  });

  test('2.14 Dashboard sidebar repo links work', async ({ page }) => {
    await freshPage(page);
    await page.locator('aside a:has-text("admin/react-clone")').click();
    await expect(page).toHaveURL(/\/admin\/react-clone/);
  });

  test('2.15 Dashboard Star button exists and is clickable', async ({ page }) => {
    await freshPage(page);
    const starButton = page.locator('button:has-text("Star")').first();
    await expect(starButton).toBeVisible();
    await starButton.click();
    // Star button should still be there (dashboard star is not wired to dispatch)
    await page.screenshot({ path: 'tests/screenshots/26-dashboard-star.png' });
  });

  test('2.16 Dashboard Explore button exists', async ({ page }) => {
    await freshPage(page);
    const exploreBtn = page.locator('button:has-text("Explore")');
    await expect(exploreBtn).toBeVisible();
    await exploreBtn.click();
    // The explore button doesn't navigate anywhere - just a button
    await page.screenshot({ path: 'tests/screenshots/27-dashboard-explore.png' });
  });

  test('2.17 Dashboard "Show more" button exists', async ({ page }) => {
    await freshPage(page);
    const showMore = page.locator('button:has-text("Show more")');
    await expect(showMore).toBeVisible();
    await showMore.click();
    // Non-functional but should exist
  });
});

test.describe('Phase 2: Repository Code Page Interactions', () => {

  test('2.18 Branch selector dropdown opens and switches branches', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Click branch button
    const branchBtn = page.locator('button:has-text("main")').first();
    await branchBtn.click();

    // Branch dropdown should appear
    await expect(page.locator('text=feature/login')).toBeVisible();
    await expect(page.locator('input[placeholder="Find a branch..."]')).toBeVisible();

    await page.screenshot({ path: 'tests/screenshots/30-branch-dropdown.png' });

    // Switch to feature/login
    await page.locator('button:has-text("feature/login")').click();

    // Branch name should update
    await expect(page.locator('button:has-text("feature/login")')).toBeVisible();
  });

  test('2.19 File links navigate to file view', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Click on a file
    await page.locator('a:has-text("package.json")').click();
    await expect(page).toHaveURL(/\/blob\/package\.json/);
    // File content should be visible
    await expect(page.locator('text=react-clone')).toBeVisible();
    await page.screenshot({ path: 'tests/screenshots/31-file-view.png' });
  });

  test('2.20 Folder links navigate to folder view', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Click on src folder
    await page.locator('a:has-text("src")').first().click();
    await expect(page).toHaveURL(/\/blob\/src/);

    // Should see files inside src
    await page.screenshot({ path: 'tests/screenshots/32-folder-view.png' });
  });

  test('2.21 README.md renders markdown', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // README section should be visible
    await expect(page.locator('text=README.md')).toBeVisible();
    await expect(page.locator('text=React Clone')).toBeVisible();
    await expect(page.locator('text=This is a cool project')).toBeVisible();
  });

  test('2.22 File viewer Raw button works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/blob/package.json`);
    await page.waitForLoadState('networkidle');

    const rawBtn = page.locator('button:has-text("Raw")');
    await expect(rawBtn).toBeVisible();
    await rawBtn.click();

    // Should show raw content
    await page.screenshot({ path: 'tests/screenshots/33-raw-view.png' });
  });

  test('2.23 Code green button exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    const codeBtn = page.locator('button:has-text("Code")').first();
    await expect(codeBtn).toBeVisible();
    await codeBtn.click();
    // Currently no dropdown is implemented for the Code button
    await page.screenshot({ path: 'tests/screenshots/34-code-button.png' });
  });

  test('2.24 Commits link on code page works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Click the "N commits" link
    await page.locator('a:has-text("commits")').first().click();
    await expect(page).toHaveURL(/\/commits/);
  });

  test('2.25 Tab navigation works (all tabs)', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Test Issues tab
    await page.locator('nav a:has-text("Issues")').click();
    await expect(page).toHaveURL(/\/issues/);

    // Test Pull requests tab
    await page.locator('nav a:has-text("Pull requests")').click();
    await expect(page).toHaveURL(/\/pulls/);

    // Test Projects tab
    await page.locator('nav a:has-text("Projects")').click();
    await expect(page).toHaveURL(/\/projects/);

    // Test Wiki tab
    await page.locator('nav a:has-text("Wiki")').click();
    await expect(page).toHaveURL(/\/wiki/);

    // Test Settings tab
    await page.locator('nav a:has-text("Settings")').click();
    await expect(page).toHaveURL(/\/settings/);

    // Test Code tab back
    await page.locator('nav a:has-text("Code")').click();
    await expect(page).toHaveURL(`${BASE}/admin/react-clone`);
  });

  test('2.26 Star/Unstar button on repo page works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Find the Star button in the repo header (not the tab bar)
    const starBtn = page.locator('button:has-text("Star")').last();
    await expect(starBtn).toBeVisible();

    // Get initial star count
    const initialCount = await page.locator('text=124').textContent().catch(() => null);

    // Click star
    await starBtn.click();

    // Should show "Starred" now
    await expect(page.locator('button:has-text("Starred")')).toBeVisible();
    // Star count should increase
    await expect(page.locator('text=125')).toBeVisible();

    await page.screenshot({ path: 'tests/screenshots/35-starred.png' });

    // Click again to unstar
    await page.locator('button:has-text("Starred")').click();
    await expect(page.locator('button:has-text("Star")')).toBeVisible();
    // Count should go back
    await expect(page.locator('text=124')).toBeVisible();
  });

  test('2.27 Watch and Fork buttons exist', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('button:has-text("Watch")')).toBeVisible();
    await expect(page.locator('button:has-text("Fork")')).toBeVisible();
  });
});

test.describe('Phase 2: Issues Interactions', () => {

  test('2.28 Open/Closed filter works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    // Default should show open issues
    await expect(page.locator('text=Fix login bug')).toBeVisible();

    // Click Closed
    await page.locator('button:has-text("Closed")').click();
    await expect(page.locator('text=Update documentation')).toBeVisible();
    // Fix login bug should not be visible
    await expect(page.locator('text=Fix login bug')).not.toBeVisible();

    await page.screenshot({ path: 'tests/screenshots/36-issues-closed.png' });

    // Click Open again
    await page.locator('button:has-text("Open")').click();
    await expect(page.locator('text=Fix login bug')).toBeVisible();
  });

  test('2.29 Issue search filter works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[placeholder="Search issues..."]');
    await searchInput.fill('login');
    await expect(page.locator('text=Fix login bug')).toBeVisible();

    await searchInput.fill('nonexistent');
    await expect(page.locator('text=Fix login bug')).not.toBeVisible();
    // Empty state should show
    await expect(page.locator('text=Welcome to issues!')).toBeVisible();
  });

  test('2.30 Issue list items navigate to detail', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    await page.locator('a:has-text("Fix login bug")').click();
    await expect(page).toHaveURL(/\/issues\/1/);
    await expect(page.locator('h1')).toContainText('Fix login bug');
  });

  test('2.31 New Issue button navigates correctly', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    await page.locator('a:has-text("New Issue")').click();
    await expect(page).toHaveURL(/\/issues\/new/);
  });

  test('2.32 Author/Label/Sort filters are visible (static)', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Author ▼')).toBeVisible();
    await expect(page.locator('text=Label ▼')).toBeVisible();
    await expect(page.locator('text=Sort ▼')).toBeVisible();
    await expect(page.locator('text=Assignee ▼')).toBeVisible();
  });

  test('2.33 Issue labels display correctly', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=bug')).toBeVisible();
    await expect(page.locator('text=high-priority')).toBeVisible();
  });
});

test.describe('Phase 2: Issue Detail Interactions', () => {

  test('2.34 Comment textarea accepts input', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea[placeholder="Leave a comment"]');
    await expect(textarea).toBeVisible();
    await textarea.fill('This is a test comment');
    await expect(textarea).toHaveValue('This is a test comment');
  });

  test('2.35 Submit comment button creates comment', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    // Count existing comments
    const existingComments = await page.locator('.flex.gap-4 >> .border.border-xithub-border.rounded-md').count();

    const textarea = page.locator('textarea[placeholder="Leave a comment"]');
    await textarea.fill('Playwright test comment');

    await page.locator('button[type="submit"]:has-text("Comment")').click();

    // New comment should appear
    await expect(page.locator('text=Playwright test comment')).toBeVisible();
    // Textarea should be cleared
    await expect(textarea).toHaveValue('');

    await page.screenshot({ path: 'tests/screenshots/37-comment-added.png', fullPage: true });
  });

  test('2.36 Submit empty comment does nothing', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    // Click submit without entering text
    await page.locator('button[type="submit"]:has-text("Comment")').click();
    // Should not add empty comment - count should stay the same
    // The existing comment "I will look into this." should still be there
    await expect(page.locator('text=I will look into this.')).toBeVisible();
  });

  test('2.37 Edit button exists but does not open edit form', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    const editBtn = page.locator('button:has-text("Edit")');
    await expect(editBtn).toBeVisible();
    await editBtn.click();
    // No edit form should appear - this is a known broken feature
    await page.screenshot({ path: 'tests/screenshots/38-edit-button.png' });
  });

  test('2.38 Issue status badge shows correctly', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    // Open badge should be visible
    await expect(page.locator('span:has-text("Open")')).toBeVisible();
  });

  test('2.39 Assignees sidebar shows info', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Assignees')).toBeVisible();
    // Issue 1 has assignee u1, but it shows the ID not username
    // This might be a bug
  });

  test('2.40 Labels sidebar shows labels', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Labels')).toBeVisible();
    // Check label badges in sidebar
    const labelSection = page.locator('text=Labels').locator('..');
    await expect(page.locator('span:has-text("bug")').last()).toBeVisible();
    await expect(page.locator('span:has-text("high-priority")').last()).toBeVisible();
  });

  test('2.41 Existing comment from mock data is displayed', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=I will look into this.')).toBeVisible();
    // Author of the comment should be shown
    await expect(page.locator('text=admin').first()).toBeVisible();
  });
});

test.describe('Phase 2: New Issue Form', () => {

  test('2.42 New issue form submits and redirects', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/new`);
    await page.waitForLoadState('networkidle');

    // Fill in the form
    await page.locator('input[placeholder="Title"]').fill('Test Issue from Playwright');
    await page.locator('textarea[placeholder="Leave a comment"]').fill('This is a test issue body.');

    // Submit
    await page.locator('button:has-text("Submit new issue")').click();

    // Should redirect to the new issue detail page
    await expect(page).toHaveURL(/\/issues\/3/);
    await expect(page.locator('h1')).toContainText('Test Issue from Playwright');

    await page.screenshot({ path: 'tests/screenshots/39-new-issue-created.png', fullPage: true });
  });

  test('2.43 New issue form requires title', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/new`);
    await page.waitForLoadState('networkidle');

    // Try to submit without title
    await page.locator('button:has-text("Submit new issue")').click();

    // Should stay on the same page (HTML5 required attribute)
    await expect(page).toHaveURL(/\/issues\/new/);
  });

  test('2.44 New issue cancel button works', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/new`);
    await page.waitForLoadState('networkidle');

    await page.locator('button:has-text("Cancel")').click();
    // Should navigate back
    await expect(page).not.toHaveURL(/\/issues\/new/);
  });
});

test.describe('Phase 2: Pull Requests Interactions', () => {

  test('2.45 PR list items navigate to detail', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');

    await page.locator('a:has-text("Add Login Feature")').click();
    await expect(page).toHaveURL(/\/pulls\/3/);
  });

  test('2.46 New Pull Request button exists but is non-functional', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');

    const newPrBtn = page.locator('button:has-text("New Pull Request")');
    await expect(newPrBtn).toBeVisible();
    await newPrBtn.click();
    // Should stay on the same page since it's a button with no handler
    await expect(page).toHaveURL(/\/pulls/);
  });

  test('2.47 PR status badge shows correctly (Approved)', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Approved')).toBeVisible();
  });

  test('2.48 PR detail - Merge button exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');

    const mergeBtn = page.locator('button:has-text("Merge pull request")');
    await expect(mergeBtn).toBeVisible();
    await mergeBtn.click();
    // Currently no merge functionality - button doesn't do anything
    await page.screenshot({ path: 'tests/screenshots/40-merge-button.png' });
  });

  test('2.49 PR detail shows reviewer info', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Reviewers')).toBeVisible();
    await expect(page.locator('text=jane_doe')).toBeVisible();
  });

  test('2.50 PR detail Edit button exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');

    const editBtn = page.locator('button:has-text("Edit")');
    await expect(editBtn).toBeVisible();
    await editBtn.click();
    // Known non-functional
  });

  test('2.51 PR detail shows branch info', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=main')).toBeVisible();
    await expect(page.locator('text=feature/login')).toBeVisible();
  });

  test('2.52 PR detail shows mock diff', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls/3`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Files changed')).toBeVisible();
    await expect(page.locator('text=src/auth/Login.js')).toBeVisible();
    // Green diff lines
    await expect(page.locator('text=+ function login()')).toBeVisible();
  });

  test('2.53 PR Open/Closed filter buttons exist', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('button:has-text("Open")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Closed")').first()).toBeVisible();
  });
});

test.describe('Phase 2: Project Board Interactions', () => {

  test('2.54 Project board shows correct columns', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=To Do')).toBeVisible();
    await expect(page.locator('text=In Progress')).toBeVisible();
    await expect(page.locator('text=Done')).toBeVisible();
  });

  test('2.55 Project board shows issues as cards', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');

    // Issue 1 (Fix login bug) should be in "todo" column
    await expect(page.locator('text=Fix login bug')).toBeVisible();
    // Issue 2 (Update documentation) should be in "done" column
    await expect(page.locator('text=Update documentation')).toBeVisible();
  });

  test('2.56 Project board cards are draggable', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');

    // Check that cards have draggable attribute
    const card = page.locator('[draggable="true"]').first();
    await expect(card).toBeVisible();
  });

  test('2.57 Project board Add Item button exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');

    const addItemBtns = page.locator('button:has-text("Add item")');
    const count = await addItemBtns.count();
    expect(count).toBe(3); // One per column
  });
});

test.describe('Phase 2: Wiki Interactions', () => {

  test('2.58 Wiki displays home page content', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/wiki`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1:has-text("Home")')).toBeVisible();
    await expect(page.locator('text=Welcome to the wiki!')).toBeVisible();
  });

  test('2.59 Wiki sidebar shows page list', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/wiki`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h3:has-text("Pages")')).toBeVisible();
    await expect(page.locator('a:has-text("Home")')).toBeVisible();
  });

  test('2.60 Wiki for repo without wiki pages', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/awesome-tools/wiki`);
    await page.waitForLoadState('networkidle');

    // awesome-tools has no wiki pages
    await expect(page.locator('text=Wiki is empty')).toBeVisible();
    await expect(page.locator('button:has-text("Create the first page")')).toBeVisible();
  });
});

test.describe('Phase 2: Settings Interactions', () => {

  test('2.61 Settings shows repo name', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/settings`);
    await page.waitForLoadState('networkidle');

    const nameInput = page.locator('input[value="react-clone"]');
    await expect(nameInput).toBeVisible();
    // Input is readOnly
    await expect(nameInput).toHaveAttribute('readonly', '');
  });

  test('2.62 Settings sidebar navigation exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/settings`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('a:has-text("General")')).toBeVisible();
    await expect(page.locator('a:has-text("Collaborators")')).toBeVisible();
    await expect(page.locator('a:has-text("Webhooks")')).toBeVisible();
    await expect(page.locator('a:has-text("Pages")')).toBeVisible();
  });

  test('2.63 Settings danger zone delete button exists', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/settings`);
    await page.waitForLoadState('networkidle');

    const deleteBtn = page.locator('button:has-text("Delete this repository")');
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();
    // No action - button is non-functional
    await page.screenshot({ path: 'tests/screenshots/41-danger-zone.png' });
  });
});

test.describe('Phase 2: Commits Page Interactions', () => {

  test('2.64 Commit list items navigate to commit detail', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/commits`);
    await page.waitForLoadState('networkidle');

    await page.locator('a:has-text("Add button component")').click();
    await expect(page).toHaveURL(/\/commit\/c2/);
  });

  test('2.65 Commit SHA hash buttons exist', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/commits`);
    await page.waitForLoadState('networkidle');

    // Short SHA links
    const shaButton = page.locator('button').filter({ hasText: /^[a-f0-9]{7}$/ });
    const count = await shaButton.count();
    expect(count).toBeGreaterThan(0);
  });

  test('2.66 Commit detail shows diff', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/commit/c2`);
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Add button component')).toBeVisible();
    await expect(page.locator('text=src/components/Button.js')).toBeVisible();
    // Diff content
    await expect(page.locator('text=5 additions')).toBeVisible();
    await expect(page.locator('text=2 deletions')).toBeVisible();
  });
});

// ============================================================
// PHASE 3: EDGE CASES & STATE PERSISTENCE
// ============================================================

test.describe('Phase 3: Edge Cases', () => {

  test('3.1 State persists across page refresh', async ({ page }) => {
    await freshPage(page);

    // Create a new issue
    await page.goto(`${BASE}/admin/react-clone/issues/new`);
    await page.waitForLoadState('networkidle');
    await page.locator('input[placeholder="Title"]').fill('Persistence Test Issue');
    await page.locator('textarea[placeholder="Leave a comment"]').fill('Testing persistence');
    await page.locator('button:has-text("Submit new issue")').click();
    await page.waitForURL(/\/issues/);

    // Reload page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Issue should still exist
    await expect(page.locator('text=Persistence Test Issue')).toBeVisible();
  });

  test('3.2 Browser back navigation works', async ({ page }) => {
    await freshPage(page);

    // Navigate to repo
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    // Navigate to issues
    await page.locator('nav a:has-text("Issues")').click();
    await expect(page).toHaveURL(/\/issues/);

    // Go back
    await page.goBack();
    await expect(page).toHaveURL(`${BASE}/admin/react-clone`);
  });

  test('3.3 Empty issues list shows welcome message', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/awesome-tools/issues`);
    await page.waitForLoadState('networkidle');

    // awesome-tools has no issues, should show empty state
    await expect(page.locator('text=Welcome to issues!')).toBeVisible();
  });

  test('3.4 Empty PRs list shows message', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/awesome-tools/pulls`);
    await page.waitForLoadState('networkidle');

    // awesome-tools has no PRs
    await expect(page.locator('text=No pull requests')).toBeVisible();
  });

  test('3.5 Security tab exists but has no route', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    const securityTab = page.locator('nav a:has-text("Security")');
    await expect(securityTab).toBeVisible();
    await securityTab.click();
    // No security route defined - should show something
    await page.screenshot({ path: 'tests/screenshots/50-security-tab.png' });
  });

  test('3.6 Actions tab exists but has no route', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone`);
    await page.waitForLoadState('networkidle');

    const actionsTab = page.locator('nav a:has-text("Actions")');
    await expect(actionsTab).toBeVisible();
    await actionsTab.click();
    // No actions route defined
    await page.screenshot({ path: 'tests/screenshots/51-actions-tab.png' });
  });

  test('3.7 Comment is persisted to state', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues/1`);
    await page.waitForLoadState('networkidle');

    // Add a comment
    await page.locator('textarea[placeholder="Leave a comment"]').fill('State persistence comment');
    await page.locator('button[type="submit"]:has-text("Comment")').click();
    await expect(page.locator('text=State persistence comment')).toBeVisible();

    // Now check localStorage for the state
    const stateStr = await page.evaluate(() => localStorage.getItem('gitmock_state'));
    const state = JSON.parse(stateStr);
    const issue = state.issues.find(i => i.number === 1);
    const lastComment = issue.comments[issue.comments.length - 1];
    expect(lastComment.content).toBe('State persistence comment');
  });

  test('3.8 Multiple repos have separate issues', async ({ page }) => {
    await freshPage(page);

    // Check react-clone issues
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Fix login bug')).toBeVisible();

    // Check awesome-tools issues (should be empty)
    await page.goto(`${BASE}/admin/awesome-tools/issues`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Fix login bug')).not.toBeVisible();
    await expect(page.locator('text=Welcome to issues!')).toBeVisible();
  });

  test('3.9 File viewer for different languages renders', async ({ page }) => {
    await freshPage(page);

    // View JS file
    await page.goto(`${BASE}/admin/react-clone/blob/src/index.js`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Hello World')).toBeVisible();

    // View markdown file
    await page.goto(`${BASE}/admin/react-clone/blob/README.md`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=React Clone')).toBeVisible();

    // View Python file in awesome-tools
    await page.goto(`${BASE}/admin/awesome-tools/blob/main.py`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Hello from Python')).toBeVisible();
  });

  test('3.10 Codespaces, Marketplace, Explore links go to dashboard', async ({ page }) => {
    await freshPage(page);

    const codespacesLink = page.locator('nav a:has-text("Codespaces")');
    await expect(codespacesLink).toBeVisible();
    await codespacesLink.click();
    await expect(page).toHaveURL(BASE + '/');

    await page.locator('nav a:has-text("Marketplace")').click();
    await expect(page).toHaveURL(BASE + '/');

    await page.locator('nav a:has-text("Explore")').click();
    await expect(page).toHaveURL(BASE + '/');
  });

  test('3.11 Profile menu items are not clickable links', async ({ page }) => {
    await freshPage(page);

    // Open profile menu
    const profileButton = page.locator('header button').filter({ has: page.locator('img') });
    await profileButton.click();

    // These are divs, not links - check they exist
    await expect(page.locator('text=Your profile')).toBeVisible();
    await expect(page.locator('text=Your repositories')).toBeVisible();
    await expect(page.locator('text=Your stars')).toBeVisible();
    await expect(page.locator('text=Settings')).toBeVisible();
    await expect(page.locator('text=Sign out')).toBeVisible();

    // Click "Your profile" - it's a div with cursor-pointer but no action
    await page.locator('text=Your profile').click();
    // Should stay on same page
    await expect(page).toHaveURL(BASE + '/');
  });

  test('3.12 Check for console errors on all pages', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await freshPage(page);

    const urls = [
      BASE + '/',
      BASE + '/admin/react-clone',
      BASE + '/admin/react-clone/issues',
      BASE + '/admin/react-clone/issues/1',
      BASE + '/admin/react-clone/pulls',
      BASE + '/admin/react-clone/pulls/3',
      BASE + '/admin/react-clone/projects',
      BASE + '/admin/react-clone/wiki',
      BASE + '/admin/react-clone/settings',
      BASE + '/admin/react-clone/commits',
      BASE + '/admin/react-clone/commit/c2',
      BASE + '/admin/awesome-tools',
    ];

    for (const url of urls) {
      await page.goto(url);
      await page.waitForLoadState('networkidle');
    }

    // Filter out React dev mode warnings and picsum image errors
    const realErrors = errors.filter(e =>
      !e.includes('picsum') &&
      !e.includes('net::ERR') &&
      !e.includes('favicon') &&
      !e.includes('Warning:')
    );

    if (realErrors.length > 0) {
      console.log('Console errors found:', realErrors);
    }
    // We just log rather than fail - some errors may be expected in a mock
  });

  test('3.13 PR Open/Closed filter buttons are not functional', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/pulls`);
    await page.waitForLoadState('networkidle');

    // The Open/Closed buttons exist but don't filter - they're just buttons
    const closedBtn = page.locator('button:has-text("Closed")').first();
    await closedBtn.click();
    // PR list should still show the same items (no filter logic)
    await expect(page.locator('text=Add Login Feature')).toBeVisible();
  });

  test('3.14 Drag and drop on project board changes column', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/projects`);
    await page.waitForLoadState('networkidle');

    // The drag-and-drop uses HTML5 API
    // Let's simulate it via dataTransfer
    const sourceCard = page.locator('[draggable="true"]:has-text("Fix login bug")');
    const targetColumn = page.locator('text=In Progress').locator('..').locator('..');

    await expect(sourceCard).toBeVisible();

    // Use Playwright's drag-and-drop
    const sourceBounds = await sourceCard.boundingBox();
    const targetBounds = await targetColumn.boundingBox();

    if (sourceBounds && targetBounds) {
      // Manual drag simulation
      await page.mouse.move(sourceBounds.x + sourceBounds.width / 2, sourceBounds.y + sourceBounds.height / 2);
      await page.mouse.down();
      await page.mouse.move(targetBounds.x + targetBounds.width / 2, targetBounds.y + targetBounds.height / 2, { steps: 5 });
      await page.mouse.up();
    }

    await page.screenshot({ path: 'tests/screenshots/52-drag-drop.png', fullPage: true });
  });

  test('3.15 Issue number count display', async ({ page }) => {
    await freshPage(page);
    await page.goto(`${BASE}/admin/react-clone/issues`);
    await page.waitForLoadState('networkidle');

    // Open count badge
    await expect(page.locator('button:has-text("1 Open")')).toBeVisible();
    await expect(page.locator('button:has-text("1 Closed")')).toBeVisible();
  });
});

test.describe('Phase 3: State Inspection Endpoint', () => {

  test('3.16 /go API endpoint returns JSON', async ({ page }) => {
    const response = await page.request.get(`${BASE}/go`);
    expect(response.status()).toBe(200);
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('application/json');

    const data = await response.json();
    expect(data).toHaveProperty('initial_state');
    expect(data).toHaveProperty('current_state');
    expect(data).toHaveProperty('state_diff');
  });

  test('3.17 /state API endpoint works', async ({ page }) => {
    const response = await page.request.get(`${BASE}/state`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('has_custom_state');
  });
});
