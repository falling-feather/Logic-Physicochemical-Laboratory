// ===== Chemical Reactions Visualization =====
const ChemReaction = {
    canvas: null,
    ctx: null,
    W: 0, H: 0,
    particles: [],
    animId: null,
    running: false,
    progress: 0, // 0 → 1
    speed: 1,
    currentReaction: null,

    atomColors: {
        H: '#ffffff', O: '#FF0D0D', C: '#555555', N: '#3050F8',
        Na: '#AB5CF2', Cl: '#1FF01F', Fe: '#E06633', S: '#FFFF30',
        Ca: '#3DFF00', Cu: '#C88033', Mg: '#8AFF00', Al: '#BFA6A6'
    },

    reactions: {
        combustion: {
            name: '甲烷燃烧',
            equation: 'CH₄ + 2O₂ → CO₂ + 2H₂O',
            desc: '放热反应，天然气燃烧的主要过程',
            type: '放热',
            energy: -890,
            unit: 'kJ/mol',
            reactants: [
                { formula: 'CH₄', atoms: [
                    { el: 'C', x: 0, y: 0 },
                    { el: 'H', x: -0.7, y: -0.5 }, { el: 'H', x: 0.7, y: -0.5 },
                    { el: 'H', x: -0.7, y: 0.5 }, { el: 'H', x: 0.7, y: 0.5 }
                ]},
                { formula: 'O₂', atoms: [
                    { el: 'O', x: -0.4, y: 0 }, { el: 'O', x: 0.4, y: 0 }
                ], count: 2 }
            ],
            products: [
                { formula: 'CO₂', atoms: [
                    { el: 'C', x: 0, y: 0 }, { el: 'O', x: -0.8, y: 0 }, { el: 'O', x: 0.8, y: 0 }
                ]},
                { formula: 'H₂O', atoms: [
                    { el: 'O', x: 0, y: 0 }, { el: 'H', x: -0.6, y: 0.4 }, { el: 'H', x: 0.6, y: 0.4 }
                ], count: 2 }
            ]
        },
        synthesis: {
            name: '合成氨',
            equation: 'N₂ + 3H₂ → 2NH₃',
            desc: '哈伯法，工业上最重要的化学反应之一',
            type: '放热',
            energy: -92,
            unit: 'kJ/mol',
            reactants: [
                { formula: 'N₂', atoms: [
                    { el: 'N', x: -0.35, y: 0 }, { el: 'N', x: 0.35, y: 0 }
                ]},
                { formula: 'H₂', atoms: [
                    { el: 'H', x: -0.25, y: 0 }, { el: 'H', x: 0.25, y: 0 }
                ], count: 3 }
            ],
            products: [
                { formula: 'NH₃', atoms: [
                    { el: 'N', x: 0, y: -0.2 },
                    { el: 'H', x: 0.6, y: 0.3 }, { el: 'H', x: -0.6, y: 0.3 }, { el: 'H', x: 0, y: 0.7 }
                ], count: 2 }
            ]
        },
        neutralization: {
            name: '酸碱中和',
            equation: 'HCl + NaOH → NaCl + H₂O',
            desc: '强酸强碱中和反应，生成盐和水',
            type: '放热',
            energy: -57,
            unit: 'kJ/mol',
            reactants: [
                { formula: 'HCl', atoms: [
                    { el: 'H', x: -0.4, y: 0 }, { el: 'Cl', x: 0.4, y: 0 }
                ]},
                { formula: 'NaOH', atoms: [
                    { el: 'Na', x: -0.6, y: 0 }, { el: 'O', x: 0, y: 0 }, { el: 'H', x: 0.5, y: 0.3 }
                ]}
            ],
            products: [
                { formula: 'NaCl', atoms: [
                    { el: 'Na', x: -0.4, y: 0 }, { el: 'Cl', x: 0.4, y: 0 }
                ]},
                { formula: 'H₂O', atoms: [
                    { el: 'O', x: 0, y: 0 }, { el: 'H', x: -0.5, y: 0.35 }, { el: 'H', x: 0.5, y: 0.35 }
                ]}
            ]
        },
        decomposition: {
            name: '碳酸钙分解',
            equation: 'CaCO₃ → CaO + CO₂',
            desc: '吸热反应，石灰石高温煅烧制生石灰',
            type: '吸热',
            energy: 178,
            unit: 'kJ/mol',
            reactants: [
                { formula: 'CaCO₃', atoms: [
                    { el: 'Ca', x: -0.6, y: 0 }, { el: 'C', x: 0.2, y: 0 },
                    { el: 'O', x: 0.9, y: 0 }, { el: 'O', x: 0.2, y: 0.6 }, { el: 'O', x: 0.2, y: -0.6 }
                ]}
            ],
            products: [
                { formula: 'CaO', atoms: [
                    { el: 'Ca', x: -0.4, y: 0 }, { el: 'O', x: 0.4, y: 0 }
                ]},
                { formula: 'CO₂', atoms: [
                    { el: 'C', x: 0, y: 0 }, { el: 'O', x: -0.7, y: 0 }, { el: 'O', x: 0.7, y: 0 }
                ]}
            ]
        },
        redox: {
            name: '铁与硫酸铜置换',
            equation: 'Fe + CuSO₄ → FeSO₄ + Cu',
            desc: '金属置换反应，铁比铜更活泼',
            type: '放热',
            energy: -153,
            unit: 'kJ/mol',
            reactants: [
                { formula: 'Fe', atoms: [
                    { el: 'Fe', x: 0, y: 0 }
                ]},
                { formula: 'CuSO₄', atoms: [
                    { el: 'Cu', x: -0.5, y: 0 }, { el: 'S', x: 0.3, y: 0 },
                    { el: 'O', x: 0.9, y: 0 }, { el: 'O', x: 0.3, y: 0.6 }
                ]}
            ],
            products: [
                { formula: 'FeSO₄', atoms: [
                    { el: 'Fe', x: -0.5, y: 0 }, { el: 'S', x: 0.3, y: 0 },
                    { el: 'O', x: 0.9, y: 0 }, { el: 'O', x: 0.3, y: 0.6 }
                ]},
                { formula: 'Cu', atoms: [
                    { el: 'Cu', x: 0, y: 0 }
                ]}
            ]
        }
    },

    init() {
        this.canvas = document.getElementById('rxn-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.loadReaction('combustion');
        this.bindControls();
        window.addEventListener('resize', () => { this.resize(); this.draw(); });
    },

    resize() {
        const wrap = this.canvas.parentElement;
        const w = wrap.clientWidth;
        const h = Math.min(w * 0.55, 360);
        this.canvas.width = w * devicePixelRatio;
        this.canvas.height = h * devicePixelRatio;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindControls() {
        document.querySelectorAll('.rxn-select-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.rxn-select-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.loadReaction(btn.dataset.rxn);
            });
        });

        const playBtn = document.getElementById('rxn-play');
        if (playBtn) playBtn.addEventListener('click', () => this.play());

        const resetBtn = document.getElementById('rxn-reset');
        if (resetBtn) resetBtn.addEventListener('click', () => this.reset());

        const speedSlider = document.getElementById('rxn-speed');
        if (speedSlider) speedSlider.addEventListener('input', () => {
            this.speed = parseFloat(speedSlider.value);
        });
    },

    loadReaction(key) {
        this.currentReaction = this.reactions[key];
        if (!this.currentReaction) return;
        this.stop();
        this.progress = 0;
        this.buildParticles();
        this.draw();
        this.updateInfo();
        this.updateEnergyBar();
    },

    buildParticles() {
        this.particles = [];
        const rxn = this.currentReaction;
        const scale = 40;
        const midX = this.W / 2;
        const midY = this.H / 2;

        // Place reactants on the left
        let rx = midX * 0.35;
        rxn.reactants.forEach((group, gi) => {
            const count = group.count || 1;
            for (let c = 0; c < count; c++) {
                const offsetY = (c - (count - 1) / 2) * 60;
                group.atoms.forEach(a => {
                    this.particles.push({
                        el: a.el,
                        startX: rx + a.x * scale,
                        startY: midY + offsetY + a.y * scale,
                        endX: 0, endY: 0, // filled later
                        x: 0, y: 0
                    });
                });
            }
            rx += midX * 0.25;
        });

        // Place products on the right
        let px = midX * 1.2;
        let prodIdx = 0;
        rxn.products.forEach((group) => {
            const count = group.count || 1;
            for (let c = 0; c < count; c++) {
                const offsetY = (c - (count - 1) / 2) * 60;
                group.atoms.forEach(a => {
                    if (prodIdx < this.particles.length) {
                        this.particles[prodIdx].endX = px + a.x * scale;
                        this.particles[prodIdx].endY = midY + offsetY + a.y * scale;
                    }
                    prodIdx++;
                });
            }
            px += midX * 0.3;
        });

        // If not enough product positions, extend
        while (prodIdx < this.particles.length) {
            const p = this.particles[prodIdx];
            p.endX = midX + (Math.random() - 0.5) * midX;
            p.endY = midY + (Math.random() - 0.5) * this.H * 0.4;
            prodIdx++;
        }

        // Set initial positions
        this.particles.forEach(p => {
            p.x = p.startX;
            p.y = p.startY;
        });
    },

    play() {
        if (this.running) return;
        this.running = true;
        const btn = document.getElementById('rxn-play');
        if (btn) btn.textContent = '反应中...';

        const animate = () => {
            this.progress += 0.004 * this.speed;
            if (this.progress >= 1) {
                this.progress = 1;
                this.running = false;
                if (btn) btn.textContent = '▶ 开始反应';
            }
            this.updatePositions();
            this.draw();
            this.updateEnergyBar();
            if (this.running) {
                this.animId = requestAnimationFrame(animate);
            }
        };
        this.animId = requestAnimationFrame(animate);
    },

    stop() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
        this.running = false;
        const btn = document.getElementById('rxn-play');
        if (btn) btn.textContent = '▶ 开始反应';
    },

    reset() {
        this.stop();
        this.progress = 0;
        this.buildParticles();
        this.draw();
        this.updateEnergyBar();
    },

    updatePositions() {
        // Smooth easing
        const t = this.progress;
        const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        // Phase 1 (0-0.4): atoms gather to center
        // Phase 2 (0.4-0.6): "reaction" zone - scatter/flash
        // Phase 3 (0.6-1): atoms move to product positions
        this.particles.forEach(p => {
            const midX = this.W / 2;
            const midY = this.H / 2;
            if (t < 0.4) {
                const localT = t / 0.4;
                const e = localT * localT;
                p.x = p.startX + (midX - p.startX) * e;
                p.y = p.startY + (midY - p.startY) * e;
            } else if (t < 0.6) {
                // Vibrate around center
                const jitter = (1 - (t - 0.4) / 0.2) * 15;
                p.x = midX + (Math.random() - 0.5) * jitter;
                p.y = midY + (Math.random() - 0.5) * jitter;
            } else {
                const localT = (t - 0.6) / 0.4;
                const e = 1 - Math.pow(1 - localT, 3);
                p.x = midX + (p.endX - midX) * e;
                p.y = midY + (p.endY - midY) * e;
            }
        });
    },

    draw() {
        const { ctx, W, H } = this;
        ctx.clearRect(0, 0, W, H);

        // Background
        ctx.fillStyle = '#0d1017';
        ctx.fillRect(0, 0, W, H);

        // Reaction flash effect
        if (this.progress > 0.35 && this.progress < 0.65) {
            const intensity = 1 - Math.abs(this.progress - 0.5) / 0.15;
            const rxn = this.currentReaction;
            const flashColor = rxn.type === '放热'
                ? `rgba(255,120,30,${intensity * 0.25})`
                : `rgba(100,180,255,${intensity * 0.25})`;
            const grd = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, 120);
            grd.addColorStop(0, flashColor);
            grd.addColorStop(1, 'transparent');
            ctx.fillStyle = grd;
            ctx.fillRect(0, 0, W, H);
        }

        // Arrow in center
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '28px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('→', W / 2, H / 2);

        // Labels
        ctx.font = '13px "Inter", sans-serif';
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.textAlign = 'center';
        ctx.fillText('反应物', W * 0.25, 20);
        ctx.fillText('生成物', W * 0.75, 20);

        // Draw particles
        this.particles.forEach(p => {
            const color = this.atomColors[p.el] || '#aaa';
            const r = p.el === 'H' ? 10 : 14;

            // Glow
            ctx.shadowColor = color;
            ctx.shadowBlur = 8;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;

            // Label
            ctx.fillStyle = p.el === 'H' || p.el === 'S' ? '#333' : '#fff';
            ctx.font = `bold 10px "JetBrains Mono", monospace`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(p.el, p.x, p.y);
        });

        // Equation at bottom
        if (this.currentReaction) {
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.font = '14px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(this.currentReaction.equation, W / 2, H - 16);
        }
    },

    updateEnergyBar() {
        const bar = document.getElementById('rxn-energy-bar');
        const label = document.getElementById('rxn-energy-label');
        if (!bar || !label || !this.currentReaction) return;
        const rxn = this.currentReaction;
        const val = rxn.energy * this.progress;
        const pct = Math.abs(this.progress * 50);

        if (rxn.energy < 0) {
            bar.style.background = `linear-gradient(90deg, #c4793a ${pct}%, transparent ${pct}%)`;
            label.textContent = `ΔH = ${val.toFixed(0)} ${rxn.unit} (放热)`;
            label.style.color = '#c4793a';
        } else {
            bar.style.background = `linear-gradient(90deg, #5b8dce ${pct}%, transparent ${pct}%)`;
            label.textContent = `ΔH = +${val.toFixed(0)} ${rxn.unit} (吸热)`;
            label.style.color = '#5b8dce';
        }
    },

    updateInfo() {
        const el = document.getElementById('rxn-info');
        if (!el || !this.currentReaction) return;
        const rxn = this.currentReaction;
        el.innerHTML = `
            <div class="rxn-info-title">${rxn.name}</div>
            <div class="rxn-info-desc">${rxn.desc}</div>
            <div class="rxn-info-row"><span class="rxn-info-label">方程式</span><span>${rxn.equation}</span></div>
            <div class="rxn-info-row"><span class="rxn-info-label">类型</span><span>${rxn.type}反应</span></div>
            <div class="rxn-info-row"><span class="rxn-info-label">能量变化</span><span>ΔH = ${rxn.energy > 0 ? '+' : ''}${rxn.energy} ${rxn.unit}</span></div>
        `;
    }
};

function initChemReaction() {
    ChemReaction.init();
}
