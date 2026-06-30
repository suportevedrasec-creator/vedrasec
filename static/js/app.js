/* ─── Vedra SEC — Frontend JS ─────────────────────────────────────────── */

// ─── Toast ───────────────────────────────────────────────────────────────────

function toast(msg, type = 'info', duration = 4000) {
  const icons = {
    success: `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>`,
    error:   `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>`,
    warning: `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`,
    info:    `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>`,
  };
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.style.color = type === 'success' ? 'var(--success)' : type === 'error' ? 'var(--danger)' : type === 'warning' ? 'var(--warning)' : 'var(--navy)';
  el.innerHTML = icons[type] || icons.info;
  const txt = document.createElement('span');
  txt.style.color = 'var(--text-dark)';
  txt.textContent = msg;
  el.appendChild(txt);
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(20px)'; el.style.transition = '.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

// ─── Modal ───────────────────────────────────────────────────────────────────

function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('active'); document.body.style.overflow = 'hidden'; }
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove('active'); document.body.style.overflow = ''; }
}

document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) closeModal(e.target.id);
  if (e.target.closest('[data-close-modal]')) {
    const id = e.target.closest('[data-close-modal]').dataset.closeModal;
    closeModal(id);
  }
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => {
      m.classList.remove('active');
      document.body.style.overflow = '';
    });
  }
});

// ─── API Helpers ──────────────────────────────────────────────────────────────

async function apiGet(url) {
  const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function apiPost(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await r.json();
  if (!r.ok) throw new Error(json.mensagem || json.error || `HTTP ${r.status}`);
  return json;
}

async function apiPut(url, data) {
  const r = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await r.json();
  if (!r.ok) throw new Error(json.mensagem || json.error || `HTTP ${r.status}`);
  return json;
}

async function apiDelete(url) {
  const r = await fetch(url, { method: 'DELETE', headers: { 'Accept': 'application/json' } });
  const json = await r.json();
  if (!r.ok) throw new Error(json.mensagem || json.error || `HTTP ${r.status}`);
  return json;
}

// ─── Formatação ───────────────────────────────────────────────────────────────

function fmtMoeda(v, defaultText = '—') {
  if (v == null || v === '') return defaultText;
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
}

function fmtData(s, defaultText = '—') {
  if (!s) return defaultText;
  const [y, m, d] = s.split('-');
  return `${d}/${m}/${y}`;
}

function fmtPct(v, defaultText = '—') {
  if (v == null) return defaultText;
  return `${Number(v).toFixed(2).replace('.', ',')}%`;
}

function fmtNum(v, defaultText = '—') {
  if (v == null) return defaultText;
  return new Intl.NumberFormat('pt-BR').format(v);
}

function emptyRow(cols, msg = 'Nenhum registro encontrado.') {
  return `<tr class="loading-row"><td colspan="${cols}" style="text-align:center;padding:40px;color:var(--text-muted);font-style:italic;">${msg}</td></tr>`;
}

// ─── Badge de Status ──────────────────────────────────────────────────────────

function statusBadge(status) {
  if (!status) return '<span class="badge badge-muted">—</span>';
  const s = status.toLowerCase();
  let cls = 'badge-muted';
  if (s.includes('quitad') || s.includes('recebid') || s.includes('encerrad')) cls = 'badge-success';
  else if (s.includes('andamento') || s.includes('negociando') || s.includes('aguardando')) cls = 'badge-warning';
  else if (s.includes('cancelad') || s.includes('frustrad') || s.includes('inadimplente')) cls = 'badge-danger';
  else if (s.includes('citad') || s.includes('intimad') || s.includes('bloqueio')) cls = 'badge-info';
  else if (s.includes('proposta') || s.includes('proposto')) cls = 'badge-navy';
  return `<span class="badge ${cls}">${status}</span>`;
}

// ─── Paginação ────────────────────────────────────────────────────────────────

function renderPaginacao(container, pagina, totalPaginas, callback) {
  if (!container) return;
  container.innerHTML = '';
  if (totalPaginas <= 1) return;

  const prev = document.createElement('button');
  prev.className = 'page-btn';
  prev.innerHTML = '‹';
  prev.disabled = pagina === 1;
  prev.onclick = () => callback(pagina - 1);
  container.appendChild(prev);

  const start = Math.max(1, pagina - 2);
  const end   = Math.min(totalPaginas, start + 4);

  for (let i = start; i <= end; i++) {
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (i === pagina ? ' active' : '');
    btn.textContent = i;
    btn.onclick = () => callback(i);
    container.appendChild(btn);
  }

  const next = document.createElement('button');
  next.className = 'page-btn';
  next.innerHTML = '›';
  next.disabled = pagina === totalPaginas;
  next.onclick = () => callback(pagina + 1);
  container.appendChild(next);

  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = `Página ${pagina} de ${totalPaginas}`;
  container.appendChild(info);
}

// ─── Formulário → Objeto ──────────────────────────────────────────────────────

function formToObj(form) {
  const obj = {};
  new FormData(form).forEach((v, k) => {
    obj[k] = v === '' ? null : v;
  });
  // checkboxes não marcados
  form.querySelectorAll('input[type=checkbox]').forEach(cb => {
    obj[cb.name] = cb.checked;
  });
  return obj;
}

// ─── Confirmação ──────────────────────────────────────────────────────────────

function confirmar(msg) {
  return window.confirm(msg);
}

// ─── Ativa item no nav ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && (path === href || (href !== '/' && path.startsWith(href)))) {
      item.classList.add('active');
    }
  });
});
