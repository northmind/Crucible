/* modal.js — Game detail modal: Steam Library Style */
'use strict';

var _modalGame = null;
var _modalTab = 'overview';
var _modalReturnView = 'library';

function openGameModal(gameName) {
    var modal = document.getElementById('hero-modal');
    if (modal && !modal.classList.contains('open')) {
        _modalReturnView = window._activeView || 'library';
    }
    call('getGame', gameName).then(function(game) {
        if (!game || !game.name) return;
        _modalGame = game;
        _modalTab = 'overview';
        renderModal();
        modal.classList.add('open');
        if (bridge && bridge.setActiveView) bridge.setActiveView('modal');
        if (bridge && bridge.setModalGameName) bridge.setModalGameName(game.name);
    });
}

function closeGameModal(nextView) {
    var restoreView = nextView || _modalReturnView || 'library';
    document.getElementById('hero-modal').classList.remove('open');
    _modalGame = null;
    _modalReturnView = restoreView === 'modal' ? 'library' : restoreView;
    if (bridge && bridge.setActiveView) bridge.setActiveView(restoreView);
    if (bridge && bridge.setModalGameName) bridge.setModalGameName('');
}

function getModalScrollTop() {
    var content = document.querySelector('#hero-modal .modal-content-area');
    return content ? content.scrollTop : 0;
}

function restoreModalScrollTop(scrollTop) {
    if (!scrollTop) return;
    setTimeout(function() {
        var content = document.querySelector('#hero-modal .modal-content-area');
        if (content) content.scrollTop = scrollTop;
    }, 0);
}

function renderModal() {
    var g = _modalGame;
    var modal = document.getElementById('hero-modal');
    modal.innerHTML = '';

    // Close button
    var closeBtn = document.createElement('div');
    closeBtn.className = 'modal-close';
    closeBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
    closeBtn.addEventListener('click', closeGameModal);
    modal.appendChild(closeBtn);

    // Hero banner
    var header = document.createElement('div');
    header.className = 'hero-header';
    var bannerImg = document.createElement('img');
    bannerImg.className = 'hero-banner';
    bannerImg.alt = g.name;
    call('getHeroArtworkPath', g.exe_path).then(function(path) {
        if (path) {
            bannerImg.src = 'file://' + path;
        }
    });
    header.appendChild(bannerImg);
    var gradient = document.createElement('div');
    gradient.className = 'hero-gradient';
    header.appendChild(gradient);
    modal.appendChild(header);

    // Steam Play Bar (Play btn, Meta info, Actions)
    var playBar = document.createElement('div');
    playBar.className = 'steam-play-bar';
    renderPlayBar(playBar, g, header);
    modal.appendChild(playBar);

    // Horizontal Tabs
    var navBar = document.createElement('div');
    navBar.className = 'steam-nav-bar';
    renderNavBar(navBar, g);
    modal.appendChild(navBar);

    // Content Area
    var contentArea = document.createElement('div');
    contentArea.className = 'modal-content-area';
    contentArea.id = 'modal-tab-content';
    modal.appendChild(contentArea);

    setTimeout(renderModalTabContent, 0);
}

function renderPlayBar(container, g, heroHeader) {
    // Play button
    var playBtn = document.createElement('button');
    playBtn.className = 'hero-play-btn';
    playBtn.id = 'modal-play-btn';
    
    var playSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    
    function setPlayState(running) {
        playBtn.innerHTML = playSvg + ' <span>' + (running ? 'STOP' : 'PLAY') + '</span>';
        if (running) {
            playBtn.classList.add('stop');
        } else {
            playBtn.classList.remove('stop');
        }
        playBtn.dataset.running = running ? '1' : '0';
    }
    
    playBtn.addEventListener('click', function() {
        if (playBtn.dataset.running === '1') {
            call('stopGame', g.name).then(function(ok) {
                if (ok) { showToast('Stopping ' + g.name + '...', 'info'); setPlayState(false); }
                else showToast('Failed to stop game', 'error');
            });
        } else {
            call('launchGame', g.name).then(function(err) {
                if (err) showToast(err, 'error');
                else { showToast('Launching ' + g.name + '...', 'success'); setPlayState(true); }
            });
        }
    });

    container.appendChild(playBtn);

    // Initial state check
    setPlayState(false);
    call('isGameRunning', g.name).then(function(r) { setPlayState(r); });

    // Meta blocks (Last Played, Playtime)
    var metaBlock1 = document.createElement('div');
    metaBlock1.className = 'steam-meta-block';
    var lp = formatLastPlayed(g.last_played);
    metaBlock1.innerHTML = '<span class="steam-meta-label">Last Played</span><span class="steam-meta-value">' + (lp === 'Never' ? 'Never played' : lp) + '</span>';
    container.appendChild(metaBlock1);

    var pt = formatPlaytime(g.playtime_seconds);
    if (pt && pt !== 'Never played') {
        var metaBlock2 = document.createElement('div');
        metaBlock2.className = 'steam-meta-block';
        metaBlock2.innerHTML = '<span class="steam-meta-label">Play Time</span><span class="steam-meta-value">' + pt + '</span>';
        container.appendChild(metaBlock2);
    }

}

function renderNavBar(container, g) {
    var cleanTabs = ['Overview', 'Launch Options', 'Graphics', 'Advanced Wine', 'Manage Data'];
    var tabIds = ['overview', 'launch', 'graphics', 'wine', 'data'];
    
    tabIds.forEach(function(id, i) {
        var btn = document.createElement('button');
        btn.className = 'steam-nav-item' + (id === _modalTab ? ' active' : '');
        btn.dataset.mtab = id;
        btn.textContent = cleanTabs[i];
        btn.addEventListener('click', function() {
            container.querySelectorAll('.steam-nav-item').forEach(function(t) { t.classList.remove('active'); });
            btn.classList.add('active');
            _modalTab = id;
            renderModalTabContent();
        });
        container.appendChild(btn);
    });

    // Action buttons (right side)
    var actions = document.createElement('div');
    actions.className = 'nav-actions';

    var svgStyle = 'width:16px;height:16px';
    var svgAttrs = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"';

    // Winetricks button (wrench icon)
    var wtBtn = document.createElement('button');
    wtBtn.className = 'nav-action-btn';
    wtBtn.title = 'Open Winetricks';
    wtBtn.innerHTML = '<svg ' + svgAttrs + ' style="' + svgStyle + '"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>';
    wtBtn.addEventListener('click', function() { call('launchWinetricks', g.name); });
    actions.appendChild(wtBtn);

    // View Logs button (file-text icon)
    var logBtn = document.createElement('button');
    logBtn.className = 'nav-action-btn';
    logBtn.title = 'View Logs';
    logBtn.innerHTML = '<svg ' + svgAttrs + ' style="' + svgStyle + '"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>';
    logBtn.addEventListener('click', function() { call('openGameLogDir', g.name); });
    actions.appendChild(logBtn);

    // Desktop Shortcut button (link icon)
    var shortcutBtn = document.createElement('button');
    shortcutBtn.className = 'nav-action-btn';
    shortcutBtn.id = 'modal-shortcut-btn';
    shortcutBtn.title = 'Desktop Shortcut';
    shortcutBtn.innerHTML = '<svg ' + svgAttrs + ' style="' + svgStyle + '"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>';
    call('hasShortcut', g.name).then(function(has) {
        shortcutBtn.dataset.has = has ? '1' : '0';
        if (has) shortcutBtn.classList.add('active');
    });
    shortcutBtn.addEventListener('click', function() {
        if (shortcutBtn.dataset.has === '1') {
            call('removeShortcut', g.name).then(function(ok) {
                if (ok) { showToast('Shortcut removed', 'success'); shortcutBtn.dataset.has = '0'; shortcutBtn.classList.remove('active'); }
                else showToast('Failed to remove shortcut', 'error');
            });
        } else {
            call('createShortcut', g.name).then(function(r) {
                showToast(r.message, r.success ? 'success' : 'error');
                if (r.success) { shortcutBtn.dataset.has = '1'; shortcutBtn.classList.add('active'); }
            });
        }
    });
    actions.appendChild(shortcutBtn);

    container.appendChild(actions);
}

function renderModalTabContent() {
    var g = _modalGame;
    var el = document.getElementById('modal-tab-content');
    if (!el || !g) return;
    var html = '';
    if (_modalTab === 'overview') html = renderTabOverview(g);
    else if (_modalTab === 'launch') html = renderTabLaunch(g);
    else if (_modalTab === 'graphics') html = renderTabGraphics(g);
    else if (_modalTab === 'wine') html = renderTabWine(g);
    else if (_modalTab === 'data') html = renderTabData(g);
    el.innerHTML = '<div class="modal-tab-content active">' + html + '</div>';
    bindModalEvents(el, g);
}

function bindModalEvents(container, g) {
    bindRunnerSelect(container, g);
    bindInputFields(container, g);
    bindToggles(container, g);
    bindBrowseButtons(container, g);
    bindEnvVarControls(container, g);
    bindActionButtons(container, g);
}

function bindRunnerSelect(container, g) {
    var sel = container.querySelector('#modal-runner');
    if (!sel) return;
    call('getRunnerNames').then(function(names) {
        var current = g.proton_version || '';
        sel.innerHTML = '';
        var placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select Proton version';
        placeholder.disabled = true;
        if (!current) placeholder.selected = true;
        sel.appendChild(placeholder);
        (names || []).forEach(function(n) {
            var opt = document.createElement('option');
            opt.value = n; opt.textContent = n;
            if (n === current) opt.selected = true;
            sel.appendChild(opt);
        });
    });
    sel.addEventListener('change', function() {
        updateGameField(g.name, 'proton_version', sel.value);
    });
}

function updateGameField(name, field, value, onSuccess, options) {
    var opts = options || {};
    var modal = document.getElementById('hero-modal');
    var modalWasOpen = !!(modal && modal.classList.contains('open'));
    var activeModalName = _modalGame && _modalGame.name;
    var scrollTop = getModalScrollTop();
    call('updateGameField', name, field, value).then(function(ok) {
        if (!ok) return;
        var targetName = field === 'name' ? String(value || '').trim() : name;
        call('getGame', targetName).then(function(updated) {
            if (!updated || !updated.name) return;
            if (typeof onSuccess === 'function') onSuccess(updated);

            var shouldRefreshModal = modalWasOpen && _modalGame &&
                (_modalGame.name === activeModalName || _modalGame.name === targetName);
            _modalGame = updated;
            if (bridge && bridge.setModalGameName) bridge.setModalGameName(updated.name);
            if (!shouldRefreshModal || opts.rerender === false) return;
            renderModal();
            restoreModalScrollTop(scrollTop);
        });
    });
}

var _gsUpdatePending = false;
function updateGamescopeField(name, field, value) {
    if (_gsUpdatePending) {
        setTimeout(function() { updateGamescopeField(name, field, value); }, 50);
        return;
    }
    _gsUpdatePending = true;
    call('getGame', name).then(function(game) {
        if (!game || !game.name) {
            _gsUpdatePending = false;
            return;
        }
        var gs = Object.assign({}, game.gamescope_settings || {});
        gs[field] = value;
        updateGameField(name, 'gamescope_settings', gs, function(updated) {
            _gsUpdatePending = false;
            if (!updated || !updated.name) return;
        }, { rerender: false });
    }).catch(function() {
        _gsUpdatePending = false;
    });
}

function onGameRunningChanged(name, running) {
    if (_modalGame && _modalGame.name === name) {
        var playBtn = document.getElementById('modal-play-btn');
        if (playBtn) {
            var playSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
            playBtn.innerHTML = playSvg + ' <span>' + (running ? 'STOP' : 'PLAY') + '</span>';
            if (running) {
                playBtn.classList.add('stop');
            } else {
                playBtn.classList.remove('stop');
            }
            playBtn.dataset.running = running ? '1' : '0';
        }
    }
}
