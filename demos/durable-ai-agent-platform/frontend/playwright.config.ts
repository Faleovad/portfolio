import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const python =
  process.env.PYTHON_EXECUTABLE ||
  resolve(
    "..",
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const root = resolve("..");
const dsn =
  process.env.ORCHESTRATOR_DSN ||
  "postgresql://agent_lab_app@127.0.0.1:55439/agent_orchestrator";
const reader =
  process.env.PROVIDER_READ_DSN ||
  "postgresql://agent_lab_reader@127.0.0.1:55439/agent_provider";
const writer =
  process.env.PROVIDER_WRITE_DSN ||
  "postgresql://agent_lab_writer@127.0.0.1:55439/agent_provider";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 15000 },
  use: {
    baseURL: process.env.BROWSER_BASE_URL || "http://127.0.0.1:58045",
    viewport: { width: 1480, height: 1120 },
    trace: "retain-on-failure",
  },
  reporter: [["list"], ["json", { outputFile: "test-results/browser.json" }]],
  webServer:
    process.env.BROWSER_EXTERNAL_SERVERS === "1"
      ? undefined
      : [
          {
            command: `"${python}" -m uvicorn platform_core.api:from_environment --factory --host 127.0.0.1 --port 58042`,
            cwd: root,
            url: "http://127.0.0.1:58042/health",
            env: {
              PYTHONPATH: resolve(root, "backend"),
              ORCHESTRATOR_DSN: dsn,
              PROVIDER_READ_DSN: reader,
              PROVIDER_WRITE_DSN: "",
            },
            reuseExistingServer: false,
          },
          {
            command: `"${python}" -m uvicorn platform_core.control_api:from_environment --factory --host 127.0.0.1 --port 58043`,
            cwd: root,
            url: "http://127.0.0.1:58043/health",
            env: {
              PYTHONPATH: resolve(root, "backend"),
              ORCHESTRATOR_DSN: dsn,
              PROVIDER_READ_DSN: reader,
              PROVIDER_WRITE_DSN: writer,
              ENABLE_LAB_CONTROLS: "1",
            },
            reuseExistingServer: false,
          },
          {
            command: "npm run dev -- --port 58045 --strictPort",
            url: "http://127.0.0.1:58045",
            reuseExistingServer: false,
          },
        ],
});
