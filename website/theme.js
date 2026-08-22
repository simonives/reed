const STORAGE_KEY = 'reed-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem(STORAGE_KEY, next);
  applyTheme(next);
}

const saved = localStorage.getItem(STORAGE_KEY);
if (saved) applyTheme(saved);

document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
