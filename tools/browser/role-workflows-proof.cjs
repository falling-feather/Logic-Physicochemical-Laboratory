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
    if ((page.__astraExpectedRequestFailurePaths || []).some((item) => (
      request.method() === item.method && new URL(request.url()).pathname === item.path
    ))) return;
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
    if ((page.__astraExpectedHttpResponses || []).some((item) => (
      response.request().method() === item.method
      && response.status() === item.status
      && resource.pathname === item.path
    ))) return;
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

async function adminOrganizationResponsiveEvidence(page, outDir) {
  await page.setViewportSize({ width: 390, height: 844 });
  const dialog = page.locator('[data-admin-organization-dialog]');
  await dialog.waitFor({ state: 'visible' });
  const layout = await page.evaluate(() => {
    const activeDialog = document.querySelector('[data-admin-organization-dialog][open]');
    const rect = activeDialog && activeDialog.getBoundingClientRect();
    const form = activeDialog && activeDialog.querySelector('[data-admin-organization-form]');
    const actionBoxes = Array.from(activeDialog.querySelectorAll([
      '[data-admin-organization-close]',
      '[data-admin-organization-confirm]',
      '[data-admin-organization-reconcile]',
      '[data-admin-organization-unlock]'
    ].join(','))).filter((element) => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
    }).map((element) => {
      const box = element.getBoundingClientRect();
      return {
        action: element.getAttribute('data-admin-organization-confirm')
          || Array.from(element.attributes).find((attribute) => attribute.name.startsWith('data-admin-organization-'))?.name
          || element.tagName,
        width: box.width,
        height: box.height,
      };
    });
    return {
      innerWidth: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      dialogLeft: rect && rect.left,
      dialogRight: rect && rect.right,
      dialogScrollWidth: activeDialog && activeDialog.scrollWidth,
      dialogClientWidth: activeDialog && activeDialog.clientWidth,
      formScrollWidth: form && form.scrollWidth,
      formClientWidth: form && form.clientWidth,
      actionBoxes,
    };
  });
  const screenshot = path.join(outDir, 'admin-organization-390x844.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  assert(layout.bodyScrollWidth <= layout.innerWidth, 'admin organization body overflows 390px viewport');
  assert(layout.documentScrollWidth <= layout.innerWidth, 'admin organization document overflows 390px viewport');
  assert(layout.dialogLeft >= 0 && layout.dialogRight <= layout.innerWidth, 'admin organization dialog is outside viewport');
  assert(layout.dialogScrollWidth <= layout.dialogClientWidth + 1, 'admin organization dialog has horizontal overflow');
  assert(layout.formScrollWidth <= layout.formClientWidth + 1, 'admin organization form has horizontal overflow');
  assert(layout.actionBoxes.length >= 3, 'admin organization dialog must expose visible governance actions');
  assert(layout.actionBoxes.every((box) => box.width >= 44 && box.height >= 44), `admin organization touch targets are smaller than 44px: ${JSON.stringify(layout.actionBoxes)}`);
  return { ...layout, screenshot };
}

async function organizationFocusEvidence(page, label, expectedSelector = '') {
  await page.waitForFunction(({ selector }) => {
    const dialog = document.querySelector('[data-admin-organization-dialog][open]');
    const active = document.activeElement;
    return Boolean(dialog && active && dialog.contains(active) && (!selector || active.matches(selector)));
  }, { selector: expectedSelector });
  const evidence = await page.evaluate(() => {
    const dialog = document.querySelector('[data-admin-organization-dialog][open]');
    const active = document.activeElement;
    return {
      insideDialog: Boolean(dialog && active && dialog.contains(active)),
      tag: active && active.tagName,
      name: active && active.getAttribute('name'),
      action: active && (
        active.getAttribute('data-admin-organization-confirm')
        || Array.from(active.attributes).find((attribute) => attribute.name.startsWith('data-admin-organization-'))?.name
      ),
      text: String(active && active.textContent || '').trim().slice(0, 120),
    };
  });
  assert(evidence.insideDialog, `${label}: focus escaped the open organization dialog`);
  return evidence;
}

async function openOrganizationEditor(page, panelId, entityName) {
  const row = page.locator(`[data-admin-panel="${panelId}"] tbody tr`).filter({ hasText: entityName }).first();
  await row.waitFor({ state: 'visible' });
  await row.locator('[data-admin-organization-edit]').click();
  const dialog = page.locator('[data-admin-organization-dialog]');
  await dialog.waitFor({ state: 'visible' });
  await dialog.locator('[data-admin-organization-form]').waitFor({ state: 'visible' });
  await organizationFocusEvidence(page, `open ${panelId} organization editor`);
  return dialog;
}

async function closeOrganizationEditor(dialog) {
  await dialog.locator('[data-admin-organization-close]').click();
  await dialog.waitFor({ state: 'hidden' });
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

    const schoolName = `E2E School ${runId}`;
    const className = `E2E Class ${runId}`;
    await teacherForm(teacherRuntime.page, 'school', {
      name: schoolName,
      region: 'Shanghai',
    }, '学校已创建');
    const schoolId = await selectedValue(teacherRuntime.page, '[data-teacher-scope="schoolId"]');

    await teacherForm(teacherRuntime.page, 'class', {
      name: className,
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
    const initialPolicyForm = teacherRuntime.page.locator('[data-teacher-form="assignment-class-policy"]');
    await initialPolicyForm.locator('button[type="submit"]').click();
    await teacherRuntime.page.locator('[data-teacher-flash]').filter({ hasText: '当前班级作业与积分覆盖策略已保存' }).waitFor({ state: 'visible' });
    await teacherRuntime.page.locator('[data-teacher-class-policy-reset]:not([disabled])').waitFor({ state: 'visible' });
    report.entities = { schoolId, classId, courseId, unitId, assignmentId };
    record('teacher creates published course workflow and persisted class policy', report.entities);

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
    studentRuntime.page.__astraExpectedHttpResponses = [
      { method: 'GET', status: 403, path: `/api/admin/schools/${schoolId}` },
      { method: 'PATCH', status: 403, path: `/api/admin/schools/${schoolId}` },
    ];
    teacherRuntime.page.__astraExpectedHttpResponses = [
      { method: 'GET', status: 403, path: `/api/admin/classes/${classId}` },
      { method: 'PATCH', status: 403, path: `/api/admin/classes/${classId}` },
    ];
    const studentSchoolReadDenied = await pageApi(studentRuntime.page, apiBase, `/api/admin/schools/${schoolId}`);
    const studentSchoolPatchDenied = await pageApi(studentRuntime.page, apiBase, `/api/admin/schools/${schoolId}`, {
      method: 'PATCH',
      body: { expected_version: 1, reason: 'student denial proof', name: 'denied' },
    });
    const teacherClassReadDenied = await pageApi(teacherRuntime.page, apiBase, `/api/admin/classes/${classId}`);
    const teacherClassPatchDenied = await pageApi(teacherRuntime.page, apiBase, `/api/admin/classes/${classId}`, {
      method: 'PATCH',
      body: { expected_version: 1, reason: 'teacher denial proof', name: 'denied' },
    });
    assert(studentSchoolReadDenied.status === 403 && studentSchoolPatchDenied.status === 403, 'student organization governance must be denied');
    assert(teacherClassReadDenied.status === 403 && teacherClassPatchDenied.status === 403, 'teacher organization governance must be denied');
    studentRuntime.page.__astraExpectedHttpResponses = [];
    teacherRuntime.page.__astraExpectedHttpResponses = [];
    record('role permission denials', {
      studentAdmin: 403,
      teacherAdminQueue: 403,
      studentOrganization: [403, 403],
      teacherOrganization: [403, 403],
    });

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

    const organizationPatches = [];
    adminRuntime.page.on('request', (request) => {
      const resource = new URL(request.url());
      if (request.method() !== 'PATCH' || !/^\/api\/admin\/(schools|classes)\/\d+$/.test(resource.pathname)) return;
      let body = null;
      try { body = request.postDataJSON(); } catch {}
      organizationPatches.push({ path: resource.pathname, body });
    });
    const schoolPath = `/api/admin/schools/${schoolId}`;
    const classPath = `/api/admin/classes/${classId}`;

    const activeSchoolPage = await pageApi(adminRuntime.page, apiBase, '/api/admin/schools?status=active&limit=1&offset=0');
    const archivedSchoolPage = await pageApi(adminRuntime.page, apiBase, '/api/admin/schools?status=archived&limit=1&offset=0');
    const activeClassPage = await pageApi(adminRuntime.page, apiBase, '/api/admin/classes?status=active&limit=1&offset=0');
    const archivedClassPage = await pageApi(adminRuntime.page, apiBase, '/api/admin/classes?status=archived&limit=1&offset=0');
    const visualCounts = await adminRuntime.page.evaluate(() => {
      const read = (kind) => Array.from(document.querySelectorAll(`[data-admin-organization-summary-kind="${kind}"] dd`))
        .map((item) => Number(String(item.textContent || '').replace(/[^0-9]/g, '')) || 0);
      return { schools: read('schools'), classes: read('classes') };
    });
    assert(visualCounts.schools[0] === activeSchoolPage.body.total, 'active school visual total must match API');
    assert(visualCounts.schools[1] === archivedSchoolPage.body.total, 'archived school visual total must match API');
    assert(visualCounts.classes[0] === activeClassPage.body.total, 'active class visual total must match API');
    assert(visualCounts.classes[1] === archivedClassPage.body.total, 'archived class visual total must match API');
    record('admin organization status visualization matches authoritative totals', visualCounts);

    const schoolRow = adminRuntime.page.locator('[data-admin-panel="schools"] tbody tr').filter({ hasText: schoolName }).first();
    const schoolEditorTrigger = schoolRow.locator('[data-admin-organization-edit]');
    let releaseSchoolRead;
    const schoolReadGate = new Promise((resolve) => { releaseSchoolRead = resolve; });
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }
      await schoolReadGate;
      await route.continue();
    });
    await schoolEditorTrigger.click();
    let organizationDialog = adminRuntime.page.locator('[data-admin-organization-dialog]');
    await organizationDialog.waitFor({ state: 'visible' });
    const loadingFocus = await organizationFocusEvidence(adminRuntime.page, 'busy exact GET', '[data-admin-organization-title]');
    await adminRuntime.page.keyboard.press('Escape');
    assert(await organizationDialog.isVisible(), 'Escape must not close organization dialog during exact GET');
    releaseSchoolRead();
    await organizationDialog.locator('[data-admin-organization-form]').waitFor({ state: 'visible' });
    await adminRuntime.page.unroute(`**${schoolPath}`);
    const loadedFocus = await organizationFocusEvidence(adminRuntime.page, 'completed exact GET', '[data-admin-organization-title]');
    await adminRuntime.page.keyboard.press('Escape');
    await organizationDialog.waitFor({ state: 'hidden' });
    await adminRuntime.page.waitForFunction(() => document.activeElement?.hasAttribute('data-admin-organization-edit'));
    assert(await schoolEditorTrigger.evaluate((element) => document.activeElement === element), 'idle Escape must restore focus to the organization editor trigger');
    record('organization dialog Escape and focus lifecycle', { loadingFocus, loadedFocus, triggerRestored: true });

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'schools', schoolName);
    const initialSchoolVersion = Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version'));
    const schoolForm = organizationDialog.locator('[data-admin-organization-form]');
    const schoolPatchStart = organizationPatches.filter((item) => item.path === schoolPath).length;
    await schoolForm.locator('[name="description"]').fill(`治理说明 ${runId}`);
    await schoolForm.locator('[data-admin-organization-reason]').fill(`E2E 学校治理 ${runId}`);
    await schoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await schoolForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    assert(organizationPatches.filter((item) => item.path === schoolPath).length === schoolPatchStart, 'first organization confirmation must send zero PATCH requests');
    await schoolForm.locator('[name="region"]').fill('Shanghai Governance');
    await schoolForm.locator('[data-admin-organization-preview]').waitFor({ state: 'detached' });
    await schoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await schoolForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    assert(organizationPatches.filter((item) => item.path === schoolPath).length === schoolPatchStart, 'changed input must require a fresh zero-write preview');
    const previewFocus = await organizationFocusEvidence(adminRuntime.page, 'school metadata preview', '[data-admin-organization-confirm="metadata"]');
    let releaseSchoolPatch;
    const schoolPatchGate = new Promise((resolve) => { releaseSchoolPatch = resolve; });
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      await schoolPatchGate;
      await route.continue();
    });
    await schoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await schoolForm.waitFor({ state: 'visible' });
    await adminRuntime.page.waitForFunction(() => document.querySelector('[data-admin-organization-form]')?.getAttribute('aria-busy') === 'true');
    const busyPatchFocus = await organizationFocusEvidence(adminRuntime.page, 'busy school PATCH', '[data-admin-organization-title]');
    await adminRuntime.page.keyboard.press('Escape');
    assert(await organizationDialog.isVisible(), 'Escape must not close organization dialog during PATCH reconciliation');
    assert(organizationPatches.filter((item) => item.path === schoolPath).length === schoolPatchStart + 1, 'busy PATCH Escape path must still send exactly one request');
    releaseSchoolPatch();
    await adminRuntime.page.locator('[data-admin-notice]').filter({ hasText: `学校 #${schoolId} 已更新` }).waitFor({ state: 'visible' });
    await adminRuntime.page.unroute(`**${schoolPath}`);
    await organizationDialog.locator(`[data-admin-organization-version="${initialSchoolVersion + 1}"]`).waitFor({ state: 'visible' });
    const successFocus = await organizationFocusEvidence(adminRuntime.page, 'school metadata success', '[data-admin-organization-status]');
    const schoolUiPatches = organizationPatches.filter((item) => item.path === schoolPath).slice(schoolPatchStart);
    assert(schoolUiPatches.length === 1, `school metadata expected exactly one PATCH, got ${schoolUiPatches.length}`);
    assert(
      JSON.stringify(Object.keys(schoolUiPatches[0].body).sort()) === JSON.stringify(['description', 'expected_version', 'reason', 'region']),
      `school PATCH contains unexpected fields: ${JSON.stringify(schoolUiPatches[0].body)}`
    );
    assert(schoolUiPatches[0].body.expected_version === initialSchoolVersion, 'school PATCH must use exact GET version');
    const schoolAudit = await pageApi(adminRuntime.page, apiBase, `/api/admin/audit-logs?action=admin.school.update&resource_id=${schoolId}`);
    assert(schoolAudit.status === 200 && schoolAudit.body.total >= 1, 'school governance audit reconciliation failed');
    record('admin school metadata double-confirm and authoritative reread', {
      versionBefore: initialSchoolVersion,
      versionAfter: initialSchoolVersion + 1,
      patchCount: schoolUiPatches.length,
      auditTotal: schoolAudit.body.total,
      focus: { previewFocus, busyPatchFocus, successFocus },
    });

    const lifecycleVersion = initialSchoolVersion + 1;
    const lifecycleForm = organizationDialog.locator('[data-admin-organization-form]');
    await lifecycleForm.locator('[name="description"]').fill(`生命周期切换不落库 ${runId}`);
    await lifecycleForm.locator('[data-admin-organization-reason]').fill(`E2E 路由生命周期竞态 ${runId}`);
    await lifecycleForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await lifecycleForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    const lifecyclePatchStart = organizationPatches.filter((item) => item.path === schoolPath).length;
    let releaseLifecyclePatch;
    let lifecycleRouteOutcome = 'pending';
    const lifecyclePatchGate = new Promise((resolve) => { releaseLifecyclePatch = resolve; });
    adminRuntime.page.__astraExpectedRequestFailurePaths = [{ method: 'PATCH', path: schoolPath }];
    const lifecyclePatchFailure = adminRuntime.page.waitForEvent('requestfailed', {
      predicate: (request) => request.method() === 'PATCH' && new URL(request.url()).pathname === schoolPath,
      timeout: 10000,
    });
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      await lifecyclePatchGate;
      try {
        await route.abort('connectionreset');
        lifecycleRouteOutcome = 'aborted';
      } catch {
        lifecycleRouteOutcome = 'already-cancelled';
      }
    });
    await lifecycleForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await adminRuntime.page.waitForFunction(() => document.querySelector('[data-admin-organization-form]')?.getAttribute('aria-busy') === 'true');
    assert(
      organizationPatches.filter((item) => item.path === schoolPath).length === lifecyclePatchStart + 1,
      'lifecycle race must send exactly one PATCH before route destroy'
    );

    await adminRuntime.page.evaluate(() => { window.location.hash = 'teacher'; });
    await adminRuntime.page.waitForURL(/#teacher$/);
    await adminRuntime.page.locator('[data-teacher-dashboard]:not([hidden])').waitFor({ state: 'visible' });

    let releaseReentryStats;
    let markReentryStatsStarted;
    const reentryStatsGate = new Promise((resolve) => { releaseReentryStats = resolve; });
    const reentryStatsStarted = new Promise((resolve) => { markReentryStatsStarted = resolve; });
    await adminRuntime.page.route('**/api/admin/stats', async (route) => {
      markReentryStatsStarted();
      await reentryStatsGate;
      await route.continue();
    });
    await adminRuntime.page.evaluate(() => { window.location.hash = 'admin'; });
    await adminRuntime.page.waitForURL(/#admin$/);
    await reentryStatsStarted;
    await adminRuntime.page.locator('[data-admin-governance].is-busy').waitFor({ state: 'visible' });

    releaseLifecyclePatch();
    await lifecyclePatchFailure;
    await adminRuntime.page.waitForTimeout(150);
    const reentryBusyEvidence = await adminRuntime.page.evaluate(() => ({
      rootBusy: document.querySelector('[data-admin-governance]')?.classList.contains('is-busy') === true,
      refreshDisabled: document.querySelector('[data-admin-refresh-control]')?.disabled === true,
    }));
    assert(reentryBusyEvidence.rootBusy, 'old PATCH completion must not clear the re-entered admin lifecycle busy state');
    assert(reentryBusyEvidence.refreshDisabled, 'old PATCH completion must not re-enable controls owned by the new lifecycle');

    releaseReentryStats();
    await adminRuntime.page.unroute('**/api/admin/stats');
    await adminRuntime.page.unroute(`**${schoolPath}`);
    adminRuntime.page.__astraExpectedRequestFailurePaths = [];
    await adminRuntime.page.waitForFunction(() => !document.querySelector('[data-admin-governance]')?.classList.contains('is-busy'));
    await adminRuntime.page.waitForFunction(({ targetId }) => {
      const target = document.querySelector(`[data-admin-organization-edit][data-organization-kind="school"][data-organization-id="${targetId}"]`);
      const other = document.querySelector('[data-admin-organization-edit][data-organization-kind="class"]');
      return Boolean(target && !target.disabled && other && other.disabled);
    }, { targetId: String(schoolId) });

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'schools', schoolName);
    await organizationDialog.locator('[data-admin-organization-lock]').waitFor({ state: 'visible' });
    await organizationDialog.locator('[data-admin-organization-reconcile]').waitFor({ state: 'visible' });
    assert(
      Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version')) === lifecycleVersion,
      'destroyed lifecycle PATCH must not silently change the authoritative resource'
    );
    const lifecyclePatchBeforeReconcile = organizationPatches.filter((item) => item.path === schoolPath).length;
    await organizationDialog.locator('[data-admin-organization-reconcile]').click();
    await organizationDialog.locator('[data-admin-organization-unlock]').waitFor({ state: 'visible' });
    assert(
      organizationPatches.filter((item) => item.path === schoolPath).length === lifecyclePatchBeforeReconcile,
      'new lifecycle reconciliation must not resend the destroyed PATCH'
    );
    await organizationDialog.locator('[data-admin-organization-unlock]').click();
    await organizationDialog.locator('[data-admin-organization-status]').filter({ hasText: '人工解除锁定' }).waitFor({ state: 'visible' });
    record('in-flight PATCH route destroy preserves lock across admin re-entry', {
      version: lifecycleVersion,
      patchCount: organizationPatches.filter((item) => item.path === schoolPath).length - lifecyclePatchStart,
      routeOutcome: lifecycleRouteOutcome,
      reentryBusyEvidence,
      reconciledWithoutReplay: true,
    });
    await closeOrganizationEditor(organizationDialog);

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'schools', schoolName);
    const mismatchVersion = initialSchoolVersion + 1;
    const mismatchForm = organizationDialog.locator('[data-admin-organization-form]');
    await mismatchForm.locator('[name="description"]').fill(`伪成功未落库 ${runId}`);
    await mismatchForm.locator('[data-admin-organization-reason]').fill(`E2E 2xx 权威不一致 ${runId}`);
    await mismatchForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await mismatchForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    let mismatchPatchCount = 0;
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      mismatchPatchCount += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: Number(schoolId), version: mismatchVersion, status: 'active' }),
      });
    });
    await mismatchForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await organizationDialog.locator('[data-admin-organization-unlock]').waitFor({ state: 'visible' });
    await organizationDialog.locator('[data-admin-organization-status]').filter({ hasText: '精确权威资源不是预期的 version+1' }).waitFor({ state: 'visible' });
    const mismatchFocus = await organizationFocusEvidence(adminRuntime.page, '2xx authority mismatch', '[data-admin-organization-unlock]');
    assert(Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version')) === mismatchVersion, '2xx mismatch must retain the unchanged authority version');
    assert(mismatchPatchCount === 1, `2xx mismatch expected exactly one PATCH, got ${mismatchPatchCount}`);
    await adminRuntime.page.waitForTimeout(300);
    assert(mismatchPatchCount === 1, '2xx mismatch must not retry PATCH');
    assert(!String(await adminRuntime.page.locator('[data-admin-notice]').textContent()).includes('已更新，权威资源'), '2xx mismatch must not claim governance success');
    await adminRuntime.page.unroute(`**${schoolPath}`);
    await organizationDialog.locator('[data-admin-organization-unlock]').click();
    await organizationDialog.locator('[data-admin-organization-status]').filter({ hasText: '人工解除锁定' }).waitFor({ state: 'visible' });
    record('2xx response with unchanged authority remains locked without retry', {
      authorityVersion: mismatchVersion,
      patchCount: mismatchPatchCount,
      focus: mismatchFocus,
    });
    await closeOrganizationEditor(organizationDialog);

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'classes', className);
    const classForm = organizationDialog.locator('[data-admin-organization-form]');
    const classVersion = Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version'));
    await classForm.locator('[name="grade"]').fill('11');
    await classForm.locator('[data-admin-organization-reason]').fill(`E2E 冲突草稿 ${runId}`);
    await classForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await classForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    const concurrentClass = await pageApi(adminRuntime.page, apiBase, classPath, {
      method: 'PATCH',
      body: { expected_version: classVersion, reason: `E2E 并发推进 ${runId}`, term: `2026B-${runId}` },
    });
    assert(concurrentClass.status === 200, `concurrent class update expected 200, got ${concurrentClass.status}`);
    adminRuntime.page.__astraExpectedHttpResponses = [{ method: 'PATCH', status: 409, path: classPath }];
    const classPatchBeforeConflict = organizationPatches.filter((item) => item.path === classPath).length;
    await classForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await organizationDialog.locator('.admin-organization-alert').filter({ hasText: '检测到版本冲突' }).waitFor({ state: 'visible' });
    await organizationDialog.locator(`[data-admin-organization-version="${classVersion + 1}"]`).waitFor({ state: 'visible' });
    assert(await organizationDialog.locator('[name="grade"]').inputValue() === '11', '409 reconciliation must preserve user draft');
    assert(organizationPatches.filter((item) => item.path === classPath).length === classPatchBeforeConflict + 1, '409 flow must send one UI PATCH');
    await adminRuntime.page.waitForTimeout(300);
    assert(organizationPatches.filter((item) => item.path === classPath).length === classPatchBeforeConflict + 1, '409 flow must not retry PATCH');
    adminRuntime.page.__astraExpectedHttpResponses = [];
    record('admin organization 409 conflict rereads authority without retry', {
      staleVersion: classVersion,
      authorityVersion: classVersion + 1,
      uiPatchCount: 1,
    });
    await closeOrganizationEditor(organizationDialog);

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'classes', className);
    let governedClassVersion = Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version'));
    let governedClassForm = organizationDialog.locator('[data-admin-organization-form]');
    await governedClassForm.locator('[data-admin-organization-reason]').fill(`E2E 归档班级 ${runId}`);
    const classPatchBeforeArchive = organizationPatches.filter((item) => item.path === classPath).length;
    await governedClassForm.locator('[data-admin-organization-confirm="status"]').click();
    await governedClassForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    assert(organizationPatches.filter((item) => item.path === classPath).length === classPatchBeforeArchive, 'class archive preview must send zero PATCH requests');
    await governedClassForm.locator('[data-admin-organization-confirm="status"]').click();
    await adminRuntime.page.locator('[data-admin-notice]').filter({ hasText: `班级 #${classId} 已更新` }).waitFor({ state: 'visible' });
    await organizationDialog.locator(`[data-admin-organization-version="${governedClassVersion + 1}"]`).waitFor({ state: 'visible' });
    await organizationDialog.locator('[data-admin-organization-readonly="archived"]').waitFor({ state: 'visible' });
    const archivedFocus = await organizationFocusEvidence(adminRuntime.page, 'class archive success', '[data-admin-organization-status]');
    const archiveVisual = await organizationDialog.evaluate((dialog) => {
      const badge = dialog.querySelector('[data-admin-organization-readonly="archived"] .admin-status-pill');
      const restore = dialog.querySelector('[data-admin-organization-confirm="status"]');
      const style = restore && getComputedStyle(restore);
      const box = restore && restore.getBoundingClientRect();
      return {
        badgeText: String(badge && badge.textContent || '').trim(),
        restoreText: String(restore && restore.textContent || '').trim(),
        restoreClass: String(restore && restore.className || ''),
        restoreColor: style && style.color,
        restoreWidth: box && box.width,
        restoreHeight: box && box.height,
      };
    });
    assert(archiveVisual.badgeText.includes('已归档 · 教学只读'), `archived organization wording missing: ${JSON.stringify(archiveVisual)}`);
    assert(archiveVisual.restoreText.includes('恢复') && archiveVisual.restoreClass.includes('admin-icon-button--restore'), 'archived organization must expose the green restore action');
    assert(archiveVisual.restoreColor === 'rgb(191, 245, 213)', `restore action must use the green semantic color, got ${archiveVisual.restoreColor}`);
    assert(archiveVisual.restoreWidth >= 44 && archiveVisual.restoreHeight >= 44, 'restore action must be at least 44x44');
    const archivePatches = organizationPatches.filter((item) => item.path === classPath).slice(classPatchBeforeArchive);
    assert(archivePatches.length === 1 && archivePatches[0].body.status === 'archived', 'class archive must send one constrained status PATCH');
    const archivedClassStats = await pageApi(adminRuntime.page, apiBase, `/api/admin/classes/${classId}/stats`);
    assert(archivedClassStats.status === 200, 'archived class history statistics must remain readable');
    const classArchiveAudit = await pageApi(adminRuntime.page, apiBase, `/api/admin/audit-logs?action=admin.class.archive&resource_id=${classId}`);
    assert(classArchiveAudit.status === 200 && classArchiveAudit.body.total >= 1, 'class archive audit must exist');
    await teacherRuntime.page.locator('[data-teacher-action="refresh"]').click();
    await teacherRuntime.page.locator('[data-teacher-scope="classId"] option:checked').filter({ hasText: 'archived' }).waitFor({ state: 'attached' });
    assert(await teacherRuntime.page.locator('[data-teacher-form="student-batch-import"] button[type="submit"]').isDisabled(), 'archived class must disable teacher membership writes');
    assert(await teacherRuntime.page.locator('[data-teacher-form="grade"] button[type="submit"]').isDisabled(), 'archived class must disable teacher grading writes');
    assert(await teacherRuntime.page.locator('[data-teacher-form="assignment-class-policy"] button[type="submit"]').isDisabled(), 'archived class must disable teacher assignment-class-policy PUT');
    assert(await teacherRuntime.page.locator('[data-teacher-class-policy-reset]').isDisabled(), 'archived class must disable teacher assignment-class-policy DELETE');

    governedClassVersion += 1;
    governedClassForm = organizationDialog.locator('[data-admin-organization-form]');
    await governedClassForm.locator('[data-admin-organization-reason]').fill(`E2E 恢复班级 ${runId}`);
    const classPatchBeforeRestore = organizationPatches.filter((item) => item.path === classPath).length;
    await governedClassForm.locator('[data-admin-organization-confirm="status"]').click();
    await governedClassForm.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    assert(organizationPatches.filter((item) => item.path === classPath).length === classPatchBeforeRestore, 'class restore preview must send zero PATCH requests');
    await governedClassForm.locator('[data-admin-organization-confirm="status"]').click();
    await organizationDialog.locator(`[data-admin-organization-version="${governedClassVersion + 1}"]`).waitFor({ state: 'visible' });
    await organizationDialog.locator('[data-admin-organization-readonly="active"]').waitFor({ state: 'visible' });
    const restoredFocus = await organizationFocusEvidence(adminRuntime.page, 'class restore success', '[data-admin-organization-status]');
    const restorePatches = organizationPatches.filter((item) => item.path === classPath).slice(classPatchBeforeRestore);
    assert(restorePatches.length === 1 && restorePatches[0].body.status === 'active', 'class restore must send one constrained status PATCH');
    const classRestoreAudit = await pageApi(adminRuntime.page, apiBase, `/api/admin/audit-logs?action=admin.class.restore&resource_id=${classId}`);
    assert(classRestoreAudit.status === 200 && classRestoreAudit.body.total >= 1, 'class restore audit must exist');
    await teacherRuntime.page.locator('[data-teacher-action="refresh"]').click();
    await teacherRuntime.page.waitForFunction(({ expectedClassName }) => {
      const selected = document.querySelector('[data-teacher-scope="classId"] option:checked');
      const membershipWrite = document.querySelector('[data-teacher-form="student-batch-import"] button[type="submit"]');
      const policyWrite = document.querySelector('[data-teacher-form="assignment-class-policy"] button[type="submit"]');
      const policyReset = document.querySelector('[data-teacher-class-policy-reset]');
      return selected
        && String(selected.textContent || '').includes(expectedClassName)
        && !String(selected.textContent || '').includes('archived')
        && membershipWrite
        && !membershipWrite.disabled
        && policyWrite
        && !policyWrite.disabled
        && policyReset
        && !policyReset.disabled;
    }, { expectedClassName: className });
    assert(!(await teacherRuntime.page.locator('[data-teacher-form="student-batch-import"] button[type="submit"]').isDisabled()), 'restored class must re-enable eligible teacher membership writes');
    record('admin archives and restores class with historical read and teacher readonly boundary', {
      archivePatchCount: archivePatches.length,
      restorePatchCount: restorePatches.length,
      archivedStatsStatus: archivedClassStats.status,
      archiveAuditTotal: classArchiveAudit.body.total,
      restoreAuditTotal: classRestoreAudit.body.total,
      archiveVisual,
      focus: { archivedFocus, restoredFocus },
    });
    await closeOrganizationEditor(organizationDialog);

    organizationDialog = await openOrganizationEditor(adminRuntime.page, 'schools', schoolName);
    let currentSchoolVersion = Number(await organizationDialog.locator('[data-admin-organization-version]').getAttribute('data-admin-organization-version'));
    let currentSchoolForm = organizationDialog.locator('[data-admin-organization-form]');
    await currentSchoolForm.locator('[name="description"]').fill(`响应丢失但已落库 ${runId}`);
    await currentSchoolForm.locator('[data-admin-organization-reason]').fill(`E2E 未知结果已生效 ${runId}`);
    await currentSchoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    let appliedUnknownCount = 0;
    adminRuntime.page.__astraExpectedRequestFailurePaths = [{ method: 'PATCH', path: schoolPath }];
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      appliedUnknownCount += 1;
      await route.fetch();
      await route.abort('connectionreset');
    });
    await currentSchoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await adminRuntime.page.locator('[data-admin-notice]').filter({ hasText: '已由权威回读确认生效' }).waitFor({ state: 'visible' });
    await organizationDialog.locator(`[data-admin-organization-version="${currentSchoolVersion + 1}"]`).waitFor({ state: 'visible' });
    const appliedUnknownFocus = await organizationFocusEvidence(adminRuntime.page, 'applied unknown reconciliation', '[data-admin-organization-status]');
    assert(appliedUnknownCount === 1, `applied unknown result expected one PATCH, got ${appliedUnknownCount}`);
    await adminRuntime.page.unroute(`**${schoolPath}`);
    adminRuntime.page.__astraExpectedRequestFailurePaths = [];
    record('unknown response with committed mutation resolves by exact GET without retry', {
      patchCount: appliedUnknownCount,
      versionBefore: currentSchoolVersion,
      versionAfter: currentSchoolVersion + 1,
      focus: appliedUnknownFocus,
    });

    currentSchoolVersion += 1;
    currentSchoolForm = organizationDialog.locator('[data-admin-organization-form]');
    await currentSchoolForm.locator('[name="description"]').fill(`响应丢失且未落库 ${runId}`);
    await currentSchoolForm.locator('[data-admin-organization-reason]').fill(`E2E 未知结果未生效 ${runId}`);
    await currentSchoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    let unappliedUnknownCount = 0;
    adminRuntime.page.__astraExpectedRequestFailurePaths = [{ method: 'PATCH', path: schoolPath }];
    await adminRuntime.page.route(`**${schoolPath}`, async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      unappliedUnknownCount += 1;
      await route.abort('connectionreset');
    });
    await currentSchoolForm.locator('[data-admin-organization-confirm="metadata"]').click();
    await organizationDialog.locator('[data-admin-organization-unlock]').waitFor({ state: 'visible' });
    assert(unappliedUnknownCount === 1, `unapplied unknown result expected one PATCH, got ${unappliedUnknownCount}`);
    await adminRuntime.page.unroute(`**${schoolPath}`);
    adminRuntime.page.__astraExpectedRequestFailurePaths = [];
    const lockedFocus = await organizationFocusEvidence(adminRuntime.page, 'unapplied unknown reconciliation', '[data-admin-organization-unlock]');
    const patchCountBeforeManualReconcile = organizationPatches.filter((item) => item.path === schoolPath).length;
    await organizationDialog.locator('[data-admin-organization-reconcile]').click();
    await organizationDialog.locator('[data-admin-organization-unlock]').waitFor({ state: 'visible' });
    const manualReconcileFocus = await organizationFocusEvidence(adminRuntime.page, 'manual authoritative reconciliation', '[data-admin-organization-unlock]');
    assert(organizationPatches.filter((item) => item.path === schoolPath).length === patchCountBeforeManualReconcile, 'manual reconciliation must not resend PATCH');
    await organizationDialog.locator('[data-admin-organization-unlock]').click();
    await organizationDialog.locator('.admin-organization-alert').filter({ hasText: '人工解除锁定' }).waitFor({ state: 'visible' });
    const patchCountBeforeFreshPreview = organizationPatches.filter((item) => item.path === schoolPath).length;
    await organizationDialog.locator('[data-admin-organization-confirm="metadata"]').click();
    await organizationDialog.locator('[data-admin-organization-preview]').waitFor({ state: 'visible' });
    assert(organizationPatches.filter((item) => item.path === schoolPath).length === patchCountBeforeFreshPreview, 'manual unlock must require a fresh zero-write preview');
    report.responsive.adminOrganization = await adminOrganizationResponsiveEvidence(adminRuntime.page, outDir);
    record('unapplied unknown result remains locked until explicit reconciliation', {
      patchCount: unappliedUnknownCount,
      version: currentSchoolVersion,
      focus: { lockedFocus, manualReconcileFocus },
    });
    await closeOrganizationEditor(organizationDialog);
    await adminRuntime.page.setViewportSize({ width: 1440, height: 1000 });

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
