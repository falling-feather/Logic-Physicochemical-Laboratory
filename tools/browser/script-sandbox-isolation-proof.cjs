#!/usr/bin/env node

const fs = require('node:fs/promises');
const path = require('node:path');

let playwright;
try {
  playwright = require('playwright');
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    code: 'playwright_missing',
    message: 'Install Playwright or run with NODE_PATH pointing at a Playwright installation.',
    detail: error && error.message ? error.message : String(error),
  }, null, 2));
  process.exit(2);
}

const { chromium } = playwright;

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith('--')) continue;
    const raw = item.slice(2);
    const equals = raw.indexOf('=');
    if (equals >= 0) {
      parsed[raw.slice(0, equals)] = raw.slice(equals + 1);
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith('--')) {
      parsed[raw] = true;
    } else {
      parsed[raw] = next;
      index += 1;
    }
  }
  return parsed;
}

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function encodeSlug(slug) {
  return slug.split('/').map(encodeURIComponent).join('/');
}

function assertCheck(report, name, ok, evidence = {}) {
  report.checks.push({ name, ok: Boolean(ok), evidence });
}

function checkSucceeded(report) {
  return report.checks.every((item) => item.ok);
}

function firstScriptManifest(value) {
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = firstScriptManifest(item);
      if (found) return found;
    }
    return null;
  }
  if (!value || typeof value !== 'object') return null;
  if (value.scriptManifest && typeof value.scriptManifest === 'object') {
    return value.scriptManifest;
  }
  for (const item of Object.values(value)) {
    const found = firstScriptManifest(item);
    if (found) return found;
  }
  return null;
}

async function fetchText(url) {
  const response = await fetch(url, { headers: { Accept: '*/*' } });
  return {
    url,
    status: response.status,
    headers: Object.fromEntries(response.headers.entries()),
    text: await response.text(),
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  const text = await response.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  return {
    url,
    status: response.status,
    headers: Object.fromEntries(response.headers.entries()),
    body,
    text,
  };
}

async function launchChromium(args) {
  const requested = args.channel || process.env.ASTRA_BROWSER_CHANNEL || '';
  const channels = requested ? [requested] : ['', 'msedge', 'chrome'];
  const errors = [];
  for (const channel of channels) {
    try {
      const browser = await chromium.launch({
        headless: args.headed ? false : true,
        ...(channel ? { channel } : {}),
      });
      return { browser, channel: channel || 'playwright-chromium' };
    } catch (error) {
      errors.push({
        channel: channel || 'playwright-chromium',
        message: error && error.message ? error.message.split('\n')[0] : String(error),
      });
    }
  }
  const detail = errors.map((item) => `${item.channel}: ${item.message}`).join(' | ');
  throw new Error(`Unable to launch Chromium-compatible browser. ${detail}`);
}

function isLocalUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost';
  } catch {
    return false;
  }
}

function isBenignMissingResource(entry) {
  return /\/favicon\.ico(?:$|\?)/.test(entry.url);
}

async function waitForContentFrame(iframeHandle, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const frame = await iframeHandle.contentFrame();
    if (frame) return frame;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return null;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const apiBase = stripTrailingSlash(args.api || args['api-base'] || process.env.ASTRA_BROWSER_DRILL_API || 'http://127.0.0.1:8000');
  const webBase = stripTrailingSlash(args.web || args['web-base'] || process.env.ASTRA_BROWSER_DRILL_WEB || 'http://127.0.0.1:8766');
  const slug = String(args.slug || 'physics/energy-conservation').replace(/^\/+|\/+$/g, '');
  const timeoutMs = Number(args.timeout || 15000);
  const outDir = path.resolve(String(args.out || path.join('test-screenshots', 'browser-isolation')));
  const appUrl = String(args.url || `${webBase}/?backendSchema=1&apiBase=${encodeURIComponent(apiBase)}#${slug}`);
  const encodedSlug = encodeSlug(slug);
  const renderUrl = `${apiBase}/api/render/page/${encodedSlug}`;
  const generatedAt = new Date().toISOString();

  await fs.mkdir(outDir, { recursive: true });

  const report = {
    ok: false,
    phase: 'V6.6.48',
    generatedAt,
    appUrl,
    apiBase,
    webBase,
    slug,
    browser: null,
    checks: [],
    console: [],
    pageErrors: [],
    network: [],
    requestFailures: [],
    screenshots: {},
    failClosed: {},
  };

  const render = await fetchJson(renderUrl);
  assertCheck(report, 'render API returns published schema', render.status === 200 && render.body, {
    status: render.status,
    cacheControl: render.headers['cache-control'] || '',
    sandboxHeader: render.headers['x-astra-content-script-sandbox'] || '',
  });

  const manifest = render.body ? firstScriptManifest(render.body) : null;
  const embed = manifest && manifest.embed ? manifest.embed : null;
  const iframeConfig = embed && embed.iframe ? embed.iframe : null;
  const sandboxUrl = iframeConfig && iframeConfig.src
    ? new URL(iframeConfig.src, apiBase).href
    : '';

  assertCheck(report, 'public render exposes a single embeddable descriptor', Boolean(embed && embed.status === 'embeddable' && sandboxUrl), {
    sandboxId: embed && embed.sandboxId,
    iframe: iframeConfig || null,
    assetCount: embed && embed.assetCount,
  });
  assertCheck(report, 'descriptor keeps iframe sandbox opaque', iframeConfig && iframeConfig.sandbox === 'allow-scripts', {
    sandbox: iframeConfig && iframeConfig.sandbox,
    hasAllowSameOrigin: iframeConfig && String(iframeConfig.sandbox || '').includes('allow-same-origin'),
  });
  assertCheck(report, 'descriptor keeps referrer policy no-referrer', iframeConfig && iframeConfig.referrerPolicy === 'no-referrer', {
    referrerPolicy: iframeConfig && iframeConfig.referrerPolicy,
  });

  if (sandboxUrl) {
    const sandboxDocument = await fetchText(sandboxUrl);
    const csp = sandboxDocument.headers['content-security-policy'] || '';
    assertCheck(report, 'sandbox document has hardened CSP and no-store headers', sandboxDocument.status === 200
      && /script-src 'nonce-[^']+'/.test(csp)
      && csp.includes("frame-ancestors 'self'")
      && csp.includes("form-action 'none'")
      && csp.includes("object-src 'none'")
      && (sandboxDocument.headers['cache-control'] || '').includes('no-store')
      && sandboxDocument.headers['x-content-type-options'] === 'nosniff'
      && sandboxDocument.headers['referrer-policy'] === 'no-referrer', {
      status: sandboxDocument.status,
      csp,
      cacheControl: sandboxDocument.headers['cache-control'] || '',
      contentTypeOptions: sandboxDocument.headers['x-content-type-options'] || '',
      referrerPolicy: sandboxDocument.headers['referrer-policy'] || '',
    });
  }

  const missingSandbox = await fetchJson(`${apiBase}/api/render/script-sandboxes/sm_missing/page/${encodedSlug}`);
  const missingBootstrap = await fetchJson(`${apiBase}/api/render/script-sandboxes/sm_missing/bootstrap/page/${encodedSlug}`);
  assertCheck(report, 'unknown sandbox id fails closed before executable path', missingSandbox.status === 404 && missingBootstrap.status === 404, {
    sandboxStatus: missingSandbox.status,
    bootstrapStatus: missingBootstrap.status,
  });
  report.failClosed.missingSandbox = {
    sandboxStatus: missingSandbox.status,
    bootstrapStatus: missingBootstrap.status,
  };

  if (manifest && Array.isArray(manifest.references) && manifest.references[0] && sandboxUrl) {
    const missingAssetUrl = `${apiBase}/api/render/script-sandboxes/${manifest.sandboxId}/assets/${'0'.repeat(64)}/page/${encodedSlug}`;
    const missingAsset = await fetchJson(missingAssetUrl);
    assertCheck(report, 'unknown sandbox asset hash fails closed', missingAsset.status === 404, {
      status: missingAsset.status,
      url: missingAssetUrl,
    });
    report.failClosed.missingAsset = { status: missingAsset.status };
  }

  let browser;
  try {
    const launched = await launchChromium(args);
    browser = launched.browser;
    report.browser = { channel: launched.channel };
    const context = await browser.newContext({
      viewport: { width: 1366, height: 900 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();

    page.on('console', (message) => {
      report.console.push({
        type: message.type(),
        text: message.text().slice(0, 1000),
        location: message.location(),
      });
    });
    page.on('pageerror', (error) => {
      report.pageErrors.push({
        name: error.name,
        message: error.message.slice(0, 1000),
      });
    });
    page.on('requestfailed', (request) => {
      report.requestFailures.push({
        url: request.url(),
        method: request.method(),
        failure: request.failure() ? request.failure().errorText : '',
      });
    });
    page.on('response', (response) => {
      const url = response.url();
      if (!isLocalUrl(url) && !url.startsWith('data:')) return;
      report.network.push({
        url,
        status: response.status(),
        contentType: response.headers()['content-type'] || '',
        cacheControl: response.headers()['cache-control'] || '',
        csp: response.headers()['content-security-policy'] || '',
      });
    });

    await page.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    await page.evaluate(() => {
      localStorage.setItem('__astra_parent_local_secret', 'parent-local-secret');
      sessionStorage.setItem('__astra_parent_session_secret', 'parent-session-secret');
      document.cookie = '__astra_parent_cookie_secret=parent-cookie-secret; path=/; SameSite=Lax';
      document.body.setAttribute('data-astra-parent-secret', 'parent-dom-secret');
    });

    const iframeHandle = await page.waitForSelector('[data-backend-sandbox-frame]', { timeout: timeoutMs });
    const iframeAttrs = await iframeHandle.evaluate((iframe) => ({
      sandbox: iframe.getAttribute('sandbox') || '',
      src: iframe.src,
      referrerPolicy: iframe.referrerPolicy || '',
      title: iframe.title || '',
    }));
    assertCheck(report, 'parent page creates iframe from descriptor', iframeAttrs.src === sandboxUrl, {
      expectedSrc: sandboxUrl,
      actualSrc: iframeAttrs.src,
    });
    assertCheck(report, 'runtime iframe attributes preserve sandbox boundary', iframeAttrs.sandbox === 'allow-scripts'
      && !iframeAttrs.sandbox.includes('allow-same-origin')
      && iframeAttrs.referrerPolicy === 'no-referrer', iframeAttrs);

    const frame = await waitForContentFrame(iframeHandle, timeoutMs);
    assertCheck(report, 'browser exposes loaded sandbox frame', Boolean(frame), {
      frameUrl: frame ? frame.url() : '',
    });
    if (!frame) {
      throw new Error('Sandbox iframe frame was not available.');
    }
    await frame.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
    await page.waitForFunction(() => {
      const card = document.querySelector('[data-backend-sandbox-card]');
      return card && card.dataset && ['bootstrapping', 'assets', 'ready', 'timeout', 'error'].includes(card.dataset.state);
    }, { timeout: timeoutMs });

    const cardState = await page.evaluate(() => {
      const card = document.querySelector('[data-backend-sandbox-card]');
      return {
        state: card ? card.dataset.state || '' : '',
        status: card ? (card.querySelector('[data-backend-sandbox-status]')?.textContent || '') : '',
        message: card ? (card.querySelector('[data-backend-sandbox-message]')?.textContent || '') : '',
      };
    });
    assertCheck(report, 'parent adapter reaches a non-loading sandbox state', ['bootstrapping', 'assets', 'ready', 'timeout'].includes(cardState.state), cardState);

    const isolation = await frame.evaluate(() => {
      const attempt = (label, fn) => {
        try {
          const value = fn();
          return { label, ok: true, value: String(value).slice(0, 120) };
        } catch (error) {
          return {
            label,
            ok: false,
            name: error && error.name ? error.name : '',
            message: error && error.message ? String(error.message).slice(0, 240) : String(error).slice(0, 240),
          };
        }
      };
      return {
        frameUrl: location.href,
        globalOrigin: typeof origin === 'string' ? origin : '',
        hasSandboxRoot: Boolean(document.getElementById('astra-sandbox-root')),
        sandboxId: document.querySelector('meta[name="astra-script-sandbox-id"]')?.getAttribute('content') || '',
        attempts: {
          parentDocument: attempt('parentDocument', () => window.parent.document.body.getAttribute('data-astra-parent-secret')),
          parentLocalStorage: attempt('parentLocalStorage', () => window.parent.localStorage.getItem('__astra_parent_local_secret')),
          parentSessionStorage: attempt('parentSessionStorage', () => window.parent.sessionStorage.getItem('__astra_parent_session_secret')),
          parentCookie: attempt('parentCookie', () => window.parent.document.cookie),
          topLocation: attempt('topLocation', () => window.top.location.href),
          ownLocalStorage: attempt('ownLocalStorage', () => localStorage.getItem('__astra_parent_local_secret')),
          ownCookie: attempt('ownCookie', () => document.cookie),
        },
      };
    });

    const parentAttempts = [
      isolation.attempts.parentDocument,
      isolation.attempts.parentLocalStorage,
      isolation.attempts.parentSessionStorage,
      isolation.attempts.parentCookie,
      isolation.attempts.topLocation,
    ];
    assertCheck(report, 'sandbox frame cannot read parent DOM/storage/cookie/session', parentAttempts.every((item) => item && item.ok === false), {
      globalOrigin: isolation.globalOrigin,
      attempts: parentAttempts,
    });
    assertCheck(report, 'sandbox document root and metadata are present', isolation.hasSandboxRoot && isolation.sandboxId === manifest.sandboxId, {
      hasSandboxRoot: isolation.hasSandboxRoot,
      sandboxId: isolation.sandboxId,
      expectedSandboxId: manifest && manifest.sandboxId,
    });

    const seriousConsole = report.console.filter((item) => item.type === 'error' && !/favicon\.ico/i.test(item.text));
    const badNetwork = report.network.filter((item) => item.status >= 400 && !isBenignMissingResource(item));
    const unexpectedExternal = report.network.filter((item) => !isLocalUrl(item.url) && !item.url.startsWith('data:'));
    assertCheck(report, 'browser console has no severe errors', seriousConsole.length === 0 && report.pageErrors.length === 0, {
      severeConsoleCount: seriousConsole.length,
      pageErrorCount: report.pageErrors.length,
    });
    assertCheck(report, 'browser network stays local and executable resources load', badNetwork.length === 0 && unexpectedExternal.length === 0 && report.requestFailures.length === 0, {
      badNetwork,
      unexpectedExternal,
      requestFailures: report.requestFailures,
    });

    const pageScreenshot = path.join(outDir, 'script-sandbox-isolation-page.png');
    await page.screenshot({ path: pageScreenshot, fullPage: true });
    report.screenshots.page = pageScreenshot;

    const box = await iframeHandle.boundingBox();
    if (box) {
      const iframeScreenshot = path.join(outDir, 'script-sandbox-isolation-iframe.png');
      await page.screenshot({ path: iframeScreenshot, clip: box });
      report.screenshots.iframe = iframeScreenshot;
    }

    await context.close();
  } finally {
    if (browser) await browser.close();
  }

  report.ok = checkSucceeded(report);
  const reportPath = path.join(outDir, 'script-sandbox-isolation-report.json');
  await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify({
    ok: report.ok,
    report: reportPath,
    screenshots: report.screenshots,
    checks: report.checks.length,
    failed: report.checks.filter((item) => !item.ok).map((item) => item.name),
  }, null, 2));
  if (!report.ok) process.exit(1);
}

main().catch(async (error) => {
  const outDir = path.resolve(path.join('test-screenshots', 'browser-isolation'));
  await fs.mkdir(outDir, { recursive: true }).catch(() => {});
  const reportPath = path.join(outDir, 'script-sandbox-isolation-crash.json');
  const payload = {
    ok: false,
    code: 'browser_isolation_drill_crashed',
    message: error && error.message ? error.message : String(error),
    stack: error && error.stack ? error.stack : '',
    generatedAt: new Date().toISOString(),
  };
  await fs.writeFile(reportPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8').catch(() => {});
  console.error(JSON.stringify({ ok: false, report: reportPath, message: payload.message }, null, 2));
  process.exit(1);
});
