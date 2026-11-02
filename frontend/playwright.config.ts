import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8765", viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH, args: ["--no-sandbox"] }
      : {},
  },
  webServer: {
    command: "python ../backend/manage.py migrate --noinput && python ../backend/manage.py runserver 127.0.0.1:8765 --noreload",
    url: "http://127.0.0.1:8765",
    reuseExistingServer: false,
    env: { DJANGO_DATABASE_PATH: resolve("../backend/browser-tests.sqlite3"),
      DJANGO_DEBUG: "1", DJANGO_ALLOWED_HOSTS: "127.0.0.1,localhost" },
  },
});
