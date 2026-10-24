import { defineConfig, devices } from '@playwright/test'

/**
 * Tests de bout en bout (T128, T143) : le vrai backend sert l'interface compilée, sur une base
 * neuve par projet. Prérequis : `npm run build` dans frontend/ et `uv sync` dans backend/.
 */
const JOURNEY_PORT = 8765
const KEYBOARD_PORT = 8766

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'parcours',
      testMatch: /quickstart\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${JOURNEY_PORT}` },
    },
    {
      name: 'clavier',
      testMatch: /keyboard\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://127.0.0.1:${KEYBOARD_PORT}` },
    },
  ],
  webServer: [JOURNEY_PORT, KEYBOARD_PORT].map((port) => ({
    command: `bash tests/e2e/server.sh ${port}`,
    url: `http://127.0.0.1:${port}/api/v1/auth/status`,
    reuseExistingServer: false,
    timeout: 90_000,
  })),
})
