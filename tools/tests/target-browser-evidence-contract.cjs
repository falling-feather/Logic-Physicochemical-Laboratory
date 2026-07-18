const assert = require('node:assert/strict');

const {
  REQUIRED_TARGET_BROWSER_CHECKS,
  buildTargetBrowserEvidence,
  createTargetReleaseChecks,
} = require('../browser/target-browser-evidence.cjs');

const report = {
  ok: true,
  completedAt: '2026-07-18T12:00:00.000Z',
  environment: {
    mode: 'target-staging',
    apiBase: 'https://astra-staging.trycloudflare.com',
    webBase: 'https://astra-staging.trycloudflare.com',
    browserChannel: 'msedge',
    browserVersion: '140.0.0.0',
    gitHead: 'a'.repeat(40),
  },
  targetReleaseChecks: Object.fromEntries(
    REQUIRED_TARGET_BROWSER_CHECKS.map((name) => [name, true])
  ),
};

const evidence = buildTargetBrowserEvidence(report);
assert.deepEqual(Object.keys(evidence).sort(), [
  'browser',
  'checks',
  'completed_at',
  'ok',
  'public_origin',
  'release_revision',
  'roles',
  'sensitive_fields_returned',
  'sensitive_values_returned',
  'status',
  'viewports',
].sort());
assert.equal(evidence.status, 'ready');
assert.equal(evidence.public_origin, report.environment.apiBase);
assert.equal(evidence.release_revision, report.environment.gitHead);
assert.deepEqual(new Set(evidence.roles), new Set(['student', 'teacher', 'admin']));
assert.deepEqual(new Set(evidence.viewports), new Set(['desktop', '390x844']));
assert.deepEqual(Object.keys(evidence.checks).sort(), [...REQUIRED_TARGET_BROWSER_CHECKS].sort());
assert.ok(Object.values(evidence.checks).every((value) => value === true));
assert.equal(evidence.sensitive_fields_returned, false);
assert.equal(evidence.sensitive_values_returned, false);

const incomplete = { ...report, targetReleaseChecks: createTargetReleaseChecks() };
assert.throws(
  () => buildTargetBrowserEvidence(incomplete),
  /check is incomplete: login_before_shell/
);
assert.throws(
  () => buildTargetBrowserEvidence({ ...report, environment: { ...report.environment, mode: 'isolated-local' } }),
  /successful target-staging workflow/
);
assert.throws(
  () => buildTargetBrowserEvidence({ ...report, environment: { ...report.environment, browserVersion: '' } }),
  /real Microsoft Edge name and version/
);
assert.throws(
  () => buildTargetBrowserEvidence({ ...report, environment: { ...report.environment, gitHead: '' } }),
  /frozen 40-hex Git revision/
);
assert.throws(
  () => buildTargetBrowserEvidence({
    ...report,
    targetReleaseChecks: { ...report.targetReleaseChecks, extra_check: true },
  }),
  /check set does not match target-release-v2/
);

console.log('target-browser-evidence-contract: ok');
