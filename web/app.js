// CTO Copilot UI, Table Directory & PR Controller
document.addEventListener('DOMContentLoaded', () => {
  const homeView = document.getElementById('homeView');
  const prsView = document.getElementById('prsView');
  const navHomeBtn = document.getElementById('navHomeBtn');
  const navPrsBtn = document.getElementById('navPrsBtn');
  const navPrCount = document.getElementById('navPrCount');
  const refreshTableBtn = document.getElementById('refreshTableBtn');
  const prsTableBody = document.getElementById('prsTableBody');
  const tableEmptyState = document.getElementById('tableEmptyState');

  // Drawer elements
  const sideDrawer = document.getElementById('sideDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const toggleDrawerBtn = document.getElementById('toggleDrawerBtn');
  const sidePullHandle = document.getElementById('sidePullHandle');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const prListContainer = document.getElementById('prListContainer');
  const emptyPrState = document.getElementById('emptyPrState');
  const drawerPrTab = document.querySelector('.drawer-tab');
  const drawerCountPill = document.querySelector('.count-pill');

  // Automatically connect to FastAPI backend at port 8000
  const API_BASE = (window.location.protocol.startsWith('http') && window.location.port === '8000')
    ? window.location.origin
    : 'http://localhost:8000';

  // Navigation switching
  function switchView(viewName) {
    if (viewName === 'prs') {
      homeView.classList.remove('active');
      prsView.classList.add('active');
      navHomeBtn.classList.remove('active');
      navPrsBtn.classList.add('active');
      loadPullRequests();
    } else {
      prsView.classList.remove('active');
      homeView.classList.add('active');
      navPrsBtn.classList.remove('active');
      navHomeBtn.classList.add('active');
    }
  }

  navHomeBtn?.addEventListener('click', () => switchView('home'));
  navPrsBtn?.addEventListener('click', () => switchView('prs'));

  // Clicking PR Requests inside drawer switches directly to the table view
  drawerPrTab?.addEventListener('click', () => {
    closeDrawer();
    switchView('prs');
  });

  // Drawer open / close
  const openDrawer = () => {
    sideDrawer.classList.add('open');
    drawerBackdrop.classList.add('active');
    loadPullRequests();
  };

  const closeDrawer = () => {
    sideDrawer.classList.remove('open');
    drawerBackdrop.classList.remove('active');
  };

  toggleDrawerBtn?.addEventListener('click', () => {
    if (sideDrawer.classList.contains('open')) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  sidePullHandle?.addEventListener('click', openDrawer);
  closeDrawerBtn?.addEventListener('click', closeDrawer);
  drawerBackdrop?.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sideDrawer.classList.contains('open')) {
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

  // Render Table View & Drawer View
  function renderPRs(prs) {
    const totalCount = prs ? prs.length : 0;
    document.querySelectorAll('.nav-counter, .count-pill, #navPrCount, #drawerPrCount').forEach(el => {
      el.textContent = totalCount;
    });


    // Handle Empty State
    if (!prs || prs.length === 0) {
      if (prsTableBody) prsTableBody.innerHTML = '';
      if (tableEmptyState) tableEmptyState.style.display = 'flex';
      if (prListContainer) prListContainer.innerHTML = '';
      if (emptyPrState) emptyPrState.style.display = 'flex';
      return;
    }

    if (tableEmptyState) tableEmptyState.style.display = 'none';
    if (emptyPrState) emptyPrState.style.display = 'none';

    // Populate Table View
    if (prsTableBody) {
      prsTableBody.innerHTML = prs.map((pr) => `
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
            <span class="pr-state-badge ${pr.state}">${pr.state}</span>
          </td>
          <td>
            <span class="table-date-cell">${formatTimestamp(pr.created_at)}</span>
          </td>
        </tr>
      `).join('');
    }

    // Populate Side Drawer
    if (prListContainer) {
      prListContainer.innerHTML = prs.map((pr) => `
        <div class="pr-card" data-pr-number="${pr.number}">
          <div class="pr-header">
            <div class="pr-title-group">
              <a href="${pr.html_url}" target="_blank" rel="noopener noreferrer" class="pr-number-title">
                #${pr.number} ${escapeHtml(pr.title)}
              </a>
              <div class="pr-meta-info">
                <span class="pr-author-wrap">
                  ${pr.author_avatar ? `<img src="${pr.author_avatar}" class="pr-author-avatar" alt="${pr.author}"/>` : `<span class="pr-author-avatar">${pr.author.slice(0, 2).toUpperCase()}</span>`}
                  ${escapeHtml(pr.author)}
                </span>
                <span>•</span>
                <span>${formatTimestamp(pr.created_at)}</span>
              </div>
            </div>
            <span class="pr-state-badge ${pr.state}">${pr.state}</span>
          </div>

          <div class="pr-summary-box">
            <div class="summary-header">
              <span class="summary-title-tag">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                Executive Summary
              </span>
            </div>
            <div class="summary-body">${pr.summary ? escapeHtml(pr.summary) : '<em>Generating summary automatically...</em>'}</div>
          </div>
        </div>
      `).join('');
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
