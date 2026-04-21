/* library.js — Library grid rendering */
'use strict';

var _pendingGameCards = Object.create(null);

function refreshLibrary() {
    call('getGames').then(function(games) {
        var grid = document.getElementById('library-grid');
        grid.innerHTML = '';
        games.forEach(function(game) {
            var cardGame = _pendingGameCards[game.exe_path]
                ? Object.assign({}, game, { pendingArtwork: true })
                : game;
            grid.appendChild(createGameCard(cardGame));
        });
        grid.appendChild(createAddCard());
    });
}

function createGameCard(game) {
    var card = document.createElement('div');
    card.className = 'game-card';
    card.dataset.name = game.name;
    card.dataset.exe = game.exe_path;
    if (game.pendingArtwork) card.classList.add('pending-artwork');

    var img = document.createElement('img');
    img.alt = game.name;
    img.src = '';
    img.hidden = true;
    card.appendChild(img);

    if (game.pendingArtwork) {
        card.appendChild(createGameCardOverlay());
    }

    // Load portrait artwork for card (falls back to header)
    call('getPortraitArtworkPath', game.exe_path).then(function(path) {
        if (path) {
            img.src = 'file://' + path;
            img.hidden = false;
            clearPendingCardState(card);
        } else {
            img.removeAttribute('src');
            img.hidden = true;
        }
    });

    card.addEventListener('click', function() { openGameModal(game.name); });
    return card;
}

function createGameCardOverlay() {
    var overlay = document.createElement('div');
    overlay.className = 'game-card-overlay';
    overlay.innerHTML =
        '<div class="game-card-spinner" aria-hidden="true"></div>' +
        '<span>Fetching artwork...</span>';
    return overlay;
}

function clearPendingCardState(card) {
    if (!card) return;
    card.classList.remove('pending-artwork');
    var overlay = card.querySelector('.game-card-overlay');
    if (overlay) overlay.remove();
    var img = card.querySelector('img');
    if (img && img.getAttribute('src')) img.hidden = false;
}

function insertPendingGameCard(game) {
    if (!game || !game.exe_path) return;
    if (_pendingGameCards[game.exe_path]) return;
    var grid = document.getElementById('library-grid');
    if (!grid) return;
    var addCard = grid.querySelector('.add-game-card');
    var pendingGame = Object.assign({}, game, { pendingArtwork: true });
    var card = createGameCard(pendingGame);
    _pendingGameCards[game.exe_path] = true;
    if (addCard) grid.insertBefore(card, addCard);
    else grid.appendChild(card);
}

function createAddCard() {
    var card = document.createElement('div');
    card.className = 'add-game-card';
    card.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>' +
        '<span>Add Game</span>';
    card.addEventListener('click', function() {
        call('openFileDialog').then(function(path) {
            if (path) {
                call('addGame', path).then(function(result) {
                    if (result.success) {
                        if (result.game) insertPendingGameCard(result.game);
                        showToast('Added ' + (result.game ? result.game.name : 'game'), 'success');
                    } else {
                        showToast(result.error || 'Failed to add game', 'error');
                    }
                });
            }
        });
    });
    return card;
}

function onPortraitUpdated(exePath) {
    call('getPortraitArtworkPath', exePath).then(function(path) {
        if (!path) return;
        var cards = document.querySelectorAll('.game-card[data-exe="' + CSS.escape(exePath) + '"]');
        cards.forEach(function(card) {
            var img = card.querySelector('img');
            if (img) {
                img.src = 'file://' + path + '?t=' + Date.now();
                img.hidden = false;
            }
            clearPendingCardState(card);
        });
        delete _pendingGameCards[exePath];
    });
}

function onHeroUpdated(exePath) {
    if (!_modalGame || _modalGame.exe_path !== exePath) return;
    // Update hero banner
    call('getHeroArtworkPath', exePath).then(function(path) {
        if (!path) return;
        var img = document.getElementById('hero-banner-img');
        if (img) {
            img.src = 'file://' + path + '?t=' + Date.now();
        }
    });
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatPlaytime(seconds) {
    if (!seconds || seconds < 60) return 'Never played';
    var hours = Math.floor(seconds / 3600);
    var mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return hours + 'h ' + mins + 'm';
    return mins + 'm';
}

function formatLastPlayed(dateStr) {
    if (!dateStr) return 'Never';
    var date = new Date(dateStr);
    var now = new Date();
    var diff = Math.floor((now - date) / 86400000);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Yesterday';
    if (diff < 7) return diff + ' days ago';
    if (diff < 30) return Math.floor(diff / 7) + ' weeks ago';
    return date.toLocaleDateString();
}
