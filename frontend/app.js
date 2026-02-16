const API_BASE = 'http://localhost:8000';

const { createApp } = Vue;

createApp({
    data() {
        return {
            // ── Auth ──────────────────────────────────────────────────────────
            isAuthenticated: false,
            isLoading: false,
            showSignupForm: false,
            showApiKeyModal: false,

            loginForm:  { username: '', apiKey: '' },
            signupForm: { username: '' },
            createdAccount: { username: '', apiKey: '' },
            copyButtonText: 'Copy API Key',
            errorMessage: '',

            // ── User ──────────────────────────────────────────────────────────
            currentUser: { username: '', apiKey: '', userId: '' },

            // ── Sessions ──────────────────────────────────────────────────────
            sessions: [],
            currentSession: { sessionId: '', sessionName: '' },

            // ── Messages ──────────────────────────────────────────────────────
            messages: [],
            messageInput: '',
            isLoadingResponse: false,
            isThinking: false,
            streamController: null,
            lastUserMessage: '',

            // ── Files ─────────────────────────────────────────────────────────
            uploadedFiles: [],
            uploadStatus: '',
        };
    },

    async mounted() {
        await this.checkExistingSession();
    },

    methods: {
        // ── Formatting ────────────────────────────────────────────────────────

        formatMessage(content, streaming) {
            const cursor = streaming ? '<span class="stream-cursor"></span>' : '';
            
            // Ensure content is a string
            const contentStr = String(content || '');
            if (!contentStr) return cursor;
            
            // Check if marked is available
            if (typeof marked === 'undefined') {
                console.error('marked.js is not loaded!');
                return `<pre>${contentStr}</pre>${cursor}`;
            }
            
            try {
                const parsed = marked.parse(contentStr);
                return parsed + cursor;
            } catch (err) {
                console.error('Markdown parse error:', err);
                const safe = contentStr
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                return `<pre>${safe}</pre>${cursor}`;
            }
        },

        formatSessionDate(isoStr) {
            if (!isoStr) return '';
            const d = new Date(isoStr + (isoStr.endsWith('Z') ? '' : 'Z'));
            const now = new Date();
            const diffMs = now - d;
            const diffMin = Math.floor(diffMs / 60000);
            if (diffMin < 1) return 'just now';
            if (diffMin < 60) return `${diffMin}m ago`;
            const diffH = Math.floor(diffMin / 60);
            if (diffH < 24) return `${diffH}h ago`;
            return d.toLocaleDateString();
        },

        attachCopyButtons() {
            this.$nextTick(() => {
                const container = this.$refs.messagesContainer;
                if (!container) return;
                container.querySelectorAll('pre').forEach(pre => {
                    if (pre.querySelector('.copy-btn')) return;

                    const btn = document.createElement('button');
                    btn.className = 'copy-btn';
                    btn.textContent = 'Copy';

                    btn.addEventListener('click', () => {
                        const codeEl = pre.querySelector('code');
                        const text = codeEl ? codeEl.innerText : pre.innerText;

                        const tryFallback = () => {
                            const ta = document.createElement('textarea');
                            ta.value = text;
                            ta.style.cssText = 'position:fixed;opacity:0;top:-9999px';
                            document.body.appendChild(ta);
                            ta.focus(); ta.select();
                            document.execCommand('copy');
                            document.body.removeChild(ta);
                        };

                        (navigator.clipboard?.writeText(text) || Promise.reject())
                            .catch(tryFallback)
                            .finally(() => {
                                btn.textContent = '✓ Copied';
                                btn.classList.add('copied');
                                setTimeout(() => {
                                    btn.textContent = 'Copy';
                                    btn.classList.remove('copied');
                                }, 2000);
                            });
                    });

                    pre.style.position = 'relative';
                    pre.appendChild(btn);
                });
            });
        },

        // ── Auth ──────────────────────────────────────────────────────────────

        showError(msg, duration = 5000) {
            this.errorMessage = msg;
            clearTimeout(this._errTimer);
            this._errTimer = setTimeout(() => { this.errorMessage = ''; }, duration);
        },

        async checkExistingSession() {
            const raw = localStorage.getItem('ca_user');
            if (!raw) return;
            try {
                this.currentUser = JSON.parse(raw);
                this.isAuthenticated = true;
                const sessions = await this.loadSessions();
                const rawSess = localStorage.getItem('ca_session');
                if (rawSess) {
                    const saved = JSON.parse(rawSess);
                    const found = sessions.find((s) => s.id === saved.sessionId);
                    if (found) {
                        await this.selectSession(found);
                        return;
                    }
                }

                // If the saved session no longer exists, open the newest one.
                if (sessions.length > 0) {
                    await this.selectSession(sessions[0]);
                }
            } catch (err) {
                console.error('Session restore failed:', err);
                this.handleLogout();
            }
        },

        async handleSignup() {
            if (!this.signupForm.username.trim()) {
                this.showError('Please enter a username');
                return;
            }
            this.isLoading = true;
            this.errorMessage = '';
            try {
                const res = await fetch(`${API_BASE}/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: this.signupForm.username.trim() }),
                });
                const data = await res.json();
                if (!res.ok) { this.showError(data.detail || 'Registration failed'); return; }
                this.createdAccount = { username: data.username, apiKey: data.api_key };
                this.showApiKeyModal = true;
                this.signupForm.username = '';
            } catch {
                this.showError('Network error — is the backend running?');
            } finally {
                this.isLoading = false;
            }
        },

        copyApiKey() {
            navigator.clipboard?.writeText(this.createdAccount.apiKey).then(() => {
                this.copyButtonText = '✓ Copied!';
                setTimeout(() => { this.copyButtonText = 'Copy API Key'; }, 2000);
            }).catch(() => {
                this.copyButtonText = 'See key above';
            });
        },

        closeApiKeyModal() {
            this.showApiKeyModal = false;
            this.showSignupForm = false;
        },

        async handleLogin() {
            if (!this.loginForm.username.trim() || !this.loginForm.apiKey.trim()) {
                this.showError('Please enter both username and API key');
                return;
            }
            this.isLoading = true;
            this.errorMessage = '';
            try {
                const res = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: this.loginForm.username.trim(),
                        api_key:  this.loginForm.apiKey.trim(),
                    }),
                });
                const data = await res.json();
                if (!res.ok) { this.showError(data.detail || 'Login failed'); return; }

                this.currentUser = {
                    username: data.username,
                    apiKey:   this.loginForm.apiKey.trim(),
                    userId:   data.user_id,
                };
                localStorage.setItem('ca_user', JSON.stringify(this.currentUser));
                this.isAuthenticated = true;
                this.loginForm = { username: '', apiKey: '' };
                await this.loadSessions();
            } catch {
                this.showError('Network error — is the backend running?');
            } finally {
                this.isLoading = false;
            }
        },

        handleLogout() {
            this.stopGeneration();
            localStorage.removeItem('ca_user');
            localStorage.removeItem('ca_session');
            this.isAuthenticated = false;
            this.currentUser = { username: '', apiKey: '', userId: '' };
            this.sessions = [];
            this.currentSession = { sessionId: '', sessionName: '' };
            this.messages = [];
            this.uploadedFiles = [];
            this.lastUserMessage = '';
        },

        // ── Sessions ──────────────────────────────────────────────────────────

        async loadSessions() {
            try {
                const res = await fetch(`${API_BASE}/sessions?api_key=${this.currentUser.apiKey}`);
                if (!res.ok) {
                    if (res.status === 401) {
                        this.showError('Session expired. Please sign in again.');
                        this.handleLogout();
                    }
                    return [];
                }
                this.sessions = await res.json();
                return this.sessions;
            } catch {
                return [];
            }
        },

        async createNewSession() {
            this.isLoading = true;
            try {
                const res = await fetch(`${API_BASE}/sessions?api_key=${this.currentUser.apiKey}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const data = await res.json();
                if (res.ok) {
                    await this.loadSessions();
                    const newSess = this.sessions.find(s => s.id === data.session_id);
                    if (newSess) this.selectSession(newSess);
                }
            } catch {
                this.showError('Could not create session');
            } finally {
                this.isLoading = false;
            }
        },

        async selectSession(session) {
            this.stopGeneration();
            this.currentSession = { sessionId: session.id, sessionName: session.name };
            localStorage.setItem('ca_session', JSON.stringify(this.currentSession));
            this.messages = [];
            this.uploadedFiles = [];
            this.isThinking = false;
            this.lastUserMessage = '';
            await Promise.all([this.loadMessages(), this.loadSessionFiles()]);
        },

        async deleteCurrentSession() {
            if (!this.currentSession.sessionId) return;
            if (!confirm(`Delete session "${this.currentSession.sessionName}"? This cannot be undone.`)) return;
            this.stopGeneration();
            try {
                const res = await fetch(
                    `${API_BASE}/sessions/${this.currentSession.sessionId}?api_key=${this.currentUser.apiKey}`,
                    { method: 'DELETE' }
                );
                if (res.ok) {
                    localStorage.removeItem('ca_session');
                    this.currentSession = { sessionId: '', sessionName: '' };
                    this.messages = [];
                    this.uploadedFiles = [];
                    await this.loadSessions();
                }
            } catch {
                this.showError('Could not delete session');
            }
        },

        // ── Messages ──────────────────────────────────────────────────────────

        async loadMessages() {
            if (!this.currentSession.sessionId) return;
            try {
                const res = await fetch(
                    `${API_BASE}/sessions/${this.currentSession.sessionId}/messages?api_key=${this.currentUser.apiKey}`
                );
                if (!res.ok) {
                    this.messages = [];
                    return;
                }
                const data = await res.json();
                if (data.length > 0) {
                    this.messages = data.map((m) => ({
                        id: m.id,
                        role: m.role,
                        content: m.content || '',
                        createdAt: m.created_at,
                    }));
                } else {
                    this.messages = [{
                        role: 'assistant',
                        content: `Hey ${this.currentUser.username}! I'm **CodeAssist**, your AI coding agent.`,
                    }];
                }
                this.$nextTick(() => this.attachCopyButtons());
                this.scrollToBottom();
            } catch {
                this.messages = [];
            }
        },

        // ── Files ─────────────────────────────────────────────────────────────

        async loadSessionFiles() {
            if (!this.currentSession.sessionId) return;
            try {
                const res = await fetch(
                    `${API_BASE}/sessions/${this.currentSession.sessionId}/files?api_key=${this.currentUser.apiKey}`
                );
                if (res.ok) this.uploadedFiles = await res.json();
            } catch {
                this.uploadedFiles = [];
            }
        },

        async handleFileSelect(event) {
            const file = event.target.files?.[0];
            if (!file || !this.currentSession.sessionId) return;

            const maxSize = 1 * 1024 * 1024; // 1 MB
            if (file.size > maxSize) {
                this.showError(`File too large (max 1 MB). Got ${(file.size/1024).toFixed(0)} KB.`);
                event.target.value = '';
                return;
            }

            this.uploadStatus = `Uploading ${file.name}…`;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(
                    `${API_BASE}/sessions/${this.currentSession.sessionId}/upload?api_key=${this.currentUser.apiKey}`,
                    { method: 'POST', body: formData }
                );
                const data = await res.json();
                if (!res.ok) {
                    this.uploadStatus = `✗ ${data.detail || 'Upload failed'}`;
                    setTimeout(() => { this.uploadStatus = ''; }, 4000);
                    return;
                }

                this.uploadStatus = `✓ ${file.name} ready`;
                setTimeout(() => { this.uploadStatus = ''; }, 3000);
                await this.loadSessionFiles();

                this.messages.push({
                    role: 'assistant',
                    content: `I've received **${file.name}** (${(file.size/1024).toFixed(1)} KB). Its contents are now in context — ask me anything about it!`,
                });
                this.scrollToBottom();
                this.attachCopyButtons();
            } catch {
                this.uploadStatus = '✗ Network error';
                setTimeout(() => { this.uploadStatus = ''; }, 3000);
            } finally {
                event.target.value = '';
            }
        },

        async removeFile(filename) {
            try {
                await fetch(
                    `${API_BASE}/sessions/${this.currentSession.sessionId}/files/${encodeURIComponent(filename)}?api_key=${this.currentUser.apiKey}`,
                    { method: 'DELETE' }
                );
                await this.loadSessionFiles();
            } catch {}
        },

        // ── Chat / Streaming ──────────────────────────────────────────────────

        handleKeydown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        },

        stopGeneration() {
            if (this.streamController) {
                this.streamController.abort();
                this.streamController = null;
            }
        },

        applySseEvent(part, assistantIndex, rawContent) {
            const dataLines = part
                .split('\n')
                .filter((line) => line.startsWith('data:'))
                .map((line) => line.slice(5).trimStart());

            if (dataLines.length === 0) {
                return rawContent;
            }

            let payload;
            try {
                payload = JSON.parse(dataLines.join('\n'));
            } catch {
                return rawContent;
            }

            if (payload.type === 'token') {
                rawContent += payload.content || '';
                this.messages[assistantIndex].content = rawContent;
                this.scrollToBottom();
            } else if (payload.type === 'done') {
                rawContent = payload.content || rawContent;
                this.messages[assistantIndex].content = rawContent;
                this.scrollToBottom();
            } else if (payload.type === 'error') {
                rawContent += `\n\n*⚠ Error: ${payload.content}*`;
                this.messages[assistantIndex].content = rawContent;
                this.scrollToBottom();
            }

            return rawContent;
        },

        async retryLastMessage() {
            if (this.isLoadingResponse) return;
            const fallback = [...this.messages].reverse().find(m => m.role === 'user')?.content || '';
            const text = (this.lastUserMessage || fallback).trim();
            if (!text) {
                this.showError('No previous message to retry.');
                return;
            }
            await this.sendMessage(text);
        },

        async sendMessage(overrideText = null) {
            const text = (overrideText ?? this.messageInput).trim();
            if (!text || this.isLoadingResponse || !this.currentSession.sessionId) return;

            this.lastUserMessage = text;
            this.messages.push({ role: 'user', content: text });
            if (overrideText === null) {
                this.messageInput = '';
                this.$nextTick(() => this.resetTextarea());
            }
            this.isLoadingResponse = true;
            this.isThinking = true;
            this.scrollToBottom();

            let rawContent = '';
            let assistantIndex = -1;

            try {
                this.streamController = new AbortController();
                const res = await fetch(`${API_BASE}/chat/stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    signal: this.streamController.signal,
                    body: JSON.stringify({
                        session_id: this.currentSession.sessionId,
                        message:    text,
                        api_key:    this.currentUser.apiKey,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }

                // Kick off the streaming assistant message after response starts
                this.isThinking = false;
                assistantIndex = this.messages.length;
                this.messages.push({ role: 'assistant', content: '', streaming: true });

                const reader  = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (value) {
                        buffer += decoder.decode(value, { stream: true });
                    }

                    // Split on SSE event boundaries (\n\n)
                    const parts = buffer.split('\n\n');
                    buffer = parts.pop(); // keep incomplete last chunk

                    for (const part of parts) {
                        rawContent = this.applySseEvent(part, assistantIndex, rawContent);
                    }

                    if (done) {
                        buffer += decoder.decode();
                        break;
                    }
                }

                // Process any final partial event to avoid truncating long messages.
                if (buffer.trim()) {
                    rawContent = this.applySseEvent(buffer, assistantIndex, rawContent);
                }

            } catch (err) {
                console.error('Stream error:', err);
                this.isThinking = false;
                if (assistantIndex === -1) {
                    assistantIndex = this.messages.length;
                    this.messages.push({ role: 'assistant', content: '', streaming: true });
                }
                const wasAborted = err?.name === 'AbortError';
                const msg = wasAborted
                    ? (rawContent || '*Generation stopped.*')
                    : (rawContent || `*Failed to get a response.*\n\nError: ${err.message}`);
                this.messages[assistantIndex].content = msg;
                this.scrollToBottom();
            } finally {
                this.streamController = null;
                if (assistantIndex !== -1) {
                    this.messages[assistantIndex].streaming = false;
                }
                this.isLoadingResponse = false;
                this.isThinking = false;
                this.attachCopyButtons();
                // Refresh session list to update "last updated" time
                await this.loadSessions();
            }
        },

        // ── UI Helpers ────────────────────────────────────────────────────────

        autoGrow(e) {
            const el = e?.target || this.$refs.chatTextarea;
            if (!el) return;
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
        },

        resetTextarea() {
            const ta = this.$refs.chatTextarea;
            if (ta) { ta.style.height = 'auto'; }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                const c = this.$refs.messagesContainer;
                if (c) c.scrollTop = c.scrollHeight;
            });
        },
    },
}).mount('#app');