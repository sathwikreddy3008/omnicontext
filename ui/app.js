document.addEventListener('DOMContentLoaded', () => {
    fetchStats();

    // DOM Elements
    const chatHistory = document.getElementById('chat-history');
    const queryInput = document.getElementById('query-input');
    const askBtn = document.getElementById('ask-btn');
    const ingestPath = document.getElementById('ingest-path');
    const ingestUrl = document.getElementById('ingest-url');
    const ingestPdfFile = document.getElementById('ingest-pdf-file');
    
    const ingestBtn = document.getElementById('ingest-btn');
    const ingestUrlBtn = document.getElementById('ingest-url-btn');
    const ingestPdfBtn = document.getElementById('ingest-pdf-btn');
    
    const clearBtn = document.getElementById('clear-btn');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const contextContent = document.getElementById('context-content');
    const ingestStatus = document.getElementById('ingest-status');
    const ingestType = document.getElementById('ingest-type');
    
    // Memory Browser Elements
    const memoryList = document.getElementById('memory-list');
    const memorySearch = document.getElementById('memory-search');
    const memorySearchBtn = document.getElementById('memory-search-btn');
    const memoryRefreshBtn = document.getElementById('memory-refresh-btn');
    const noteInput = document.getElementById('note-input');
    const addNoteBtn = document.getElementById('add-note-btn');
    const noteStatus = document.getElementById('note-status');

    // Tab Elements
    const chatView = document.getElementById('chat-view');
    const memoriesView = document.getElementById('memories-view');
    const navTabs = document.querySelectorAll('.nav-tab');

    // Tab Switching
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const target = tab.dataset.tab;
            if (target === 'chat') {
                chatView.classList.remove('hidden');
                memoriesView.classList.add('hidden');
                queryInput.focus();
            } else {
                chatView.classList.add('hidden');
                memoriesView.classList.remove('hidden');
                loadMemories();
                contextContent.innerHTML = '<p class="empty-state">No context retrieved yet.</p>';
            }
        });
    });

    // Enter key support
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAsk();
    });
    memorySearch.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchMemories();
    });

    // Ingestion Dropdown Logic
    ingestType.addEventListener('change', (e) => {
        document.getElementById('ingest-folder-group').classList.add('hidden');
        document.getElementById('ingest-url-group').classList.add('hidden');
        document.getElementById('ingest-pdf-group').classList.add('hidden');
        
        document.getElementById(`ingest-${e.target.value}-group`).classList.remove('hidden');
        ingestStatus.innerText = '';
    });

    askBtn.addEventListener('click', handleAsk);
    ingestBtn.addEventListener('click', handleIngestFolder);
    ingestUrlBtn.addEventListener('click', handleIngestUrl);
    ingestPdfBtn.addEventListener('click', handleIngestPdf);
    clearBtn.addEventListener('click', handleClear);
    clearChatBtn.addEventListener('click', handleClearChat);
    memorySearchBtn.addEventListener('click', searchMemories);
    memoryRefreshBtn.addEventListener('click', loadMemories);
    addNoteBtn.addEventListener('click', handleAddNote);

    // ===== Stats =====
    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('memory-count').innerText = data.count;
        } catch (e) {
            console.error("Failed to fetch stats", e);
        }
    }

    // ===== Ingestion =====
    function setIngestStatus(msg, type) {
        ingestStatus.innerText = msg;
        ingestStatus.className = `status-msg ${type}`;
    }

    async function handleIngestFolder() {
        const path = ingestPath.value.trim();
        if(!path) return;

        ingestBtn.disabled = true;
        setIngestStatus('Scanning directory...', '');

        try {
            const res = await fetch('/api/ingest', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path})
            });
            const data = await res.json();
            
            if(res.ok) {
                setIngestStatus(data.message, 'success');
                fetchStats();
            } else {
                setIngestStatus(data.detail || 'Error', 'error');
            }
        } catch (e) {
            setIngestStatus('Server error', 'error');
        }
        ingestBtn.disabled = false;
    }

    async function handleIngestUrl() {
        const url = ingestUrl.value.trim();
        if(!url) return;

        ingestUrlBtn.disabled = true;
        setIngestStatus('Scraping URL...', '');

        try {
            const res = await fetch('/api/ingest_url', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });
            const data = await res.json();
            
            if(res.ok) {
                setIngestStatus(data.message, 'success');
                ingestUrl.value = '';
                fetchStats();
            } else {
                setIngestStatus(data.detail || 'Error', 'error');
            }
        } catch (e) {
            setIngestStatus('Server error', 'error');
        }
        ingestUrlBtn.disabled = false;
    }

    async function handleIngestPdf() {
        const file = ingestPdfFile.files[0];
        if(!file) return;

        ingestPdfBtn.disabled = true;
        setIngestStatus('Parsing PDF...', '');

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch('/api/ingest_pdf', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if(res.ok) {
                setIngestStatus(data.message, 'success');
                ingestPdfFile.value = '';
                fetchStats();
            } else {
                setIngestStatus(data.detail || 'Error', 'error');
            }
        } catch (e) {
            setIngestStatus('Server error', 'error');
        }
        ingestPdfBtn.disabled = false;
    }

    // ===== Clear Memory =====
    async function handleClear() {
        if(!confirm("Are you sure you want to permanently delete all memories?")) return;
        try {
            await fetch('/api/clear', { method: 'POST' });
            fetchStats();
            contextContent.innerHTML = '<p class="empty-state">No context retrieved yet.</p>';
            memoryList.innerHTML = '<p class="empty-state">All memories cleared.</p>';
        } catch (e) {
            console.error(e);
        }
    }

    // ===== Clear Chat =====
    async function handleClearChat() {
        try {
            await fetch('/api/clear_chat', { method: 'POST' });
            chatHistory.innerHTML = `
                <div class="message system">
                    <div class="avatar">🧠</div>
                    <div class="bubble">Chat history cleared. I'm ready for a new topic!</div>
                </div>
            `;
            contextContent.innerHTML = '<p class="empty-state">No context retrieved yet.</p>';
        } catch (e) {
            console.error(e);
        }
    }

    // ===== Chat Messages =====
    function addMessage(text, isUser = false) {
        const div = document.createElement('div');
        div.className = `message ${isUser ? 'user' : 'system'}`;
        const avatar = `<div class="avatar">${isUser ? '👤' : '🧠'}</div>`;
        const content = `<div class="bubble">${isUser ? text : marked.parse(text)}</div>`;
        div.innerHTML = avatar + content;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return div;
    }

    function addTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'message system';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="avatar">🧠</div>
            <div class="bubble">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
            </div>
        `;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if(indicator) indicator.remove();
    }

    // ===== Streaming Ask =====
    let currentAbortController = null;

    async function handleAsk() {
        const query = queryInput.value.trim();
        if(!query) return;

        queryInput.value = '';
        askBtn.classList.add('hidden');
        document.getElementById('stop-btn').classList.remove('hidden');
        
        addMessage(query, true);
        addTypingIndicator();
        contextContent.innerHTML = '<p class="empty-state">Searching vector database...</p>';

        currentAbortController = new AbortController();

        try {
            const res = await fetch('/api/ask_stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query}),
                signal: currentAbortController.signal
            });

            removeTypingIndicator();

            const responseDiv = document.createElement('div');
            responseDiv.className = 'message system';
            responseDiv.innerHTML = `<div class="avatar">🧠</div><div class="bubble" id="stream-bubble"></div>`;
            chatHistory.appendChild(responseDiv);

            const bubble = document.getElementById('stream-bubble');
            let fullText = '';

            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.context) {
                                contextContent.innerText = data.context;
                            }
                            if (data.token) {
                                fullText += data.token;
                                bubble.innerHTML = marked.parse(fullText);
                                
                                // Smart scroll: Only auto-scroll if user is near the bottom
                                const isNearBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight < 150;
                                if (isNearBottom) {
                                    chatHistory.scrollTop = chatHistory.scrollHeight;
                                }
                            }
                        } catch (e) {}
                    }
                }
            }

            bubble.removeAttribute('id');
            if (!fullText) {
                bubble.innerHTML = '<em>No response generated.</em>';
            }
        } catch (e) {
            removeTypingIndicator();
            if (e.name === 'AbortError') {
                addMessage("🛑 Generation stopped by user.", false);
            } else {
                addMessage("⚠️ Error communicating with the local brain server.", false);
            }
        }

        askBtn.classList.remove('hidden');
        document.getElementById('stop-btn').classList.add('hidden');
        currentAbortController = null;
    }

    document.getElementById('stop-btn').addEventListener('click', () => {
        if (currentAbortController) {
            currentAbortController.abort();
        }
    });

    // ===== Memory Browser =====
    async function loadMemories() {
        memoryList.innerHTML = '<p class="empty-state">Loading...</p>';
        try {
            const res = await fetch('/api/memories?limit=50');
            const data = await res.json();
            renderMemories(data.memories);
            fetchStats();
        } catch (e) {
            memoryList.innerHTML = '<p class="empty-state">Failed to load memories.</p>';
        }
    }

    async function searchMemories() {
        const query = memorySearch.value.trim();
        if (!query) { loadMemories(); return; }
        
        memoryList.innerHTML = '<p class="empty-state">Searching...</p>';
        try {
            const res = await fetch(`/api/memories/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            renderMemories(data.memories, true);
        } catch (e) {
            memoryList.innerHTML = '<p class="empty-state">Search failed.</p>';
        }
    }

    function renderMemories(memories, showRelevance = false) {
        if (!memories || memories.length === 0) {
            memoryList.innerHTML = '<p class="empty-state">No memories found.</p>';
            return;
        }

        memoryList.innerHTML = '';
        memories.forEach(mem => {
            const card = document.createElement('div');
            card.className = 'memory-card';
            
            const relevanceHtml = showRelevance && mem.relevance !== undefined 
                ? `<span class="memory-relevance">${(mem.relevance * 100).toFixed(1)}% match</span>` 
                : '';
            
            const previewText = escapeHtml(mem.text);
            const fullText = escapeHtml(mem.full_text || mem.text);
            const isLong = mem.full_text && mem.full_text.length > 300;
            
            card.innerHTML = `
                <div class="memory-card-header">
                    <span class="memory-source">${mem.source}</span>
                    <span class="memory-time">${new Date(mem.timestamp).toLocaleString()}</span>
                </div>
                <div class="memory-text" data-preview="${previewText}" data-full="${fullText}">${previewText}</div>
                ${isLong ? '<div class="memory-expand-hint">Click to expand ▼</div>' : ''}
                <div class="memory-card-footer">
                    ${relevanceHtml}
                    <button class="delete-memory-btn" data-id="${escapeHtml(mem.id)}">Delete</button>
                </div>
            `;
            
            // Click to expand/collapse and show in context panel
            card.addEventListener('click', (e) => {
                // Don't expand if they clicked the delete button
                if (e.target.classList.contains('delete-memory-btn')) return;
                
                const textEl = card.querySelector('.memory-text');
                const hintEl = card.querySelector('.memory-expand-hint');
                const isExpanded = card.classList.toggle('expanded');
                
                if (isExpanded) {
                    textEl.innerText = mem.full_text || mem.text;
                    if (hintEl) hintEl.innerText = 'Click to collapse ▲';
                } else {
                    textEl.innerText = mem.text;
                    if (hintEl) hintEl.innerText = 'Click to expand ▼';
                }
                
                // Show full content in the context panel on the right
                contextContent.innerText = mem.full_text || mem.text;
            });

            // Delete handler
            card.querySelector('.delete-memory-btn').addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = e.target.dataset.id;
                try {
                    await fetch(`/api/memories/${encodeURIComponent(id)}`, { method: 'DELETE' });
                    card.remove();
                    fetchStats();
                } catch (err) {
                    console.error(err);
                }
            });

            memoryList.appendChild(card);
        });
    }

    // ===== Add Note =====
    async function handleAddNote() {
        const text = noteInput.value.trim();
        if (!text) return;

        addNoteBtn.disabled = true;
        try {
            const res = await fetch('/api/add_note', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text})
            });
            const data = await res.json();
            
            if (res.ok) {
                noteInput.value = '';
                noteStatus.innerText = '✅ Note saved!';
                noteStatus.className = 'status-msg success';
                fetchStats();
                loadMemories();
            } else {
                noteStatus.innerText = data.detail || 'Error';
                noteStatus.className = 'status-msg error';
            }
        } catch (e) {
            noteStatus.innerText = 'Server error';
            noteStatus.className = 'status-msg error';
        }
        addNoteBtn.disabled = false;

        setTimeout(() => { noteStatus.innerText = ''; }, 3000);
    }

    // Helper: escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
