// Multi-Agent System Frontend JavaScript

// Global variables
const API = 'http://localhost:8000';
let seenLogs = new Set();
let activeChips = new Set();
let pollTimer = null;
let isTaskRunning = false; // Flag to prevent UI interruption during task execution
let uploadedFileId = null; // Track uploaded file

// Chart instances
let tasksChart = null;
let performanceChart = null;

// ── INITIALIZATION ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  // Initialize character counter
  const taskInput = document.getElementById('task-input');
  if (taskInput) {
    taskInput.addEventListener('input', handleCharCounter);
  }
  
  // Initialize file upload
  initializeFileUpload();
  
  // Initialize system
  checkHealth();
  loadHistory();
  loadAnalytics();
  initializeCharts();
});

// ── CHARACTER COUNTER ────────────────────────────────────────────
function handleCharCounter() {
  const taskInput = document.getElementById('task-input');
  const n = Math.min(taskInput.value.length, 500);
  document.getElementById('char-count').textContent = n + ' / 500 chars';
  if (taskInput.value.length > 500) {
    taskInput.value = taskInput.value.slice(0, 500);
  }
}

// ── FILE UPLOAD ───────────────────────────────────────────────────
function initializeFileUpload() {
  const uploadArea = document.getElementById('upload-area');
  const fileInput = document.getElementById('file-input');
  
  if (!uploadArea || !fileInput) return;
  
  // Click to upload
  uploadArea.addEventListener('click', () => {
    fileInput.click();
  });
  
  // Drag and drop
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
  });
  
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
  });
  
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });
  
  // File input change
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  // Validate file type
  const validTypes = ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/json'];
  const validExtensions = ['.csv', '.xlsx', '.json'];
  
  const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
  if (!validExtensions.includes(fileExtension)) {
    alert('Please upload a CSV, Excel (.xlsx), or JSON file');
    return;
  }
  
  // Validate file size (10MB max)
  if (file.size > 10 * 1024 * 1024) {
    alert('File size must be less than 10MB');
    return;
  }
  
  // Create FormData
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    // Show loading state
    const uploadArea = document.getElementById('upload-area');
    uploadArea.innerHTML = '<div class="upload-icon">⏳</div><div class="upload-title">Uploading...</div>';
    
    // Upload file
    const response = await fetch(API + '/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('Upload failed');
    }
    
    const result = await response.json();
    
    // Store file ID
    uploadedFileId = result.file_id;
    
    // Show file preview
    showFilePreview(file.name, result);
    
  } catch (error) {
    console.error('Upload error:', error);
    alert('Failed to upload file. Please try again.');
    
    // Reset upload area
    resetUploadArea();
  }
}

function showFilePreview(fileName, data) {
  const uploadArea = document.getElementById('upload-area');
  const filePreview = document.getElementById('file-preview');
  const fileNameEl = document.getElementById('file-name');
  const dataPreview = document.getElementById('file-data-preview');
  
  // Hide upload area, show preview
  uploadArea.style.display = 'none';
  filePreview.style.display = 'block';
  
  // Set file name
  fileNameEl.textContent = fileName;
  
  // Create preview table
  let tableHTML = '<table class="file-table"><thead><tr>';
  
  // Add headers
  data.columns.forEach(col => {
    tableHTML += `<th>${col}</th>`;
  });
  tableHTML += '</tr></thead><tbody>';
  
  // Add preview rows (first 5)
  data.preview.slice(0, 5).forEach(row => {
    tableHTML += '<tr>';
    data.columns.forEach(col => {
      tableHTML += `<td>${row[col] || ''}</td>`;
    });
    tableHTML += '</tr>';
  });
  
  tableHTML += '</tbody></table>';
  
  // Add summary if available
  if (data.summary) {
    tableHTML += '<div style="margin-top: 12px; padding: 8px; background: var(--surface); border-radius: 6px;">';
    tableHTML += '<div style="font-size: 0.7rem; color: var(--muted); margin-bottom: 4px;">Data Summary:</div>';
    Object.entries(data.summary).forEach(([key, value]) => {
      tableHTML += `<div style="font-size: 0.8rem;">${key}: ${value}</div>`;
    });
    tableHTML += '</div>';
  }
  
  dataPreview.innerHTML = tableHTML;
}

function removeFile() {
  uploadedFileId = null;
  resetUploadArea();
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('upload-area').style.display = 'block';
}

function resetUploadArea() {
  const uploadArea = document.getElementById('upload-area');
  uploadArea.innerHTML = `
    <div class="upload-icon">📁</div>
    <div class="upload-text">
      <div class="upload-title">Drop file here or click to upload</div>
      <div class="upload-subtitle">CSV, Excel (.xlsx), JSON (Max 10MB)</div>
    </div>
    <input type="file" id="file-input" accept=".csv,.xlsx,.json" style="display: none;">
  `;
  
  // Re-initialize file input
  const fileInput = uploadArea.querySelector('#file-input');
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

// ── HEALTH CHECK ─────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(API + '/');
    document.getElementById('api-status').textContent = r.ok ? 'API ONLINE' : 'API ERROR';
    if (!r.ok) {
      document.querySelector('.dot').style.background = 'var(--danger)';
    }
  } catch {
    document.getElementById('api-status').textContent = 'API OFFLINE';
    document.querySelector('.dot').style.background = 'var(--danger)';
  }
}

// ── TASK SUBMISSION ───────────────────────────────────────────────
async function submitTask() {
  const text = document.getElementById('task-input').value.trim();
  if (!text) { 
    document.getElementById('task-input').focus(); 
    return; 
  }

  resetUI();
  isTaskRunning = true; // Set flag to prevent UI interruption
  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Running...';

  // Progress ticker
  let prog = 0;
  const ticker = setInterval(() => {
    prog = Math.min(prog + 0.8, 88);
    document.getElementById('pbar').style.width = prog + '%';
  }, 500);

  try {
    // Step 1: Start the pipeline (returns immediately with task_id)
    const requestBody = {user_input: text};
    if (uploadedFileId) {
      requestBody.file_id = uploadedFileId;
    }
    
    const res = await fetch(API + '/task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(requestBody)
    });

    if (!res.ok) throw new Error('HTTP ' + res.status + ' ' + res.statusText);
    const startData = await res.json();
    const taskId = startData.task_id;

    // Step 2: Poll logs + status until completed
    await pollUntilDone(taskId);

    // Only refresh history and analytics after task completes
    isTaskRunning = false; // Clear flag before refreshing
    loadHistory();

  } catch (err) {
    sysLog('Error — ' + err.message);
  } finally {
    clearInterval(ticker);
    document.getElementById('pbar').style.width = '100%';
    btn.disabled = false;
    btn.innerHTML = 'Run Pipeline →';
    isTaskRunning = false; // Clear flag when task completes
  }
}

// ── POLLING ───────────────────────────────────────────────────────
async function pollUntilDone(taskId) {
  return new Promise((resolve) => {
    let attempts = 0;
    const MAX = 120; // 120 × 1s = 2 min timeout
    let lastStatus = '';

    pollTimer = setInterval(async () => {
      attempts++;

      try {
        // Fetch logs first with error handling
        try {
          const lr = await fetch(API + '/task/' + taskId + '/logs');
          if (!lr.ok) throw new Error('Logs fetch failed: ' + lr.status);
          const ld = await lr.json();
          renderLogs(ld.logs || []);
        } catch (logErr) {
          console.error('Log fetch error:', logErr.message);
        }

        // Then fetch status
        try {
          const sr = await fetch(API + '/task/' + taskId + '/status');
          if (!sr.ok) throw new Error('Status fetch failed: ' + sr.status);
          const sd = await sr.json();
          
          // Status changed to completed - fetch fresh result
          if (sd.status === 'completed' && lastStatus !== 'completed') {
            // Fetch fresh status to get the result
            const freshSr = await fetch(API + '/task/' + taskId + '/status');
            const freshSd = await freshSr.json();
            clearInterval(pollTimer);
            showResult(freshSd);
            resolve();
          }
          else if (sd.status === 'failed') {
            clearInterval(pollTimer);
            showError(sd.error || sd.reason || 'Pipeline failed');
            resolve();
          }
          else if (attempts >= MAX) {
            clearInterval(pollTimer);
            showError('Timed out waiting for pipeline to complete');
            resolve();
          }
          
          lastStatus = sd.status;
        } catch (statusErr) {
          console.error('Status fetch error:', statusErr.message);
        }

      } catch (e) {
        console.error('Poll error:', e.message);
      }

    }, 1000); // poll every 1 second for stable updates
  });
}

// ── RESULT DISPLAY ───────────────────────────────────────────────
function showResult(data) {
  document.getElementById('result-placeholder').style.display = 'none';
  const section = document.getElementById('result-section');
  section.style.display = 'block';

  // Try multiple possible result fields
  const resultText = String(data.result || data.output || data.final_result || '').trim();
  const box = document.getElementById('rbox');
  box.style.color = '';
  box.style.borderColor = '';

  // Check if result contains HTML (dashboard)
  const isHTML = resultText.includes('<html') || resultText.includes('<div') || resultText.includes('<canvas');

  if (resultText && resultText !== 'undefined' && resultText !== 'null') {
    if (isHTML) {
      // Render HTML dashboard
      box.innerHTML = resultText;
      
      // Show control buttons for HTML dashboards
      document.getElementById('expand-btn').style.display = 'inline-block';
      document.getElementById('download-btn').style.display = 'inline-block';
      document.getElementById('download-pdf-btn').style.display = 'inline-block';
      
      // Store current result for download
      window.currentDashboardHTML = resultText;
    } else {
      // Render formatted text report
      function formatReport(text) {
        return text
          .replace(/📊 EXECUTIVE SUMMARY/g, '<h3>📊 Executive Summary</h3>')
          .replace(/🔍 KEY FINDINGS/g, '<h3>🔍 Key Findings</h3>')
          .replace(/📈 ANALYSIS/g, '<h3>📈 Analysis</h3>')
          .replace(/⚠️ RISKS & LIMITATIONS/g, '<h3>⚠️ Risks & Limitations</h3>')
          .replace(/💡 STRATEGIC RECOMMENDATIONS/g, '<h3>💡 Recommendations</h3>')
          .replace(/🧾 FINAL VERDICT/g, '<h3>🧾 Final Verdict</h3>')
          .replace(/\n\n/g, '</p><p>')
          .replace(/\n/g, '<br>')
          .replace(/^/, '<p>')
          .replace(/$/, '</p>');
      }
      
      // Handle chart images
      let formattedContent = formatReport(resultText);
      if (resultText.includes(".png")) {
        formattedContent += `<img src="${resultText}" style="width:100%;margin-top:10px;border-radius:10px;">`;
      }
      
      box.innerHTML = formattedContent;
      
      // Hide HTML-only controls, show PDF export for text reports
      document.getElementById('expand-btn').style.display = 'none';
      document.getElementById('download-btn').style.display = 'none';
      document.getElementById('download-pdf-btn').style.display = 'inline-block';
    }
  } else {
    box.textContent = 'Pipeline completed but no result was returned. Check the logs for details.';
    box.style.color = 'var(--muted)';
    
    // Hide control buttons for empty results
    document.getElementById('expand-btn').style.display = 'none';
    document.getElementById('download-btn').style.display = 'none';
    document.getElementById('download-pdf-btn').style.display = 'none';
  }

  // Handle analysis
  const analysisText = String(data.analysis || data.final_analysis || '').trim();
  const pill = document.getElementById('apill');
  if (analysisText && analysisText !== 'undefined' && analysisText !== 'null') {
    pill.textContent = '✦ Analyst: ' + analysisText;
    pill.style.display = 'block';
  } else {
    pill.style.display = 'none';
  }
}

function showError(msg) {
  document.getElementById('result-placeholder').style.display = 'none';
  const section = document.getElementById('result-section');
  section.style.display = 'block';
  const box = document.getElementById('rbox');
  box.textContent = '✕ ' + msg;
  box.style.color = 'var(--danger)';
  box.style.borderColor = 'var(--danger)';
  document.getElementById('apill').style.display = 'none';
}

// ── LOGS ───────────────────────────────────────────────────────────
function renderLogs(logs) {
  const box = document.getElementById('logbox');
  let added = false;
  let newLogCount = 0;
  
  // Sort logs by timestamp to ensure proper order
  const sortedLogs = logs.sort((a, b) => new Date(a.time) - new Date(b.time));
  
  for (const log of sortedLogs) {
    const key = log.agent + '|' + log.message + '|' + log.time;
    if (seenLogs.has(key)) continue;
    seenLogs.add(key);
    added = true;
    newLogCount++;
    
    box.querySelector('.empty')?.remove();
    const row = document.createElement('div');
    row.className = 'logrow';
    const tag = document.createElement('span');
    tag.className = 'tag ' + log.agent;
    tag.textContent = log.agent.toUpperCase();
    const wrap = document.createElement('div');
    const msg = document.createElement('div'); 
    msg.className = 'lmsg'; 
    msg.textContent = log.message;
    const ts  = document.createElement('div'); 
    ts.className  = 'ltime'; 
    ts.textContent  = fmt(log.time);
    wrap.appendChild(msg); 
    wrap.appendChild(ts);
    row.appendChild(tag); 
    row.appendChild(wrap);
    box.appendChild(row);
    activateChip(log.agent);
  }
  
  if (added) {
    box.scrollTop = box.scrollHeight;
  }
}

function sysLog(msg) {
  const box = document.getElementById('logbox');
  box.querySelector('.empty')?.remove();
  const row = document.createElement('div'); 
  row.className = 'logrow';
  const tag = document.createElement('span'); 
  tag.className = 'tag SYS'; 
  tag.textContent = 'SYS';
  const wrap = document.createElement('div');
  const msg2 = document.createElement('div'); 
  msg2.className = 'lmsg'; 
  msg2.textContent = msg;
  wrap.appendChild(msg2); 
  row.appendChild(tag); 
  row.appendChild(wrap);
  box.appendChild(row); 
  box.scrollTop = box.scrollHeight;
}

// ── AGENT CHIPS ───────────────────────────────────────────────────
function activateChip(name) {
  if (activeChips.has(name)) return;
  activeChips.add(name);
  document.getElementById('chip-' + name)?.classList.add('on');
  updateAgentStatus(name, 'ACTIVE');
}

function updateAgentStatus(agentName, status) {
  const chip = document.getElementById('chip-' + agentName);
  if (chip) {
    const statusElement = chip.querySelector('.status');
    if (statusElement) {
      statusElement.textContent = status;
    }
  }
}

function resetAgentStatuses() {
  ['Planner', 'Supervisor', 'Executor', 'Analyst'].forEach(agent => {
    updateAgentStatus(agent, 'IDLE');
    document.getElementById('chip-' + agent)?.classList.remove('on');
  });
  activeChips.clear();
}

// ── HISTORY ───────────────────────────────────────────────────────
async function loadHistory() {
  // Skip refresh during active task execution to prevent UI interference
  if (isTaskRunning) {
    return;
  }
  
  try {
    const r = await fetch(API + '/tasks');
    const d = await r.json();
    const list = document.getElementById('hlist');
    const tasks = d.tasks || [];
    if (!tasks.length) { 
      list.innerHTML = '<div class="empty" style="padding:24px">No tasks yet</div>'; 
      return; 
    }
    list.innerHTML = tasks.map(t => `
      <div class="hitem" onclick="viewLogs(${t.id})">
        <span class="hid">#${t.id}</span>
        <span class="hinput">${esc(t.input)}</span>
        <span class="hst ${t.status}">${t.status}</span>
        <span class="hdate">${fmt(t.created_at)}</span>
      </div>`).join('');
    
    // Update charts with task data
    updateCharts(tasks);
    
    // Update active tasks count
    const activeTasksCount = tasks.filter(task => task.status === 'running').length;
    document.getElementById('active-tasks-count').textContent = activeTasksCount;
  } catch {
    document.getElementById('hlist').innerHTML = '<div class="empty" style="padding:24px">Could not load history</div>';
  }
  // Refresh analytics when history is loaded
  loadAnalytics();
}

async function viewLogs(taskId) {
  // Prevent interruption during active task execution
  if (isTaskRunning) {
    return;
  }
  
  // Only clear logs and chips, not the results
  if (pollTimer) { 
    clearInterval(pollTimer); 
    pollTimer = null; 
  }
  seenLogs.clear();
  resetAgentStatuses();
  document.getElementById('logbox').innerHTML = '<div class="empty">Loading logs...</div>';
  
  // Load and display the result for this task if it exists
  try {
    const sr = await fetch(API + '/task/' + taskId + '/status');
    const sd = await sr.json();
    if (sd.status === 'completed' && (sd.result || sd.analysis)) {
      showResult(sd);
    }
  } catch {}
  
  try {
    const r = await fetch(API + '/task/' + taskId + '/logs');
    const d = await r.json();
    renderLogs(d.logs || []);
  } catch {}
}

// ── UI RESET ───────────────────────────────────────────────────────
function resetUI() {
  if (pollTimer) { 
    clearInterval(pollTimer); 
    pollTimer = null; 
  }
  seenLogs.clear();
  resetAgentStatuses();
  document.getElementById('logbox').innerHTML = '<div class="empty">Running pipeline...</div>';
  document.getElementById('result-placeholder').style.display = 'block';
  document.getElementById('result-section').style.display = 'none';
  document.getElementById('apill').style.display = 'none';
  document.getElementById('pbar').style.width = '0%';
}

// ── ANALYTICS ─────────────────────────────────────────────────────
async function loadAnalytics() {
  // Skip refresh during active task execution to prevent UI interference
  if (isTaskRunning) {
    return;
  }
  
  try {
    const response = await fetch(API + '/analytics');
    const data = await response.json();
    
    if (data.error) {
      console.error('Analytics error:', data.error);
      return;
    }
    
    // Update total tasks
    document.getElementById('total-tasks').textContent = data.total_tasks || 0;
    
    // Update success rate
    const successRate = data.success_rate || 0;
    document.getElementById('success-rate').textContent = successRate.toFixed(1) + '%';
    document.getElementById('success-fill').style.width = successRate + '%';
    
    // Update average score
    const avgScore = data.avg_score || 0;
    document.getElementById('avg-score').textContent = avgScore.toFixed(1) + '/10';
    document.getElementById('score-fill').style.width = (avgScore * 10) + '%';
    
  } catch (error) {
    console.error('Failed to load analytics:', error);
    // Show error state
    document.getElementById('total-tasks').textContent = 'Error';
    document.getElementById('success-rate').textContent = '-';
    document.getElementById('avg-score').textContent = '-';
  }
}

// ── MODAL FUNCTIONS ───────────────────────────────────────────────
function expandResult() {
  const modal = document.getElementById('result-modal');
  const modalBody = document.getElementById('modal-body');
  
  // Get the current dashboard HTML
  const dashboardHTML = window.currentDashboardHTML || document.getElementById('rbox').innerHTML;
  
  // Create an iframe to display the dashboard safely
  modalBody.innerHTML = `<iframe srcdoc="${dashboardHTML.replace(/"/g, '&quot;')}" frameborder="0"></iframe>`;
  
  // Show modal
  modal.style.display = 'block';
}

function closeModal() {
  const modal = document.getElementById('result-modal');
  modal.style.display = 'none';
}

function downloadResult() {
  const dashboardHTML = window.currentDashboardHTML || document.getElementById('rbox').innerHTML;
  
  // Create a blob with the HTML content
  const blob = new Blob([dashboardHTML], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  
  // Create a temporary link and trigger download
  const a = document.createElement('a');
  a.href = url;
  a.download = `dashboard_${new Date().getTime()}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  
  // Clean up
  URL.revokeObjectURL(url);
}

async function downloadPDFResult() {
  const resultElement = document.getElementById('rbox');
  const filename = `report_${new Date().getTime()}.pdf`;

  try {
    const canvas = await html2canvas(resultElement, {
      scale: 2,
      backgroundColor: '#0a0a0f',
      useCORS: true,
      allowTaint: true
    });

    const imgData = canvas.toDataURL('image/png');
    const pdf = new window.jspdf.jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const imgProps = pdf.getImageProperties(imgData);
    const pdfWidth = pageWidth - 20;
    const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
    let position = 10;

    pdf.addImage(imgData, 'PNG', 10, position, pdfWidth, pdfHeight);

    if (pdfHeight > pageHeight - 20) {
      let heightLeft = pdfHeight - (pageHeight - 20);
      while (heightLeft > 0) {
        position = heightLeft - pdfHeight + 10;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 10, position, pdfWidth, pdfHeight);
        heightLeft -= pageHeight - 20;
      }
    }

    pdf.save(filename);
  } catch (err) {
    console.error('PDF export failed:', err);
    alert('Failed to export PDF. Please try again.');
  }
}

// Close modal when clicking outside
window.onclick = function(event) {
  const modal = document.getElementById('result-modal');
  if (event.target == modal) {
    closeModal();
  }
}

// ── UTILITY FUNCTIONS ─────────────────────────────────────────────
function fmt(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return isNaN(d) ? ts : d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── CHART FUNCTIONS ─────────────────────────────────────────────────
function initializeCharts() {
  // Check if Chart.js is loaded
  if (typeof Chart === 'undefined') {
    console.error('Chart.js is not loaded');
    return;
  }
  
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        labels: {
          color: '#e2e8f0',
          font: {
            family: 'Space Mono',
            size: 11
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          color: '#64748b',
          font: {
            family: 'Space Mono',
            size: 10
          }
        }
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        },
        ticks: {
          color: '#64748b',
          font: {
            family: 'Space Mono',
            size: 10
          }
        }
      }
    }
  };

  // Tasks Chart
  const tasksCtx = document.getElementById('tasksChart');
  if (tasksCtx) {
    tasksChart = new Chart(tasksCtx, {
      type: 'bar',
      data: {
        labels: ['Completed', 'Failed', 'Running', 'Pending'],
        datasets: [{
          label: 'Task Status',
          data: [0, 0, 0, 0],
          backgroundColor: [
            'rgba(16, 185, 129, 0.6)',
            'rgba(239, 68, 68, 0.6)',
            'rgba(245, 158, 11, 0.6)',
            'rgba(100, 116, 139, 0.6)'
          ],
          borderColor: [
            'rgba(16, 185, 129, 1)',
            'rgba(239, 68, 68, 1)',
            'rgba(245, 158, 11, 1)',
            'rgba(100, 116, 139, 1)'
          ],
          borderWidth: 1
        }]
      },
      options: chartOptions
    });
  }

  // Performance Chart
  const performanceCtx = document.getElementById('performanceChart');
  if (performanceCtx) {
    performanceChart = new Chart(performanceCtx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Task Scores',
          data: [],
          borderColor: 'rgba(124, 58, 237, 1)',
          backgroundColor: 'rgba(124, 58, 237, 0.1)',
          tension: 0.4,
          fill: true
        }]
      },
      options: {
        ...chartOptions,
        scales: {
          ...chartOptions.scales,
          y: {
            ...chartOptions.scales.y,
            min: 0,
            max: 10
          }
        }
      }
    });
  }
}

function updateCharts(tasks) {
  if (!tasks || !Array.isArray(tasks)) return;

  // Update tasks chart
  if (tasksChart) {
    const statusCounts = {
      completed: 0,
      failed: 0,
      running: 0,
      pending: 0
    };

    tasks.forEach(task => {
      if (statusCounts.hasOwnProperty(task.status)) {
        statusCounts[task.status]++;
      }
    });

    tasksChart.data.datasets[0].data = [
      statusCounts.completed,
      statusCounts.failed,
      statusCounts.running,
      statusCounts.pending
    ];
    tasksChart.update();
  }

  // Update performance chart with recent task scores
  if (performanceChart) {
    const recentTasks = tasks
      .filter(task => task.status === 'completed')
      .slice(-10)
      .reverse();

    const labels = recentTasks.map((_, index) => `Task ${index + 1}`);
    const scores = recentTasks.map(task => {
      // Extract score from analysis or use default
      const analysis = task.analysis || '';
      const scoreMatch = analysis.match(/Score:\s*(\d+)/);
      return scoreMatch ? parseInt(scoreMatch[1]) : 5;
    });

    performanceChart.data.labels = labels;
    performanceChart.data.datasets[0].data = scores;
    performanceChart.update();
  }
}

// ── EXPORT FUNCTIONS FOR GLOBAL ACCESS ─────────────────────────────
// Make functions globally accessible for inline event handlers
window.submitTask = submitTask;
window.viewLogs = viewLogs;
window.loadHistory = loadHistory;
window.removeFile = removeFile;
window.expandResult = expandResult;
window.closeModal = closeModal;
window.downloadResult = downloadResult;
