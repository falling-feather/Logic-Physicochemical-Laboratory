const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const teacher = fs.readFileSync(path.join(root, 'pages/teacher/teacher.js'), 'utf8');

function between(start, end) {
  const startIndex = teacher.indexOf(start);
  const endIndex = teacher.indexOf(end, startIndex + start.length);
  assert.ok(startIndex >= 0 && endIndex > startIndex, `missing teacher block: ${start}`);
  return teacher.slice(startIndex, endIndex);
}

for (const [name, maximum] of [
  ['MEMBER_PAGE_LIMIT', 200],
  ['ACTIVE_STUDENT_PAGE_LIMIT', 200],
  ['ASSIGNMENT_SUBMISSION_PAGE_LIMIT', 200],
  ['CODE_ATTEMPT_PAGE_LIMIT', 200]
]) {
  const match = teacher.match(new RegExp(`const ${name} = (\\d+);`));
  assert.ok(match, `${name} must be explicit`);
  assert.ok(Number(match[1]) > 0 && Number(match[1]) <= maximum, `${name} must stay within the API ceiling`);
}

const classScope = between('async function loadClassScope', 'async function fetchClassKnowledge');
assert.match(classScope, /\/api\/classes\/\$\{classId\}\/members\/page/);
assert.match(classScope, /membersResult\.value\.items/);
assert.match(classScope, /activeStudentsResult\.value\.items/);
assert.doesNotMatch(classScope, /\/members`,/);

const assignmentScope = between('async function loadAssignmentScope', 'async function loadCurriculumScope');
assert.match(assignmentScope, /\/api\/assignments\/\$\{state\.selected\.assignmentId\}\/submissions\/page/);
assert.match(assignmentScope, /submissionsResult\.value\.items/);
assert.doesNotMatch(assignmentScope, /\/submissions`,/);

const codeDetails = between('async function loadCodeSubmissionDetails', 'function handleViewNavigationKeydown');
assert.match(codeDetails, /\/api\/code-submissions\/\$\{submissionId\}\/attempts\/page/);
assert.match(codeDetails, /attemptsResult\.value\.items/);
assert.doesNotMatch(codeDetails, /\/attempts`/);

for (const kind of ['members', 'active-students', 'assignment-submissions', 'code-attempts']) {
  assert.ok(teacher.includes(`'${kind}'`), `teacher pagination must expose ${kind}`);
  assert.ok(teacher.includes(`renderCurriculumPageControls`), 'shared pagination controls must remain available');
}

assert.match(teacher, /activeStudentsPage\s*&&\s*state\.data\.activeStudentsPage\.total/);
assert.match(teacher, /function studentOptions\(\)[\s\S]*state\.data\.activeStudents\.map/);
assert.match(teacher, /function normalizeSelectedUserId/);
assert.match(teacher, /data-teacher-curriculum-page=/);
assert.match(teacher, /page\.next_offset/);

console.log('teacher-pagination-contract: ok');
