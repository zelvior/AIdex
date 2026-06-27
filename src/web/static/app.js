// AIdex Web UI — application logic
// Vanilla JS, ES modules, no build step. Talks to the local AIdex server
// (src/web/server.py) which wraps the exact same Agent/Config/provider
// code used by the terminal app — no logic is duplicated here.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const els = {
  rail: $('#rail'),
  panels: $$('.panel'),
  statusDot: $('#statusDot'),
  statusLabel: $('#statusLabel'),
  modelChip: $('#modelChip'),
  chatScroll: $('#chatScroll'),
  emptyState: $('#emptyState'),
  messages: $('#messages'),
  composer: $('#composer'),
  composerInput: $('#composerInput'),
  sendBtn: $('#sendBtn'),
  clearBtn: $('#clearBtn'),
  toastStack: $('#toastStack'),

  fsBreadcrumb: $('#fsBreadcrumb'),
  fileList: $('#fileList'),
  fileViewerName: $('#fileViewerName'),
  fileViewerContent: $('#fileViewerContent'),
  fileSaveBtn: $('#fileSaveBtn'),
  fsRefreshBtn: $('#fsRefreshBtn'),

  providerSelect: $('#providerSelect'),
  modelSearch: $('#modelSearch'),
  sortSeg: $('#sortSeg'),
  freeOnlyToggle: $('#freeOnlyToggle'),
  modelsTableBody: $('#modelsTableBody'),
  modelsSourcePill: $('#modelsSourcePill'),
  modelsRefreshBtn: $('#modelsRefreshBtn'),

  keyFields: $('#keyFields'),
  workspaceInput: $('#workspaceInput'),
  workspaceSaveBtn: $('#workspaceSaveBtn'),
  safeModeToggle: $('#safeModeToggle'),
  streamToggle: $('#streamToggle'),
  maxTokensInput: $('#maxTokensInput'),
  temperatureInput: $('#temperatureInput'),

  ralphCountsPill: $('#ralphCountsPill'),
  ralphStopBtn: $('#ralphStopBtn'),
  ralphClearBtn: $('#ralphClearBtn'),
  ralphTaskInput: $('#ralphTaskInput'),
  ralphAddBtn: $('#ralphAddBtn'),
  ralphMaxIterations: $('#ralphMaxIterations'),
  ralphRunBtn: $('#ralphRunBtn'),
  ralphTaskList: $('#ralphTaskList'),
  ralphLog: $('#ralphLog'),
};

const state = {
  status: null,
  fsPath: '.',
  fsCurrentFile: null,
  modelsCache: { models: [], source: '-' },
  sending: false,
};

// ───────────────────────── Toasts ─────────────────────────

function toast(message, isError = false) {
  const node = document.createElement('div');
  node.className = 'toast' + (isError ? ' is-error' : '');
  node.textContent = message;
  els.toastStack.appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

// ───────────────────────── API helpers ─────────────────────────

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).error || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

const getJSON = (path) => api(path);
const postJSON = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });

// ───────────────────────── Panel navigation ─────────────────────────

function activatePanel(name) {
  $$('.rail-btn').forEach(b => b.classList.toggle('is-active', b.dataset.panel === name));
  els.panels.forEach(p => p.classList.toggle('is-active', p.id === `panel-${name}`));
  if (name === 'files' && state.fsPath) loadDirectory(state.fsPath);
  if (name === 'models') loadModels();
  if (name === 'settings') loadSettings();
  if (name === 'ralph') loadRalphStatus();
}

$$('.rail-btn').forEach(btn => {
  btn.addEventListener('click', () => activatePanel(btn.dataset.panel));
});

// ───────────────────────── Status / header ─────────────────────────

async function refreshStatus() {
  try {
    const s = await getJSON('/api/status');
    state.status = s;
    els.statusDot.className = 'status-dot is-online';
    els.statusLabel.textContent = s.has_key ? 'ready' : 'no key set';
    els.modelChip.textContent = `${s.provider_name} / ${s.model}`;
    if (els.providerSelect.children.length === 0) {
      s.providers.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p; opt.textContent = p;
        els.providerSelect.appendChild(opt);
      });
    }
    els.providerSelect.value = s.provider;
  } catch (e) {
    els.statusDot.className = 'status-dot is-error';
    els.statusLabel.textContent = 'offline';
  }
}

// ───────────────────────── Chat rendering ─────────────────────────

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** Minimal markdown: fenced code blocks and inline code only — enough for
 * tool output and code snippets without pulling in a markdown library. */
function renderMarkdownLite(text) {
  const escaped = escapeHtml(text);
  const withBlocks = escaped.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="lang-${lang || 'plain'}">${code}</code></pre>`;
  });
  return withBlocks.replace(/`([^`\n]+)`/g, '<code>$1</code>');
}

function scrollToBottom() {
  els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
}

function addUserMessage(text) {
  els.emptyState.classList.add('hidden');
  const row = document.createElement('div');
  row.className = 'msg role-user';
  row.innerHTML = `
    <div class="msg-avatar">you</div>
    <div class="msg-body"><div class="msg-content"></div></div>`;
  row.querySelector('.msg-content').textContent = text;
  els.messages.appendChild(row);
  scrollToBottom();
}

/** Creates (and returns handles into) the in-progress assistant message
 * row that streamed text/tool events get appended into. */
function startAssistantMessage() {
  els.emptyState.classList.add('hidden');
  const row = document.createElement('div');
  row.className = 'msg role-assistant';
  row.innerHTML = `
    <div class="msg-avatar">A</div>
    <div class="msg-body">
      <div class="msg-tools"></div>
      <div class="msg-content"><span class="typing-dots"><span></span><span></span><span></span></span></div>
    </div>`;
  els.messages.appendChild(row);
  scrollToBottom();
  return {
    toolsEl: row.querySelector('.msg-tools'),
    contentEl: row.querySelector('.msg-content'),
    text: '',
  };
}

function appendToolCard(toolsEl, name) {
  const card = document.createElement('div');
  card.className = 'tool-card';
  card.innerHTML = `
    <div class="tool-card-head"><span class="dot"></span><span class="tname"></span></div>
    <div class="tool-card-body"></div>`;
  card.querySelector('.tname').textContent = name + '(…)';
  card.querySelector('.tool-card-head').addEventListener('click', () => {
    card.classList.toggle('is-expanded');
  });
  toolsEl.appendChild(card);
  scrollToBottom();
  return card;
}

function finishToolCard(card, output, isError) {
  card.classList.add(isError ? 'is-error' : 'is-done');
  card.querySelector('.tool-card-body').textContent = output;
}

// ───────────────────────── Chat sending (SSE over fetch) ─────────────────────────

function autoGrowComposer() {
  els.composerInput.style.height = 'auto';
  els.composerInput.style.height = Math.min(els.composerInput.scrollHeight, 200) + 'px';
}
els.composerInput.addEventListener('input', autoGrowComposer);
els.composerInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    els.composer.requestSubmit();
  }
});

$$('.suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    els.composerInput.value = btn.dataset.prompt;
    autoGrowComposer();
    els.composer.requestSubmit();
  });
});

els.composer.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = els.composerInput.value.trim();
  if (!text || state.sending) return;
  els.composerInput.value = '';
  autoGrowComposer();
  addUserMessage(text);
  await sendChat(text);
});

async function sendChat(text) {
  state.sending = true;
  els.sendBtn.disabled = true;
  const handle = startAssistantMessage();
  let currentToolCard = null;
  let sawAnyText = false;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    if (!res.ok || !res.body) throw new Error('Stream failed to start (' + res.status + ')');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const lines = rawEvent.split('\n');
        let eventType = 'message';
        let dataStr = '';
        for (const line of lines) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
        }
        if (!dataStr) continue;
        let payload = {};
        try { payload = JSON.parse(dataStr); } catch { continue; }

        if (eventType === 'text') {
          if (!sawAnyText) { handle.contentEl.innerHTML = ''; sawAnyText = true; }
          handle.text += payload.text;
          handle.contentEl.innerHTML = renderMarkdownLite(handle.text);
          scrollToBottom();
        } else if (eventType === 'tool_call') {
          if (!sawAnyText) handle.contentEl.innerHTML = '';
          currentToolCard = appendToolCard(handle.toolsEl, payload.name);
        } else if (eventType === 'tool_result') {
          if (currentToolCard) finishToolCard(currentToolCard, payload.output, false);
        } else if (eventType === 'error') {
          if (!sawAnyText) handle.contentEl.innerHTML = '';
          handle.contentEl.innerHTML += `<div class="msg-error">${escapeHtml(payload.message)}</div>`;
          toast(payload.message, true);
        } else if (eventType === 'done') {
          // no-op; loop ends when stream closes
        }
      }
    }
    if (!sawAnyText && !handle.contentEl.querySelector('.msg-error')) {
      handle.contentEl.innerHTML = '<span class="muted">(no text response — see tool output above)</span>';
    }
  } catch (err) {
    handle.contentEl.innerHTML = `<div class="msg-error">${escapeHtml(err.message || String(err))}</div>`;
    toast('Chat error: ' + (err.message || err), true);
  } finally {
    state.sending = false;
    els.sendBtn.disabled = false;
    refreshStatus();
  }
}

els.clearBtn.addEventListener('click', async () => {
  await postJSON('/api/history/clear', {});
  els.messages.innerHTML = '';
  els.emptyState.classList.remove('hidden');
  toast('Conversation cleared');
});

// ───────────────────────── Files panel ─────────────────────────

async function loadDirectory(path) {
  state.fsPath = path;
  els.fsBreadcrumb.textContent = path;
  els.fileList.innerHTML = '<div class="muted pad">Loading…</div>';
  try {
    const data = await getJSON('/api/fs/list?path=' + encodeURIComponent(path));
    if (!data.ok) throw new Error(data.error || 'Failed to list directory');
    renderFileList(data.items, path);
  } catch (e) {
    els.fileList.innerHTML = `<div class="muted pad">${escapeHtml(e.message)}</div>`;
  }
}

function humanSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function renderFileList(items, currentPath) {
  els.fileList.innerHTML = '';

  if (currentPath !== '.') {
    const up = document.createElement('div');
    up.className = 'file-row is-dir';
    up.innerHTML = '<span class="ficon">⬆️</span><span>..</span>';
    up.addEventListener('click', () => {
      const parent = currentPath.split('/').slice(0, -1).join('/') || '.';
      loadDirectory(parent);
    });
    els.fileList.appendChild(up);
  }

  if (!items || items.length === 0) {
    els.fileList.innerHTML += '<div class="muted pad">Empty directory.</div>';
    return;
  }

  for (const item of items) {
    const row = document.createElement('div');
    row.className = 'file-row' + (item.is_dir ? ' is-dir' : '');
    row.innerHTML = `<span class="ficon"></span><span class="fname"></span><span class="fsize muted"></span>`;
    row.querySelector('.ficon').textContent = item.is_dir ? '📁' : '📄';
    row.querySelector('.fname').textContent = item.name;
    if (!item.is_dir) row.querySelector('.fsize').textContent = humanSize(item.size);
    row.addEventListener('click', () => {
      const childPath = currentPath === '.' ? item.name : currentPath + '/' + item.name;
      if (item.is_dir) loadDirectory(childPath);
      else openFile(childPath, row);
    });
    els.fileList.appendChild(row);
  }
}

async function openFile(path, rowEl) {
  $$('.file-row.is-active', els.fileList).forEach(r => r.classList.remove('is-active'));
  if (rowEl) rowEl.classList.add('is-active');
  els.fileViewerName.textContent = path;
  els.fileViewerContent.disabled = true;
  els.fileViewerContent.value = 'Loading…';
  els.fileSaveBtn.hidden = true;
  try {
    const data = await getJSON('/api/fs/read?path=' + encodeURIComponent(path));
    if (!data.ok) throw new Error(data.error || 'Failed to read file');
    state.fsCurrentFile = path;
    els.fileViewerContent.value = data.output;
    els.fileViewerContent.disabled = false;
    els.fileSaveBtn.hidden = false;
  } catch (e) {
    els.fileViewerContent.value = 'Error: ' + e.message;
  }
}

els.fileSaveBtn.addEventListener('click', async () => {
  if (!state.fsCurrentFile) return;
  try {
    const data = await postJSON('/api/fs/write', { path: state.fsCurrentFile, content: els.fileViewerContent.value });
    if (!data.ok) throw new Error(data.error || 'Save failed');
    toast('Saved ' + state.fsCurrentFile);
  } catch (e) {
    toast('Save failed: ' + e.message, true);
  }
});

els.fsRefreshBtn.addEventListener('click', () => loadDirectory(state.fsPath));

// ───────────────────────── Models panel ─────────────────────────

function priceClass(m) {
  if (m.is_free) return 'price-free';
  if (m.price_label === '?') return 'price-unknown';
  return 'price-paid';
}

function sourcePillClass(source) {
  if (source === 'live') return 'is-live';
  if (source === 'cache' || source === 'stale-cache') return 'is-cache';
  return 'is-fallback';
}

let modelsSort = 'name';

function applyModelsFilterSort() {
  const query = els.modelSearch.value.trim().toLowerCase();
  const freeOnly = els.freeOnlyToggle.checked;
  let list = state.modelsCache.models.filter(m => {
    if (freeOnly && !m.is_free) return false;
    if (query && !m.id.toLowerCase().includes(query) && !m.name.toLowerCase().includes(query)) return false;
    return true;
  });
  if (modelsSort === 'price') {
    list = [...list].sort((a, b) => {
      const av = a.is_free ? -1 : (a.price_label === '?' ? Infinity : parseFloat(a.price_label.replace(/[^0-9.]/g, '')) || 0);
      const bv = b.is_free ? -1 : (b.price_label === '?' ? Infinity : parseFloat(b.price_label.replace(/[^0-9.]/g, '')) || 0);
      return av - bv;
    });
  } else if (modelsSort === 'context') {
    list = [...list].sort((a, b) => (b.context_length || 0) - (a.context_length || 0));
  } else {
    list = [...list].sort((a, b) => a.id.localeCompare(b.id));
  }
  renderModelsTable(list);
}

function renderModelsTable(list) {
  els.modelsTableBody.innerHTML = '';
  if (list.length === 0) {
    els.modelsTableBody.innerHTML = '<tr><td colspan="5" class="muted pad">No models match.</td></tr>';
    return;
  }
  for (const m of list.slice(0, 200)) {
    const tr = document.createElement('tr');
    const isCurrent = m.id === state.status?.model;
    if (isCurrent) tr.classList.add('is-current');
    tr.innerHTML = `
      <td>${isCurrent ? '<span class="star">★</span>' : ''}</td>
      <td class="model-name"></td>
      <td>${escapeHtml(m.context_label)}</td>
      <td class="${priceClass(m)}"></td>
      <td>${m.supports_tools === true ? '<span class="tools-check">✓</span>' : m.supports_tools === false ? '<span class="tools-cross">✗</span>' : ''}</td>`;
    tr.querySelector('.model-name').textContent = m.id;
    tr.querySelector(`.${priceClass(m)}`).textContent = m.price_label;
    tr.addEventListener('click', async () => {
      try {
        await postJSON('/api/models/switch', { model: m.id });
        toast('Model set to ' + m.id);
        await refreshStatus();
        applyModelsFilterSort();
      } catch (e) {
        toast('Failed to switch model: ' + e.message, true);
      }
    });
    els.modelsTableBody.appendChild(tr);
  }
}

async function loadModels(forceRefresh = false) {
  els.modelsTableBody.innerHTML = '<tr><td colspan="5" class="muted pad">Fetching live models…</td></tr>';
  try {
    const provider = els.providerSelect.value || undefined;
    const qs = new URLSearchParams();
    if (provider) qs.set('provider', provider);
    if (forceRefresh) qs.set('refresh', '1');
    const data = await getJSON('/api/models?' + qs.toString());
    state.modelsCache = data;
    els.modelsSourcePill.textContent = data.source;
    els.modelsSourcePill.className = 'source-pill ' + sourcePillClass(data.source);
    applyModelsFilterSort();
  } catch (e) {
    els.modelsTableBody.innerHTML = `<tr><td colspan="5" class="muted pad">${escapeHtml(e.message)}</td></tr>`;
  }
}

els.providerSelect.addEventListener('change', async () => {
  try {
    await postJSON('/api/provider/switch', { provider: els.providerSelect.value });
    await refreshStatus();
    loadModels();
  } catch (e) {
    toast('Failed to switch provider: ' + e.message, true);
  }
});
els.modelSearch.addEventListener('input', applyModelsFilterSort);
els.freeOnlyToggle.addEventListener('change', applyModelsFilterSort);
els.modelsRefreshBtn.addEventListener('click', () => loadModels(true));
$$('.seg-btn', els.sortSeg).forEach(btn => {
  btn.addEventListener('click', () => {
    modelsSort = btn.dataset.sort;
    $$('.seg-btn', els.sortSeg).forEach(b => b.classList.toggle('is-active', b === btn));
    applyModelsFilterSort();
  });
});

// ───────────────────────── Settings panel ─────────────────────────

const PROVIDER_KEY_LABELS = {
  openrouter_api_key: 'OpenRouter',
  groq_api_key: 'Groq',
  anthropic_api_key: 'Anthropic',
  openai_api_key: 'OpenAI',
  ollama_api_key: 'Ollama',
};

async function loadSettings() {
  try {
    const cfg = await getJSON('/api/config');
    els.keyFields.innerHTML = '';
    for (const [field, label] of Object.entries(PROVIDER_KEY_LABELS)) {
      const row = document.createElement('div');
      row.className = 'key-field-row';
      row.innerHTML = `<label></label><input class="text-input" type="password" placeholder="not set" style="flex:1">
        <button class="ghost-btn small" type="button">Save</button>`;
      row.querySelector('label').textContent = label;
      const input = row.querySelector('input');
      const btn = row.querySelector('button');
      input.value = '';
      input.dataset.masked = cfg[field] || '';
      input.placeholder = cfg[field] ? cfg[field] : 'not set';
      btn.addEventListener('click', async () => {
        if (!input.value.trim()) { toast('Enter a key first', true); return; }
        await postJSON('/api/config', { [field]: input.value.trim() });
        toast(label + ' key saved');
        input.value = '';
        loadSettings();
      });
      els.keyFields.appendChild(row);
    }

    els.workspaceInput.value = cfg.workspace || '';
    els.safeModeToggle.checked = !!cfg.safe_mode;
    els.streamToggle.checked = !!cfg.stream;
    els.maxTokensInput.value = cfg.max_tokens || 4096;
    els.temperatureInput.value = cfg.temperature ?? 0.7;
  } catch (e) {
    toast('Failed to load settings: ' + e.message, true);
  }
}

els.workspaceSaveBtn.addEventListener('click', async () => {
  try {
    await postJSON('/api/config', { workspace: els.workspaceInput.value.trim() });
    toast('Workspace updated');
    refreshStatus();
  } catch (e) {
    toast('Failed: ' + e.message, true);
  }
});
els.safeModeToggle.addEventListener('change', () => postJSON('/api/config', { safe_mode: els.safeModeToggle.checked }));
els.streamToggle.addEventListener('change', () => postJSON('/api/config', { stream: els.streamToggle.checked }));
els.maxTokensInput.addEventListener('change', () => postJSON('/api/config', { max_tokens: parseInt(els.maxTokensInput.value, 10) || 4096 }));
els.temperatureInput.addEventListener('change', () => postJSON('/api/config', { temperature: parseFloat(els.temperatureInput.value) || 0.7 }));

// ───────────────────────── Ralph panel ─────────────────────────

function ralphStatusLabel(s) {
  return { pending: 'pending', in_progress: 'running', done: 'done', failed: 'failed', skipped: 'skipped' }[s] || s;
}

function renderRalphTasks(tasks) {
  els.ralphTaskList.innerHTML = '';
  if (!tasks || tasks.length === 0) {
    els.ralphTaskList.innerHTML = '<div class="muted pad">No tasks yet. Add one above.</div>';
    return;
  }
  const iconChar = { pending: '○', in_progress: '●', done: '✓', failed: '✗', skipped: '–' };
  for (const t of tasks) {
    const row = document.createElement('div');
    row.className = `ralph-task-row is-${t.status}`;
    row.dataset.taskId = t.id;
    row.innerHTML = `
      <span class="ralph-task-icon"></span>
      <div class="ralph-task-title">
        <div></div>
        <div class="ralph-task-notes"></div>
      </div>`;
    row.querySelector('.ralph-task-icon').textContent = iconChar[t.status] || '?';
    row.querySelector('.ralph-task-title > div').textContent = `#${t.id} ${t.title}`;
    if (t.notes) row.querySelector('.ralph-task-notes').textContent = t.notes.slice(0, 80);
    els.ralphTaskList.appendChild(row);
  }
}

function setRalphRunningUI(running) {
  state.ralphRunning = running;
  els.ralphRunBtn.disabled = running;
  els.ralphStopBtn.hidden = !running;
  els.ralphClearBtn.disabled = running;
}

async function loadRalphStatus() {
  try {
    const data = await getJSON('/api/ralph');
    els.ralphCountsPill.textContent =
      `${data.counts.pending} pending · ${data.counts.done} done · ${data.counts.failed} failed`;
    renderRalphTasks(data.tasks);
    setRalphRunningUI(data.running);
  } catch (e) {
    toast('Failed to load Ralph status: ' + e.message, true);
  }
}

els.ralphAddBtn.addEventListener('click', async () => {
  const title = els.ralphTaskInput.value.trim();
  if (!title) return;
  try {
    await postJSON('/api/ralph/add', { title });
    els.ralphTaskInput.value = '';
    loadRalphStatus();
  } catch (e) {
    toast('Failed to add task: ' + e.message, true);
  }
});
els.ralphTaskInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') els.ralphAddBtn.click();
});

els.ralphClearBtn.addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/ralph/clear', {});
    if (!data.ok) { toast(data.error || 'Failed to clear', true); return; }
    els.ralphLog.innerHTML = '<div class="muted pad">Task output will stream here while the loop runs.</div>';
    loadRalphStatus();
  } catch (e) {
    toast('Failed to clear: ' + e.message, true);
  }
});

els.ralphStopBtn.addEventListener('click', async () => {
  try {
    const data = await postJSON('/api/ralph/stop', {});
    toast(data.message || 'Stop requested');
  } catch (e) {
    toast('Failed to stop: ' + e.message, true);
  }
});

function ralphLogAppend(html) {
  if (els.ralphLog.querySelector('.muted.pad')) els.ralphLog.innerHTML = '';
  const div = document.createElement('div');
  div.innerHTML = html;
  els.ralphLog.appendChild(div.firstElementChild || div);
  els.ralphLog.scrollTop = els.ralphLog.scrollHeight;
}

els.ralphRunBtn.addEventListener('click', async () => {
  if (state.ralphRunning) return;
  const maxIterations = parseInt(els.ralphMaxIterations.value, 10) || 35;
  setRalphRunningUI(true);
  els.ralphLog.innerHTML = '';
  let currentTextEl = null;

  try {
    const res = await fetch('/api/ralph/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_iterations: maxIterations }),
    });
    if (res.status === 409) {
      const data = await res.json();
      toast(data.error || 'A run is already in progress', true);
      setRalphRunningUI(true); // something else is genuinely running
      return;
    }
    if (!res.ok || !res.body) throw new Error('Stream failed to start (' + res.status + ')');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let eventType = 'message', dataStr = '';
        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataStr += line.slice(5).trim();
        }
        if (!dataStr) continue;
        let payload = {};
        try { payload = JSON.parse(dataStr); } catch { continue; }

        if (eventType === 'task_start') {
          ralphLogAppend(`<div class="ralph-log-rule">Task ${payload.index}/${payload.total}: ${escapeHtml(payload.task.title)}</div>`);
          currentTextEl = null;
          renderRalphTasks((await getJSON('/api/ralph')).tasks);
        } else if (eventType === 'text') {
          if (!currentTextEl) {
            currentTextEl = document.createElement('div');
            currentTextEl.className = 'ralph-log-entry';
            els.ralphLog.appendChild(currentTextEl);
          }
          currentTextEl.textContent += payload.text;
          els.ralphLog.scrollTop = els.ralphLog.scrollHeight;
        } else if (eventType === 'tool_call') {
          ralphLogAppend(`<div class="ralph-log-entry ralph-log-tool">⚙ ${escapeHtml(payload.name)}(…)</div>`);
          currentTextEl = null;
        } else if (eventType === 'error') {
          ralphLogAppend(`<div class="ralph-log-entry ralph-log-error">${escapeHtml(payload.message)}</div>`);
          currentTextEl = null;
        } else if (eventType === 'task_done') {
          const label = payload.outcome === 'done' ? '✓ complete' : '✗ failed';
          ralphLogAppend(`<div class="ralph-log-status">${label}: task #${payload.task.id}</div>`);
          currentTextEl = null;
          renderRalphTasks((await getJSON('/api/ralph')).tasks);
        } else if (eventType === 'finished') {
          const labels = {
            completed: 'All tasks complete!',
            max_iterations: 'Stopped: hit the iteration cap.',
            stopped: 'Stopped by request.',
            no_tasks: 'No tasks to run.',
          };
          ralphLogAppend(`<div class="ralph-log-status">${labels[payload.reason] || payload.reason}</div>`);
          toast(labels[payload.reason] || payload.reason);
        }
      }
    }
  } catch (err) {
    ralphLogAppend(`<div class="ralph-log-entry ralph-log-error">${escapeHtml(err.message || String(err))}</div>`);
    toast('Ralph run error: ' + (err.message || err), true);
  } finally {
    setRalphRunningUI(false);
    loadRalphStatus();
  }
});

// ───────────────────────── Boot ─────────────────────────

async function boot() {
  await refreshStatus();
  setInterval(refreshStatus, 15000);
}
boot();
