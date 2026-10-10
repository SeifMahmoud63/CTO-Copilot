// CTO Copilot UI & PR Controller
document.addEventListener('DOMContentLoaded', () => {
  const sideDrawer = document.getElementById('sideDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const toggleDrawerBtn = document.getElementById('toggleDrawerBtn');
  const sidePullHandle = document.getElementById('sidePullHandle');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const prListContainer = document.getElementById('prListContainer');
  const emptyPrState = document.getElementById('emptyPrState');

  // Automatically connect to FastAPI backend at port 8000
  const API_BASE = (window.location.protocol.startsWith('http') && window.location.port === '8000')
    ? window.location.origin
    : 'http://localhost:8000';

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

  // Format timestamp nicely
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

  // Render PR list with automatic summaries
  function renderPRs(prs) {
    if (!prs || prs.length === 0) {
      prListContainer.innerHTML = '';
      if (emptyPrState) emptyPrState.style.display = 'flex';
      return;
    }

    if (emptyPrState) emptyPrState.style.display = 'none';

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
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
              </svg>
              Executive Summary
            </span>
          </div>
          <div class="summary-body">${pr.summary ? escapeHtml(pr.summary) : '<em>Generating summary automatically...</em>'}</div>
        </div>
      </div>
    `).join('');
  }

  // Load PRs automatically from API
  async function loadPullRequests() {
    try {
      const res = await fetch(`${API_BASE}/api/prs`);
      if (!res.ok) throw new Error('Failed to load PRs');
      const data = await res.json();
      renderPRs(data.prs);
    } catch {
      // Backend offline or unreachable
    }
  }

  // Auto-refresh PRs every 20 seconds while page is active
  setInterval(() => {
    if (sideDrawer.classList.contains('open')) {
      loadPullRequests();
    }
  }, 20000);

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
