const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const html = read('index.html');
const registrySource = read('shared/js/page-registry.js');
const router = read('shared/js/router.js');
const main = read('shared/js/main.js');
const serviceWorker = read('sw.js');
const sessionCss = read('shared/css/app-session.css');
const teacher = read('pages/teacher/teacher.js');
const teacherCss = read('pages/teacher/teacher.css');
const browserProof = read('tools/browser/role-workflows-proof.cjs');
const context = { window: {} };

vm.runInNewContext(registrySource, context, { filename: 'shared/js/page-registry.js' });
const registry = context.window.AstraPageRegistry;

for (const page of ['student', 'teacher', 'admin']) {
  assert.equal(registry.galaxyFor(page), 'astra', `${page} must be a top-level Astra workspace`);
  assert.match(
    html,
    new RegExp(`id="page-${page}" class="page astra-workspace-page [^"]+"[^>]+data-astra-workspace="${page}"`),
    `${page} section must use the shared Astra workspace shell`,
  );
}

const bootEnglab = html.match(/var englabPages = \[([^\]]+)\]/);
assert.ok(bootEnglab, 'early boot must declare the Engineering Lab page set');
for (const rolePage of ['student', 'teacher', 'admin']) {
  assert.doesNotMatch(bootEnglab[1], new RegExp(`['"]${rolePage}['"]`));
}

for (const label of ['星序总览', '工科试验室', '代码空间', '未来星系', '身份工作区']) {
  assert.ok(html.includes(label), `shared Astra shell must expose ${label}`);
}
assert.match(html, /data-astra-workspace="teacher"[\s\S]*星序[\s\S]*教学工作台/);
assert.match(html, /data-astra-workspace="admin"[\s\S]*星序[\s\S]*全局治理/);
assert.match(html, /data-astra-workspace="student"[\s\S]*星序[\s\S]*我的学习/);

assert.match(router, /navbar--hidden', this\._galaxyForPage\(initialPage\) === 'astra'/);
assert.match(router, /navbar--hidden', this\._galaxyForPage\(page\) === 'astra'/);
assert.match(router, /return this\._galaxyForPage\(page\) === 'englab' && page !== 'home'/);
assert.match(html, /shared\/js\/router\.js\?v=20260719v758ReleaseAuditP0/);
assert.match(main, /const galaxy = window\.AstraPageRegistry[\s\S]*const showEnglab = galaxy === 'englab' && page !== 'home'/);
assert.match(main, /shared\/js\/router\.js\?v=' \+ SHELL_RUNTIME_ASSET_VERSION/);
assert.match(serviceWorker, /shared\/js\/router\.js\?v=20260719v758ReleaseAuditP0/);

assert.match(sessionCss, /\.astra-workspace-shell\s*\{[\s\S]*grid-template-columns:\s*232px minmax\(0, 1fr\)/);
assert.match(sessionCss, /\.astra-workspace-rail/);
assert.match(sessionCss, /@media \(max-width: 900px\)[\s\S]*\.astra-workspace-dock/);
assert.match(sessionCss, /\.page\.astra-workspace-page[\s\S]*padding-top:\s*0\s*!important/);
assert.match(sessionCss, /@media \(max-width: 900px\)[\s\S]*\.page\.astra-workspace-page\.active\s*\{[\s\S]*transform:\s*none\s*!important[\s\S]*will-change:\s*auto\s*!important/);

for (const label of ['教学总览', '课程节奏', '作业发布', '批改与学情', '组织与课程']) {
  assert.ok(teacher.includes(label), `teacher workbench must expose ${label}`);
}
assert.match(teacher, /activeView:\s*'overview'/);
assert.match(teacher, /overview:\s*renderOverviewPanel[\s\S]*curriculum:\s*renderCurriculumWorkspace[\s\S]*assignments:\s*renderAssignmentWorkspace[\s\S]*grading:\s*renderGradingWorkspace[\s\S]*structure:\s*renderOrganizationPanel/);
assert.match(teacher, /data-teacher-operation=/);
assert.match(teacher, /function renderOperation/);
assert.doesNotMatch(teacher, /class="teacher-kpi-grid"/);
assert.doesNotMatch(teacher, /renderSetupPanel\(\)[\s\S]*renderReservedPanel\(\)/);

assert.match(teacherCss, /V7\.4\.37 · 星序教学工作台/);
assert.match(teacherCss, /V7\.5\.7 · 三星系课程节奏与学情轨道/);
assert.match(teacherCss, /\.teacher-curriculum-grid/);
assert.match(teacherCss, /\.teacher-progress-matrix/);
assert.match(teacherCss, /\.teacher-code-station/);
assert.match(teacherCss, /\.teacher-summary-strip\s*\{[\s\S]*grid-template-columns:\s*repeat\(4/);
assert.match(teacherCss, /\.teacher-overview-layout\s*\{[\s\S]*grid-template-columns:/);
assert.match(teacherCss, /@media \(max-width: 760px\)[\s\S]*\.teacher-operation-list,[\s\S]*grid-template-columns:\s*1fr/);

assert.match(browserProof, /const viewByForm = \{/);
assert.match(browserProof, /node\.closest\('details'\)/);

console.log('astra-workspace-hierarchy-contract: ok');
