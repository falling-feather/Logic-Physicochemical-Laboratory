(function () {
    'use strict';

    const TEACHER_ASSET_VERSION = '20260709v6650TeacherMvpP1';
    const API_BASE_STORAGE_KEY = 'astra-teacher-api-base';
    const TOKEN_STORAGE_KEYS = [
        'astra-access-token',
        'englab-access-token',
        'access_token',
        'auth_token'
    ];

    const state = {
        root: null,
        apiBase: '',
        initialized: false,
        busy: false,
        user: null,
        selected: {
            schoolId: '',
            classId: '',
            courseId: '',
            unitId: '',
            assignmentId: '',
            studentId: ''
        },
        filters: {
            memberRole: 'student',
            memberStatus: 'active',
            submissionStatus: 'submitted'
        },
        data: {
            schools: [],
            classes: [],
            courses: [],
            units: [],
            assignments: [],
            members: [],
            submissions: [],
            assignmentSubmissions: [],
            collaborators: [],
            pointRule: null,
            knowledge: null,
            progress: null
        },
        errors: {},
        flash: null
    };

    function initTeacher() {
        state.root = document.querySelector('[data-teacher-workbench]');
        if (!state.root) return;
        state.apiBase = resolveApiBase();
        renderShell();
        if (!state.initialized) {
            bindEvents();
            state.initialized = true;
        }
        refreshAll();
    }

    function renderShell() {
        state.root.innerHTML = `
            <header class="teacher-workbench__header">
                <div class="teacher-workbench__title">
                    <span class="teacher-workbench__eyebrow">
                        <i data-lucide="presentation"></i>
                        教师端
                    </span>
                    <h1>教学工作台</h1>
                </div>
                <div class="teacher-workbench__actions">
                    <label class="teacher-api-base">
                        <span>API</span>
                        <input type="url" data-teacher-api-base value="${escapeAttr(state.apiBase)}" placeholder="同源" autocomplete="off">
                    </label>
                    <button type="button" class="teacher-icon-button" data-teacher-action="refresh" aria-label="刷新教师工作台">
                        <i data-lucide="refresh-cw"></i>
                        <span>刷新</span>
                    </button>
                </div>
            </header>
            <div class="teacher-auth-state" data-teacher-auth-state></div>
            <div class="teacher-flash" data-teacher-flash hidden></div>
            <div class="teacher-dashboard" data-teacher-dashboard hidden>
                <section class="teacher-kpi-grid" data-teacher-kpis></section>
                <section class="teacher-scope" data-teacher-scope></section>
                <section class="teacher-panel-grid" data-teacher-panels></section>
            </div>
        `;
        refreshIcons();
    }

    function bindEvents() {
        state.root.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const refreshButton = target.closest('[data-teacher-action="refresh"]');
            if (refreshButton) {
                refreshAll();
                return;
            }
            const memberButton = target.closest('[data-teacher-member-status]');
            if (memberButton) {
                updateMemberStatus(memberButton);
                return;
            }
            const collaboratorButton = target.closest('[data-teacher-collaborator-status]');
            if (collaboratorButton) {
                updateCollaboratorStatus(collaboratorButton);
                return;
            }
        });

        state.root.addEventListener('submit', (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement) || !form.dataset.teacherForm) return;
            event.preventDefault();
            handleFormSubmit(form);
        });

        state.root.addEventListener('change', (event) => {
            const target = event.target;
            if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) return;
            if (target.matches('[data-teacher-scope]')) {
                handleScopeChange(target);
                return;
            }
            if (target.matches('[data-teacher-filter]')) {
                handleFilterChange(target);
                return;
            }
            if (target.matches('[data-teacher-api-base]')) {
                state.apiBase = target.value.trim();
                persistApiBase();
            }
        });

        state.root.addEventListener('blur', (event) => {
            const target = event.target;
            if (target instanceof HTMLInputElement && target.matches('[data-teacher-api-base]')) {
                state.apiBase = target.value.trim();
                persistApiBase();
            }
        }, true);
    }

    async function refreshAll() {
        if (!state.root) return;
        setBusy(true);
        renderAuthState('checking');
        hideDashboard();
        try {
            const user = await fetchJson('/api/users/me');
            state.user = user;
            if (!['teacher', 'admin'].includes(user.role)) {
                renderAuthState('forbidden', user);
                clearWorkspace();
                return;
            }
            renderAuthState('ready', user);
            await loadSchools();
            showDashboard();
        } catch (error) {
            renderAuthError(error);
            clearWorkspace();
        } finally {
            setBusy(false);
            refreshIcons();
        }
    }

    async function loadSchools(preferredId) {
        state.errors.schools = null;
        try {
            state.data.schools = await fetchJson('/api/schools');
        } catch (error) {
            state.data.schools = [];
            state.errors.schools = error;
        }
        const schoolId = preferredId || state.selected.schoolId;
        state.selected.schoolId = normalizeSelectedId(schoolId, state.data.schools);
        if (!state.selected.schoolId && state.data.schools.length) {
            state.selected.schoolId = String(state.data.schools[0].id);
        }
        await loadSchoolScope();
    }

    async function loadSchoolScope() {
        resetBelow('school');
        if (!state.selected.schoolId) {
            renderWorkspace();
            return;
        }
        state.errors.classes = null;
        state.errors.courses = null;
        const schoolId = state.selected.schoolId;
        const [classesResult, coursesResult] = await Promise.allSettled([
            fetchJson('/api/classes', { params: { school_id: schoolId } }),
            fetchJson('/api/courses', { params: { school_id: schoolId } })
        ]);
        if (classesResult.status === 'fulfilled') {
            state.data.classes = classesResult.value;
        } else {
            state.data.classes = [];
            state.errors.classes = classesResult.reason;
        }
        if (coursesResult.status === 'fulfilled') {
            state.data.courses = coursesResult.value;
        } else {
            state.data.courses = [];
            state.errors.courses = coursesResult.reason;
        }
        state.selected.classId = normalizeSelectedId(state.selected.classId, state.data.classes);
        state.selected.courseId = normalizeSelectedId(state.selected.courseId, state.data.courses);
        if (!state.selected.classId && state.data.classes.length) state.selected.classId = String(state.data.classes[0].id);
        if (!state.selected.courseId && state.data.courses.length) state.selected.courseId = String(state.data.courses[0].id);
        await Promise.all([loadClassScope(), loadCourseScope()]);
        renderWorkspace();
    }

    async function loadClassScope() {
        state.data.members = [];
        state.data.submissions = [];
        state.data.knowledge = null;
        state.data.progress = null;
        state.errors.members = null;
        state.errors.submissions = null;
        state.errors.knowledge = null;
        state.errors.progress = null;
        if (!state.selected.classId) return;
        const classId = state.selected.classId;
        const memberParams = {
            role: state.filters.memberRole || undefined,
            status: state.filters.memberStatus || undefined
        };
        const submissionParams = {
            class_id: classId,
            status: state.filters.submissionStatus || undefined,
            limit: 50,
            offset: 0
        };
        const knowledgeParams = {
            course_id: state.selected.courseId || undefined
        };
        const [membersResult, submissionsResult, knowledgeResult] = await Promise.allSettled([
            fetchJson(`/api/classes/${classId}/members`, { params: memberParams }),
            fetchJson('/api/admin/submissions/pending', { params: submissionParams }),
            fetchJson(`/api/classes/${classId}/knowledge`, { params: knowledgeParams })
        ]);
        if (membersResult.status === 'fulfilled') {
            state.data.members = membersResult.value;
            state.selected.studentId = normalizeSelectedId(state.selected.studentId, state.data.members.filter((item) => item.role === 'student'));
            if (!state.selected.studentId) {
                const firstStudent = state.data.members.find((item) => item.role === 'student');
                state.selected.studentId = firstStudent ? String(firstStudent.user_id) : '';
            }
        } else {
            state.errors.members = membersResult.reason;
        }
        if (submissionsResult.status === 'fulfilled') {
            state.data.submissions = Array.isArray(submissionsResult.value.items) ? submissionsResult.value.items : [];
            state.data.submissions.total = submissionsResult.value.total || state.data.submissions.length;
        } else {
            state.errors.submissions = submissionsResult.reason;
        }
        if (knowledgeResult.status === 'fulfilled') {
            state.data.knowledge = knowledgeResult.value;
        } else {
            state.errors.knowledge = knowledgeResult.reason;
        }
        await loadStudentProgress();
    }

    async function loadStudentProgress() {
        state.data.progress = null;
        state.errors.progress = null;
        if (!state.selected.classId || !state.selected.studentId) return;
        try {
            state.data.progress = await fetchJson(`/api/progress/users/${state.selected.studentId}`, {
                params: { class_id: state.selected.classId }
            });
        } catch (error) {
            state.errors.progress = error;
        }
    }

    async function loadCourseScope() {
        state.data.units = [];
        state.data.assignments = [];
        state.data.assignmentSubmissions = [];
        state.data.collaborators = [];
        state.data.pointRule = null;
        state.errors.units = null;
        state.errors.assignments = null;
        state.errors.assignmentSubmissions = null;
        state.errors.collaborators = null;
        state.errors.pointRule = null;
        if (!state.selected.courseId) return;
        const courseId = state.selected.courseId;
        const [unitsResult, assignmentsResult, collaboratorsResult] = await Promise.allSettled([
            fetchJson(`/api/courses/${courseId}/units`),
            fetchJson(`/api/courses/${courseId}/assignments`),
            fetchJson(`/api/courses/${courseId}/collaborators`, { params: { status: 'all' } })
        ]);
        if (unitsResult.status === 'fulfilled') {
            state.data.units = unitsResult.value;
        } else {
            state.errors.units = unitsResult.reason;
        }
        if (assignmentsResult.status === 'fulfilled') {
            state.data.assignments = assignmentsResult.value;
        } else {
            state.errors.assignments = assignmentsResult.reason;
        }
        if (collaboratorsResult.status === 'fulfilled') {
            state.data.collaborators = collaboratorsResult.value;
        } else {
            state.errors.collaborators = collaboratorsResult.reason;
        }
        state.selected.unitId = normalizeSelectedId(state.selected.unitId, state.data.units);
        state.selected.assignmentId = normalizeSelectedId(state.selected.assignmentId, state.data.assignments);
        if (!state.selected.unitId && state.data.units.length) state.selected.unitId = String(state.data.units[0].id);
        if (!state.selected.assignmentId && state.data.assignments.length) {
            state.selected.assignmentId = String(state.data.assignments[0].id);
        }
        await loadAssignmentScope();
    }

    async function loadAssignmentScope() {
        state.data.assignmentSubmissions = [];
        state.data.pointRule = null;
        state.errors.assignmentSubmissions = null;
        state.errors.pointRule = null;
        if (!state.selected.assignmentId) return;
        const params = state.selected.classId ? { class_id: state.selected.classId } : {};
        const [submissionsResult, ruleResult] = await Promise.allSettled([
            fetchJson(`/api/assignments/${state.selected.assignmentId}/submissions`, { params }),
            fetchJson(`/api/points/assignments/${state.selected.assignmentId}/rule`)
        ]);
        if (submissionsResult.status === 'fulfilled') {
            state.data.assignmentSubmissions = submissionsResult.value;
        } else {
            state.errors.assignmentSubmissions = submissionsResult.reason;
        }
        if (ruleResult.status === 'fulfilled') {
            state.data.pointRule = ruleResult.value;
        } else {
            state.errors.pointRule = ruleResult.reason;
        }
    }

    function renderWorkspace() {
        renderFlash();
        const dashboard = getDashboard();
        if (dashboard) dashboard.hidden = !state.user || !['teacher', 'admin'].includes(state.user.role);
        renderKpis();
        renderScope();
        renderPanels();
        refreshIcons();
    }

    function renderKpis() {
        const container = state.root.querySelector('[data-teacher-kpis]');
        if (!container) return;
        const activeClasses = state.data.classes.filter((item) => item.status === 'active').length;
        const visibleCourses = state.data.courses.filter((item) => item.status !== 'archived').length;
        const activeAssignments = state.data.assignments.filter((item) => item.status === 'active').length;
        const activeStudents = state.data.members.filter((item) => item.role === 'student' && item.status === 'active').length;
        const pendingTotal = state.data.submissions.total || state.data.submissions.length || 0;
        const knowledge = state.data.knowledge || {};
        const items = [
            ['学校', state.data.schools.length, 'school'],
            ['班级', activeClasses, 'users'],
            ['课程', visibleCourses, 'book-open'],
            ['待处理提交', pendingTotal, 'inbox'],
            ['学生', activeStudents, 'graduation-cap'],
            ['活跃作业', activeAssignments, 'clipboard-check'],
            ['完成率', `${formatPercent(knowledge.completion_percent || 0)}`, 'target'],
            ['平均得分', `${formatPercent(knowledge.average_score_percent || 0)}`, 'gauge']
        ];
        container.innerHTML = items.map(([label, value, icon]) => `
            <article class="teacher-kpi">
                <span class="teacher-kpi__icon"><i data-lucide="${icon}"></i></span>
                <strong>${escapeHtml(String(value))}</strong>
                <span>${escapeHtml(label)}</span>
            </article>
        `).join('');
    }

    function renderScope() {
        const container = state.root.querySelector('[data-teacher-scope]');
        if (!container) return;
        container.innerHTML = `
            ${renderScopeSelect('schoolId', '学校', state.data.schools, state.selected.schoolId, (item) => item.name, state.errors.schools)}
            ${renderScopeSelect('classId', '班级', state.data.classes, state.selected.classId, (item) => `${item.name}${item.status !== 'active' ? ` · ${item.status}` : ''}`, state.errors.classes)}
            ${renderScopeSelect('courseId', '课程', state.data.courses, state.selected.courseId, (item) => `${item.title}${item.status !== 'published' ? ` · ${item.status}` : ''}`, state.errors.courses)}
            ${renderScopeSelect('unitId', '单元', state.data.units, state.selected.unitId, (item) => `${item.position}. ${item.title}`, state.errors.units)}
            ${renderScopeSelect('assignmentId', '作业', state.data.assignments, state.selected.assignmentId, (item) => `${item.title}${item.status !== 'active' ? ` · ${item.status}` : ''}`, state.errors.assignments)}
        `;
    }

    function renderScopeSelect(key, label, items, value, labeler, error) {
        return `
            <label class="teacher-scope__field${error ? ' is-error' : ''}">
                <span>${escapeHtml(label)}</span>
                <select data-teacher-scope="${escapeAttr(key)}" ${error ? 'disabled' : ''}>
                    ${items.length ? '' : '<option value="">--</option>'}
                    ${items.map((item) => `<option value="${item.id}"${String(item.id) === String(value) ? ' selected' : ''}>${escapeHtml(labeler(item))}</option>`).join('')}
                </select>
            </label>
        `;
    }

    function renderPanels() {
        const container = state.root.querySelector('[data-teacher-panels]');
        if (!container) return;
        container.innerHTML = [
            renderSetupPanel(),
            renderCoursePanel(),
            renderMembersPanel(),
            renderSubmissionsPanel(),
            renderInsightPanel(),
            renderReservedPanel()
        ].join('');
    }

    function renderSetupPanel() {
        const schoolDisabled = !state.selected.schoolId;
        const courseDisabled = !state.selected.courseId || isCourseReadOnly();
        const classDisabled = !state.selected.classId || isClassReadOnly();
        const unitOptions = state.data.units.map((unit) => `<option value="${unit.id}"${String(unit.id) === state.selected.unitId ? ' selected' : ''}>${escapeHtml(unit.title)}</option>`).join('');
        return `
            <article class="teacher-panel teacher-panel--wide">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="layout-dashboard"></i>主路径</h2>
                    <span class="teacher-status-pill teacher-status-pill--readonly">V6.6.50</span>
                </header>
                <div class="teacher-form-grid">
                    <form class="teacher-form" data-teacher-form="school">
                        <h3>学校</h3>
                        <label><span>名称</span><input name="name" maxlength="160" required></label>
                        <label><span>区域</span><input name="region" maxlength="160"></label>
                        <button type="submit"><i data-lucide="plus"></i><span>创建</span></button>
                    </form>
                    <form class="teacher-form" data-teacher-form="class">
                        <h3>班级</h3>
                        <label><span>名称</span><input name="name" maxlength="160" required ${schoolDisabled ? 'disabled' : ''}></label>
                        <label><span>年级</span><input name="grade" maxlength="64" ${schoolDisabled ? 'disabled' : ''}></label>
                        <label><span>学期</span><input name="term" maxlength="64" ${schoolDisabled ? 'disabled' : ''}></label>
                        <button type="submit" ${schoolDisabled ? 'disabled' : ''}><i data-lucide="users"></i><span>创建</span></button>
                    </form>
                    <form class="teacher-form" data-teacher-form="course">
                        <h3>课程</h3>
                        <label><span>标题</span><input name="title" maxlength="180" required ${schoolDisabled ? 'disabled' : ''}></label>
                        <label><span>状态</span><select name="status" ${schoolDisabled ? 'disabled' : ''}>${optionSet(['draft', 'published', 'archived'], 'draft')}</select></label>
                        <label class="teacher-form__full"><span>摘要</span><textarea name="summary" maxlength="2000" rows="2" ${schoolDisabled ? 'disabled' : ''}></textarea></label>
                        <button type="submit" ${schoolDisabled ? 'disabled' : ''}><i data-lucide="book-plus"></i><span>创建</span></button>
                    </form>
                    <form class="teacher-form" data-teacher-form="attach">
                        <h3>挂班</h3>
                        <p>${escapeHtml(selectedCourseLabel())}</p>
                        <p>${escapeHtml(selectedClassLabel())}</p>
                        <button type="submit" ${courseDisabled || classDisabled ? 'disabled' : ''}><i data-lucide="link"></i><span>挂接</span></button>
                    </form>
                    <form class="teacher-form" data-teacher-form="unit">
                        <h3>单元</h3>
                        <label><span>标题</span><input name="title" maxlength="180" required ${courseDisabled ? 'disabled' : ''}></label>
                        <label><span>序号</span><input name="position" type="number" min="1" value="${state.data.units.length + 1}" required ${courseDisabled ? 'disabled' : ''}></label>
                        <label><span>状态</span><select name="status" ${courseDisabled ? 'disabled' : ''}>${optionSet(['draft', 'published', 'archived'], 'published')}</select></label>
                        <label><span>内容 slug</span><input name="content_slug" maxlength="180" ${courseDisabled ? 'disabled' : ''}></label>
                        <button type="submit" ${courseDisabled ? 'disabled' : ''}><i data-lucide="layers-3"></i><span>创建</span></button>
                    </form>
                    <form class="teacher-form" data-teacher-form="assignment">
                        <h3>作业</h3>
                        <label><span>单元</span><select name="unit_id" ${!unitOptions || courseDisabled ? 'disabled' : ''}>${unitOptions || '<option value="">--</option>'}</select></label>
                        <label><span>标题</span><input name="title" maxlength="180" required ${!unitOptions || courseDisabled ? 'disabled' : ''}></label>
                        <label><span>满分</span><input name="max_score" type="number" min="0" max="1000" value="100" ${!unitOptions || courseDisabled ? 'disabled' : ''}></label>
                        <label><span>状态</span><select name="status" ${!unitOptions || courseDisabled ? 'disabled' : ''}>${optionSet(['active', 'closed', 'archived'], 'active')}</select></label>
                        <label><span>截止</span><input name="due_at" type="datetime-local" ${!unitOptions || courseDisabled ? 'disabled' : ''}></label>
                        <label class="teacher-form__full"><span>说明</span><textarea name="description" maxlength="4000" rows="2" ${!unitOptions || courseDisabled ? 'disabled' : ''}></textarea></label>
                        <button type="submit" ${!unitOptions || courseDisabled ? 'disabled' : ''}><i data-lucide="clipboard-plus"></i><span>创建</span></button>
                    </form>
                </div>
            </article>
        `;
    }

    function renderCoursePanel() {
        const selectedAssignment = findById(state.data.assignments, state.selected.assignmentId);
        const rule = state.data.pointRule || {};
        return `
            <article class="teacher-panel teacher-panel--wide">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="book-open-check"></i>课程结构</h2>
                    ${statusBadge(selectedCourse() && selectedCourse().status)}
                </header>
                <div class="teacher-structure">
                    <div>
                        <h3>单元</h3>
                        ${renderSimpleList(state.data.units, (unit) => `
                            <strong>${escapeHtml(unit.position + '. ' + unit.title)}</strong>
                            <span>${escapeHtml(unit.content_slug || '无内容绑定')} · ${escapeHtml(unit.status)}</span>
                        `, state.errors.units)}
                    </div>
                    <div>
                        <h3>作业</h3>
                        ${renderSimpleList(state.data.assignments, (assignment) => `
                            <strong>${escapeHtml(assignment.title)}</strong>
                            <span>${escapeHtml(assignment.status)} · ${formatNumber(assignment.max_score)} 分 · ${assignment.due_at ? formatDate(assignment.due_at) : '无截止'}</span>
                        `, state.errors.assignments)}
                    </div>
                </div>
                <div class="teacher-subpanel-grid">
                    <form class="teacher-form teacher-form--inline" data-teacher-form="point-rule">
                        <h3>积分规则</h3>
                        <label><span>作业</span><select name="assignment_id" ${selectedAssignment ? '' : 'disabled'}>${assignmentOptions()}</select></label>
                        <label class="teacher-checkbox"><input name="enabled" type="checkbox" ${rule.enabled !== false ? 'checked' : ''} ${selectedAssignment ? '' : 'disabled'}><span>启用</span></label>
                        <label><span>每分积分</span><input name="points_per_score" type="number" min="0" max="1000" value="${escapeAttr(rule.points_per_score ?? 1)}" ${selectedAssignment ? '' : 'disabled'}></label>
                        <label><span>上限</span><input name="max_points" type="number" min="0" max="100000" value="${escapeAttr(rule.max_points ?? '')}" ${selectedAssignment ? '' : 'disabled'}></label>
                        <button type="submit" ${selectedAssignment && !isCourseReadOnly() ? '' : 'disabled'}><i data-lucide="save"></i><span>保存</span></button>
                    </form>
                    <form class="teacher-form teacher-form--inline" data-teacher-form="collaborator">
                        <h3>协作者</h3>
                        <label><span>用户 ID</span><input name="user_id" type="number" min="1" ${state.selected.courseId && !isCourseReadOnly() ? '' : 'disabled'}></label>
                        <button type="submit" ${state.selected.courseId && !isCourseReadOnly() ? '' : 'disabled'}><i data-lucide="user-plus"></i><span>添加</span></button>
                    </form>
                </div>
                ${renderCollaborators()}
            </article>
        `;
    }

    function renderMembersPanel() {
        return `
            <article class="teacher-panel">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="users-round"></i>成员</h2>
                    ${statusBadge(selectedClass() && selectedClass().status)}
                </header>
                <div class="teacher-filter-row">
                    <label><span>角色</span><select data-teacher-filter="memberRole">${optionSet(['student', 'teacher'], state.filters.memberRole, [['', '全部']])}</select></label>
                    <label><span>状态</span><select data-teacher-filter="memberStatus">${optionSet(['active', 'inactive'], state.filters.memberStatus)}</select></label>
                </div>
                ${renderMembersTable()}
            </article>
        `;
    }

    function renderMembersTable() {
        if (state.errors.members) return renderError(state.errors.members, '成员读取失败');
        if (!state.selected.classId) return renderEmpty('请选择班级');
        if (!state.data.members.length) return renderEmpty('暂无成员');
        return `
            <div class="teacher-table-wrap">
                <table class="teacher-table">
                    <thead><tr><th>用户</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>
                        ${state.data.members.map((member) => `
                            <tr>
                                <td><strong>${escapeHtml(member.display_name || member.username)}</strong><span>${escapeHtml(member.username)} · #${member.user_id}</span></td>
                                <td>${statusBadge(member.role)}</td>
                                <td>${statusBadge(member.status)}</td>
                                <td>
                                    ${member.role === 'student' ? `
                                        <button type="button" class="teacher-icon-button teacher-icon-button--compact" data-teacher-member-status="${member.status === 'active' ? 'inactive' : 'active'}" data-membership-id="${member.id}" ${isClassReadOnly() ? 'disabled' : ''} aria-label="切换学生状态">
                                            <i data-lucide="${member.status === 'active' ? 'user-minus' : 'user-check'}"></i>
                                        </button>
                                    ` : '<span class="teacher-muted">--</span>'}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    function renderSubmissionsPanel() {
        return `
            <article class="teacher-panel">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="clipboard-list"></i>提交与评分</h2>
                    <span class="teacher-status-pill">${formatNumber(state.data.submissions.total || state.data.submissions.length)} 条</span>
                </header>
                <div class="teacher-filter-row">
                    <label><span>队列</span><select data-teacher-filter="submissionStatus">${optionSet(['submitted', 'returned'], state.filters.submissionStatus, [['', '全部']])}</select></label>
                </div>
                ${renderSubmissionQueue()}
                ${renderGradeForm()}
            </article>
        `;
    }

    function renderSubmissionQueue() {
        if (state.errors.submissions) return renderError(state.errors.submissions, '提交队列读取失败');
        if (!state.selected.classId) return renderEmpty('请选择班级');
        if (!state.data.submissions.length) return renderEmpty('暂无待处理提交');
        return `
            <div class="teacher-table-wrap teacher-table-wrap--short">
                <table class="teacher-table">
                    <thead><tr><th>学生</th><th>作业</th><th>状态</th><th>时间</th></tr></thead>
                    <tbody>
                        ${state.data.submissions.map((item) => `
                            <tr>
                                <td><strong>${escapeHtml(item.student_display_name || item.student_username)}</strong><span>#${item.student_id}</span></td>
                                <td><strong>${escapeHtml(item.assignment_title)}</strong><span>${escapeHtml(item.course_title || '')}</span></td>
                                <td>${statusBadge(item.status)}</td>
                                <td>${formatDate(item.submitted_at)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    function renderGradeForm() {
        const options = state.data.assignmentSubmissions.map((submission) => {
            const member = state.data.members.find((item) => item.user_id === submission.student_id);
            const label = `${member ? (member.display_name || member.username) : `#${submission.student_id}`} · ${submission.status} · #${submission.id}`;
            return `<option value="${submission.id}">${escapeHtml(label)}</option>`;
        }).join('');
        const disabled = !options;
        return `
            <form class="teacher-form teacher-form--grade" data-teacher-form="grade">
                <h3>评分</h3>
                <label><span>提交</span><select name="submission_id" ${disabled ? 'disabled' : ''}>${options || '<option value="">--</option>'}</select></label>
                <label><span>分数</span><input name="score" type="number" min="0" max="1000" value="100" ${disabled ? 'disabled' : ''}></label>
                <label><span>状态</span><select name="status" ${disabled ? 'disabled' : ''}>${optionSet(['graded', 'returned'], 'graded')}</select></label>
                <label class="teacher-form__full"><span>反馈</span><textarea name="feedback" maxlength="4000" rows="2" ${disabled ? 'disabled' : ''}></textarea></label>
                <button type="submit" ${disabled ? 'disabled' : ''}><i data-lucide="check-check"></i><span>提交</span></button>
            </form>
        `;
    }

    function renderInsightPanel() {
        const knowledge = state.data.knowledge;
        const progress = state.data.progress;
        return `
            <article class="teacher-panel">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="chart-no-axes-combined"></i>学情</h2>
                    ${state.errors.knowledge ? statusBadge('limited') : statusBadge('ready')}
                </header>
                ${state.errors.knowledge ? renderError(state.errors.knowledge, '班级学情读取失败') : `
                    <div class="teacher-metric-grid">
                        ${metric('活跃学生', knowledge && knowledge.students_active)}
                        ${metric('应交', knowledge && knowledge.expected_submissions)}
                        ${metric('已交', knowledge && knowledge.submitted_assignments)}
                        ${metric('已评分', knowledge && knowledge.graded_assignments)}
                        ${metric('完成率', knowledge ? formatPercent(knowledge.completion_percent) : '--')}
                        ${metric('平均分', knowledge ? formatPercent(knowledge.average_score_percent) : '--')}
                    </div>
                    ${renderKnowledgeStats(knowledge)}
                `}
                <div class="teacher-divider"></div>
                <div class="teacher-filter-row">
                    <label><span>学生</span><select data-teacher-scope="studentId">${studentOptions()}</select></label>
                </div>
                ${state.errors.progress ? renderError(state.errors.progress, '学生进度读取失败') : renderProgress(progress)}
            </article>
        `;
    }

    function renderReservedPanel() {
        const items = [
            ['移除/转班', '后续'],
            ['批量导入', '后续'],
            ['多角色协作者', '后续'],
            ['班级专属作业', '后续']
        ];
        return `
            <article class="teacher-panel teacher-panel--reserved">
                <header class="teacher-panel__header">
                    <h2><i data-lucide="route"></i>后续入口</h2>
                    <span class="teacher-status-pill teacher-status-pill--paused">预留</span>
                </header>
                <div class="teacher-reserved-list">
                    ${items.map(([label, status]) => `
                        <div>
                            <span>${escapeHtml(label)}</span>
                            ${statusBadge(status)}
                        </div>
                    `).join('')}
                </div>
            </article>
        `;
    }

    async function handleFormSubmit(form) {
        const formType = form.dataset.teacherForm;
        try {
            setBusy(true);
            if (formType === 'school') await createSchool(form);
            if (formType === 'class') await createClass(form);
            if (formType === 'course') await createCourse(form);
            if (formType === 'attach') await attachCourseToClass();
            if (formType === 'unit') await createUnit(form);
            if (formType === 'assignment') await createAssignment(form);
            if (formType === 'point-rule') await updatePointRule(form);
            if (formType === 'collaborator') await createCollaborator(form);
            if (formType === 'grade') await gradeSubmission(form);
            form.reset();
        } catch (error) {
            setFlash('error', errorMessage(error));
        } finally {
            setBusy(false);
            renderWorkspace();
        }
    }

    async function createSchool(form) {
        const data = formData(form);
        const school = await fetchJson('/api/schools', {
            method: 'POST',
            body: { name: data.name, region: optional(data.region) }
        });
        setFlash('success', '学校已创建');
        state.selected.schoolId = String(school.id);
        await loadSchools(school.id);
    }

    async function createClass(form) {
        const data = formData(form);
        const classGroup = await fetchJson('/api/classes', {
            method: 'POST',
            body: {
                school_id: Number(state.selected.schoolId),
                name: data.name,
                grade: optional(data.grade),
                term: optional(data.term)
            }
        });
        setFlash('success', '班级已创建');
        state.selected.classId = String(classGroup.id);
        await loadSchoolScope();
    }

    async function createCourse(form) {
        const data = formData(form);
        const course = await fetchJson('/api/courses', {
            method: 'POST',
            body: {
                school_id: Number(state.selected.schoolId),
                title: data.title,
                summary: optional(data.summary),
                status: data.status || 'draft'
            }
        });
        setFlash('success', '课程已创建');
        state.selected.courseId = String(course.id);
        await loadSchoolScope();
    }

    async function attachCourseToClass() {
        await fetchJson(`/api/courses/${state.selected.courseId}/classes`, {
            method: 'POST',
            body: { class_id: Number(state.selected.classId) }
        });
        setFlash('success', '课程已挂接班级');
        await loadClassScope();
    }

    async function createUnit(form) {
        const data = formData(form);
        const unit = await fetchJson(`/api/courses/${state.selected.courseId}/units`, {
            method: 'POST',
            body: {
                title: data.title,
                position: Number(data.position) || 1,
                content_slug: optional(data.content_slug),
                status: data.status || 'published'
            }
        });
        setFlash('success', '单元已创建');
        state.selected.unitId = String(unit.id);
        await loadCourseScope();
    }

    async function createAssignment(form) {
        const data = formData(form);
        const unitId = data.unit_id || state.selected.unitId;
        const assignment = await fetchJson(`/api/courses/${state.selected.courseId}/units/${unitId}/assignments`, {
            method: 'POST',
            body: {
                title: data.title,
                description: optional(data.description),
                due_at: data.due_at ? new Date(data.due_at).toISOString() : null,
                max_score: Number(data.max_score) || 0,
                status: data.status || 'active'
            }
        });
        setFlash('success', '作业已创建');
        state.selected.assignmentId = String(assignment.id);
        await loadCourseScope();
    }

    async function updatePointRule(form) {
        const data = formData(form);
        const assignmentId = data.assignment_id || state.selected.assignmentId;
        await fetchJson(`/api/points/assignments/${assignmentId}/rule`, {
            method: 'PATCH',
            body: {
                enabled: Boolean(data.enabled),
                points_per_score: Number(data.points_per_score) || 0,
                max_points: data.max_points ? Number(data.max_points) : null
            }
        });
        setFlash('success', '积分规则已保存');
        state.selected.assignmentId = String(assignmentId);
        await loadAssignmentScope();
    }

    async function createCollaborator(form) {
        const data = formData(form);
        await fetchJson(`/api/courses/${state.selected.courseId}/collaborators`, {
            method: 'POST',
            body: { user_id: Number(data.user_id), role: 'editor' }
        });
        setFlash('success', '协作者已添加');
        await loadCourseScope();
    }

    async function gradeSubmission(form) {
        const data = formData(form);
        await fetchJson(`/api/submissions/${data.submission_id}/grade`, {
            method: 'PATCH',
            body: {
                score: Number(data.score) || 0,
                feedback: optional(data.feedback),
                status: data.status || 'graded'
            }
        });
        setFlash('success', '评分已提交');
        await Promise.all([loadClassScope(), loadAssignmentScope()]);
    }

    async function updateMemberStatus(button) {
        try {
            setBusy(true);
            await fetchJson(`/api/classes/${state.selected.classId}/members/${button.dataset.membershipId}`, {
                method: 'PATCH',
                body: { status: button.dataset.teacherMemberStatus, note: null }
            });
            setFlash('success', '成员状态已更新');
            await loadClassScope();
        } catch (error) {
            setFlash('error', errorMessage(error));
        } finally {
            setBusy(false);
            renderWorkspace();
        }
    }

    async function updateCollaboratorStatus(button) {
        try {
            setBusy(true);
            await fetchJson(`/api/courses/${state.selected.courseId}/collaborators/${button.dataset.collaboratorId}`, {
                method: 'PATCH',
                body: { status: button.dataset.teacherCollaboratorStatus }
            });
            setFlash('success', '协作者状态已更新');
            await loadCourseScope();
        } catch (error) {
            setFlash('error', errorMessage(error));
        } finally {
            setBusy(false);
            renderWorkspace();
        }
    }

    async function handleScopeChange(target) {
        const key = target.dataset.teacherScope;
        state.selected[key] = target.value;
        setBusy(true);
        try {
            if (key === 'schoolId') await loadSchoolScope();
            if (key === 'classId') await loadClassScope();
            if (key === 'courseId') {
                await loadCourseScope();
                await loadClassScope();
            }
            if (key === 'unitId') renderWorkspace();
            if (key === 'assignmentId') await loadAssignmentScope();
            if (key === 'studentId') await loadStudentProgress();
        } finally {
            setBusy(false);
            renderWorkspace();
        }
    }

    async function handleFilterChange(target) {
        const key = target.dataset.teacherFilter;
        if (key === 'memberRole') state.filters.memberRole = target.value;
        if (key === 'memberStatus') state.filters.memberStatus = target.value;
        if (key === 'submissionStatus') state.filters.submissionStatus = target.value;
        setBusy(true);
        try {
            await loadClassScope();
        } finally {
            setBusy(false);
            renderWorkspace();
        }
    }

    function renderAuthState(mode, user) {
        const container = state.root.querySelector('[data-teacher-auth-state]');
        if (!container) return;
        if (mode === 'checking') {
            container.innerHTML = `
                <div class="teacher-auth-card teacher-auth-card--checking">
                    <i data-lucide="loader-circle"></i>
                    <span>正在校验教师会话</span>
                </div>
            `;
            return;
        }
        if (mode === 'forbidden') {
            container.innerHTML = `
                <div class="teacher-auth-card teacher-auth-card--blocked">
                    <i data-lucide="shield-x"></i>
                    <div>
                        <strong>当前账号无教师权限</strong>
                        <span>${escapeHtml(user.display_name || user.username || '当前用户')} · ${escapeHtml(user.role || 'unknown')}</span>
                    </div>
                </div>
            `;
            return;
        }
        container.innerHTML = `
            <div class="teacher-auth-card teacher-auth-card--ready">
                <i data-lucide="presentation"></i>
                <div>
                    <strong>${escapeHtml(user.display_name || user.username)}</strong>
                    <span>${escapeHtml(user.username)} · ${escapeHtml(user.role)} · ${escapeHtml(user.status)}</span>
                </div>
            </div>
        `;
    }

    function renderAuthError(error) {
        const container = state.root.querySelector('[data-teacher-auth-state]');
        if (!container) return;
        const isAuth = error && (error.status === 401 || error.status === 403);
        container.innerHTML = `
            <div class="teacher-auth-card teacher-auth-card--blocked">
                <i data-lucide="${isAuth ? 'lock' : 'server-off'}"></i>
                <div>
                    <strong>${isAuth ? '需要教师会话' : '后端连接失败'}</strong>
                    <span>${escapeHtml(errorMessage(error))}</span>
                </div>
            </div>
        `;
    }

    function renderCollaborators() {
        if (state.errors.collaborators) return renderError(state.errors.collaborators, '协作者读取失败');
        if (!state.selected.courseId) return '';
        if (!state.data.collaborators.length) return `<div class="teacher-empty teacher-empty--inline">暂无协作者</div>`;
        return `
            <div class="teacher-collaborators">
                ${state.data.collaborators.map((item) => `
                    <div>
                        <span>#${item.user_id}</span>
                        ${statusBadge(item.role)}
                        ${statusBadge(item.status)}
                        <button type="button" class="teacher-icon-button teacher-icon-button--compact" data-teacher-collaborator-status="${item.status === 'active' ? 'inactive' : 'active'}" data-collaborator-id="${item.id}" ${isCourseReadOnly() ? 'disabled' : ''} aria-label="切换协作者状态">
                            <i data-lucide="${item.status === 'active' ? 'user-minus' : 'user-check'}"></i>
                        </button>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderKnowledgeStats(knowledge) {
        if (!knowledge || !Array.isArray(knowledge.knowledge_stats) || !knowledge.knowledge_stats.length) {
            return renderEmpty('暂无规则统计');
        }
        return `
            <div class="teacher-knowledge-list">
                ${knowledge.knowledge_stats.slice(0, 5).map((item) => `
                    <div>
                        <strong>${escapeHtml(item.rule_code)}</strong>
                        <span>${formatNumber(item.frequency)} / ${formatNumber(item.sample_size)} · ${formatPercent(item.percent)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderProgress(progress) {
        if (!state.selected.studentId) return renderEmpty('暂无学生');
        if (!progress) return renderEmpty('暂无学生进度');
        return `
            <div class="teacher-metric-grid teacher-metric-grid--progress">
                ${metric('提交', progress.submitted_assignments)}
                ${metric('已评分', progress.graded_assignments)}
                ${metric('事件', progress.learning_events)}
                ${metric('完成', progress.completed_events)}
                ${metric('积分', progress.total_points)}
                ${metric('完成率', formatPercent(progress.completion_percent))}
            </div>
        `;
    }

    function renderSimpleList(items, renderer, error) {
        if (error) return renderError(error, '读取失败');
        if (!items.length) return renderEmpty('暂无数据');
        return `<div class="teacher-simple-list">${items.map((item) => `<div>${renderer(item)}</div>`).join('')}</div>`;
    }

    function metric(label, value) {
        return `
            <div class="teacher-metric">
                <strong>${value === undefined || value === null ? '--' : escapeHtml(String(value))}</strong>
                <span>${escapeHtml(label)}</span>
            </div>
        `;
    }

    function renderError(error, label) {
        return `
            <div class="teacher-error">
                <i data-lucide="triangle-alert"></i>
                <span>${escapeHtml(label)}：${escapeHtml(errorMessage(error))}</span>
            </div>
        `;
    }

    function renderEmpty(text) {
        return `<div class="teacher-empty">${escapeHtml(text)}</div>`;
    }

    function renderFlash() {
        const container = state.root.querySelector('[data-teacher-flash]');
        if (!container) return;
        if (!state.flash) {
            container.hidden = true;
            container.innerHTML = '';
            return;
        }
        container.hidden = false;
        container.className = `teacher-flash teacher-flash--${state.flash.type}`;
        container.innerHTML = `
            <i data-lucide="${state.flash.type === 'success' ? 'circle-check' : 'triangle-alert'}"></i>
            <span>${escapeHtml(state.flash.message)}</span>
        `;
    }

    function setFlash(type, message) {
        state.flash = { type, message };
    }

    function selectedSchool() {
        return findById(state.data.schools, state.selected.schoolId);
    }

    function selectedClass() {
        return findById(state.data.classes, state.selected.classId);
    }

    function selectedCourse() {
        return findById(state.data.courses, state.selected.courseId);
    }

    function selectedCourseLabel() {
        const course = selectedCourse();
        return course ? `课程：${course.title}` : '课程：--';
    }

    function selectedClassLabel() {
        const classGroup = selectedClass();
        return classGroup ? `班级：${classGroup.name}` : '班级：--';
    }

    function isClassReadOnly() {
        const classGroup = selectedClass();
        return !classGroup || classGroup.status !== 'active';
    }

    function isCourseReadOnly() {
        const course = selectedCourse();
        return !course || course.status === 'archived';
    }

    function assignmentOptions() {
        return state.data.assignments.map((assignment) => (
            `<option value="${assignment.id}"${String(assignment.id) === state.selected.assignmentId ? ' selected' : ''}>${escapeHtml(assignment.title)}</option>`
        )).join('') || '<option value="">--</option>';
    }

    function studentOptions() {
        const students = state.data.members.filter((item) => item.role === 'student');
        return students.map((member) => (
            `<option value="${member.user_id}"${String(member.user_id) === state.selected.studentId ? ' selected' : ''}>${escapeHtml(member.display_name || member.username)}</option>`
        )).join('') || '<option value="">--</option>';
    }

    function optionSet(values, current, prefix) {
        const options = (prefix || []).concat(values.map((value) => [value, value]));
        return options.map(([value, label]) => `<option value="${escapeAttr(value)}"${value === current ? ' selected' : ''}>${escapeHtml(label)}</option>`).join('');
    }

    function statusBadge(value) {
        if (!value) return '<span class="teacher-status-pill">--</span>';
        const normalized = String(value).replace(/[^a-z0-9_-]/gi, '').toLowerCase();
        return `<span class="teacher-status-pill teacher-status-pill--${escapeAttr(normalized)}">${escapeHtml(String(value))}</span>`;
    }

    function formData(form) {
        const data = {};
        const raw = new FormData(form);
        raw.forEach((value, key) => {
            data[key] = typeof value === 'string' ? value.trim() : value;
        });
        form.querySelectorAll('input[type="checkbox"][name]').forEach((input) => {
            data[input.name] = input.checked;
        });
        return data;
    }

    function optional(value) {
        const text = String(value || '').trim();
        return text || null;
    }

    function normalizeSelectedId(value, items) {
        if (!value) return '';
        return items.some((item) => String(item.id) === String(value)) ? String(value) : '';
    }

    function resetBelow(level) {
        if (level === 'school') {
            state.data.classes = [];
            state.data.courses = [];
            state.data.units = [];
            state.data.assignments = [];
            state.data.members = [];
            state.data.submissions = [];
            state.data.assignmentSubmissions = [];
            state.data.collaborators = [];
            state.data.pointRule = null;
            state.data.knowledge = null;
            state.data.progress = null;
        }
    }

    function clearWorkspace() {
        state.user = null;
        Object.keys(state.data).forEach((key) => {
            state.data[key] = Array.isArray(state.data[key]) ? [] : null;
        });
        hideDashboard();
    }

    function showDashboard() {
        const dashboard = getDashboard();
        if (dashboard) dashboard.hidden = false;
        renderWorkspace();
    }

    function hideDashboard() {
        const dashboard = getDashboard();
        if (dashboard) dashboard.hidden = true;
    }

    function getDashboard() {
        return state.root && state.root.querySelector('[data-teacher-dashboard]');
    }

    function setBusy(value) {
        state.busy = Boolean(value);
        if (state.root) state.root.classList.toggle('is-busy', state.busy);
    }

    async function fetchJson(path, options) {
        const request = options || {};
        const url = buildUrl(path, request.params);
        const headers = new Headers(request.headers || {});
        headers.set('Accept', 'application/json');
        if (request.body !== undefined) headers.set('Content-Type', 'application/json');
        const token = readBearerToken();
        if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
        const response = await fetch(url.toString(), {
            method: request.method || 'GET',
            headers,
            credentials: 'include',
            body: request.body !== undefined ? JSON.stringify(request.body) : undefined
        });
        if (!response.ok) {
            let message = response.statusText || 'Request failed';
            try {
                const payload = await response.json();
                message = payload.detail || payload.message || message;
            } catch (e) {}
            const error = new Error(message);
            error.status = response.status;
            throw error;
        }
        if (response.status === 204) return null;
        return response.json();
    }

    function buildUrl(path, params) {
        const base = state.apiBase ? state.apiBase.replace(/\/$/, '') : '';
        const url = new URL(`${base}${path}`, window.location.origin);
        Object.entries(params || {}).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                url.searchParams.set(key, value);
            }
        });
        return url;
    }

    function resolveApiBase() {
        try {
            const queryBase = new URLSearchParams(location.search).get('apiBase');
            if (queryBase) return queryBase.replace(/\/$/, '');
        } catch (e) {}
        try {
            const stored = localStorage.getItem(API_BASE_STORAGE_KEY);
            if (stored) return stored.replace(/\/$/, '');
        } catch (e) {}
        if (window.CONFIG && CONFIG.backend && CONFIG.backend.apiBaseUrl) {
            return String(CONFIG.backend.apiBaseUrl).replace(/\/$/, '');
        }
        return '';
    }

    function persistApiBase() {
        try {
            if (state.apiBase) localStorage.setItem(API_BASE_STORAGE_KEY, state.apiBase);
            else localStorage.removeItem(API_BASE_STORAGE_KEY);
        } catch (e) {}
    }

    function readBearerToken() {
        for (const key of TOKEN_STORAGE_KEYS) {
            try {
                const token = localStorage.getItem(key) || sessionStorage.getItem(key);
                if (token) return token;
            } catch (e) {}
        }
        return '';
    }

    function findById(items, id) {
        return (items || []).find((item) => String(item.id) === String(id)) || null;
    }

    function errorMessage(error) {
        if (!error) return '未知错误';
        const status = error.status ? `${error.status} ` : '';
        return `${status}${error.message || error.detail || '请求失败'}`;
    }

    function formatNumber(value) {
        return new Intl.NumberFormat('zh-CN').format(Number(value || 0));
    }

    function formatPercent(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }

    function formatDate(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return new Intl.DateTimeFormat('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    }

    function escapeHtml(value) {
        return String(value === undefined || value === null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    function refreshIcons() {
        if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
            try {
                lucide.createIcons({ attrs: { 'stroke-width': 1.8 }, root: state.root || document });
            } catch (e) {}
        }
    }

    window.initTeacher = initTeacher;
    window.initTeacherWorkbench = initTeacher;
    window.TEACHER_WORKBENCH_VERSION = TEACHER_ASSET_VERSION;
})();
