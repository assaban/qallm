let sessionId = null;
let currentFindings = [];
let pendingRegressionIds = [];
let sortCol = -1;
let sortAsc = true;
let _healthPollTimer = null;

const SEV_ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3};

// --- Service health indicator ---
const HEALTH_ENDPOINTS = {
    simple: '/api/health/llm',
    agent:  '/api/health/agent',
};

async function checkServiceHealth() {
    const mode = document.getElementById('repairMode')?.value || 'simple';
    const dot  = document.getElementById('modeStatusDot');
    if (!dot) return;

    dot.className = 'status-dot dot-unknown';
    dot.title = 'Checking service…';

    try {
        const res = await fetch(HEALTH_ENDPOINTS[mode], { method: 'GET', cache: 'no-store' });
        if (res.ok) {
            const data = await res.json().catch(() => ({}));
            const svc  = data.service || (mode === 'agent' ? 'agent pipeline' : 'LLM service');
            dot.className = 'status-dot dot-online';
            dot.title = `${svc} is online`;
        } else {
            dot.className = 'status-dot dot-offline';
            dot.title = `Service unavailable (HTTP ${res.status})`;
        }
    } catch {
        dot.className = 'status-dot dot-offline';
        dot.title = 'Service unreachable';
    }
}

function onModeChange() {
    checkServiceHealth();
}

function startHealthPolling() {
    checkServiceHealth();
    clearInterval(_healthPollTimer);
    _healthPollTimer = setInterval(checkServiceHealth, 30_000);
}

document.addEventListener('DOMContentLoaded', startHealthPolling);

function setStatus(msg, type = 'info') {
    const el = document.getElementById('status');
    el.className = 'status ' + type;
    el.textContent = msg;
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
        throw new Error(`Server error (HTTP ${res.status}) — upstream service may be unavailable`);
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
}

function showBusy(label) {
    show('progressBar');
    document.getElementById('overlayLabel').textContent = label;
    show('resultsBusyOverlay');
}
function hideBusy() {
    hide('progressBar');
    hide('resultsBusyOverlay');
}

// --- Stepper ---
function setStep(active) {
    for (let i = 1; i <= 5; i++) {
        const el = document.getElementById('step-' + i);
        el.classList.remove('active', 'completed');
        if (i < active) el.classList.add('completed');
        else if (i === active) el.classList.add('active');
    }
}

// --- Upload ---
async function uploadZip() {
    const input = document.getElementById('zipFile');
    if (!input.files.length) { setStatus('Please select a ZIP file', 'error'); return; }

    setStatus('Uploading...', 'info');
    const form = new FormData();
    form.append('archive', input.files[0]);

    try {
        const data = await fetchJSON('/api/session/upload', { method: 'POST', body: form });
        sessionId = data.session_id;
        setStatus('Upload successful! Session: ' + sessionId.slice(0, 8) + '...', 'success');
        await loadFiles();
    } catch (e) { setStatus('Upload failed: ' + e.message, 'error'); }
}

// --- Clone ---
async function cloneRepo() {
    const url = document.getElementById('gitUrl').value.trim();
    if (!url) { setStatus('Please enter a GitHub URL', 'error'); return; }

    setStatus('Cloning repository...', 'info');
    try {
        const data = await fetchJSON('/api/session/clone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ git_url: url }),
        });
        sessionId = data.session_id;
        setStatus('Clone successful! Session: ' + sessionId.slice(0, 8) + '...', 'success');
        await loadFiles();
    } catch (e) { setStatus('Clone failed: ' + e.message, 'error'); }
}

// --- File List ---
async function loadFiles() {
    const data = await fetchJSON(`/api/session/${sessionId}/files`);
    const files = data.files || [];

    const container = document.getElementById('fileList');
    container.innerHTML = files.map(f =>
        `<label><input type="checkbox" value="${f}" checked> ${f}</label>`
    ).join('');
    document.getElementById('fileCount').textContent = `${files.length} files`;
    show('fileSection');
    setStep(2);
}

function toggleAll(checked) {
    document.querySelectorAll('#fileList input').forEach(cb => cb.checked = checked);
}

// --- Analyse ---
async function runAnalysis() {
    const btn = document.getElementById('analyseBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Analysing...';

    const selected = [...document.querySelectorAll('#fileList input:checked')].map(cb => cb.value);
    if (!selected.length) { setStatus('Select at least one file', 'error'); btn.disabled = false; btn.textContent = 'Run Analysis (all 4 tools)'; return; }

    show('resultsSection');
    showBusy('Analysing…');

    try {
        const data = await fetchJSON('/api/analyse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, selected_files: selected }),
        });

        currentFindings = data.findings || [];
        renderSummary(data.summary);
        renderFindings(currentFindings);
        setStep(3);
        // Show repair section and load providers
        if (currentFindings.length > 0) {
            await loadProviders();
            show('repairSection');
            setStep(4);
        }

        // Hide verification from a previous run when re-analysing
        hide('verificationSection');
        hide('verificationResults');

        setStatus(`Analysis complete: ${currentFindings.length} findings`, 'success');
    } catch (e) {
        setStatus('Analysis failed: ' + e.message, 'error');
    } finally {
        hideBusy();
        btn.disabled = false;
        btn.textContent = 'Run Analysis (all 4 tools)';
    }
}

// --- Summary ---
function renderSummary(s, targetId = 'summary') {
    if (!s) return;
    const el = document.getElementById(targetId);
    el.innerHTML = `
        <span class="badge total">${s.total} Total</span>
        <span class="badge critical">${s.by_severity.CRITICAL || 0} Critical</span>
        <span class="badge high">${s.by_severity.HIGH || 0} High</span>
        <span class="badge medium">${s.by_severity.MEDIUM || 0} Medium</span>
        <span class="badge low">${s.by_severity.LOW || 0} Low</span>
    `;
}

// --- Findings Table ---
function renderFindings(findings) {
    const body = document.getElementById('findingsBody');
    const wrap = body.closest('.findings-table-wrap');
    const empty = document.getElementById('findingsEmpty');
    if (!findings.length) {
        body.innerHTML = '';
        wrap.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }
    wrap.classList.remove('hidden');
    empty.classList.add('hidden');

    body.innerHTML = findings.map((f, i) => `<tr>
        <td>${i + 1}</td>
        <td><span class="sev sev-${f.severity}">${f.severity}</span></td>
        <td><span class="type">${f.type}</span></td>
        <td>${f.tool}</td>
        <td>${f.file || '—'}</td>
        <td>${f.line || '—'}</td>
        <td>${escHtml(f.message)}</td>
        <td>${f.code_snippet ? '<code class="snippet">' + escHtml(f.code_snippet) + '</code>' : '—'}</td>
    </tr>`).join('');
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// --- Sort ---
function sortTable(col) {
    if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = true; }

    const keys = ['_idx','severity','type','tool','file','line','message','code_snippet'];
    const key = keys[col];

    currentFindings.sort((a, b) => {
        let va = a[key], vb = b[key];
        if (key === 'severity') { va = SEV_ORDER[va] ?? 9; vb = SEV_ORDER[vb] ?? 9; }
        if (key === 'line') { va = va || 0; vb = vb || 0; }
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    });
    renderFindings(currentFindings);
}

// --- LLM Model Selection ---
async function loadProviders() {
    try {
        const data = await fetchJSON('/api/llm/providers');
        const select = document.getElementById('providerSelect');
        select.innerHTML = '';
        // Auto option (routes by severity)
        const autoOpt = document.createElement('option');
        autoOpt.value = '';
        autoOpt.textContent = 'Auto (route by severity)';
        autoOpt.selected = true;
        select.appendChild(autoOpt);
        // Configured models
        (data.configured || []).forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        });
        // Unconfigured models (greyed out)
        (data.available || []).filter(n => !(data.configured || []).includes(n)).forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name + ' (not configured)';
            opt.disabled = true;
            select.appendChild(opt);
        });
    } catch (e) { console.error('Failed to load models:', e); }
}

// --- Repair ---
async function runRepair() {
    const btn = document.getElementById('repairBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Repairing...';

    // Reset verification state from any previous run
    hide('verificationSection');
    hide('verificationResults');

    const mode = document.getElementById('repairMode').value;
    const endpoint = mode === 'agent'
        ? `/api/repair-agent/${sessionId}`
        : `/api/repair/${sessionId}`;
    showBusy(mode === 'agent' ? 'Running agent pipeline…' : 'Repairing…');
    const provider = document.getElementById('providerSelect').value || null;

    try {
        const data = await fetchJSON(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider }),
        });

        renderRepairResults(data);
        show('repairResults');
        setStatus(`Repair complete: ${data.repaired_count} patches applied via ${data.provider_used}. Now run verification ↓`, 'success');

        // Reveal Step 5 automatically after a successful repair
        show('verificationSection');
        setStep(5);
        document.getElementById('verificationSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
        setStatus('Repair failed: ' + e.message, 'error');
    } finally {
        hideBusy();
        btn.disabled = false;
        btn.textContent = 'Repair Findings';
    }
}

async function reRunRepair() {
    if (!pendingRegressionIds.length) return;
    const btn = document.getElementById('reRepairBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Repairing…';
    hide('verificationResults');
    showBusy('Re-repairing regressions…');

    const provider = document.getElementById('providerSelect').value || null;
    const mode = document.getElementById('repairMode').value;
    const endpoint = mode === 'agent'
        ? `/api/repair-agent/${sessionId}`
        : `/api/repair/${sessionId}`;
    try {
        const data = await fetchJSON(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, finding_ids: pendingRegressionIds }),
        });
        renderRepairResults(data);
        show('repairResults');
        show('verificationResults');
        setStatus(`Re-repair complete: ${data.repaired_count} patches applied. Run Verification again to check.`, 'success');
        document.getElementById('verifyBtn').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
        show('verificationResults');
        setStatus('Re-repair failed: ' + e.message, 'error');
    } finally {
        hideBusy();
        btn.disabled = false;
        btn.textContent = 'Re-repair regressions';
    }
}

function renderRepairResults(data) {
    const summaryEl = document.getElementById('repairSummary');
    const tu = data.token_usage || {};
    summaryEl.innerHTML = `
        <span class="badge total">${(data.patches || []).length} Patches</span>
        <span class="badge high">${data.repaired_count || 0} Applied</span>
        <span class="badge medium">${tu.total_tokens || 0} Tokens</span>
        <span class="badge low">${tu.remaining || 0} Remaining</span>
        <span class="badge">${data.provider_used || '?'}</span>
    `;

    const listEl = document.getElementById('patchList');
    const patches = data.patches || [];
    if (!patches.length) {
        listEl.innerHTML = '<p style="color:var(--muted)">No patches generated.</p>';
        return;
    }

    listEl.innerHTML = patches.map((p, i) => `
        <div class="patch-card ${p.applied ? 'patch-applied' : p.error ? 'patch-error' : 'patch-noop'}">
            <div class="patch-header">
                <strong>#${i + 1}</strong>
                <span class="patch-status">${p.applied ? '✅ Applied' : p.error ? '❌ ' + escHtml(p.error) : '⏭ No change'}</span>
            </div>
            <p class="patch-desc">${escHtml(p.description)}</p>
            ${p.unified_diff ? '<details><summary>Show diff</summary><pre class="diff">' + escHtml(p.unified_diff) + '</pre></details>' : ''}
        </div>
    `).join('');
}

// --- Verification ---
async function runVerification() {
    const btn = document.getElementById('verifyBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Re-running analysis...';
    setStatus('Running post-repair analysis...', 'info');
    showBusy('Verifying…');

    try {
        const data = await fetchJSON(`/api/verify/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });

        show('verificationResults');
        requestAnimationFrame(() => renderVerificationResults(data));

        const improved = (data.before.total - data.after.total);
        const pct = data.before.total > 0
            ? Math.round((data.resolved / data.before.total) * 100)
            : 0;

        const msg = data.new > 0
            ? `Verification complete: ${data.resolved} resolved, ${data.new} regressions introduced.`
            : `Verification complete: ${pct}% of issues resolved (${data.resolved} fixed, ${data.remaining} remaining).`;

        setStatus(msg, data.new > 0 ? 'error' : 'success');

    } catch (e) {
        setStatus('Verification failed: ' + e.message, 'error');
    } finally {
        hideBusy();
        btn.disabled = false;
        btn.textContent = 'Run Verification';
    }
}

// ── Chart helpers ────────────────────────────────────────────────
const _charts = {};
function destroyChart(id) {
    if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

function renderSeverityChart(before, after) {
    destroyChart('chartSeverity');
    const SEV_LABELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
    const SEV_COLORS = ['#ef4444', '#fd7e14', '#f59e0b', '#38bdf8'];
    const canvas = document.getElementById('chartSeverity');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    _charts['chartSeverity'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: SEV_LABELS,
            datasets: [
                {
                    label: 'Before',
                    data: SEV_LABELS.map(s => before.by_severity[s] || 0),
                    backgroundColor: '#94a3b8',
                    borderRadius: 4,
                    barPercentage: 0.7,
                },
                {
                    label: 'After',
                    data: SEV_LABELS.map(s => after.by_severity[s] || 0),
                    backgroundColor: SEV_COLORS,
                    borderRadius: 4,
                    barPercentage: 0.7,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top', align: 'end' },
                tooltip: {
                    callbacks: {
                        footer(items) {
                            const sev = items[0].label;
                            const b = before.by_severity[sev] || 0;
                            const a = after.by_severity[sev] || 0;
                            const fixed = b - a;
                            return fixed > 0 ? `▼ ${fixed} fixed` : fixed < 0 ? `▲ ${Math.abs(fixed)} new` : 'No change';
                        },
                    },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, precision: 0 },
                    grid: { color: '#f1f5f9' },
                },
                x: { grid: { display: false } },
            },
        },
    });
}

function renderOutcomeChart(resolved, remaining, newCount) {
    destroyChart('chartOutcome');
    const wrap = document.getElementById('chartOutcomeWrap');

    // Hide when everything is resolved — a 100% green donut adds no info
    if (remaining === 0 && newCount === 0) {
        wrap.classList.add('hidden');
        return;
    }
    wrap.classList.remove('hidden');

    const labels = ['Resolved', 'Remaining', 'New'];
    const values = [resolved, remaining, newCount];
    const colors = ['#10b981', '#f59e0b', '#ef4444'];

    // Drop zero-value segments
    const filtered = labels.reduce((acc, l, i) => {
        if (values[i] > 0) acc.push({ label: l, value: values[i], color: colors[i] });
        return acc;
    }, []);

    const canvas = document.getElementById('chartOutcome');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    _charts['chartOutcome'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: filtered.map(d => d.label),
            datasets: [{
                data: filtered.map(d => d.value),
                backgroundColor: filtered.map(d => d.color),
                borderWidth: 2,
                borderColor: '#fff',
                hoverOffset: 6,
            }],
        },
        options: {
            cutout: '70%',
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 12, boxWidth: 12 } },
                tooltip: {
                    callbacks: {
                        label(item) {
                            const total = resolved + remaining + newCount;
                            const pct = Math.round((item.raw / total) * 100);
                            return ` ${item.raw} (${pct}%)`;
                        },
                    },
                },
            },
        },
        plugins: [{
            id: 'centreLabel',
            afterDraw(chart) {
                const { ctx: c, chartArea: { width, height, left, top } } = chart;
                const total = resolved + remaining + newCount;
                c.save();
                c.textAlign = 'center';
                c.textBaseline = 'middle';
                const cx = left + width / 2;
                const cy = top + height / 2;
                c.font = 'bold 1.4rem Inter, sans-serif';
                c.fillStyle = '#0f172a';
                c.fillText(total, cx, cy - 8);
                c.font = '0.7rem Inter, sans-serif';
                c.fillStyle = '#64748b';
                c.fillText('total', cx, cy + 12);
                c.restore();
            },
        }],
    });
}

function sevColor(sev) {
    return { CRITICAL: '#ef4444', HIGH: '#fd7e14', MEDIUM: '#f59e0b', LOW: '#38bdf8' }[sev] || '#94a3b8';
}

function renderFileTreemap(resolvedIds) {
    destroyChart('chartFiles');
    const canvas = document.getElementById('chartFiles');
    if (!canvas) return;

    const resolved = new Set(resolvedIds || []);

    const fileMap = {};
    currentFindings
        .filter(f => !resolved.has(f.id))
        .forEach(f => {
            const file = f.file || '(unknown)';
            if (!fileMap[file]) fileMap[file] = { count: 0, worstSev: 'LOW' };
            fileMap[file].count++;
            if (SEV_ORDER[f.severity] < SEV_ORDER[fileMap[file].worstSev])
                fileMap[file].worstSev = f.severity;
        });

    const tree = Object.entries(fileMap).map(([file, d]) => ({
        file,
        label: file.split('/').pop(),
        count: d.count,
        worstSev: d.worstSev,
    }));

    if (!tree.length) {
        document.getElementById('chartFilesDetails').style.display = 'none';
        return;
    }
    document.getElementById('chartFilesDetails').style.display = '';

    const ctx = canvas.getContext('2d');
    _charts['chartFiles'] = new Chart(ctx, {
        type: 'treemap',
        data: {
            datasets: [{
                label: 'Remaining findings',
                data: tree,
                key: 'count',
                backgroundColor(ctx) {
                    const raw = ctx.raw?._data;
                    return raw ? sevColor(raw.worstSev) + 'cc' : '#94a3b8cc';
                },
                borderColor(ctx) {
                    const raw = ctx.raw?._data;
                    return raw ? sevColor(raw.worstSev) : '#94a3b8';
                },
                borderWidth: 1,
                labels: {
                    display: true,
                    formatter(ctx) {
                        const d = ctx.raw?._data;
                        return d ? [`${d.label}`, `${d.count} finding${d.count !== 1 ? 's' : ''}`] : '';
                    },
                    color: '#fff',
                    font: [{ size: 12, weight: 'bold' }, { size: 11 }],
                },
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title(items) {
                            return items[0]?.raw?._data?.file || '';
                        },
                        label(item) {
                            const d = item.raw?._data;
                            return d ? [`${d.count} finding${d.count !== 1 ? 's' : ''}`, `Worst: ${d.worstSev}`] : '';
                        },
                    },
                },
            },
        },
    });
}

function renderToolChart(resolvedIds) {
    destroyChart('chartTool');
    const canvas = document.getElementById('chartTool');
    if (!canvas) return;

    const resolved = new Set(resolvedIds || []);

    // Group currentFindings by tool → resolved / remaining counts
    const toolMap = {};
    currentFindings.forEach(f => {
        const t = f.tool || 'unknown';
        if (!toolMap[t]) toolMap[t] = { resolved: 0, remaining: 0 };
        if (resolved.has(f.id)) toolMap[t].resolved++;
        else toolMap[t].remaining++;
    });

    // Only show tools that have at least one finding
    const tools = Object.keys(toolMap).filter(t => (toolMap[t].resolved + toolMap[t].remaining) > 0);
    if (!tools.length) return;

    const ctx = canvas.getContext('2d');
    _charts['chartTool'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: tools,
            datasets: [
                {
                    label: 'Resolved',
                    data: tools.map(t => toolMap[t].resolved),
                    backgroundColor: '#10b981',
                    stack: 'a',
                    borderRadius: 4,
                },
                {
                    label: 'Remaining',
                    data: tools.map(t => toolMap[t].remaining),
                    backgroundColor: '#f59e0b',
                    stack: 'a',
                    borderRadius: 4,
                },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', align: 'end' },
                tooltip: {
                    callbacks: {
                        footer(items) {
                            const t = items[0].label;
                            const total = toolMap[t].resolved + toolMap[t].remaining;
                            const pct = total > 0 ? Math.round((toolMap[t].resolved / total) * 100) : 0;
                            return `${pct}% of ${total} findings resolved`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { stepSize: 1, precision: 0 },
                    grid: { color: '#f1f5f9' },
                },
                y: {
                    stacked: true,
                    grid: { display: false },
                },
            },
        },
    });
}

function animateCount(el, target, suffix, duration) {
    const start = performance.now();
    function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(eased * target) + suffix;
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target + suffix;
    }
    requestAnimationFrame(step);
}

function renderVerificationResults(data) {
    // Visual 1: Headline % improvement
    const pct = data.before.total > 0
        ? Math.round((data.resolved / data.before.total) * 100)
        : 0;
    const pctEl = document.getElementById('verifyPct');
    pctEl.classList.remove('is-regressed', 'is-neutral');
    if (data.new > data.resolved)      pctEl.classList.add('is-regressed');
    else if (pct === 0)                pctEl.classList.add('is-neutral');
    animateCount(pctEl, pct, '%', 700);
    document.getElementById('verifyPctSub').textContent =
        `${data.resolved} fixed · ${data.remaining} remaining` +
        (data.new > 0 ? ` · ${data.new} new regressions` : '');

    // Score cards
    document.getElementById('verifyResolved').textContent = data.resolved;
    document.getElementById('verifyRemaining').textContent = data.remaining;
    document.getElementById('verifyNew').textContent = data.new;

    // Colour the "new" card red if regressions exist
    const newCard = document.getElementById('verifyNew').closest('.scorecard');
    newCard.classList.toggle('scorecard-danger', data.new > 0);

    // Visual 2 + 3: Grouped bar + donut
    renderSeverityChart(data.before, data.after);
    renderOutcomeChart(data.resolved, data.remaining, data.new);

    // Visual 4: Tool breakdown
    renderToolChart(data.resolved_ids);

    // Visual 5: File treemap — render when user opens the <details>
    const details = document.getElementById('chartFilesDetails');
    const onToggle = () => {
        if (details.open) {
            details.removeEventListener('toggle', onToggle);
            requestAnimationFrame(() => renderFileTreemap(data.resolved_ids));
        }
    };
    destroyChart('chartFiles');
    details.removeEventListener('toggle', onToggle); // clean up any prior run
    details.open = false;
    details.addEventListener('toggle', onToggle);

    // Before / after summary badges
    renderSummary(data.before, 'verifyBefore');
    renderSummary(data.after,  'verifyAfter');

    // Regression warning
    if (data.new > 0 && data.new_ids && data.new_ids.length) {
        pendingRegressionIds = data.new_ids;
        document.getElementById('regressionCount').textContent =
            `${data.new} regression${data.new !== 1 ? 's' : ''} detected —`;

        // Show per-file regression breakdown
        const listEl = document.getElementById('regressionFileList');
        const findings = data.new_findings || [];
        if (findings.length && listEl) {
            // Group by file
            const byFile = {};
            findings.forEach(f => {
                const file = f.file || '(unknown)';
                if (!byFile[file]) byFile[file] = [];
                byFile[file].push(f);
            });
            listEl.innerHTML = Object.entries(byFile).map(([file, fList]) => `
                <div class="regression-file">
                    <span class="regression-filename">${escHtml(file)}</span>
                    <span class="regression-file-count">${fList.length} new issue${fList.length !== 1 ? 's' : ''}</span>
                    <ul class="regression-finding-list">
                        ${fList.map(f => `<li>
                            <span class="sev-badge sev-${f.severity||'LOW'}">${f.severity||'?'}</span>
                            ${f.line ? `<span class="regression-line">L${f.line}</span>` : ''}
                            <span class="regression-msg">${escHtml(f.message||'')}</span>
                        </li>`).join('')}
                    </ul>
                </div>`).join('');
        } else if (listEl) {
            listEl.innerHTML = '';
        }

        show('regressionWarning');
    } else {
        pendingRegressionIds = [];
        hide('regressionWarning');
    }
}
