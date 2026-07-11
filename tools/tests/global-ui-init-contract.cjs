const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..', '..');
const guardedModules = [
  'shared/js/experiment-export.js',
  'shared/js/global-search.js',
  'shared/js/keyboard-shortcuts.js',
];

for (const relativePath of guardedModules) {
  const source = fs.readFileSync(path.join(repoRoot, relativePath), 'utf8');
  assert.match(source, /_initialized:\s*false/,
    `${relativePath} must track global initialization state`);
  assert.match(source, /init\(\)\s*{\s*if \(this\._initialized\) return;/,
    `${relativePath} init() must be idempotent`);
  assert.match(source, /this\._initialized\s*=\s*true;/,
    `${relativePath} must mark successful initialization`);
}

console.log('global UI initialization contract passed');
