// CTO Copilot dashboard controller
document.addEventListener('DOMContentLoaded', () => {
  const homeView = document.getElementById('homeView');
  const prsView = document.getElementById('prsView');
  const dashboardView = document.getElementById('dashboardView');
  const staleView = document.getElementById('staleView');
  const chatView = document.getElementById('chatView');
  const reportsView = document.getElementById('reportsView');
  const voiceView = document.getElementById('voiceView');
  const brandBtn = document.getElementById('brandBtn');
  const homeNavBtn = document.getElementById('homeNavBtn');
  const currentActiveViewBadge = document.getElementById('currentActiveViewBadge');
  const activeViewIcon = document.getElementById('activeViewIcon');
  const activeViewLabel = document.getElementById('activeViewLabel');
  const activeViewCounter = document.getElementById('activeViewCounter');

  const refreshTableBtn = document.getElementById('refreshTableBtn');
  const refreshStaleBtn = document.getElementById('refreshStaleBtn');
  const prsTableBody = document.getElementById('prsTableBody');
  const tableEmptyState = document.getElementById('tableEmptyState');

  // Workspace drawer
  const sideDrawer = document.getElementById('sideDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const toggleDrawerBtn = document.getElementById('toggleDrawerBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const sidePullHandle = document.getElementById('sidePullHandle');
  const drawerHomeBtn = document.getElementById('drawerHomeBtn');
  const drawerPrBtn = document.getElementById('drawerPrBtn');
  const drawerDashBtn = document.getElementById('drawerDashBtn');
  const drawerStaleBtn = document.getElementById('drawerStaleBtn');
  const drawerChatBtn = document.getElementById('drawerChatBtn');
  const drawerVoiceBtn = document.getElementById('drawerVoiceBtn');
  const drawerReportsBtn = document.getElementById('drawerReportsBtn');
  const drawerPrCount = document.getElementById('drawerPrCount');
  const drawerStaleCount = document.getElementById('drawerStaleCount');

  // Overdue SLA table
  const staleTableBody = document.getElementById('staleTableBody');
  const staleEmptyState = document.getElementById('staleEmptyState');
  const staleCountBadge = document.getElementById('staleCountBadge');
  let staleDaysThreshold = 5;

  const filterBtns = document.querySelectorAll('.filter-btn');

  // Leaderboard & stats
  const timeframeBtns = document.querySelectorAll('.timeframe-btn');
  const dashTimeframeBadge = document.getElementById('dashTimeframeBadge');
  const dashTotalPrs = document.getElementById('dashTotalPrs');
  const dashTotalEngineers = document.getElementById('dashTotalEngineers');
  const dashTopContributor = document.getElementById('dashTopContributor');
  const dashTopScore = document.getElementById('dashTopScore');
  const leaderboardTableBody = document.getElementById('leaderboardTableBody');
  const dashEmptyState = document.getElementById('dashEmptyState');

  // Chat
  const chatSessionsList = document.getElementById('chatSessionsList');
  const btnNewChat = document.getElementById('btnNewChat');
  const activeChatTitle = document.getElementById('activeChatTitle');
  const chatMessagesContainer = document.getElementById('chatMessagesContainer');
  const chatTypingIndicator = document.getElementById('chatTypingIndicator');
  const chatInputForm = document.getElementById('chatInputForm');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');

  let allPRs = [];
  let currentFilter = 'all';
  let currentDays = 30;
  let activeSessionId = null;
  let chatSessions = [];
  let currentActiveView = 'home';

  const API_BASE = (window.location.protocol.startsWith('http') && window.location.port === '8000')
    ? window.location.origin
    : 'http://localhost:8000';

  // Active view metadata for the topbar indicator
  const viewConfigs = {
    home: {
      label: 'Home',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
      showCounter: false
    },
    prs: {
      label: 'PR Requests',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>`,
      showCounter: true
    },
    dashboard: {
      label: 'Dashboard',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
      showCounter: false
    },
    stale: {
      label: 'Overdue',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
      showCounter: true
    },
    chat: {
      label: 'Chatbot',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
      showCounter: false
    },
    voice: {
      label: 'Voice Agent',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
      showCounter: false
    },
    reports: {
      label: 'Daily Reports',
      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
      showCounter: false
    }
  };

  function updateActiveViewIndicator() {
    const cfg = viewConfigs[currentActiveView] || viewConfigs.home;
    if (activeViewLabel) activeViewLabel.textContent = cfg.label;
    if (activeViewIcon) activeViewIcon.innerHTML = cfg.icon;
    if (activeViewCounter) {
      if (currentActiveView === 'prs') {
        activeViewCounter.style.display = 'inline-block';
        activeViewCounter.textContent = allPRs.length || '0';
      } else if (currentActiveView === 'stale') {
        const staleCount = (allPRs || []).filter(
          (pr) => pr.is_overdue || ((pr.state || '').toLowerCase() === 'open' && daysSince(pr.created_at) >= staleDaysThreshold)
        ).length;
        activeViewCounter.style.display = 'inline-block';
        activeViewCounter.textContent = staleCount;
      } else {
        activeViewCounter.style.display = 'none';
      }
    }
  }

  function switchView(viewName) {
    currentActiveView = viewName;

    // Disconnect voice call when navigating away from voice view
    if (viewName !== 'voice' && typeof stopVoiceSession === 'function' && isVoiceActive) {
      stopVoiceSession();
    }

    homeView?.classList.remove('active');
    prsView?.classList.remove('active');
    dashboardView?.classList.remove('active');
    staleView?.classList.remove('active');
    chatView?.classList.remove('active');
    reportsView?.classList.remove('active');
    voiceView?.classList.remove('active');

    drawerHomeBtn?.classList.remove('active');
    drawerPrBtn?.classList.remove('active');
    drawerDashBtn?.classList.remove('active');
    drawerStaleBtn?.classList.remove('active');
    drawerChatBtn?.classList.remove('active');
    drawerVoiceBtn?.classList.remove('active');
    drawerReportsBtn?.classList.remove('active');

    if (viewName === 'prs') {
      prsView?.classList.add('active');
      drawerPrBtn?.classList.add('active');
      loadPullRequests();
    } else if (viewName === 'dashboard') {
      dashboardView?.classList.add('active');
      drawerDashBtn?.classList.add('active');
      loadDashboard(currentDays);
    } else if (viewName === 'stale') {
      staleView?.classList.add('active');
      drawerStaleBtn?.classList.add('active');
      loadPullRequests();
    } else if (viewName === 'chat') {
      chatView?.classList.add('active');
      drawerChatBtn?.classList.add('active');
      loadChatSessions();
    } else if (viewName === 'voice') {
      voiceView?.classList.add('active');
      drawerVoiceBtn?.classList.add('active');
    } else if (viewName === 'reports') {
      reportsView?.classList.add('active');
      drawerReportsBtn?.classList.add('active');
      loadReports();
    } else {
      homeView?.classList.add('active');
      drawerHomeBtn?.classList.add('active');
      loadHome();
    }

    updateActiveViewIndicator();
  }

  // Brand logo + center Home button both go Home (click or Enter/Space keys)
  const goHome = () => switchView('home');
  brandBtn?.addEventListener('click', goHome);
  brandBtn?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      goHome();
    }
  });
  homeNavBtn?.addEventListener('click', goHome);

  // Drawer buttons switch views directly
  drawerHomeBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('home');
  });

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

  drawerVoiceBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('voice');
  });

  drawerReportsBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('reports');
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

  filterBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      filterBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter || 'all';
      renderPRs(allPRs);
    });
  });

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

  function renderPRs(prs) {
    allPRs = prs ? [...prs] : [];
    const totalCount = allPRs.length;
    if (drawerPrCount) drawerPrCount.textContent = totalCount;
    if (currentActiveView === 'prs' && activeViewCounter) activeViewCounter.textContent = totalCount;

    const filtered = currentFilter === 'all'
      ? allPRs
      : allPRs.filter((pr) => (pr.state || '').toLowerCase() === currentFilter);

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

    renderStalePRs(allPRs);
  }

  function renderStalePRs(prs) {
    document.querySelectorAll('.stale-threshold-num').forEach(el => el.textContent = staleDaysThreshold);

    const stale = (prs || [])
      .filter((pr) => pr.is_overdue || ((pr.state || '').toLowerCase() === 'open' && daysSince(pr.created_at) >= staleDaysThreshold))
      .sort((a, b) => (b.overdue_days || daysSince(b.created_at)) - (a.overdue_days || daysSince(a.created_at)));

    if (staleCountBadge) staleCountBadge.textContent = `${stale.length} Overdue`;
    if (drawerStaleCount) drawerStaleCount.textContent = stale.length;
    if (currentActiveView === 'stale' && activeViewCounter) activeViewCounter.textContent = stale.length;

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

  timeframeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      timeframeBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentDays = parseInt(btn.dataset.days, 10) || 30;
      if (dashTimeframeBadge) dashTimeframeBadge.textContent = btn.textContent;
      loadDashboard(currentDays);
    });
  });

  function renderDashboard(data) {
    if (!data) return;

    if (dashTotalPrs) dashTotalPrs.textContent = data.total_prs || 0;
    if (dashTotalEngineers) dashTotalEngineers.textContent = data.total_engineers || 0;

    // Sync threshold configured on backend
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

  // ---------- Home: live SLA health + weekly activity chart ----------
  const slaChip = document.getElementById('slaChip');
  const slaValue = document.getElementById('slaValue');
  const slaBarFill = document.getElementById('slaBarFill');
  const slaFoot = document.getElementById('slaFoot');
  const homeChart = document.getElementById('homeChart');
  const homeChartEmpty = document.getElementById('homeChartEmpty');
  const homeChartFoot = document.getElementById('homeChartFoot');

  // Share of currently-open PRs still inside the SLA window.
  function renderSLA(prs) {
    if (!slaValue) return;
    const open = (prs || []).filter((p) => (p.state || '').toLowerCase() === 'open');
    const breached = open.filter((p) => p.is_overdue).length;
    const within = open.length - breached;
    const pct = open.length === 0 ? 100 : Math.round((within / open.length) * 100);

    slaValue.textContent = pct + '%';
    if (slaBarFill) {
      slaBarFill.style.width = pct + '%';
      slaBarFill.classList.toggle('warn', pct < 90 && pct >= 70);
      slaBarFill.classList.toggle('bad', pct < 70);
    }
    if (slaChip) {
      let label = 'All Clear';
      let cls = 'metric-chip positive';
      if (open.length > 0) {
        if (pct >= 90) { label = 'Healthy'; cls = 'metric-chip positive'; }
        else if (pct >= 70) { label = 'Watch'; cls = 'metric-chip neutral'; }
        else { label = 'At Risk'; cls = 'metric-chip danger'; }
      }
      slaChip.className = cls;
      slaChip.textContent = label;
    }
    if (slaFoot) {
      slaFoot.textContent = open.length === 0
        ? 'No open PRs right now — nothing past SLA.'
        : `${within} within SLA · ${breached} breached of ${open.length} open`;
    }
  }

  // Two SVG series over the last 7 local days: opened (created_at) + merged (state + updated_at).
  function renderWeeklyChart(prs) {
    if (!homeChart) return;
    const NS = 'http://www.w3.org/2000/svg';
    while (homeChart.firstChild) homeChart.removeChild(homeChart.firstChild);

    const days = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      days.push({ date: d, opened: 0, merged: 0 });
    }
    const sameDay = (iso, day) => {
      if (!iso) return false;
      const t = new Date(iso);
      return t.getFullYear() === day.getFullYear()
        && t.getMonth() === day.getMonth()
        && t.getDate() === day.getDate();
    };
    (prs || []).forEach((p) => {
      const cDay = days.find((d) => sameDay(p.created_at, d.date));
      if (cDay) cDay.opened += 1;
      if ((p.state || '').toLowerCase() === 'merged') {
        const mDay = days.find((d) => sameDay(p.updated_at || p.created_at, d.date));
        if (mDay) mDay.merged += 1;
      }
    });

    const totalOpened = days.reduce((s, d) => s + d.opened, 0);
    const totalMerged = days.reduce((s, d) => s + d.merged, 0);
    const hasData = totalOpened + totalMerged > 0;
    if (homeChartEmpty) homeChartEmpty.style.display = hasData ? 'none' : 'block';
    if (homeChartFoot) {
      homeChartFoot.textContent = hasData
        ? `${totalOpened} opened · ${totalMerged} merged in the last 7 days`
        : 'No PR activity in the last 7 days.';
    }
    if (!hasData) return;

    const W = 680, H = 280, PL = 36, PR = 16, PT = 16, PB = 34;
    const maxV = Math.max(1, ...days.map((d) => Math.max(d.opened, d.merged)));
    const step = maxV <= 7 ? 1 : Math.ceil(maxV / 7);
    const top = Math.ceil(maxV / step) * step;
    const x = (i) => PL + (i * (W - PL - PR)) / (days.length - 1);
    const y = (v) => PT + (1 - v / top) * (H - PT - PB);

    const el = (tag, attrs) => {
      const n = document.createElementNS(NS, tag);
      for (const k in attrs) n.setAttribute(k, attrs[k]);
      return n;
    };

    for (let v = 0; v <= top; v += step) {
      homeChart.appendChild(el('line', { x1: PL, x2: W - PR, y1: y(v), y2: y(v), class: 'chart-grid' }));
      const t = el('text', { x: PL - 8, y: y(v) + 4, class: 'chart-tick', 'text-anchor': 'end' });
      t.textContent = v;
      homeChart.appendChild(t);
    }

    const series = (key, cls) => {
      const pts = days.map((d, i) => `${x(i)},${y(d[key])}`).join(' ');
      homeChart.appendChild(el('polyline', {
        points: `${x(0)},${y(0)} ${pts} ${x(days.length - 1)},${y(0)}`,
        class: `chart-area ${cls}`
      }));
      homeChart.appendChild(el('polyline', { points: pts, class: `chart-line ${cls}` }));
      days.forEach((d, i) => {
        homeChart.appendChild(el('circle', { cx: x(i), cy: y(d[key]), r: 4, class: `chart-dot ${cls}` }));
      });
    };
    series('opened', 'opened');
    series('merged', 'merged');

    const fmt = new Intl.DateTimeFormat('en', { weekday: 'short' });
    days.forEach((d, i) => {
      const t = el('text', { x: x(i), y: H - 10, class: 'chart-tick', 'text-anchor': 'middle' });
      t.textContent = `${fmt.format(d.date)} ${d.date.getDate()}`;
      homeChart.appendChild(t);
    });
  }

  async function loadHome() {
    try {
      const res = await fetch(`${API_BASE}/api/prs?state=all`);
      if (!res.ok) throw new Error('Failed to load home data');
      const data = await res.json();
      if (data.stale_threshold_days) staleDaysThreshold = data.stale_threshold_days;
      renderSLA(data.prs);
      renderWeeklyChart(data.prs);
    } catch (err) {
      console.warn('Home fetch error:', err);
      if (slaFoot) slaFoot.textContent = 'Could not reach the backend — retrying…';
      if (homeChartFoot) homeChartFoot.textContent = 'Could not reach the backend — retrying…';
    }
  }

  // Initial load
  loadPullRequests();
  loadHome();

  // Background poll for incoming PR activity
  setInterval(() => {
    loadPullRequests();
    loadHome();
  }, 25000);

  // Chat
  async function loadChatSessions() {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions`);
      if (!res.ok) throw new Error('Failed to load chat sessions');
      const data = await res.json();
      chatSessions = data.sessions || [];
      renderSessionsList(chatSessions);

      if (chatSessions.length === 0) {
        await createNewChatSession();
      } else if (!activeSessionId || !chatSessions.some(s => s.id === activeSessionId)) {
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
              <p><strong>Hello! I am your CTO Copilot assistant.</strong></p>
              <p>You can ask me questions about:</p>
              <ul>
                <li>Team pull requests, summaries, and impact metrics</li>
                <li>Contributor velocities and rankings</li>
                <li>Delivery timelines and code activity</li>
                <li>General engineering leadership topics</li>
              </ul>
              <p style="margin-top: 8px; color: #64748b; font-size: 0.8rem;">Type your question below to begin!</p>
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
      const rawContent = isUser ? escapeHtml(m.content) : renderMarkdown(m.content);
      const formattedContent = isolateBidiRuns(rawContent);
      return `
        <div class="chat-bubble ${isUser ? 'user' : 'assistant'}">
          <div class="bubble-avatar">${avatar}</div>
          <div class="bubble-content" dir="auto">${formattedContent}</div>
        </div>
      `;
    }).join('');
  }

  async function sendChatMessage(text) {
    if (!text || !text.trim() || !activeSessionId) return;
    const cleanText = text.trim();

    appendMessageBubble('user', cleanText);
    scrollChatToBottom();

    if (chatInput) {
      chatInput.value = '';
      chatInput.style.height = 'auto';
    }

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
    const rawContent = isUser ? escapeHtml(content) : renderMarkdown(content);
    const formattedContent = isolateBidiRuns(rawContent);

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${isUser ? 'user' : 'assistant'}`;
    bubble.innerHTML = `
      <div class="bubble-avatar">${avatar}</div>
      <div class="bubble-content" dir="auto">${formattedContent}</div>
    `;
    chatMessagesContainer.appendChild(bubble);
  }

  function scrollChatToBottom() {
    if (chatMessagesContainer) {
      chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
  }

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

  // Daily CTO Reports (standalone view, auto-generated 08:00 Africa/Cairo)
  const reportsTableBody = document.getElementById('reportsTableBody');
  const reportsEmptyState = document.getElementById('reportsEmptyState');
  const refreshReportsBtn = document.getElementById('refreshReportsBtn');

  async function loadReports() {
    try {
      const res = await fetch(`${API_BASE}/api/reports`);
      if (!res.ok) throw new Error('Failed to load reports');
      const data = await res.json();
      renderReports(data.reports || []);
    } catch (err) {
      console.warn('Reports fetch error:', err);
    }
  }

  // "2026-10-11" + DB created_at (UTC) "2026-10-11T09:54:34" -> "2026-10-11 • 09:54 UTC"
  function formatReportDateTime(r) {
    const datePart = r.report_date || '';
    const created = r.created_at || '';
    const timePart = created.length >= 16 ? created.slice(11, 16) : '';
    return timePart ? `${datePart} • ${timePart} UTC` : datePart;
  }

  function renderReports(reports) {
    if (!reports || reports.length === 0) {
      if (reportsTableBody) reportsTableBody.innerHTML = '';
      if (reportsEmptyState) reportsEmptyState.style.display = 'flex';
      return;
    }
    if (reportsEmptyState) reportsEmptyState.style.display = 'none';
    if (reportsTableBody) {
      reportsTableBody.innerHTML = reports.map((r) => {
        const overdue = r.overdue_count ?? 0;
        return `
        <tr>
          <td><span class="table-pr-title" style="font-size: 0.88rem;">${escapeHtml(r.title)}</span></td>
          <td><span class="table-date-cell" style="white-space: nowrap;">${escapeHtml(formatReportDateTime(r))}</span></td>
          <td><strong>${r.prs_opened ?? 0}</strong></td>
          <td><strong>${r.prs_merged ?? 0}</strong></td>
          <td>${overdue > 0 ? `<span class="overdue-days-pill">⏳ ${overdue}</span>` : '<span class="table-date-cell">0</span>'}</td>
          <td>
            <div style="display: flex; gap: 8px;">
              <a href="${API_BASE}/api/reports/${r.id}/file?mode=preview" target="_blank" rel="noopener noreferrer" class="btn-refresh-table" style="text-decoration: none; padding: 6px 12px; font-size: 0.78rem;">👁 Preview</a>
              <a href="${API_BASE}/api/reports/${r.id}/file?mode=download" class="btn-refresh-table" style="text-decoration: none; padding: 6px 12px; font-size: 0.78rem;">⬇ Download</a>
            </div>
          </td>
        </tr>
      `;
      }).join('');
    }
  }

  refreshReportsBtn?.addEventListener('click', () => {
    refreshReportsBtn.classList.add('spinning');
    loadReports().finally(() => {
      refreshReportsBtn.classList.remove('spinning');
    });
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

    // Links: [text](url) — href stays raw LTR, text gets bidi isolation later
    html = html.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

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

  // Arabic/Hebrew (or any RTL script) detection for chat bubbles
  const RTL_RE = /[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]/;
  function hasRtl(text) { return RTL_RE.test(text || ''); }

  // Wrap Latin tokens in <bdi> to preserve punctuation and order inside RTL blocks
  function isolateBidiRuns(html) {
    if (!html || !hasRtl(html)) return html;
    const parts = html.split(/(<[^>]+>)/g);
    const entityRe = /(&[a-zA-Z0-9#]+;)/g;
    const runRe = /https?:\/\/[^\s<]+|#?[A-Za-z0-9_][A-Za-z0-9_.:/#+-]*/g;
    return parts.map((seg) => {
      if (!seg || seg.startsWith('<')) return seg;
      return seg.split(entityRe).map((chunk) => {
        if (!chunk || chunk.startsWith('&')) return chunk;
        return chunk.replace(runRe, '<bdi>$&</bdi>');
      }).join('');
    }).join('');
  }

  // Voice agent
  const voiceOrb = document.getElementById('voiceOrb');
  const voiceStatusPill = document.getElementById('voiceStatusPill');
  const voiceStatusText = document.getElementById('voiceStatusText');
  const voiceDbQueryBadge = document.getElementById('voiceDbQueryBadge');
  const voiceDbQueryText = document.getElementById('voiceDbQueryText');
  const btnVoiceToggle = document.getElementById('btnVoiceToggle');
  const voiceBtnLabel = document.getElementById('voiceBtnLabel');
  const btnVoiceMute = document.getElementById('btnVoiceMute');
  const voiceTranscriptBox = document.getElementById('voiceTranscriptBox');
  const voiceInterruptionNotice = document.getElementById('voiceInterruptionNotice');

  let voiceWs = null;
  let isVoiceActive = false;
  let isVoiceMuted = false;
  let recordAudioCtx = null;
  let micMediaStream = null;
  let micSourceNode = null;
  let micProcessorNode = null;
  let playbackAudioCtx = null;
  let nextAudioPlaybackTime = 0;
  let activeAudioPlaybackNodes = [];

  function setVoiceVisualState(state) {
    if (voiceOrb) {
      voiceOrb.className = `voice-orb ${state}`;
    }
    if (voiceStatusPill) {
      voiceStatusPill.className = `voice-status-pill ${state}`;
    }
    if (voiceStatusText) {
      const labels = {
        idle: 'Ready to Connect',
        connecting: 'Connecting to Deepgram...',
        listening: 'Listening to CTO...',
        thinking: 'Querying MySQL / Thinking...',
        speaking: 'CTO Copilot Speaking...',
      };
      voiceStatusText.textContent = labels[state] || state;
    }
  }

  function appendVoiceTranscript(role, text) {
    if (!voiceTranscriptBox || !text) return;

    // Remove placeholder message if present
    const placeholder = voiceTranscriptBox.querySelector('div[style*="italic"]');
    if (placeholder) {
      placeholder.remove();
    }

    const row = document.createElement('div');
    row.className = 'voice-msg-row';

    const authorSpan = document.createElement('span');
    authorSpan.className = `voice-msg-author ${role === 'user' ? 'user' : ''}`;
    authorSpan.textContent = role === 'user' ? 'You (CTO):' : 'Copilot:';

    const textSpan = document.createElement('span');
    textSpan.className = 'voice-msg-text';
    textSpan.dir = 'auto';
    textSpan.textContent = text;

    row.appendChild(authorSpan);
    row.appendChild(textSpan);
    voiceTranscriptBox.appendChild(row);
    voiceTranscriptBox.scrollTop = voiceTranscriptBox.scrollHeight;
  }

  function downsampleBuffer(buffer, inSampleRate, outSampleRate) {
    if (inSampleRate === outSampleRate) return buffer;
    const ratio = inSampleRate / outSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0, count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  async function startVoiceSession() {
    try {
      setVoiceVisualState('connecting');

      // Request microphone stream
      micMediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Prepare Playback AudioContext (Deepgram delivers linear16 at 24000Hz)
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      playbackAudioCtx = new AudioCtxClass({ sampleRate: 24000 });
      if (playbackAudioCtx.state === 'suspended') {
        await playbackAudioCtx.resume();
      }
      nextAudioPlaybackTime = playbackAudioCtx.currentTime;
      activeAudioPlaybackNodes = [];

      // Open WebSocket to our FastAPI endpoint
      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProto}//${window.location.host}/api/voice/ws`;
      voiceWs = new WebSocket(wsUrl);
      voiceWs.binaryType = 'arraybuffer';

      voiceWs.onopen = () => {
        isVoiceActive = true;
        if (btnVoiceToggle) {
          btnVoiceToggle.classList.add('active');
          if (voiceBtnLabel) voiceBtnLabel.textContent = 'End Voice Call';
        }
        if (btnVoiceMute) {
          btnVoiceMute.disabled = false;
        }
        setVoiceVisualState('listening');
      };

      voiceWs.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary audio received from Deepgram Voice Agent (linear16, 24kHz)
          if (!playbackAudioCtx) return;
          const rawInt16 = new Int16Array(event.data);
          if (rawInt16.length === 0) return;

          const float32 = new Float32Array(rawInt16.length);
          for (let i = 0; i < rawInt16.length; i++) {
            float32[i] = rawInt16[i] / 32768.0;
          }

          const audioBuf = playbackAudioCtx.createBuffer(1, float32.length, 24000);
          audioBuf.getChannelData(0).set(float32);

          const sourceNode = playbackAudioCtx.createBufferSource();
          sourceNode.buffer = audioBuf;
          sourceNode.connect(playbackAudioCtx.destination);

          const now = playbackAudioCtx.currentTime;
          const startTime = Math.max(now, nextAudioPlaybackTime);
          sourceNode.start(startTime);
          nextAudioPlaybackTime = startTime + audioBuf.duration;

          activeAudioPlaybackNodes.push(sourceNode);
          setVoiceVisualState('speaking');

          sourceNode.onended = () => {
            const idx = activeAudioPlaybackNodes.indexOf(sourceNode);
            if (idx > -1) activeAudioPlaybackNodes.splice(idx, 1);
            if (activeAudioPlaybackNodes.length === 0) {
              setVoiceVisualState('listening');
            }
          };
        } else if (typeof event.data === 'string') {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'AgentQueryingDatabase') {
              if (voiceDbQueryBadge && voiceDbQueryText) {
                voiceDbQueryText.textContent = msg.query || 'Executing SELECT...';
                voiceDbQueryBadge.style.display = 'flex';
              }
              setVoiceVisualState('thinking');
            } else if (msg.type === 'UserStartedSpeaking') {
              // Barge-in: cut active playback immediately
              activeAudioPlaybackNodes.forEach((node) => {
                try { node.stop(); } catch (e) {}
              });
              activeAudioPlaybackNodes = [];
              nextAudioPlaybackTime = playbackAudioCtx ? playbackAudioCtx.currentTime : 0;

              if (voiceInterruptionNotice) {
                voiceInterruptionNotice.style.display = 'inline';
                setTimeout(() => {
                  if (voiceInterruptionNotice) voiceInterruptionNotice.style.display = 'none';
                }, 1600);
              }
              setVoiceVisualState('listening');
            } else if (msg.type === 'ConversationText') {
              if (msg.role && msg.content) {
                appendVoiceTranscript(msg.role, msg.content);
                if (msg.role === 'assistant' && voiceDbQueryBadge) {
                  setTimeout(() => {
                    if (voiceDbQueryBadge) voiceDbQueryBadge.style.display = 'none';
                  }, 4000);
                }
              }
            } else if (msg.type === 'AgentThinking') {
              setVoiceVisualState('thinking');
            } else if (msg.type === 'AgentStartedSpeaking') {
              setVoiceVisualState('speaking');
            } else if (msg.type === 'Error' || msg.type === 'error') {
              appendVoiceTranscript('system', `Error: ${msg.description || msg.message}`);
              stopVoiceSession();
            }
          } catch (e) {
            console.warn('Voice message parsing error:', e);
          }
        }
      };

      voiceWs.onerror = (err) => {
        console.error('Voice WebSocket error:', err);
        stopVoiceSession();
      };

      voiceWs.onclose = () => {
        stopVoiceSession();
      };

      recordAudioCtx = new AudioCtxClass();
      micSourceNode = recordAudioCtx.createMediaStreamSource(micMediaStream);
      micProcessorNode = recordAudioCtx.createScriptProcessor(2048, 1, 1);

      micProcessorNode.onaudioprocess = (e) => {
        if (!voiceWs || voiceWs.readyState !== WebSocket.OPEN || isVoiceMuted) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const resampled = downsampleBuffer(inputData, recordAudioCtx.sampleRate, 16000);
        const pcm16 = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
          let s = Math.max(-1, Math.min(1, resampled[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        voiceWs.send(pcm16.buffer);
      };

      micSourceNode.connect(micProcessorNode);
      micProcessorNode.connect(recordAudioCtx.destination);
    } catch (err) {
      console.error('Could not start voice session:', err);
      alert('Microphone access failed or Voice Agent error: ' + (err.message || err));
      stopVoiceSession();
    }
  }

  function stopVoiceSession() {
    isVoiceActive = false;
    isVoiceMuted = false;

    if (btnVoiceToggle) {
      btnVoiceToggle.classList.remove('active');
      if (voiceBtnLabel) voiceBtnLabel.textContent = 'Start Voice Call';
    }
    if (btnVoiceMute) {
      btnVoiceMute.disabled = true;
      btnVoiceMute.classList.remove('muted');
    }
    if (voiceDbQueryBadge) {
      voiceDbQueryBadge.style.display = 'none';
    }

    setVoiceVisualState('idle');

    if (activeAudioPlaybackNodes) {
      activeAudioPlaybackNodes.forEach((node) => {
        try { node.stop(); } catch (e) {}
      });
      activeAudioPlaybackNodes = [];
    }

    if (micProcessorNode) {
      try { micProcessorNode.disconnect(); } catch (e) {}
      micProcessorNode = null;
    }
    if (micSourceNode) {
      try { micSourceNode.disconnect(); } catch (e) {}
      micSourceNode = null;
    }
    if (recordAudioCtx) {
      try { recordAudioCtx.close(); } catch (e) {}
      recordAudioCtx = null;
    }
    if (playbackAudioCtx) {
      try { playbackAudioCtx.close(); } catch (e) {}
      playbackAudioCtx = null;
    }
    if (micMediaStream) {
      micMediaStream.getTracks().forEach((track) => track.stop());
      micMediaStream = null;
    }
    if (voiceWs) {
      try {
        if (voiceWs.readyState === WebSocket.OPEN) {
          voiceWs.close();
        }
      } catch (e) {}
      voiceWs = null;
    }
  }

  btnVoiceToggle?.addEventListener('click', () => {
    if (isVoiceActive) {
      stopVoiceSession();
    } else {
      startVoiceSession();
    }
  });

  btnVoiceMute?.addEventListener('click', () => {
    if (!isVoiceActive) return;
    isVoiceMuted = !isVoiceMuted;
    btnVoiceMute.classList.toggle('muted', isVoiceMuted);
    btnVoiceMute.title = isVoiceMuted ? 'Unmute microphone' : 'Mute microphone';
  });
});

