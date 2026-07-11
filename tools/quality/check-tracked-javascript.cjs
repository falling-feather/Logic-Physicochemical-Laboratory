const { execFileSync, spawnSync } = require('node:child_process');
const path = require('node:path');

const repositoryRoot = path.resolve(__dirname, '..', '..');
const trackedOutput = execFileSync(
  'git',
  ['ls-files', '-z', '--', '*.js', '*.mjs', '*.cjs'],
  { cwd: repositoryRoot, encoding: 'buffer', windowsHide: true },
);
const trackedFiles = trackedOutput
  .toString('utf8')
  .split('\0')
  .filter(Boolean)
  .sort();

if (trackedFiles.length === 0) {
  console.error('No tracked JavaScript files were found.');
  process.exit(1);
}

for (const trackedFile of trackedFiles) {
  const result = spawnSync(process.execPath, ['--check', trackedFile], {
    cwd: repositoryRoot,
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.stderr.write(result.stderr || result.stdout || 'JavaScript syntax check failed.\n');
    process.exit(result.status || 1);
  }
}

console.log(`all ${trackedFiles.length} tracked JavaScript files passed syntax check`);
