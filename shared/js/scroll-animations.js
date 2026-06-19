// ===== Scroll Animations (GSAP ScrollTrigger) =====

function initScrollAnimations() {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;
    gsap.registerPlugin(ScrollTrigger);
}

function initPageScrollAnimations(page) {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;

    // Kill existing triggers for this page to avoid duplicates
    const pageEl = document.getElementById(`page-${page}`);
    if (!pageEl) return;

    // Staggered card reveal
    const cards = pageEl.querySelectorAll('.bento-grid .card');
    if (cards.length) {
        gsap.fromTo(cards,
            { y: 30, opacity: 0 },
            {
                y: 0,
                opacity: 1,
                duration: 0.5,
                ease: 'power3.out',
                stagger: {
                    each: 0.08,
                    from: 'start'
                },
                scrollTrigger: {
                    trigger: pageEl.querySelector('.bento-grid'),
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                }
            }
        );
    }

    // Section headers
    const headers = pageEl.querySelectorAll('.section-header');
    headers.forEach(header => {
        gsap.fromTo(header,
            { y: 20, opacity: 0 },
            {
                y: 0, opacity: 1,
                duration: 0.6,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: header,
                    start: 'top 82%',
                    toggleActions: 'play none none none'
                }
            }
        );
    });

    // Demo sections
    const demos = pageEl.querySelectorAll('.demo-section');
    demos.forEach(demo => {
        gsap.fromTo(demo,
            { y: 30, opacity: 0 },
            {
                y: 0, opacity: 1,
                duration: 0.7,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: demo,
                    start: 'top 80%',
                    toggleActions: 'play none none none'
                }
            }
        );
    });

    // Video sections
    const videos = pageEl.querySelectorAll('.video-section');
    videos.forEach(vid => {
        gsap.fromTo(vid,
            { y: 25, opacity: 0 },
            {
                y: 0, opacity: 1,
                duration: 0.6,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: vid,
                    start: 'top 80%',
                    toggleActions: 'play none none none'
                }
            }
        );
    });

    // Steps panels
    const steps = pageEl.querySelectorAll('.steps-panel');
    steps.forEach(step => {
        gsap.fromTo(step,
            { y: 20, opacity: 0 },
            {
                y: 0, opacity: 1,
                duration: 0.6,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: step,
                    start: 'top 82%',
                    toggleActions: 'play none none none'
                }
            }
        );
    });

    // Page hero text — NOTE: hero elements are already animated by Router.animatePageContent()
    // on page transition. Running a second fromTo here caused triple-flicker (appear→hide→appear).
    // Hero animation is intentionally omitted here to avoid the conflict.

    // Page hero visual — same reason as above, handled by animatePageContent.
}

const HeroVisualRuntime = {
    frames: Object.create(null)
};

function requestHeroFrame(page, callback) {
    HeroVisualRuntime.frames[page] = requestAnimationFrame(callback);
}

function destroyHeroVisual(page) {
    if (!page) return;
    const frame = HeroVisualRuntime.frames[page];
    if (frame) cancelAnimationFrame(frame);
    delete HeroVisualRuntime.frames[page];

    const canvas = document.getElementById(`hero-canvas-${page}`);
    if (canvas) {
        delete canvas.dataset.initialized;
        if (typeof canvas.getContext === 'function') {
            const ctx = canvas.getContext('2d');
            if (ctx) ctx.clearRect(0, 0, canvas.width || canvas.clientWidth, canvas.height || canvas.clientHeight);
        }
    }
}

function destroyAllHeroVisuals() {
    Object.keys(HeroVisualRuntime.frames).forEach((page) => destroyHeroVisual(page));
}

// Hero visual animations (SVG/Canvas decorations)
function initHeroVisual(page) {
    const canvas = document.getElementById(`hero-canvas-${page}`);
    if (!canvas || canvas.dataset.initialized) return;
    if (typeof canvas.getContext !== 'function') {
        canvas.dataset.initialized = 'unsupported';
        return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        canvas.dataset.initialized = 'unsupported';
        return;
    }
    canvas.dataset.initialized = 'true';
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    // Use offsetWidth fallback if getBoundingClientRect returns 0 (page not yet painted)
    const w = rect.width || canvas.offsetWidth || (canvas.parentElement && canvas.parentElement.offsetWidth) || 400;
    const h = rect.height || canvas.offsetHeight || (canvas.parentElement && canvas.parentElement.offsetHeight) || 220;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const visuals = {
        mathematics: () => drawLissajous(page, ctx, w, h),
        physics: () => drawWaveInterference(page, ctx, w, h),
        chemistry: () => drawMolecule(page, ctx, w, h),
        algorithms: () => drawSortBars(page, ctx, w, h),
        biology: () => drawDNAHelix(page, ctx, w, h),
        cosmos: () => drawEarthOrbit(page, ctx, w, h),
        datascience: () => drawDataRegression(page, ctx, w, h),
        infotech: () => drawNetworkFlow(page, ctx, w, h),
        materials: () => drawMaterialLattice(page, ctx, w, h),
        humanities: () => drawTextConstellation(page, ctx, w, h),
        engineering: () => drawEngineeringTruss(page, ctx, w, h)
    };

    if (visuals[page]) visuals[page]();
}

// ── Lissajous curve for Mathematics ──
function drawLissajous(page, ctx, w, h) {
    const cx = w / 2, cy = h / 2;
    const scale = Math.min(w, h) * 0.35;
    let t = 0;

    function draw() {
        ctx.clearRect(0, 0, w, h);
        ctx.beginPath();
        for (let i = 0; i <= 600; i++) {
            const angle = (i / 600) * Math.PI * 2 * 3;
            const x = cx + Math.sin(angle * 3 + t) * scale;
            const y = cy + Math.sin(angle * 2) * scale * 0.8;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = 'rgba(91,141,206,0.25)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Dot at current position
        const dotX = cx + Math.sin(t * 3 + t) * scale;
        const dotY = cy + Math.sin(t * 2) * scale * 0.8;
        ctx.beginPath();
        ctx.arc(dotX, dotY, 3, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(91,141,206,0.5)';
        ctx.fill();

        t += 0.008;
        requestHeroFrame(page, draw);
    }
    draw();
}

// ── Wave interference for Physics ──
function drawWaveInterference(page, ctx, w, h) {
    let t = 0;

    function draw() {
        ctx.clearRect(0, 0, w, h);

        for (let layer = 0; layer < 3; layer++) {
            ctx.beginPath();
            const freq = 0.02 + layer * 0.008;
            const amp = 25 - layer * 5;
            const yOffset = h / 2 + (layer - 1) * 40;
            const phase = t * (1 + layer * 0.3);

            for (let x = 0; x < w; x++) {
                const y = yOffset +
                    Math.sin(x * freq + phase) * amp +
                    Math.sin(x * freq * 1.7 + phase * 0.6) * amp * 0.5;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }

            ctx.strokeStyle = `rgba(139,111,192,${0.15 + layer * 0.05})`;
            ctx.lineWidth = 1.2;
            ctx.stroke();
        }

        t += 0.025;
        requestHeroFrame(page, draw);
    }
    draw();
}

// ── Hexagonal molecule for Chemistry ──
function drawMolecule(page, ctx, w, h) {
    const cx = w / 2, cy = h / 2;
    const r = Math.min(w, h) * 0.12;
    let t = 0;

    const nodes = [];
    // Central hex ring
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        nodes.push({ x: Math.cos(angle) * r, y: Math.sin(angle) * r, ring: 0 });
    }
    // Outer nodes
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        nodes.push({ x: Math.cos(angle) * r * 2, y: Math.sin(angle) * r * 2, ring: 1 });
    }

    const bonds = [];
    for (let i = 0; i < 6; i++) {
        bonds.push([i, (i + 1) % 6]);
        bonds.push([i, i + 6]);
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const rot = t * 0.3;

        // Bonds
        bonds.forEach(([a, b]) => {
            const ax = cx + nodes[a].x * Math.cos(rot) - nodes[a].y * Math.sin(rot) * 0.3;
            const ay = cy + nodes[a].x * Math.sin(rot) * 0.3 + nodes[a].y * Math.cos(rot);
            const bx = cx + nodes[b].x * Math.cos(rot) - nodes[b].y * Math.sin(rot) * 0.3;
            const by = cy + nodes[b].x * Math.sin(rot) * 0.3 + nodes[b].y * Math.cos(rot);

            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.strokeStyle = 'rgba(77,158,126,0.2)';
            ctx.lineWidth = 1.2;
            ctx.stroke();
        });

        // Nodes
        nodes.forEach((node, i) => {
            const nx = cx + node.x * Math.cos(rot) - node.y * Math.sin(rot) * 0.3;
            const ny = cy + node.x * Math.sin(rot) * 0.3 + node.y * Math.cos(rot);
            const radius = node.ring === 0 ? 4 : 3;

            ctx.beginPath();
            ctx.arc(nx, ny, radius, 0, Math.PI * 2);
            ctx.fillStyle = node.ring === 0 ? 'rgba(77,158,126,0.4)' : 'rgba(77,158,126,0.25)';
            ctx.fill();
        });

        t += 0.01;
        requestHeroFrame(page, draw);
    }
    draw();
}

// ── Decorative sort bars for Algorithms ──
function drawSortBars(page, ctx, w, h) {
    const barCount = 16;
    const barW = w / (barCount * 2);
    const heights = [];
    for (let i = 0; i < barCount; i++) {
        heights.push(0.2 + Math.random() * 0.8);
    }

    let t = 0;
    let swapI = 0;
    let swapTimer = 0;

    function draw() {
        ctx.clearRect(0, 0, w, h);

        // Slowly swap bars
        swapTimer++;
        if (swapTimer > 60) {
            swapTimer = 0;
            const a = swapI % barCount;
            const b = (swapI + 1) % barCount;
            if (heights[a] > heights[b]) {
                const tmp = heights[a];
                heights[a] = heights[b];
                heights[b] = tmp;
            }
            swapI++;
        }

        for (let i = 0; i < barCount; i++) {
            const x = (w / 2) - (barCount * barW) + i * barW * 2;
            const barH = heights[i] * h * 0.6;
            const y = h - barH - 10;

            ctx.fillStyle = `rgba(196,121,58,${0.15 + heights[i] * 0.2})`;
            ctx.fillRect(x, y, barW, barH);
        }

        t += 0.016;
        requestHeroFrame(page, draw);
    }
    draw();
}

window.initScrollAnimations = initScrollAnimations;
window.initPageScrollAnimations = initPageScrollAnimations;
window.initHeroVisual = initHeroVisual;
window.destroyHeroVisual = destroyHeroVisual;
window.destroyAllHeroVisuals = destroyAllHeroVisuals;

// ── DNA double helix for Biology ──
function drawDNAHelix(page, ctx, w, h) {
    let t = 0;
    const cx = w / 2;
    const amplitude = Math.min(w, h) * 0.18;
    const freq = 0.022;
    const baseColor1 = 'rgba(58,158,143,';
    const baseColor2 = 'rgba(77,200,170,';
    const bondColor = 'rgba(58,158,143,0.12)';

    function draw() {
        ctx.clearRect(0, 0, w, h);

        // Draw backbone strands
        for (let strand = 0; strand < 2; strand++) {
            const phase = strand * Math.PI;
            ctx.beginPath();
            for (let y = 0; y <= h; y += 2) {
                const x = cx + Math.sin(y * freq + t + phase) * amplitude;
                if (y === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            const alpha = 0.3 - strand * 0.08;
            ctx.strokeStyle = strand === 0 ? baseColor1 + alpha + ')' : baseColor2 + alpha + ')';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Draw base pair rungs
        const step = Math.PI / (freq * 8);
        for (let k = 0; k < 12; k++) {
            const y = ((k * step - t / freq) % h + h) % h;
            const x1 = cx + Math.sin(y * freq + t) * amplitude;
            const x2 = cx + Math.sin(y * freq + t + Math.PI) * amplitude;
            ctx.beginPath();
            ctx.moveTo(x1, y);
            ctx.lineTo(x2, y);
            ctx.strokeStyle = bondColor;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Nodes at each end
            [x1, x2].forEach((x, i) => {
                ctx.beginPath();
                ctx.arc(x, y, 2.5, 0, Math.PI * 2);
                ctx.fillStyle = i === 0 ? 'rgba(58,158,143,0.35)' : 'rgba(77,200,170,0.35)';
                ctx.fill();
            });
        }

        t += 0.012;
        requestHeroFrame(page, draw);
    }
    draw();
}

// Regression scatter and fit for Data Science
function drawDataRegression(page, ctx, w, h) {
    let t = 0;
    const points = [
        [0.12, 0.72], [0.23, 0.62], [0.34, 0.66], [0.45, 0.48],
        [0.56, 0.43], [0.66, 0.34], [0.78, 0.31], [0.88, 0.2]
    ];

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const pad = Math.min(w, h) * 0.17;
        const left = pad;
        const top = pad * 0.85;
        const width = w - pad * 2;
        const height = h - pad * 1.8;
        const pulse = 0.5 + Math.sin(t) * 0.5;

        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.11)';
        ctx.lineWidth = 1;
        ctx.strokeRect(left, top, width, height);

        ctx.strokeStyle = 'rgba(138,167,255,0.78)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(left + width * 0.08, top + height * (0.78 - pulse * 0.02));
        ctx.lineTo(left + width * 0.94, top + height * (0.18 + pulse * 0.02));
        ctx.stroke();

        points.forEach(([x, y], index) => {
            const px = left + x * width;
            const py = top + y * height;
            ctx.beginPath();
            ctx.arc(px, py, 4 + (index % 3) * 0.6, 0, Math.PI * 2);
            ctx.fillStyle = index % 2 ? 'rgba(67,214,176,0.86)' : 'rgba(216,220,230,0.86)';
            ctx.fill();
        });

        for (let i = 0; i < 4; i += 1) {
            const x = left + width * (0.18 + i * 0.19);
            const y1 = top + height * (0.7 - i * 0.12);
            const y2 = top + height * (0.63 - i * 0.12 + pulse * 0.03);
            ctx.strokeStyle = 'rgba(242,200,107,0.32)';
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(x, y1);
            ctx.lineTo(x, y2);
            ctx.stroke();
        }

        ctx.restore();
        t += 0.018;
        requestHeroFrame(page, draw);
    }

    draw();
}

// Packet route and layered envelope for Information Technology
function drawNetworkFlow(page, ctx, w, h) {
    let t = 0;
    const nodes = [
        { x: 0.14, y: 0.62, r: 12 },
        { x: 0.32, y: 0.42, r: 9 },
        { x: 0.52, y: 0.58, r: 10 },
        { x: 0.72, y: 0.38, r: 9 },
        { x: 0.88, y: 0.56, r: 12 }
    ];

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const packetPhase = (t % 1) * (nodes.length - 1);
        const segment = Math.min(nodes.length - 2, Math.floor(packetPhase));
        const local = packetPhase - segment;
        const a = nodes[segment];
        const b = nodes[segment + 1];
        const px = (a.x + (b.x - a.x) * local) * w;
        const py = (a.y + (b.y - a.y) * local) * h;

        ctx.save();
        ctx.strokeStyle = 'rgba(94,224,216,0.22)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        nodes.forEach((node, index) => {
            const x = node.x * w;
            const y = node.y * h;
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        nodes.forEach((node, index) => {
            const x = node.x * w;
            const y = node.y * h;
            ctx.beginPath();
            ctx.arc(x, y, node.r + 8 + Math.sin(t * 4 + index) * 1.5, 0, Math.PI * 2);
            ctx.fillStyle = index === 0 || index === nodes.length - 1
                ? 'rgba(94,224,216,0.14)'
                : 'rgba(242,200,107,0.10)';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(x, y, node.r, 0, Math.PI * 2);
            ctx.fillStyle = index === 0 || index === nodes.length - 1
                ? 'rgba(94,224,216,0.72)'
                : 'rgba(242,200,107,0.62)';
            ctx.fill();
        });

        const stackX = w * 0.18;
        const stackY = h * 0.16;
        ['HTTP', 'TCP', 'IPv6', 'LINK'].forEach((label, index) => {
            const width = w * 0.2 + index * 16;
            const height = 24;
            const x = stackX - index * 8;
            const y = stackY + index * 30;
            ctx.beginPath();
            ctx.roundRect(x, y, width, height, 6);
            ctx.fillStyle = index % 2 ? 'rgba(94,224,216,0.13)' : 'rgba(138,167,255,0.12)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(238,241,248,0.16)';
            ctx.stroke();
            ctx.fillStyle = 'rgba(238,241,248,0.62)';
            ctx.font = `11px ${typeof CF !== 'undefined' ? CF.mono : 'monospace'}`;
            ctx.fillText(label, x + 10, y + 16);
        });

        ctx.beginPath();
        ctx.roundRect(px - 18, py - 10, 36, 20, 6);
        ctx.fillStyle = 'rgba(94,224,216,0.86)';
        ctx.fill();
        ctx.fillStyle = 'rgba(8,9,14,0.86)';
        ctx.font = `700 10px ${typeof CF !== 'undefined' ? CF.mono : 'monospace'}`;
        ctx.textAlign = 'center';
        ctx.fillText('PKT', px, py + 4);
        ctx.restore();

        t += 0.012;
        requestHeroFrame(page, draw);
    }

    draw();
}

// Crystal lattice and grains for Materials
function drawMaterialLattice(page, ctx, w, h) {
    const cx = w / 2;
    const cy = h / 2;
    let t = 0;
    const grains = Array.from({ length: 34 }, (_, i) => ({
        a: (i / 34) * Math.PI * 2,
        r: 24 + (i % 7) * 15 + Math.floor(i / 7) * 8,
        s: 2.4 + (i % 5) * 0.8
    }));

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const radius = Math.min(w, h) * 0.28;
        const spacing = Math.max(20, Math.min(w, h) * 0.095);
        const tilt = Math.sin(t * 0.55) * 0.08;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-0.18 + tilt);

        ctx.strokeStyle = 'rgba(126,215,193,0.20)';
        ctx.lineWidth = 1.1;
        for (let row = -3; row <= 3; row += 1) {
            ctx.beginPath();
            let started = false;
            for (let col = -3; col <= 3; col += 1) {
                const x = col * spacing + (row % 2) * spacing * 0.5;
                const y = row * spacing * 0.72;
                if (Math.hypot(x, y) > radius * 1.08) continue;
                if (!started) {
                    ctx.moveTo(x, y);
                    started = true;
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();
        }

        for (let row = -3; row <= 3; row += 1) {
            for (let col = -3; col <= 3; col += 1) {
                const x = col * spacing + (row % 2) * spacing * 0.5;
                const y = row * spacing * 0.72;
                if (Math.hypot(x, y) > radius * 1.08) continue;
                const pulse = 1 + Math.sin(t * 1.3 + row + col) * 0.08;
                ctx.beginPath();
                ctx.arc(x, y, 4.8 * pulse, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(224,181,106,0.62)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(126,215,193,0.22)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
        }
        ctx.restore();

        ctx.save();
        grains.forEach(grain => {
            const x = cx + Math.cos(grain.a + t * 0.04) * grain.r;
            const y = cy + Math.sin(grain.a + t * 0.04) * grain.r * 0.68;
            ctx.beginPath();
            ctx.arc(x, y, grain.s, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(138,167,255,${0.12 + (grain.s / 8) * 0.22})`;
            ctx.fill();
        });
        ctx.strokeStyle = 'rgba(224,181,106,0.28)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (let i = 0; i <= 6; i += 1) {
            const a = (i / 6) * Math.PI * 2 + t * 0.08;
            const x = cx + Math.cos(a) * radius;
            const y = cy + Math.sin(a) * radius * 0.72;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
        ctx.restore();

        t += 0.018;
        requestHeroFrame(page, draw);
    }

    draw();
}

// Term nodes and context arcs for Humanities
function drawTextConstellation(page, ctx, w, h) {
    const terms = ['文本', '语境', '词项', '史料', '提问', '证据', '阅读', '关系'];
    const cx = w / 2;
    const cy = h / 2;
    let t = 0;

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const radius = Math.min(w, h) * 0.31;
        const nodes = terms.map((term, index) => {
            const angle = -Math.PI / 2 + (index / terms.length) * Math.PI * 2 + Math.sin(t * 0.3) * 0.05;
            return {
                term,
                x: cx + Math.cos(angle) * radius * (0.72 + (index % 3) * 0.08),
                y: cy + Math.sin(angle) * radius * 0.62,
                r: 3.8 + (index % 4) * 0.55
            };
        });

        ctx.save();
        ctx.strokeStyle = 'rgba(126,215,193,0.22)';
        ctx.lineWidth = 1.1;
        for (let i = 0; i < nodes.length; i += 1) {
            const a = nodes[i];
            const b = nodes[(i + 2) % nodes.length];
            const midX = (a.x + b.x) / 2;
            const midY = (a.y + b.y) / 2 - 24 - (i % 3) * 9;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.quadraticCurveTo(midX, midY, b.x, b.y);
            ctx.stroke();
        }

        ctx.strokeStyle = 'rgba(224,181,106,0.18)';
        for (let line = 0; line < 6; line += 1) {
            const y = cy - radius * 0.65 + line * radius * 0.25 + Math.sin(t + line) * 2;
            ctx.beginPath();
            ctx.moveTo(cx - radius * 1.2, y);
            ctx.lineTo(cx + radius * 1.2, y);
            ctx.stroke();
        }

        nodes.forEach((node, index) => {
            const pulse = 1 + Math.sin(t * 1.2 + index) * 0.12;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.r * pulse + 3.5, 0, Math.PI * 2);
            ctx.fillStyle = index % 2 ? 'rgba(126,215,193,0.16)' : 'rgba(224,181,106,0.13)';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.r * pulse, 0, Math.PI * 2);
            ctx.fillStyle = index % 2 ? 'rgba(126,215,193,0.78)' : 'rgba(224,181,106,0.74)';
            ctx.fill();
        });

        ctx.fillStyle = 'rgba(238,241,248,0.18)';
        ctx.font = `12px ${typeof CF !== 'undefined' ? CF.sans : 'sans-serif'}`;
        ctx.textAlign = 'center';
        nodes.slice(0, 5).forEach((node, index) => {
            ctx.fillText(node.term, node.x, node.y - 13 - (index % 2) * 5);
        });
        ctx.restore();

        t += 0.018;
        requestHeroFrame(page, draw);
    }

    draw();
}

// Earth orbit and axial tilt for Earth & Space Science
function drawEarthOrbit(page, ctx, w, h) {
    let t = 0;
    const cx = w / 2;
    const cy = h / 2;
    const rx = Math.min(w, h) * 0.34;
    const ry = Math.min(w, h) * 0.2;

    function draw() {
        ctx.clearRect(0, 0, w, h);
        ctx.save();
        ctx.strokeStyle = 'rgba(116,185,255,0.18)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.stroke();

        const sunGlow = ctx.createRadialGradient(cx, cy, 6, cx, cy, 58);
        sunGlow.addColorStop(0, 'rgba(242,200,107,0.72)');
        sunGlow.addColorStop(0.45, 'rgba(242,200,107,0.16)');
        sunGlow.addColorStop(1, 'rgba(242,200,107,0)');
        ctx.fillStyle = sunGlow;
        ctx.beginPath();
        ctx.arc(cx, cy, 58, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(242,200,107,0.92)';
        ctx.beginPath();
        ctx.arc(cx, cy, 15, 0, Math.PI * 2);
        ctx.fill();

        const angle = t;
        const ex = cx + Math.cos(angle) * rx;
        const ey = cy + Math.sin(angle) * ry;
        ctx.fillStyle = 'rgba(116,185,255,0.92)';
        ctx.beginPath();
        ctx.arc(ex, ey, 18, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(216,220,230,0.68)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(ex - 9, ey + 24);
        ctx.lineTo(ex + 9, ey - 24);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(242,200,107,0.22)';
        ctx.lineWidth = 1;
        for (let i = -2; i <= 2; i += 1) {
            ctx.beginPath();
            ctx.moveTo(cx + 24, cy + i * 10);
            ctx.lineTo(ex - 18, ey + i * 5);
            ctx.stroke();
        }

        ctx.restore();
        t += 0.012;
        requestHeroFrame(page, draw);
    }

    draw();
}

// Truss force path for Engineering
function drawEngineeringTruss(page, ctx, w, h) {
    let t = 0;
    const colorSteel = 'rgba(216,220,230,0.34)';
    const colorCompression = 'rgba(216,163,72,0.42)';
    const colorTension = 'rgba(79,168,163,0.38)';
    const colorLoad = 'rgba(184,84,80,0.48)';

    function point(x, y) {
        return {
            x: w * (0.12 + x * 0.76),
            y: h * (0.68 - y * 0.38)
        };
    }

    function drawMember(a, b, color, width) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.lineCap = 'round';
        ctx.stroke();
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const pulse = 0.5 + Math.sin(t) * 0.5;
        const bottom = [0, 0.25, 0.5, 0.75, 1].map(x => point(x, 0));
        const top = [0.125, 0.375, 0.625, 0.875].map(x => point(x, 1));

        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < bottom.length - 1; i += 1) {
            drawMember(bottom[i], bottom[i + 1], colorSteel, 2.4);
        }
        for (let i = 0; i < top.length - 1; i += 1) {
            drawMember(top[i], top[i + 1], colorCompression, 3.2 + pulse * 1.6);
        }
        top.forEach((node, i) => {
            drawMember(bottom[i], node, i % 2 ? colorCompression : colorTension, 2.4 + pulse);
            drawMember(node, bottom[i + 1], i % 2 ? colorTension : colorCompression, 2.4 + pulse);
        });

        [...bottom, ...top].forEach((node, index) => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, index < bottom.length ? 3.6 : 3, 0, Math.PI * 2);
            ctx.fillStyle = index < bottom.length ? 'rgba(216,220,230,0.62)' : 'rgba(216,163,72,0.58)';
            ctx.fill();
        });

        const load = bottom[2];
        ctx.strokeStyle = colorLoad;
        ctx.fillStyle = colorLoad;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(load.x, load.y - h * (0.28 + pulse * 0.04));
        ctx.lineTo(load.x, load.y - 16);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(load.x, load.y - 8);
        ctx.lineTo(load.x - 8, load.y - 22);
        ctx.lineTo(load.x + 8, load.y - 22);
        ctx.closePath();
        ctx.fill();

        ctx.restore();
        t += 0.024;
        requestHeroFrame(page, draw);
    }

    draw();
}
