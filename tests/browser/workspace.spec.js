import { test, expect } from '@playwright/test';

async function menu(page, action) {
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: action, exact: true }).click();
}
async function start(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await expect(page.locator('#workspace-view')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
}
async function type(page, name = 'Tools') {
  await menu(page, 'Settings');
  await page.getByRole('link', { name: 'Manage Tana Types' }).click();
  await page.getByRole('link', { name: 'Add type', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Save type' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText(name);
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
}
async function item(page, name = 'Garden hammer') {
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await page.getByRole('link', { name: 'Add item', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill(name);
  await page.getByRole('combobox', { name: 'Item type', exact: true }).click();
  await page.getByRole('option', { name: 'Tools', exact: true }).click();
  await page.getByRole('button', { name: 'Save item' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText(name);
}

test.beforeEach(async ({ page }) => {
  page.on('pageerror', error => { throw error; });
  await start(page);
});

test('partial navigation preserves shell, title, history, theme and sidebar preference', async ({ page }) => {
  await page.locator('.app-header').evaluate(el => el.dataset.testIdentity = 'same-header');
  await page.locator('.sidebar').evaluate(el => el.dataset.testIdentity = 'same-sidebar');
  await page.locator('[data-theme-toggle]').click();
  await page.locator('[data-sidebar-toggle]').click();
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'collapsed');
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await expect(page).toHaveURL(/\/tana\/items\/$/);
  await expect(page).toHaveTitle('My Tana · TanaSpace');
  await page.evaluate(() => history.back());
  await expect(page.getByRole('heading', { name: /Welcome home/ })).toBeVisible();
  await page.evaluate(() => history.forward());
  await expect(page.getByRole('heading', { name: 'My Tana', exact: true })).toBeVisible();
  await expect(page.locator('.app-header')).toHaveAttribute('data-test-identity', 'same-header');
  await expect(page.locator('.sidebar')).toHaveAttribute('data-test-identity', 'same-sidebar');
  const theme = await page.locator('html').getAttribute('data-theme');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'collapsed');
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
  await expect(page.locator('[data-nav=items]')).toHaveAttribute('aria-current', 'page');
  expect(await page.evaluate(() => scrollY)).toBe(0);
});

test('mobile drawer and account menu have keyboard focus and dismissal behavior', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await page.getByRole('button', { name: 'Expand navigation' }).click();
  await expect(page.locator('#workspace-sidebar')).toHaveAttribute('aria-modal', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('[data-sidebar-toggle]')).toBeFocused();
  await page.getByRole('button', { name: 'Expand navigation' }).click();
  await page.getByRole('link', { name: 'Favorites', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Favorites', exact: true })).toBeVisible();
  await expect(page.locator('body')).not.toHaveClass(/drawer-open/);
  await page.getByRole('button', { name: 'Account menu' }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('menuitem', { name: 'Profile', exact: true })).toBeFocused();
  await page.keyboard.press('End');
  await expect(page.getByRole('menuitem', { name: 'Log out', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('profile saves immediately, rejects invalid data, and confirms navigation away', async ({ page }) => {
  await menu(page, 'Profile');
  await page.getByLabel('Nickname', { exact: true }).fill('Shelf keeper');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Your profile has been saved.')).toBeVisible();
  await expect(page.locator('#account-display-name')).toHaveText('Shelf keeper');
  await page.getByLabel('Nickname', { exact: true }).fill('Unsaved nickname');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await expect(page).toHaveURL(/\/tana\/profile\/$/);
  page.once('dialog', dialog => dialog.dismiss());
  await page.evaluate(() => history.back());
  await expect(page).toHaveURL(/\/tana\/profile\/$/);
  await expect(page.getByLabel('Nickname', { exact: true })).toHaveValue('Unsaved nickname');
  await page.locator('form[data-dirty-check]').evaluate(form => form.noValidate = true);
  await page.getByLabel('Nickname', { exact: true }).evaluate(input => input.value = 'x'.repeat(81));
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.locator('.field-errors')).toBeVisible();
  await expect(page.locator('#account-display-name')).toHaveText('Shelf keeper');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.locator('.welcome-panel')).toContainText('Shelf keeper');
});

test('windows retain the underlying page and support item editing, favorites and deletion', async ({ page }) => {
  await type(page);
  await item(page);
  await expect(page.locator('#main')).toHaveAttribute('inert', '');
  await page.getByRole('link', { name: 'Edit item', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill('Updated hammer');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Updated hammer');
  await page.getByRole('button', { name: 'Add to favorites' }).click();
  await expect(page.getByRole('button', { name: 'Remove from favorites' })).toBeVisible();
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await page.getByRole('link', { name: 'Favorites', exact: true }).click();
  await page.getByRole('link', { name: 'View Updated hammer' }).click();
  await page.getByRole('link', { name: 'Delete', exact: true }).click();
  await page.getByRole('button', { name: 'Delete item' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await expect(page.getByText('No favorites yet.')).toBeVisible();
  await expect(page).toHaveURL(/\/tana\/favorites\/$/);
  await expect(page).toHaveTitle('Favorites · TanaSpace');
});

test('bound validation retains edits and window close returns to the filtered origin', async ({ page }) => {
  await type(page);
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search value' }).fill('hammer');
  await page.locator('.item-search button[type=submit]').click();
  await expect(page).toHaveURL(/value=hammer/);
  await page.locator('#main').evaluate(el => el.dataset.identity = 'underlying');
  await page.getByRole('link', { name: 'Add item', exact: true }).click();
  await expect(page.locator('#main')).toHaveAttribute('data-identity', 'underlying');
  await page.locator('#modal-host form').evaluate(form => form.noValidate = true);
  await page.getByLabel('Notes', { exact: true }).fill('Do not lose this note');
  await page.getByRole('button', { name: 'Save item' }).click();
  await expect(page.locator('.field-errors').first()).toBeVisible();
  await expect(page.getByLabel('Notes', { exact: true })).toHaveValue('Do not lose this note');
  page.once('dialog', dialog => dialog.dismiss());
  await page.keyboard.press('Escape');
  await expect(page.locator('[role=dialog]')).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.keyboard.press('Escape');
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await expect(page).toHaveURL(/value=hammer/);
});

test('direct window visits close safely, and protected types remain visible', async ({ page }) => {
  await type(page);
  await item(page);
  const direct = new URL(page.url()).pathname;
  await page.goto(direct);
  await page.getByRole('link', { name: 'Edit item', exact: true }).click();
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await expect(page).toHaveURL(/\/tana\/items\/$/);
  await menu(page, 'Settings');
  await page.getByRole('link', { name: 'Manage Tana Types' }).click();
  await page.getByRole('link', { name: 'View Tools' }).click();
  await page.getByRole('link', { name: 'Delete', exact: true }).click();
  await expect(page.getByText('This type is used by items. Move or delete those items first.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete type' })).toHaveCount(0);
});

test('late responses and server errors cannot overwrite a newer navigation', async ({ page }) => {
  await page.route('**/tana/items/', async route => {
    await new Promise(resolve => setTimeout(resolve, 500));
    await route.continue().catch(() => {});
  });
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await expect(page.locator('#workspace-view')).toHaveAttribute('inert', '');
  await page.getByRole('link', { name: 'Favorites', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Favorites', exact: true })).toBeVisible();
  await page.waitForTimeout(700);
  await expect(page).toHaveURL(/\/tana\/favorites\/$/);
  await page.unroute('**/tana/items/');
  await page.route('**/tana/items/', route => route.fulfill({ status: 500, body: '<h1>Server failure</h1>' }));
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await expect(page.locator('#workspace-status')).toContainText('Unable to load');
  await expect(page.getByRole('heading', { name: 'Favorites', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/tana\/favorites\/$/);
});

test('expired authentication exits the workspace instead of embedding the landing page', async ({ page, context }) => {
  await context.clearCookies();
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await expect(page).toHaveURL(/\/\?next=/);
  await expect(page.locator('#workspace-view')).toHaveCount(0);
});

test('ordinary forms and window URLs still work with JavaScript disabled', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('/');
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await page.goto('/tana/item_types/');
  await page.getByRole('link', { name: 'Add type', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill('No JS type');
  await page.getByRole('button', { name: 'Save type' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('No JS type');
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.getByRole('heading', { name: 'Tana Types', exact: true })).toBeVisible();
  await page.goto('/tana/items/');
  await page.getByRole('link', { name: 'Add item', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill('Native select item');
  await page.getByLabel('Item type', { exact: true }).selectOption({ label: 'No JS type' });
  await page.getByRole('button', { name: 'Save item' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Native select item');
  await page.getByRole('link', { name: 'Close window' }).click();
  await page.getByRole('menuitem', { name: 'Log out', exact: true }).click();
  await expect(page).toHaveURL('/');
  await context.close();
});

test('modal Back/Forward states and deleted-record history recover safely', async ({ page }) => {
  await type(page);
  await item(page);
  await page.getByRole('link', { name: 'Edit item', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Edit Garden hammer');
  await page.evaluate(() => history.back());
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await page.evaluate(() => history.forward());
  await expect(page.locator('#modal-host h2')).toHaveText('Edit Garden hammer');
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await expect(page).toHaveTitle('My Tana · TanaSpace');
  await page.evaluate(() => history.forward());
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await page.getByRole('link', { name: 'Delete', exact: true }).click();
  await page.getByRole('button', { name: 'Delete item' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await page.evaluate(() => history.forward());
  await expect(page.locator('#workspace-status')).toContainText('unavailable');
  await expect(page).toHaveURL(/\/tana\/items\/$/);
});

test('responsive shell keeps content scrollable and drawer/window focus isolated', async ({ page }) => {
  await type(page);
  await item(page);
  await page.getByRole('link', { name: 'Close window' }).click();
  for (const [width, height] of [[1440, 900], [900, 600], [768, 600], [390, 700], [320, 568]]) {
    await page.setViewportSize({ width, height });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(height);
  }
  await page.getByRole('button', { name: 'Expand navigation' }).click();
  await page.locator('.drawer-scrim').click({ position: { x: 310, y: 300 }, force: true });
  await expect(page.locator('body')).not.toHaveClass(/drawer-open/);
  await page.getByRole('link', { name: 'View Garden hammer' }).click();
  await expect(page.locator('#main')).toHaveAttribute('inert', '');
  const first = page.getByRole('link', { name: 'Close window' });
  await first.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('link', { name: 'Edit item', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(first).toBeFocused();
});

test.afterEach(async ({ page, context }) => {
  const cookies = await context.cookies();
  const token = cookies.find(cookie => cookie.name === 'csrftoken')?.value;
  if (token && cookies.some(cookie => cookie.name === 'sessionid')) {
    await page.request.post('/accounts/logout/', { form: { csrfmiddlewaretoken: token } });
  }
});

test('sidebar branding stays inside navigation when collapsed and expanded', async ({ page }) => {
  const sidebar = page.locator('#workspace-sidebar');
  const brand = sidebar.locator('.sidebar-brand');
  const logo = brand.locator('.brand-logo');
  const name = brand.locator('.sidebar-brand-name');
  const toggle = page.locator('[data-sidebar-toggle]');
  await expect(logo).toBeVisible();
  await expect(name).toBeVisible();
  const expandedSidebar = await sidebar.boundingBox();
  const expandedLogo = await logo.boundingBox();
  const expandedToggle = await toggle.boundingBox();
  expect(expandedLogo.x).toBeGreaterThanOrEqual(expandedSidebar.x);
  expect(expandedToggle.x).toBeGreaterThan(expandedLogo.x + expandedLogo.width);

  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'collapsed');
  await expect(name).toBeHidden();
  await expect(logo).toBeVisible();
  await expect.poll(async () => (await sidebar.boundingBox()).width).toBeLessThan(expandedSidebar.width);
  const collapsedSidebar = await sidebar.boundingBox();
  const collapsedToggle = await toggle.boundingBox();
  expect(collapsedToggle.x).toBeGreaterThan(collapsedSidebar.x);

  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'expanded');
  await expect(name).toBeVisible();
  await expect.poll(async () => Math.round((await sidebar.boundingBox()).width)).toBe(Math.round(expandedSidebar.width));
});

test('pointer opening the account menu does not autofocus the first option', async ({ page }) => {
  const avatar = page.getByRole('button', { name: 'Account menu' });
  const profile = page.getByRole('menuitem', { name: 'Profile', exact: true });
  await avatar.click();
  await expect(avatar).toBeFocused();
  await expect(profile).not.toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(profile).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(avatar).toBeFocused();
  await expect(page.locator('#account-menu')).toHaveAttribute('inert', '');
});

test('themed select supports keyboard selection, Escape isolation, and form submission', async ({ page }) => {
  await type(page);
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  await page.getByRole('link', { name: 'Add item', exact: true }).click();
  const combo = page.getByRole('combobox', { name: 'Item type', exact: true });
  await page.getByLabel('Name', { exact: true }).fill('Keyboard selected item');
  await page.getByRole('button', { name: 'Save item' }).click();
  await expect(page.locator('#modal-host .select-error')).toBeVisible();
  await expect(combo).toBeFocused();
  await combo.focus();
  await page.keyboard.press('ArrowDown');
  await expect(combo).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('End');
  await page.keyboard.press('Escape');
  await expect(combo).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('[role=dialog]')).toBeVisible();
  await expect(page.locator('select[name=item_type]')).toHaveValue('');
  await combo.click();
  const list = page.getByRole('listbox');
  await expect(list.getByRole('option', { name: 'Choose an option' })).toHaveCount(0);
  const dimensions = await list.evaluate(element => ({
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  }));
  expect(dimensions.scrollHeight).toBe(dimensions.clientHeight);
  const box = await list.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(900);
  await page.keyboard.type('Tools');
  await page.keyboard.press('Enter');
  await expect(combo).toContainText('Tools');
  await page.getByLabel('Name', { exact: true }).fill('Keyboard selected item');
  await page.getByRole('button', { name: 'Save item' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Keyboard selected item');
  await expect(page.getByRole('link', { name: 'Close window' })).toHaveText('');
  await expect(page.getByRole('link', { name: 'Edit item', exact: true }).locator('svg')).toHaveCount(1);
});

test('closing and saving windows never exposes the native select behind the custom control', async ({ page }) => {
  await type(page);
  await page.getByRole('link', { name: 'My Tana', exact: true }).click();
  async function checkSelection() {
    await expect(page.locator('#main')).not.toHaveClass(/htmx-settling/);
    await expect(page.getByRole('combobox', { name: 'Search by' })).toHaveCount(1);
    await expect(page.getByRole('textbox', { name: 'Search value' })).toHaveCount(1);
  }
  for (let repeat = 0; repeat < 3; repeat++) {
    await page.locator('#main').evaluate(el => el.dataset.beforeWindow = 'original');
    await page.getByRole('link', { name: 'Add item', exact: true }).click();
    await page.getByRole('link', { name: 'Close window' }).click();
    await expect(page.locator('#main')).not.toHaveAttribute('data-before-window', 'original');
    await checkSelection();
  }
  await item(page, 'Selection regression item');
  await expect(page.locator('#main')).not.toHaveClass(/htmx-settling/);
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await checkSelection();
});

test('Back from a protected type deletion does not reopen deletion when detail closes', async ({ page }) => {
  await type(page);
  await item(page);
  await page.getByRole('link', { name: 'Close window' }).click();
  await menu(page, 'Settings');
  await page.getByRole('link', { name: 'Manage Tana Types' }).click();
  for (let repeat = 0; repeat < 2; repeat++) {
    await page.getByRole('link', { name: 'View Tools' }).click();
    await page.getByRole('link', { name: 'Delete', exact: true }).click();
    await expect(page.locator('#modal-host h2')).toHaveText('Delete Tools?');
    await page.getByRole('link', { name: 'Back', exact: true }).click();
    await expect(page.locator('#modal-host h2')).toHaveText('Tools');
    await page.getByRole('link', { name: 'Close window' }).click();
    await expect(page.locator('[role=dialog]')).toHaveCount(0);
    await expect(page).toHaveURL(/\/tana\/item_types\/$/);
    await expect(page).toHaveTitle('Tana Types · TanaSpace');
  }
});

test('delete cancellation reverses the window and direct-delete fallback stays inside the app', async ({ page }) => {
  await type(page);
  await item(page);
  const detailURL = new URL(page.url()).pathname;
  await page.getByRole('link', { name: 'Delete', exact: true }).click();
  await page.getByRole('link', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await page.goto(detailURL + 'delete/');
  await page.getByRole('link', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Garden hammer');
  await expect(page).toHaveURL(new RegExp(detailURL));
  await page.getByRole('link', { name: 'Close window' }).click();
  await expect(page.locator('[role=dialog]')).toHaveCount(0);
  await expect(page).toHaveURL(/\/tana\/items\/$/);
});
