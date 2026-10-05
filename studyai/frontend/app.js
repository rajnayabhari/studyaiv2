const API_BASE = "http://localhost:8000";
let currentSessionId = localStorage.getItem('studyai_session');

// Initialize Session
async function initSession() {
    if (currentSessionId) {
        document.getElementById('sessionIdDisplay').innerText = currentSessionId.substring(0, 8) + '...';
        loadChatHistory();
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
        const data = await response.json();
        currentSessionId = data.session_id;
        localStorage.setItem('studyai_session', currentSessionId);
        document.getElementById('sessionIdDisplay').innerText = currentSessionId.substring(0, 8) + '...';
    } catch (error) {
        console.error("Failed to initialize session", error);
        document.getElementById('sessionIdDisplay').innerText = "Error initializing";
    }
}

function loadChatHistory() {
    const history = localStorage.getItem('studyai_chat');
    if (history) {
        document.getElementById('messagesContainer').innerHTML = history;
        document.getElementById('messagesContainer').scrollTop = document.getElementById('messagesContainer').scrollHeight;
    }
}

function saveChatHistory() {
    const history = document.getElementById('messagesContainer').innerHTML;
    localStorage.setItem('studyai_chat', history);
}

// File Upload Handler
document.getElementById('fileInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!currentSessionId) {
        alert("Session not initialized yet!");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', currentSessionId);

    const statusEl = document.getElementById('uploadStatus');
    const uploadBtn = document.querySelector('.upload-btn');
    
    uploadBtn.style.opacity = '0.5';
    uploadBtn.style.pointerEvents = 'none';
    statusEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing ${file.name}... (This may take a minute)`;

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        statusEl.innerHTML = `<i class="fa-solid fa-check" style="color: #4ade80;"></i> ${file.name} ready!`;
    } catch (error) {
        statusEl.innerHTML = `<i class="fa-solid fa-xmark" style="color: #ef4444;"></i> Upload failed.`;
        console.error("Upload error", error);
    } finally {
        uploadBtn.style.opacity = '1';
        uploadBtn.style.pointerEvents = 'auto';
        e.target.value = ''; // Reset input
    }
});

// Chat UI Logic
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const messagesContainer = document.getElementById('messagesContainer');
let currentEventSource = null;

chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    // Add User Message
    appendUserMessage(query);
    userInput.value = '';

    // Trigger AI Stream
    streamAIResponse(query);
});

function appendUserMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    msgDiv.innerHTML = `<div class="glass-message"><div class="message-content">${text}</div></div>`;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    saveChatHistory();
}

function streamAIResponse(query) {
    if (currentEventSource) {
        currentEventSource.close();
    }

    const aiMsgDiv = document.createElement('div');
    aiMsgDiv.className = 'message ai-message';
    const glassDiv = document.createElement('div');
    glassDiv.className = 'glass-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const citationsDiv = document.createElement('div');
    citationsDiv.className = 'citations-container';
    citationsDiv.style.display = 'none';

    glassDiv.appendChild(contentDiv);
    glassDiv.appendChild(citationsDiv);
    aiMsgDiv.appendChild(glassDiv);
    messagesContainer.appendChild(aiMsgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    let accumulatedMarkdown = "";
    
    // Create EventSource
    const url = new URL(`${API_BASE}/chat`);
    url.searchParams.append('query', query);
    url.searchParams.append('session_id', currentSessionId);
    
    currentEventSource = new EventSource(url.toString());

    currentEventSource.addEventListener('token', (e) => {
        try {
            // Data is JSON encoded to handle newlines
            const token = JSON.parse(e.data);
            accumulatedMarkdown += token;
            contentDiv.innerHTML = marked.parse(accumulatedMarkdown);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        } catch (err) {
            console.error("Token parse error", err);
        }
    });

    currentEventSource.addEventListener('citation', (e) => {
        try {
            const data = JSON.parse(e.data);
            citationsDiv.style.display = 'flex';
            
            const chip = document.createElement('span');
            chip.className = 'citation-chip';
            chip.innerHTML = `<i class="fa-regular fa-file-pdf"></i> ${data.filename} (pg. ${data.page_number})`;
            citationsDiv.appendChild(chip);
        } catch (err) {
            console.error("Citation parse error", err);
        }
    });

    currentEventSource.addEventListener('done', (e) => {
        currentEventSource.close();
        currentEventSource = null;
        saveChatHistory();
    });

    currentEventSource.onerror = (err) => {
        console.error("EventSource failed", err);
        currentEventSource.close();
        currentEventSource = null;
        saveChatHistory();
    };
}

// Start
initSession();
