const STATE = {
    series: [],
    episodes: [],
    currentSeries: null,
    currentEpisodeId: null,
    audioTrack: null,
    subTrack: null,
    isPlaying: false,
    duration: 0,
    settings: {
        alwaysZero: localStorage.getItem('alwaysZero') === 'true',
        disableSync: localStorage.getItem('disableSync') === 'true'
    }
};

// DOM Elements
const seriesGrid = document.getElementById('seriesGrid');
const episodeModal = document.getElementById('episodeModal');
const episodeList = document.getElementById('episodeList');
const tabContainer = document.getElementById('tabContainer');
const playerOverlay = document.getElementById('playerOverlay');
const mainVideo = document.getElementById('mainVideo');
const searchInput = document.getElementById('seriesSearch');
const trackSelectorBtn = document.getElementById('trackSelectorBtn');
const trackMenu = document.getElementById('trackMenu');
const audioTrackList = document.getElementById('audioTrackList');
const subTrackList = document.getElementById('subTrackList');
const playPauseBtn = document.getElementById('playPauseBtn');
const progressBar = document.getElementById('progressBar');
const timeDisplay = document.getElementById('timeDisplay');
const videoLoader = document.getElementById('videoLoader');

// New UI Elements
const upNextPopup = document.getElementById('upNextPopup');
const upNextTitle = document.getElementById('upNextTitle');
const upNextPlayBtn = document.getElementById('upNextPlayBtn');
const upNextConfigBtn = document.getElementById('upNextConfigBtn');
const upNextDismissBtn = document.getElementById('upNextDismissBtn');
const nerdStats = document.getElementById('nerdStats');
const statsContent = document.getElementById('statsContent');
const closeStatsBtn = document.getElementById('closeStatsBtn');
const nerdStatsBtn = document.getElementById('nerdStatsBtn');
const nextEpBtn = document.getElementById('nextEpBtn');

async function init() {
    await fetchSeries();
    setupEventListeners();
}

async function fetchSeries() {
    try {
        const response = await fetch('/api/series');
        STATE.series = await response.json();
        renderSeries(STATE.series);
    } catch (err) { console.error(err); }
}

function renderSeries(list) {
    seriesGrid.innerHTML = '';
    list.forEach(series => {
        const card = document.createElement('div');
        card.className = 'series-card';
        card.onclick = () => openSeries(series);
        const posterUrl = series.thumbnail_path ? `/api/posters?path=${encodeURIComponent(series.thumbnail_path)}` : 'https://via.placeholder.com/200x300?text=No+Poster';
        card.innerHTML = `<div class="card-img"><img src="${posterUrl}"></div><div class="card-info"><h4>${series.name}</h4></div>`;
        seriesGrid.appendChild(card);
    });
}

async function openSeries(series) {
    STATE.currentSeries = series;
    document.getElementById('modalSeriesTitle').innerText = series.name;
    const response = await fetch(`/api/series/${series.id}/episodes`);
    STATE.episodes = await response.json();
    renderEpisodesTabbed(STATE.episodes);
    episodeModal.classList.remove('hidden');
}

function renderEpisodesTabbed(episodes) {
    const groups = {};
    episodes.forEach(ep => {
        const folder = ep.folder_name || 'Main';
        if (!groups[folder]) groups[folder] = [];
        groups[folder].push(ep);
    });
    const folders = Object.keys(groups).sort((a,b) => (a === 'Main' ? -1 : a.localeCompare(b)));
    tabContainer.innerHTML = '';
    if (folders.length > 1) {
        folders.forEach((folder, idx) => {
            const tab = document.createElement('div');
            tab.className = `tab ${idx === 0 ? 'active' : ''}`;
            tab.innerText = folder;
            tab.onclick = () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                renderEpisodeList(groups[folder]);
            };
            tabContainer.appendChild(tab);
        });
    }
    renderEpisodeList(groups[folders[0]]);
}

const prePlayModal = document.getElementById('prePlayModal');
const prePlayAudioList = document.getElementById('prePlayAudioList');
const prePlaySubList = document.getElementById('prePlaySubList');
const prePlayStartBtn = document.getElementById('prePlayStartBtn');

function renderEpisodeList(list) {
    episodeList.innerHTML = '';
    list.forEach(ep => {
        const item = document.createElement('div');
        item.className = 'episode-item';
        const label = (ep.season_number ? `S${ep.season_number.toString().padStart(2, '0')}` : '') + 
                      (ep.episode_number ? `E${ep.episode_number.toString().padStart(2, '0')}` : '') + 
                      ` - ${ep.filename}`;
        
        const progress = ep.progress ? (ep.progress.timestamp / ep.progress.duration * 100) : 0;
        const durLabel = ep.progress ? formatTime(ep.progress.duration) : '';

        item.innerHTML = `
            <div class="ep-info">
                <h4>${label}</h4>
                <div class="ep-meta">
                    <span class="text-dim">${durLabel}</span>
                    <div class="progress-track"><div class="progress-fill" style="width: ${progress}%"></div></div>
                </div>
            </div>
            <div class="ep-actions">
                <button class="btn-icon-small" onclick="showPrePlay(${ep.id}, '${label.replace(/'/g, "\\'")}')" title="Configure Tracks">
                    <span class="material-symbols-rounded">tune</span>
                </button>
                <button class="btn-primary" onclick="startPlayback(${ep.id}, '${label.replace(/'/g, "\\'")}')">
                    <span class="material-symbols-rounded">play_arrow</span> Play
                </button>
            </div>
        `;
        episodeList.appendChild(item);
    });
}

async function showPrePlay(episodeId, label) {
    STATE.currentEpisodeId = episodeId;
    STATE.audioTrack = null;
    STATE.subTrack = null;
    document.getElementById('prePlaySubtitle').innerText = label;
    
    const res = await fetch(`/api/episodes/${episodeId}/tracks`);
    const data = await res.json();
    STATE.duration = data.duration;
    
    renderPrePlayTracks(data.tracks);
    prePlayModal.classList.remove('hidden');
    
    prePlayStartBtn.onclick = () => {
        prePlayModal.classList.add('hidden');
        startPlayback(episodeId, label, false); // false = don't reset tracks
    };
}

function renderPrePlayTracks(tracks) {
    prePlayAudioList.innerHTML = '';
    prePlaySubList.innerHTML = '';
    
    tracks.forEach(t => {
        const item = document.createElement('div');
        item.className = 'track-item';
        item.innerText = `${t.title} (${t.language})`;
        
        if (t.type === 'audio') {
            item.onclick = () => {
                prePlayAudioList.querySelectorAll('.track-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                STATE.audioTrack = t.index;
            };
            if (STATE.audioTrack === t.index || (STATE.audioTrack === null && t.index === tracks.find(at => at.type === 'audio')?.index)) {
                item.classList.add('active');
                STATE.audioTrack = t.index;
            }
            prePlayAudioList.appendChild(item);
        } else if (t.type === 'subtitle') {
            item.onclick = () => {
                prePlaySubList.querySelectorAll('.track-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                STATE.subTrack = t.sub_index;
            };
            prePlaySubList.appendChild(item);
        }
    });

    const noneSub = document.createElement('div');
    noneSub.className = `track-item ${STATE.subTrack === null ? 'active' : ''}`;
    noneSub.innerText = 'None';
    noneSub.onclick = () => {
        prePlaySubList.querySelectorAll('.track-item').forEach(i => i.classList.remove('active'));
        noneSub.classList.add('active');
        STATE.subTrack = null;
    };
    prePlaySubList.prepend(noneSub);
}

async function startPlayback(episodeId, label, resetTracks = true) {
    const prevAudioLang = STATE.lastAudioLang;
    const prevSubIndex = STATE.lastSubIndex;
    
    STATE.currentEpisodeId = episodeId;
    document.getElementById('playerSubtitle').innerText = label;
    upNextPopup.classList.add('hidden');
    
    const res = await fetch(`/api/episodes/${episodeId}/tracks`);
    const data = await res.json();
    STATE.duration = data.duration;
    
    // Auto-match tracks if possible
    if (resetTracks && !STATE.settings.alwaysZero) {
        STATE.audioTrack = null;
        STATE.subTrack = null;
        
        if (prevAudioLang) {
            const match = data.tracks.find(t => t.type === 'audio' && t.language === prevAudioLang);
            if (match) STATE.audioTrack = match.index;
        }
        if (prevSubIndex !== undefined) {
             const subMatch = data.tracks.find(t => t.type === 'subtitle' && t.sub_index === prevSubIndex);
             if (subMatch) STATE.subTrack = subMatch.sub_index;
        }
    }
    
    renderTrackMenu(data.tracks);

    const ep = STATE.episodes.find(e => e.id === episodeId);
    let startTime = 0;
    
    if (!STATE.settings.alwaysZero && ep && ep.progress && !ep.progress.completed) {
        startTime = ep.progress.timestamp;
    }
    
    updateStream(startTime);
    playerOverlay.classList.remove('hidden');
}

function updateStream(startTime = null) {
    if (startTime === null) startTime = mainVideo.currentTime;
    
    let url = `/api/transcode/${STATE.currentEpisodeId}?start_time=${startTime}`;
    if (STATE.audioTrack !== null) url += `&audio_track=${STATE.audioTrack}`;
    if (STATE.subTrack !== null) url += `&sub_track=${STATE.subTrack}`;
    
    videoLoader.classList.remove('hidden');
    console.log(`Streaming from: ${startTime}s`);
    
    // Reset video state
    mainVideo.pause();
    mainVideo.src = url;
    mainVideo.load();
    mainVideo.play().catch(e => console.log("Playback interrupted"));
}

function renderTrackMenu(tracks) {
    audioTrackList.innerHTML = '';
    subTrackList.innerHTML = '';
    
    tracks.forEach(t => {
        const item = document.createElement('div');
        item.className = 'track-item';
        item.innerText = `${t.title} (${t.language})`;
        
        if (t.type === 'audio') {
            if (STATE.audioTrack === t.index) item.classList.add('active');
            item.onclick = () => { STATE.audioTrack = t.index; updateTrackSelection('audio'); };
            audioTrackList.appendChild(item);
        } else if (t.type === 'subtitle') {
            if (STATE.subTrack === t.sub_index) item.classList.add('active');
            item.onclick = () => { STATE.subTrack = t.sub_index; updateTrackSelection('sub'); };
            subTrackList.appendChild(item);
        }
    });

    // Add "None" for subtitles
    const noneSub = document.createElement('div');
    noneSub.className = `track-item ${STATE.subTrack === null ? 'active' : ''}`;
    noneSub.innerText = 'None';
    noneSub.onclick = () => { STATE.subTrack = null; updateTrackSelection('sub'); };
    subTrackList.prepend(noneSub);
}

function updateTrackSelection(type) {
    // Store preferences for next ep
    fetch(`/api/episodes/${STATE.currentEpisodeId}/tracks`)
        .then(res => res.json())
        .then(data => {
            renderTrackMenu(data.tracks);
            
            const audioTrack = data.tracks.find(t => t.index === STATE.audioTrack);
            if (audioTrack) STATE.lastAudioLang = audioTrack.language;
            
            STATE.lastSubIndex = STATE.subTrack;
        });
    
    updateStream();
}
function setupEventListeners() {
    const fullscreenBtn = document.getElementById('fullscreenBtn');

    trackSelectorBtn.onclick = (e) => { e.stopPropagation(); trackMenu.classList.toggle('hidden'); };
    document.querySelector('.close-modal').onclick = () => episodeModal.classList.add('hidden');
    document.querySelector('.close-preplay').onclick = () => prePlayModal.classList.add('hidden');
    document.querySelector('.close-player').onclick = () => { mainVideo.pause(); playerOverlay.classList.add('hidden'); };

    playPauseBtn.onclick = () => {
        if (mainVideo.paused) { mainVideo.play(); }
        else { mainVideo.pause(); }
    };

    fullscreenBtn.onclick = () => {
        if (!document.fullscreenElement) {
            playerOverlay.requestFullscreen().catch(err => console.error(err));
        } else {
            document.exitFullscreen();
        }
    };

    // Auto-hide Controls Logic
    let controlsTimeout;
    const showUI = () => {
        playerOverlay.classList.remove('hide-ui', 'hide-cursor');
        clearTimeout(controlsTimeout);
        if (!mainVideo.paused) {
            controlsTimeout = setTimeout(() => {
                if (!trackMenu.classList.contains('hidden')) return;
                playerOverlay.classList.add('hide-ui', 'hide-cursor');
            }, 3000);
        }
    };

    playerOverlay.onmousemove = showUI;
    playerOverlay.onclick = showUI;
    mainVideo.onplay = () => { 
        showUI(); 
        playPauseBtn.querySelector('.material-symbols-rounded').innerText = 'pause';
    };
    mainVideo.onpause = () => { 
        showUI(); 
        playPauseBtn.querySelector('.material-symbols-rounded').innerText = 'play_arrow';
    };

    mainVideo.onplaying = () => { 
        videoLoader.classList.add('hidden'); 
        playPauseBtn.querySelector('.material-symbols-rounded').innerText = 'pause';
        updateNerdStats();
    };
    
    mainVideo.onpause = () => { 
        showUI(); 
        playPauseBtn.querySelector('.material-symbols-rounded').innerText = 'play_arrow';
        updateNerdStats();
    };

    // Nerd Stats Logic
    
    closeStatsBtn.onclick = () => nerdStats.classList.add('hidden');

    function updateNerdStats() {
        if (nerdStats.classList.contains('hidden')) return;
        
        const video = mainVideo;
        const buffered = video.buffered.length > 0 ? (video.buffered.end(0) - video.currentTime).toFixed(2) + 's' : '0s';
        
        // Find current tracks from STATE
        const currentEp = STATE.episodes.find(e => e.id === STATE.currentEpisodeId);
        
        statsContent.innerHTML = `
            <div>Video ID</div><div>${STATE.currentEpisodeId}</div>
            <div>Resolution</div><div>${video.videoWidth} x ${video.videoHeight}</div>
            <div>Source Path</div><div>${currentEp?.path || 'N/A'}</div>
            <div>Buffer Health</div><div>${buffered}</div>
            <div>Codec (Browser)</div><div>H.264 / AAC (Transcoded)</div>
            <div>MIME Type</div><div>video/mp4</div>
            <div>State</div><div>${video.paused ? 'Paused' : 'Playing'}</div>
        `;
        
        if (!nerdStats.classList.contains('hidden')) {
            requestAnimationFrame(updateNerdStats);
        }
    }

    // Toggle Stats (N for Nerds)
    nerdStatsBtn.onclick = () => {
        nerdStats.classList.toggle('hidden');
        if (!nerdStats.classList.contains('hidden')) updateNerdStats();
    };

    window.onkeydown = (e) => {
        // Only trigger if not typing in search
        if (e.target.tagName === 'INPUT') return;

        if (e.key.toLowerCase() === 'n') {
            e.preventDefault();
            nerdStats.classList.toggle('hidden');
            if (!nerdStats.classList.contains('hidden')) updateNerdStats();
        }
    };
    mainVideo.onwaiting = () => { videoLoader.classList.remove('hidden'); };
    
    mainVideo.ontimeupdate = () => {
        const curr = mainVideo.currentTime;
        const dur = STATE.duration || mainVideo.duration || 0;
        if (!isSeeking) {
            progressBar.value = (curr / dur) * 100 || 0;
        }
        timeDisplay.innerText = formatTime(curr) + ' / ' + formatTime(dur);
        if (curr > 0 && curr % 10 < 0.2) syncProgress(curr, dur);

        // Up Next Logic (30s remaining) 
        // might not work xddd
        if (dur > 0 && (dur - curr) < 30 && (dur - curr) > 5) {
            showUpNext();
        } else if ((dur - curr) <= 5) {
            upNextPopup.classList.add('hidden');
        }
    };

    let isSeeking = false;
    progressBar.onmousedown = () => isSeeking = true;
    progressBar.onmouseup = () => isSeeking = false;
    progressBar.onchange = () => {
        const time = (progressBar.value / 100) * (STATE.duration || mainVideo.duration || 0);
        updateStream(time);
    };

    const upNextPopup = document.getElementById('upNextPopup');
    const upNextTitle = document.getElementById('upNextTitle');
    const upNextPlayBtn = document.getElementById('upNextPlayBtn');
    const upNextConfigBtn = document.getElementById('upNextConfigBtn');
    const upNextDismissBtn = document.getElementById('upNextDismissBtn');

    const nextEpBtn = document.getElementById('nextEpBtn');
    nextEpBtn.onclick = () => showUpNext(true);

    function showUpNext(force = false) {
        if (!upNextPopup.classList.contains('hidden') && !force) return;
        if (STATE.upNextDismissed === STATE.currentEpisodeId && !force) return;
        
        const currentIdx = STATE.episodes.findIndex(e => e.id === STATE.currentEpisodeId);
        const nextEp = STATE.episodes[currentIdx + 1];
        
        if (!nextEp) return;
        
        const label = (nextEp.season_number ? `S${nextEp.season_number.toString().padStart(2, '0')}` : '') + 
                      (nextEp.episode_number ? `E${nextEp.episode_number.toString().padStart(2, '0')}` : '') + 
                      ` - ${nextEp.filename}`;
        
        upNextTitle.innerText = label;
        upNextPopup.classList.remove('hidden');
        
        upNextPlayBtn.onclick = () => {
            upNextPopup.classList.add('hidden');
            startPlayback(nextEp.id, label, false); // Auto-play with same tracks
        };
        
        upNextConfigBtn.onclick = () => {
            upNextPopup.classList.add('hidden');
            playerOverlay.classList.add('hidden');
            mainVideo.pause();
            showPrePlay(nextEp.id, label);
        };
        
        upNextDismissBtn.onclick = () => {
            upNextPopup.classList.add('hidden');
            // Don't show again for this ep
            STATE.upNextDismissed = STATE.currentEpisodeId;
        };
    }

    searchInput.oninput = (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = STATE.series.filter(s => s.name.toLowerCase().includes(query));
        renderSeries(filtered);
    };
    
    const settingAlwaysZero = document.getElementById('settingAlwaysZero');
    const settingDisableSync = document.getElementById('settingDisableSync');
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');

    // Init settings UI
    settingAlwaysZero.checked = STATE.settings.alwaysZero;
    settingAlwaysZero.onchange = (e) => {
        STATE.settings.alwaysZero = e.target.checked;
        localStorage.setItem('alwaysZero', e.target.checked);
    };

    settingDisableSync.checked = STATE.settings.disableSync;
    settingDisableSync.onchange = (e) => {
        STATE.settings.disableSync = e.target.checked;
        localStorage.setItem('disableSync', e.target.checked);
    };

    settingsBtn.onclick = () => settingsModal.classList.remove('hidden');
    document.querySelector('.close-settings').onclick = () => settingsModal.classList.add('hidden');

    window.onclick = (e) => {
        if (e.target === episodeModal) episodeModal.classList.add('hidden');
        if (e.target === prePlayModal) prePlayModal.classList.add('hidden');
        if (e.target === settingsModal) settingsModal.classList.add('hidden');
        if (!trackMenu.contains(e.target) && e.target !== trackSelectorBtn) {
            trackMenu.classList.add('hidden');
        }
    };
}

function formatTime(s) {
    if (isNaN(s) || s === null || s === undefined) return "00:00";
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

async function syncProgress(curr, dur) {
    if (!STATE.currentEpisodeId || STATE.settings.disableSync) return;
    fetch('/api/progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ episode_id: STATE.currentEpisodeId, timestamp: curr, duration: dur })
    });
}

init();
