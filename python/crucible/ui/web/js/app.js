/* app.js — Navigation, sidebar, window controls, toast, theme */
'use strict';

document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

// --- Navigation ---
window._activeView = 'library';
function applySidebarState(collapsed) {
    var sidebar = document.getElementById('main-sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed', !!collapsed);
}

function persistSidebarState(collapsed) {
    if (!bridge) return;
    call('getSettings').then(function(settings) {
        if (!settings || !settings.restore_geometry) return;
        call('setSetting', 'sidebar_collapsed', !!collapsed);
    });
}

function switchView(viewId) {
    var modal = document.getElementById('hero-modal');
    if (modal && modal.classList.contains('open') && typeof closeGameModal === 'function') {
        closeGameModal(viewId);
    }

    document.querySelectorAll('.nav-item').forEach(function(el) { el.classList.remove('active'); });
    document.querySelector('.nav-item[data-view="' + viewId + '"]').classList.add('active');
    document.querySelectorAll('.view-content').forEach(function(el) { el.classList.remove('active'); });
    document.getElementById('view-' + viewId).classList.add('active');
    window._activeView = viewId;
    if (bridge && bridge.setActiveView) bridge.setActiveView(viewId);
    if (viewId === 'settings' && typeof refreshSettings === 'function') refreshSettings();
}

document.querySelectorAll('.nav-item[data-view]').forEach(function(el) {
    el.addEventListener('click', function() { switchView(el.dataset.view); });
});

// --- Sidebar collapse ---
document.getElementById('sidebar-toggle').addEventListener('click', function() {
    var sidebar = document.getElementById('main-sidebar');
    var collapsed = !sidebar.classList.contains('collapsed');
    applySidebarState(collapsed);
    persistSidebarState(collapsed);
});

// --- Window controls ---
document.getElementById('wc-min').addEventListener('click', function() {
    if (bridge) bridge.minimizeWindow();
});
document.getElementById('wc-max').addEventListener('click', function() {
    if (bridge) bridge.maximizeWindow();
});
document.getElementById('wc-close').addEventListener('click', function() {
    if (bridge) bridge.closeWindow();
});

// --- Drag region ---
document.getElementById('drag-region').addEventListener('mousedown', function() {
    if (bridge) bridge.startDrag();
});

// --- Toast ---
function showToast(message, level) {
    var container = document.getElementById('toast-container');
    var toast = document.createElement('div');
    toast.className = 'toast';
    var iconColor = level === 'error' ? 'var(--danger)' : level === 'warning' ? 'var(--warning)' : 'var(--accent)';
    var icon = document.createElement('div');
    icon.className = 'toast-icon';
    icon.style.color = iconColor;
    icon.innerHTML =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    var body = document.createElement('div');
    body.textContent = String(message || '');
    toast.appendChild(icon);
    toast.appendChild(body);
    container.appendChild(toast);
    setTimeout(function() { toast.classList.add('show'); }, 10);
    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
}

// --- Theme ---
function applyTheme() {
    call('getThemeColors').then(function(colors) {
        var root = document.documentElement.style;
        root.setProperty('--bg-base', colors.bg);
        root.setProperty('--bg-surface', colors.chrome_bg);
        root.setProperty('--bg-surface-hover', colors.hover_bg);
        root.setProperty('--accent', colors.accent);
        root.setProperty('--accent-transparent', colors.accent_soft);
        root.setProperty('--text-main', colors.text);
        root.setProperty('--text-muted', colors.text_dim);
        root.setProperty('--border', colors.border);
        root.setProperty('--danger', colors.error);
        root.setProperty('--success', colors.success);
        root.setProperty('--warning', colors.warning);
    });
}

// --- Drag-drop toast (called from Python event filter) ---
window._dragToastEl = null;
window._showDragToast = function(message) {
    if (window._dragToastEl) return;
    var msg = message || 'Drop to add game';
    var container = document.getElementById('toast-container');
    var toast = document.createElement('div');
    toast.className = 'toast';
    var icon = document.createElement('div');
    icon.className = 'toast-icon';
    icon.style.color = 'var(--accent)';
    icon.innerHTML =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    var body = document.createElement('div');
    body.textContent = msg;
    toast.appendChild(icon);
    toast.appendChild(body);
    container.appendChild(toast);
    window._dragToastEl = toast;
    setTimeout(function() { toast.classList.add('show'); }, 10);
};
window._hideDragToast = function() {
    var toast = window._dragToastEl;
    if (!toast) return;
    window._dragToastEl = null;
    toast.classList.remove('show');
    setTimeout(function() { toast.remove(); }, 300);
};

// --- Init ---
onBridgeReady(function() {
    call('getSettings').then(function(settings) {
        var collapsed = !!(settings && settings.restore_geometry && settings.sidebar_collapsed);
        applySidebarState(collapsed);
    });
    applyTheme();
    refreshLibrary();
    refreshRunners();
    initSettings();
});
