const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function read(relativePath) {
    return fs.readFileSync(path.resolve(__dirname, '../..', relativePath), 'utf8');
}

function main() {
    const teacher = read('pages/teacher/teacher.js');
    const student = read('pages/student/student.js');
    const admin = read('pages/admin/admin.js');

    for (const token of [
        '/students/batch-import',
        '/students/${Number(data.membership_id)}/transfer',
        '/collaborators/batch',
        "'content_editor'",
        "'assessment_editor'",
        "'viewer'",
        '/classes/${state.selected.classId}/policy',
        '/audience',
        'result.failed_count',
    ]) {
        assert.ok(teacher.includes(token), `teacher workbench must expose ${token}`);
    }
    assert.match(teacher, /软移除：保留提交、积分和审计历史/);
    assert.match(teacher, /恢复继承/);
    assert.match(teacher, /statistics|统计口径/);
    assert.match(teacher, /hasCourseCapability\(\['editor', 'content_editor'\]\)/);
    assert.match(teacher, /hasCourseCapability\(\['editor', 'content_editor', 'assessment_editor'\]\)/);
    assert.match(teacher, /hasCourseCapability\(\['editor', 'assessment_editor'\]\)/);
    assert.match(teacher, /canManageCourseOwnership\(\)/);
    assert.match(teacher, /fetchClassKnowledge\(classId\)/);
    assert.match(teacher, /params:\s*\{\s*class_id:\s*classId\s*\}/);
    assert.match(teacher, /attachedCourses\.some/);

    assert.match(student, /dimension === 'knowledge_point'/);
    assert.match(student, /优先复习知识点/);
    assert.match(student, /优先完成或复盘作业/);
    assert.match(student, /knowledge\.rule_version/);

    assert.match(admin, /\/api\/admin\/class-join-requests\/\$\{joinRequestId\}/);
    assert.match(admin, /AstraApiClient\.isAmbiguousMutation/);
    assert.match(admin, /系统未自动重试/);
    assert.match(admin, /state\.writeLock/);
    assert.match(admin, /state\.pendingJoinReview/);
    assert.match(admin, /再次点击同一按钮以确认/);
    assert.match(admin, /rerenderJoinRequestsPanel/);
    assert.match(admin, /Promise\.all\(\[\s*refreshPanel\('join-requests'\),\s*refreshStats\(\)/);
    assert.doesNotMatch(admin, /Authorization\s*:/i, 'admin mutations must remain cookie-only');

    process.stdout.write('v6653-permission-analytics-contract: ok\n');
}

try {
    main();
} catch (error) {
    console.error(error);
    process.exitCode = 1;
}
