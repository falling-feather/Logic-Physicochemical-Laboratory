const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const testsDirectory = __dirname;
const testFiles = fs.readdirSync(testsDirectory)
  .filter((name) => name.endsWith('.cjs') && name !== path.basename(__filename))
  .sort();

for (const testFile of testFiles) {
  const result = spawnSync(process.execPath, [path.join(testsDirectory, testFile)], {
    cwd: path.resolve(testsDirectory, '..', '..'),
    encoding: 'utf8',
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status || 1;
    break;
  }
}

if (!process.exitCode) {
  console.log(`all ${testFiles.length} frontend contracts passed`);
}
