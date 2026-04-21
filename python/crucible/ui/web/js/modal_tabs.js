/* modal_tabs.js — Modal tab rendering (Design A: Steam-Style Flat Sections, 5 tabs) */
'use strict';

/* ── Tab 1: Overview ── */
function renderTabOverview(g) {
    var raw = g._raw || {};
    return '<div class="sections">' +
        '<div class="section-title">Game Identity</div>' +
        '<div class="section">' +
            sField('Name', '', 'name', g.name) +
            sFieldBrowse('Executable Path', '', 'exe_path', g.exe_path, 'file') +
            sFieldBrowse('Install Directory', '', 'install_dir', g.install_dir, 'dir') +
        '</div>' +
        '<div class="section-title">Wine / Proton</div>' +
        '<div class="section">' +
            sFieldSelect('Runner Version', '', 'proton_version') +
            sFieldBrowse('Prefix Path', 'Leave empty for default', 'prefix_path', raw.prefix_path || '', 'dir') +
        '</div>' +
    '</div>';
}

/* ── Tab 2: Launch Options ── */
function renderTabLaunch(g) {
    var envVars = g.env_vars || {};
    var envRows = '';
    Object.keys(envVars).forEach(function(k) { envRows += envVarRow(k, envVars[k]); });

    return '<div class="sections">' +
        '<div class="section-title">Command Line</div>' +
        '<div class="section-desc">Advanced users may modify launch parameters.</div>' +
        '<div class="section">' +
            sField('Launch Arguments', '', 'launch_args', g.launch_args || '') +
            sField('DLL Overrides', '', 'custom_overrides', g.custom_overrides || '') +
            sField('Wrapper Command', '', 'wrapper_command', g.wrapper_command || '') +
        '</div>' +
        '<div class="section-title">Environment Variables</div>' +
        '<div class="section-desc">Custom environment variables passed to the game process.</div>' +
        '<div class="section">' +
            '<table class="env-table"><thead><tr>' +
            '<th>Key</th><th>Value</th>' +
            '<th style="width:28px"><button class="add-env-btn" id="add-env-btn">+</button></th>' +
            '</tr></thead><tbody id="env-tbody">' + envRows + '</tbody></table>' +
        '</div>' +
    '</div>';
}

/* ── Tab 3: Graphics ── */
function renderTabGraphics(g) {
    var gs = g.gamescope_settings || {};
    var env = g.env_vars || {};
    var gsVisible = g.enable_gamescope ? '' : ' style="display:none"';

    return '<div class="sections">' +
        '<div class="section-title">Performance</div>' +
        '<div class="section-desc">System-level performance enhancements applied during gameplay.</div>' +
        '<div class="section">' +
            sToggleRow('Enable GameMode', 'OS-level CPU/GPU optimizations during gameplay.', 'enable_gamemode', g.enable_gamemode) +
            sToggleRow('Enable MangoHUD', 'In-game performance overlay.', 'enable_mangohud', g.enable_mangohud) +
            sToggleRow('Enable Gamescope', 'Wrap game in the Gamescope micro-compositor.', 'enable_gamescope', g.enable_gamescope) +
        '</div>' +
        '<div class="section-title">Engine Upscaling</div>' +
        '<div class="section-desc">Enable upscaling technology replacements injected into the game engine.</div>' +
        '<div class="section">' +
            sToggleRow('DLSS upgrade', '', 'env:PROTON_DLSS_UPGRADE:1', env['PROTON_DLSS_UPGRADE'] === '1') +
            sToggleRow('FSR3 upgrade', '', 'env:PROTON_FSR3_UPGRADE:1', env['PROTON_FSR3_UPGRADE'] === '1') +
            sToggleRow('FSR4 upgrade', '', 'env:PROTON_FSR4_UPGRADE:1', env['PROTON_FSR4_UPGRADE'] === '1') +
            sToggleRow('FSR4 RDNA3', '', 'env:PROTON_FSR4_RDNA3_UPGRADE:1', env['PROTON_FSR4_RDNA3_UPGRADE'] === '1') +
            sToggleRow('XeSS upgrade', '', 'env:PROTON_XESS_UPGRADE:1', env['PROTON_XESS_UPGRADE'] === '1') +
        '</div>' +
        '<div id="gamescope-group"' + gsVisible + '>' +
        '<div class="section-title">Gamescope</div>' +
        '<div class="section-desc">Resolution, upscaling, and compositor options. Only applies when Gamescope is enabled.</div>' +
        '<div class="section">' +
            sField('Game Width', '', 'gs:game_width', gs.game_width || '') +
            sField('Game Height', '', 'gs:game_height', gs.game_height || '') +
            sField('Upscale Width', '', 'gs:upscale_width', gs.upscale_width || '') +
            sField('Upscale Height', '', 'gs:upscale_height', gs.upscale_height || '') +
            sFieldSelect('Upscale Method', '', 'gs:upscale_method',
                gsOption('FSR', gs.upscale_method) + gsOption('NIS', gs.upscale_method) + gsOption('integer', gs.upscale_method)) +
            sFieldSelect('Window Type', '', 'gs:window_type',
                gsOption('Borderless', gs.window_type) + gsOption('Fullscreen', gs.window_type)) +
            sToggleRow('Force Grab Cursor', 'Confine cursor to game window.', 'gs:enable_force_grab_cursor', gs.enable_force_grab_cursor) +
            sField('FPS Limit', '', 'gs:fps_limiter', gs.fps_limiter || '') +
            sField('FPS Limit (Unfocused)', '', 'gs:fps_limiter_no_focus', gs.fps_limiter_no_focus || '') +
            sField('Additional Options', 'Extra CLI flags', 'gs:additional_options', gs.additional_options || '') +
        '</div>' +
        '</div>' +
    '</div>';
}

/* ── Tab 4: Advanced Wine ── */
function renderTabWine(g) {
    var env = g.env_vars || {};
    return '<div class="sections">' +
        '<div class="section-title">Wine Features</div>' +
        '<div class="section">' +
            sToggleRow('Enable NVAPI', 'NVIDIA API translation layer.', 'env:PROTON_ENABLE_NVAPI:1', env['PROTON_ENABLE_NVAPI'] === '1') +
            sToggleRow('Enable Wayland', 'Native Wayland display driver.', 'env:PROTON_ENABLE_WAYLAND:1', env['PROTON_ENABLE_WAYLAND'] === '1') +
            sToggleRow('Enable HDR', 'High Dynamic Range output.', 'env:PROTON_ENABLE_HDR:1', env['PROTON_ENABLE_HDR'] === '1') +
            sToggleRow('Enable WoW64', 'Run 32-bit apps via 64-bit Wine.', 'env:PROTON_USE_WOW64:1', env['PROTON_USE_WOW64'] === '1') +
            sToggleRow('Use WineD3D', 'OpenGL-based D3D translation instead of DXVK/VKD3D.', 'env:PROTON_USE_WINED3D:1', env['PROTON_USE_WINED3D'] === '1') +
        '</div>' +
        '<div class="section-title">Debugging &amp; Utilities</div>' +
        '<div class="section">' +
            sToggleRow('Enable logging', 'Writes debug output to log files.', 'env:PROTON_LOG:1', env['PROTON_LOG'] === '1') +
            sToggleRow('Disable lsteamclient', 'Skip Steam client library injection.', 'env:PROTON_DISABLE_LSTEAMCLIENT:1', env['PROTON_DISABLE_LSTEAMCLIENT'] === '1') +
            sToggleRow('Skip runtime update', 'Use cached runtime instead of updating.', 'env:UMU_RUNTIME_UPDATE:0', env['UMU_RUNTIME_UPDATE'] === '0') +
        '</div>' +
    '</div>';
}

/* ── Tab 5: Manage Data ── */
function renderTabData(g) {
    return '<div class="sections">' +
        '<div class="section-title">Cleanup</div>' +
        '<div class="section">' +
            sActionRow('Clear Logs', 'Remove all Proton and application logs for this game.', 'clear-logs', 'secondary') +
            sActionRow('Remove UMU Config', 'Clear cached UMU files and settings.', 'remove-umu', 'secondary') +
        '</div>' +
        '<div class="section-title danger">Destructive Actions</div>' +
        '<div class="section-desc">These actions are irreversible. Proceed with caution.</div>' +
        '<div class="section">' +
            sActionRow('Reset Wine Prefix', 'Deletes the entire wine prefix directory. Irreversible.', 'reset-prefix', 'danger') +
            sActionRow('Remove Game Data', 'Delete game config and remove from your library.', 'remove-game', 'danger') +
        '</div>' +
    '</div>';
}

/* ── HTML helpers (Design A flat style) ── */

function sField(label, hint, key, value) {
    return '<div class="s-field"><label>' + label + (hint ? ' <span>' + hint + '</span>' : '') + '</label>' +
        '<input type="text" class="input-field" data-gfield="' + key + '" value="' + escapeHtml(String(value || '')) + '"></div>';
}

function sFieldBrowse(label, hint, key, value, type) {
    return '<div class="s-field"><label>' + label + (hint ? ' <span>' + hint + '</span>' : '') + '</label>' +
        '<div class="input-row"><input type="text" class="input-field" data-gfield="' + key + '" value="' + escapeHtml(String(value || '')) + '">' +
        '<button class="browse-btn" data-gbrowse="' + key + '" data-btype="' + type + '">Browse</button></div></div>';
}

function sFieldSelect(label, hint, key, optionsHtml) {
    var idAttr = key === 'proton_version' ? ' id="modal-runner"' : '';
    return '<div class="s-field"><label>' + label + (hint ? ' <span>' + hint + '</span>' : '') + '</label>' +
        '<select class="input-field" data-gfield="' + key + '"' + idAttr + '>' + (optionsHtml || '') + '</select></div>';
}

function sToggleRow(label, desc, key, checked) {
    return '<div class="s-row"><div class="s-row-info"><h4>' + label + '</h4>' +
        (desc ? '<p>' + desc + '</p>' : '') +
        '</div><label class="toggle"><input type="checkbox" data-gfield="' + key + '"' +
        (checked ? ' checked' : '') + '><span class="slider"></span></label></div>';
}

function modalRawGame() {
    return (_modalGame && _modalGame._raw) || {};
}

function modalGlobalDefaults() {
    return (_modalGame && _modalGame._global) || {};
}

function setModalToggleState(key, checked) {
    var input = document.querySelector('.toggle input[data-gfield="' + key + '"]');
    if (input) input.checked = !!checked;
}

function revertModalOverrideState(key, checked) {
    syncModalOverrideState(key, checked);
    if (key.indexOf('env:') === 0) {
        var parts = key.split(':'), envKey = parts[1], envVal = parts[2];
        var nextEnv = Object.assign({}, _modalGame.env_vars || {});
        if (checked) nextEnv[envKey] = envVal;
        else delete nextEnv[envKey];
        _modalGame.env_vars = nextEnv;
        return;
    }
    _modalGame[key] = checked;
}

function syncModalOverrideState(key, checked) {
    var raw = modalRawGame();
    var globals = modalGlobalDefaults();
    if (key.indexOf('env:') === 0) {
        var parts = key.split(':'), envKey = parts[1], envVal = parts[2];
        var rawEnv = Object.assign({}, raw.env_vars || {});
        var disabledEnv = Array.isArray(raw.disabled_env_vars) ? raw.disabled_env_vars.slice() : [];
        if (checked) {
            if ((globals.env_vars || {}).hasOwnProperty(envKey)) delete rawEnv[envKey];
            else rawEnv[envKey] = envVal;
            disabledEnv = disabledEnv.filter(function(item) { return item !== envKey; });
        } else {
            delete rawEnv[envKey];
            if ((globals.env_vars || {}).hasOwnProperty(envKey) && disabledEnv.indexOf(envKey) === -1) {
                disabledEnv.push(envKey);
            }
        }
        raw.env_vars = rawEnv;
        raw.disabled_env_vars = disabledEnv;
        return;
    }

    var disabledFlags = Array.isArray(raw.disabled_global_flags) ? raw.disabled_global_flags.slice() : [];
    if (checked) {
        raw[key] = true;
        disabledFlags = disabledFlags.filter(function(item) { return item !== key; });
    } else {
        delete raw[key];
        if (disabledFlags.indexOf(key) === -1) disabledFlags.push(key);
    }
    raw.disabled_global_flags = disabledFlags;
}

function sActionRow(label, desc, action, style) {
    return '<div class="s-row"><div class="s-row-info"><h4>' + label + '</h4>' +
        (desc ? '<p>' + desc + '</p>' : '') +
        '</div><button class="action-btn ' + style + '" data-action="' + action + '">Execute</button></div>';
}

function gsOption(val, current) {
    return '<option value="' + val + '"' + (current === val ? ' selected' : '') + '>' + val + '</option>';
}

function envVarRow(k, v) {
    return '<tr><td><input type="text" class="input-field" value="' + escapeHtml(k) + '" data-envkey style="font-family:\'Fira Code\',monospace"></td>' +
        '<td><input type="text" class="input-field" value="' + escapeHtml(String(v)) + '" data-envval></td>' +
        '<td style="text-align:center;color:var(--text-muted);cursor:pointer" data-envdel>&times;</td></tr>';
}

/* ── Tab event binding ── */

function bindInputFields(container, g) {
    container.querySelectorAll('.input-field[data-gfield]').forEach(function(inp) {
        inp.addEventListener('change', function() {
            var key = inp.dataset.gfield;
            if (key.indexOf('gs:') === 0) updateGamescopeField(g.name, key.slice(3), inp.value);
            else updateGameField(g.name, key, inp.value);
        });
    });
}

function bindToggles(container, g) {
    container.querySelectorAll('.toggle input[data-gfield]').forEach(function(inp) {
        inp.addEventListener('change', function() {
            var key = inp.dataset.gfield;
            if (key.indexOf('gs:') === 0) {
                updateGamescopeField(g.name, key.slice(3), inp.checked);
            }
            else if (key.indexOf('env:') === 0) {
                var parts = key.split(':'), envKey = parts[1], envVal = parts[2];
                syncModalOverrideState(key, inp.checked);
                var nextEnv = Object.assign({}, _modalGame.env_vars || {});
                if (inp.checked) nextEnv[envKey] = envVal;
                else delete nextEnv[envKey];
                _modalGame.env_vars = nextEnv;
                call('setGameEnvOverride', g.name, envKey, envVal, inp.checked).then(function(ok) {
                    if (!ok) {
                        revertModalOverrideState(key, !inp.checked);
                        setModalToggleState(key, !inp.checked);
                    }
                });
            }
            else {
                syncModalOverrideState(key, inp.checked);
                _modalGame[key] = inp.checked;
                updateGameField(g.name, key, inp.checked, function() {
                    setModalToggleState(key, inp.checked);
                }, { rerender: false });
                if (key === 'enable_gamescope') {
                    var gsPanel = document.getElementById('gamescope-group');
                    if (gsPanel) gsPanel.style.display = inp.checked ? '' : 'none';
                }
            }
        });
    });
}

function bindBrowseButtons(container, g) {
    container.querySelectorAll('[data-gbrowse]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var method = btn.dataset.btype === 'file' ? 'openFileDialog' : 'openDirDialog';
            var args = method === 'openDirDialog' ? [btn.dataset.gbrowse] : [];
            call.apply(null, [method].concat(args)).then(function(path) {
                if (path) {
                    var inp = container.querySelector('.input-field[data-gfield="' + btn.dataset.gbrowse + '"]');
                    if (inp) { inp.value = path; updateGameField(g.name, btn.dataset.gbrowse, path); }
                }
            });
        });
    });
}

function bindEnvVarControls(container, g) {
    var addBtn = container.querySelector('#add-env-btn');
    if (addBtn) {
        addBtn.addEventListener('click', function() {
            var tbody = container.querySelector('#env-tbody');
            tbody.insertAdjacentHTML('beforeend', envVarRow('NEW_VAR', ''));
            bindEnvRowEvents(tbody, g);
        });
    }
    bindEnvRowEvents(container, g);
}

function bindActionButtons(container, g) {
    container.querySelectorAll('[data-action]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var a = btn.dataset.action;
            if (a === 'clear-logs') call('clearGameLogs', g.name);
            else if (a === 'remove-umu') call('removeUmuConfig', g.name);
            else if (a === 'reset-prefix') call('resetGamePrefix', g.name);
            else if (a === 'remove-game') call('deleteGameFull', g.name).then(function(ok) {
                if (ok) { closeGameModal(); refreshLibrary(); }
            });
        });
    });
}

function bindEnvRowEvents(container, g) {
    container.querySelectorAll('[data-envdel]').forEach(function(el) {
        el.onclick = function() {
            el.closest('tr').remove();
            saveEnvVars(container, g);
        };
    });
    container.querySelectorAll('[data-envkey],[data-envval]').forEach(function(inp) {
        inp.onchange = function() { saveEnvVars(container, g); };
    });
}

function saveEnvVars(container, g) {
    var vars = {};
    container.querySelectorAll('#env-tbody tr').forEach(function(tr) {
        var k = tr.querySelector('[data-envkey]').value.trim();
        var v = tr.querySelector('[data-envval]').value;
        if (k) vars[k] = v;
    });
    if (_modalGame && _modalGame._raw) {
        _modalGame._raw.env_vars = Object.assign({}, vars);
        _modalGame._raw.disabled_env_vars = [];
    }
    updateGameField(g.name, 'env_vars', vars);
    _modalGame.env_vars = vars;
}
