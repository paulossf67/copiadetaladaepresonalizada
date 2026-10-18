// ============ CONFIGURAÇÃO GLOBAL ============
const config = {
    apiBase: window.location.origin,
    autoRefresh: true
};

let currentOperation = null;
let operationHistory = JSON.parse(localStorage.getItem('copyHistory')) || [];

// ============ INICIALIZAÇÃO ============
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadSettings();
    updateSystemStats();
    setInterval(updateSystemStats, 5000);
});

// ============ EVENT LISTENERS ============
function initializeEventListeners() {
    // Tabs
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', switchTab);
    });

    // Copy Section
    document.getElementById('btn-start-copy').addEventListener('click', startCopy);
    document.getElementById('btn-new-copy').addEventListener('click', resetCopyForm);

    // Path validation
    document.getElementById('source').addEventListener('change', () => validatePath('source'));
    document.getElementById('destination').addEventListener('change', () => validatePath('destination'));

    // Recovery
    document.getElementById('btn-check-file').addEventListener('click', checkFileAccess);

    // Settings
    document.querySelector('.settings-form .btn-success')?.addEventListener('click', saveSettings);

    // Placeholder file browsing (client-side, can be extended with Electron or backend API)
    document.getElementById('btn-browse-source').addEventListener('click', () => {
        showToast('Use o caminho completo do arquivo ou pasta', 'info');
    });
    document.getElementById('btn-browse-dest').addEventListener('click', () => {
        showToast('Use o caminho completo do destino', 'info');
    });
    document.getElementById('btn-browse-recovery').addEventListener('click', () => {
        showToast('Use o caminho completo do arquivo', 'info');
    });
}

// ============ TABS ============
function switchTab(e) {
    const tabName = e.currentTarget.dataset.tab;

    // Remove active class from all items and sections
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(section => section.classList.remove('active'));

    // Add active class to clicked item and corresponding section
    e.currentTarget.classList.add('active');
    document.getElementById(tabName).classList.add('active');

    // Load history when switching to history tab
    if (tabName === 'history') {
        displayHistory();
    }
}

// ============ PATH VALIDATION ============
async function validatePath(fieldType) {
    const input = document.getElementById(fieldType);
    const infoDiv = document.getElementById(`${fieldType}-info`);
    const path = input.value.trim();

    if (!path) {
        infoDiv.classList.remove('valid', 'invalid');
        return;
    }

    try {
        const response = await fetch(`${config.apiBase}/api/check-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });

        const data = await response.json();

        if (data.valid) {
            infoDiv.classList.add('valid');
            infoDiv.classList.remove('invalid');

            if (data.type === 'directory') {
                infoDiv.innerHTML = `
                    <i class="fas fa-check-circle"></i>
                    ${data.file_count} arquivo(s) | ${data.size_mb} MB
                `;
            } else {
                infoDiv.innerHTML = `
                    <i class="fas fa-check-circle"></i>
                    ${data.size_mb} MB
                `;
            }
        } else {
            infoDiv.classList.add('invalid');
            infoDiv.classList.remove('valid');
            infoDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.message}`;
        }
    } catch (error) {
        console.error('Erro ao validar caminho:', error);
        infoDiv.classList.add('invalid');
        infoDiv.classList.remove('valid');
        infoDiv.innerHTML = '<i class="fas fa-exclamation-circle"></i> Erro ao validar caminho';
    }
}

// ============ COPY FUNCTIONALITY ============
async function startCopy() {
    const source = document.getElementById('source').value.trim();
    const destination = document.getElementById('destination').value.trim();

    if (!source || !destination) {
        showToast('Preencha os caminhos de origem e destino', 'warning');
        return;
    }

    currentOperation = { source, destination };

    // Hide form and show progress
    document.querySelector('.copy-form').style.display = 'none';
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('completion-section').classList.add('hidden');

    // Start WebSocket connection
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws/copy`);

    ws.onopen = () => {
        ws.send(JSON.stringify({
            type: 'start_copy',
            source: source,
            destination: destination,
            operation_id: Date.now().toString()
        }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleCopyProgress(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket erro:', error);
        showToast('Erro na conexão WebSocket', 'error');
        resetCopyForm();
    };

    ws.onclose = () => {
        console.log('WebSocket fechado');
    };
}

function handleCopyProgress(data) {
    if (data.status === 'progress') {
        // Update progress bar
        const percent = data.progress_percent || 0;
        document.getElementById('progress-fill').style.width = percent + '%';
        document.getElementById('progress-percent').textContent = percent.toFixed(1) + '%';

        // Update current file
        document.getElementById('current-file-name').textContent = data.current_file;

        // Update stats
        document.getElementById('files-copied').textContent = `${data.files_copied}/${data.total_files}`;
        document.getElementById('size-copied').textContent = `${data.bytes_copied / (1024 * 1024) | 0} MB`;
        document.getElementById('copy-speed').textContent = `${data.speed_mbps} MB/s`;
        document.getElementById('elapsed-time').textContent = `${data.elapsed_time.toFixed(1)}s`;
    }
    else if (['completed', 'partial', 'failed'].includes(data.status)) {
        showCopyCompletion(data);
        if (data.status === 'completed') {
            showToast('Cópia concluída com sucesso!', 'success');
        } else {
            showToast(
                `Cópia finalizada com ${data.failed_files} arquivo(s) com erro.`,
                'warning'
            );
        }
    }
    else if (data.status === 'file_error') {
        showToast(`Erro ao copiar: ${data.file}`, 'warning');
    }
    else if (data.status === 'warning') {
        showToast(data.message, 'warning');
    }
    else if (data.status === 'error') {
        showToast(`Erro: ${data.message}`, 'error');
        resetCopyForm();
    }
}

function showCopyCompletion(data) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('completion-section').classList.remove('hidden');

    const completionCard = document.querySelector('.completion-card');
    const completionIcon = document.querySelector('.completion-icon i');
    const completionTitle = document.getElementById('completion-title');
    const hasErrors = data.failed_files > 0;
    completionCard.classList.toggle('warning', hasErrors);
    completionCard.classList.toggle('success', !hasErrors);
    completionIcon.className = hasErrors ? 'fas fa-exclamation-triangle' : 'fas fa-check-circle';
    completionTitle.textContent = hasErrors
        ? 'Cópia finalizada com erros'
        : 'Cópia Concluída com Sucesso!';

    document.getElementById('final-files').textContent = data.total_files;
    document.getElementById('final-failed-files').textContent = data.failed_files;
    document.getElementById('final-size').textContent = `${data.total_size_mb} MB`;
    document.getElementById('final-time').textContent = `${data.total_time.toFixed(2)}s`;
    document.getElementById('final-speed').textContent = `${data.average_speed_mbps} MB/s`;

    // Display file types
    const fileTypesDiv = document.getElementById('file-types');
    fileTypesDiv.innerHTML = '';

    for (const [type, count] of Object.entries(data.file_types)) {
        const item = document.createElement('div');
        item.className = 'file-type-item';
        item.innerHTML = `<div class="type">${type || 'sem extensão'}</div><div class="count">${count} arquivo(s)</div>`;
        fileTypesDiv.appendChild(item);
    }

    // Save to history
    const historyItem = {
        timestamp: data.timestamp,
        source: currentOperation?.source,
        destination: currentOperation?.destination,
        files: data.total_files,
        failed_files: data.failed_files,
        size_mb: data.total_size_mb,
        time_seconds: data.total_time,
        speed_mbps: data.average_speed_mbps
    };

    operationHistory.unshift(historyItem);
    localStorage.setItem('copyHistory', JSON.stringify(operationHistory.slice(0, 50)));
}

function resetCopyForm() {
    document.querySelector('.copy-form').style.display = 'block';
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('completion-section').classList.add('hidden');
    document.getElementById('source').value = '';
    document.getElementById('destination').value = '';
    document.getElementById('source-info').classList.remove('valid', 'invalid');
    document.getElementById('dest-info').classList.remove('valid', 'invalid');
    currentOperation = null;
}

document.getElementById('btn-new-copy').addEventListener('click', resetCopyForm);

// ============ FILE ACCESS ============
async function checkFileAccess() {
    const filePath = document.getElementById('recovery-file').value.trim();

    if (!filePath) {
        showToast('Informe o caminho do arquivo', 'warning');
        return;
    }

    const resultDiv = document.getElementById('recovery-result');
    resultDiv.classList.remove('hidden');

    const cardDiv = document.getElementById('recovery-card');
    cardDiv.innerHTML = '<div style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Verificando...</div>';

    try {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws/copy`);

        ws.onopen = () => {
            ws.send(JSON.stringify({
                type: 'check_file',
                file_path: filePath
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            displayRecoveryResult(data);
            ws.close();
        };

        ws.onerror = () => {
            showToast('Erro ao verificar arquivo', 'error');
        };
    } catch (error) {
        showToast('Erro: ' + error.message, 'error');
    }
}

function displayRecoveryResult(data) {
    const cardDiv = document.getElementById('recovery-card');

    if (data.status === 'accessible') {
        cardDiv.className = 'card recovery-card healthy';
        cardDiv.innerHTML = `
            <h3><i class="fas fa-check-circle"></i> Arquivo Acessível</h3>
            <div class="info">
                <strong>Arquivo:</strong> ${data.file}
            </div>
            <div class="info">
                <strong>Tamanho:</strong> ${data.size} bytes
            </div>
            <div class="info">
                <strong>Status:</strong> Leitura completa bem-sucedida. Isso não verifica se o conteúdo está íntegro.
            </div>
        `;
    } else if (data.status === 'unreadable') {
        cardDiv.className = 'card recovery-card corrupted';
        cardDiv.innerHTML = `
            <h3><i class="fas fa-exclamation-triangle"></i> Não foi possível ler o arquivo</h3>
            <div class="info">
                <strong>Arquivo:</strong> ${data.file}
            </div>
            <div class="info">
                <strong>Erro:</strong> ${data.error}
            </div>
        `;
    } else if (data.status === 'not_found') {
        cardDiv.className = 'card recovery-card corrupted';
        cardDiv.innerHTML = `
            <h3><i class="fas fa-times-circle"></i> Arquivo Não Encontrado</h3>
            <div class="info">
                ${data.message}
            </div>
        `;
    } else if (data.status === 'not_file') {
        cardDiv.className = 'card recovery-card corrupted';
        cardDiv.innerHTML = `
            <h3><i class="fas fa-times-circle"></i> Caminho inválido</h3>
            <div class="info">
                ${data.message}
            </div>
        `;
    }
}

// ============ HISTORY ============
function displayHistory() {
    const historyList = document.getElementById('history-list');

    if (operationHistory.length === 0) {
        historyList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>Nenhuma operação registrada ainda</p>
            </div>
        `;
        return;
    }

    historyList.innerHTML = operationHistory.map((item, index) => `
        <div class="history-item">
            <div class="history-item-header">
                <span class="history-item-title">#${index + 1} - Cópia realizada</span>
                <span class="history-item-time">${new Date(item.timestamp).toLocaleString('pt-BR')}</span>
            </div>
            <div class="history-item-stats">
                <div class="history-stat">
                    <span>Arquivos:</span>
                    <span>${item.files}</span>
                </div>
                <div class="history-stat">
                    <span>Tamanho:</span>
                    <span>${item.size_mb} MB</span>
                </div>
                <div class="history-stat">
                    <span>Tempo:</span>
                    <span>${item.time_seconds.toFixed(2)}s</span>
                </div>
                <div class="history-stat">
                    <span>Velocidade:</span>
                    <span>${item.speed_mbps} MB/s</span>
                </div>
            </div>
        </div>
    `).join('');
}

// ============ SETTINGS ============
function saveSettings() {
    const settings = {
        notifyCompletion: document.getElementById('notify-completion').checked,
        notifyErrors: document.getElementById('notify-errors').checked,
        preserveTimestamps: document.getElementById('preserve-timestamps').checked,
        autoClear: document.getElementById('auto-clear').checked,
        theme: document.getElementById('theme-select').value
    };

    localStorage.setItem('appSettings', JSON.stringify(settings));
    showToast('Configurações salvas com sucesso!', 'success');
}

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('appSettings')) || {
        notifyCompletion: true,
        notifyErrors: true,
        preserveTimestamps: true,
        autoClear: true,
        theme: 'auto'
    };

    document.getElementById('notify-completion').checked = settings.notifyCompletion;
    document.getElementById('notify-errors').checked = settings.notifyErrors;
    document.getElementById('preserve-timestamps').checked = settings.preserveTimestamps;
    document.getElementById('auto-clear').checked = settings.autoClear;
    document.getElementById('theme-select').value = settings.theme;
}

// ============ SYSTEM STATS ============
async function updateSystemStats() {
    try {
        const response = await fetch(`${config.apiBase}/api/system-info`);
        const data = await response.json();

        document.getElementById('memory-usage').textContent =
            `MEM: ${data.memory.available}/${data.memory.total}GB (${data.memory.percent}%)`;
        document.getElementById('disk-usage').textContent =
            `DISK: ${data.disk.free}/${data.disk.total}GB (${data.disk.percent}%)`;
    } catch (error) {
        console.error('Erro ao atualizar stats:', error);
    }
}

// ============ TOAST NOTIFICATIONS ============
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
`;
document.head.appendChild(style);
