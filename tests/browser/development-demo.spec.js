import { test, expect } from '@playwright/test';

async function menu(page, name) {
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name, exact: true }).click();
}
async function start(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await expect(page.locator('#workspace-view')).toBeVisible();
}

test('development logout resumes the same workspace and explicit reset preserves the account', async ({ page, context }) => {
  await start(page);
  await menu(page, 'Profile');
  await page.getByLabel('Nickname', { exact: true }).fill('Persistent Keeper');
  await page.getByRole('button', { name: 'Save profile', exact: true }).click();
  await expect(page.getByText('Your profile has been saved.')).toBeVisible();
  await page.goto('/tana/item_types/new/');
  await page.getByLabel('Name', { exact: true }).fill('Persistent Tools');
  await page.getByRole('button', { name: 'Save type', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Persistent Tools');
  await page.getByRole('link', { name: 'Close window' }).click();
  await menu(page, 'Log out');
  await expect(page).toHaveURL('/');
  await page.goto('/tana/items/');
  await expect(page).toHaveURL(/\/?next=/);
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await expect(page.locator('#account-display-name')).toHaveText('Persistent Keeper');
  await page.goto('/tana/item_types/');
  await expect(page.getByRole('link', { name: 'View Persistent Tools', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: 'Reset Demo Development', exact: true }).click();
  await expect(page.locator('#modal-host h2')).toHaveText('Reset Demo?');
  await page.getByRole('link', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('link', { name: 'View Persistent Tools', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('menuitem', { name: 'Reset Demo Development', exact: true }).click();
  const before = (await context.cookies()).find(cookie => cookie.name === 'tanaspace_dev_demo').value;
  await page.getByRole('button', { name: 'Reset Demo', exact: true }).click();
  await expect(page).toHaveURL('/tana');
  await expect(page.locator('#account-display-name')).toHaveText('Persistent Keeper');
  const after = (await context.cookies()).find(cookie => cookie.name === 'tanaspace_dev_demo');
  expect(after.value).not.toBe(before);
  expect(after.httpOnly).toBe(true);
  await page.goto('/tana/item_types/');
  await expect(page.getByRole('heading', { name: 'No types yet.', exact: true })).toBeVisible();
});
