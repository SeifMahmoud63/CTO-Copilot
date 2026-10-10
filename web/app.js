// CTO Copilot UI, Table Directory & PR Controller
document.addEventListener('DOMContentLoaded', () => {
  // Navigation & View elements
  const homeView = document.getElementById('homeView');
  const prsView = document.getElementById('prsView');
  const dashboardView = document.getElementById('dashboardView');
  const navHomeBtn = document.getElementById('navHomeBtn');
  const navPrsBtn = document.getElementById('navPrsBtn');
  const navDashBtn = document.getElementById('navDashBtn');
  const navPrCount = document.getElementById('navPrCount');
  const refreshTableBtn = document.getElementById('refreshTableBtn');
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
  const drawerPrCount = document.getElementById('drawerPrCount');

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

  // State
  let allPRs = [];
  let currentFilter = 'all';
  let currentDays = 30;

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
    navHomeBtn?.classList.remove('active');
    navPrsBtn?.classList.remove('active');
    navDashBtn?.classList.remove('active');

    if (viewName === 'prs') {
      prsView?.classList.add('active');
      navPrsBtn?.classList.add('active');
      loadPullRequests();
    } else if (viewName === 'dashboard') {
      dashboardView?.classList.add('active');
      navDashBtn?.classList.add('active');
      loadDashboard(currentDays);
    } else {
      homeView?.classList.add('active');
      navHomeBtn?.classList.add('active');
    }
  }

  navHomeBtn?.addEventListener('click', () => switchView('home'));
  navPrsBtn?.addEventListener('click', () => switchView('prs'));
  navDashBtn?.addEventListener('click', () => switchView('dashboard'));

  // Drawer buttons switch views directly
  drawerPrBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('prs');
  });

  drawerDashBtn?.addEventListener('click', () => {
    closeDrawer();
    switchView('dashboard');
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

  // Helper to render JEV Impact Badge
  function renderImpactBadge(score) {
    if (score !== null && score !== undefined) {
      let levelClass = 'low';
      if (score >= 8.0) levelClass = 'high';
      else if (score >= 6.0) levelClass = 'medium';
      else if (score >= 4.0) levelClass = 'moderate';

      return `<span class="impact-badge ${levelClass}" title="Impact evaluated by JEV Decision Intelligence: ${score}/10">⚡ Impact: ${score}/10</span>`;
    }
    return `<span class="impact-badge low" style="opacity: 0.7;" title="Impact score pending JEV evaluation">⚡ Impact: —</span>`;
  }

  // Render Table View & Drawer View
  function renderPRs(prs) {
    allPRs = prs ? [...prs] : [];
    const totalCount = allPRs.length;
    if (navPrCount) navPrCount.textContent = totalCount;
    if (drawerPrCount) drawerPrCount.textContent = totalCount;

    // Apply status filter: open = متعلّقة, merged = مندمجة, closed = مقفولة
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
      return;
    }

    if (tableEmptyState) tableEmptyState.style.display = 'none';

    // Populate Table View
    if (prsTableBody) {
      prsTableBody.innerHTML = filtered.map((pr) => `
        <tr>
          <td>
            <a href="${pr.html_url}" target="_blank" rel="noopener noreferrer" class="table-pr-title">
              #${pr.number} ${escapeHtml(pr.title)}
            </a>
            <div class="table-pr-branches">
              <span class="branch-tag">${escapeHtml(pr.base_branch)}</span>
              <span>←</span>
              <span class="branch-tag">${escapeHtml(pr.head_branch)}</span>
            </div>
          </td>
          <td>
            <div class="table-author-cell">
              ${pr.author_avatar ? `<img src="${pr.author_avatar}" class="table-author-avatar" alt="${pr.author}"/>` : `<span class="table-author-avatar">${pr.author.slice(0, 2).toUpperCase()}</span>`}
              <span>${escapeHtml(pr.author)}</span>
            </div>
          </td>
          <td>
            <div class="table-summary-box">
              ${pr.summary ? escapeHtml(pr.summary) : '<em>Generating executive summary automatically...</em>'}
            </div>
          </td>
          <td>
            <div style="display: flex; flex-direction: column; gap: 6px; align-items: flex-start;">
              <span class="pr-state-badge ${pr.state}">${pr.state}</span>
              ${renderImpactBadge(pr.impact_score)}
            </div>
          </td>
          <td>
            <span class="table-date-cell">${formatTimestamp(pr.created_at)}</span>
          </td>
        </tr>
      `).join('');
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

  // Load PRs from FastAPI backend
  async function loadPullRequests() {
    try {
      const res = await fetch(`${API_BASE}/api/prs`);
      if (!res.ok) throw new Error('Failed to load PRs');
      const data = await res.json();
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
