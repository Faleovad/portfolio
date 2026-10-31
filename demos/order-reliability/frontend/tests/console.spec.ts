import { test, expect, type Page } from '@playwright/test';

test('initial API failure can reconnect without reloading or fabricating state', async ({
  page,
}) => {
  await page.route('**/api/system', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toBeVisible();
  await page.unroute('**/api/system');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByLabel('Choose a failure boundary')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

async function load(page: Page, scenario: string) {
  await page.goto('/');
  await expect(page.getByLabel('Choose a failure boundary')).toBeVisible();
  await page.getByLabel('Choose a failure boundary').selectOption(scenario);
  await page.getByRole('button', { name: 'Reset / seed' }).click();
  await expect(page.getByTestId('order-state')).toHaveText('DISCOVERED');
  await expect(page.getByRole('button', { name: 'Step', exact: true })).toBeEnabled();
}

test('run reaches confirmed state and repeated run does not call provider again', async ({
  page,
}) => {
  await load(page, 'happy');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByTestId('order-state')).toHaveText('DONE');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByTestId('create-count')).toHaveText('1');
  await expect(page.getByTestId('fulfill-count')).toHaveText('1');
  await expect(page.getByTestId('timeline')).toContainText('local stock settled');
});

test('step reveals provider commit while ERP is UNKNOWN; recovery does not resend', async ({
  page,
}) => {
  await load(page, 'completion_lost');
  for (let i = 0; i < 5; i++) {
    await page.getByRole('button', { name: 'Step', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Step', exact: true })).toBeEnabled();
  }
  await expect(page.getByTestId('order-state')).toHaveText('UNKNOWN');
  await expect(
    page.getByRole('heading', { name: 'External CRM state' }).locator('..').locator('..'),
  ).toContainText('DONE');
  await page.screenshot({ path: 'test-results/console-unknown.png', fullPage: true });
  await page.getByRole('button', { name: 'Recover', exact: true }).click();
  await expect(page.getByTestId('order-state')).toHaveText('DONE');
  await expect(page.getByTestId('fulfill-count')).toHaveText('1');
});

test('unprovable completion remains manual review with an UNKNOWN fence', async ({ page }) => {
  await load(page, 'unprovable');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByTestId('order-state')).toHaveText('MANUAL REVIEW');
  const fence = page.getByRole('heading', { name: 'Mutation fence' }).locator('..').locator('..');
  await expect(fence).toContainText('UNKNOWN');
  await expect(page.getByTestId('fulfill-count')).toHaveText('1');
});

test('interruption renders an error, retains state and resumes through recovery', async ({
  page,
}) => {
  await load(page, 'interrupt_create');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('simulated_interruption');
  await expect(page.getByTestId('order-state')).toHaveText('VALIDATED');
  await page.reload();
  await expect(page.getByTestId('order-state')).toHaveText('VALIDATED');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByTestId('order-state')).toHaveText('DONE');
  await expect(page.getByTestId('create-count')).toHaveText('1');
});

test('scenario selection requires reset and reset clears the run', async ({ page }) => {
  await load(page, 'happy');
  await page.getByLabel('Choose a failure boundary').selectOption('simple');
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Reset / seed' }).click();
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeEnabled();
  await expect(page.getByTestId('create-count')).toHaveText('0');
});

test('mobile console remains within viewport and shows backend errors', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await load(page, 'happy');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.route('**/api/orders/*/step', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'test_unavailable', message: 'Synthetic connection failure' },
      }),
    }),
  );
  await page.getByRole('button', { name: 'Step', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('test_unavailable');
  await expect(page.getByTestId('order-state')).toHaveText('DISCOVERED');
});
