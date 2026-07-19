const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const sha256 = (file) => crypto
  .createHash('sha256')
  .update(fs.readFileSync(path.join(root, file)))
  .digest('hex');

const html = read('index.html');
const about = read('pages/about/about.js');
const registry = read('shared/js/page-registry.js');
const packageJson = JSON.parse(read('package.json'));
const lock = JSON.parse(read('package-lock.json'));
const source = read('shared/vendor/marked-v12/SOURCE.md');

assert.doesNotMatch(html, /fonts\.(?:googleapis|gstatic)\.com/i, 'application boot must not fetch remote fonts');
assert.doesNotMatch(about, /(?:cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)/i, 'about pages must not load a CDN runtime');
assert.match(about, /shared\/vendor\/marked-v12\/marked\.min\.js\?v=20260719re2OfflineP0/);
assert.match(registry, /ABOUT_RESOURCE_VERSION = '20260719re2OfflineP0'/);
assert.equal(packageJson.dependencies.marked, '12.0.0');
assert.equal(lock.packages['node_modules/marked'].version, '12.0.0');
assert.equal(
  lock.packages['node_modules/marked'].integrity,
  'sha512-Vkwtq9rLqXryZnWaQc86+FHLC6tr/fycMfYAhiOIXkrNmeGAyhSxjqu0Rs1i0bBqw5u0S7+lV9fdH2ZSVaoa0w=='
);

const expectedHashes = {
  'shared/vendor/marked-v12/marked.min.js': 'eb1f6b19880bc80a5fe34c6a61885173b60edda455ba7a33c98714db17d39f99',
  'shared/vendor/marked-v12/LICENSE.md': '8e3a3f82f59a60958f56ca08f445647c32a4733dc7ca6c2c46f6eb898471ab9c',
};
for (const [file, expected] of Object.entries(expectedHashes)) {
  assert.equal(sha256(file), expected, `${file} must match the audited npm payload`);
  assert.match(source, new RegExp(expected));
}

console.log('offline-runtime-assets-contract: ok');
