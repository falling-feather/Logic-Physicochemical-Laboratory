const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(path.join(repoRoot, 'tools/browser/role-workflows-proof.cjs'), 'utf8');

assert.match(source, /--confirm-isolated-environment[\s\S]*disposable local database/);
assert.match(source, /isLocalUrl\(apiBase\)[\s\S]*isLocalUrl\(webBase\)/);
assert.match(source, /development'[\s\S]*'test'[\s\S]*'testing/);
assert.match(source, /gitHead:\s*currentGitHead\(\)/);
assert.match(source, /gitStatusShort:\s*currentGitStatusShort\(\)/);
assert.match(source, /criticalArtifactHashes\(\)/);
assert.match(source, /const REQUIRED_BROWSER_CHANNEL = 'msedge'/);
assert.match(source, /requested === REQUIRED_BROWSER_CHANNEL/);
assert.match(source, /channel:\s*REQUIRED_BROWSER_CHANNEL/);
assert.match(source, /AbortSignal\.timeout\(Number\(options\.timeoutMs \|\| DEFAULT_REQUEST_TIMEOUT_MS\)\)/);
assert.match(source, /async function waitForNetworkQuiet/);
assert.match(source, /workflow watchdog exceeded/);

assert.match(source, /function roleUrl[\s\S]*cacheMode=service-worker/);
assert.match(source, /navigator\.serviceWorker[\s\S]*controller/);
assert.match(source, /Service Worker readiness timed out:[\s\S]*JSON\.stringify\(diagnostics\)/);
assert.match(source, /Service Worker readiness failed:[\s\S]*JSON\.stringify\(readiness\)/);
assert.match(source, /async function serviceWorkerRoleEvidence/);
assert.match(source, /await caches\.keys\(\)/);
assert.match(source, /apiEntries\.length === 0/);
assert.match(source, /roleEntries\.length === 0/);
assert.match(source, /fromServiceWorker/);
assert.match(source, /const responses = \(page\.__astraRoleResponses \|\| \[\]\)\.map\(\(item\) => \(\{ \.\.\.item \}\)\);/);
assert.match(source, /controllerPath === '\/sw\.js'/);
assert.match(source, /registrations\.length === 1/);
assert.match(source, /expectedCacheName/);
assert.match(source, /responsePaths\.length === expectedResources\.length/);
assert.match(source, /\/pages\/student\/student\.css/);
assert.match(source, /\/pages\/teacher\/teacher\.js/);
assert.match(source, /\/pages\/admin\/admin\.js/);
assert.match(source, /anonymous authentication gate and Service Worker preflight before any business mutation/);
assert.match(source, /anonymousRoleResponses\.length === 0/);
assert.match(source, /timeline\.swReadyAt = new Date\(\)\.toISOString\(\)[\s\S]*timeline\.firstMutationAt = new Date\(\)\.toISOString\(\)[\s\S]*Service Worker preflight must precede the first mutation/);
assert.ok(
  source.indexOf('const anonymousPreflight = await createRolePage') < source.indexOf('const bootstrap = await fetchJson'),
  'anonymous Service Worker preflight must execute before admin bootstrap'
);

assert.match(source, /async function registerThenLogout/);
assert.match(source, /logout\.status === 200[\s\S]*logout\.body\.status === 'ok'/);
assert.match(source, /registerThenLogout\(browser,[\s\S]*'teacher'/);
assert.match(source, /registerThenLogout\(browser,[\s\S]*'student'/);
assert.match(source, /await loginFromUi\(teacherRuntime\.page, 'teacher', accounts\.teacher\)/);
assert.match(source, /await loginFromUi\(studentRuntime\.page, 'student', accounts\.student\)/);
assert.match(source, /serviceWorkerRoleEvidence\(teacherRuntime\.page, 'teacher'/);
assert.match(source, /serviceWorkerRoleEvidence\(studentRuntime\.page, 'student'/);
assert.match(source, /serviceWorkerRoleEvidence\(adminRuntime\.page, 'admin'/);
assert.match(source, /batch import prerequisite uses public class join to establish same-school eligibility/);
assert.match(source, /\/api\/classes\/\$\{eligibilityClassId\}\/join[\s\S]*body:\s*\{ role: 'student' \}/);
assert.ok(
  source.indexOf('batch import prerequisite uses public class join to establish same-school eligibility')
    < source.indexOf("teacherForm(teacherRuntime.page, 'student-batch-import'"),
  'same-school eligibility must be established before the teacher batch import'
);
assert.match(source, /student-batch-import[\s\S]*batchImportRequests === 1/);
assert.match(source, /submissionWriteCount === 1/);
assert.match(source, /data-admin-user-governance[\s\S]*governedPatchCount === 1/);
assert.match(source, /role:\s*'teacher',[\s\S]*status:\s*'disabled'/);
assert.match(source, /governedSessionAfter\.status === 401/);
assert.match(source, /admin\.user\.update/);
assert.match(source, /admin full domain data map matches authoritative stats/);

assert.match(source, /async function mobileRoleInteraction/);
assert.match(source, /data-student-panel=\"assignments\"[^`]*data-student-assignment-id/);
assert.match(source, /setViewportSize\(\{ width: 390, height: 844 \}\)[\s\S]*mobileRoleInteraction/);
assert.match(source, /waitForResponse[\s\S]*searchParams\.get\('filter'\) === filter[\s\S]*response\.status\(\) === 200/);
assert.match(source, /async function stableUiEvidence/);
assert.match(source, /visibleErrors\.length === 0/);
assert.match(source, /visibleLoading\.length === 0/);
assert.match(source, /await freezeDiagnostics\(contexts\)/);
assert.match(source, /report\.ok = Boolean\(workflowCompleted[\s\S]*report\.browserIssues\.length === 0\)/);
assert.match(source, /sqliteDirectReconciliation:\s*'required-after-browser-proof'/);
assert.match(source, /targetEnvironmentRelease:\s*'not-in-scope'/);

console.log('role-workflows-proof-contract: ok');
