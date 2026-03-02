const API = '';

// --- Utility ---

function toast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

async function api(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed (${res.status})`);
    }
    if (res.status === 204 || res.headers.get('content-length') === '0') return null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return null;
}

function badgeHtml(text, type) {
    return `<span class="badge badge-${type}">${text}</span>`;
}

function formatDate(iso) {
    return new Date(iso).toLocaleDateString();
}

// --- Tab Navigation ---

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

        if (btn.dataset.tab === 'routes') loadRoutes();
        else if (btn.dataset.tab === 'certificates') { loadCA(); loadCerts(); }
        else if (btn.dataset.tab === 'health') loadHealth();
        else if (btn.dataset.tab === 'logs') { loadLogs(); startLogAutoRefresh(); }
    });
});

// --- Modal Helpers ---

function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.closest('.modal-overlay').classList.remove('active');
    });
});

document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

// --- Routes ---

function renderRouteCard(r, isChild) {
    const cls = isChild ? 'card route-child' : 'card';
    const display = r.route_type === 'host'
        ? `${r.match_pattern} &rarr; ${r.target_host}:${r.target_port}`
        : `${r.match_pattern} &rarr; ${r.target_host}:${r.target_port}`;
    return `
        <div class="${cls}">
            <div class="card-info">
                <h4>
                    ${r.name}
                    ${badgeHtml(r.route_type, r.route_type)}
                    ${r.ssl_enabled ? badgeHtml('SSL', 'ssl') : ''}
                    ${badgeHtml(r.enabled ? 'enabled' : 'disabled', r.enabled ? 'enabled' : 'disabled')}
                    ${badgeHtml(r.health_status, r.health_status)}
                </h4>
                <p>${display}</p>
            </div>
            <div class="card-actions">
                <button class="btn btn-sm btn-secondary" onclick="toggleRoute(${r.id})">${r.enabled ? 'Disable' : 'Enable'}</button>
                <button class="btn btn-sm btn-secondary" onclick="editRoute(${r.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteRoute(${r.id})">Delete</button>
            </div>
        </div>`;
}

async function loadRoutes() {
    try {
        const routes = await api('/api/routes');
        const list = document.getElementById('routes-list');
        if (routes.length === 0) {
            list.innerHTML = '<div class="empty-state">No routes configured yet.</div>';
            return;
        }

        // Group: host routes as parents, path routes with matching match_host as children
        const hostRoutes = routes.filter(r => r.route_type === 'host');
        const pathRoutes = routes.filter(r => r.route_type === 'path');

        // Build hostname -> host route mapping
        const hostMap = new Map();
        for (const r of hostRoutes) {
            const hostname = r.match_pattern.split(':')[0].split('/')[0];
            hostMap.set(hostname, r);
        }

        // Assign path routes to their host groups
        const grouped = new Map(); // hostname -> { host: route, children: [] }
        for (const r of hostRoutes) {
            const hostname = r.match_pattern.split(':')[0].split('/')[0];
            grouped.set(hostname, { host: r, children: [] });
        }

        const ungrouped = [];
        for (const r of pathRoutes) {
            if (r.match_host && grouped.has(r.match_host)) {
                grouped.get(r.match_host).children.push(r);
            } else {
                ungrouped.push(r);
            }
        }

        let html = '';
        for (const [hostname, group] of grouped) {
            html += `<div class="route-group">`;
            html += renderRouteCard(group.host, false);
            for (const child of group.children) {
                html += renderRouteCard(child, true);
            }
            html += `</div>`;
        }
        for (const r of ungrouped) {
            html += renderRouteCard(r, false);
        }

        list.innerHTML = html;
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function toggleRoute(id) {
    try {
        await api(`/api/routes/${id}/toggle`, { method: 'POST' });
        toast('Route toggled');
        loadRoutes();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function deleteRoute(id) {
    if (!confirm('Delete this route?')) return;
    try {
        await api(`/api/routes/${id}`, { method: 'DELETE' });
        toast('Route deleted');
        loadRoutes();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function editRoute(id) {
    try {
        const r = await api(`/api/routes/${id}`);
        document.getElementById('route-modal-title').textContent = 'Edit Route';
        document.getElementById('route-id').value = r.id;
        document.getElementById('route-name').value = r.name;
        document.getElementById('route-type').value = r.route_type;
        document.getElementById('route-match').value = r.match_pattern;
        await toggleMatchHost();
        document.getElementById('route-match-host').value = r.match_host || '';
        document.getElementById('route-target-host').value = r.target_host;
        document.getElementById('route-target-port').value = r.target_port;
        document.getElementById('route-ssl').checked = r.ssl_enabled;
        toggleCertSelect();
        if (r.certificate_id) {
            await loadCertOptions();
            document.getElementById('route-cert').value = r.certificate_id;
        }
        openModal('route-modal');
    } catch (e) {
        toast(e.message, 'error');
    }
}

document.getElementById('btn-add-route').addEventListener('click', async () => {
    document.getElementById('route-modal-title').textContent = 'Add Route';
    document.getElementById('route-form').reset();
    document.getElementById('route-id').value = '';
    toggleCertSelect();
    await toggleMatchHost();
    openModal('route-modal');
});

document.getElementById('route-ssl').addEventListener('change', toggleCertSelect);
document.getElementById('route-type').addEventListener('change', () => toggleMatchHost());

async function toggleMatchHost() {
    const type = document.getElementById('route-type').value;
    const hostGroup = document.getElementById('match-host-group');
    const matchLabel = document.getElementById('route-match-label');
    const matchInput = document.getElementById('route-match');

    if (type === 'path') {
        hostGroup.style.display = 'block';
        matchLabel.textContent = 'Path';
        matchInput.placeholder = '/api/';
        await loadHostRouteOptions();
    } else {
        hostGroup.style.display = 'none';
        matchLabel.textContent = 'Hostname';
        matchInput.placeholder = 'app.example.com';
        document.getElementById('route-match-host').value = '';
    }
}

async function loadHostRouteOptions() {
    try {
        const routes = await api('/api/routes');
        const select = document.getElementById('route-match-host');
        const current = select.value;
        const hostRoutes = routes.filter(r => r.route_type === 'host');
        select.innerHTML = '<option value="">-- No host (any) --</option>' +
            hostRoutes.map(r => {
                const hostname = r.match_pattern.split(':')[0].split('/')[0];
                return `<option value="${hostname}">${r.name} (${hostname})</option>`;
            }).join('');
        if (current) select.value = current;
    } catch (e) { /* ignore */ }
}

function toggleCertSelect() {
    const show = document.getElementById('route-ssl').checked;
    document.getElementById('cert-select-group').style.display = show ? 'block' : 'none';
    if (show) loadCertOptions();
}

async function loadCertOptions() {
    try {
        const certs = await api('/api/certificates');
        const select = document.getElementById('route-cert');
        const current = select.value;
        select.innerHTML = '<option value="">-- Select Certificate --</option>' +
            certs.map(c => `<option value="${c.id}">${c.common_name}</option>`).join('');
        if (current) select.value = current;
    } catch (e) { /* ignore */ }
}

document.getElementById('route-form').addEventListener('submit', async e => {
    e.preventDefault();
    const id = document.getElementById('route-id').value;
    const data = {
        name: document.getElementById('route-name').value,
        route_type: document.getElementById('route-type').value,
        match_pattern: document.getElementById('route-match').value,
        match_host: document.getElementById('route-match-host').value || null,
        target_host: document.getElementById('route-target-host').value,
        target_port: parseInt(document.getElementById('route-target-port').value),
        ssl_enabled: document.getElementById('route-ssl').checked,
        certificate_id: document.getElementById('route-cert').value ? parseInt(document.getElementById('route-cert').value) : null,
    };
    try {
        if (id) {
            await api(`/api/routes/${id}`, { method: 'PUT', body: JSON.stringify(data) });
            toast('Route updated');
        } else {
            await api('/api/routes', { method: 'POST', body: JSON.stringify(data) });
            toast('Route created');
        }
        closeModal('route-modal');
        loadRoutes();
    } catch (e) {
        toast(e.message, 'error');
    }
});

// --- CA ---

async function loadCA() {
    try {
        const ca = await api('/api/ca');
        const section = document.getElementById('ca-status');
        if (ca) {
            section.innerHTML = `
                <p><strong>Active CA:</strong> ${ca.name}</p>
                <p>Created: ${formatDate(ca.created_at)}</p>
                <div class="ca-actions">
                    <a class="btn btn-sm btn-secondary" href="/api/ca/download" download>Download CA Certificate</a>
                </div>
            `;
        } else {
            section.innerHTML = `
                <p>No Certificate Authority configured.</p>
                <div class="ca-actions">
                    <button class="btn btn-primary" onclick="initCA()">Initialize CA</button>
                </div>
            `;
        }
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function initCA() {
    try {
        await api('/api/ca/init', { method: 'POST', body: JSON.stringify({}) });
        toast('CA initialized');
        loadCA();
    } catch (e) {
        toast(e.message, 'error');
    }
}

// --- Certificates ---

async function loadCerts() {
    try {
        const certs = await api('/api/certificates');
        const list = document.getElementById('certs-list');
        if (certs.length === 0) {
            list.innerHTML = '<div class="empty-state">No certificates issued yet.</div>';
            return;
        }
        list.innerHTML = certs.map(c => `
            <div class="card">
                <div class="card-info">
                    <h4>${c.common_name}</h4>
                    <p>Valid until: ${formatDate(c.valid_until)} | Domains: ${c.domain_names}</p>
                </div>
                <div class="card-actions">
                    <a class="btn btn-sm btn-secondary" href="/api/certificates/${c.id}/download" download>Download</a>
                    <button class="btn btn-sm btn-danger" onclick="deleteCert(${c.id})">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function deleteCert(id) {
    if (!confirm('Delete this certificate?')) return;
    try {
        await api(`/api/certificates/${id}`, { method: 'DELETE' });
        toast('Certificate deleted');
        loadCerts();
    } catch (e) {
        toast(e.message, 'error');
    }
}

document.getElementById('btn-issue-cert').addEventListener('click', () => {
    document.getElementById('cert-form').reset();
    openModal('cert-modal');
});

document.getElementById('cert-form').addEventListener('submit', async e => {
    e.preventDefault();
    const domainsStr = document.getElementById('cert-domains').value.trim();
    const domains = domainsStr ? domainsStr.split(',').map(d => d.trim()).filter(Boolean) : [];
    const validityStr = document.getElementById('cert-validity').value;
    const data = {
        common_name: document.getElementById('cert-cn').value,
        domain_names: domains,
    };
    if (validityStr) data.validity_days = parseInt(validityStr);
    try {
        await api('/api/certificates/issue', { method: 'POST', body: JSON.stringify(data) });
        toast('Certificate issued');
        closeModal('cert-modal');
        loadCerts();
    } catch (e) {
        toast(e.message, 'error');
    }
});

// --- Health ---

async function loadHealth() {
    try {
        const items = await api('/api/health');
        const list = document.getElementById('health-list');
        if (items.length === 0) {
            list.innerHTML = '<div class="empty-state">No routes to check.</div>';
            return;
        }
        list.innerHTML = items.map(h => `
            <div class="card">
                <div class="card-info">
                    <h4>
                        ${h.route_name}
                        ${badgeHtml(h.status, h.status)}
                        ${badgeHtml(h.enabled ? 'enabled' : 'disabled', h.enabled ? 'enabled' : 'disabled')}
                    </h4>
                    <p>${h.target}</p>
                </div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

document.getElementById('btn-refresh-health').addEventListener('click', loadHealth);

// --- Logs ---

let logAutoRefreshTimer = null;
let currentLogSource = 'proxy';

function statusClass(code) {
    if (code < 300) return 'status-2xx';
    if (code < 400) return 'status-3xx';
    if (code < 500) return 'status-4xx';
    return 'status-5xx';
}

function methodClass(method) {
    return `method-${(method || '').toLowerCase()}`;
}

function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function updateLogTableHeader() {
    const thead = document.getElementById('logs-thead');
    if (currentLogSource === 'proxy') {
        thead.innerHTML = `<tr>
            <th>Time</th>
            <th>Client IP</th>
            <th>Method</th>
            <th>Host / Path</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Backend</th>
            <th>User-Agent</th>
        </tr>`;
    } else {
        thead.innerHTML = `<tr>
            <th>Time</th>
            <th>Client IP</th>
            <th>Method</th>
            <th>Path</th>
            <th>Status</th>
            <th>Duration</th>
            <th>User-Agent</th>
        </tr>`;
    }
}

function renderProxyRow(l) {
    const dur = l.duration_s != null ? (parseFloat(l.duration_s) * 1000).toFixed(0) + 'ms' : '-';
    const host = l.server_name && l.server_name !== '_' && l.server_name !== '' ? l.server_name : '';
    const pathCol = host ? `${host}${l.path}` : l.path;
    const backend = l.upstream || '-';
    return `<tr>
        <td class="time-cell">${formatTime(l.timestamp)}</td>
        <td>${l.client_ip}</td>
        <td class="${methodClass(l.method)}">${l.method}</td>
        <td>${pathCol}</td>
        <td class="${statusClass(l.status)}">${l.status}</td>
        <td>${dur}</td>
        <td>${backend}</td>
        <td class="ua-cell" title="${l.user_agent}">${l.user_agent}</td>
    </tr>`;
}

function renderManagerRow(l) {
    return `<tr>
        <td class="time-cell">${formatTime(l.timestamp)}</td>
        <td>${l.client_ip}</td>
        <td class="${methodClass(l.method)}">${l.method}</td>
        <td>${l.path}${l.query ? '?' + l.query : ''}</td>
        <td class="${statusClass(l.status)}">${l.status}</td>
        <td>${l.duration_ms}ms</td>
        <td class="ua-cell" title="${l.user_agent}">${l.user_agent}</td>
    </tr>`;
}

function buildLogQuery() {
    const params = new URLSearchParams({ limit: '500' });
    const ip = document.getElementById('filter-ip').value.trim();
    const method = document.getElementById('filter-method').value;
    const path = document.getElementById('filter-path').value.trim();
    const from = document.getElementById('filter-time-from').value;
    const to = document.getElementById('filter-time-to').value;
    if (ip) params.set('ip', ip);
    if (method) params.set('method', method);
    if (path) params.set('path', path);
    if (from) params.set('time_from', new Date(from).toISOString());
    if (to) params.set('time_to', new Date(to).toISOString());
    return params.toString();
}

async function loadLogs() {
    try {
        const qs = buildLogQuery();
        const logs = await api(`/api/logs/${currentLogSource}?${qs}`);
        const tbody = document.getElementById('logs-body');
        const cols = currentLogSource === 'proxy' ? 8 : 7;
        if (logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;color:var(--text-muted);padding:2rem;">No matching log entries.</td></tr>`;
            return;
        }
        const reversed = [...logs].reverse();
        const renderRow = currentLogSource === 'proxy' ? renderProxyRow : renderManagerRow;
        tbody.innerHTML = reversed.map(renderRow).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

function startLogAutoRefresh() {
    stopLogAutoRefresh();
    const checkbox = document.getElementById('log-auto-refresh');
    if (checkbox && checkbox.checked) {
        logAutoRefreshTimer = setInterval(() => {
            const logsTab = document.getElementById('tab-logs');
            if (logsTab && logsTab.classList.contains('active')) {
                loadLogs();
            } else {
                stopLogAutoRefresh();
            }
        }, 3000);
    }
}

function stopLogAutoRefresh() {
    if (logAutoRefreshTimer) {
        clearInterval(logAutoRefreshTimer);
        logAutoRefreshTimer = null;
    }
}

document.querySelectorAll('.log-subtab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.log-subtab').forEach(b => {
            b.classList.remove('btn-primary');
            b.classList.add('btn-secondary');
            b.classList.remove('active');
        });
        btn.classList.add('btn-primary', 'active');
        btn.classList.remove('btn-secondary');
        currentLogSource = btn.dataset.logsrc;
        updateLogTableHeader();
        loadLogs();
    });
});

document.getElementById('log-auto-refresh').addEventListener('change', e => {
    if (e.target.checked) startLogAutoRefresh();
    else stopLogAutoRefresh();
});

document.getElementById('btn-refresh-logs').addEventListener('click', loadLogs);

document.getElementById('btn-apply-filters').addEventListener('click', loadLogs);

document.getElementById('btn-clear-filters').addEventListener('click', () => {
    document.getElementById('filter-ip').value = '';
    document.getElementById('filter-method').value = '';
    document.getElementById('filter-path').value = '';
    document.getElementById('filter-time-from').value = '';
    document.getElementById('filter-time-to').value = '';
    loadLogs();
});

// Apply filters on Enter in text inputs
document.querySelectorAll('#filter-ip, #filter-path').forEach(input => {
    input.addEventListener('keydown', e => { if (e.key === 'Enter') loadLogs(); });
});

// --- Init ---
loadRoutes();
