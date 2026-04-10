// ===== Genetics (Punnett Square) Visualization =====

function initGenetics() {
    const canvas = document.getElementById('genetics-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const info = document.getElementById('genetics-info');

    const parent1El = document.getElementById('bio-parent1');
    const parent2El = document.getElementById('bio-parent2');

    function getGametes(genotype) {
        if (genotype === 'AA') return ['A', 'A'];
        if (genotype === 'Aa') return ['A', 'a'];
        return ['a', 'a'];
    }

    function cross() {
        const g1 = parent1El ? parent1El.value : 'Aa';
        const g2 = parent2El ? parent2El.value : 'Aa';
        const gametes1 = getGametes(g1);
        const gametes2 = getGametes(g2);

        const offspring = [];
        gametes1.forEach(a => {
            gametes2.forEach(b => {
                // Normalize: uppercase first
                const pair = [a, b].sort((x, y) => x.toLowerCase().localeCompare(y.toLowerCase()) || x.localeCompare(y));
                offspring.push(pair.join(''));
            });
        });

        drawPunnett(g1, g2, gametes1, gametes2, offspring);
    }

    function drawPunnett(g1, g2, gam1, gam2, offspring) {
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const teal = '#3a9e8f';
        const cellSize = 80;
        const startX = w / 2 - cellSize * 1.5;
        const startY = h * 0.2;

        // Title
        ctx.fillStyle = 'rgba(255,255,255,0.8)';
        ctx.font = 'bold 16px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`杂交: ${g1} × ${g2}`, w / 2, startY - 30);

        // Draw grid
        const drawCell = (row, col, text, isHeader) => {
            const x = startX + col * cellSize;
            const y = startY + row * cellSize;
            ctx.fillStyle = isHeader ? 'rgba(58,158,143,0.15)' : 'rgba(255,255,255,0.04)';
            ctx.fillRect(x, y, cellSize, cellSize);
            ctx.strokeStyle = 'rgba(255,255,255,0.1)';
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, cellSize, cellSize);
            ctx.fillStyle = isHeader ? teal : '#e0e0e0';
            ctx.font = isHeader ? 'bold 18px JetBrains Mono' : '20px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, x + cellSize / 2, y + cellSize / 2);
        };

        // Empty top-left
        drawCell(0, 0, '♀＼♂', true);
        // Parent 2 gametes (top)
        drawCell(0, 1, gam2[0], true);
        drawCell(0, 2, gam2[1], true);
        // Parent 1 gametes (left)
        drawCell(1, 0, gam1[0], true);
        drawCell(2, 0, gam1[1], true);
        // Offspring
        drawCell(1, 1, offspring[0], false);
        drawCell(1, 2, offspring[1], false);
        drawCell(2, 1, offspring[2], false);
        drawCell(2, 2, offspring[3], false);

        // Color-code offspring genotypes
        const colorMap = { dominant: 'rgba(58,158,143,0.3)', carrier: 'rgba(196,168,58,0.2)', recessive: 'rgba(184,84,80,0.2)' };
        const offspringCells = [[1,1],[1,2],[2,1],[2,2]];
        offspringCells.forEach((pos, i) => {
            const geno = offspring[i];
            let type = geno === 'AA' ? 'dominant' : geno === 'Aa' ? 'carrier' : 'recessive';
            const x = startX + pos[1] * cellSize;
            const y = startY + pos[0] * cellSize;
            ctx.fillStyle = colorMap[type];
            ctx.fillRect(x + 1, y + 1, cellSize - 2, cellSize - 2);
            // Re-draw text on top
            ctx.fillStyle = '#e0e0e0';
            ctx.font = '20px JetBrains Mono';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(geno, x + cellSize / 2, y + cellSize / 2);
        });

        // Statistics
        const counts = {};
        offspring.forEach(g => { counts[g] = (counts[g] || 0) + 1; });
        const statsY = startY + cellSize * 3 + 30;

        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.font = '14px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('后代基因型比例:', w / 2, statsY);

        let offsetX = 0;
        const entries = Object.entries(counts).sort();
        const totalEntries = entries.length;
        const entryWidth = 120;
        const totalWidth = totalEntries * entryWidth;
        const baseX = w / 2 - totalWidth / 2;

        entries.forEach(([geno, count], i) => {
            const x = baseX + i * entryWidth + entryWidth / 2;
            const phenotype = geno.includes('A') ? '显性' : '隐性';
            const barH = (count / 4) * 60;
            const barW = 40;

            // Bar
            ctx.fillStyle = geno === 'AA' ? 'rgba(58,158,143,0.5)' : geno === 'Aa' ? 'rgba(196,168,58,0.4)' : 'rgba(184,84,80,0.4)';
            ctx.fillRect(x - barW / 2, statsY + 50 + (60 - barH), barW, barH);

            // Label
            ctx.fillStyle = '#ccc';
            ctx.font = 'bold 14px JetBrains Mono';
            ctx.fillText(geno, x, statsY + 25);
            ctx.font = '11px "Noto Sans SC"';
            ctx.fillText(`${count}/4 (${phenotype})`, x, statsY + 120);
        });

        // Phenotype ratio
        const dominant = offspring.filter(g => g.includes('A')).length;
        const recessive = 4 - dominant;
        if (info) {
            info.textContent = `表现型比例 — 显性:隐性 = ${dominant}:${recessive}`;
        }
    }

    const crossBtn = document.getElementById('bio-cross');
    if (crossBtn) crossBtn.addEventListener('click', cross);

    // Initial draw
    cross();
}
