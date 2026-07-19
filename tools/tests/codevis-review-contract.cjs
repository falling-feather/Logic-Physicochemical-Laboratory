const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const challenge = fs.readFileSync(path.join(root, 'codevis/pages/course-challenge/course-challenge.js'), 'utf8');

assert.match(challenge, /function restoreResultFocus\(intent, generation\)/,
    'challenge results need an explicit, user-action-only focus restoration path');
assert.match(challenge, /render\(\);\s*restoreResultFocus\('run', runGeneration\);/,
    'run completion must restore focus after the result is rendered');
assert.match(challenge, /render\(\);\s*restoreResultFocus\('submit', generation\);/,
    'formal-submit completion must restore focus after the status is rendered');
assert.match(challenge, /generation !== challenge\.runGeneration/, 'stale repeated runs must not reclaim focus');
assert.match(challenge, /generation !== challenge\.submissionGeneration/, 'stale submissions must not reclaim focus');
assert.match(challenge, /#challenge-repair/, 'run completion must land on the repair action');
assert.match(challenge, /#challenge-submit:not\(\[disabled\]\).*#challenge-submission-status/s,
    'formal completion must prefer a next action and fall back to the semantic status');
assert.match(challenge, /id="challenge-submission-status"[^>]*tabindex="-1"/,
    'the formal result status must be programmatically focusable');
assert.match(challenge, /code\.addEventListener\('keydown',[\s\S]*event\.key === 'Enter'[\s\S]*run\(\)/,
    'Ctrl/Cmd+Enter must share the user-triggered run completion path');
assert.equal((challenge.match(/\.focus\(/g) || []).length, 2,
    'only result completion and the explicit repair action may move challenge focus');
assert.match(challenge, /#challenge-repair[\s\S]*requestAnimationFrame\(\(\) => root\.querySelector\('#challenge-code'\)\.focus\(\)\)/,
    'the existing repair action may keep its explicit editor focus behavior');

process.stdout.write('codevis-review-contract: re3 focus contract ok\n');
