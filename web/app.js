// CTO Copilot UI, Table Directory & PR Controller
document.addEventListener('DOMContentLoaded', () => {
  // Navigation & View elements
  const homeView = document.getElementById('homeView');
  const prsView = document.getElementById('prsView');
  const dashboardView = document.getElementById('dashboardView');
  const staleView = document.getElementById('staleView');
  const chatView = document.getElementById('chatView');
  const navHomeBtn = document.getElementById('navHomeBtn');
  const navPrsBtn = document.getElementById('navPrsBtn');
  const navDashBtn = document.getElementById('navDashBtn');
  const navStaleBtn = document.getElementById('navStaleBtn');
  const navChatBtn = document.getElementById('navChatBtn');
  const navPrCount = document.getElementById('navPrCount');
  const navStaleCount = document.getElementById('navStaleCount');
  const refreshTableBtn = document.getElementById('refreshTableBtn');
  const refreshStaleBtn = document.getElementById('refreshStaleBtn');
  const prsTableBody = document.getElementById('prsTableBody');
  const tableEmptyState = document.getElementById('tableEmptyState');

  // Drawer elements
  const sideDrawer = document.getElementById('sideDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const toggleDrawerBtn = document.getElementById('toggleDrawerBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const sidePullHandle = document.getElementById('sidePullHandle');
  const drawerPrBtn = document.getElementById('drawerPrBtn');
  const drawerDashBtn = document.getElementById('drawerDashBtn');
  const drawerStaleBtn = document.getElementById('drawerStaleBtn');
  const drawerChatBtn = document.getElementById('drawerChatBtn');

  // Stale table elements (threshold synced from backend /api/prs, configured via PR_STALE_THRESHOLD_DAYS)
  const staleTableBody = document.getElementById('staleTableBody');
  const staleEmptyState = document.getElementById('staleEmptyState');
  const staleCountBadge = document.getElementById('staleCountBadge');
  let staleDaysThreshold = 5;

  // PR Filters
  const filterBtns = document.querySelectorAll('.filter-btn');

  // Dashboard elements
  const timeframeBtns = document.querySelectorAll('.timeframe-btn');
  const dashTimeframeBadge = document.getElementById('dashTimeframeBadge');
  const dashTotalPrs = document.getElementById('dashTotalPrs');
  const dashTotalEngineers = document.getElementById('dashTotalEngineers');
  const dashTopContributor = document.getElementById('dashTopContributor');
  const dashTopScore = document.getElementById('dashTopScore');
  const leaderboardTableBody = document.getElementById('leaderboardTableBody');
  const dashEmptyState = document.getElementById('dashEmptyState');

  // Chatbot elements
  const chatSessionsList = document.getElementById('chatSessionsList');
  const btnNewChat = document.getElementById('btnNewChat');
  const activeChatTitle = document.getElementById('activeChatTitle');
  const chatMessagesContainer = document.getElementById('chatMessagesContainer');
  const chatTypingIndicator = document.getElementById('chatTypingIndicator');
  const chatInputForm = document.getElementById('chatInputForm');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');

  // State
  let allPRs = [];
  let currentFilter = 'all';
  let currentDays = 30;
  let activeSessionId = null;
  let chatSessions = [];

  // Automatically connect to FastAPI backend at port 8000
  const API_BASE = (window.location.protocol.startsWith('http') && window.location.port === '8000')
    ? window.location.origin
    : 'http://localhost:8000';

  // Navigation switching
  function switchView(viewName) {
    // Reset all views & navs
    homeView?.classList.remove('active');
    prsView?.classList.remove('active');
    dashboardView?.classList.remove('active');
    staleView?.classList.remove('active');
    chatView?.classList.remove('active');
    navHomeBtn?.classList.remove('active');
    navPrsBtn?.classList.remove('active');
    navDashBtn?.classList.remove('active');
    navStaleBtn?.classList.remove('active');
    navChatBtn?.classList.remove('active');

    if (viewName === 'prs') {
      prsView?.classList.add('active');
      navPrsBtn?.classList.add('active');
      loadPullRequests();
    } else if (viewName === 'dashboard') {
      dashboardView?.classList.add('active');
      navDashBtn?.classList.add('active');
      loadDashboard(currentDays);
    } else if (viewName === 'stale') {
      staleView?.classList.add('active');
      navStaleBtn?.classList.add('active');
      loadPullRequests();
    } else if (viewName === 'chat') {
      chatView?.classList.add('active');
      navChatBtn?.classList.add('active');
      loadChatSessions();
    } else {
      homeView?.classList.add('active');
      navHomeBtn?.classList.add('active');
    }
  }

  navHomeBtn?.addEventListener('click', () => switchView('home'));
  navPrsBtn?.addEventListener('click', () => switchView('prs'));
  navDashBtn?.addEventListener('click', () => switchView('dashboard'));
  navStaleBtn?.addEventListener('click', () => switchView('stale'));
  navChatBtn?.addEventListener('click', () => switchView('chat'));

  // Drawer buttons switch views directly
  drawerPrBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('prs');
  });

  drawerDashBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('dashboard');
  });

  drawerStaleBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('stale');
  });

  drawerChatBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('chat');
  });

  // Drawer open / close
  const openDrawer = () => {
    sideDrawer?.classList.add('open');
    drawerBackdrop?.classList.add('active');
    loadPullRequests();
  };

  const closeDrawer = () => {
    sideDrawer?.classList.remove('open');
    drawerBackdrop?.classList.remove('active');
  };

  toggleDrawerBtn?.addEventListener('click', () => {
    if (sideDrawer?.classList.contains('open')) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  sidePullHandle?.addEventListener('click', openDrawer);
  closeDrawerBtn?.addEventListener('click', closeDrawer);
  drawerBackdrop?.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sideDrawer?.classList.contains('open')) {
      closeDrawer();
    }
  });

  refreshTableBtn?.addEventListener('click', () => {
    refreshTableBtn.classList.add('spinning');
    loadPullRequests().finally(() => {
      refreshTableBtn.classList.remove('spinning');
    });
  });

  refreshStaleBtn?.addEventListener('click', () => {
    refreshStaleBtn.classList.add('spinning');
    loadPullRequests().finally(() => {
      refreshStaleBtn.classList.remove('spinning');
    });
  });

  // Timestamp formatter
  function formatTimestamp(isoStr) {
    if (!isoStr) return 'Just now';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoStr;
    }
  }

  // Status filter switching (client-side, no extra backend call)
  filterBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      filterBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter || 'all';
      renderPRs(allPRs);
    });
  });

  // Helper to render Impact Badge
  function renderImpactBadge(score) {
    if (score !== null && score !== undefined) {
      let levelClass = 'low';
      if (score >= 8.0) levelClass = 'high';
      else if (score >= 6.0) levelClass = 'medium';
      else if (score >= 4.0) levelClass = 'moderate';

      return `<span class="impact-badge ${levelClass}" title="Impact Score: ${score}/10">⚡ ${score}/10</span>`;
    }
    return `<span class="impact-badge low" style="opacity: 0.7;" title="Impact evaluation in progress">⚡ —</span>`;
  }

  // Days since creation (for stale detection)
  function daysSince(isoStr) {
    if (!isoStr) return 0;
    try {
      const created = new Date(isoStr);
      const diffMs = Date.now() - created.getTime();
      return Math.floor(diffMs / (1000 * 60 * 60 * 24));
    } catch {
      return 0;
    }
  }

  // Render Table 1 — comprehensive: # | ID | Author | Created | Summary | State | Score | PR
  function renderPRs(prs) {
    allPRs = prs ? [...prs] : [];
    const totalCount = allPRs.length;
    if (navPrCount) navPrCount.textContent = totalCount;

    // Apply status filter: open, merged, closed
    const filtered = currentFilter === 'all'
      ? allPRs
      : allPRs.filter((pr) => (pr.state || '').toLowerCase() === currentFilter);

    // Handle Empty State
    if (!filtered || filtered.length === 0) {
      if (prsTableBody) prsTableBody.innerHTML = '';
      if (tableEmptyState) {
        tableEmptyState.style.display = 'flex';
        const emptyTitle = tableEmptyState.querySelector('h4');
        const emptyDesc = tableEmptyState.querySelector('p');
        if (!allPRs || allPRs.length === 0) {
          if (emptyTitle) emptyTitle.textContent = 'No PRs Detected Yet';
          if (emptyDesc) emptyDesc.textContent = 'Pull requests will automatically populate here with full AI summaries once submitted on GitHub.';
        } else {
          if (emptyTitle) emptyTitle.textContent = `No ${currentFilter} PRs`;
          if (emptyDesc) emptyDesc.textContent = `There are no pull requests with status "${currentFilter}" right now. Try another filter.`;
        }
      }
    } else if (tableEmptyState) {
      tableEmptyState.style.display = 'none';

      // Populate Table 1 — one row per PR with serial #, ID, author, date, summary, state, score
      if (prsTableBody) {
        prsTableBody.innerHTML = filtered.map((pr, idx) => `
        <tr>
          <td><span class="table-date-cell" style="font-weight: 800;">${idx + 1}</span></td>
          <td><span class="branch-tag">#${pr.number}</span></td>
          <td>
            <div class="table-author-cell">
              ${pr.author_avatar ? `<img src="${pr.author_avatar}" class="table-author-avatar" alt="${pr.author}"/>` : `<span class="table-author-avatar">${(pr.author || '?').slice(0, 2).toUpperCase()}</span>`}
              <span>${escapeHtml(pr.author)}</span>
            </div>
          </td>
          <td>
            <span class="table-date-cell">${formatTimestamp(pr.created_at)}</span>
          </td>
          <td>
            <div class="table-summary-box">
              ${pr.summary ? escapeHtml(pr.summary) : '<em>Generating executive summary automatically...</em>'}
            </div>
          </td>
          <td>
            <span class="pr-state-badge ${pr.state}">${pr.state}</span>
            ${pr.is_overdue ? `<span class="overdue-pill" title="Overdue SLA threshold exceeded">⚠️ Overdue (${pr.overdue_days || daysSince(pr.created_at)}d)</span>` : ''}
          </td>
          <td>
            ${renderImpactBadge(pr.impact_score)}
          </td>
          <td>
            <a href="${pr.html_url}" target="_blank" rel="noopener noreferrer" class="table-pr-title" style="font-size: 0.82rem;">
              ${escapeHtml(pr.title)}
            </a>
            <div class="table-pr-branches">
              <span class="branch-tag">${escapeHtml(pr.base_branch)}</span>
              <span>←</span>
              <span class="branch-tag">${escapeHtml(pr.head_branch)}</span>
            </div>
          </td>
        </tr>
      `).join('');
      }
    }

    // Always refresh Table 3 (stale) from the full list, independent of the filter
    renderStalePRs(allPRs);
  }

  // Render Table 3 — stale: open PRs older than the backend-configured threshold
  function renderStalePRs(prs) {
    // Keep the "(X days)" label in sync wherever this table renders
    document.querySelectorAll('.stale-threshold-num').forEach(el => el.textContent = staleDaysThreshold);

    const stale = (prs || [])
      .filter((pr) => pr.is_overdue || ((pr.state || '').toLowerCase() === 'open' && daysSince(pr.created_at) >= staleDaysThreshold))
      .sort((a, b) => (b.overdue_days || daysSince(b.created_at)) - (a.overdue_days || daysSince(a.created_at)));

    if (staleCountBadge) staleCountBadge.textContent = `${stale.length} Overdue`;
    if (navStaleCount) navStaleCount.textContent = stale.length;

    if (!stale || stale.length === 0) {
      if (staleTableBody) staleTableBody.innerHTML = '';
      if (staleEmptyState) staleEmptyState.style.display = 'flex';
      return;
    }

    if (staleEmptyState) staleEmptyState.style.display = 'none';

    if (staleTableBody) {
      staleTableBody.innerHTML = stale.map((pr, idx) => {
        const days = pr.overdue_days || daysSince(pr.created_at);
        return `
        <tr style="background: #fff7f7;">
          <td><span class="table-date-cell" style="font-weight: 800;">${idx + 1}</span></td>
          <td>
            <div class="table-author-cell">
              ${pr.author_avatar ? `<img src="${pr.author_avatar}" class="table-author-avatar" alt="${pr.author}"/>` : `<span class="table-author-avatar">${(pr.author || '?').slice(0, 2).toUpperCase()}</span>`}
              <span>${escapeHtml(pr.author)}</span>
            </div>
          </td>
          <td>
            <a href="${pr.html_url}" target="_blank" rel="noopener noreferrer" class="table-pr-title" style="font-size: 0.82rem;">
              #${pr.number} ${escapeHtml(pr.title)}
            </a>
            <div class="table-pr-branches">
              <span class="branch-tag">${escapeHtml(pr.base_branch)}</span>
              <span>←</span>
              <span class="branch-tag">${escapeHtml(pr.head_branch)}</span>
            </div>
          </td>
          <td>
            <div class="table-summary-box">
              ${pr.summary ? escapeHtml(pr.summary) : '<em>Generating executive summary automatically...</em>'}
            </div>
          </td>
          <td>
            <span class="table-date-cell">${formatTimestamp(pr.created_at)}</span>
          </td>
          <td>
            <span class="overdue-days-pill">⏳ ${days}d open</span>
          </td>
        </tr>
      `;
      }).join('');
    }
  }

  // Timeframe filter tabs for Dashboard
  timeframeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      timeframeBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentDays = parseInt(btn.dataset.days, 10) || 30;
      if (dashTimeframeBadge) dashTimeframeBadge.textContent = btn.textContent;
      loadDashboard(currentDays);
    });
  });

  // Render Dashboard
  function renderDashboard(data) {
    if (!data) return;

    if (dashTotalPrs) dashTotalPrs.textContent = data.total_prs || 0;
    if (dashTotalEngineers) dashTotalEngineers.textContent = data.total_engineers || 0;

    // SLA threshold: single source of truth is the backend (.env) — sync it;
    // renderStalePRs below refreshes the "(X days)" labels everywhere.
    staleDaysThreshold = data.stale_threshold_days || staleDaysThreshold;
    renderStalePRs(allPRs);

    const list = data.leaderboard || [];

    if (list.length > 0) {
      const top = list[0];
      if (dashTopContributor) dashTopContributor.textContent = top.author;
      if (dashTopScore) {
        dashTopScore.textContent = `${top.total_impact_points} pts (${top.total_prs} PRs, avg ${top.avg_impact_score}/10)`;
      }

      if (dashEmptyState) dashEmptyState.style.display = 'none';

      if (leaderboardTableBody) {
        leaderboardTableBody.innerHTML = list.map((eng, idx) => {
          const rank = idx + 1;
          const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : '';
          const rawTier = (eng.tier || '').toLowerCase();
          const tierClass = rawTier.includes('critical') ? 'critical' : rawTier.includes('high') ? 'high' : rawTier.includes('solid') ? 'solid' : 'routine';
          const tierName = eng.tier || 'Routine';
          const avgScore = eng.avg_impact_score ? eng.avg_impact_score.toFixed(1) : '—';
          const barWidth = Math.min(100, Math.max(10, Math.round(((eng.avg_impact_score || 5) / 10) * 100)));

          const avatarHtml = eng.author_avatar
            ? `<img src="${eng.author_avatar}" class="table-author-avatar" alt="${eng.author}"/>`
            : `<span class="table-author-avatar">${eng.author.slice(0, 2).toUpperCase()}</span>`;

          return `
            <tr>
              <td>
                <span class="rank-badge ${rankClass}">#${rank}</span>
              </td>
              <td>
                <div class="table-author-cell">
                  ${avatarHtml}
                  <span style="font-weight: 600;">${escapeHtml(eng.author)}</span>
                </div>
              </td>
              <td>
                <strong style="font-size: 0.95rem;">${eng.total_prs}</strong> <span style="color: var(--text-muted); font-size: 0.8rem;">PRs</span>
              </td>
              <td>
                <div class="impact-meter-cell">
                  <span class="impact-score-num">${avgScore} <span style="font-size: 0.72rem; color: var(--text-muted); font-weight: normal;">/ 10</span></span>
                  <div class="impact-meter-bar">
                    <div class="impact-meter-fill ${eng.avg_impact_score >= 8.5 ? 'critical' : ''}" style="width: ${barWidth}%;"></div>
                  </div>
                </div>
              </td>
              <td>
                <span style="font-weight: 800; color: var(--primary-accent); font-size: 0.95rem;">${eng.total_impact_points}</span> <span style="color: var(--text-muted); font-size: 0.8rem;">pts</span>
              </td>
              <td>
                <span class="tier-pill ${tierClass}">${tierName}</span>
              </td>
            </tr>
          `;
        }).join('');
      }
    } else {
      if (dashTopContributor) dashTopContributor.textContent = '—';
      if (dashTopScore) dashTopScore.textContent = 'No PRs submitted in this timeframe';
      if (leaderboardTableBody) leaderboardTableBody.innerHTML = '';
      if (dashEmptyState) dashEmptyState.style.display = 'flex';
    }
  }

  // Fetch Dashboard from FastAPI backend
  async function loadDashboard(days = currentDays) {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard?days=${days}`);
      if (!res.ok) throw new Error('Failed to load dashboard data');
      const data = await res.json();
      renderDashboard(data);
    } catch (err) {
      console.warn('Dashboard fetch error:', err);
    }
  }

  // Load PRs from FastAPI backend (also syncs the stale threshold from .env config)
  async function loadPullRequests() {
    try {
      const res = await fetch(`${API_BASE}/api/prs`);
      if (!res.ok) throw new Error('Failed to load PRs');
      const data = await res.json();
      if (data.stale_threshold_days) staleDaysThreshold = data.stale_threshold_days;
      renderPRs(data.prs);
    } catch {
      // Backend unreachable fallback
    }
  }

  // Initial load
  loadPullRequests();

  // Polling every 25 seconds for new PRs
  setInterval(() => {
    loadPullRequests();
  }, 25000);

  // =========================================================================
  // Chatbot & LangGraph Read-Only MySQL Controller
  // =========================================================================

  async function loadChatSessions() {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions`);
      if (!res.ok) throw new Error('Failed to load chat sessions');
      const data = await res.json();
      chatSessions = data.sessions || [];
      renderSessionsList(chatSessions);

      if (chatSessions.length === 0) {
        // Automatically create first session
        await createNewChatSession();
      } else if (!activeSessionId || !chatSessions.some(s => s.id === activeSessionId)) {
        // Select the most recent session
        selectChatSession(chatSessions[0].id);
      }
    } catch (err) {
      console.warn('Chat sessions fetch error:', err);
    }
  }

  function renderSessionsList(sessions) {
    if (!chatSessionsList) return;
    if (!sessions || sessions.length === 0) {
      chatSessionsList.innerHTML = '<div style="padding: 16px; font-size: 0.78rem; color: #94a3b8; text-align: center;">No conversations yet</div>';
      return;
    }

    chatSessionsList.innerHTML = sessions.map(s => {
      const isActive = s.id === activeSessionId ? 'active' : '';
      const timeStr = s.created_at ? formatTimestamp(s.created_at) : '';
      return `
        <div class="session-item ${isActive}" data-id="${s.id}">
          <div class="session-item-content">
            <span class="session-item-title">${escapeHtml(s.title || 'Conversation')}</span>
            <span class="session-item-time">${timeStr}</span>
          </div>
          <button class="session-delete-btn" data-delete-id="${s.id}" title="Delete session">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;
    }).join('');

    // Attach click events
    chatSessionsList.querySelectorAll('.session-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.session-delete-btn')) return;
        const sId = item.dataset.id;
        selectChatSession(sId);
      });
    });

    chatSessionsList.querySelectorAll('.session-delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const sId = btn.dataset.deleteId;
        deleteChatSession(sId);
      });
    });
  }

  async function createNewChatSession() {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Conversation' })
      });
      if (!res.ok) throw new Error('Failed to create session');
      const newSession = await res.json();
      activeSessionId = newSession.id;
      await loadChatSessions();
      selectChatSession(newSession.id);
    } catch (err) {
      console.error('Error creating chat session:', err);
    }
  }

  async function deleteChatSession(sessionId) {
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    try {
      await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
      if (activeSessionId === sessionId) {
        activeSessionId = null;
      }
      await loadChatSessions();
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  }

  async function selectChatSession(sessionId) {
    activeSessionId = sessionId;
    const sessionObj = chatSessions.find(s => s.id === sessionId);
    if (activeChatTitle && sessionObj) {
      activeChatTitle.textContent = sessionObj.title || 'Conversation';
    }

    // Highlight in list
    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === sessionId);
    });

    await loadSessionMessages(sessionId);
  }

  async function loadSessionMessages(sessionId) {
    if (!chatMessagesContainer) return;
    chatMessagesContainer.innerHTML = '';

    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`);
      if (!res.ok) throw new Error('Failed to fetch messages');
      const data = await res.json();
      const messages = data.messages || [];

      if (messages.length === 0) {
        // Render welcome message
        chatMessagesContainer.innerHTML = `
          <div class="chat-bubble assistant">
            <div class="bubble-avatar">🤖</div>
            <div class="bubble-content">
              <p><strong>Hello! I am your autonomous CTO Copilot.</strong></p>
              <p>I have direct, secure <strong>read-only access to the MySQL database</strong> (<code>pull_requests</code> and <code>engineers</code>). You can ask me anything about:</p>
              <ul>
                <li>Open and overdue pull requests</li>
                <li>Architectural impact scores and summaries</li>
                <li>Contributor rankings, tiers, and velocities</li>
                <li>General engineering leadership and codebase questions</li>
              </ul>
              <p style="margin-top: 8px; color: #64748b; font-size: 0.8rem;">Click a prompt above or type your question below to begin!</p>
            </div>
          </div>
        `;
      } else {
        renderMessages(messages);
      }
      scrollChatToBottom();
    } catch (err) {
      console.warn('Error loading messages:', err);
    }
  }

  function renderMessages(messages) {
    if (!chatMessagesContainer) return;
    chatMessagesContainer.innerHTML = messages.map(m => {
      const isUser = m.role === 'user';
      const avatar = isUser ? '👤' : '🤖';
      const formattedContent = isUser ? escapeHtml(m.content) : renderMarkdown(m.content);
      return `
        <div class="chat-bubble ${isUser ? 'user' : 'assistant'}">
          <div class="bubble-avatar">${avatar}</div>
          <div class="bubble-content">${formattedContent}</div>
        </div>
      `;
    }).join('');
  }

  async function sendChatMessage(text) {
    if (!text || !text.trim() || !activeSessionId) return;
    const cleanText = text.trim();

    // 1. Immediately append user bubble to UI
    appendMessageBubble('user', cleanText);
    scrollChatToBottom();

    // 2. Clear input
    if (chatInput) {
      chatInput.value = '';
      chatInput.style.height = 'auto';
    }

    // 3. Show typing indicator
    if (chatTypingIndicator) chatTypingIndicator.style.display = 'flex';
    if (chatSendBtn) chatSendBtn.disabled = true;
    scrollChatToBottom();

    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${activeSessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: cleanText })
      });
      if (!res.ok) throw new Error('Agent failed to respond');
      const data = await res.json();

      // 4. Append assistant bubble
      appendMessageBubble('assistant', data.reply);
      scrollChatToBottom();

      // Refresh sessions to sync updated title
      const sessRes = await fetch(`${API_BASE}/api/chat/sessions`);
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        chatSessions = sessData.sessions || [];
        renderSessionsList(chatSessions);
        const curr = chatSessions.find(s => s.id === activeSessionId);
        if (curr && activeChatTitle) activeChatTitle.textContent = curr.title;
      }
    } catch (err) {
      appendMessageBubble('assistant', `⚠️ Error: Could not get a response from the agent. (${err.message})`);
    } finally {
      if (chatTypingIndicator) chatTypingIndicator.style.display = 'none';
      if (chatSendBtn) chatSendBtn.disabled = false;
      scrollChatToBottom();
    }
  }

  function appendMessageBubble(role, content) {
    if (!chatMessagesContainer) return;
    const isUser = role === 'user';
    const avatar = isUser ? '👤' : '🤖';
    const formattedContent = isUser ? escapeHtml(content) : renderMarkdown(content);

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${isUser ? 'user' : 'assistant'}`;
    bubble.innerHTML = `
      <div class="bubble-avatar">${avatar}</div>
      <div class="bubble-content">${formattedContent}</div>
    `;
    chatMessagesContainer.appendChild(bubble);
  }

  function scrollChatToBottom() {
    if (chatMessagesContainer) {
      chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
  }

  // Quick chip suggestion clicks
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      if (prompt) sendChatMessage(prompt);
    });
  });

  // Chat Form Submit
  chatInputForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const val = chatInput?.value || '';
    sendChatMessage(val);
  });

  // Chat Textarea Enter to submit (Shift+Enter for newline)
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(chatInput.value);
    }
  });

  // Auto-resize chat textarea
  chatInput?.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });

  btnNewChat?.addEventListener('click', () => {
    createNewChatSession();
  });

  // Basic Markdown Renderer for LLM answers (tables, code, lists, bold)
  function renderMarkdown(md) {
    if (!md) return '';
    let html = escapeHtml(md);

    // Code blocks
    html = html.replace(/```([a-zA-Z]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Markdown tables
    const tableRegex = /((?:\|[^\n]+\|\r?\n)+)/g;
    html = html.replace(tableRegex, (match) => {
      const rows = match.trim().split(/\r?\n/).map(r => r.trim());
      if (rows.length < 2) return match;

      let tableHtml = '<table>';
      let isHeader = true;

      rows.forEach((row, i) => {
        // Skip separator rows like |---|---|
        if (/^\|[\s\-:|]+\|$/.test(row)) {
          isHeader = false;
          return;
        }

        const cols = row.split('|').slice(1, -1).map(c => c.trim());
        tableHtml += '<tr>';
        cols.forEach(col => {
          if (isHeader) {
            tableHtml += `<th>${col}</th>`;
          } else {
            tableHtml += `<td>${col}</td>`;
          }
        });
        tableHtml += '</tr>';
        if (i === 0) isHeader = false;
      });

      tableHtml += '</table>';
      return tableHtml;
    });

    // Paragraphs & line breaks
    html = html.split(/\n\n+/).map(p => {
      if (p.startsWith('<pre>') || p.startsWith('<table>')) return p;
      return `<p>${p.replace(/\n/g, '<br/>')}</p>`;
    }).join('');

    return html;
  }

  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});

