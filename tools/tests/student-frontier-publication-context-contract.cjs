const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..');
const contextPath = path.join(root, 'shared', 'js', 'frontier-publication-context.js');
const contextSource = fs.readFileSync(contextPath, 'utf8');
const studentSource = fs.readFileSync(path.join(root, 'pages', 'student', 'student.js'), 'utf8');
const indexSource = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const courseKeys = [
  'earth-space', 'engineering-systems', 'data-ai',
  'information-technology', 'materials-science', 'humanities-futures'
];
const courses = courseKeys.map((course_key, index) => ({
  id: index + 101,
  galaxy_key: 'future-galaxy',
  course_key
}));

const listeners = new Map();
const fetchCalls = [];
const configurations = [];
const renders = [];
let scenario = 'single';
let activeConfig = null;

function response(payload, ok = true) {
  return { ok, json: async () => payload };
}

global.window = global;
global.navigator = { onLine: true };
global.location = { origin: 'https://astra.test', hash: '#cosmos/day-season' };
global.addEventListener = (name, handler) => listeners.set(name, handler);
global.removeEventListener = (name) => listeners.delete(name);
global.FrontierLearning = { renderRoute: (page) => renders.push(page) };
global.AstraApplicationSession = { getUser: () => null };
global.FrontierCourseManifest = {
  galaxy_key: 'future-galaxy',
  courses: courseKeys.map((course_key) => ({ course_key })),
  configureHttp(config) {
    configurations.push(config);
    const valid = Boolean(config && config.course_ids && config.class_id !== undefined && typeof config.fetcher === 'function');
    activeConfig = valid ? config : null;
    return valid;
  },
  async refresh() {
    if (!activeConfig) return { availability: 'unavailable' };
    await activeConfig.fetcher(`/api/courses/${activeConfig.course_ids['earth-space']}/units?class_id=${activeConfig.class_id}`, { credentials: 'same-origin' });
    return { availability: 'available', source: 'http-cache' };
  }
};
global.fetch = async (url, options = {}) => {
  fetchCalls.push({ url: String(url), options });
  if (String(url).startsWith('/api/classes')) {
    if (scenario === 'multi') return response([{ id: 7 }, { id: 8 }]);
    if (scenario === 'classes-fail') return response({}, false);
    return response([{ id: 7 }]);
  }
  if (String(url).startsWith('/api/courses?')) {
    if (scenario === 'courses-fail') return response({}, false);
    return response(scenario === 'missing-course' ? courses.slice(0, -1) : courses);
  }
  if (String(url).startsWith('/api/courses/')) return response([]);
  throw new Error(`Unexpected request ${url}`);
};

delete require.cache[contextPath];
const publication = require(contextPath);

async function run() {
  assert.ok(listeners.has('astra:session-ready'), 'the globally loaded publication controller must bridge direct Future Galaxy entry');
  assert.ok(listeners.has('astra:api-auth-required'), 'authority loss must close the future release snapshot');
  assert.ok(listeners.has('astra:session-signed-out'), 'sign-out must close the future release snapshot');

  listeners.get('astra:session-ready')({ detail: { user: { id: 11, role: 'student' } } });
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  const singleConfig = configurations.at(-1);
  assert.equal(singleConfig.class_id, 7, 'one class may become the automatic authority context');
  assert.deepEqual(singleConfig.course_ids, Object.fromEntries(courses.map((course) => [course.course_key, course.id])));
  assert.equal(fetchCalls[0].url, '/api/classes?mine=true');
  assert.equal(fetchCalls[0].options.credentials, 'same-origin');
  assert.equal(fetchCalls[1].url, '/api/courses?class_id=7');
  const unitFetch = fetchCalls.find((call) => call.url.startsWith('/api/courses/101/units'));
  assert.ok(unitFetch, 'manifest refresh must use the configured course map');
  assert.equal(unitFetch.options.credentials, 'same-origin');
  assert.ok(renders.includes('cosmos'), 'a completed authority refresh must rerender the active future route');

  scenario = 'multi';
  fetchCalls.length = 0;
  const multi = await publication.bootstrap({ id: 11, role: 'student' });
  assert.equal(multi.source, 'class-selection-required');
  assert.deepEqual(configurations.at(-1), {}, 'multiple classes must close availability instead of guessing one');
  assert.equal(fetchCalls.length, 1, 'multiple classes must not request a guessed course map');

  scenario = 'missing-course';
  const missing = await publication.bootstrap({ id: 11, role: 'student' });
  assert.equal(missing.source, 'course-map-unavailable');
  assert.deepEqual(configurations.at(-1), {}, 'an incomplete six-course map must fail closed');

  scenario = 'courses-fail';
  const failed = await publication.bootstrap({ id: 11, role: 'student' });
  assert.equal(failed.source, 'course-context-unavailable');
  assert.deepEqual(configurations.at(-1), {}, 'a failed course endpoint must fail closed');

  const admin = await publication.bootstrap({ id: 99, role: 'admin' });
  assert.equal(admin.availability, 'legacy-boundary', 'non-student sessions must not configure student publication context');

  assert.doesNotMatch(contextSource, /localStorage|sessionStorage/, 'future class and course context must remain in memory only');
  assert.match(contextSource, /classes\.length !== 1/, 'multi-class learners require an explicit workbench selection');
  assert.match(contextSource, /item\.galaxy_key !== GALAXY_KEY/, 'course IDs must be filtered by Future Galaxy identity');
  assert.match(contextSource, /credentials: 'same-origin'/, 'authority requests must keep same-origin cookies');
  assert.match(studentSource, /window\.FutureGalaxyPublicationContext/, 'the student workbench must delegate class switches to the shared controller');
  assert.doesNotMatch(studentSource, /addEventListener\('astra:session-ready'/, 'the lazy student asset must not own the direct-entry session listener');

  const manifestIndex = indexSource.indexOf('pages/frontier/frontier-manifest.js');
  const contextIndex = indexSource.indexOf('shared/js/frontier-publication-context.js');
  const runtimeIndex = indexSource.indexOf('shared/js/frontier-learning.js');
  assert.ok(manifestIndex >= 0 && manifestIndex < contextIndex && contextIndex < runtimeIndex,
    'the direct-entry controller must load after the manifest and before the Future runtime');

  console.log('student-frontier-publication-context-contract: ok');
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
