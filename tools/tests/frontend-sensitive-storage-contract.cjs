const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const sensitiveModules = [
  'shared/js/experiment-favorites.js',
  'shared/js/experiment-rating.js',
  'shared/js/experiment-quiz.js',
  'shared/js/experiment-guide.js',
  'shared/js/learning-progress.js',
];
for (const relativePath of sensitiveModules) {
  const source = fs.readFileSync(path.join(repoRoot, relativePath), 'utf8');
  assert.doesNotMatch(source, /\b(?:localStorage|sessionStorage)\b/, `${relativePath} must remain memory-only`);
}

const apiClient = fs.readFileSync(path.join(repoRoot, 'shared/js/api-client.js'), 'utf8');
for (const legacyKey of [
  'englab-favorites',
  'englab-ratings',
  'englab-quiz-scores',
  'englab-guide-seen',
  'englab-progress',
]) {
  assert.match(apiClient, new RegExp(`['\"]${legacyKey}['\"]`), `${legacyKey} must be scrubbed`);
}
assert.match(apiClient, /storage\.removeItem\(key\)/);

console.log('frontend sensitive storage contract passed');
