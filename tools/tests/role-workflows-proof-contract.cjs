const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(path.join(repoRoot, 'tools/browser/role-workflows-proof.cjs'), 'utf8');

assert.match(source, /--confirm-isolated-environment/);
assert.match(source, /Pass exactly one of --confirm-isolated-environment or --confirm-target-staging/);
assert.match(source, /isLocalUrl\(apiBase\)[\s\S]*isLocalUrl\(webBase\)/);
assert.match(source, /--confirm-target-staging/);
assert.match(source, /rawApiBase[\s\S]*rawWebBase[\s\S]*isExactTargetHttpsOrigin\(rawApiBase\)/);
assert.match(source, /new URL\(rawApiBase\)\.origin === new URL\(rawWebBase\)\.origin/);
assert.match(source, /apiBase = new URL\(rawApiBase\)\.origin[\s\S]*report\.environment\.apiBase = apiBase/);
assert.match(source, /reservedSuffixes[\s\S]*isIP\(hostname\) === 0/);
assert.match(source, /EXAMPLE_DOMAIN_ROOTS[\s\S]*exampleDomain[\s\S]*parsed\.port === ''/);
assert.match(source, /exactAuthority[\s\S]*authority === `\$\{hostname\}:443`/);
assert.match(source, /\[a-z\][\s\S]*labels\.at\(-1\)/);
assert.match(source, /Target role workflow proof requires a clean frozen Git worktree/);
assert.match(source, /Target role workflow proof requires an explicit --out directory/);
assert.match(source, /Target role workflow proof output must be outside the Git worktree/);
assert.match(source, /Target role workflow proof output must start empty/);
assert.match(source, /target staging HTTPS and production-like environment guard/);
assert.match(source, /\['staging', 'production'\]\.includes/);
assert.match(source, /process\.env\.ASTRA_ADMIN_BOOTSTRAP_TOKEN/);
assert.match(source, /Target staging bootstrap token must be injected through ASTRA_ADMIN_BOOTSTRAP_TOKEN/);
assert.match(source, /process\.env\.ASTRA_QA_ADMIN_USERNAME/);
assert.match(source, /process\.env\.ASTRA_QA_ADMIN_PASSWORD/);
assert.match(source, /Local pre-provisioned admin requires both ASTRA_QA_ADMIN_USERNAME and ASTRA_QA_ADMIN_PASSWORD/);
assert.match(source, /pre-provisioned local admin selected without runtime bootstrap/);
assert.match(source, /credentialSource:\s*'process-environment'/);
assert.match(source, /adminProvisioning = 'pre-provisioned-local-environment'/);
assert.ok(
  source.indexOf('if (usePreProvisionedLocalAdmin)') < source.indexOf('const adminBootstrapToken = targetMode'),
  'local pre-provisioned credentials must bypass only the runtime bootstrap branch'
);
assert.match(source, /development'[\s\S]*'test'[\s\S]*'testing/);
assert.match(source, /gitHead:\s*currentGitHead\(\)/);
assert.match(source, /gitStatusShort:\s*currentGitStatusShort\(\)/);
assert.match(source, /criticalArtifactHashes\(\)/);
assert.match(source, /const REQUIRED_BROWSER_CHANNEL = 'msedge'/);
assert.match(source, /requested === REQUIRED_BROWSER_CHANNEL/);
assert.match(source, /channel:\s*REQUIRED_BROWSER_CHANNEL/);
assert.match(source, /browserVersion = await browser\.version\(\)/);
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
assert.match(source, /teacher forbidden admin hash falls back to planets before admin CSS or script load/);
assert.match(source, /goto\(roleUrl\(webBase, apiBase, 'admin'\)[\s\S]*waitForURL\(\/#planets\$\/\)[\s\S]*#page-planets\.page\.active/);
assert.match(source, /teacher forbidden admin hash falls back[\s\S]*window\.location\.hash = 'teacher'[\s\S]*data-teacher-dashboard/);
assert.match(source, /role shell falls back to planets before protected CSS or script load/);
assert.match(source, /goto\(roleUrl\(webBase, apiBase, 'teacher'\)[\s\S]*waitForURL\(\/#planets\$\/\)[\s\S]*Student must not load teacher or admin page resources/);
assert.match(source, /cookieSessionEvidence[\s\S]*astra_session[\s\S]*HttpOnly[\s\S]*SameSite=Lax[\s\S]*cookie-only/);
assert.match(source, /markTargetReleaseCheck\('cookie_session'\)/);
assert.match(source, /markTargetReleaseCheck\('service_worker_api_no_store'\)/);
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
assert.match(source, /data-admin-panel-form="users"[\s\S]*accounts\.governed\.username[\s\S]*button\[type="submit"\]/);
assert.match(source, /role:\s*'teacher',[\s\S]*status:\s*'disabled'/);
assert.match(source, /governedSessionAfter\.status === 401/);
assert.match(source, /admin\.user\.update/);
assert.match(source, /admin full domain data map matches authoritative stats/);
assert.match(source, /async function selectAdminSection/);
assert.match(source, /selectAdminSection\(adminRuntime\.page, 'organizations', '\[data-admin-panel="join-requests"\]'/);
assert.match(source, /selectAdminSection\(adminRuntime\.page, 'identity', '\[data-admin-panel="users"\]'/);
assert.match(source, /selectAdminSection\(adminRuntime\.page, 'operations', '\[data-admin-panel="audit-logs"\]'/);
assert.match(source, /selectAdminSection\(adminRuntime\.page, 'overview', '\[data-admin-overview\]'/);

assert.match(source, /async function mobileRoleInteraction/);
assert.match(source, /mobileRoleInteraction[\s\S]*selectAdminSection\(page, 'organizations', '\[data-admin-panel="schools"\]'/);
assert.match(source, /data-student-panel=\"assignments\"[^`]*data-student-assignment-id/);
assert.match(source, /setViewportSize\(\{ width: 390, height: 844 \}\)[\s\S]*mobileRoleInteraction/);
assert.match(source, /waitForResponse[\s\S]*searchParams\.get\('filter'\) === filter[\s\S]*response\.status\(\) === 200/);
assert.match(source, /async function stableUiEvidence/);
assert.match(source, /visibleErrors\.length === 0/);
assert.match(source, /visibleLoading\.length === 0/);
assert.match(source, /await freezeDiagnostics\(contexts\)/);
assert.match(source, /report\.ok = Boolean\(workflowCompleted[\s\S]*report\.browserIssues\.length === 0\)/);
assert.match(source, /databaseDirectReconciliation:[\s\S]*'required-sqlite-after-browser-proof'[\s\S]*'required-mysql-after-browser-proof'/);
assert.match(source, /targetEnvironmentRelease:\s*targetMode\s*\?\s*'required-after-browser-proof'\s*:\s*'not-in-scope'/);
assert.match(source, /buildTargetBrowserEvidence\(report\)/);
assert.match(source, /TARGET_BROWSER_EVIDENCE_FILENAME/);
assert.match(source, /markTargetReleaseCheck\('organization_stale_version_409'\)/);
assert.match(source, /markTargetReleaseCheck\('organization_archive'\)/);
assert.match(source, /markTargetReleaseCheck\('organization_restore'\)/);
assert.match(source, /markTargetReleaseCheck\('no_console_errors'\)/);
assert.match(source, /markTargetReleaseCheck\('no_page_errors'\)/);
assert.match(source, /markTargetReleaseCheck\('no_horizontal_overflow'\)/);

console.log('role-workflows-proof-contract: ok');
