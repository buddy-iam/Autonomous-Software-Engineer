const THREAD_ID = "session_12345";
let BACKEND_URL = localStorage.getItem("agent_backend_url") || "http://localhost:8000";

let editorInstance = null;
let activeFile = null;
let workspaceFiles = {};
let saveTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    const urlInput = document.getElementById("backend-url");
    if (urlInput) urlInput.value = BACKEND_URL;
});

function saveBackendUrl() {
    const input = document.getElementById("backend-url").value.trim().replace(/\/$/, "");
    if (input) {
        BACKEND_URL = input;
        localStorage.setItem("agent_backend_url", BACKEND_URL);
        refreshWorkspace();
    }
}

require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
require(['vs/editor/editor.main'], function() {
    editorInstance = monaco.editor.create(document.getElementById('monaco-container'), {
        value: '// Your generated code will appear here...\n',
        language: 'javascript',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        padding: { top: 16 }
    });

    editorInstance.onDidChangeModelContent(() => {
        const status = document.getElementById('save-status');
        status.innerText = "Saving changes...";
        status.style.color = "#e2b93d"; 
        
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => { autoSaveFile(); }, 1000); 
    });

    refreshWorkspace();
});

async function autoSaveFile() {
    if (!activeFile || !editorInstance) return;
    const content = editorInstance.getValue();
    workspaceFiles[activeFile] = content; 

    try {
        const response = await fetch(`${BACKEND_URL}/api/workspace/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thread_id: THREAD_ID, filename: activeFile, content: content })
        });
        
        const status = document.getElementById('save-status');
        if (response.ok) {
            status.innerText = "All changes saved to AI memory";
            status.style.color = "#2ea043"; 
        } else {
            status.innerText = "Save failed";
            status.style.color = "#f85149"; 
        }
    } catch (e) {
        document.getElementById('save-status').innerText = "Offline";
    }
}

async function refreshWorkspace() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/workspace/${THREAD_ID}`);
        if (!response.ok) return;
        const data = await response.json();
        workspaceFiles = data.code_files || {};
        
        // Split UI dynamically if code exists
        if (Object.keys(workspaceFiles).length > 0) {
            document.body.classList.add('is-coding');
        }
        
        renderTabs();
    } catch (e) {
        console.error("Workspace fetch error:", e);
    }
}

function renderTabs() {
    const tabsContainer = document.getElementById('file-tabs');
    tabsContainer.innerHTML = '';
    
    const fileKeys = Object.keys(workspaceFiles);
    
    fileKeys.forEach(filename => {
        const tab = document.createElement('div');
        tab.className = `file-tab ${activeFile === filename ? 'active' : ''}`;
        tab.innerText = filename;
        tab.onclick = () => openFile(filename);
        tabsContainer.appendChild(tab);
    });

    if (fileKeys.length > 0 && (!activeFile || !workspaceFiles[activeFile])) {
        openFile(fileKeys[0]);
    }
}

function openFile(filename) {
    activeFile = filename;
    
    let language = 'javascript';
    if (filename.endsWith('.html')) language = 'html';
    else if (filename.endsWith('.css')) language = 'css';
    else if (filename.endsWith('.py')) language = 'python';
    else if (filename.endsWith('.json')) language = 'json';

    if (editorInstance) {
        const currentModel = editorInstance.getModel();
        monaco.editor.setModelLanguage(currentModel, language);
        editorInstance.setValue(workspaceFiles[filename] || '');
        document.getElementById('save-status').innerText = "All changes saved to AI memory";
        document.getElementById('save-status').style.color = "#2ea043";
    }
    
    renderTabs();
}

async function sendMessage(action) {
    const inputElement = document.getElementById('chat-input');
    const input = inputElement.value.trim();
    const historyDiv = document.getElementById('chat-history');

    if (action === 'start' && !input) return;

    // 1. Render User Message
    if (input) {
        historyDiv.innerHTML += `<div class="msg user-msg">${input}</div>`;
    } else if (action === 'approve') {
        historyDiv.innerHTML += `<div class="msg user-msg"><em>Approved next step</em></div>`;
    }

    inputElement.value = '';
    historyDiv.scrollTop = historyDiv.scrollHeight;

    // 2. Render "Thinking..." Indicator
    const typingId = "typing-" + Date.now();
    historyDiv.innerHTML += `
        <div class="msg ai-msg" id="${typingId}">
            <div class="typing-indicator">
                Thinking <div class="dot"></div><div class="dot"></div><div class="dot"></div>
            </div>
        </div>
    `;
    historyDiv.scrollTop = historyDiv.scrollHeight;

    const formData = new FormData();
    formData.append("thread_id", THREAD_ID);
    formData.append("action", action);
    formData.append("prompt", input);

    try {
        // 3. Wait for Backend
        const res = await fetch(`${BACKEND_URL}/api/chat`, { method: "POST", body: formData });
        const data = await res.json();

        // 4. Remove "Thinking..." Indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        // 5. Parse Markdown and Render Final AI Message
        // Fallback to basic string replacement if marked fails to load
        let formattedResponse = typeof marked !== 'undefined' 
            ? marked.parse(data.chat_response || "") 
            : (data.chat_response || "").replace(/\n/g, '<br>');

        historyDiv.innerHTML += `<div class="msg ai-msg">${formattedResponse}</div>`;
        historyDiv.scrollTop = historyDiv.scrollHeight;

        await refreshWorkspace();
    } catch (e) {
        // Remove typing indicator on error
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        
        historyDiv.innerHTML += `<div class="msg error-msg">Error: Failed to connect to server.</div>`;
        historyDiv.scrollTop = historyDiv.scrollHeight;
    }
}