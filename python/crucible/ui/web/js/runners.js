/* runners.js — Wine Cabinet with sidebar source tabs + grouped list rows */
'use strict';

var _activeSource = 'ge';
var _cabinetSources = [
    { id: 'ge', label: 'GE-Proton', icon: '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>' },
    { id: 'umu', label: 'UMU-Proton', icon: '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>' },
    { id: 'cachy', label: 'CachyProton', icon: '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>' }
];

function initCabinetSidebar() {
    var sb = document.getElementById('cabinet-sidebar');
    var html = '<div class="nav-label" style="padding:0;margin-bottom:12px">Sources</div>';
    for (var i = 0; i < _cabinetSources.length; i++) {
        var s = _cabinetSources[i];
        var cls = s.id === _activeSource ? 'internal-nav-item active' : 'internal-nav-item';
        html += '<div class="' + cls + '" data-source="' + s.id + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
            s.icon + '</svg>' + s.label + '</div>';
    }
    sb.innerHTML = html;
    sb.querySelectorAll('.internal-nav-item').forEach(function(el) {
        el.addEventListener('click', function() {
            sb.querySelectorAll('.internal-nav-item').forEach(function(n) { n.classList.remove('active'); });
            el.classList.add('active');
            _activeSource = el.dataset.source;
            renderCabinetContent();
        });
    });
}

function refreshRunners() {
    initCabinetSidebar();
    renderCabinetContent();
}

function renderCabinetContent() {
    var content = document.getElementById('cabinet-content');
    content.innerHTML = '<div style="color:var(--text-muted);padding:24px">Loading...</div>';

    // All sources now have backend support
    Promise.all([
        call('getInstalledRunnersForSource', _activeSource),
        call('fetchReleasesForSource', _activeSource)
    ]).then(function(results) {
        var installed = results[0] || {};
        var releases = results[1] || {};
        var html = '';

        // Installed section
        var iKeys = Object.keys(installed);
        var installedNames = {};
        html += '<div class="cabinet-section">';
        html += '<div class="cabinet-section-title">Installed <span class="count">' + iKeys.length + '</span></div>';
        if (iKeys.length === 0) {
            html += '<div class="cabinet-empty">No runners installed</div>';
        } else {
            html += '<div class="list-group">';
            for (var i = 0; i < iKeys.length; i++) {
                var r = installed[iKeys[i]];
                installedNames[r.name] = true;
                html += '<div class="runner-row">' +
                    '<div class="runner-name">' + escapeHtml(r.name) + '</div>' +
                    '<button class="btn-action delete" data-tag="' +
                    escapeHtml(r.tag || r.name) + '">Delete</button></div>';
            }
            html += '</div>';
        }
        html += '</div>';

        // Available section
        var rKeys = Object.keys(releases);
        var availRows = '';
        var availCount = 0;
        for (var j = 0; j < rKeys.length; j++) {
            var rel = releases[rKeys[j]];
            if (installedNames[rel.tag] || installedNames[rel.name]) continue;
            availCount++;
            availRows += '<div class="runner-row">' +
                '<div class="runner-name">' + escapeHtml(rel.tag || rel.name) + '</div>' +
                '<button class="btn-action download" data-tag="' +
                escapeHtml(rel.tag) + '"><span class="progress-fill"></span><span class="btn-label">Download</span></button></div>';
        }
        html += '<div class="cabinet-section">';
        html += '<div class="cabinet-section-title collapsible collapsed" id="avail-toggle">' +
            '<svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>' +
            'Available <span class="count">' + availCount + '</span></div>';
        if (availCount === 0) {
            html += '<div class="cabinet-empty" style="display:none" data-collapsible="avail">No releases found</div>';
        } else {
            html += '<div class="list-group" style="display:none" data-collapsible="avail">' + availRows + '</div>';
        }
        html += '</div>';

        content.innerHTML = html;
        bindCabinetActions(content);
    });
}

function bindCabinetActions(container) {
    var source = _activeSource;
    // Collapsible toggle
    var toggle = document.getElementById('avail-toggle');
    if (toggle) {
        toggle.addEventListener('click', function() {
            toggle.classList.toggle('collapsed');
            var body = container.querySelector('[data-collapsible="avail"]');
            if (body) body.style.display = toggle.classList.contains('collapsed') ? 'none' : '';
        });
    }
    container.querySelectorAll('.btn-action.delete').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var tag = btn.dataset.tag;
            call('deleteRunner', tag).then(function(ok) {
                if (ok) { showToast('Deleted ' + tag, 'success'); renderCabinetContent(); }
            });
        });
    });
    container.querySelectorAll('.btn-action.download').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var tag = btn.dataset.tag;
            btn.classList.add('downloading');
            btn.querySelector('.btn-label').textContent = '0%';
            call('downloadRunnerFromSource', tag, source);
        });
    });
}

function onDownloadProgress(data) {
    var btn = document.querySelector('.btn-action.download[data-tag="' + data.tag + '"]');
    if (btn) {
        var fill = btn.querySelector('.progress-fill');
        var label = btn.querySelector('.btn-label');
        if (fill) fill.style.width = Math.min(data.percent, 100) + '%';
        if (label) {
            if (data.percent >= 100) label.textContent = 'Done';
            else if (data.percent >= 85) label.textContent = 'Installing...';
            else if (data.percent >= 70) label.textContent = 'Extracting...';
            else label.textContent = data.percent + '%';
        }
    }
    if (data.percent >= 100) {
        setTimeout(renderCabinetContent, 500);
    }
}
