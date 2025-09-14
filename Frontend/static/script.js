// Theme Management
function initializeTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
    
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

// File size formatter
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Upload form functionality
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const analyzeBtn = document.querySelector('.analyze-btn');
    const fileLabel = document.querySelector('.file-input-label');
    const progress = document.getElementById('progress');
    const error = document.getElementById('error');
    const filePreview = document.getElementById('filePreview');
    const removeFileBtn = document.getElementById('removeFile');

    // Initialize theme
    initializeTheme();

    // Enable button when file is selected
    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        analyzeBtn.disabled = !file;
        
        if (file) {
            showFilePreview(file);
        } else {
            hideFilePreview();
        }
    });

    // Remove file functionality
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            fileInput.value = '';
            analyzeBtn.disabled = true;
            hideFilePreview();
        });
    }

    // Drag and drop functionality
    fileLabel.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('dragover');
    });

    fileLabel.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
    });

    fileLabel.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            analyzeBtn.disabled = false;
            updateUploadText(files[0].name);
        }
    });

    // Form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Home Q&A (retrieve without upload)
    const qaHomeForm = document.getElementById('qaHomeForm');
    const qaHomeQuestion = document.getElementById('qaHomeQuestion');
    const qaHomePidInput = document.getElementById('qaHomePatientId');
    const qaHomeTopK = document.getElementById('qaHomeTopK');
    const qaHomeResult = document.getElementById('qaHomeResult');
    const patientIdInput = document.getElementById('patientId');
    if (qaHomeForm) {
        // Prefill from patientId input
        if (qaHomePidInput && patientIdInput && patientIdInput.value) {
            qaHomePidInput.value = patientIdInput.value.trim();
        }

        qaHomeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('qaHomeSubmit');
            try {
                const payload = {
                    patient_id: (qaHomePidInput.value || '').trim() || null,
                    question: (qaHomeQuestion.value || '').trim(),
                    top_k: parseInt((qaHomeTopK.value || '5'), 10)
                };
                if (!payload.question) return;

                // Show loading
                btn.querySelector('.btn-content').style.display = 'none';
                btn.querySelector('.btn-loader').style.display = 'flex';
                btn.disabled = true;
                qaHomeResult.textContent = '';

                const resp = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.detail || 'Query failed');

                qaHomeResult.innerHTML = `
                    <div class="result-card" style="margin-top: 12px;">
                        <h3>Answer</h3>
                        <div>${escapeHtml(data.answer || '')}</div>
                        <div style="margin-top:8px; color: var(--text-muted); font-size: 0.85rem;">Snippets used: ${data.snippets_used}</div>
                    </div>
                `;
            } catch (err) {
                qaHomeResult.innerHTML = `
                    <div class="error-section">
                        <div class="error-message">
                            <div class="error-icon">⚠️</div>
                            <div class="error-content">
                                <div class="error-title">Q&A Error</div>
                                <div class="error-text">${escapeHtml(err.message || 'Something went wrong')}</div>
                            </div>
                        </div>
                    </div>
                `;
            } finally {
                btn.querySelector('.btn-content').style.display = 'flex';
                btn.querySelector('.btn-loader').style.display = 'none';
                btn.disabled = false;
            }
        });
    }

    function showFilePreview(file) {
        const uploadContent = document.querySelector('.upload-content');
        const fileName = filePreview.querySelector('.file-name');
        const fileSize = filePreview.querySelector('.file-size');
        
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        
        uploadContent.style.display = 'none';
        filePreview.style.display = 'block';
        
        // Add success animation
        fileLabel.style.borderColor = 'var(--success)';
        fileLabel.style.background = 'rgb(16 185 129 / 0.05)';
    }

    function hideFilePreview() {
        const uploadContent = document.querySelector('.upload-content');
        
        uploadContent.style.display = 'flex';
        filePreview.style.display = 'none';
        
        // Reset styles
        fileLabel.style.borderColor = '';
        fileLabel.style.background = '';
    }

    async function handleUpload(e) {
        e.preventDefault();
        
        const formData = new FormData();
        const file = fileInput.files[0];
        const patientId = document.getElementById('patientId') ? document.getElementById('patientId').value.trim() : '';
        
        if (!file) {
            showError('Please select a file');
            return;
        }

        formData.append('file', file);

        // Show progress
        showProgress();
        hideError();

        try {
            const url = patientId ? `/upload?patient_id=${encodeURIComponent(patientId)}` : '/upload';
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                // Store results and redirect
                sessionStorage.setItem('analysisResults', JSON.stringify(result));
                window.location.href = '/results';
            } else {
                throw new Error(result.detail || 'Upload failed');
            }
        } catch (err) {
            console.error('Upload error:', err);
            showError(err.message || 'An error occurred while processing your file');
        } finally {
            hideProgress();
        }
    }

    function showProgress() {
        progress.style.display = 'block';
        analyzeBtn.querySelector('.btn-content').style.display = 'none';
        analyzeBtn.querySelector('.btn-loader').style.display = 'flex';
        analyzeBtn.disabled = true;
        
        // Animate progress steps
        animateProgressSteps();
    }

    function hideProgress() {
        progress.style.display = 'none';
        analyzeBtn.querySelector('.btn-content').style.display = 'flex';
        analyzeBtn.querySelector('.btn-loader').style.display = 'none';
        analyzeBtn.disabled = false;
    }

    function animateProgressSteps() {
        const steps = document.querySelectorAll('.step');
        steps.forEach((step, index) => {
            setTimeout(() => {
                steps.forEach(s => s.classList.remove('active'));
                step.classList.add('active');
            }, index * 1000);
        });
    }

    function showError(message) {
        error.style.display = 'block';
        error.querySelector('.error-text').textContent = message;
        
        // Auto-hide error after 5 seconds
        setTimeout(() => {
            hideError();
        }, 5000);
    }

    function hideError() {
        error.style.display = 'none';
    }
});

// Navigation functionality for results page
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.result-card');
    
    // Smooth scroll to sections
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetSection = document.getElementById(targetId);
            
            if (targetSection) {
                targetSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update active nav item
                navItems.forEach(nav => nav.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });
    
    // Intersection Observer for active nav highlighting
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                const correspondingNav = document.querySelector(`[href="#${id}"]`);
                if (correspondingNav) {
                    navItems.forEach(nav => nav.classList.remove('active'));
                    correspondingNav.classList.add('active');
                }
            }
        });
    }, {
        rootMargin: '-20% 0px -70% 0px'
    });
    
    sections.forEach(section => {
        if (section.id) {
            observer.observe(section);
        }
    });
}

// Enhanced share functionality
function initializeShare() {
    const shareBtn = document.getElementById('btnShare');
    if (shareBtn) {
        shareBtn.addEventListener('click', async () => {
            const resultsData = sessionStorage.getItem('analysisResults');
            if (!resultsData) return;
            
            const results = JSON.parse(resultsData);
            const shareData = {
                title: 'Medical Report Analysis Results',
                text: `Analysis results for ${results.filename || 'medical report'}`,
                url: window.location.href
            };
            
            try {
                if (navigator.share) {
                    await navigator.share(shareData);
                } else {
                    // Fallback: copy URL to clipboard
                    await navigator.clipboard.writeText(window.location.href);
                    shareBtn.innerHTML = '<span class="btn-icon">✅</span><span>Copied!</span>';
                    setTimeout(() => {
                        shareBtn.innerHTML = '<span class="btn-icon">📤</span><span>Share</span>';
                    }, 2000);
                }
            } catch (err) {
                console.log('Share failed:', err);
            }
        });
    }
}

// Results page functionality
function displayResults() {
    const resultsContainer = document.getElementById('results-content');
    if (!resultsContainer) return;

    const resultsData = sessionStorage.getItem('analysisResults');
    
    if (!resultsData) {
        resultsContainer.innerHTML = `
            <div class="error-section">
                <div class="error-message">
                    No analysis results found. Please upload a file first.
                </div>
            </div>
        `;
        return;
    }

    const results = JSON.parse(resultsData);
    const a = results.analysis || {};

    // Helper builders
    const buildList = (title, items, id) => !items || items.length === 0 ? '' : `
        <div class="result-card" ${id ? `id="${id}"` : ''}>
            <h3>${title}</h3>
            <ul style="list-style: none; padding: 0;">
                ${items.map(i => `<li style="padding: 8px 0; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; gap: 8px;">
                    <span style="color: var(--accent-primary);">•</span>
                    ${escapeHtml(i)}
                </li>`).join('')}
            </ul>
        </div>`;

    const buildTable = (title, rows, headers, id) => !rows || rows.length === 0 ? '' : `
        <div class="result-card" ${id ? `id="${id}"` : ''}>
            <h3>${title}</h3>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
                    <tbody>
                        ${rows.map(r => `<tr>
                            <td><strong>${escapeHtml(r.name || '')}</strong></td>
                            <td>${escapeHtml(r.value || r.status || r.action || r.dose || '')}</td>
                            <td>${escapeHtml(r.unit || r.timeframe || r.frequency || r.severity || r.reference || '')}</td>
                            <td>
                                ${escapeHtml(r.notes || '')} 
                                ${r.flag ? `<span class="flag-${r.flag}" style="margin-left: 8px; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">${r.flag.toUpperCase()}</span>` : ''}
                            </td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            </div>
        </div>`;

    const patientBlock = a.patient ? `
        <div class="result-card two-col" id="patient-info">
            <div><strong>Patient Information</strong><br>
            Name: ${escapeHtml(a.patient.name || '—')}<br>
            Age: ${escapeHtml(a.patient.age || '—')}<br>
            Sex: ${escapeHtml(a.patient.sex || '—')}<br>
            UHID: ${escapeHtml(a.patient.uhid || '—')}<br>
            MRN: ${escapeHtml(a.patient.mrn || '—')}</div>
            <div><strong>Encounter Details</strong><br>
            Admission: ${escapeHtml((a.encounter && a.encounter.admission_date) || '—')}<br>
            Discharge: ${escapeHtml((a.encounter && a.encounter.discharge_date) || '—')}<br>
            Department: ${escapeHtml((a.encounter && a.encounter.department) || '—')}<br>
            Discharge Type: ${escapeHtml((a.encounter && a.encounter.discharge_type) || '—')}</div>
        </div>` : '';

    const summaryBlock = a.summary ? `
        <div class="result-card" id="summary">
            <h3>🔍 Clinical Summary</h3>
            <div class="analysis-text">${escapeHtml(a.summary)}</div>
        </div>` : '';

    const diagnosesBlock = buildTable('🏥 Diagnoses', a.diagnoses, ['Name', 'Status', 'Severity', ''], 'diagnoses');
    const vitalsBlock = buildTable('💓 Vital Signs', a.vitals, ['Vital', 'Value', 'Unit', 'Flag'], 'vitals');
    const labsBlock = buildTable('🧪 Laboratory Results', a.labs, ['Test', 'Value', 'Reference/Unit', 'Flag'], 'labs');
    const proceduresBlock = buildList('⚕️ Procedures Performed', a.procedures, 'procedures');
    const imagingBlock = buildList('🔬 Imaging Findings', a.imaging_findings, 'imaging');
    const redFlagsBlock = buildList('🚨 Red Flags', a.red_flags, 'red-flags');
    const keyFindingsBlock = buildList('📋 Key Clinical Findings', a.key_findings, 'key-findings');
    const recommendationsBlock = buildList('💡 AI Recommendations', a.recommendations, 'recommendations');
    const followUpBlock = buildTable('📅 Follow-up Plan', a.follow_up, ['Action', 'Details', 'Timeline', 'Notes'], 'follow-up');
    const medsBlock = buildTable('💊 Medications', a.medications, ['Medication', 'Dosage', 'Frequency', 'Notes'], 'medications');
    const lifestyleBlock = !a.lifestyle || a.lifestyle.length === 0 ? '' : `
        <div class="result-card" id="lifestyle">
            <h3>🌱 Lifestyle Recommendations</h3>
            <div class="insights-grid">
                ${a.lifestyle.map(i => `
                    <div class="insight-card priority-low">
                        <div class="insight-category">${escapeHtml(i.category)}</div>
                        <div class="insight-recommendation">${escapeHtml(i.suggestion)}</div>
                    </div>
                `).join('')}
            </div>
        </div>`;
    const disclaimerBlock = a.disclaimer ? `
        <div class="result-card" id="disclaimer">
            <h3>⚠️ Important Disclaimer</h3>
            <div class="analysis-text" style="background: rgb(245 158 11 / 0.1); padding: 16px; border-radius: 8px; border-left: 4px solid var(--warning);">
                ${escapeHtml(a.disclaimer)}
            </div>
        </div>` : '';

    const rawToggle = `
        <div class="result-card">
            <h3>📄 Extracted Text</h3>
            <details>
                <summary>Show/Hide raw extracted text</summary>
                <div class="extracted-text">${escapeHtml(results.extracted_text)}</div>
            </details>
        </div>`;

    resultsContainer.innerHTML = `
        <div class="results-section">
            ${patientBlock}
            ${summaryBlock}
            ${diagnosesBlock}
            ${vitalsBlock}
            ${labsBlock}
            ${proceduresBlock}
            ${imagingBlock}
            ${redFlagsBlock}
            ${keyFindingsBlock}
            ${recommendationsBlock}
            ${followUpBlock}
            ${medsBlock}
            ${lifestyleBlock}
            ${disclaimerBlock}
            ${rawToggle}
            <div class="result-card">
                <h3>💡 Health Insights</h3>
                <div class="insights-grid">
                    ${results.insights.map(insight => `
                        <div class="insight-card priority-${insight.priority.toLowerCase()}">
                            <div class="insight-category">${escapeHtml(insight.category)}</div>
                            <div class="insight-recommendation">${escapeHtml(insight.recommendation)}</div>
                            <div class="priority-badge priority-${insight.priority.toLowerCase()}">
                                ${insight.priority} Priority
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    // Actions
    const btnPrint = document.getElementById('btnPrint');
    const btnCopyJson = document.getElementById('btnCopyJson');
    
    if (btnPrint) {
        btnPrint.onclick = () => window.print();
    }
    
    if (btnCopyJson) {
        btnCopyJson.onclick = async () => {
            try {
                await navigator.clipboard.writeText(JSON.stringify(results.analysis, null, 2));
                const originalHTML = btnCopyJson.innerHTML;
                btnCopyJson.innerHTML = '<span class="btn-icon">✅</span><span>Copied!</span>';
                btnCopyJson.style.background = 'var(--success)';
                btnCopyJson.style.color = 'white';
                
                setTimeout(() => {
                    btnCopyJson.innerHTML = originalHTML;
                    btnCopyJson.style.background = '';
                    btnCopyJson.style.color = '';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy:', err);
                btnCopyJson.innerHTML = '<span class="btn-icon">❌</span><span>Failed</span>';
                setTimeout(() => {
                    btnCopyJson.innerHTML = '<span class="btn-icon">📋</span><span>Copy JSON</span>';
                }, 2000);
            }
        };
    }
    
    // Initialize share functionality
    initializeShare();

    // Prefill Q&A patient ID from results
    try {
        const qaPid = document.getElementById('qaPatientId');
        if (qaPid && results.patient_id) {
            qaPid.value = results.patient_id;
        }
    } catch {}

    // Q&A form
    const qaForm = document.getElementById('qaForm');
    const qaQuestion = document.getElementById('qaQuestion');
    const qaTopK = document.getElementById('qaTopK');
    const qaResult = document.getElementById('qaResult');
    if (qaForm) {
        qaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('qaSubmit');
            try {
                const payload = {
                    patient_id: (document.getElementById('qaPatientId').value || '').trim() || null,
                    question: (qaQuestion.value || '').trim(),
                    top_k: parseInt(qaTopK.value || '5', 10)
                };
                if (!payload.question) return;

                // Show loading
                btn.querySelector('.btn-content').style.display = 'none';
                btn.querySelector('.btn-loader').style.display = 'flex';
                btn.disabled = true;
                qaResult.textContent = '';

                const resp = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.detail || 'Query failed');

                qaResult.innerHTML = `
                    <div class="result-card" style="margin-top: 12px;">
                        <h3>Answer</h3>
                        <div>${escapeHtml(data.answer || '')}</div>
                        <div style="margin-top:8px; color: var(--text-muted); font-size: 0.85rem;">Snippets used: ${data.snippets_used}</div>
                    </div>
                `;
            } catch (err) {
                qaResult.innerHTML = `
                    <div class="error-section">
                        <div class="error-message">
                            <div class="error-icon">⚠️</div>
                            <div class="error-content">
                                <div class="error-title">Q&A Error</div>
                                <div class="error-text">${escapeHtml(err.message || 'Something went wrong')}</div>
                            </div>
                        </div>
                    </div>
                `;
            } finally {
                btn.querySelector('.btn-content').style.display = 'flex';
                btn.querySelector('.btn-loader').style.display = 'none';
                btn.disabled = false;
            }
        });
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}