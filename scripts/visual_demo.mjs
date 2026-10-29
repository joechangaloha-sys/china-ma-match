// Isolated visual smoke test: temporary SQLite data, headless Chrome, automatic cleanup.
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
await mkdir(path.join(root, "data"), { recursive: true });
const temp = await mkdtemp(path.join(root, "data", "visual-demo-"));
const output = path.join(root, "artifacts", "demo-visual");
await mkdir(output, { recursive: true });
const appPort = 7100;
const debugPort = 9300 + Math.floor(Math.random() * 500);
const base = `http://127.0.0.1:${appPort}`;
let app;
let chrome;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function until(check, label, timeout = 30000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    try { const value = await check(); if (value) return value; } catch {}
    await sleep(200);
  }
  throw new Error(`Timed out: ${label}`);
}
function stop(child) {
  if (!child?.pid || child.killed) return;
  try { process.kill(-child.pid, "SIGTERM"); } catch { try { child.kill("SIGTERM"); } catch {} }
}

try {
  app = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(appPort)], {
    cwd: root,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      MAMATCH_DATABASE_URL: `sqlite:///${path.join(temp, "demo.db")}`,
      MAMATCH_UPLOAD_DIR: path.join(temp, "uploads"),
      MAMATCH_DEMO_MODE: "true",
      MAMATCH_DEMO_ACCESS_KEY: "visual-demo-only",
      MAMATCH_SEED_DEMO: "true",
      MAMATCH_SECURE_COOKIES: "false",
      MAMATCH_LLM: "off",
    },
  });
  let appLog = "";
  app.stdout.on("data", (chunk) => { appLog += chunk; });
  app.stderr.on("data", (chunk) => { appLog += chunk; });
  app.on("exit", (code) => { if (code && code !== 0) console.error(appLog); });
  await until(async () => (await fetch(`${base}/health/live`)).ok, "application startup");

  chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
    "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
    `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(temp, "chrome")}`,
    "--window-size=1440,1000", "about:blank",
  ], { detached: true, stdio: "ignore" });
  const target = await until(async () => {
    const tabs = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
    return tabs.find((tab) => tab.type === "page");
  }, "Chrome startup");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let serial = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(JSON.stringify(message.error)));
    else request.resolve(message.result);
  };
  const cdp = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const navigate = async (url, expectedPath) => {
    await cdp("Page.navigate", { url });
    await until(() => evaluate(`document.readyState === 'complete' && location.pathname === ${JSON.stringify(expectedPath)}`), `navigation to ${expectedPath}`);
  };
  const screenshot = async (name) => {
    const image = await cdp("Page.captureScreenshot", { format: "jpeg", quality: 82, captureBeyondViewport: false });
    await writeFile(path.join(output, `${name}.jpg`), Buffer.from(image.data, "base64"));
  };
  const layout = () => evaluate(`({ path: location.pathname, title: document.title, overflow: document.documentElement.scrollWidth > innerWidth, width: innerWidth, demoWarning: document.body.innerText.includes('虚构') || document.body.innerText.includes('fictional') })`);

  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate(`${base}/demo-access?next=%2Fzh`, "/demo-access");
  await screenshot("01-demo-access");

  await evaluate(`document.querySelector('#access_key').value = 'visual-demo-only'; document.querySelector('form').submit(); true`);
  await until(() => evaluate(`document.readyState === 'complete' && location.pathname === '/zh'`), "passcode redirect");
  const chinese = await layout();
  if (!chinese.demoWarning || chinese.overflow) throw new Error(`Chinese layout failed: ${JSON.stringify(chinese)}`);
  await screenshot("02-chinese-home");

  await navigate(`${base}/en/opportunities`, "/en/opportunities");
  const english = await layout();
  if (!english.demoWarning || english.overflow) throw new Error(`English layout failed: ${JSON.stringify(english)}`);
  await screenshot("03-english-opportunities");

  await cdp("Emulation.setDeviceMetricsOverride", { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await navigate(`${base}/zh/opportunities`, "/zh/opportunities");
  const mobile = await layout();
  if (!mobile.demoWarning || mobile.overflow) throw new Error(`Mobile layout failed: ${JSON.stringify(mobile)}`);
  await screenshot("04-mobile-opportunities");
  console.log(JSON.stringify({ result: "passed", chinese, english, mobile, screenshots: output }, null, 2));
  ws.close();
} finally {
  stop(chrome);
  stop(app);
}
