import { test, expect } from '@playwright/test';

test.beforeEach(({ page }) => { page.on('pageerror', error => { throw error; }); });

async function start(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await expect(page.locator('#workspace-view')).toBeVisible();
}
async function newType(page, name) {
  await page.goto('/tana/item_types/');
  await page.getByRole('link', { name: 'Add type', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Save type' }).click();
  await expect(page.locator('#modal-host h2')).toHaveText(name);
  await expect(page).toHaveURL(/\/item_types\/\d+\//);
  return new URL(page.url()).pathname.match(/\d+/)[0];
}
async function select(page, label, option) {
  await page.getByRole('combobox', { name: label, exact: true }).click();
  await page.getByRole('option', { name: option, exact: true }).click();
}
async function property(page, name, kind = 'Text', configure) {
  await page.getByRole('link', { name: 'Add property', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Add property');
  await page.getByLabel('Name', { exact: true }).fill(name);
  await select(page, 'Data type', kind);
  if (configure) await configure();
  await page.getByRole('button', { name: 'Save property', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toContainText('Edit ');
}

test('property editor, dynamic item fields, renamed labels, and archived values work together', async ({ page }) => {
  await start(page);
  const typeID = await newType(page, 'Devices');
  await property(page, 'Brand', 'Text', () => page.getByLabel('Required', { exact: true }).check());
  await property(page, 'Wattage', 'Number');
  await property(page, 'Purchased', 'Date');
  await property(page, 'Warranty', 'Boolean');
  await property(page, 'Unit', 'Dropdown', () => page.getByLabel('Label', { exact: true }).fill('Each'));
  await page.goto('/tana/items/');
  await page.getByRole('link', { name: 'Add item', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill('Laptop');
  await select(page, 'Item type', 'Devices');
  await expect(page.getByLabel('Brand', { exact: true })).toBeVisible();
  await page.getByLabel('Brand', { exact: true }).fill('ACME');
  await page.getByLabel('Wattage', { exact: true }).fill('65.125');
  await page.getByLabel('Purchased', { exact: true }).fill('2026-01-02');
  await page.getByLabel('Warranty', { exact: true }).check();
  await select(page, 'Unit', 'Each');
  await page.getByRole('button', { name: 'Save item', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Laptop');
  const detailURL = page.url();
  for (const value of ['ACME', '65.125', 'Jan 2, 2026', 'Yes', 'Each']) await expect(page.locator('#modal-host')).toContainText(value);
  await page.goto(`/tana/item_types/${typeID}/edit/`);
  await page.getByRole('link', { name: 'Edit Brand', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Edit Brand');
  await page.getByLabel('Name', { exact: true }).fill('Manufacturer');
  await page.getByRole('button', { name: 'Save property', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Archive Manufacturer' })).toBeVisible();
  await page.getByRole('link', { name: 'Archive Manufacturer' }).click();
  await page.getByRole('button', { name: 'Archive property', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Edit Devices');
  await page.goto(detailURL);
  await page.locator('.archived-properties summary').click();
  await expect(page.locator('.archived-properties')).toContainText('ACME');
  await page.getByRole('link', { name: 'Edit item', exact: true }).click();
  await expect(page.getByLabel('Manufacturer', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Laptop');
});

test('type switching preserves core drafts and requires confirmation before clearing values', async ({ page }) => {
  await start(page);
  await newType(page, 'Tools');
  await property(page, 'Serial');
  await newType(page, 'Books');
  await property(page, 'Author', 'Text', () => page.getByLabel('Required', { exact: true }).check());
  await page.goto('/tana/items/new/');
  await page.getByLabel('Name', { exact: true }).fill('My item');
  await select(page, 'Item type', 'Tools');
  await page.getByLabel('Serial', { exact: true }).fill('S-123');
  await page.getByRole('button', { name: 'Save item', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('My item');
  await page.getByRole('link', { name: 'Edit item', exact: true }).click();
  await page.getByLabel('Notes', { exact: true }).fill('Core draft');
  await select(page, 'Item type', 'Books');
  await page.getByLabel('Author', { exact: true }).fill('Writer');
  await expect(page.getByLabel('Notes', { exact: true })).toHaveValue('Core draft');
  await expect(page.getByLabel(/Clear the previous type/)).not.toBeChecked();
  await select(page, 'Item type', 'Tools');
  await expect(page.getByLabel('Serial', { exact: true })).toHaveValue('S-123');
  await select(page, 'Item type', 'Books');
  await expect(page.getByLabel('Author', { exact: true })).toHaveValue('Writer');
  await page.getByLabel(/Clear the previous type/).check();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('My item');
  await expect(page.locator('#modal-host')).toContainText('Writer');
  await expect(page.locator('#modal-host')).not.toContainText('S-123');
});

test('failed property loading blocks saving and can be retried without reloading the window', async ({ page }) => {
  await start(page);
  await newType(page, 'Tools');
  await property(page, 'Serial');
  await page.goto('/tana/items/new/');
  await page.getByLabel('Name', { exact: true }).fill('Draft');
  const windowURL = page.url();
  await page.route('**/tana/items/custom-fields/', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await select(page, 'Item type', 'Tools');
  await expect(page.getByRole('button', { name: 'Save item', exact: true })).toBeDisabled();
  await expect(page.locator('#workspace-status')).toContainText('Could not load properties');
  await page.unroute('**/tana/items/custom-fields/');
  await page.getByRole('button', { name: 'Load properties', exact: true }).click();
  await expect(page.getByLabel('Serial', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save item', exact: true })).toBeEnabled();
  expect(page.url()).toBe(windowURL);
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Draft');
});

test('custom property workflows work without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await start(page);
  await newType(page, 'Native type');
  await page.getByRole('link', { name: 'Add property', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Add property');
  await page.getByLabel('Name', { exact: true }).fill('Brand');
  await page.getByLabel('Data type', { exact: true }).selectOption('text');
  await page.getByLabel('Required', { exact: true }).check();
  await page.getByRole('button', { name: 'Save property', exact: true }).click();
  await page.goto('/tana/items/new/');
  await page.getByLabel('Name', { exact: true }).fill('No JS item');
  await page.getByLabel('Item type', { exact: true }).selectOption({ label: 'Native type' });
  await page.getByRole('button', { name: 'Load properties', exact: true }).click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('No JS item');
  await page.getByLabel('Brand', { exact: true }).fill('ACME');
  await page.getByRole('button', { name: 'Save item', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('No JS item');
  await expect(page.locator('#modal-host')).toContainText('ACME');
  await context.close();
});

test('dropdown options can be added and property ordering uses the latest schema', async ({ page }) => {
  await start(page);
  await newType(page, 'Food');
  await property(page, 'Quantity', 'Number');
  await property(page, 'Unit', 'Dropdown', async () => {
    await page.getByLabel('Label', { exact: true }).fill('Each');
    await page.getByRole('button', { name: 'Add option', exact: true }).click();
    await expect(page.getByLabel('Label', { exact: true })).toHaveCount(2);
    await page.getByLabel('Label', { exact: true }).nth(1).fill('Pack');
    await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Unit');
  });
  await page.getByRole('button', { name: 'Move Unit up', exact: true }).click();
  await expect(page.locator('.property-list > li strong').first()).toHaveText('Unit');
  await page.goto('/tana/items/new/');
  await select(page, 'Item type', 'Food');
  await page.getByRole('combobox', { name: 'Unit', exact: true }).click();
  await expect(page.getByRole('option', { name: 'Each', exact: true })).toBeVisible();
  await expect(page.getByRole('option', { name: 'Pack', exact: true })).toBeVisible();
});

test('rapid type changes ignore an older field response and keep modal history stable', async ({ page }) => {
  await start(page);
  const tools = await newType(page, 'Tools');
  await property(page, 'Serial');
  await newType(page, 'Books');
  await property(page, 'Author');
  await page.goto('/tana/items/new/');
  await page.getByLabel('Name', { exact: true }).fill('Draft');
  const url = page.url();
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  await page.route('**/tana/items/custom-fields/', async route => {
    const typeID = new URLSearchParams(route.request().postData()).get('item_type');
    const response = await route.fetch();
    if (typeID === tools) await delayed;
    await route.fulfill({ response }).catch(() => {});
  });
  await select(page, 'Item type', 'Tools');
  await select(page, 'Item type', 'Books');
  await expect(page.getByLabel('Author', { exact: true })).toBeVisible();
  release();
  await expect(page.getByLabel('Serial', { exact: true })).toHaveCount(0);
  expect(page.url()).toBe(url);
  await expect(page.getByRole('button', { name: 'Save item', exact: true })).toBeEnabled();
});
