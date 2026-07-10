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

function isHttpUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function urlOrigin(url) {
  try {
    return new URL(url).origin;
  } catch {
    return '';
  }
}

function isBenignMissingResource(entry) {
  return /\/favicon\.ico(?:$|\?)/.test(entry.url);
}

async function waitForSandboxTerminalState(page, timeoutMs) {
  await page.waitForFunction(() => {
    const card = document.querySelector('[data-backend-sandbox-card]');
    return card && card.dataset && ['ready', 'timeout', 'error'].includes(card.dataset.state);
  }, undefined, { timeout: timeoutMs });
  return page.evaluate(() => {
    const card = document.querySelector('[data-backend-sandbox-card]');
    return {
      state: card ? card.dataset.state || '' : '',
      status: card ? (card.querySelector('[data-backend-sandbox-status]')?.textContent || '') : '',
      message: card ? (card.querySelector('[data-backend-sandbox-message]')?.textContent || '') : '',
    };
  });
}

async function waitForReadySandboxFrame(page, timeoutMs, selector = '[data-backend-sandbox-frame]') {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const remaining = Math.max(1, timeoutMs - (Date.now() - started));
    await page.waitForFunction((iframeSelector) => {
      const iframe = document.querySelector(iframeSelector);
      const card = iframe && iframe.closest('[data-backend-sandbox-card]');
      return Boolean(iframe && card && card.dataset && card.dataset.state === 'ready');
    }, selector, { timeout: remaining });
    const iframeHandle = await page.$(selector);
    const frame = iframeHandle ? await iframeHandle.contentFrame() : null;
    const state = await page.evaluate((iframeSelector) => {
      const iframe = document.querySelector(iframeSelector);
      const card = iframe && iframe.closest('[data-backend-sandbox-card]');
      return {
        state: card && card.dataset ? card.dataset.state || '' : '',
        status: card ? (card.querySelector('[data-backend-sandbox-status]')?.textContent || '') : '',
        message: card ? (card.querySelector('[data-backend-sandbox-message]')?.textContent || '') : '',
      };
    }, selector);
    if (iframeHandle && frame && state.state === 'ready') {
      return { iframeHandle, frame, state };
    }
    await page.waitForTimeout(50);
  }
  return null;
}

async function inspectEnergySandbox(frame) {
  return frame.evaluate(() => {
    const requiredIds = [
      'energy-canvas',
      'energy-friction',
      'energy-play',
      'energy-reset',
      'energy-info',
    ];
    const root = document.getElementById('astra-sandbox-root');
    const nodes = Object.fromEntries(requiredIds.map((id) => [id, document.getElementById(id)]));
    const canvas = nodes['energy-canvas'];
    const rect = canvas ? canvas.getBoundingClientRect() : null;
    const runtime = window.EnergyConservation || null;
    return {
      requiredIds,
      missingIds: requiredIds.filter((id) => !nodes[id]),
      rootOwnsAll: Boolean(root) && requiredIds.every((id) => root.contains(nodes[id])),
      canvas: canvas ? {
        bitmapWidth: canvas.width,
        bitmapHeight: canvas.height,
        clientWidth: rect ? rect.width : 0,
        clientHeight: rect ? rect.height : 0,
        hasContext: Boolean(canvas.getContext && canvas.getContext('2d')),
      } : null,
      frictionValue: nodes['energy-friction'] ? nodes['energy-friction'].value : '',
      playText: nodes['energy-play'] ? nodes['energy-play'].textContent || '' : '',
      resetText: nodes['energy-reset'] ? nodes['energy-reset'].textContent || '' : '',
      infoTextLength: nodes['energy-info'] ? (nodes['energy-info'].textContent || '').trim().length : 0,
      runtime: runtime ? {
        rootMatches: runtime.root === root,
        canvasMatches: runtime.canvas === canvas,
        running: runtime.running === true,
        width: Number(runtime.W || 0),
        height: Number(runtime.H || 0),
      } : null,
    };
  });
}

async function exerciseEnergySandbox(frame, frictionValue) {
  return frame.evaluate((requestedFriction) => {
    const slider = document.getElementById('energy-friction');
    const output = document.getElementById('energy-friction-value');
    const play = document.getElementById('energy-play');
    const reset = document.getElementById('energy-reset');
    const info = document.getElementById('energy-info');
    const runtime = window.EnergyConservation || null;
    if (!slider || !play || !reset || !info || !runtime) {
      return {
        ok: false,
        missing: {
          slider: !slider,
          play: !play,
          reset: !reset,
          info: !info,
          runtime: !runtime,
        },
      };
    }

    const initialRunning = runtime.running === true;
    slider.value = String(requestedFriction);
    slider.dispatchEvent(new Event('input', { bubbles: true }));
    slider.dispatchEvent(new Event('change', { bubbles: true }));
    const frictionApplied = Math.abs(Number(runtime.friction) - Number(requestedFriction)) < 0.0001;
    const outputUpdated = Boolean(output) && output.textContent.trim() === Number(requestedFriction).toFixed(2);
    const infoUpdated = info.textContent.includes(Number(requestedFriction).toFixed(2));

    play.click();
    const paused = runtime.running === false;
    const pausedText = play.textContent || '';
    const pausedLabelUpdated = pausedText.includes('播放');
    play.click();
    const resumed = runtime.running === true;
    const resumedText = play.textContent || '';
    const resumedLabelUpdated = resumedText.includes('暂停');

    runtime.ballPos = 0.42;
    runtime.ballSpeed = 2;
    runtime.internalEnergy = 3;
    reset.click();
    const resetApplied = Number(runtime.ballPos) < 0.01
      && Number(runtime.internalEnergy) < 0.01
      && runtime.running === true;

    return {
      ok: initialRunning && frictionApplied && outputUpdated && infoUpdated
        && paused && pausedLabelUpdated && resumed && resumedLabelUpdated && resetApplied,
      initialRunning,
      frictionApplied,
      outputUpdated,
      infoUpdated,
      runtimeFriction: Number(runtime.friction),
      outputText: output ? output.textContent || '' : '',
      paused,
      pausedText,
      pausedLabelUpdated,
      resumed,
      resumedText,
      resumedLabelUpdated,
      resetApplied,
      resetState: {
        ballPos: Number(runtime.ballPos),
        internalEnergy: Number(runtime.internalEnergy),
        running: runtime.running === true,
      },
    };
  }, frictionValue);
}

async function inspectCacheStorage(page) {
  return page.evaluate(async () => {
    if (!('caches' in window)) {
      return { supported: false, cacheNames: [], entries: [], apiEntries: [] };
    }
    const cacheNames = await caches.keys();
    const entries = [];
    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      const requests = await cache.keys();
      for (const request of requests) {
        entries.push({ cacheName, url: request.url, method: request.method });
      }
    }
    const apiEntries = entries.filter((entry) => {
      try {
        return /^\/api(?:\/|$)/.test(new URL(entry.url).pathname);
      } catch {
        return false;
      }
    });
    return { supported: true, cacheNames, entries, apiEntries };
  });
}

async function settleCaptureTasks(tasks) {
  let observed = -1;
  while (observed !== tasks.length) {
    observed = tasks.length;
    await Promise.allSettled(tasks.slice());
  }
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
  const allowedOrigins = new Set([apiBase, webBase, appUrl].map(urlOrigin).filter(Boolean));

  await fs.mkdir(outDir, { recursive: true });

  const report = {
    ok: false,
    phase: 'V6.6.60',
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
    energy: {},
    parentDom: {},
    cacheStorage: {},
    mobile: {},
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
    const nonceMatch = csp.match(/script-src 'nonce-([^']+)'/);
    const bootstrapSrcMatch = sandboxDocument.text.match(/<script\s+src="([^"]+)"\s+nonce="([^"]+)"\s+defer><\/script>/);
    const bootstrapUrl = bootstrapSrcMatch
      ? new URL(bootstrapSrcMatch[1], sandboxUrl).href
      : '';
    const bootstrap = bootstrapUrl ? await fetchText(bootstrapUrl) : null;
    assertCheck(report, 'sandbox document has hardened CSP and no-store headers', sandboxDocument.status === 200
      && /script-src 'nonce-[^']+'/.test(csp)
      && /'sha256-[A-Za-z0-9+/=]+'/.test(csp)
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
    assertCheck(report, 'bootstrap nonce cannot authorize mutable asset scripts', Boolean(
      nonceMatch
      && bootstrapSrcMatch
      && nonceMatch[1] === bootstrapSrcMatch[2]
      && bootstrap
      && bootstrap.status === 200
      && !bootstrap.text.includes(nonceMatch[1])
      && !/currentScript|\.nonce\b|setAttribute\(\s*['"]nonce/.test(bootstrap.text)
      && /"integrity":"sha256-[A-Za-z0-9+/=]+"/.test(bootstrap.text)
      && /script\.integrity\s*=\s*asset\.integrity/.test(bootstrap.text)
    ), {
      bootstrapUrl,
      bootstrapStatus: bootstrap && bootstrap.status,
      cspHasAssetHash: /'sha256-[A-Za-z0-9+/=]+'/.test(csp),
      nonceExposedToBootstrap: Boolean(nonceMatch && bootstrap && bootstrap.text.includes(nonceMatch[1])),
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
    const responseCaptureTasks = [];

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
      if (!isHttpUrl(url)) return;
      const capture = Promise.resolve(response.headers())
        .then((headers) => {
          report.network.push({
            url,
            origin: urlOrigin(url),
            status: response.status(),
            contentType: headers['content-type'] || '',
            cacheControl: headers['cache-control'] || '',
            csp: headers['content-security-policy'] || '',
          });
        })
        .catch((error) => {
          report.network.push({
            url,
            origin: urlOrigin(url),
            status: response.status(),
            headerCaptureError: error && error.message ? error.message : String(error),
          });
        });
      responseCaptureTasks.push(capture);
    });

    await page.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    await page.evaluate(() => {
      localStorage.setItem('__astra_parent_local_secret', 'parent-local-secret');
      sessionStorage.setItem('__astra_parent_session_secret', 'parent-session-secret');
      document.cookie = '__astra_parent_cookie_secret=parent-cookie-secret; path=/; SameSite=Lax';
      document.body.setAttribute('data-astra-parent-secret', 'parent-dom-secret');
    });

    const initialReady = await waitForReadySandboxFrame(page, timeoutMs);
    if (!initialReady) {
      throw new Error('Sandbox iframe did not reach a stable ready state.');
    }
    const cardState = initialReady.state;
    let activeIframeHandle = initialReady.iframeHandle;
    const iframeAttrs = await activeIframeHandle.evaluate((iframe) => ({
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

    let activeFrame = initialReady.frame;
    assertCheck(report, 'browser exposes loaded sandbox frame', Boolean(activeFrame), {
      frameUrl: activeFrame ? activeFrame.url() : '',
    });
    if (!activeFrame) {
      throw new Error('Sandbox iframe frame was not available.');
    }
    await activeFrame.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
    assertCheck(report, 'parent adapter reaches the ready sandbox state', cardState.state === 'ready', cardState);

    const initialEnergy = await inspectEnergySandbox(activeFrame);
    report.energy.initial = initialEnergy;
    const initialCanvas = initialEnergy.canvas || {};
    const initialRuntime = initialEnergy.runtime || {};
    assertCheck(report, 'sandbox document renders complete energy DOM and a sized canvas', initialEnergy.missingIds.length === 0
      && initialEnergy.rootOwnsAll
      && initialCanvas.hasContext === true
      && initialCanvas.bitmapWidth > 0
      && initialCanvas.bitmapHeight > 0
      && initialCanvas.clientWidth > 0
      && initialCanvas.clientHeight > 0
      && initialEnergy.infoTextLength > 0
      && initialRuntime.rootMatches === true
      && initialRuntime.canvasMatches === true
      && initialRuntime.width > 0
      && initialRuntime.height > 0, initialEnergy);

    const initialInteraction = await exerciseEnergySandbox(activeFrame, 0.23);
    report.energy.initialInteraction = initialInteraction;
    assertCheck(report, 'sandbox energy slider, playback, and reset controls are interactive', initialInteraction.ok === true, initialInteraction);

    const isolation = await activeFrame.evaluate(() => {
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
          ownLocalStorage: attempt('ownLocalStorage', () => {
            localStorage.setItem('__astra_sandbox_local_probe', 'sandbox-local-secret');
            return localStorage.getItem('__astra_sandbox_local_probe');
          }),
          ownSessionStorage: attempt('ownSessionStorage', () => {
            sessionStorage.setItem('__astra_sandbox_session_probe', 'sandbox-session-secret');
            return sessionStorage.getItem('__astra_sandbox_session_probe');
          }),
          ownCookie: attempt('ownCookie', () => {
            document.cookie = '__astra_sandbox_cookie_probe=sandbox-cookie-secret; path=/; SameSite=Lax';
            return document.cookie;
          }),
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
    const ownStorageAttempts = [
      isolation.attempts.ownLocalStorage,
      isolation.attempts.ownSessionStorage,
    ];
    const ownCookieAttempt = isolation.attempts.ownCookie;
    assertCheck(report, 'opaque sandbox cannot use its own persistent storage or cookie jar', isolation.globalOrigin === 'null'
      && ownStorageAttempts.every((item) => item && item.ok === false)
      && ownCookieAttempt
      && (ownCookieAttempt.ok === false || !String(ownCookieAttempt.value || '').includes('sandbox-cookie-secret')), {
      globalOrigin: isolation.globalOrigin,
      storageAttempts: ownStorageAttempts,
      cookieAttempt: ownCookieAttempt,
    });
    assertCheck(report, 'sandbox document root and metadata are present', isolation.hasSandboxRoot && isolation.sandboxId === manifest.sandboxId, {
      hasSandboxRoot: isolation.hasSandboxRoot,
      sandboxId: isolation.sandboxId,
      expectedSandboxId: manifest && manifest.sandboxId,
    });

    await activeIframeHandle.evaluate((iframe) => {
      iframe.dataset.astraProofGeneration = 'initial';
    });
    const parentDom = await page.evaluate(() => {
      const ids = ['energy-canvas', 'energy-friction', 'energy-play', 'energy-reset', 'energy-info'];
      const beforeIds = ids.filter((id) => Boolean(document.getElementById(id)));
      ids.forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.remove();
      });
      const remainingIds = ids.filter((id) => Boolean(document.getElementById(id)));
      const refresh = document.querySelector('[data-backend-sandbox-refresh]');
      if (refresh) refresh.click();
      return {
        requiredIds: ids,
        beforeIds,
        removedIds: beforeIds.filter((id) => !remainingIds.includes(id)),
        remainingIds,
        refreshClicked: Boolean(refresh),
      };
    });
    report.parentDom = parentDom;
    assertCheck(report, 'parent energy DOM is removed before sandbox remount', parentDom.beforeIds.length === parentDom.requiredIds.length
      && parentDom.removedIds.length === parentDom.requiredIds.length
      && parentDom.remainingIds.length === 0
      && parentDom.refreshClicked, parentDom);

    const remountedReady = await waitForReadySandboxFrame(
      page,
      timeoutMs,
      '[data-backend-sandbox-frame]:not([data-astra-proof-generation="initial"])',
    );
    activeIframeHandle = remountedReady && remountedReady.iframeHandle;
    activeFrame = remountedReady && remountedReady.frame;
    assertCheck(report, 'browser exposes remounted sandbox frame after parent DOM removal', Boolean(activeFrame), {
      frameUrl: activeFrame ? activeFrame.url() : '',
    });
    if (!activeFrame) {
      throw new Error('Remounted sandbox iframe frame was not available.');
    }
    await activeFrame.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
    const remountedCardState = remountedReady ? remountedReady.state : { state: '', status: '', message: '' };
    assertCheck(report, 'sandbox remount reaches ready without parent energy DOM', remountedCardState.state === 'ready', remountedCardState);

    const remountedParentIds = await page.evaluate(() => (
      ['energy-canvas', 'energy-friction', 'energy-play', 'energy-reset', 'energy-info']
        .filter((id) => Boolean(document.getElementById(id)))
    ));
    const remountedEnergy = await inspectEnergySandbox(activeFrame);
    const remountedInteraction = await exerciseEnergySandbox(activeFrame, 0.07);
    report.energy.remounted = remountedEnergy;
    report.energy.remountedInteraction = remountedInteraction;
    const remountedCanvas = remountedEnergy.canvas || {};
    const remountedRuntime = remountedEnergy.runtime || {};
    assertCheck(report, 'remounted sandbox remains self-contained and interactive', remountedParentIds.length === 0
      && remountedEnergy.missingIds.length === 0
      && remountedEnergy.rootOwnsAll
      && remountedCanvas.hasContext === true
      && remountedCanvas.bitmapWidth > 0
      && remountedCanvas.bitmapHeight > 0
      && remountedCanvas.clientWidth > 0
      && remountedCanvas.clientHeight > 0
      && remountedRuntime.rootMatches === true
      && remountedRuntime.canvasMatches === true
      && remountedInteraction.ok === true, {
      parentIds: remountedParentIds,
      energy: remountedEnergy,
      interaction: remountedInteraction,
    });

    await page.waitForTimeout(150);
    const cacheStorage = await inspectCacheStorage(page);
    report.cacheStorage = cacheStorage;
    assertCheck(report, 'CacheStorage contains no API request entries', cacheStorage.supported === true
      && cacheStorage.apiEntries.length === 0, {
      supported: cacheStorage.supported,
      cacheNames: cacheStorage.cacheNames,
      totalEntries: cacheStorage.entries.length,
      apiEntries: cacheStorage.apiEntries,
    });

    await settleCaptureTasks(responseCaptureTasks);
    const seriousConsole = report.console.filter((item) => ['error', 'warning', 'warn'].includes(item.type)
      && !/favicon\.ico/i.test(item.text));
    const badNetwork = report.network.filter((item) => item.status >= 400 && !isBenignMissingResource(item));
    const unexpectedExternal = report.network.filter((item) => isHttpUrl(item.url) && !allowedOrigins.has(item.origin));
    assertCheck(report, 'browser console has no warnings or errors', seriousConsole.length === 0 && report.pageErrors.length === 0, {
      warningOrErrorCount: seriousConsole.length,
      warningOrErrors: seriousConsole,
      pageErrorCount: report.pageErrors.length,
    });
    assertCheck(report, 'browser network stays within configured origins and executable resources load', badNetwork.length === 0
      && unexpectedExternal.length === 0
      && report.requestFailures.length === 0, {
      allowedOrigins: Array.from(allowedOrigins),
      badNetwork,
      unexpectedExternal,
      requestFailures: report.requestFailures,
    });

    const pageScreenshot = path.join(outDir, 'script-sandbox-isolation-page.png');
    await page.screenshot({ path: pageScreenshot, fullPage: true });
    report.screenshots.page = pageScreenshot;

    const box = await activeIframeHandle.boundingBox();
    if (box) {
      const iframeScreenshot = path.join(outDir, 'script-sandbox-isolation-iframe.png');
      await page.screenshot({ path: iframeScreenshot, clip: box });
      report.screenshots.iframe = iframeScreenshot;
    }

    await page.reload({ waitUntil: 'domcontentloaded', timeout: timeoutMs });
    const navigationReady = await waitForReadySandboxFrame(page, timeoutMs);
    const navigationReadyState = navigationReady ? navigationReady.state : { state: '', status: '', message: '' };
    const navigationFrame = navigationReady && navigationReady.frame;
    if (!navigationFrame) {
      throw new Error('Reloaded sandbox iframe frame was not available.');
    }
    await navigationFrame.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
    assertCheck(report, 'sandbox reload restores the static fallback prerequisite', navigationReadyState.state === 'ready', {
      navigationReadyState,
    });
    await navigationFrame.evaluate(() => window.location.replace('about:blank')).catch(() => {});
    await page.waitForFunction(() => {
      const card = document.querySelector('[data-backend-sandbox-card]');
      return card && card.dataset && card.dataset.state === 'error';
    }, undefined, { timeout: timeoutMs });
    const navigationState = await page.evaluate(() => {
      const card = document.querySelector('[data-backend-sandbox-card]');
      return {
        state: card ? card.dataset.state || '' : '',
        status: card ? (card.querySelector('[data-backend-sandbox-status]')?.textContent || '') : '',
        message: card ? (card.querySelector('[data-backend-sandbox-message]')?.textContent || '') : '',
      };
    });
    const navigationFallback = await page.evaluate(() => {
      const card = document.querySelector('[data-backend-sandbox-card]');
      const iframe = card && card.querySelector('[data-backend-sandbox-frame]');
      const target = card && card.parentElement;
      const runtime = window.EnergyConservation || null;
      return {
        state: card ? card.dataset.state || '' : '',
        iframeHasSrc: Boolean(iframe && iframe.hasAttribute('src')),
        sandboxRuntimeActive: Boolean(target && target.classList.contains('backend-sandbox-runtime-active')),
        staticRuntimeRunning: Boolean(runtime && runtime.running === true),
      };
    });
    assertCheck(report, 'unexpected iframe navigation fails closed and restores static runtime', navigationState.state === 'error'
      && navigationFallback.state === 'error'
      && navigationFallback.iframeHasSrc === false
      && navigationFallback.sandboxRuntimeActive === false
      && navigationFallback.staticRuntimeRunning === true, {
      navigationState,
      navigationFallback,
    });

    await context.close();

    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      ignoreHTTPSErrors: true,
    });
    const mobilePage = await mobileContext.newPage();
    const mobileConsole = [];
    const mobilePageErrors = [];
    mobilePage.on('console', (message) => {
      if (['error', 'warning', 'warn'].includes(message.type())) {
        mobileConsole.push({ type: message.type(), text: message.text().slice(0, 1000) });
      }
    });
    mobilePage.on('pageerror', (error) => {
      mobilePageErrors.push({ name: error.name, message: error.message.slice(0, 1000) });
    });
    await mobilePage.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    await mobilePage.waitForSelector('[data-backend-sandbox-frame]', { timeout: timeoutMs });
    const mobileSandboxState = await waitForSandboxTerminalState(mobilePage, timeoutMs);
    const mobileGuideButton = mobilePage.getByRole('button', { name: '知道了，开始探索' });
    const mobileGuideCount = await mobileGuideButton.count();
    let mobileGuideDismissed = false;
    if (mobileGuideCount === 1 && await mobileGuideButton.isVisible()) {
      await mobileGuideButton.click();
      await mobileGuideButton.waitFor({ state: 'hidden', timeout: timeoutMs });
      mobileGuideDismissed = true;
    }
    const mobileLayout = await mobilePage.evaluate(() => {
      const target = document.querySelector('#page-physics [data-module="energy-conservation"]');
      const card = target && target.querySelector('[data-backend-sandbox-card]');
      const iframe = card && card.querySelector('[data-backend-sandbox-frame]');
      const rect = card ? card.getBoundingClientRect() : null;
      return {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        documentWidth: document.documentElement.scrollWidth,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        cardWithinViewport: Boolean(rect) && rect.left >= -1 && rect.right <= window.innerWidth + 1,
        cardRect: rect ? { left: rect.left, right: rect.right, width: rect.width } : null,
        sandboxState: card && card.dataset ? card.dataset.state || '' : '',
        iframeSandbox: iframe ? iframe.getAttribute('sandbox') || '' : '',
      };
    });
    const mobileScreenshot = path.join(outDir, 'script-sandbox-isolation-mobile.png');
    await mobilePage.screenshot({ path: mobileScreenshot, fullPage: false });
    report.screenshots.mobile = mobileScreenshot;
    report.mobile = {
      viewport: { width: 390, height: 844 },
      guideDismissed: mobileGuideDismissed,
      sandbox: mobileSandboxState,
      layout: mobileLayout,
      console: mobileConsole,
      pageErrors: mobilePageErrors,
    };
    assertCheck(report, 'mobile viewport keeps the sandbox ready without horizontal overflow', mobileSandboxState.state === 'ready'
      && mobileLayout.innerWidth === 390
      && mobileLayout.innerHeight === 844
      && mobileLayout.horizontalOverflow === false
      && mobileLayout.cardWithinViewport === true
      && mobileLayout.sandboxState === 'ready'
      && mobileLayout.iframeSandbox === 'allow-scripts'
      && mobileConsole.length === 0
      && mobilePageErrors.length === 0, report.mobile);
    await mobileContext.close();
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
  const crashArgs = parseArgs(process.argv.slice(2));
  const outDir = path.resolve(String(crashArgs.out || path.join('test-screenshots', 'browser-isolation')));
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
