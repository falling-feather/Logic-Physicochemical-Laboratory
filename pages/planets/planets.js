/* ===== 星序顶层星系入口 · DOM + Canvas 星场 ===== */

(function () {
    const GALAXIES = {
        englab: {
            title: '工科试验室',
            copy: '进入工科试验室后，再选择数学、物理、化学、算法或生物。',
            modules: [
                ['总览', '#home'],
                ['数学', '#mathematics'],
                ['物理', '#physics'],
                ['化学', '#chemistry'],
                ['算法', '#algorithms'],
                ['生物', '#biology']
            ],
            orbit: { rx: 250, ry: 132, phase: Math.PI, speed: 0.000045, dir: 1 }
        },
        codespace: {
            title: '代码空间',
            copy: '进入代码空间后，再选择代码追踪或语言运行方向。',
            modules: [
                ['首页', 'codevis/index.html#home'],
                ['代码追踪', 'codevis/index.html#trace'],
                ['JavaScript', 'codevis/index.html#trace'],
                ['Python', 'codevis/index.html#trace'],
                ['C / C++', 'codevis/index.html#trace']
            ],
            orbit: { rx: 250, ry: 132, phase: 0, speed: 0.000045, dir: 1 }
        },
        frontier: {
            title: '未来星系',
            state: '学习方向',
            copy: '跨学科入口由未来星系独立承载：先看学习主线，再进入材料样板路线和其他学科总览。',
            modules: [
                { label: '学习主线', href: '#frontier-frontier-route', meta: '星序 -> 未来星系 -> 材料微观' },
                { label: '材料样板路线', href: '#frontier-materials-route', meta: '尺度桥 · 实验台 · 状态回查' },
                { label: '未来星系总览', href: '#frontier', meta: '星系坐标 · 二级目录' },
                { label: '地球与宇宙科学', href: '#cosmos', meta: '季节变化 · 太阳高度' },
                { label: '工程应用', href: '#engineering', meta: '桥梁受力 · 入门实验' },
                { label: '数据科学与 AI', href: '#datascience', meta: '线性回归 · 模型训练' },
                { label: '信息技术基础', href: '#infotech', meta: '网络分层 · 数据包旅程' },
                { label: '材料与微观结构', href: '#materials', meta: '晶体结构 · 晶粒边界' },
                { label: '语言/人文可视化', href: '#humanities', meta: '文本结构 · 史料脉络' }
            ],
            orbit: { rx: 250, ry: 132, phase: Math.PI * 0.5, speed: 0.000045, dir: -1 }
        }
    };

    window.PlanetsView = {
        root: null,
        atlas: null,
        stage: null,
        canvas: null,
        ctx: null,
        menu: null,
        menuState: null,
        menuTitle: null,
        menuCopy: null,
        moduleMenu: null,
        galaxyButtons: [],
        activeGalaxy: null,
        rafId: 0,
        galaxyRafId: 0,
        width: 0,
        height: 0,
        dpr: 1,
        stars: [],
        filaments: [],
        reduceMotion: false,
        _bound: false,
        _resizeHandler: null,
        _mouseHandler: null,
        _galaxyClickHandler: null,
        _closeHandler: null,
        _markHandler: null,
        _moduleLinkHandler: null,
        _loopHandler: null,
        _galaxyMotionHandler: null,

        init() {
            if (this._bound) this.destroy();

            this.root = document.getElementById('page-planets');
            this.atlas = this.root && this.root.querySelector('.planets-atlas');
            this.stage = this.root && this.root.querySelector('.planets-stage');
            this.canvas = document.getElementById('planets-starfield');
            this.menu = document.getElementById('planets-menu');
            this.menuState = document.getElementById('planets-menu-state');
            this.menuTitle = document.getElementById('planets-menu-title');
            this.menuCopy = document.getElementById('planets-menu-copy');
            this.moduleMenu = document.getElementById('planets-module-menu');
            this.galaxyButtons = Array.from(document.querySelectorAll('#page-planets [data-galaxy]'));
            if (!this.root || !this.stage) return;

            this.ctx = this.canvas && typeof this.canvas.getContext === 'function'
                ? this.canvas.getContext('2d')
                : null;
            this.reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            window.scrollTo(0, 0);
            document.body.classList.add('planets-scroll-locked');
            if (!this._resizeHandler) {
                this._resizeHandler = this._onResize.bind(this);
                this._mouseHandler = this._onMouseMove.bind(this);
                this._galaxyClickHandler = this._onGalaxyClick.bind(this);
                this._closeHandler = this._onClose.bind(this);
                this._markHandler = this._onMarkClick.bind(this);
                this._moduleLinkHandler = this._onModuleLinkClick.bind(this);
                this._loopHandler = this._loop.bind(this);
                this._galaxyMotionHandler = this._animateGalaxies.bind(this);
            }

            this._seedGalaxyParticles();
            this._onResize();
            window.addEventListener('resize', this._resizeHandler);
            document.addEventListener('mousemove', this._mouseHandler);
            this.galaxyButtons.forEach(button => button.addEventListener('click', this._galaxyClickHandler));
            const close = this.root.querySelector('[data-close-menu]');
            if (close) close.addEventListener('click', this._closeHandler);
            const mark = this.root.querySelector('.planets-mark');
            if (mark) mark.addEventListener('click', this._markHandler);
            if (this.moduleMenu) this.moduleMenu.addEventListener('click', this._moduleLinkHandler);
            this._bound = true;

            if (this.ctx) this._loop(0);
            if (!this.reduceMotion) this.galaxyRafId = requestAnimationFrame(this._galaxyMotionHandler);
            else this._animateGalaxies(0);
        },

        destroy() {
            if (this.rafId) cancelAnimationFrame(this.rafId);
            if (this.galaxyRafId) cancelAnimationFrame(this.galaxyRafId);
            this.rafId = 0;
            this.galaxyRafId = 0;
            if (this._bound) {
                window.removeEventListener('resize', this._resizeHandler);
                document.removeEventListener('mousemove', this._mouseHandler);
                this.galaxyButtons.forEach(button => button.removeEventListener('click', this._galaxyClickHandler));
                const close = this.root && this.root.querySelector('[data-close-menu]');
                if (close) close.removeEventListener('click', this._closeHandler);
                const mark = this.root && this.root.querySelector('.planets-mark');
                if (mark) mark.removeEventListener('click', this._markHandler);
                if (this.moduleMenu) this.moduleMenu.removeEventListener('click', this._moduleLinkHandler);
            }
            this._bound = false;
            this.activeGalaxy = null;
            document.body.classList.remove('planets-scroll-locked');
        },

        _onGalaxyClick(event) {
            this.openGalaxy(event.currentTarget.dataset.galaxy);
        },

        _onClose() {
            this.resetGalaxyView();
        },

        _onMarkClick(event) {
            event.preventDefault();
            this.resetGalaxyView();
        },

        _onModuleLinkClick(event) {
            const link = event.target.closest('a[href^="#"]');
            if (!link || !this.moduleMenu || !this.moduleMenu.contains(link)) return;

            const href = link.getAttribute('href') || '';
            const router = window.Router || (typeof Router !== 'undefined' ? Router : null);
            const hashTarget = href.slice(1);
            const page = this._pageFromHashTarget(hashTarget, router);
            if (!page) return;

            event.preventDefault();
            const rect = link.getBoundingClientRect();

            if (router && typeof router.navigateTo === 'function') {
                router.transitionOrigin = {
                    x: ((rect.left + rect.width / 2) / window.innerWidth) * 100,
                    y: ((rect.top + rect.height / 2) / window.innerHeight) * 100
                };
                router._pendingModule = null;
                router._pendingAnchor = this._isFrontierAnchor(hashTarget, router) ? hashTarget : null;
                if (!router._pendingAnchor) router._lastAppliedAnchor = null;
                this.resetGalaxyView();
                router.navigateTo(page, false);
            } else if (typeof window.navigate === 'function') {
                this.resetGalaxyView();
                window.navigate(page);
            } else {
                window.location.hash = href;
            }
        },

        openGalaxy(key) {
            const source = GALAXIES[key];
            if (!source || !this.menu || !this.moduleMenu) return;
            this.activeGalaxy = key;
            if (this.menuState) this.menuState.textContent = source.state || '进入星系';
            this.menuTitle.textContent = source.title;
            this.menuCopy.textContent = source.copy;
            this.moduleMenu.innerHTML = source.modules.map(item => this._renderModuleLink(item)).join('');
            this.galaxyButtons.forEach(btn => btn.classList.toggle('is-selected', btn.dataset.galaxy === key));
            this.stage.classList.add('has-open-menu');
            this.menu.classList.add('is-open');
        },

        _renderModuleLink(item) {
            const source = Array.isArray(item)
                ? { label: item[0], href: item[1], meta: item[2] }
                : item;
            const label = this._escapeHtml(source.label || '');
            const href = this._escapeHtml(source.href || '#planets');
            const rawHash = source.href && String(source.href).startsWith('#') ? String(source.href).slice(1) : '';
            const page = rawHash ? this._pageFromHashTarget(rawHash) : '';
            const pageAttr = page ? ` data-page="${this._escapeHtml(page)}"` : '';
            const meta = source.meta
                ? `<span class="planets-module-link__meta">${this._escapeHtml(source.meta)}</span>`
                : '';
            return `<a class="planets-module-link${source.meta ? ' planets-module-link--planned' : ''}" href="${href}"${pageAttr}><span>${label}</span>${meta}</a>`;
        },

        _pageFromHashTarget(hashTarget, router) {
            if (!hashTarget) return '';
            const activeRouter = router || window.Router || (typeof Router !== 'undefined' ? Router : null);
            if (this._isFrontierAnchor(hashTarget, activeRouter)) {
                return activeRouter && typeof activeRouter._pageForFrontierAnchor === 'function'
                    ? activeRouter._pageForFrontierAnchor(hashTarget)
                    : 'frontier';
            }
            return hashTarget.split('/')[0];
        },

        _isFrontierAnchor(hashTarget, router) {
            if (!hashTarget || !hashTarget.startsWith('frontier-')) return false;
            const activeRouter = router || window.Router || (typeof Router !== 'undefined' ? Router : null);
            if (activeRouter && typeof activeRouter._pageForFrontierAnchor === 'function') {
                return !!activeRouter._pageForFrontierAnchor(hashTarget);
            }
            return /^frontier-(frontier|cosmos|engineering|datascience|infotech|materials|humanities)-/.test(hashTarget);
        },

        _escapeHtml(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        resetGalaxyView() {
            this.activeGalaxy = null;
            this.galaxyButtons.forEach(btn => btn.classList.remove('is-selected'));
            if (this.stage) this.stage.classList.remove('has-open-menu');
            if (this.menu) this.menu.classList.remove('is-open');
        },

        _seedGalaxyParticles() {
            this.root.querySelectorAll('.planets-cluster-dot').forEach(dot => dot.remove());
            this.root.querySelectorAll('[data-particles]').forEach((disc, discIndex) => {
                const isCode = disc.dataset.particles === 'codespace';
                const isFrontier = disc.dataset.particles === 'frontier';
                const count = isCode ? 64 : isFrontier ? 58 : 78;
                for (let i = 0; i < count; i += 1) {
                    const dot = document.createElement('span');
                    dot.className = 'planets-cluster-dot';
                    const angle = (i / count) * 360 + (Math.random() * 22 - 11);
                    const radius = 14 + Math.pow(i / count, 0.72) * 64 + Math.random() * 10;
                    const size = 1 + Math.random() * (isCode ? 3.4 : isFrontier ? 3 : 2.7);
                    const palette = isFrontier
                        ? ['#f2c86b', '#ff9f6e', '#b8f1ff', '#edf6ff']
                        : isCode
                        ? ['#67f2ac', '#65e4f0', '#f2c86b', '#edf6ff']
                        : ['#78b8ff', '#65e4f0', '#edf6ff', '#9fd0ff'];
                    dot.style.setProperty('--a', `${angle + discIndex * 8}deg`);
                    dot.style.setProperty('--r', `${radius}px`);
                    dot.style.setProperty('--s', `${size}px`);
                    dot.style.setProperty('--c', palette[Math.floor(Math.random() * palette.length)]);
                    dot.style.setProperty('--o', `${0.36 + Math.random() * 0.62}`);
                    disc.appendChild(dot);
                }
            });
        },

        _animateGalaxies(time) {
            if (!this.stage) return;
            const rect = this.stage.getBoundingClientRect();
            const responsive = Math.max(0.56, Math.min(1, rect.width / 820, rect.height / 650));

            this.galaxyButtons.forEach(button => {
                const config = GALAXIES[button.dataset.galaxy].orbit;
                const drift = this.reduceMotion ? 0 : Math.sin(time * config.speed * 18 + config.phase) * 0.08 * config.dir;
                const angle = config.phase + drift;
                let x = Math.cos(angle) * config.rx * responsive;
                let y = Math.sin(angle) * config.ry * responsive;
                let depth = (Math.sin(angle) + 1) / 2;
                let scale = 0.82 + depth * 0.22;

                if (this.activeGalaxy) {
                    const selected = this.activeGalaxy === button.dataset.galaxy;
                    const compact = rect.width < 620;
                    const inactiveButtons = this.galaxyButtons.filter(btn => btn.dataset.galaxy !== this.activeGalaxy);
                    const inactiveIndex = Math.max(0, inactiveButtons.indexOf(button));
                    const inactiveCenter = (inactiveButtons.length - 1) / 2;
                    const inactiveSpread = compact ? 132 : 140;
                    const float = Math.sin(time * 0.0011 + (selected ? 0 : 2.4)) * (compact ? 5 : 8);
                    x = (selected ? (compact ? -34 : -120) : (compact ? 82 : 190)) * responsive;
                    y = selected
                        ? (compact ? -118 : -100) * responsive + float
                        : (compact ? 48 : 92) * responsive + (inactiveIndex - inactiveCenter) * inactiveSpread + float;
                    depth = selected ? 0.92 : 0.22;
                    scale = selected ? (compact ? 0.98 : 1.08) : (compact ? 0.70 : 0.74);
                }

                button.style.transform = `translate(calc(-50% + ${x.toFixed(2)}px), calc(-50% + ${y.toFixed(2)}px)) scale(${scale.toFixed(3)})`;
                button.style.zIndex = String(10 + Math.round(depth * 10));
            });

            if (!this.reduceMotion) this.galaxyRafId = requestAnimationFrame(this._galaxyMotionHandler);
        },

        _onMouseMove(event) {
            if (!this.atlas) return;
            const mx = (event.clientX / window.innerWidth - 0.5) * 56;
            const my = (event.clientY / window.innerHeight - 0.5) * 46;
            this.atlas.style.setProperty('--mouse-x', `${mx}px`);
            this.atlas.style.setProperty('--mouse-y', `${my}px`);
        },

        _onResize() {
            if (!this.canvas || !this.ctx) return;
            this.dpr = Math.min(window.devicePixelRatio || 1, 2);
            this.width = window.innerWidth;
            this.height = window.innerHeight;
            this.canvas.width = Math.round(this.width * this.dpr);
            this.canvas.height = Math.round(this.height * this.dpr);
            this.canvas.style.width = `${this.width}px`;
            this.canvas.style.height = `${this.height}px`;
            this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

            const starCount = this.width < 720 ? 150 : 260;
            this.stars = Array.from({ length: starCount }, () => ({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                z: Math.random(),
                r: 0.4 + Math.random() * 1.7,
                a: 0.18 + Math.random() * 0.8,
                drift: 0.05 + Math.random() * 0.22
            }));

            this.filaments = Array.from({ length: 9 }, () => ({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                radius: 180 + Math.random() * 360,
                hue: Math.random() > 0.45 ? 'blue' : 'green',
                alpha: 0.02 + Math.random() * 0.035
            }));
        },

        _drawBackground(time) {
            const ctx = this.ctx;
            if (!ctx) return;
            ctx.clearRect(0, 0, this.width, this.height);
            const bg = ctx.createLinearGradient(0, 0, this.width, this.height);
            bg.addColorStop(0, '#05080d');
            bg.addColorStop(0.52, '#081321');
            bg.addColorStop(1, '#05080d');
            ctx.fillStyle = bg;
            ctx.fillRect(0, 0, this.width, this.height);

            this.filaments.forEach(field => {
                const pulse = this.reduceMotion ? 1 : 0.85 + Math.sin(time * 0.00015 + field.x) * 0.15;
                const grad = ctx.createRadialGradient(field.x, field.y, 0, field.x, field.y, field.radius);
                const color = field.hue === 'green' ? '103, 242, 172' : '120, 184, 255';
                grad.addColorStop(0, `rgba(${color}, ${field.alpha * pulse})`);
                grad.addColorStop(1, `rgba(${color}, 0)`);
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(field.x, field.y, field.radius, 0, Math.PI * 2);
                ctx.fill();
            });

            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            this.stars.forEach(star => {
                if (!this.reduceMotion) {
                    star.y += star.drift * (0.4 + star.z);
                    star.x += Math.sin(time * 0.00008 + star.y) * 0.05;
                    if (star.y > this.height + 8) {
                        star.y = -8;
                        star.x = Math.random() * this.width;
                    }
                }

                ctx.globalAlpha = star.a;
                ctx.fillStyle = star.z > 0.72 ? '#dff3ff' : '#8fb8df';
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.restore();

            ctx.save();
            ctx.strokeStyle = 'rgba(160, 196, 240, 0.22)';
            ctx.lineWidth = 1;
            for (let i = 0; i < this.stars.length; i += 1) {
                const a = this.stars[i];
                for (let j = i + 1; j < Math.min(i + 8, this.stars.length); j += 1) {
                    const b = this.stars[j];
                    const dx = a.x - b.x;
                    const dy = a.y - b.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 82) {
                        ctx.globalAlpha = (1 - dist / 82) * 0.16;
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.stroke();
                    }
                }
            }
            ctx.restore();
        },

        _loop(time) {
            this._drawBackground(time || 0);
            if (!this.reduceMotion) this.rafId = requestAnimationFrame(this._loopHandler);
        }
    };

    window.initPlanets = function initPlanets() { window.PlanetsView.init(); };
    window.destroyPlanets = function destroyPlanets() { window.PlanetsView.destroy(); };
})();
