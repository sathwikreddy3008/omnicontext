/* ============================================================
   OmniContext — app.js
   Features: Chat (SSE streaming), Memory Browser, Context Explorer,
             Source-type badges, Relevance bars, Confidence indicators,
             Source citations, Related context discovery, Tag filters
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    fetchStats();
    loadProjectsForFilter();
    loadTagsForFilter();

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const chatHistory     = document.getElementById('chat-history');
    const queryInput      = document.getElementById('query-input');
    const askBtn          = document.getElementById('ask-btn');
    const stopBtn         = document.getElementById('stop-btn');
    const ingestPath      = document.getElementById('ingest-path');
    const ingestUrl       = document.getElementById('ingest-url');
    const ingestPdfFile   = document.getElementById('ingest-pdf-file');
    const ingestBtn       = document.getElementById('ingest-btn');
    const ingestUrlBtn    = document.getElementById('ingest-url-btn');
    const ingestPdfBtn    = document.getElementById('ingest-pdf-btn');
    const clearBtn        = document.getElementById('clear-btn');
    const clearChatBtn    = document.getElementById('clear-chat-btn');
    const contextContent  = document.getElementById('context-content');
    const ingestStatus    = document.getElementById('ingest-status');
    const ingestType      = document.getElementById('ingest-type');
    const confidenceBadge = document.getElementById('confidence-badge');
    const citationsPanel  = document.getElementById('citations-panel');
    const citationsList   = document.getElementById('citations-list');

    // Memory browser
    const memoryList       = document.getElementById('memory-list');
    const memorySearch     = document.getElementById('memory-search');
    const memorySearchBtn  = document.getElementById('memory-search-btn');
    const memoryRefreshBtn = document.getElementById('memory-refresh-btn');
    const noteInput        = document.getElementById('note-input');
    const addNoteBtn       = document.getElementById('add-note-btn');
    const noteStatus       = document.getElementById('note-status');

    // Explorer
    const explorerQuery     = document.getElementById('explorer-query');
    const explorerSearchBtn = document.getElementById('explorer-search-btn');
    const explorerResults   = document.getElementById('explorer-results');
    const filterSourceType  = document.getElementById('filter-source-type');
    const filterProject     = document.getElementById('filter-project');
    const filterTagsEl      = document.getElementById('filter-tags');

    // Views
    const chatView     = document.getElementById('chat-view');
    const memoriesView = document.getElementById('memories-view');
    const explorerView = document.getElementById('explorer-view');
    const navTabs      = document.querySelectorAll('.nav-tab');

    let activeExplorerTags = new Set();

    // ── Tab switching ─────────────────────────────────────────────────────────
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            chatView.classList.add('hidden');
            memoriesView.classList.add('hidden');
            explorerView.classList.add('hidden');

            const target = tab.dataset.tab;
            if (target === 'chat') {
                chatView.classList.remove('hidden');
                queryInput.focus();
            } else if (target === 'memories') {
                memoriesView.classList.remove('hidden');
                loadMemories();
                clearContextPanel();
            } else if (target === 'explorer') {
                explorerView.classList.remove('hidden');
            }
        });
    });

    // ── Keyboard shortcuts ────────────────────────────────────────────────────
    queryInput.addEventListener('keypress', e => { if (e.key === 'Enter') handleAsk(); });
    memorySearch.addEventListener('keypress', e => { if (e.key === 'Enter') searchMemories(); });
    explorerQuery.addEventListener('keypress', e => { if (e.key === 'Enter') handleExploreSearch(); });

    // ── Ingestion type switcher ───────────────────────────────────────────────
    ingestType.addEventListener('change', e => {
        ['folder', 'url', 'pdf'].forEach(t =>
            document.getElementById(`ingest-${t}-group`).classList.add('hidden')
        );
        document.getElementById(`ingest-${e.target.value}-group`).classList.remove('hidden');
        ingestStatus.innerText = '';
    });

    // ── Button bindings ───────────────────────────────────────────────────────
    askBtn.addEventListener('click', handleAsk);
    ingestBtn.addEventListener('click', handleIngestFolder);
    ingestUrlBtn.addEventListener('click', handleIngestUrl);
    ingestPdfBtn.addEventListener('click', handleIngestPdf);
    clearBtn.addEventListener('click', handleClear);
    clearChatBtn.addEventListener('click', handleClearChat);
    memorySearchBtn.addEventListener('click', searchMemories);
    memoryRefreshBtn.addEventListener('click', loadMemories);
    addNoteBtn.addEventListener('click', handleAddNote);
    explorerSearchBtn.addEventListener('click', handleExploreSearch);

    stopBtn.addEventListener('click', () => {
        if (currentAbortController) currentAbortController.abort();
    });

    // ═══════════════════════════════════════════════════════════════════════════
    //  STATS
    // ═══════════════════════════════════════════════════════════════════════════
    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('memory-count').innerText = data.count;
        } catch (e) {}
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  INGESTION
    // ═══════════════════════════════════════════════════════════════════════════
    function setIngestStatus(msg, type = '') {
        ingestStatus.innerText = msg;
        ingestStatus.className = `status-msg ${type}`;
    }

    async function handleIngestFolder() {
        const path = ingestPath.value.trim();
        if (!path) return;
        ingestBtn.disabled = true;
        setIngestStatus('Scanning directory...');
        try {
            const res = await fetch('/api/ingest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            });
            const data = await res.json();
            setIngestStatus(res.ok ? data.message : (data.detail || 'Error'), res.ok ? 'success' : 'error');
            if (res.ok) { fetchStats(); loadProjectsForFilter(); loadTagsForFilter(); }
        } catch { setIngestStatus('Server error', 'error'); }
        ingestBtn.disabled = false;
    }

    async function handleIngestUrl() {
        const url = ingestUrl.value.trim();
        if (!url) return;
        ingestUrlBtn.disabled = true;
        setIngestStatus('Scraping URL...');
        try {
            const res = await fetch('/api/ingest_url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });
            const data = await res.json();
            setIngestStatus(res.ok ? data.message : (data.detail || 'Error'), res.ok ? 'success' : 'error');
            if (res.ok) { ingestUrl.value = ''; fetchStats(); }
        } catch { setIngestStatus('Server error', 'error'); }
        ingestUrlBtn.disabled = false;
    }

    async function handleIngestPdf() {
        const file = ingestPdfFile.files[0];
        if (!file) return;
        ingestPdfBtn.disabled = true;
        setIngestStatus('Parsing PDF...');
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch('/api/ingest_pdf', { method: 'POST', body: formData });
            const data = await res.json();
            setIngestStatus(res.ok ? data.message : (data.detail || 'Error'), res.ok ? 'success' : 'error');
            if (res.ok) { ingestPdfFile.value = ''; fetchStats(); }
        } catch { setIngestStatus('Server error', 'error'); }
        ingestPdfBtn.disabled = false;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  CLEAR
    // ═══════════════════════════════════════════════════════════════════════════
    async function handleClear() {
        if (!confirm('Are you sure you want to permanently delete all OmniContext memories?')) return;
        await fetch('/api/clear', { method: 'POST' });
        fetchStats();
        clearContextPanel();
        memoryList.innerHTML = '<p class="empty-state">All memories cleared.</p>';
        explorerResults.innerHTML = '<p class="empty-state">Memory cleared.</p>';
    }

    async function handleClearChat() {
        await fetch('/api/clear_chat', { method: 'POST' });
        chatHistory.innerHTML = `
            <div class="message system">
                <div class="avatar"><i data-lucide="zap" class="icon-md"></i></div>
                <div class="bubble">Chat history cleared. Ready for a new session!</div>
            </div>`;
        lucide.createIcons();
        clearContextPanel();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  CHAT + STREAMING
    // ═══════════════════════════════════════════════════════════════════════════
    function addMessage(text, isUser = false) {
        const div = document.createElement('div');
        div.className = `message ${isUser ? 'user' : 'system'}`;
        const avatar = `<div class="avatar">${isUser ? '<i data-lucide="user" class="icon-md"></i>' : '<i data-lucide="zap" class="icon-md"></i>'}</div>`;
        const content = `<div class="bubble">${isUser ? escapeHtml(text) : marked.parse(text)}</div>`;
        div.innerHTML = avatar + content;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        lucide.createIcons();
        return div;
    }

    function addTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'message system';
        div.id = 'typing-indicator';
        div.innerHTML = `<div class="avatar"><i data-lucide="zap" class="icon-md"></i></div><div class="bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        lucide.createIcons();
    }

    function removeTypingIndicator() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    function clearContextPanel() {
        contextContent.innerHTML = '<p class="empty-state">No context retrieved yet.</p>';
        confidenceBadge.classList.add('hidden');
        citationsPanel.classList.add('hidden');
        citationsList.innerHTML = '';
    }

    function renderConfidence(confidence) {
        confidenceBadge.classList.remove('hidden', 'high', 'medium', 'low');
        let level, label;
        if (confidence >= 0.75)      { level = 'high';   label = `✓ ${(confidence * 100).toFixed(0)}% confident`; }
        else if (confidence >= 0.45) { level = 'medium'; label = `~ ${(confidence * 100).toFixed(0)}% confident`; }
        else                          { level = 'low';    label = `⚠ ${(confidence * 100).toFixed(0)}% confident`; }
        confidenceBadge.classList.add(level);
        confidenceBadge.textContent = label;
    }

    function renderCitations(sources) {
        if (!sources || sources.length === 0) {
            citationsPanel.classList.add('hidden');
            return;
        }
        citationsPanel.classList.remove('hidden');
        citationsList.innerHTML = '';
        sources.forEach(s => {
            const item = document.createElement('div');
            item.className = 'citation-item';
            const shortSrc = s.source.length > 40 ? '...' + s.source.slice(-40) : s.source;
            item.innerHTML = `
                <div class="citation-index">${s.index}</div>
                <span class="citation-source" title="${escapeHtml(s.source)}">${escapeHtml(shortSrc)}</span>
                <span class="citation-score">${(s.score * 100).toFixed(0)}%</span>
            `;
            citationsList.appendChild(item);
        });
    }

    function attachAnswerMeta(messageDiv, meta) {
        if (!meta) return;
        const confidence = meta.confidence || 0;
        const sources = meta.used_sources || [];

        const metaEl = document.createElement('div');
        metaEl.className = 'answer-meta';

        // Confidence pill
        let level = confidence >= 0.75 ? 'high' : confidence >= 0.45 ? 'medium' : 'low';
        const pill = document.createElement('span');
        pill.className = `confidence-pill ${level}`;
        pill.textContent = `${level === 'high' ? '✓' : level === 'medium' ? '~' : '⚠'} ${(confidence * 100).toFixed(0)}% confidence`;
        metaEl.appendChild(pill);

        // Citation chips (max 3)
        sources.slice(0, 3).forEach(s => {
            const chip = document.createElement('span');
            chip.className = 'citation-chip';
            chip.textContent = `[${s.index}] ${s.source.split(':').slice(-1)[0]}`;
            chip.title = s.source;
            metaEl.appendChild(chip);
        });

        messageDiv.querySelector('.bubble').appendChild(metaEl);

        // Also update right panel
        renderConfidence(confidence);
        renderCitations(sources);
    }

    let currentAbortController = null;

    async function handleAsk() {
        const query = queryInput.value.trim();
        if (!query) return;

        queryInput.value = '';
        askBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');

        addMessage(query, true);
        addTypingIndicator();
        clearContextPanel();
        contextContent.innerHTML = '<p class="empty-state">Searching vector database...</p>';

        currentAbortController = new AbortController();

        try {
            const res = await fetch('/api/ask_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
                signal: currentAbortController.signal,
            });

            removeTypingIndicator();

            const responseDiv = document.createElement('div');
            responseDiv.className = 'message system';
            responseDiv.innerHTML = `<div class="avatar"><i data-lucide="zap" class="icon-md"></i></div><div class="bubble" id="stream-bubble"></div>`;
            chatHistory.appendChild(responseDiv);
            lucide.createIcons();

            const bubble = document.getElementById('stream-bubble');
            let fullText = '';

            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                for (const line of chunk.split('\n')) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.context) {
                            contextContent.innerText = data.context;
                        }

                        if (data.token) {
                            fullText += data.token;
                            bubble.innerHTML = marked.parse(fullText);
                            const isNearBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight < 150;
                            if (isNearBottom) chatHistory.scrollTop = chatHistory.scrollHeight;
                        }

                        if (data.done && data.meta) {
                            attachAnswerMeta(responseDiv, data.meta);
                        }
                    } catch {}
                }
            }

            bubble.removeAttribute('id');
            if (!fullText) bubble.innerHTML = '<em>No response generated.</em>';

        } catch (e) {
            removeTypingIndicator();
            if (e.name === 'AbortError') {
                addMessage('🛑 Generation stopped.', false);
            } else {
                addMessage('⚠️ Error communicating with the OmniContext server.', false);
            }
        }

        askBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
        currentAbortController = null;
        fetchStats();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  MEMORY BROWSER
    // ═══════════════════════════════════════════════════════════════════════════
    async function loadMemories() {
        memoryList.innerHTML = '<p class="empty-state">Loading...</p>';
        try {
            const res = await fetch('/api/memories?limit=50');
            const data = await res.json();
            renderMemories(data.memories);
            fetchStats();
        } catch {
            memoryList.innerHTML = '<p class="empty-state">Failed to load memories.</p>';
        }
    }

    async function searchMemories() {
        const q = memorySearch.value.trim();
        if (!q) { loadMemories(); return; }
        memoryList.innerHTML = '<p class="empty-state">Searching...</p>';
        try {
            const res = await fetch(`/api/memories/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            renderMemories(data.memories, true);
        } catch {
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
            const previewText = escapeHtml(mem.text);
            const isLong = mem.full_text && mem.full_text.length > 300;

            card.innerHTML = `
                <div class="memory-card-header">
                    ${sourceBadge(mem.source_type, mem.source)}
                    <span class="memory-time">${formatDate(mem.timestamp)}</span>
                </div>
                ${mem.tags && mem.tags.length ? `<div class="tags-row">${mem.tags.map(t => `<span class="tag-chip">${t}</span>`).join('')}</div>` : ''}
                <div class="memory-text" style="margin-top:8px">${previewText}</div>
                ${isLong ? '<div class="memory-expand-hint">Click to expand ▼</div>' : ''}
                <div class="memory-card-footer">
                    ${showRelevance && mem.relevance !== undefined ? `<span class="memory-relevance">${(mem.relevance * 100).toFixed(1)}% match</span>` : '<span></span>'}
                    <button class="delete-memory-btn" data-id="${escapeHtml(mem.id)}">Delete</button>
                </div>`;

            card.addEventListener('click', e => {
                if (e.target.classList.contains('delete-memory-btn')) return;
                const textEl = card.querySelector('.memory-text');
                const hintEl = card.querySelector('.memory-expand-hint');
                const expanded = card.classList.toggle('expanded');
                textEl.innerText = expanded ? (mem.full_text || mem.text) : mem.text;
                if (hintEl) hintEl.innerText = expanded ? 'Click to collapse ▲' : 'Click to expand ▼';
                contextContent.innerText = mem.full_text || mem.text;
            });

            card.querySelector('.delete-memory-btn').addEventListener('click', async e => {
                e.stopPropagation();
                await fetch(`/api/memories/${encodeURIComponent(e.target.dataset.id)}`, { method: 'DELETE' });
                card.remove();
                fetchStats();
            });

            memoryList.appendChild(card);
        });
        lucide.createIcons();
    }

    async function handleAddNote() {
        const text = noteInput.value.trim();
        if (!text) return;
        addNoteBtn.disabled = true;
        try {
            const res = await fetch('/api/add_note', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
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
        } catch {
            noteStatus.innerText = 'Server error';
            noteStatus.className = 'status-msg error';
        }
        addNoteBtn.disabled = false;
        setTimeout(() => { noteStatus.innerText = ''; }, 3000);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  CONTEXT EXPLORER
    // ═══════════════════════════════════════════════════════════════════════════
    async function loadProjectsForFilter() {
        try {
            const res = await fetch('/api/context/projects');
            const data = await res.json();
            filterProject.innerHTML = '<option value="">All Projects</option>';
            (data.projects || []).forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.project;
                opt.textContent = `${p.project} (${p.chunks})`;
                filterProject.appendChild(opt);
            });
        } catch {}
    }

    async function loadTagsForFilter() {
        try {
            const res = await fetch('/api/context/tags');
            const data = await res.json();
            filterTagsEl.innerHTML = '';
            (data.tags || []).slice(0, 15).forEach(t => {
                const chip = document.createElement('span');
                chip.className = 'tag-chip';
                chip.textContent = t.tag;
                chip.addEventListener('click', () => {
                    chip.classList.toggle('active');
                    if (chip.classList.contains('active')) {
                        activeExplorerTags.add(t.tag);
                    } else {
                        activeExplorerTags.delete(t.tag);
                    }
                });
                filterTagsEl.appendChild(chip);
            });
        } catch {}
    }

    async function handleExploreSearch() {
        const q = explorerQuery.value.trim();
        if (!q) return;

        explorerResults.innerHTML = '<p class="empty-state">Searching...</p>';

        const params = new URLSearchParams({ q, top_k: 10 });
        const srcType = filterSourceType.value;
        const project = filterProject.value;
        const tags = [...activeExplorerTags];

        if (srcType) params.set('source_type', srcType);
        if (project) params.set('project', project);
        if (tags.length) params.set('tags', tags.join(','));

        try {
            const res = await fetch(`/api/context/explore?${params}`);
            const data = await res.json();
            renderExplorerResults(data);
        } catch {
            explorerResults.innerHTML = '<p class="empty-state">Search failed. Is the server running?</p>';
        }
    }

    function renderExplorerResults(data) {
        if (!data.results || data.results.length === 0) {
            explorerResults.innerHTML = '<p class="empty-state">No results found for your query.</p>';
            return;
        }
        explorerResults.innerHTML = `<p style="font-size:12px;color:var(--text-secondary);margin-bottom:8px">${data.total} result${data.total !== 1 ? 's' : ''} for "<strong style="color:var(--text-primary)">${escapeHtml(data.query)}</strong>"</p>`;

        data.results.forEach(r => {
            const card = document.createElement('div');
            card.className = 'explorer-card';

            const relPct = (r.relevance * 100).toFixed(1);
            const barColor = r.relevance >= 0.75 ? '#10b981' : r.relevance >= 0.5 ? '#f59e0b' : '#ef4444';

            card.innerHTML = `
                <div class="explorer-card-header">
                    <div class="explorer-card-meta">
                        ${sourceBadge(r.source_type)}
                        ${r.project ? `<span class="tag-chip">${escapeHtml(r.project)}</span>` : ''}
                        ${r.language ? `<span class="tag-chip" style="background:rgba(0,212,255,0.1);color:var(--accent-color)">${r.language}</span>` : ''}
                    </div>
                    <button class="related-btn" data-id="${escapeHtml(r.id)}">Related ↗</button>
                </div>
                <div class="explorer-preview">${escapeHtml(r.preview)}</div>
                ${r.tags && r.tags.length ? `<div class="tags-row" style="margin-top:8px">${r.tags.map(t => `<span class="tag-chip">${t}</span>`).join('')}</div>` : ''}
                <div class="relevance-bar-wrap">
                    <div class="relevance-bar"><div class="relevance-bar-fill" style="width:${relPct}%;background:${barColor}"></div></div>
                    <span class="relevance-score" style="color:${barColor}">${relPct}%</span>
                </div>
                <div style="font-size:10px;color:var(--text-secondary);margin-top:6px">
                    <span title="Source">${escapeHtml(r.source)}</span>
                    ${r.heading ? ` · <em>${escapeHtml(r.heading)}</em>` : ''}
                    · ${formatDate(r.timestamp)}
                </div>`;

            // Click to show in context panel
            card.addEventListener('click', e => {
                if (e.target.classList.contains('related-btn')) return;
                contextContent.innerText = r.preview;
            });

            // Related context button
            card.querySelector('.related-btn').addEventListener('click', e => {
                e.stopPropagation();
                loadRelatedContext(r.id, r.source);
            });

            explorerResults.appendChild(card);
        });
        lucide.createIcons();
    }

    async function loadRelatedContext(docId, sourceLabel = '') {
        contextContent.innerHTML = `<p class="empty-state">Finding related context for:\n${escapeHtml(sourceLabel)}...</p>`;
        confidenceBadge.classList.add('hidden');
        citationsPanel.classList.add('hidden');

        try {
            const res = await fetch(`/api/context/related/${encodeURIComponent(docId)}?top_k=5`);
            const data = await res.json();

            if (!data.related || data.related.length === 0) {
                contextContent.innerText = 'No related context found.';
                return;
            }

            let text = `🔗 Related to: ${sourceLabel}\n${'─'.repeat(40)}\n\n`;
            data.related.forEach((r, i) => {
                text += `[${i + 1}] ${r.source} (${(r.similarity * 100).toFixed(1)}% similar)\n`;
                text += r.preview + '\n\n';
            });
            contextContent.innerText = text;

            // Show as pseudo-citations
            citationsPanel.classList.remove('hidden');
            citationsList.innerHTML = '';
            data.related.forEach((r, i) => {
                const item = document.createElement('div');
                item.className = 'citation-item';
                const shortSrc = r.source.length > 38 ? '...' + r.source.slice(-38) : r.source;
                item.innerHTML = `
                    <div class="citation-index">${i + 1}</div>
                    <span class="citation-source" title="${escapeHtml(r.source)}">${escapeHtml(shortSrc)}</span>
                    <span class="citation-score">${(r.similarity * 100).toFixed(0)}%</span>`;
                citationsList.appendChild(item);
            });

        } catch {
            contextContent.innerText = 'Failed to load related context.';
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    //  HELPERS
    // ═══════════════════════════════════════════════════════════════════════════
    function sourceBadge(sourceType, fullSource = '') {
        const icons = { code: 'code', pdf: 'file-text', web: 'globe', clipboard: 'clipboard', note: 'edit-3' };
        const cls   = ['code', 'pdf', 'web', 'clipboard', 'note'].includes(sourceType)
                      ? `badge-${sourceType}` : 'badge-unknown';
        const iconName = icons[sourceType] || 'box';
        const icon = `<i data-lucide="${iconName}" class="icon-sm"></i>`;
        const label = sourceType || 'unknown';
        return `<span class="source-badge ${cls}">${icon} ${label}</span>`;
    }

    function formatDate(ts) {
        if (!ts || ts === 'unknown') return '—';
        try { return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
        catch { return ts; }
    }

    function escapeHtml(text) {
        if (typeof text !== 'string') return String(text ?? '');
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
