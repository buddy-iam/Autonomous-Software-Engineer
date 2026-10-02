lucide.createIcons();

let threadId = Math.random().toString(36).substring(7);
let selectedFiles = [];
let isPaused = false;
let isWaitingForResponse = false;

const settingsPanel = document.getElementById('settingsPanel');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const promptInput = document.getElementById('promptInput');
const emptyState = document.getElementById('emptyState');
const chatHistory = document.getElementById('chatHistory');
const chatContainer = document.getElementById('chatContainer');
const approvalBanner = document.getElementById('approvalBanner');
const sendBtn = document.getElementById('sendBtn');

function toggleSettings() { settingsPanel.classList.toggle('hidden'); }
function scrollToBottom() { chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' }); }

function resetSession() {
    if(!confirm("Start a new session? This will clear the current chat history.")) return;
    threadId = Math.random().toString(36).substring(7);
    selectedFiles = [];
    isPaused = false;
    promptInput.value = '';
    fileList.innerHTML = '';
    chatHistory.innerHTML = '';
    chatHistory.appendChild(emptyState);
    emptyState.classList.remove('hidden');
    approvalBanner.classList.add('hidden');
    promptInput.placeholder = "Describe the feature or project...";
    promptInput.style.height = 'auto';
}

function handleFiles() {
    Array.from(fileInput.files).forEach(file => {
        selectedFiles.push(file);
        const span = document.createElement('span');
        span.className = "flex items-center gap-1 text-xs bg-gray-800 px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 whitespace-nowrap";
        span.innerHTML = `<i data-lucide="file" class="w-3 h-3 text-blue-400"></i> ${file.name}`;
        fileList.appendChild(span);
    });
    fileInput.value = ""; 
    lucide.createIcons();
}

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function appendUserMessage(text, files) {
    emptyState.classList.add('hidden');
    let fileHtml = '';
    if (files && files.length > 0) {
        fileHtml = `<div class="flex flex-wrap gap-2 mb-2">`;
        files.forEach(f => fileHtml += `<span class="text-xs bg-blue-700/50 px-2 py-1 rounded-md border border-blue-600/50 flex items-center gap-1"><i data-lucide="file-text" class="w-3 h-3"></i> ${f.name}</span>`);
        fileHtml += `</div>`;
    }
    const html = `<div class="self-end bg-blue-600 text-white rounded-2xl rounded-tr-sm px-5 py-4 max-w-[85%] md:max-w-[75%] shadow-md">${fileHtml}<div class="text-sm leading-relaxed whitespace-pre-wrap">${escapeHtml(text)}</div></div>`;
    chatHistory.insertAdjacentHTML('beforeend', html);
    lucide.createIcons();
    scrollToBottom();
}

function appendAgentLoading() {
    const id = 'loading-' + Date.now();
    const html = `<div id="${id}" class="self-start bg-gray-900 border border-gray-800 text-gray-100 rounded-2xl rounded-tl-sm px-6 py-5 w-full max-w-3xl shadow-lg flex items-center gap-4"><i data-lucide="loader-2" class="w-5 h-5 animate-spin text-blue-500"></i><span class="text-sm text-gray-400 animate-pulse">Agency Swarm is processing...</span></div>`;
    chatHistory.insertAdjacentHTML('beforeend', html);
    lucide.createIcons();
    scrollToBottom();
    return id;
}

function appendAgentMessage(data) {
    let contentHtml = '';
    
    if (data.chat_response) {
        contentHtml += `<div class="prose prose-invert prose-blue prose-sm max-w-none">${marked.parse(data.chat_response)}</div>`;
    }
    
    if (data.plan) {
        contentHtml += `
            <div class="mb-4">
                <h3 class="text-blue-400 font-semibold mb-3 flex items-center gap-2 border-b border-gray-800 pb-2"><i data-lucide="clipboard-list" class="w-4 h-4"></i> Architecture Blueprint</h3>
                <div class="prose prose-invert prose-blue prose-sm max-w-none prose-tables:border-collapse prose-td:border prose-td:border-gray-700 prose-th:border prose-th:border-gray-700 prose-th:bg-gray-800">${marked.parse(data.plan)}</div>
            </div>`;
    }

    if (data.code_files && Object.keys(data.code_files).length > 0) {
        contentHtml += `<div class="mt-6 border-t border-gray-800 pt-6"><h3 class="text-green-400 font-semibold mb-4 flex items-center gap-2"><i data-lucide="check-circle-2" class="w-4 h-4"></i> Final Generated Code</h3>`;
        if (data.github_url) contentHtml += `<a href="${data.github_url}" target="_blank" class="inline-flex items-center gap-2 text-sm bg-[#2ea043] hover:bg-[#2c974b] text-white px-4 py-2.5 rounded-lg mb-6 transition shadow-lg"><i data-lucide="github" class="w-4 h-4"></i> View PR on GitHub</a>`;
        
        for (const [filename, code] of Object.entries(data.code_files)) {
            if (filename === "error.txt") {
                contentHtml += `<div class="bg-red-900/20 border border-red-800 p-4 rounded-xl text-red-300 text-sm">${escapeHtml(code)}</div>`;
            } else {
                contentHtml += `
                    <div class="mb-6 rounded-xl overflow-hidden border border-gray-700 shadow-md">
                        <div class="bg-gray-800 px-4 py-2.5 border-b border-gray-700 flex items-center gap-2"><i data-lucide="file-code" class="w-4 h-4 text-gray-400"></i><span class="text-xs text-gray-300 font-mono">${escapeHtml(filename)}</span></div>
                        <pre class="bg-gray-950 p-4 text-xs text-gray-300 overflow-x-auto font-mono leading-relaxed">${escapeHtml(code)}</pre>
                    </div>`;
            }
        }
        contentHtml += `</div>`;
    }

    const html = `<div class="self-start bg-gray-900 border border-gray-800 text-gray-100 rounded-2xl rounded-tl-sm p-6 w-full max-w-4xl shadow-lg">${contentHtml}</div>`;
    chatHistory.insertAdjacentHTML('beforeend', html);
    lucide.createIcons();
    scrollToBottom();
}

function handleApprove() {
    appendUserMessage("✅ Approved. Proceed with the build phase.", []);
    callBackend("approve", null);
}

function handleSend() {
    if (isWaitingForResponse) return;
    const promptText = promptInput.value.trim();
    if (!promptText && selectedFiles.length === 0) return;
    
    const action = isPaused ? "feedback" : "start";
    appendUserMessage(promptText, selectedFiles);
    promptInput.value = '';
    promptInput.style.height = 'auto';
    callBackend(action, promptText);
}

async function callBackend(action, promptText = "") {
    const backendUrl = document.getElementById('backendUrl').value.replace(/\/$/, "");
    const githubToken = document.getElementById('githubToken').value;
    const githubRepo = document.getElementById('githubRepo').value;

    if (!backendUrl) return alert("Please provide your Cloudflared Backend URL in settings.");

    isWaitingForResponse = true;
    approvalBanner.classList.add('hidden');
    sendBtn.disabled = true;
    const loadingId = appendAgentLoading();

    const formData = new FormData();
    formData.append("thread_id", threadId);
    formData.append("action", action);
    if (promptText) formData.append("prompt", promptText);
    if (githubToken) formData.append("github_token", githubToken);
    if (githubRepo) formData.append("github_repo", githubRepo);
    selectedFiles.forEach(f => formData.append("files", f));

    try {
        const response = await fetch(`${backendUrl}/api/chat`, { method: 'POST', body: formData });
        if (!response.ok) throw new Error("Backend connection failed.");
        
        const data = await response.json();
        document.getElementById(loadingId).remove();
        appendAgentMessage(data);
        
        isPaused = data.is_paused;
        selectedFiles = [];
        fileList.innerHTML = '';

        if (isPaused) {
            approvalBanner.classList.remove('hidden');
            promptInput.placeholder = "Request changes to the plan...";
        } else {
            promptInput.placeholder = "Describe the feature or project...";
        }
    } catch (error) {
        document.getElementById(loadingId).remove();
        chatHistory.insertAdjacentHTML('beforeend', `<div class="self-center bg-red-900/50 text-red-200 border border-red-700 px-4 py-2 rounded-lg text-sm">Connection Error: Ensure your FastAPI server and Cloudflare tunnel are running.</div>`);
    } finally {
        isWaitingForResponse = false;
        sendBtn.disabled = false;
        scrollToBottom();
    }
}