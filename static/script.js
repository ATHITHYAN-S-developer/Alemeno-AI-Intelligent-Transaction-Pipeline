const API_BASE = '/api/';
const fileInput = document.getElementById('fileInput');
const refreshBtn = document.getElementById('refreshBtn');
const modalOverlay = document.getElementById('modalOverlay');
const modalContent = document.getElementById('modalContent');
const closeModal = document.getElementById('closeModal');
const uploadProcessModal = document.getElementById('uploadProcessModal');
const processFileName = document.getElementById('processFileName');

let currentView = 'overview';
let myChart = null;

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

// Routing / View Switching
const navBtns = document.querySelectorAll('.nav-btn');
const views = document.querySelectorAll('.view');

function switchView(viewName) {
    views.forEach(v => v.classList.add('hidden'));
    navBtns.forEach(b => b.classList.remove('active'));
    
    document.getElementById(`${viewName}View`).classList.remove('hidden');
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
    
    currentView = viewName;
    document.getElementById('viewTitle').textContent = viewName === 'overview' ? 'Dashboard Overview' : (viewName === 'jobs' ? 'Job History' : 'Anomalies');
    
    if (viewName === 'overview') {
        loadDashboardData();
    } else if (viewName === 'jobs') {
         loadJobsTable();
    } else {
        loadAnomalies();
    }
}

navBtns.forEach(btn => {
    btn.onclick = () => switchView(btn.dataset.view);
});

// File Upload
fileInput.onchange = async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadProcessModal.classList.remove('hidden');
    processFileName.textContent = file.name;

    try {
        const response = await fetch(`${API_BASE}jobs/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        // Short delay to show processing animation
        setTimeout(() => {
            uploadProcessModal.classList.add('hidden');
            switchView('jobs');
        }, 1500);
        
    } catch (err) {
        alert('Upload failed');
        uploadProcessModal.classList.add('hidden');
    }
};

// Dashboard Logic
async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE}jobs?status=completed`);
        const jobs = await response.json();
        
        // Update stats from the latest completed job
        if (jobs.length > 0) {
            const latestJob = jobs[0];
            const resultsResp = await fetch(`${API_BASE}jobs/${latestJob.id}/results`);
            const results = await resultsResp.json();
            
            updateStatsUI(results.summaries);
            renderCategoryChart(results.cleaned_transactions);
        } else {
            document.getElementById('activeJobsList').innerHTML = '<p class="text-muted">No jobs processed yet. Upload a CSV to begin!</p>';
        }
        
        loadActiveJobs();
    } catch (err) {
        console.error('Error loading dashboard:', err);
    }
}

function updateStatsUI(summary) {
    document.getElementById('dashTotalInr').textContent = `₹${summary?.total_spend_inr?.toLocaleString() || 0}`;
    document.getElementById('dashTotalUsd').textContent = `$${summary?.total_spend_usd?.toLocaleString() || 0}`;
    document.getElementById('dashAnomalies').textContent = summary?.anomaly_count || 0;
}

function renderCategoryChart(transactions) {
    const ctx = document.getElementById('categoryChart').getContext('2d');
    
    const catTotals = {};
    transactions.forEach(t => {
        catTotals[t.category] = (catTotals[t.category] || 0) + 1;
    });

    const data = {
        labels: Object.keys(catTotals),
        datasets: [{
            data: Object.values(catTotals),
            backgroundColor: [
                '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
            ],
            borderWidth: 0
        }]
    };

    if (myChart) myChart.destroy();
    
    myChart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            }
        }
    });
}

async function loadActiveJobs() {
    const list = document.getElementById('activeJobsList');
    try {
        const response = await fetch(`${API_BASE}jobs`);
        const jobs = await response.json();
        
        list.innerHTML = jobs.slice(0, 5).map(job => `
            <div class="compact-item">
                <div>
                    <div style="font-weight:600; font-size:0.9rem">${escapeHtml(job.filename)}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted)">${new Date(job.created_at).toLocaleTimeString()}</div>
                </div>
                <span class="badge ${getStatusClass(job.status)}">${escapeHtml(job.status)}</span>
            </div>
        `).join('');
    } catch (err) {}
}

// Job History Table Filter
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.onclick = () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        loadJobsTable(btn.dataset.status);
    };
});

async function loadJobsTable(status = 'all') {
    const container = document.getElementById('jobsTableList');
    try {
        const url = status === 'all' ? `${API_BASE}jobs` : `${API_BASE}jobs?status=${status}`;
        const response = await fetch(url);
        const jobs = await response.json();
        
        if (jobs.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:40px">
                    <p class="text-muted">No files uploaded yet.</p>
                    <button class="small-btn" style="width:auto; margin-top:15px" onclick="document.getElementById('fileInput').click()">Upload Your First CSV</button>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Filename</th>
                        <th>Date</th>
                        <th>Rows</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${jobs.map(job => `
                        <tr>
                            <td><strong>${escapeHtml(job.filename)}</strong></td>
                            <td>${new Date(job.created_at).toLocaleDateString()}</td>
                            <td style="font-size:0.85rem">
                                <div style="font-weight:600">${job.row_count_clean?.toLocaleString() || 0} cleaned</div>
                                <div class="text-muted" style="font-size:0.75rem">from ${job.row_count_raw?.toLocaleString() || 0} raw</div>
                            </td>
                            <td><span class="badge ${getStatusClass(job.status)}">${escapeHtml(job.status)}</span></td>
                            <td>
                                <button class="small-btn" style="padding:5px 12px; width:auto" ${job.status === 'pending' || job.status === 'failed' ? 'disabled' : ''} onclick="viewResults('${job.id}')">
                                    ${job.status === 'processing' ? 'Live View' : 'View Results'}
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (err) {}
}

async function loadAnomalies() {
    const list = document.getElementById('anomaliesBody');
    try {
        const response = await fetch(`${API_BASE}jobs?status=completed`);
        const jobs = await response.json();
        
        if (jobs.length > 0) {
            const resultsResp = await fetch(`${API_BASE}jobs/${jobs[0].id}/results`);
            const data = await resultsResp.json();
            const anomalies = data.cleaned_transactions.filter(t => t.is_anomaly);
            
            list.innerHTML = anomalies.map(t => `
                <tr>
                    <td>${escapeHtml(t.date)}</td>
                    <td><strong>${escapeHtml(t.merchant)}</strong></td>
                    <td>${escapeHtml(t.currency)} ${escapeHtml(t.amount)}</td>
                    <td>${escapeHtml(t.category)}</td>
                    <td style="color:var(--danger); font-weight:600">${escapeHtml(t.anomaly_reason || 'Statistical Anomaly')}</td>
                </tr>
            `).join('') || '<tr><td colspan="5" style="text-align:center">No anomalies detected in the latest job.</td></tr>';
        } else {
            list.innerHTML = '<tr><td colspan="5" style="text-align:center">No completed jobs yet.</td></tr>';
        }
    } catch (err) {}
}

function getStatusClass(status) {
    if (status === 'completed') return 'tag-success';
    if (status === 'failed') return 'tag-error';
    return 'tag-warning';
}

async function viewResults(jobId) {
    modalOverlay.classList.remove('hidden');
    modalContent.innerHTML = '<div class="loader">Loading results...</div>';
    
    try {
        const response = await fetch(`${API_BASE}jobs/${jobId}/results`);
        const data = await response.json();
        
        const summary = data.summaries || {};
        const allTxns = data.cleaned_transactions || [];
        const categories = [...new Set(allTxns.map(t => t.category))].sort();

        modalContent.innerHTML = `
            <h2 style="margin-bottom:30px">Execution Summary: ${escapeHtml(jobId.slice(0,8))}</h2>
            <div class="stats-row" style="margin-bottom:30px">
                <div class="stat-card" style="box-shadow:none; background:#f1f5f9">
                    <span class="stat-label">Total Spend</span>
                    <div class="stat-value">₹${summary.total_spend_inr?.toLocaleString() || 0}</div>
                </div>
                <div class="stat-card" style="box-shadow:none; background:#fef2f2">
                    <span class="stat-label">Anomalies Detected</span>
                    <div class="stat-value" style="color:var(--danger)">${summary.anomaly_count || 0}</div>
                </div>
                 <div class="stat-card" style="box-shadow:none; background:#f0f9ff">
                    <span class="stat-label">Risk Level</span>
                    <div class="stat-value">${escapeHtml(summary.risk_level?.toUpperCase() || 'LOW')}</div>
                </div>
            </div>

            <div class="narrative-box" style="background:#f8fafc; border:1px solid var(--border); border-left:4px solid var(--primary); padding:20px; border-radius:12px; margin-bottom:30px">
                <h4 style="margin-bottom:10px">AI Deep Insights</h4>
                <p style="font-size:0.95rem; line-height:1.6">${escapeHtml(summary.narrative || 'Narrative not available.')}</p>
            </div>

            <div class="card-header">
                <h3>Transactions</h3>
                <div style="display:flex; gap:10px">
                    <select id="modalCatFilter" class="glass-select" style="padding:5px; border-radius:8px">
                        <option value="all">All Categories</option>
                        ${categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
                    </select>
                </div>
            </div>
            
            <div style="max-height:400px; overflow-y:auto; border:1px solid var(--border); border-radius:12px">
                <table>
                    <thead>
                        <tr>
                            <th>Merchant</th>
                            <th>Amount</th>
                            <th>Category</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="modalTxnsBody"></tbody>
                </table>
            </div>
        `;

        const renderModalTxns = () => {
            const cat = document.getElementById('modalCatFilter').value;
            const filtered = allTxns.filter(t => cat === 'all' || t.category === cat);
            
            document.getElementById('modalTxnsBody').innerHTML = filtered.map(t => `
                <tr>
                    <td>${escapeHtml(t.merchant)}</td>
                    <td>${escapeHtml(t.currency)} ${escapeHtml(t.amount)}</td>
                    <td>${escapeHtml(t.category)}</td>
                    <td>${t.is_anomaly ? '<span style="color:var(--danger); font-weight:600">!! ANOMALY</span>' : '<span style="color:var(--success)">Normal</span>'}</td>
                </tr>
            `).join('');
        };

        document.getElementById('modalCatFilter').onchange = renderModalTxns;
        renderModalTxns();

    } catch (err) {
        modalContent.innerHTML = 'Error loading results.';
    }
}

closeModal.onclick = () => modalOverlay.classList.add('hidden');
refreshBtn.onclick = () => currentView === 'overview' ? loadDashboardData() : loadJobsTable();

// Initial Load
switchView('overview');

// Live Progress Tracker
setInterval(() => {
    if (currentView === 'overview') {
        loadActiveJobs();
    } else if (currentView === 'jobs') {
        // Only auto-refresh if there's an active/processing job to save bandwidth
        const processingJob = document.querySelector('.tag-warning');
        if (processingJob) {
            loadJobsTable(document.querySelector('.filter-btn.active').dataset.status);
        }
    }
}, 3000);
