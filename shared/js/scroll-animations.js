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

// Hero visual animations (SVG/Canvas decorations)
function initHeroVisual(page) {
    const canvas = document.getElementById(`hero-canvas-${page}`);
    if (!canvas || canvas.dataset.initialized) return;
    canvas.dataset.initialized = 'true';

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    // Use offsetWidth fallback if getBoundingClientRect returns 0 (page not yet painted)
    const w = rect.width || canvas.offsetWidth || (canvas.parentElement && canvas.parentElement.offsetWidth) || 400;
    const h = rect.height || canvas.offsetHeight || (canvas.parentElement && canvas.parentElement.offsetHeight) || 220;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const visuals = {
        mathematics: () => drawLissajous(ctx, w, h),
        physics: () => drawWaveInterference(ctx, w, h),
        chemistry: () => drawMolecule(ctx, w, h),
        algorithms: () => drawSortBars(ctx, w, h),
        biology: () => drawDNAHelix(ctx, w, h)
    };

    if (visuals[page]) visuals[page]();
}

// ── Lissajous curve for Mathematics ──
function drawLissajous(ctx, w, h) {
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
        requestAnimationFrame(draw);
    }
    draw();
}

// ── Wave interference for Physics ──
function drawWaveInterference(ctx, w, h) {
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
        requestAnimationFrame(draw);
    }
    draw();
}

// ── Hexagonal molecule for Chemistry ──
function drawMolecule(ctx, w, h) {
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
        requestAnimationFrame(draw);
    }
    draw();
}

// ── Decorative sort bars for Algorithms ──
function drawSortBars(ctx, w, h) {
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
        requestAnimationFrame(draw);
    }
    draw();
}

window.initScrollAnimations = initScrollAnimations;
window.initPageScrollAnimations = initPageScrollAnimations;
window.initHeroVisual = initHeroVisual;

// ── DNA double helix for Biology ──
function drawDNAHelix(ctx, w, h) {
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
        requestAnimationFrame(draw);
    }
    draw();
}
