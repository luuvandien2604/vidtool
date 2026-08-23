// VideoTool Web UI Application Logic
(function () {
  'use strict';

  // Application State
  const state = {
    currentFixture: 'berlin_wall',
    status: null,
    scriptData: null,
    activeProposal: null,
    activeJobId: null,
    logOffset: 0,
    pollingTimer: null,
  };

  // DOM Elements
  const el = {
    episodeSelect: document.getElementById('episodeSelect'),
    btnRefresh: document.getElementById('btnRefresh'),
    
    // Status Ribbon
    valDuration: document.getElementById('valDuration'),
    valBeats: document.getElementById('valBeats'),
    valVideo: document.getElementById('valVideo'),
    valOverrides: document.getElementById('valOverrides'),
    valAudio: document.getElementById('valAudio'),
    overrideCount: document.getElementById('overrideCount'),
    overridesList: document.getElementById('overridesList'),

    // Pipeline Controls
    planMode: document.getElementById('planMode'),
    chkAiEditorial: document.getElementById('chkAiEditorial'),
    btnRunPlan: document.getElementById('btnRunPlan'),
    renderAudio: document.getElementById('renderAudio'),
    chkClickTrack: document.getElementById('chkClickTrack'),
    btnRunRender: document.getElementById('btnRunRender'),
    btnGenScript: document.getElementById('btnGenScript'),
    btnQuickRender: document.getElementById('btnQuickRender'),

    // Video Player & Beat Timeline
    mainVideo: document.getElementById('mainVideo'),
    videoPlaceholder: document.getElementById('videoPlaceholder'),
    beatTrack: document.getElementById('beatTrack'),
    currentTimeDisplay: document.getElementById('currentTimeDisplay'),
    activeBeatBadge: document.getElementById('activeBeatBadge'),
    infoBeatId: document.getElementById('infoBeatId'),
    infoFamily: document.getElementById('infoFamily'),
    infoTime: document.getElementById('infoTime'),
    infoNarration: document.getElementById('infoNarration'),

    // Tabs & Tables
    tabButtons: document.querySelectorAll('.nav-tab'),
    tabContents: document.querySelectorAll('.tab-pane'),
    scriptSearch: document.getElementById('scriptSearch'),
    filterBeatSelect: document.getElementById('filterBeatSelect'),
    scriptTableBody: document.getElementById('scriptTableBody'),
    jsonViewer: document.getElementById('jsonViewer'),
    mdViewer: document.getElementById('mdViewer'),

    // Revision Studio
    feedbackInput: document.getElementById('feedbackInput'),
    revisionProvider: document.getElementById('revisionProvider'),
    btnPropose: document.getElementById('btnPropose'),
    proposalBox: document.getElementById('proposalBox'),
    propId: document.getElementById('propId'),
    propStatusBadge: document.getElementById('propStatusBadge'),
    propOldVal: document.getElementById('propOldVal'),
    propNewVal: document.getElementById('propNewVal'),
    propBeat: document.getElementById('propBeat'),
    propTarget: document.getElementById('propTarget'),
    propRationale: document.getElementById('propRationale'),
    propRejectionBox: document.getElementById('propRejectionBox'),
    propRejection: document.getElementById('propRejection'),
    btnApplyProposal: document.getElementById('btnApplyProposal'),
    suggestionChips: document.querySelectorAll('.suggestion-chip'),

    // Terminal
    terminalLog: document.getElementById('terminalLog'),
    jobStatusPill: document.getElementById('jobStatusPill'),
    btnClearConsole: document.getElementById('btnClearConsole'),
  };

  // Helper: Format Seconds to M:SS.SS
  function formatTime(sec) {
    if (isNaN(sec) || sec === null) return '--:--';
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2);
    return `${m}:${s.padStart(5, '0')}`;
  }

  // ---------------------------------------------------------------------------
  // API Fetchers
  // ---------------------------------------------------------------------------

  async function loadEpisodes() {
    try {
      const res = await fetch('/api/episodes');
      const data = await res.json();
      el.episodeSelect.innerHTML = '';
      data.episodes.forEach(ep => {
        const opt = document.createElement('option');
        opt.value = ep.fixture_name;
        opt.textContent = `${ep.fixture_name} (${ep.title})`;
        if (ep.fixture_name === state.currentFixture) opt.selected = true;
        el.episodeSelect.appendChild(opt);
      });
    } catch (err) {
      logTerminal('Error loading episodes: ' + err, 'error');
    }
  }

  async function loadEpisodeStatus() {
    try {
      const res = await fetch(`/api/episodes/${state.currentFixture}/status`);
      if (!res.ok) throw new Error('Status fetch failed');
      const status = await res.json();
      state.status = status;
      renderStatus(status);
      renderOverrides();
    } catch (err) {
      logTerminal('Error loading status: ' + err, 'error');
    }
  }

  async function loadShootingScript() {
    try {
      const res = await fetch(`/api/episodes/${state.currentFixture}/shooting-script`);
      if (!res.ok) {
        el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Chưa có shooting script. Vui lòng bấm "Chạy Planning Pipeline" hoặc "Xuất JSON & Markdown".</td></tr>`;
        el.jsonViewer.textContent = '{}';
        el.mdViewer.textContent = 'Chưa có markdown.';
        return;
      }
      const data = await res.json();
      state.scriptData = data.script;
      renderBeatTimeline(data.script);
      renderShootingScriptTable(data.script);
      el.jsonViewer.textContent = JSON.stringify(data.script, null, 2);
      el.mdViewer.textContent = data.markdown || '';
    } catch (err) {
      logTerminal('Error loading shooting script: ' + err, 'error');
    }
  }

  async function loadOverrides() {
    try {
      const res = await fetch(`/api/episodes/${state.currentFixture}/overrides`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.overrides || [];
    } catch {
      return [];
    }
  }

  // ---------------------------------------------------------------------------
  // Renderers
  // ---------------------------------------------------------------------------

  function renderStatus(status) {
    el.valDuration.textContent = formatTime(status.total_duration_sec);
    el.valBeats.textContent = status.beat_count;
    el.valOverrides.textContent = status.overrides_count;
    el.overrideCount.textContent = status.overrides_count;

    if (status.has_video) {
      el.valVideo.textContent = `Sẵn sàng (${status.video_size_mb} MB)`;
      el.valVideo.className = 'pill-value badge-green';
      el.videoPlaceholder.classList.add('hidden');
      el.mainVideo.src = `/api/episodes/${state.currentFixture}/video`;
    } else {
      el.valVideo.textContent = 'Chưa render';
      el.valVideo.className = 'pill-value badge-neutral';
      el.videoPlaceholder.classList.remove('hidden');
      el.mainVideo.removeAttribute('src');
    }

    el.valAudio.textContent = status.has_audio ? 'Synthesized' : 'None';
  }

  async function renderOverrides() {
    const overrides = await loadOverrides();
    el.overridesList.innerHTML = '';
    if (!overrides.length) {
      el.overridesList.innerHTML = '<p class="empty-hint">Chưa có override nào được áp dụng.</p>';
      return;
    }

    overrides.forEach(ovr => {
      const item = document.createElement('div');
      item.className = 'override-item';
      item.innerHTML = `
        <div class="override-info">
          <span class="override-beat">${ovr.beat_id}: ${ovr.field}</span>
          <span class="override-val">"${ovr.new_value}"</span>
        </div>
        <button class="btn-icon btn-del-override" data-id="${ovr.override_id}" title="Xóa override">🗑️</button>
      `;
      el.overridesList.appendChild(item);
    });

    // Attach delete listeners
    document.querySelectorAll('.btn-del-override').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        await deleteOverride(id);
      });
    });
  }

  async function deleteOverride(overrideId) {
    try {
      const res = await fetch(`/api/episodes/${state.currentFixture}/overrides/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ override_id: overrideId }),
      });
      const data = await res.json();
      if (data.success) {
        logTerminal(`Deleted override ${overrideId}`, 'warn');
        await loadEpisodeStatus();
        await loadShootingScript();
      }
    } catch (err) {
      logTerminal('Error deleting override: ' + err, 'error');
    }
  }

  function renderBeatTimeline(script) {
    el.beatTrack.innerHTML = '';
    el.filterBeatSelect.innerHTML = '<option value="all">Tất cả các Beats</option>';

    if (!script || !script.beats || !script.beats.length) return;

    const totalDur = script.total_duration_sec || 1;

    script.beats.forEach((beat, idx) => {
      const pct = (beat.duration_sec / totalDur) * 100;
      const seg = document.createElement('div');
      seg.className = `beat-segment ${idx === 0 ? 'active' : ''}`;
      seg.style.width = `${pct}%`;
      seg.textContent = `B${idx + 1}`;
      seg.title = `${beat.beat_id} [${formatTime(beat.start_sec)} - ${formatTime(beat.end_sec)}]: ${beat.visual_family}`;
      seg.dataset.beatId = beat.beat_id;
      seg.dataset.startSec = beat.start_sec;
      seg.dataset.endSec = beat.end_sec;

      seg.addEventListener('click', () => {
        el.mainVideo.currentTime = beat.start_sec;
        el.mainVideo.play();
        updateActiveBeat(beat.beat_id);
      });

      el.beatTrack.appendChild(seg);

      // Add to filter dropdown
      const opt = document.createElement('option');
      opt.value = beat.beat_id;
      opt.textContent = `${beat.beat_id} (${beat.visual_family})`;
      el.filterBeatSelect.appendChild(opt);
    });

    if (script.beats.length > 0) {
      updateActiveBeat(script.beats[0].beat_id);
    }
  }

  function updateActiveBeat(beatId) {
    if (!state.scriptData) return;
    const beat = state.scriptData.beats.find(b => b.beat_id === beatId);
    if (!beat) return;

    el.activeBeatBadge.textContent = beat.beat_id.toUpperCase();
    el.infoBeatId.textContent = beat.beat_id;
    el.infoFamily.textContent = `${beat.visual_family} (${beat.strategy || 'default'})`;
    el.infoTime.textContent = `[${formatTime(beat.start_sec)} - ${formatTime(beat.end_sec)}] (${beat.duration_sec.toFixed(2)}s)`;
    el.infoNarration.textContent = `"${beat.narration_text}"`;

    // Highlight timeline segment
    document.querySelectorAll('.beat-segment').forEach(seg => {
      if (seg.dataset.beatId === beatId) {
        seg.classList.add('active');
      } else {
        seg.classList.remove('active');
      }
    });
  }

  function renderShootingScriptTable(script) {
    el.scriptTableBody.innerHTML = '';
    if (!script || !script.beats || !script.beats.length) {
      el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Chưa có elements nào.</td></tr>`;
      return;
    }

    const filterBeat = el.filterBeatSelect.value;
    const query = el.scriptSearch.value.toLowerCase().trim();

    let count = 0;
    script.beats.forEach(beat => {
      if (filterBeat !== 'all' && beat.beat_id !== filterBeat) return;

      beat.elements.forEach(elem => {
        // Query match
        const rowText = `${beat.beat_id} ${elem.element_id} ${elem.element_type} ${elem.display_content} ${elem.content_source} ${elem.asset_id || ''}`.toLowerCase();
        if (query && !rowText.includes(query)) return;

        count++;
        const tr = document.createElement('tr');
        
        let srcClass = 'source-raw';
        if (elem.content_source.includes('override')) srcClass = 'source-override';
        else if (elem.content_source.includes('ai')) srcClass = 'source-ai';

        tr.innerHTML = `
          <td>${elem.index}</td>
          <td><strong style="color:var(--vox-gold)">${beat.beat_id}</strong></td>
          <td><code>${elem.element_id}</code></td>
          <td>${elem.element_type}</td>
          <td><strong>${elem.display_content}</strong></td>
          <td><span class="source-pill ${srcClass}">${elem.content_source}</span></td>
          <td>${elem.asset_id || '—'}</td>
          <td>${elem.region || '—'}</td>
          <td><code>${elem.bounds_norm || '—'}</code></td>
          <td>${formatTime(elem.entrance_sec)}</td>
          <td>${formatTime(elem.exit_sec)}</td>
          <td>${elem.motion}</td>
          <td>${elem.semantic_reason || '—'}</td>
        `;
        el.scriptTableBody.appendChild(tr);
      });
    });

    if (count === 0) {
      el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Không tìm thấy elements phù hợp với bộ lọc.</td></tr>`;
    }
  }

  // ---------------------------------------------------------------------------
  // Video Player Time Sync
  // ---------------------------------------------------------------------------

  el.mainVideo.addEventListener('timeupdate', () => {
    const cur = el.mainVideo.currentTime;
    const dur = el.mainVideo.duration || (state.status ? state.status.total_duration_sec : 0);
    el.currentTimeDisplay.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;

    if (!state.scriptData) return;
    const currentBeat = state.scriptData.beats.find(b => cur >= b.start_sec && cur < b.end_sec);
    if (currentBeat && el.infoBeatId.textContent !== currentBeat.beat_id) {
      updateActiveBeat(currentBeat.beat_id);
    }
  });

  // ---------------------------------------------------------------------------
  // Revision Studio (Propose & Apply)
  // ---------------------------------------------------------------------------

  el.suggestionChips.forEach(chip => {
    chip.addEventListener('click', () => {
      el.feedbackInput.value = chip.getAttribute('data-text');
    });
  });

  el.btnPropose.addEventListener('click', async () => {
    const text = el.feedbackInput.value.trim();
    if (!text) {
      alert('Vui lòng nhập feedback string.');
      return;
    }

    el.btnPropose.disabled = true;
    el.btnPropose.textContent = 'Đang xử lý...';

    try {
      const res = await fetch('/api/revise/propose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fixture: state.currentFixture,
          feedback_text: text,
          provider: el.revisionProvider.value,
        }),
      });

      const proposal = await res.json();
      state.activeProposal = proposal;
      renderProposal(proposal);
    } catch (err) {
      logTerminal('Revision error: ' + err, 'error');
    } finally {
      el.btnPropose.disabled = false;
      el.btnPropose.textContent = '🔍 Propose Revision';
    }
  });

  function renderProposal(prop) {
    el.proposalBox.classList.remove('hidden');
    el.propId.textContent = prop.proposal_id;
    
    if (prop.is_valid) {
      el.propStatusBadge.textContent = 'VALID (Grounded)';
      el.propStatusBadge.className = 'badge badge-green';
      el.btnApplyProposal.disabled = false;
      el.btnApplyProposal.style.display = 'block';
      el.propRejectionBox.classList.add('hidden');
    } else {
      el.propStatusBadge.textContent = 'REJECTED';
      el.propStatusBadge.className = 'badge badge-coral';
      el.btnApplyProposal.disabled = true;
      el.btnApplyProposal.style.display = 'none';
      el.propRejectionBox.classList.remove('hidden');
      el.propRejection.textContent = prop.rejection_reason || 'Rejection reason unknown';
    }

    el.propOldVal.textContent = prop.old_value || '(none)';
    el.propNewVal.textContent = prop.new_value || '(none)';
    el.propBeat.textContent = prop.beat_id || '(none)';
    el.propTarget.textContent = prop.target_id || '(none)';
    el.propRationale.textContent = prop.reason || '(none)';
  }

  el.btnApplyProposal.addEventListener('click', async () => {
    if (!state.activeProposal || !state.activeProposal.proposal_id) return;

    el.btnApplyProposal.disabled = true;
    el.btnApplyProposal.textContent = 'Đang lưu override...';

    try {
      const res = await fetch('/api/revise/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fixture: state.currentFixture,
          proposal_id: state.activeProposal.proposal_id,
        }),
      });

      const data = await res.json();
      if (data.success) {
        logTerminal(`Applied revision ${state.activeProposal.proposal_id} -> Override committed!`, 'success');
        el.proposalBox.classList.add('hidden');
        el.feedbackInput.value = '';
        state.activeProposal = null;

        await loadEpisodeStatus();
        await loadShootingScript();
      }
    } catch (err) {
      logTerminal('Apply error: ' + err, 'error');
    } finally {
      el.btnApplyProposal.disabled = false;
      el.btnApplyProposal.textContent = '✅ 1-Click Apply & Lưu Override';
    }
  });

  // ---------------------------------------------------------------------------
  // Pipeline Commands Execution & Log Stream
  // ---------------------------------------------------------------------------

  async function executeCommand(commandType, options = {}) {
    try {
      el.jobStatusPill.textContent = 'Đang chạy...';
      el.jobStatusPill.className = 'badge badge-gold';

      const res = await fetch('/api/commands/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: commandType,
          fixture: state.currentFixture,
          options: options,
        }),
      });

      const data = await res.json();
      if (data.job_id) {
        state.activeJobId = data.job_id;
        state.logOffset = 0;
        startLogPolling(data.job_id);
      }
    } catch (err) {
      logTerminal('Execution request failed: ' + err, 'error');
    }
  }

  function startLogPolling(jobId) {
    if (state.pollingTimer) clearInterval(state.pollingTimer);

    state.pollingTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/commands/jobs/${jobId}?offset=${state.logOffset}`);
        if (!res.ok) return;
        const job = await res.json();

        if (job.lines && job.lines.length) {
          job.lines.forEach(line => {
            let type = 'info';
            if (line.startsWith('$')) type = 'cmd';
            else if (line.toLowerCase().includes('error') || line.toLowerCase().includes('failed')) type = 'error';
            else if (line.toLowerCase().includes('rendered') || line.toLowerCase().includes('passed') || line.toLowerCase().includes('generated')) type = 'success';
            else if (line.toLowerCase().includes('warn')) type = 'warn';

            logTerminal(line, type);
          });
          state.logOffset = job.next_offset;
        }

        if (job.status === 'completed') {
          clearInterval(state.pollingTimer);
          el.jobStatusPill.textContent = `Hoàn tất (${job.elapsed_sec}s)`;
          el.jobStatusPill.className = 'badge badge-green';
          logTerminal(`✓ Task finished successfully in ${job.elapsed_sec}s`, 'success');
          // Refresh state
          await loadEpisodeStatus();
          await loadShootingScript();
        } else if (job.status === 'failed') {
          clearInterval(state.pollingTimer);
          el.jobStatusPill.textContent = `Thất bại (exit ${job.exit_code})`;
          el.jobStatusPill.className = 'badge badge-coral';
          logTerminal(`✗ Task failed with exit code ${job.exit_code}`, 'error');
        }
      } catch (err) {
        clearInterval(state.pollingTimer);
      }
    }, 600);
  }

  function logTerminal(text, type = 'info') {
    const line = document.createElement('div');
    line.className = `term-line term-${type}`;
    line.textContent = text;
    el.terminalLog.appendChild(line);
    el.terminalLog.scrollTop = el.terminalLog.scrollHeight;
  }

  el.btnClearConsole.addEventListener('click', () => {
    el.terminalLog.innerHTML = '<div class="term-line term-system">Console cleared.</div>';
  });

  // Action Button Listeners
  el.btnRunPlan.addEventListener('click', () => {
    executeCommand('plan', {
      mode: el.planMode.value,
      editorial_ai_enabled: el.chkAiEditorial.checked,
    });
  });

  el.btnRunRender.addEventListener('click', () => {
    executeCommand('render', {
      audio_provider: el.renderAudio.value,
      click_track: el.chkClickTrack.checked,
      no_audio: el.renderAudio.value === 'none',
    });
  });

  el.btnGenScript.addEventListener('click', () => {
    executeCommand('shooting-script');
  });

  el.btnQuickRender.addEventListener('click', () => {
    executeCommand('render', { audio_provider: 'silence' });
  });

  // Episode Change
  el.episodeSelect.addEventListener('change', async () => {
    state.currentFixture = el.episodeSelect.value;
    await loadEpisodeStatus();
    await loadShootingScript();
  });

  el.btnRefresh.addEventListener('click', async () => {
    await loadEpisodeStatus();
    await loadShootingScript();
    logTerminal('Refreshed episode status and scripts', 'system');
  });

  // Filter & Search
  el.filterBeatSelect.addEventListener('change', () => {
    if (state.scriptData) renderShootingScriptTable(state.scriptData);
  });
  el.scriptSearch.addEventListener('input', () => {
    if (state.scriptData) renderShootingScriptTable(state.scriptData);
  });

  // Tab Switching
  el.tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      el.tabButtons.forEach(b => b.classList.remove('active'));
      el.tabContents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.getAttribute('data-tab'));
      if (target) target.classList.add('active');
    });
  });

  // ---------------------------------------------------------------------------
  // Initialization
  // ---------------------------------------------------------------------------
  async function init() {
    await loadEpisodes();
    await loadEpisodeStatus();
    await loadShootingScript();
  }

  init();
})();
