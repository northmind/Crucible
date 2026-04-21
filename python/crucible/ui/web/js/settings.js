/* settings.js — Settings view rendering */
'use strict';

var _settingsData = {};
var _globalConfig = {};
var _activeSettingsTab = 'general';

function initSettings() {
    refreshSettings('general');
}

function refreshSettings(preferredTab) {
    var nextTab = preferredTab || _activeSettingsTab || 'general';
    Promise.all([call('getSettings'), call('getGlobalConfig')]).then(function(r) {
        _settingsData = r[0] || {};
        _globalConfig = r[1] || {};
        if (_settingsData.font_family) document.documentElement.style.setProperty('--font-family', _settingsData.font_family);
        _activeSettingsTab = nextTab;
        renderSettingsSidebar();
        renderSettingsTab(nextTab);
    });
}

function renderSettingsSidebar() {
    var sb = document.getElementById('settings-sidebar');
    sb.innerHTML =
        '<div class="nav-label" style="padding:0;margin-bottom:12px">App Preferences</div>' +
        settingsNavItem('general', 'General & Appearance', '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line>') +
        settingsNavItem('paths', 'Paths & Storage', '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>') +
        '<div class="nav-label" style="padding:0;margin-bottom:12px;margin-top:24px">Game Defaults</div>' +
        settingsNavItem('runner', 'Runner & Launch', '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>') +
        settingsNavItem('graphics', 'Graphics & Perf', '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>') +
        '<div class="nav-label" style="padding:0;margin-bottom:12px;margin-top:24px">Advanced</div>' +
        settingsNavItem('security', 'Debug', '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>');

    sb.querySelectorAll('.internal-nav-item').forEach(function(el) {
        el.addEventListener('click', function() {
            sb.querySelectorAll('.internal-nav-item').forEach(function(n) { n.classList.remove('active'); });
            el.classList.add('active');
            renderSettingsTab(el.dataset.tab);
        });
    });
}

function settingsNavItem(id, label, svgInner) {
    var cls = id === _activeSettingsTab ? 'internal-nav-item active' : 'internal-nav-item';
    return '<div class="' + cls + '" data-tab="' + id + '">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' + svgInner + '</svg>' +
        label + '</div>';
}

function renderSettingsTab(tabId) {
    _activeSettingsTab = tabId;
    var content = document.getElementById('settings-content');
    var html = '';
    if (tabId === 'general') html = renderGeneralTab();
    else if (tabId === 'paths') html = renderPathsTab();
    else if (tabId === 'runner') html = renderRunnerTab();
    else if (tabId === 'graphics') html = renderGraphicsTab();
    else if (tabId === 'security') html = renderSecurityTab();
    content.innerHTML = html;
    bindSettingsEvents(content);
}

function renderGeneralTab() {
    var fonts = ['Fira Code', 'Inter', 'Exo 2', 'Outfit', 'Rajdhani', 'Lexend'];
    var fontOpts = '';
    fonts.forEach(function(f) {
        fontOpts += '<option value="' + f + '"' + (f === _settingsData.font_family ? ' selected' : '') + '>' + f + '</option>';
    });
    return '<div class="settings-card"><h3>Behavior & Updates</h3>' +
        settingToggleRow('Minimize to tray', '', 'minimize_to_tray', _settingsData.minimize_to_tray) +
        settingToggleRow('Remember window size', '', 'restore_geometry', _settingsData.restore_geometry) +
        settingToggleRow('Auto-update umu-run', '', 'auto_update_umu', _settingsData.auto_update_umu) +
        '</div><div class="settings-card"><h3>Appearance</h3>' +
        '<div class="setting-row"><div class="setting-info"><h4>Font Family</h4></div>' +
        '<select class="input-field" data-key="font_family" style="width:200px">' + fontOpts + '</select></div>' +
        '</div><div class="settings-card"><h3>Themes</h3>' +
        '<div class="theme-grid" id="theme-grid"></div></div>';
}

function renderPathsTab() {
    return '<div class="settings-card"><h3>Storage Locations</h3>' +
        settingBrowseRow('Custom Proton Directory', 'custom_proton_dir', _settingsData.custom_proton_dir || '') +
        '</div>';
}

function renderRunnerTab() {
    return '<div class="settings-card"><h3>Global Runner Defaults</h3>' +
        '<div class="input-group"><label>Default Proton Version</label>' +
        '<select class="input-field" data-key="gc:default_runner" id="settings-runner-select"></select></div>' +
        '</div><div class="settings-card"><h3>Global Launch Parameters</h3>' +
        settingInputRow('Launch Arguments (ARGS)', 'gc:launch_args', _globalConfig.launch_args || '') +
        settingInputRow('Custom DLL Overrides (WINEDLLOVERRIDES)', 'gc:custom_overrides', _globalConfig.custom_overrides || '') +
        settingInputRow('Wrapper Command (WRAP)', 'gc:wrapper_command', _globalConfig.wrapper_command || '') +
        '</div>';
}

function renderGraphicsTab() {
    var upscaleMethod = (_globalConfig.gs_upscale_method || '').toLowerCase();
    var windowType = (_globalConfig.gs_window_type || '').toLowerCase();
    return '<div class="settings-card"><h3>Global Performance Defaults</h3>' +
        settingToggleRow('Enable GameMode', 'Default for OS optimizations during gameplay.', 'gc:enable_gamemode', _globalConfig.enable_gamemode) +
        settingToggleRow('Enable MangoHUD', 'Default overlay injection.', 'gc:enable_mangohud', _globalConfig.enable_mangohud) +
        settingToggleRow('Enable Gamescope', 'Default for the micro-compositor.', 'gc:enable_gamescope', _globalConfig.enable_gamescope) +
        settingToggleRow('Force Grab Cursor', 'Gamescope cursor confinement.', 'gc:force_grab_cursor', _globalConfig.force_grab_cursor) +
        '<h4 style="margin-top:24px;margin-bottom:12px;font-size:13px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;font-weight:600">Gamescope Resolution &amp; Upscaling</h4>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
        settingInputRow('Game Width', 'gc:gs_game_width', _globalConfig.gs_game_width || '') +
        settingInputRow('Game Height', 'gc:gs_game_height', _globalConfig.gs_game_height || '') +
        settingInputRow('Upscale Width', 'gc:gs_upscale_width', _globalConfig.gs_upscale_width || '') +
        settingInputRow('Upscale Height', 'gc:gs_upscale_height', _globalConfig.gs_upscale_height || '') +
        '</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
        '<div class="input-group"><label>Upscale Method</label>' +
        '<select class="input-field" data-key="gc:gs_upscale_method">' +
        '<option' + (upscaleMethod === 'fsr' ? ' selected' : '') + '>FSR</option>' +
        '<option' + (upscaleMethod === 'nis' ? ' selected' : '') + '>NIS</option>' +
        '<option' + (upscaleMethod === 'integer' ? ' selected' : '') + '>integer</option>' +
        '<option' + (upscaleMethod === 'stretch' ? ' selected' : '') + '>stretch</option></select></div>' +
        '<div class="input-group"><label>Window Type</label>' +
        '<select class="input-field" data-key="gc:gs_window_type">' +
        '<option' + (windowType === 'borderless' ? ' selected' : '') + '>Borderless</option>' +
        '<option' + (windowType === 'fullscreen' ? ' selected' : '') + '>Fullscreen</option></select></div>' +
        '</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
        settingInputRow('FPS Limiter', 'gc:gs_fps_limiter', _globalConfig.gs_fps_limiter || '') +
        settingInputRow('FPS Limiter (No Focus)', 'gc:gs_fps_limiter_no_focus', _globalConfig.gs_fps_limiter_no_focus || '') +
        '</div>' +
        settingInputRow('Additional Options', 'gc:gs_additional_options', _globalConfig.gs_additional_options || '') +
        '</div>';
}

function renderSecurityTab() {
    var env = _globalConfig.env_vars || {};
    return '<div class="settings-card"><h3>Debug</h3>' +
        settingRadioRow('Log Level', 'log_level', ['info', 'debug', 'off'], _settingsData.log_level || 'info') +
        '</div><div class="settings-card"><h3>Global Environment</h3>' +
        settingToggleRow('Disable UMU runtime update', 'Skip umu-proton runtime updates on launch.', 'genv:UMU_RUNTIME_UPDATE', !!env['UMU_RUNTIME_UPDATE']) +
        settingToggleRow('Disable Steam client', 'Disable lsteamclient library injection.', 'genv:PROTON_DISABLE_LSTEAMCLIENT', !!env['PROTON_DISABLE_LSTEAMCLIENT']) +
        '</div>';
}

// --- Setting row builders ---
function settingToggleRow(label, desc, key, checked) {
    return '<div class="setting-row"><div class="setting-info"><h4>' + label + '</h4>' +
        (desc ? '<p>' + desc + '</p>' : '') +
        '</div><label class="toggle"><input type="checkbox" data-key="' + key + '"' +
        (checked ? ' checked' : '') + '><span class="slider"></span></label></div>';
}

function settingRadioRow(label, key, options, current) {
    var radios = '<div class="radio-group">';
    options.forEach(function(opt) {
        radios += '<div class="radio-btn' + (opt === current ? ' selected' : '') + '" data-key="' + key + '" data-value="' + opt + '">' + opt + '</div>';
    });
    return '<div class="setting-row"><div class="setting-info"><h4>' + label + '</h4></div>' + radios + '</div></div>';
}

function settingInputRow(label, key, value) {
    return '<div class="input-group"><label>' + label + '</label>' +
        '<input type="text" class="input-field" data-key="' + key + '" value="' + escapeHtml(value) + '"></div>';
}

function settingBrowseRow(label, key, value) {
    return '<div class="input-group"><label>' + label + '</label><div class="input-row">' +
        '<input type="text" class="input-field" data-key="' + key + '" value="' + escapeHtml(value) + '">' +
        '<button class="btn-action download" data-browse="' + key + '">Browse</button></div></div>';
}

function bindSettingsEvents(container) {
    // Toggles
    container.querySelectorAll('.toggle input').forEach(function(inp) {
        inp.addEventListener('change', function() {
            var key = inp.dataset.key;
            var val = inp.checked;
            if (key.indexOf('genv:') === 0) {
                var envKey = key.slice(5);
                var envVal = envKey === 'UMU_RUNTIME_UPDATE' ? '0' : '1';
                var env = _globalConfig.env_vars || {};
                if (val) env[envKey] = envVal;
                else delete env[envKey];
                _globalConfig.env_vars = env;
                call('setGlobalEnvVar', envKey, envVal, val);
            } else if (key.indexOf('gc:') === 0) {
                var gcKey = key.slice(3);
                _globalConfig[gcKey] = val;
                call('setGlobalConfig', gcKey, val);
            } else {
                call('setSetting', key, val); _settingsData[key] = val;
            }
        });
    });
    // Radios
    container.querySelectorAll('.radio-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            btn.parentElement.querySelectorAll('.radio-btn').forEach(function(b) { b.classList.remove('selected'); });
            btn.classList.add('selected');
            var key = btn.dataset.key, val = btn.dataset.value;
            if (key.indexOf('gc:') === 0) {
                var gcKey = key.slice(3);
                _globalConfig[gcKey] = val;
                call('setGlobalConfig', gcKey, val);
            }
            else { call('setSetting', key, val); _settingsData[key] = val; }
        });
    });
    // Inputs (on blur)
    container.querySelectorAll('.input-field[data-key]').forEach(function(inp) {
        inp.addEventListener('change', function() {
            var key = inp.dataset.key, val = inp.value;
            if (key.indexOf('gc:') === 0) {
                var gcKey = key.slice(3);
                _globalConfig[gcKey] = val;
                call('setGlobalConfig', gcKey, val);
            }
            else {
                call('setSetting', key, val); _settingsData[key] = val;
                if (key === 'font_family') document.documentElement.style.setProperty('--font-family', val);
            }
        });
    });
    // Browse buttons
    container.querySelectorAll('[data-browse]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            call('openDirDialog', btn.dataset.browse).then(function(path) {
                if (path) {
                    var inp = container.querySelector('.input-field[data-key="' + btn.dataset.browse + '"]');
                    if (inp) { inp.value = path; inp.dispatchEvent(new Event('change')); }
                }
            });
        });
    });
    // Theme grid
    var themeGrid = document.getElementById('theme-grid');
    // Runner select in settings
    var runnerSel = document.getElementById('settings-runner-select');
    if (runnerSel) {
        call('getRunnerNames').then(function(names) {
            runnerSel.innerHTML = '';
            (names || []).forEach(function(n) {
                var opt = document.createElement('option');
                opt.value = n; opt.textContent = n;
                if (n === _globalConfig.default_runner) opt.selected = true;
                runnerSel.appendChild(opt);
            });
            if (!_globalConfig.default_runner && names && names.length) {
                runnerSel.value = names[0];
            }
        });
        runnerSel.addEventListener('change', function() {
            _globalConfig.default_runner = runnerSel.value;
            call('setGlobalConfig', 'default_runner', runnerSel.value);
        });
    }
    if (themeGrid) {
        Promise.all([call('getThemes'), call('getActiveThemeKey')]).then(function(r) {
            var themes = r[0], activeKey = r[1];
            themeGrid.innerHTML = '';
            themes.forEach(function(t) {
                var swatch = document.createElement('div');
                swatch.className = 'theme-swatch' + (t.key === activeKey ? ' active' : '');
                swatch.style.backgroundColor = t.bg;
                swatch.innerHTML = '<div class="theme-swatch-dot" style="background-color:' + t.accent + '"></div>' +
                    '<span style="color:' + t.text + '">' + escapeHtml(t.name) + '</span>';
                swatch.addEventListener('click', function() {
                    call('setTheme', t.key);
                    themeGrid.querySelectorAll('.theme-swatch').forEach(function(s) { s.classList.remove('active'); });
                    swatch.classList.add('active');
                });
                themeGrid.appendChild(swatch);
            });
        });
    }
}
