'use strict';

const REQUIRED_TARGET_BROWSER_CHECKS = Object.freeze([
  'login_before_shell',
  'cookie_session',
  'role_navigation_isolation',
  'role_resource_isolation',
  'unauthorized_requests_denied',
  'service_worker_api_no_store',
  'organization_stale_version_409',
  'organization_archive',
  'organization_restore',
  'no_console_errors',
  'no_page_errors',
  'no_horizontal_overflow',
]);

function createTargetReleaseChecks() {
  return Object.fromEntries(REQUIRED_TARGET_BROWSER_CHECKS.map((name) => [name, false]));
}

function buildTargetBrowserEvidence(report) {
  if (!report || typeof report !== 'object') {
    throw new Error('Target browser evidence requires a workflow report object');
  }
  const environment = report.environment && typeof report.environment === 'object'
    ? report.environment
    : {};
  if (report.ok !== true || environment.mode !== 'target-staging') {
    throw new Error('Target browser evidence requires a successful target-staging workflow');
  }
  if (!environment.apiBase || environment.apiBase !== environment.webBase) {
    throw new Error('Target browser evidence requires one exact public origin');
  }
  if (environment.browserChannel !== 'msedge' || !String(environment.browserVersion || '').trim()) {
    throw new Error('Target browser evidence requires the real Microsoft Edge name and version');
  }
  if (!/^[0-9a-f]{40}$/iu.test(String(environment.gitHead || ''))) {
    throw new Error('Target browser evidence requires the frozen 40-hex Git revision');
  }
  if (!Number.isFinite(Date.parse(String(report.completedAt || '')))) {
    throw new Error('Target browser evidence requires a valid completion time');
  }

  const checks = report.targetReleaseChecks && typeof report.targetReleaseChecks === 'object'
    ? report.targetReleaseChecks
    : {};
  const actualNames = Object.keys(checks).sort();
  const requiredNames = [...REQUIRED_TARGET_BROWSER_CHECKS].sort();
  if (JSON.stringify(actualNames) !== JSON.stringify(requiredNames)) {
    throw new Error('Target browser evidence check set does not match target-release-v2');
  }
  for (const name of REQUIRED_TARGET_BROWSER_CHECKS) {
    if (checks[name] !== true) {
      throw new Error(`Target browser evidence check is incomplete: ${name}`);
    }
  }

  return {
    ok: true,
    status: 'ready',
    completed_at: report.completedAt,
    public_origin: environment.apiBase,
    release_revision: String(environment.gitHead || '').toLowerCase(),
    browser: {
      name: 'Microsoft Edge',
      version: String(environment.browserVersion),
    },
    roles: ['student', 'teacher', 'admin'],
    viewports: ['desktop', '390x844'],
    checks: Object.fromEntries(REQUIRED_TARGET_BROWSER_CHECKS.map((name) => [name, true])),
    sensitive_fields_returned: false,
    sensitive_values_returned: false,
  };
}

module.exports = {
  REQUIRED_TARGET_BROWSER_CHECKS,
  buildTargetBrowserEvidence,
  createTargetReleaseChecks,
};
