import { expect, test } from '@playwright/test';

const mockApi = process.env.MOCK_API_URL || 'http://127.0.0.1:8080';

test('light-gray menu button fully closes the navigation drawer', async ({ page, request }) => {
    await request.post(`${mockApi}/_test/reset`, {
        data: { installed: true, activeTheme: 'light-gray' }
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await expect(page.locator('.loading-page')).toBeHidden();

    const toggle = page.locator('.tb-theme-nav-toggle');
    const drawer = page.locator('.tb-theme-drawer');
    await expect(toggle.locator('.mdi-menu')).toBeVisible();
    await expect(drawer).toBeVisible();

    await toggle.click();

    await expect(drawer).toBeHidden();
});
