// UI Drawer controller
document.addEventListener('DOMContentLoaded', () => {
  const sideDrawer = document.getElementById('sideDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const toggleDrawerBtn = document.getElementById('toggleDrawerBtn');
  const sidePullHandle = document.getElementById('sidePullHandle');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');

  const openDrawer = () => {
    sideDrawer.classList.add('open');
    drawerBackdrop.classList.add('active');
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
});
