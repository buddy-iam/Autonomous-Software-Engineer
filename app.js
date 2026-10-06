const THREAD_ID = "session_12345"; // Static ID for testing, change to dynamic if needed
let editorInstance = null;
let activeFile = null;
let workspaceFiles = {};

// Initialize Monaco Editor
require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
require(['vs/editor/editor.main'], function() {
    editorInstance = monaco.editor.create(document.getElementById('monaco-container'), {
        value: '// Your generated code will appear here...\n',
        language: 'javascript',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false }
    });
});

async function refreshWorkspace() {
    try {
        const response = await fetch(`http://localhost:8000/api/workspace/${THREAD_ID}`);
        const data = await response.json();
        workspaceFiles = data.code_files;
        renderTabs();
    } catch (e) {
        console.error("Failed to fetch workspace", e);
    }
}

function renderTabs() {
    const tabsContainer = document.getElementById('file-tabs');
    tabsContainer.innerHTML = '';
    
    Object.keys(workspaceFiles).forEach(filename => {
        const tab = document.createElement('div');
        tab.innerText = filename;
        tab.style.cursor = 'pointer';
        tab.style.padding = '8px 12px';
        tab.style.borderRadius = '4px 4px 0 0';
        tab.style.background = activeFile === filename ? '#333' : '#222';
        tab.style.borderBottom = activeFile === filename ? '2px solid #007acc' : 'none';
        
        tab.onclick = () => openFile(filename);
        tabsContainer.appendChild(tab);
    });

    // Auto-open the first file if none is active
    if (!activeFile && Object.keys(workspaceFiles).length > 0) {
        openFile(Object.keys(workspaceFiles)[0]);
    }
}

function openFile(filename) {
    activeFile = filename;
    let language = 'javascript';
    if (filename.endsWith('.html')) language = 'html';
    if (filename.endsWith('.css')) language = 'css';
    if (filename.endsWith('.py')) language = 'python';

    if (editorInstance) {
        monaco.editor.setModelLanguage(editorInstance.getModel(), language);
        editorInstance.setValue(workspaceFiles[filename] || '');
    }
    renderTabs();
}

async function saveCurrentFile() {
    if (!activeFile || !editorInstance) return;
    
    const content = editorInstance.getValue();
    workspaceFiles[activeFile] = content; 

    try {
        const response = await fetch('http://localhost:8000/api/workspace/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                thread_id: THREAD_ID,
                filename: activeFile,
                content: content
            })
        });
        
        if (response.ok) {
            alert(`${activeFile} saved to AI Memory!`);
        }
    } catch (e) {
        alert("Failed to save to backend.");
    }
}

async function sendMessage(action) {
    const inputElement = document.getElementById('chat-input');
    const input = inputElement.value;
    const historyDiv = document.getElementById('chat-history');
    
    if (input) {
        historyDiv.innerHTML += `<p><strong>You:</strong> ${input}</p>`;
    }
    
    inputElement.value = '';
    historyDiv.scrollTop = historyDiv.scrollHeight;
    
    const formData = new FormData();
    formData.append("thread_id", THREAD_ID);
    formData.append("action", action);
    formData.append("prompt", input);

    try {
        const res = await fetch("http://localhost:8000/api/chat", {
            method: "POST",
            body: formData
        });
        
        const data = await res.json();
        
        // Render Markdown/Code properly (using basic regex for now, you can add marked.js later)
        let formattedResponse = data.chat_response.replace(/\n/g, '<br>');
        historyDiv.innerHTML += `<p><strong>AI:</strong> ${formattedResponse}</p>`;
        historyDiv.scrollTop = historyDiv.scrollHeight;
        
        await refreshWorkspace();
    } catch (e) {
        historyDiv.innerHTML += `<p style="color:red;"><strong>Error:</strong> Failed to connect to server.</p>`;
    }
}