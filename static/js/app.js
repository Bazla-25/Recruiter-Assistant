// Application State
const AppState = {
    mode: 'job_seeker',
    resumeUploaded: false,
    jobDescriptionSet: false,
    candidateName: 'Candidate'
};

// DOM Elements
const elements = {
    modeOptions: document.querySelectorAll('.mode-option'),
    resumeUpload: document.getElementById('resumeUpload'),
    resumeFile: document.getElementById('resumeFile'),
    resumeStatus: document.getElementById('resumeStatus'),
    coverLetterUpload: document.getElementById('coverLetterUpload'),
    coverLetterFile: document.getElementById('coverLetterFile'),
    coverLetterStatus: document.getElementById('coverLetterStatus'),
    jobDescription: document.getElementById('jobDescription'),
    jobDescriptionStatus: document.getElementById('jobDescriptionStatus'),
    overallStatus: document.getElementById('overallStatus'),
    atsAnalysisBtn: document.getElementById('atsAnalysisBtn'),
    clearChatBtn: document.getElementById('clearChatBtn'),
    chatMessages: document.getElementById('chatMessages'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    chatTitle: document.getElementById('chatTitle'),
    atsModal: document.getElementById('atsModal'),
    closeModal: document.getElementById('closeModal'),
    atsResults: document.getElementById('atsResults')
};

// Utility Functions
function showStatus(element, message, type = 'info') {
    const iconClass = type === 'success' ? 'check-circle' : 
                     type === 'error' ? 'exclamation-circle' : 
                     type === 'warning' ? 'exclamation-triangle' : 'info-circle';
    
    element.innerHTML = `
        <div class="status-message status-${type}">
            <i class="fas fa-${iconClass}"></i>
            ${message}
        </div>
    `;
}

function updateOverallStatus() {
    const { overallStatus } = elements;
    
    if (AppState.resumeUploaded && AppState.jobDescriptionSet) {
        showStatus(overallStatus, '✅ Ready to chat! All documents uploaded successfully', 'success');
        elements.messageInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.atsAnalysisBtn.disabled = false;
    } else if (AppState.resumeUploaded) {
        showStatus(overallStatus, '⚠️ Almost ready! Please add job description', 'warning');
    } else {
        showStatus(overallStatus, '📋 Please upload resume and job description to start', 'warning');
    }
}

function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'message-user' : 'message-ai'}`;
    messageDiv.innerHTML = isUser ? content : `<strong>AI:</strong> ${content}`;
    
    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message message-ai loading';
    loadingDiv.id = 'loadingMessage';
    loadingDiv.innerHTML = '<strong>AI:</strong> <i class="fas fa-spinner fa-spin"></i> Thinking...';
    elements.chatMessages.appendChild(loadingDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function hideLoading() {
    const loadingMsg = document.getElementById('loadingMessage');
    if (loadingMsg) loadingMsg.remove();
}

// Event Handlers
function handleModeChange(selectedMode) {
    AppState.mode = selectedMode;
    
    // Update UI
    elements.modeOptions.forEach(option => {
        option.classList.remove('active');
        option.querySelector('input').checked = false;
    });
    
    const selectedOption = document.querySelector(`[data-mode="${selectedMode}"]`);
    selectedOption.classList.add('active');
    selectedOption.querySelector('input').checked = true;

    // Update chat title
    const modeText = selectedMode === 'job_seeker' ? 
        'Job Seeker Mode - AI will interview you' : 
        'HR Recruiter Mode - AI acts as candidate';
    elements.chatTitle.innerHTML = `<i class="fas fa-comments"></i> ${modeText}`;

    // Clear chat and notify backend
    fetch('/api/clear-chat', { method: 'POST' })
        .then(() => {
            elements.chatMessages.innerHTML = `
                <div class="message message-ai">
                    <strong>AI Assistant:</strong> Mode switched to ${modeText}! ${AppState.resumeUploaded && AppState.jobDescriptionSet ? "Let's start the interview!" : "Please ensure resume and job description are uploaded."}
                </div>
            `;
        });

    fetch('/api/set-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: selectedMode })
    });
}

function setupFileUpload(uploadArea, fileInput, statusElement, endpoint, isRequired = true) {
    // Click to upload
    uploadArea.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            fileInput.files = files;
            handleFileUpload(files[0], statusElement, endpoint, isRequired);
        } else if (files.length > 0) {
            showStatus(statusElement, '❌ Please upload PDF files only', 'error');
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0], statusElement, endpoint, isRequired);
        }
    });
}

function handleFileUpload(file, statusElement, endpoint, isRequired) {
    showStatus(statusElement, '📤 Uploading...', 'info');

    const formData = new FormData();
    formData.append(endpoint.includes('resume') ? 'resume' : 'cover_letter', file);

    fetch(`/api/${endpoint}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (endpoint.includes('resume')) {
                AppState.resumeUploaded = true;
                AppState.candidateName = data.candidate_name || 'Candidate';
                showStatus(statusElement, `✅ Resume uploaded! Detected name: ${AppState.candidateName}`, 'success');
            } else {
                showStatus(statusElement, `✅ ${data.message}`, 'success');
            }
            updateOverallStatus();
        } else {
            showStatus(statusElement, `❌ ${data.error}`, 'error');
        }
    })
    .catch(error => {
        showStatus(statusElement, `❌ Upload failed: ${error.message}`, 'error');
    });
}

function handleJobDescriptionChange() {
    const jobDesc = elements.jobDescription.value.trim();
    
    fetch('/api/job-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_description: jobDesc })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            AppState.jobDescriptionSet = jobDesc.length > 0;
            showStatus(elements.jobDescriptionStatus, 
                jobDesc.length > 0 ? '✅ Job description updated!' : '⚠️ Job description cleared', 
                jobDesc.length > 0 ? 'success' : 'warning'
            );
            updateOverallStatus();
        }
    })
    .catch(error => {
        showStatus(elements.jobDescriptionStatus, `❌ Error: ${error.message}`, 'error');
    });
}

function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message) return;

    // Disable input while processing
    elements.messageInput.disabled = true;
    elements.sendBtn.disabled = true;

    // Add user message
    addMessage(message, true);
    elements.messageInput.value = '';

    // Show loading
    showLoading();

    // Send to backend
    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.response) {
            addMessage(data.response);
        } else {
            addMessage(`❌ ${data.error || 'Unknown error occurred'}`);
        }
    })
    .catch(error => {
        hideLoading();
        addMessage(`❌ Error: ${error.message}`);
    })
    .finally(() => {
        // Re-enable input
        elements.messageInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    });
}

function performATSAnalysis() {
    elements.atsAnalysisBtn.disabled = true;
    elements.atsAnalysisBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

    fetch('/api/ats-analysis')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(`❌ ${data.error}`);
        } else {
            displayATSResults(data);
            elements.atsModal.style.display = 'block';
        }
    })
    .catch(error => {
        alert(`❌ Analysis failed: ${error.message}`);
    })
    .finally(() => {
        elements.atsAnalysisBtn.disabled = false;
        elements.atsAnalysisBtn.innerHTML = '<i class="fas fa-chart-line"></i> ATS Analysis';
    });
}

function displayATSResults(data) {
    const score = data.ats_score || 0;
    let scoreClass = 'score-needs-improvement';
    if (score >= 80) scoreClass = 'score-excellent';
    else if (score >= 60) scoreClass = 'score-good';

    elements.atsResults.innerHTML = `
        <div class="ats-score">
            <div class="score-circle ${scoreClass}">
                ${score}/100
            </div>
            <h3>ATS Compatibility Score</h3>
        </div>

        <div class="ats-results">
            <h4><i class="fas fa-lightbulb"></i> Recommendations</h4>
            <ul>
                ${(data.recommendations || ['No recommendations available']).map(rec => `<li>${rec}</li>`).join('')}
            </ul>

            <h4><i class="fas fa-check-circle" style="color: var(--success);"></i> Strengths</h4>
            <ul>
                ${(data.strengths || ['Analysis completed']).map(strength => `<li>${strength}</li>`).join('')}
            </ul>

            <h4><i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i> Areas for Improvement</h4>
            <ul>
                ${(data.weaknesses || ['See recommendations above']).map(weakness => `<li>${weakness}</li>`).join('')}
            </ul>

            <div class="keyword-grid">
                <div>
                    <h4><i class="fas fa-tags" style="color: var(--success);"></i> Matching Keywords</h4>
                    <div class="keyword-tags">
                        ${(data.keyword_matches || ['Analysis completed']).map(keyword => 
                            `<span class="keyword-tag match">${keyword}</span>`
                        ).join('')}
                    </div>
                </div>
                <div>
                    <h4><i class="fas fa-times-circle" style="color: var(--danger);"></i> Missing Keywords</h4>
                    <div class="keyword-tags">
                        ${(data.missing_keywords || ['See analysis above']).map(keyword => 
                            `<span class="keyword-tag missing">${keyword}</span>`
                        ).join('')}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function clearChat() {
    fetch('/api/clear-chat', { method: 'POST' })
    .then(() => {
        elements.chatMessages.innerHTML = `
            <div class="message message-ai">
                <strong>AI Assistant:</strong> Chat cleared! Feel free to start a new conversation.
            </div>
        `;
    })
    .catch(error => {
        console.error('Error clearing chat:', error);
    });
}

// Initialize Event Listeners
function initializeApp() {
    // Mode selection
    elements.modeOptions.forEach(option => {
        option.addEventListener('click', (e) => {
            const mode = option.dataset.mode;
            handleModeChange(mode);
        });
    });

    // File uploads
    setupFileUpload(elements.resumeUpload, elements.resumeFile, elements.resumeStatus, 'upload-resume', true);
    setupFileUpload(elements.coverLetterUpload, elements.coverLetterFile, elements.coverLetterStatus, 'upload-cover-letter', false);

    // Job description
    elements.jobDescription.addEventListener('input', debounce(handleJobDescriptionChange, 1000));

    // Chat functionality
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Actions
    elements.atsAnalysisBtn.addEventListener('click', performATSAnalysis);
    elements.clearChatBtn.addEventListener('click', clearChat);

    // Modal
    elements.closeModal.addEventListener('click', () => {
        elements.atsModal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === elements.atsModal) {
            elements.atsModal.style.display = 'none';
        }
    });

    // Initial focus
    elements.messageInput.focus();
}

// Debounce utility
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize app when DOM loads
document.addEventListener('DOMContentLoaded', initializeApp);