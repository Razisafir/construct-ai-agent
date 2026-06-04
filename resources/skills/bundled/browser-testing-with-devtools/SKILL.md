---
name: browser-testing-with-devtools
version: 1.0.0
category: testing
description: Test web applications with Playwright and debug using Chrome DevTools Protocol
author: Construct AI
tools_needed: [write_file, shell, read_file]
confidence: 0.95
---

# Browser Testing with DevTools

## Description

End-to-end testing of web applications using Playwright for browser automation and Chrome DevTools Protocol (CDP) for deep debugging, performance analysis, and network inspection.

## When to Use

- Testing complete user flows (login → dashboard → action)
- Debugging flaky tests with network or timing issues
- Performance testing and load time analysis
- Visual regression testing
- Testing responsive design across viewports
- Debugging production issues by replicating browser state

## Steps

### Step 1: Set Up Playwright Configuration

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/playwright.config.ts",
  "content": "import { defineConfig, devices } from '@playwright/test';\n\nexport default defineConfig({\n  testDir: './tests/e2e',\n  fullyParallel: true,\n  forbidOnly: !!process.env.CI,\n  retries: process.env.CI ? 2 : 0,\n  workers: process.env.CI ? 1 : undefined,\n  reporter: [['html', { open: 'never' }], ['list']],\n  use: {\n    baseURL: 'http://localhost:3000',\n    trace: 'on-first-retry',\n    screenshot: 'only-on-failure',\n    video: 'on-first-retry',\n  },\n  projects: [\n    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },\n    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },\n    { name: 'webkit', use: { ...devices['Desktop Safari'] } },\n    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },\n    { name: 'Mobile Safari', use: { ...devices['iPhone 12'] } },\n  ],\n});\n"
}
```

**Validation:** `npx playwright test --list` shows all configured projects.

### Step 2: Write Page Object Model

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/e2e/pages/LoginPage.ts",
  "content": "import { Page, Locator } from '@playwright/test';\n\nexport class LoginPage {\n  readonly emailInput: Locator;\n  readonly passwordInput: Locator;\n  readonly submitButton: Locator;\n  readonly errorMessage: Locator;\n\n  constructor(private page: Page) {\n    this.emailInput = page.locator('[data-testid=\"email-input\"]');\n    this.passwordInput = page.locator('[data-testid=\"password-input\"]');\n    this.submitButton = page.locator('[data-testid=\"login-button\"]');\n    this.errorMessage = page.locator('[data-testid=\"error-message\"]');\n  }\n\n  async goto() {\n    await this.page.goto('/login');\n  }\n\n  async login(email: string, password: string) {\n    await this.emailInput.fill(email);\n    await this.passwordInput.fill(password);\n    await this.submitButton.click();\n  }\n\n  async expectError(message: string) {\n    await expect(this.errorMessage).toHaveText(message);\n  }\n}\n"
}
```

**Validation:** Page object compiles. Selectors resolve to exactly one element.

### Step 3: Write Test Cases

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/e2e/auth.spec.ts",
  "content": "import { test, expect } from '@playwright/test';\nimport { LoginPage } from './pages/LoginPage';\n\ntest.describe('Authentication', () => {\n  test('successful login redirects to dashboard', async ({ page }) => {\n    const loginPage = new LoginPage(page);\n    await loginPage.goto();\n    await loginPage.login('user@example.com', 'password123');\n    await expect(page).toHaveURL('/dashboard');\n  });\n\n  test('invalid credentials show error', async ({ page }) => {\n    const loginPage = new LoginPage(page);\n    await loginPage.goto();\n    await loginPage.login('bad@example.com', 'wrong');\n    await loginPage.expectError('Invalid email or password');\n  });\n\n  test('unauthenticated user is redirected', async ({ page }) => {\n    await page.goto('/dashboard');\n    await expect(page).toHaveURL('/login?redirect=/dashboard');\n  });\n});\n"
}
```

**Validation:** Tests run and pass: `npx playwright tests/e2e/auth.spec.ts`.

### Step 4: Add Network Interception

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/e2e/api-mocking.spec.ts",
  "content": "import { test, expect } from '@playwright/test';\n\ntest('handles API failure gracefully', async ({ page }) => {\n  await page.route('**/api/users', route => {\n    route.fulfill({\n      status: 500,\n      body: JSON.stringify({ error: 'Server Error' }),\n    });\n  });\n\n  await page.goto('/users');\n  await expect(page.locator('[data-testid=\"error-state\"]')).toBeVisible();\n  await expect(page.locator('[data-testid=\"retry-button\"]')).toBeVisible();\n});\n\ntest('loads mocked data', async ({ page }) => {\n  await page.route('**/api/users', route => {\n    route.fulfill({\n      status: 200,\n      body: JSON.stringify({\n        data: [{ id: 1, name: 'Mock User', email: 'mock@example.com' }]\n      }),\n    });\n  });\n\n  await page.goto('/users');\n  await expect(page.locator('text=Mock User')).toBeVisible();\n});\n"
}
```

**Validation:** Mocked responses are returned correctly. Tests pass in both success and failure scenarios.

### Step 5: Performance Testing with CDP

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/e2e/performance.spec.ts",
  "content": "import { test, expect } from '@playwright/test';\n\ntest('page loads within performance budget', async ({ page }) => {\n  const client = await page.context().newCDPSession(page);\n  \n  await client.send('Performance.enable');\n  \n  const startTime = Date.now();\n  await page.goto('/dashboard');\n  await page.waitForLoadState('networkidle');\n  \n  const metrics = await client.send('Performance.getMetrics');\n  const navigationTime = Date.now() - startTime;\n  \n  const lcpMetric = metrics.metrics.find(m => m.name === 'LargestContentfulPaint');\n  \n  expect(navigationTime).toBeLessThan(3000);\n  if (lcpMetric) {\n    expect(lcpMetric.value).toBeLessThan(2500);\n  }\n});\n\ntest('no memory leaks on navigation', async ({ page }) => {\n  const client = await page.context().newCDPSession(page);\n  \n  for (let i = 0; i < 10; i++) {\n    await page.goto('/page-a');\n    await page.goto('/page-b');\n  }\n  \n  const heap = await client.send('Runtime.getHeapUsage');\n  expect(heap.usedSize).toBeLessThan(50 * 1024 * 1024); // 50MB\n});\n"
}
```

**Validation:** Performance metrics are collected. Budget thresholds are reasonable for the application.

### Step 6: Visual Regression Testing

**Tool:** `shell`
**Parameters:**

```json
{"command": "npx playwright test --update-snapshots", "description": "Update visual baselines"}
```

**Validation:** Baseline screenshots are captured. Subsequent runs detect pixel differences.

### Step 7: Run Full Suite in CI

**Tool:** `shell`
**Parameters:**

```json
{"command": "npx playwright test --reporter=html,junit --shard=1/3", "description": "Run tests with CI configuration"}
```

**Validation:** All tests pass. HTML and JUnit reports are generated. Sharding works for parallel execution.

## Examples

### Example 1: E-Commerce Checkout Flow

**Input:** "Test the complete checkout process."

**Process:**

1. Config: Multi-project (Chrome, Firefox, Safari, mobile)
2. Page objects: CartPage, CheckoutPage, PaymentPage, ConfirmationPage
3. Tests: Add to cart → checkout → payment → confirmation
4. Mocking: Mock payment gateway API responses
5. Performance: Measure each step's load time
6. Visual: Screenshots of each checkout step
7. CI: Runs on every PR with artifact retention

**Output:** Comprehensive checkout test suite covering desktop and mobile.

### Example 2: Admin Dashboard Testing

**Input:** "Test the admin dashboard with data tables."

**Process:**

1. Config: Desktop Chrome primary, mobile secondary
2. Page objects: DashboardPage, DataTableComponent, FilterPanel
3. Tests: Sorting, filtering, pagination, row selection, bulk actions
4. Mocking: Mock large dataset (10,000 rows) for performance
5. Performance: Table render time under 1 second
6. Visual: Table states (empty, loading, error, populated)
7. CI: Parallel execution with 3 shards

**Output:** Admin dashboard tests with performance benchmarks.

### Example 3: Multi-Step Form Wizard

**Input:** "Test a 4-step form wizard."

**Process:**

1. Config: Chromium with slowMo for visibility
2. Page objects: WizardPage, Step1Page, Step2Page, etc.
3. Tests: Complete flow, step navigation, validation per step, save/restore
4. Mocking: Mock save API, mock autosave endpoint
5. Performance: Step transition under 500ms
6. Visual: Each step screenshot, error states
7. CI: Retries for flaky animations

**Output:** Reliable wizard tests handling all navigation and validation scenarios.

## Best Practices

- **Use data-testid attributes.** Prefer `data-testid` over class or text selectors.
- **Page Object Model.** Encapsulate page structure in reusable page classes.
- **Independent tests.** Each test should set up its own state; no test dependencies.
- **Mock external APIs.** Never hit real payment gateways or external services.
- **Retry flaky tests.** Use Playwright's built-in retry mechanism.
- **Screenshot on failure.** Always capture screenshots and videos for debugging.
- **Parallel execution.** Use multiple workers and sharding for speed.
- **Seed test data.** Use API calls or database seeds to set up test state quickly.
- **Clean up after tests.** Remove test data in `afterEach` or `afterAll` hooks.
- **Test realistic user flows.** Mimic actual user behavior, not just isolated actions.