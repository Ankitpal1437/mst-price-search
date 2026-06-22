// common.js — shared helpers across all pages

function toast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.remove('show');
  void t.offsetWidth;
  t.classList.add('show');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}

function fmtMoney(n) {
  const num = parseFloat(n);
  if (isNaN(num) || n === '' || n === null || n === undefined) return '—';
  return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtMoneyShort(n) {
  const num = parseFloat(n);
  if (isNaN(num)) return '—';
  return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function initials(name) {
  if (!name) return '?';
  return name.trim().split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

function todayStr() {
  return new Date().toISOString().split('T')[0];
}

async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

async function apiPost(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

async function apiPut(url, data) {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}
