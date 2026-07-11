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
    if (!next || next.startsWith('--')) parsed[raw] = true;
    else {
      parsed[raw] = next;
      index += 1;
    }
  }
  return parsed;
}

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function isLocalUrl(value) {
  try {
    const parsed = new URL(value);
    return ['127.0.0.1', 'localhost', '::1'].includes(parsed.hostname)
      && ['http:', 'https:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

function safeName(value) {
  return String(value || '').replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 80);
}

async function launchBrowser(args) {
  const requested = args.channel || process.env.ASTRA_BROWSER_CHANNEL || '';
  const channels = requested ? [requested] : ['', 'msedge', 'chrome'];
  const errors = [];
  for (const channel of channels) {
    try {
      const browser = await chromium.launch({
        headless: !args.headed,
        ...(channel ? { channel } : {}),
      });
      return { browser, channel: channel || 'playwright-chromium' };
    } catch (error) {
      errors.push(`${channel || 'playwright-chromium'}: ${String(error && error.message || error).split('\n')[0]}`);
    }
  }
  throw new Error(`Unable to launch Chromium-compatible browser. ${errors.join(' | ')}`);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || 'GET',
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await response.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = null; }
  return { status: response.status, body, text };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function roleUrl(webBase, apiBase, role) {
  return `${webBase}/?apiBase=${encodeURIComponent(apiBase)}#${role}`;
}

function attachDiagnostics(page, bucket, label) {
  page.on('console', (message) => {
    if (/^Failed to load resource:/.test(message.text())) return;
    if (['warning', 'error'].includes(message.type())) {
      bucket.push({ kind: 'console', label, level: message.type(), message: message.text() });
    }
  });
  page.on('pageerror', (error) => {
    bucket.push({ kind: 'pageerror', label, message: String(error && error.message || error) });
  });
  page.on('requestfailed', (request) => {
    if (/\/favicon\.ico(?:$|\?)/.test(request.url())) return;
    bucket.push({
      kind: 'requestfailed',
      label,
      url: request.url(),
      message: request.failure() && request.failure().errorText,
    });
  });
  page.on('response', (response) => {
    if (response.status() < 400) return;
    const resource = new URL(response.url());
    const expectedAuthChallenge = response.status() === 401 && resource.pathname === '/api/users/me';
    const expectedPermissionDenial = response.status() === 403 && (
      resource.pathname === '/api/admin/stats'
      || resource.pathname === '/api/admin/class-join-requests'
      || /^\/api\/assignments\/\d+\/review$/.test(resource.pathname)
    );
    if (expectedAuthChallenge || expectedPermissionDenial) return;
    bucket.push({ kind: 'http', label, status: response.status(), url: response.url() });
  });
}

async function createRolePage(browser, report, webBase, apiBase, role, viewport = { width: 1440, height: 1000 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  attachDiagnostics(page, report.browserIssues, role);
  await page.goto(roleUrl(webBase, apiBase, role), { waitUntil: 'domcontentloaded' });
  await page.locator('[data-app-auth-overlay]:not([hidden])').waitFor({ state: 'visible' });
  await page.locator('[data-app-auth-form="login"]').waitFor({ state: 'visible' });
  return { context, page };
}

async function registerFromUi(page, role, account) {
  const registerTab = page.locator('[data-app-auth-view="register"]');
  assert(await registerTab.count() === 1, `${role} registration tab must exist exactly once`);
  await registerTab.click();
  const form = page.locator('[data-app-auth-form="register"]');
  await form.locator('[name="username"]').fill(account.username);
  await form.locator('[name="display_name"]').fill(account.displayName);
  await form.locator('[name="role"]').selectOption(role);
  await form.locator('[name="password"]').fill(account.password);
  await form.locator('[name="password_confirm"]').fill(account.password);
  await form.locator('button[type="submit"]').click();
  await page.locator(`[data-auth-ui="account"][data-auth-role="${role}"]`).waitFor({ state: 'visible' });
}

async function loginFromUi(page, role, account) {
  const form = page.locator('[data-app-auth-form="login"]');
  await form.locator('[name="username"]').fill(account.username);
  await form.locator('[name="password"]').fill(account.password);
  await form.locator('button[type="submit"]').click();
  await page.locator(`[data-auth-ui="account"][data-auth-role="${role}"]`).waitFor({ state: 'visible' });
}

async function pageApi(page, apiBase, apiPath, options = {}) {
  return page.evaluate(async ({ base, resource, request }) => {
    const response = await fetch(base + resource, {
      method: request.method || 'GET',
      credentials: 'include',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...(request.body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: request.body ? JSON.stringify(request.body) : undefined,
    });
    const text = await response.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = null; }
    return { status: response.status, body };
  }, { base: apiBase, resource: apiPath, request: options });
}

async function teacherForm(page, type, fields, successText) {
  const form = page.locator(`[data-teacher-form="${type}"]`);
  await form.waitFor({ state: 'visible' });
  for (const [name, value] of Object.entries(fields || {})) {
    const control = form.locator(`[name="${name}"]`);
    if (typeof value === 'object' && value && value.select !== undefined) {
      await control.selectOption(String(value.select));
    } else {
      await control.fill(String(value));
    }
  }
  await form.locator('button[type="submit"]').click();
  await page.locator('[data-teacher-flash]').filter({ hasText: successText }).waitFor({ state: 'visible' });
}

async function selectedValue(page, selector) {
  return page.locator(selector).inputValue();
}

async function responsiveEvidence(page, role, outDir) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(`[data-auth-ui="account"][data-auth-role="${role}"]`).waitFor({ state: 'visible' });
  const layout = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    clippedAuthNodes: Array.from(document.querySelectorAll('[data-auth-ui] *'))
      .filter((element) => element.scrollWidth > element.clientWidth + 1)
      .slice(0, 10)
      .map((element) => ({
        tag: element.tagName,
        className: String(element.className || ''),
        text: String(element.textContent || '').trim().slice(0, 80),
      })),
  }));
  const screenshot = path.join(outDir, `${safeName(role)}-390x844.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  assert(layout.bodyScrollWidth <= layout.innerWidth, `${role} body overflows 390px viewport`);
  assert(layout.documentScrollWidth <= layout.innerWidth, `${role} document overflows 390px viewport`);
  assert(layout.clippedAuthNodes.length === 0, `${role} auth UI contains clipped nodes at 390px`);
  return { ...layout, screenshot };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const apiBase = stripTrailingSlash(args.api || '');
  const webBase = stripTrailingSlash(args.web || '');
  const outDir = path.resolve(args.out || path.join('test-screenshots', 'role-workflows'));
  const report = {
    ok: false,
    generatedAt: new Date().toISOString(),
    environment: { apiBase, webBase, browserChannel: null, isolatedConfirmation: false },
    checks: [],
    entities: {},
    responsive: {},
    browserIssues: [],
    failure: null,
  };
  const contexts = [];
  let browser = null;

  function record(name, evidence = {}) {
    report.checks.push({ name, ok: true, evidence });
  }

  try {
    assert(args['confirm-isolated-environment'] === true, 'Pass --confirm-isolated-environment for a disposable local database');
    assert(isLocalUrl(apiBase) && isLocalUrl(webBase), 'Role workflow proof only accepts local API and web URLs');
    report.environment.isolatedConfirmation = true;

    const health = await fetchJson(`${apiBase}/api/health`);
    assert(health.status === 200, `API health failed with ${health.status}`);
    assert(['development', 'test', 'testing'].includes(health.body && health.body.environment), 'API must report development/test/testing');
    record('isolated local environment guard', { environment: health.body.environment });

    await fs.mkdir(outDir, { recursive: true });
    const launched = await launchBrowser(args);
    browser = launched.browser;
    report.environment.browserChannel = launched.channel;

    const runId = Date.now().toString(36);
    const password = `Astra!${runId}Aa9`;
    const accounts = {
      teacher: { username: `e2e_teacher_${runId}`, displayName: '端到端教师', password },
      student: { username: `e2e_student_${runId}`, displayName: '端到端学生', password },
      applicant: { username: `e2e_applicant_${runId}`, displayName: '审批申请学生', password },
      outsider: { username: `e2e_outsider_${runId}`, displayName: '越权验证学生', password },
      admin: { username: `e2e_admin_${runId}`, displayName: '端到端管理员', password },
    };

    const bootstrap = await fetchJson(`${apiBase}/api/admin/bootstrap`, {
      method: 'POST',
      body: {
        username: accounts.admin.username,
        display_name: accounts.admin.displayName,
        password: accounts.admin.password,
        ...(args['admin-bootstrap-token'] ? { bootstrap_token: String(args['admin-bootstrap-token']) } : {}),
      },
    });
    assert(bootstrap.status === 201, `Admin bootstrap failed with ${bootstrap.status}: ${bootstrap.text}`);
    record('controlled admin bootstrap', { role: bootstrap.body && bootstrap.body.role });

    const teacherRuntime = await createRolePage(browser, report, webBase, apiBase, 'teacher');
    contexts.push(teacherRuntime.context);
    await registerFromUi(teacherRuntime.page, 'teacher', accounts.teacher);
    await teacherRuntime.page.locator('[data-teacher-dashboard]:not([hidden])').waitFor({ state: 'visible' });
    record('teacher first-party registration and dashboard');

    await teacherForm(teacherRuntime.page, 'school', {
      name: `E2E School ${runId}`,
      region: 'Shanghai',
    }, '学校已创建');
    const schoolId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="schoolId"]');

    await teacherForm(teacherRuntime.page, 'class', {
      name: `E2E Class ${runId}`,
      grade: '10',
      term: '2026A',
    }, '班级已创建');
    const classId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="classId"]');

    await teacherForm(teacherRuntime.page, 'course', {
      title: `E2E Course ${runId}`,
      status: { select: 'published' },
      summary: '隔离三角色端到端验收课程',
    }, '课程已创建');
    const courseId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="courseId"]');

    await teacherForm(teacherRuntime.page, 'attach', {}, '课程已挂接班级');
    await teacherForm(teacherRuntime.page, 'unit', {
      title: `E2E Unit ${runId}`,
      position: '1',
      status: { select: 'published' },
      content_slug: 'physics/energy-conservation',
    }, '单元已创建');
    const unitId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="unitId"]');

    await teacherForm(teacherRuntime.page, 'assignment', {
      unit_id: { select: unitId },
      title: `E2E Assignment ${runId}`,
      max_score: '20',
      status: { select: 'active' },
      audience_mode: { select: 'all_attached_classes' },
      description: '提交能量守恒推导过程。',
    }, '作业已创建');
    const assignmentId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="assignmentId"]');
    report.entities = { schoolId, classId, courseId, unitId, assignmentId };
    record('teacher creates published course workflow', report.entities);

    const studentRuntime = await createRolePage(browser, report, webBase, apiBase, 'student');
    contexts.push(studentRuntime.context);
    await registerFromUi(studentRuntime.page, 'student', accounts.student);
    const joinForm = studentRuntime.page.locator('[data-student-join-form]');
    await joinForm.locator('[name="class_id"]').fill(classId);
    await joinForm.locator('button[type="submit"]').click();
    await studentRuntime.page.locator('[data-student-layout]:not([hidden])').waitFor({ state: 'visible' });
    const assignmentButton = studentRuntime.page.locator(`[data-student-panel="assignments"] [data-student-assignment-id="${assignmentId}"]`);
    await assignmentButton.waitFor({ state: 'visible' });
    record('student joins class and sees assignment', { classId, assignmentId });

    assert(await assignmentButton.count() === 1, 'Student assignment action must be unique inside assignment panel');
    await assignmentButton.click();
    const submissionForm = studentRuntime.page.locator(`[data-student-submission-form][data-assignment-id="${assignmentId}"]`);
    await submissionForm.waitFor({ state: 'visible' });
    const answer = `E2E answer ${runId}: energy before equals energy after.`;
    await submissionForm.locator('textarea').fill(answer);
    await submissionForm.locator('button[type="submit"]').click();
    await studentRuntime.page.locator('[data-student-panel="submission"] .student-review-block').filter({ hasText: answer }).waitFor({ state: 'visible' });
    record('student submits assignment without retry', { assignmentId });

    const teacherRefresh = teacherRuntime.page.locator('[data-teacher-action="refresh"]');
    await teacherRefresh.click();
    const gradeForm = teacherRuntime.page.locator('[data-teacher-form="grade"]');
    await gradeForm.locator('[name="submission_id"]:not([disabled])').waitFor({ state: 'visible' });
    await gradeForm.locator('[name="score"]').fill('18');
    await gradeForm.locator('[name="status"]').selectOption('graded');
    await gradeForm.locator('[name="feedback"]').fill(`E2E feedback ${runId}`);
    await gradeForm.locator('button[type="submit"]').click();
    await teacherRuntime.page.locator('[data-teacher-flash]').filter({ hasText: '评分已提交' }).waitFor({ state: 'visible' });
    record('teacher grades submission', { score: 18 });

    await studentRuntime.page.locator('[data-student-action="refresh"]').click();
    await studentRuntime.page.locator('[data-student-panel="submission"] .student-review-block').filter({ hasText: `E2E feedback ${runId}` }).waitFor({ state: 'visible' });
    record('student receives authoritative grade feedback');

    const studentAdminDenied = await pageApi(studentRuntime.page, apiBase, '/api/admin/stats');
    assert(studentAdminDenied.status === 403, `Student admin access expected 403, got ${studentAdminDenied.status}`);
    const teacherAdminDenied = await pageApi(teacherRuntime.page, apiBase, '/api/admin/class-join-requests');
    assert(teacherAdminDenied.status === 403, `Teacher admin queue expected 403, got ${teacherAdminDenied.status}`);
    record('role permission denials', { studentAdmin: 403, teacherAdminQueue: 403 });

    const applicantRuntime = await createRolePage(browser, report, webBase, apiBase, 'student');
    contexts.push(applicantRuntime.context);
    await registerFromUi(applicantRuntime.page, 'student', accounts.applicant);
    const joinRequest = await pageApi(applicantRuntime.page, apiBase, `/api/classes/${classId}/join-requests`, {
      method: 'POST',
      body: { role: 'student', message: `E2E approval ${runId}` },
    });
    assert(joinRequest.status === 201, `Join request expected 201, got ${joinRequest.status}`);
    const joinRequestId = String(joinRequest.body.id);
    report.entities.joinRequestId = joinRequestId;

    const adminRuntime = await createRolePage(browser, report, webBase, apiBase, 'admin');
    contexts.push(adminRuntime.context);
    await loginFromUi(adminRuntime.page, 'admin', accounts.admin);
    await adminRuntime.page.locator('[data-admin-dashboard]:not([hidden])').waitFor({ state: 'visible' });
    const approve = adminRuntime.page.locator(`[data-admin-join-review="approved"][data-join-request-id="${joinRequestId}"]`);
    await approve.waitFor({ state: 'visible' });
    await approve.click();
    const confirmApprove = adminRuntime.page.locator(`[data-admin-join-review="approved"][data-join-request-id="${joinRequestId}"][aria-label="再次点击确认批准加入请求"]`);
    await confirmApprove.waitFor({ state: 'visible' });
    await confirmApprove.click();
    await adminRuntime.page.locator('[data-admin-notice]').filter({ hasText: '加入请求已批准并完成权威列表核对' }).waitFor({ state: 'visible' });
    const audit = await pageApi(adminRuntime.page, apiBase, `/api/admin/audit-logs?action=class.join.request.approve&resource_id=${joinRequestId}`);
    assert(audit.status === 200 && audit.body && audit.body.total === 1, 'Admin approval audit reconciliation failed');
    record('admin approves join request and reconciles audit', { joinRequestId, auditTotal: audit.body.total });

    const outsiderRuntime = await createRolePage(browser, report, webBase, apiBase, 'student');
    contexts.push(outsiderRuntime.context);
    await registerFromUi(outsiderRuntime.page, 'student', accounts.outsider);
    const outsiderReview = await pageApi(outsiderRuntime.page, apiBase, `/api/assignments/${assignmentId}/review`);
    assert(outsiderReview.status === 403, `Outsider assignment review expected 403, got ${outsiderReview.status}`);
    record('outsider assignment denial', { status: outsiderReview.status });

    await studentRuntime.page.goto(roleUrl(webBase, apiBase, 'teacher'), { waitUntil: 'domcontentloaded' });
    await studentRuntime.page.waitForURL(/#student$/);
    const deniedRoleScripts = await studentRuntime.page.locator('script[data-router-page-script="teacher"], script[data-router-page-script="admin"]').count();
    assert(deniedRoleScripts === 0, 'Student must not load teacher or admin page scripts');
    await studentRuntime.page.locator('[data-student-dashboard]:not([hidden])').waitFor({ state: 'visible' });
    record('role shell redirects forbidden hash before protected script load');
    await studentRuntime.page.goto(roleUrl(webBase, apiBase, 'student'), { waitUntil: 'domcontentloaded' });
    await studentRuntime.page.locator('[data-auth-ui="account"][data-auth-role="student"]').waitFor({ state: 'visible' });

    report.responsive.student = await responsiveEvidence(studentRuntime.page, 'student', outDir);
    report.responsive.teacher = await responsiveEvidence(teacherRuntime.page, 'teacher', outDir);
    report.responsive.admin = await responsiveEvidence(adminRuntime.page, 'admin', outDir);
    record('three-role 390x844 responsive evidence');

    await studentRuntime.page.setViewportSize({ width: 1440, height: 1000 });
    const desktopScreenshot = path.join(outDir, 'student-feedback-desktop.png');
    await studentRuntime.page.screenshot({ path: desktopScreenshot, fullPage: true });
    report.responsive.desktopScreenshot = desktopScreenshot;

    assert(report.browserIssues.length === 0, `Browser issues detected: ${JSON.stringify(report.browserIssues)}`);
    record('browser console and request diagnostics clean');
    report.ok = true;
  } catch (error) {
    report.failure = {
      message: String(error && error.message || error),
      stack: String(error && error.stack || '').split('\n').slice(0, 12),
    };
  } finally {
    for (const context of contexts.reverse()) {
      try { await context.close(); } catch {}
    }
    if (browser) {
      try { await browser.close(); } catch {}
    }
    await fs.mkdir(outDir, { recursive: true });
    await fs.writeFile(path.join(outDir, 'role-workflows-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  }

  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : 1);
}

main();
