// ===== DNA Double Helix Visualization =====

function initDNAHelix() {
    const canvas = document.getElementById('dna-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const info = document.getElementById('dna-info');

    let angle = 0;
    let rotating = false;
    let replicating = false;
    let replicateProgress = 0;
    let animId = null;

    const basePairs = 14;
    const colors = {
        A: '#e06060', T: '#6090e0',
        G: '#60c060', C: '#e0c040',
        backbone: 'rgba(200,200,200,0.6)'
    };

    const sequence = ['A','T','G','C','A','G','T','C','G','A','T','G','C','A'];
    const complement = sequence.map(b => ({ A:'T', T:'A', G:'C', C:'G' })[b]);

    function draw() {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const cx = w / 2;
        const helixH = h * 0.85;
        const startY = (h - helixH) / 2;
        const amp = 80;
        const step = helixH / basePairs;

        for (let i = 0; i < basePairs; i++) {
            const y = startY + i * step + step / 2;
            const phase = angle + (i / basePairs) * Math.PI * 4;

            const x1 = cx + Math.sin(phase) * amp;
            const x2 = cx + Math.sin(phase + Math.PI) * amp;
            const depth1 = Math.cos(phase);
            const depth2 = Math.cos(phase + Math.PI);

            const splitGap = replicating ? Math.min(replicateProgress, 1) * 60 * (i < replicateProgress * basePairs ? 1 : 0) : 0;

            // Draw hydrogen bonds (dashed line between pairs)
            if (splitGap === 0) {
                ctx.beginPath();
                ctx.setLineDash([3, 4]);
                ctx.moveTo(x1, y);
                ctx.lineTo(x2, y);
                ctx.strokeStyle = 'rgba(255,255,255,0.15)';
                ctx.lineWidth = 1;
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // Draw nucleotides
            const drawNucleotide = (x, base, depth, offsetX) => {
                const r = 8 + depth * 3;
                const alpha = 0.5 + depth * 0.3;
                ctx.beginPath();
                ctx.arc(x + offsetX, y, Math.max(r, 4), 0, Math.PI * 2);
                ctx.fillStyle = colors[base];
                ctx.globalAlpha = Math.max(alpha, 0.2);
                ctx.fill();
                ctx.globalAlpha = 1;

                if (r > 5) {
                    ctx.fillStyle = '#fff';
                    ctx.font = 'bold 10px JetBrains Mono, monospace';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(base, x + offsetX, y);
                }
            };

            // Sort by depth for proper layering
            if (depth1 > depth2) {
                drawNucleotide(x2, complement[i], depth2, -splitGap);
                drawNucleotide(x1, sequence[i], depth1, splitGap);
            } else {
                drawNucleotide(x1, sequence[i], depth1, splitGap);
                drawNucleotide(x2, complement[i], depth2, -splitGap);
            }
        }

        // Draw backbone curves
        ctx.beginPath();
        for (let t = 0; t <= basePairs; t += 0.1) {
            const y = startY + t * step;
            const phase = angle + (t / basePairs) * Math.PI * 4;
            const x = cx + Math.sin(phase) * amp;
            if (t === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = colors.backbone;
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        for (let t = 0; t <= basePairs; t += 0.1) {
            const y = startY + t * step;
            const phase = angle + (t / basePairs) * Math.PI * 4 + Math.PI;
            const x = cx + Math.sin(phase) * amp;
            if (t === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Legend
        ctx.globalAlpha = 0.7;
        ctx.font = '11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        const legendX = 20, legendY = h - 60;
        [['A (腺嘌呤)', colors.A], ['T (胸腺嘧啶)', colors.T], ['G (鸟嘌呤)', colors.G], ['C (胞嘧啶)', colors.C]].forEach(([label, color], i) => {
            ctx.fillStyle = color;
            ctx.fillRect(legendX, legendY + i * 16, 10, 10);
            ctx.fillStyle = '#ccc';
            ctx.fillText(label, legendX + 16, legendY + i * 16 + 9);
        });
        ctx.globalAlpha = 1;
    }

    function animate() {
        if (rotating) angle += 0.015;
        if (replicating) {
            replicateProgress += 0.004;
            if (replicateProgress >= 1.2) { replicating = false; if (info) info.textContent = 'DNA 复制完成！新链已合成'; }
        }
        draw();
        animId = requestAnimationFrame(animate);
    }

    const rotateBtn = document.getElementById('bio-dna-rotate');
    if (rotateBtn) rotateBtn.addEventListener('click', () => {
        rotating = !rotating;
        rotateBtn.textContent = rotating ? '停止旋转' : '旋转螺旋';
    });

    const repBtn = document.getElementById('bio-dna-replicate');
    if (repBtn) repBtn.addEventListener('click', () => {
        replicating = true;
        replicateProgress = 0;
        if (info) info.textContent = 'DNA 复制进行中 — 解旋酶正在解开双链...';
    });

    const resetBtn = document.getElementById('bio-dna-reset');
    if (resetBtn) resetBtn.addEventListener('click', () => {
        rotating = false;
        replicating = false;
        replicateProgress = 0;
        angle = 0;
        if (rotateBtn) rotateBtn.textContent = '旋转螺旋';
        if (info) info.textContent = 'DNA 双螺旋结构 — 点击按钮开始探索';
        draw();
    });

    animate();
}
