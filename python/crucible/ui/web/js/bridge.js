/* bridge.js — QWebChannel initialization and promisified wrapper */
'use strict';

let bridge = null;
const _ready = [];

function onBridgeReady(fn) {
    if (bridge) fn(bridge);
    else _ready.push(fn);
}

function call(method) {
    const args = Array.prototype.slice.call(arguments, 1);
    return new Promise(function(resolve) {
        args.push(resolve);
        bridge[method].apply(bridge, args);
    });
}

new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;

    // Wire up signals
    bridge.gamesChanged.connect(function() {
        if (typeof refreshLibrary === 'function') refreshLibrary();
    });
    bridge.protonChanged.connect(function() {
        if (typeof refreshRunners === 'function') refreshRunners();
    });
    bridge.toastRequested.connect(function(msg, level) {
        if (typeof showToast === 'function') showToast(msg, level);
    });
    bridge.themeColorsChanged.connect(function() {
        if (typeof applyTheme === 'function') applyTheme();
    });
    bridge.portraitUpdated.connect(function(exePath) {
        if (typeof onPortraitUpdated === 'function') onPortraitUpdated(exePath);
    });
    bridge.heroUpdated.connect(function(exePath) {
        if (typeof onHeroUpdated === 'function') onHeroUpdated(exePath);
    });
    bridge.downloadProgress.connect(function(data) {
        if (typeof onDownloadProgress === 'function') onDownloadProgress(data);
    });
    bridge.gameRunningChanged.connect(function(name, running) {
        if (!running && typeof refreshLibrary === 'function') refreshLibrary();
        if (!running && typeof _modalGame !== 'undefined' && _modalGame && _modalGame.name === name) {
            call('getGame', name).then(function(game) {
                if (!game || !game.name) return;
                _modalGame = game;
                if (typeof renderModal === 'function') renderModal();
            });
        }
        if (typeof onGameRunningChanged === 'function') onGameRunningChanged(name, running);
    });

    _ready.forEach(function(fn) { fn(bridge); });
    _ready.length = 0;
});
