const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const manifestPath = path.join(root, 'tools/architecture/v76-module-boundaries.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const normalizePath = (filePath) => path.relative(root, filePath).replace(/\\/g, '/');
const lineCount = (source) => source.replace(/\r\n?/g, '\n').split('\n').length - (
  source.endsWith('\n') || source.endsWith('\r') ? 1 : 0
);

function walk(directory, predicate = () => true) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (['node_modules', 'vendor', '.venv', '__pycache__'].includes(entry.name)) return [];
      return walk(fullPath, predicate);
    }
    return predicate(fullPath) ? [fullPath] : [];
  });
}

function normalizedModelImportBlocks(source) {
  const blocks = [];
  for (const match of source.matchAll(/from\s+app\.models(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s+import\s*\(([\s\S]*?)\)/g)) {
    blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/from\s+\.{2,}models(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s+import\s*\(([\s\S]*?)\)/g)) {
    blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/^from\s+app\.models(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s+import\s+([^\r\n]+)/gm)) {
    if (!match[0].includes('(')) blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/^from\s+\.{2,}models(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s+import\s+([^\r\n]+)/gm)) {
    if (!match[0].includes('(')) blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/^import\s+app\.models(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?[^\r\n]*$/gm)) {
    blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/^from\s+app\s+import\s+([^\r\n]*\bmodels\b[^\r\n]*)$/gm)) {
    blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  for (const match of source.matchAll(/^from\s+\.{2,}\s+import\s+([^\r\n]*\bmodels\b[^\r\n]*)$/gm)) {
    blocks.push(match[0].replace(/\s+/g, ' ').trim());
  }
  return blocks;
}

function hashImportBlocks(blocks) {
  return crypto.createHash('sha256').update(blocks.join('\n')).digest('hex');
}

function endpointModelImportIsAllowed(relativePath, source) {
  const blocks = normalizedModelImportBlocks(source);
  if (!blocks.length) return true;
  const expectedHash = manifest.legacy_endpoint_model_import_hashes[relativePath];
  return Boolean(expectedHash && hashImportBlocks(blocks) === expectedHash);
}

function forbiddenBackendImports(relativePath, source) {
  const forbiddenImports = relativePath.startsWith('backend/app/api/endpoints/')
    ? [
      /^(?:from|import)\s+app\.api\.endpoints(?:\.|\s|$)/,
      /^from\s+\.(?:\s+import|[A-Za-z_][A-Za-z0-9_.]*\s+import)/,
    ]
    : relativePath.startsWith('backend/app/models/')
      || relativePath.startsWith('backend/app/schemas/')
      || relativePath.startsWith('backend/app/services/')
      ? [
        /^(?:from|import)\s+app\.api(?:\.|\s|$)/,
        /^from\s+\.{2,}api(?:\.|\s|$)/,
        /^from\s+\.{2,}\s+import\s+[^\r\n]*\bapi\b/,
      ]
      : null;
  if (!forbiddenImports) return [];
  return source
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => forbiddenImports.some((pattern) => pattern.test(line)));
}

function backendImportsAreAllowed(relativePath, source) {
  const observed = forbiddenBackendImports(relativePath, source);
  const legacy = manifest.legacy_backend_upward_imports[relativePath] || [];
  return observed.every((line) => legacy.includes(line));
}

function learningEvidenceApiIsAllowed(relativePath, source) {
  return manifest.learning_evidence_api_fragments.every(
    (fragment) => !source.includes(fragment) || manifest.learning_evidence_api_owners.includes(relativePath),
  );
}

function ownedGlobalDefinitions(relativePath, source) {
  const definitions = [];
  for (const [symbol, owner] of Object.entries(manifest.frontend_single_owner_globals)) {
    const assignmentPatterns = [
      new RegExp(`(?:globalThis|global|window)(?:\\.${symbol}|\\[['"]${symbol}['"]\\])\\s*(?:=|\\|\\|=|&&=|\\?\\?=)`),
      new RegExp(`Object\\.defineProperty\\((?:globalThis|global|window),\\s*['"]${symbol}['"]`),
      new RegExp(`Object\\.defineProperties\\((?:globalThis|global|window),\\s*\\{[\\s\\S]{0,1000}?\\b${symbol}\\s*:`),
      new RegExp(`Object\\.assign\\((?:globalThis|global|window),\\s*\\{[\\s\\S]{0,1000}?(?:\\b${symbol}\\b\\s*(?::|[,}])|['"]${symbol}['"]\\s*:)`),
      new RegExp(`Reflect\\.(?:set|defineProperty)\\((?:globalThis|global|window),\\s*['"]${symbol}['"]`),
    ];
    if (assignmentPatterns.some((pattern) => pattern.test(source))) {
      definitions.push({ symbol, owner, valid: relativePath === owner });
    }
  }
  return definitions;
}

const versionDeclaration = /\b(?:const|let|var)\s+([A-Z0-9_]+_(?:ASSET|RESOURCE)_VERSION)\s*=|^\s*(_galaxyCacheVersion)\s*:|^\s*const\s+(CACHE_NAME)\s*=/gm;
function resourceVersionDeclarations(relativePath, source) {
  return [...source.matchAll(versionDeclaration)]
    .map((match) => `${relativePath}:${match[1] || match[2] || match[3]}`);
}

assert.equal(manifest.schema_version, 'astra-architecture-boundaries-v1');
assert.match(manifest.baseline_revision, /^[0-9a-f]{40}$/);

for (const [relativePath, ceiling] of Object.entries(manifest.legacy_line_ceilings)) {
  const source = read(relativePath);
  assert.ok(
    lineCount(source) <= ceiling,
    `${relativePath} is a frozen legacy surface (${lineCount(source)} > ${ceiling}); move new behavior into its owning module`,
  );
}

const endpointFiles = walk(path.join(root, 'backend/app/api/endpoints'), (file) => file.endsWith('.py'));
for (const file of endpointFiles) {
  const relativePath = normalizePath(file);
  const source = fs.readFileSync(file, 'utf8');
  const blocks = normalizedModelImportBlocks(source);
  if (!blocks.length) continue;
  assert.ok(
    endpointModelImportIsAllowed(relativePath, source),
    `${relativePath} added or changed a direct persistence-model import; depend on a domain service instead`,
  );
}

const backendPythonFiles = walk(path.join(root, 'backend/app'), (file) => file.endsWith('.py'));
for (const file of backendPythonFiles) {
  const relativePath = normalizePath(file);
  if (relativePath === 'backend/app/api/router.py' || relativePath === 'backend/app/main.py') continue;
  const source = fs.readFileSync(file, 'utf8');
  assert.ok(
    backendImportsAreAllowed(relativePath, source),
    `${relativePath} added a dependency on the HTTP adapter layer or a peer endpoint`,
  );
}

for (const file of walk(path.join(root, 'backend/app/models'), (candidate) => candidate.endsWith('.py'))) {
  const source = fs.readFileSync(file, 'utf8');
  assert.doesNotMatch(
    source,
    /^(?:(?:from|import)\s+app\.(?:api|schemas|services)(?:\.|\s|$)|from\s+\.\.(?:api|schemas|services)(?:\.|\s|$)|from\s+\.\.\s+import\s+[^\r\n]*\b(?:api|schemas|services)\b)/m,
    `${normalizePath(file)} must remain a persistence-layer module`,
  );
}
for (const file of walk(path.join(root, 'backend/app/schemas'), (candidate) => candidate.endsWith('.py'))) {
  const source = fs.readFileSync(file, 'utf8');
  assert.doesNotMatch(
    source,
    /^(?:(?:from|import)\s+app\.(?:api|models|services)(?:\.|\s|$)|from\s+\.\.(?:api|models|services)(?:\.|\s|$)|from\s+\.\.\s+import\s+[^\r\n]*\b(?:api|models|services)\b)/m,
    `${normalizePath(file)} must remain a transport DTO module`,
  );
}

const frontendRoots = ['shared', 'pages', 'codevis']
  .map((directory) => path.join(root, directory))
  .filter((directory) => fs.existsSync(directory));
const isFrontendScript = (file) => /\.(?:[cm]?js)$/i.test(file);
const frontendFiles = frontendRoots.flatMap((directory) => walk(directory, isFrontendScript));
for (const file of frontendFiles) {
  const relativePath = normalizePath(file);
  const source = fs.readFileSync(file, 'utf8');
  assert.ok(
    learningEvidenceApiIsAllowed(relativePath, source),
    `learning-evidence API paths must be owned only by the shared client, found in ${relativePath}`,
  );
}

for (const [symbol, owner] of Object.entries(manifest.frontend_single_owner_globals)) {
  const definingFiles = [];
  for (const file of frontendFiles) {
    const relativePath = normalizePath(file);
    const source = fs.readFileSync(file, 'utf8');
    const definitions = ownedGlobalDefinitions(relativePath, source);
    if (definitions.some((definition) => definition.symbol === symbol)) definingFiles.push(relativePath);
  }
  assert.deepEqual(
    definingFiles,
    fs.existsSync(path.join(root, owner)) ? [owner] : [],
    `${symbol} must have one owner: ${owner}`,
  );
}

const progressCallOwners = [];
for (const file of frontendFiles) {
  if (fs.readFileSync(file, 'utf8').includes('LearningProgress.markVisited')) {
    progressCallOwners.push(normalizePath(file));
  }
}
for (const owner of progressCallOwners) {
  assert.ok(
    manifest.legacy_learning_progress_call_owners.includes(owner),
    `legacy visit tracking cannot gain a new caller: ${owner}`,
  );
}

const observedVersionDeclarations = [];
for (const file of [...frontendFiles, path.join(root, 'sw.js')]) {
  const relativePath = normalizePath(file);
  const source = fs.readFileSync(file, 'utf8');
  observedVersionDeclarations.push(...resourceVersionDeclarations(relativePath, source));
}
for (const declaration of observedVersionDeclarations) {
  assert.ok(
    manifest.legacy_resource_version_declarations.includes(declaration),
    `new resource-version tables are forbidden: ${declaration}`,
  );
}

const capabilitySource = read('shared/js/product-capabilities.js');
const capabilityContext = { window: {} };
vm.runInNewContext(capabilitySource, capabilityContext, { filename: 'shared/js/product-capabilities.js' });
const capabilities = capabilityContext.window.AstraProductCapabilities;
assert.ok(capabilities);
assert.ok(Object.isFrozen(capabilities));
assert.deepEqual(Array.from(capabilities.statuses), ['available', 'partial', 'planned', 'unavailable']);
const records = Array.from(capabilities.all());
assert.equal(new Set(records.map((record) => record.key)).size, records.length, 'capability keys must be unique');
assert.deepEqual(
  Object.fromEntries(records.map((record) => [record.key, record.status])),
  manifest.product_capability_statuses,
  'the capability registry must exactly implement the frozen PM-009 key/status ledger',
);
assert.equal(capabilities.get('formal-oj').status, 'unavailable');
assert.equal(capabilities.get('authoritative-learning-evidence').status, 'partial');
assert.equal(capabilities.get('browser-precheck').status, 'available');
assert.equal(capabilities.get('last-learning-position').status, 'planned');
assert.equal(capabilities.canPresentAsPrimary('browser-precheck'), true);
assert.equal(capabilities.canPresentAsPrimary('formal-oj'), false);
assert.equal(capabilities.canPresentAsPrimary('last-learning-position'), false);
for (const record of records) {
  assert.ok(Object.isFrozen(record), `${record.key} must be immutable`);
  assert.ok(capabilities.statuses.includes(record.status), `${record.key} has an invalid status`);
  assert.ok(record.roles.length > 0, `${record.key} must declare roles`);
  assert.ok(record.evidenceSource, `${record.key} must declare its evidence source`);
  assert.ok(record.allowedClaim, `${record.key} must declare its allowed claim`);
  assert.ok(record.prohibitedClaims.length > 0, `${record.key} must declare prohibited claims`);
}

// Synthetic counterexamples keep the scanners honest without mutating the repository.
assert.equal(
  endpointModelImportIsAllowed(
    'backend/app/api/endpoints/architecture_negative_fixture.py',
    'from app.models import LearningEvent\n',
  ),
  false,
  'a new endpoint -> ORM dependency must be rejected',
);
assert.equal(
  endpointModelImportIsAllowed(
    'backend/app/api/endpoints/architecture_negative_fixture.py',
    'from app.models.learning_evidence import LearningEvidence\n',
  ),
  false,
  'a new endpoint -> ORM submodule dependency must be rejected',
);
assert.equal(
  endpointModelImportIsAllowed(
    'backend/app/api/endpoints/architecture_negative_fixture.py',
    'from ...models.learning_evidence import LearningEvidence\n',
  ),
  false,
  'a new endpoint -> ORM relative submodule dependency must be rejected',
);
assert.equal(
  backendImportsAreAllowed(
    'backend/app/services/architecture_negative_fixture.py',
    'from app.api.endpoints import learning_evidence\n',
  ),
  false,
  'a service -> HTTP adapter dependency must be rejected',
);
assert.equal(
  backendImportsAreAllowed(
    'backend/app/services/architecture_negative_fixture.py',
    'from ..api.endpoints import learning_evidence\n',
  ),
  false,
  'a relative service -> HTTP adapter dependency must be rejected',
);
assert.equal(
  backendImportsAreAllowed(
    'backend/app/api/endpoints/architecture_negative_fixture.py',
    'from app.api.endpoints import progress\n',
  ),
  false,
  'an endpoint -> peer endpoint dependency must be rejected',
);
assert.equal(
  backendImportsAreAllowed(
    'backend/app/api/endpoints/architecture_negative_fixture.py',
    'from .progress import read_progress\n',
  ),
  false,
  'a relative endpoint -> peer endpoint dependency must be rejected',
);
assert.equal(
  learningEvidenceApiIsAllowed(
    'pages/planets/architecture-negative-fixture.js',
    "fetch('/api/learning-evidence')",
  ),
  false,
  'a page-owned learning-evidence request must be rejected',
);
assert.equal(
  learningEvidenceApiIsAllowed(
    'pages/planets/architecture-negative-fixture.mjs',
    "fetch('/api/learning-evidence')",
  ),
  false,
  'an ES module page-owned learning-evidence request must be rejected',
);
assert.deepEqual(
  ownedGlobalDefinitions(
    'pages/planets/architecture-negative-fixture.js',
    'globalThis.AstraLearningEvidenceClient = {};',
  ),
  [{
    symbol: 'AstraLearningEvidenceClient',
    owner: 'shared/js/learning-evidence-client.js',
    valid: false,
  }],
  'a duplicate global state-machine owner must be detectable',
);
assert.deepEqual(
  ownedGlobalDefinitions(
    'pages/planets/architecture-negative-fixture.mjs',
    "Object.assign(globalThis, { AstraLearningEvidenceClient: {} });",
  ),
  [{
    symbol: 'AstraLearningEvidenceClient',
    owner: 'shared/js/learning-evidence-client.js',
    valid: false,
  }],
  'an indirect duplicate global state-machine owner must be detectable',
);
assert.equal(isFrontendScript('pages/planets/architecture-negative-fixture.mjs'), true);
assert.equal(isFrontendScript('pages/planets/architecture-negative-fixture.cjs'), true);
assert.deepEqual(
  resourceVersionDeclarations(
    'pages/planets/architecture-negative-fixture.js',
    "const PLANETS_NEW_RESOURCE_VERSION = 'v2';",
  ),
  ['pages/planets/architecture-negative-fixture.js:PLANETS_NEW_RESOURCE_VERSION'],
  'a new resource-version declaration must be detectable',
);

console.log('architecture-boundary-contract: ok');
