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

  // DOM Elements Map
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
    btnClearConsole: document.getElementById('btnClearConsole'),
    jobStatusPill: document.getElementById('jobStatusPill'),
    navJobBadge: document.getElementById('navJobBadge'),

    // New Project Modal
    btnNewProject: document.getElementById('btnNewProject'),
    modalNewProject: document.getElementById('modalNewProject'),
    btnCloseModal: document.getElementById('btnCloseModal'),
    btnCancelModal: document.getElementById('btnCancelModal'),
    formNewProject: document.getElementById('formNewProject'),
    inputTopic: document.getElementById('inputTopic'),
    lblScriptAi: document.getElementById('lblScriptAi'),
    lblScriptCustom: document.getElementById('lblScriptCustom'),
    customScriptBox: document.getElementById('customScriptBox'),
    textareaScript: document.getElementById('textareaScript'),
    selectMediaProvider: document.getElementById('selectMediaProvider'),
    selectAudioProvider: document.getElementById('selectAudioProvider'),
    selectAiProvider: document.getElementById('selectAiProvider'),
    selectAiModel: document.getElementById('selectAiModel'),
    groupAiModel: document.getElementById('groupAiModel'),
    selectVoice: document.getElementById('selectVoice'),
    checkAutoRender: document.getElementById('checkAutoRender'),
  };

  // Helper: Format Seconds to M:SS.SS
  function formatTime(sec) {
    if (isNaN(sec) || sec === null || sec === undefined) return '0:00.00';
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2);
    return `${m}:${s.padStart(5, '0')}`;
  }

  // ---------------------------------------------------------------------------
  // Tab Switching
  // ---------------------------------------------------------------------------
  function switchToTab(tabId) {
    el.tabButtons.forEach(b => {
      if (b.getAttribute('data-tab') === tabId) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });
    el.tabContents.forEach(c => {
      if (c.id === tabId) {
        c.classList.add('active');
      } else {
        c.classList.remove('active');
      }
    });
  }

  el.tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      switchToTab(targetId);
    });
  });

  // ---------------------------------------------------------------------------
  // Modal: Tạo Dự Án Mới (New Project Topic)
  // ---------------------------------------------------------------------------
  function slugify(text) {
    return text
      .toString()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9 ]/g, '')
      .replace(/\s+/g, '_')
      .slice(0, 40);
  }

  function openNewProjectModal() {
    if (el.inputTopic) el.inputTopic.value = '';
    if (el.textareaScript) el.textareaScript.value = '';
    if (el.customScriptBox) {
      el.customScriptBox.classList.add('hidden');
      el.customScriptBox.style.display = 'none';
    }
    if (el.lblScriptAi) el.lblScriptAi.classList.add('active');
    if (el.lblScriptCustom) el.lblScriptCustom.classList.remove('active');
    
    const radioAi = document.querySelector('input[name="scriptMode"][value="ai"]');
    if (radioAi) radioAi.checked = true;

    if (el.modalNewProject) {
      el.modalNewProject.classList.remove('hidden');
      el.modalNewProject.style.display = 'flex';
    }
    if (el.inputTopic) {
      setTimeout(() => el.inputTopic.focus(), 50);
    }
  }

  function closeNewProjectModal() {
    if (el.modalNewProject) {
      el.modalNewProject.classList.add('hidden');
      el.modalNewProject.style.display = 'none';
    }
  }

  // Bind modal triggers immediately
  if (el.btnNewProject) {
    el.btnNewProject.addEventListener('click', openNewProjectModal);
  }
  if (el.btnCloseModal) {
    el.btnCloseModal.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeNewProjectModal();
    });
  }
  if (el.btnCancelModal) {
    el.btnCancelModal.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeNewProjectModal();
    });
  }
  if (el.modalNewProject) {
    el.modalNewProject.addEventListener('click', (e) => {
      if (e.target === el.modalNewProject) closeNewProjectModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && el.modalNewProject && !el.modalNewProject.classList.contains('hidden')) {
      closeNewProjectModal();
    }
  });

  // Radio Tab Toggle for Script Mode
  const scriptRadioButtons = document.querySelectorAll('input[name="scriptMode"]');
  scriptRadioButtons.forEach(radio => {
    radio.addEventListener('change', () => {
      if (radio.value === 'custom') {
        if (el.customScriptBox) {
          el.customScriptBox.classList.remove('hidden');
          el.customScriptBox.style.display = 'block';
        }
        if (el.lblScriptCustom) el.lblScriptCustom.classList.add('active');
        if (el.lblScriptAi) el.lblScriptAi.classList.remove('active');
        if (el.textareaScript) el.textareaScript.focus();
      } else {
        if (el.customScriptBox) {
          el.customScriptBox.classList.add('hidden');
          el.customScriptBox.style.display = 'none';
        }
        if (el.lblScriptAi) el.lblScriptAi.classList.add('active');
        if (el.lblScriptCustom) el.lblScriptCustom.classList.remove('active');
      }
    });
  });

  // Toggle AI Model dropdown based on Provider selection
  if (el.selectAiProvider && el.groupAiModel) {
    el.selectAiProvider.addEventListener('change', () => {
      if (el.selectAiProvider.value === 'gemini') {
        el.groupAiModel.style.display = 'block';
      } else {
        el.groupAiModel.style.display = 'none';
      }
    });
  }

  // Submit New Project Form
  if (el.formNewProject) {
    el.formNewProject.addEventListener('submit', async (e) => {
      e.preventDefault();
      const topic = el.inputTopic ? el.inputTopic.value.trim() : '';
      if (!topic) {
        alert('Vui lòng nhập chủ đề / tiêu đề phim bạn muốn làm!');
        if (el.inputTopic) el.inputTopic.focus();
        return;
      }

      // Auto generate slug silently from topic or timestamp
      const epId = slugify(topic) || `ep_${Date.now()}`;
      const scriptRadio = document.querySelector('input[name="scriptMode"]:checked');
      const scriptMode = scriptRadio ? scriptRadio.value : 'ai';
      const scriptText = (scriptMode === 'custom' && el.textareaScript) ? el.textareaScript.value.trim() : '';
      const mediaProvider = el.selectMediaProvider ? el.selectMediaProvider.value : 'wikimedia';
      const audioProvider = el.selectAudioProvider ? el.selectAudioProvider.value : 'silence';
      const aiProvider = el.selectAiProvider ? el.selectAiProvider.value : 'gemini';
      const aiModel = (el.selectAiModel && aiProvider === 'gemini') ? el.selectAiModel.value : 'gemini-3.1-flash-lite';
      const voice = el.selectVoice ? el.selectVoice.value : 'vi-VN-HoaiMyNeural';
      const autoRender = el.checkAutoRender ? el.checkAutoRender.checked : true;

      // Close modal immediately and return to console / main view
      closeNewProjectModal();
      switchToTab('tabTerminal');

      logTerminal(`================================================================================`, 'cmd');
      logTerminal(`🚀 BẮT ĐẦU SẢN XUẤT TẬP PHIM: "${topic}"`, 'cmd');
      logTerminal(`   Mã định danh tự tạo:  ${epId}`, 'info');
      logTerminal(`   Kịch bản lời bình:    ${scriptMode === 'ai' ? 'AI Tự động nghiên cứu & kiểm chứng' : 'Nhập thủ công (' + scriptText.length + ' ký tự)'}`, 'info');
      logTerminal(`   Nguồn ảnh tư liệu:    ${mediaProvider} | Âm thanh: ${audioProvider}`, 'info');
      logTerminal(`   AI Provider / Model:  ${aiProvider} (${aiModel})`, 'info');
      logTerminal(`================================================================================`, 'cmd');

      if (el.jobStatusPill) {
        el.jobStatusPill.textContent = 'Đang chạy Auto Vox Pipeline...';
        el.jobStatusPill.className = 'badge badge-coral';
      }
      if (el.navJobBadge) {
        el.navJobBadge.classList.remove('hidden');
        el.navJobBadge.textContent = 'RUNNING';
      }

      state.logOffset = 0;

      try {
        const res = await fetch('/api/episodes/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic,
            episode_id: epId,
            script_text: scriptText,
            media_provider: mediaProvider,
            audio_provider: audioProvider,
            ai_provider: aiProvider,
            ai_model: aiModel,
            voice,
            auto_render: autoRender,
          }),
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
          logTerminal(`❌ Lỗi khởi tạo: ${data.error || 'Unknown error'}`, 'error');
          if (el.jobStatusPill) {
            el.jobStatusPill.textContent = 'Lỗi';
            el.jobStatusPill.className = 'badge badge-coral';
          }
          if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
          return;
        }

        startLogPolling(data.job_id, async () => {
          await loadEpisodes();
          if (el.episodeSelect) el.episodeSelect.value = data.episode_id;
          state.currentFixture = data.episode_id;
          await loadEpisodeStatus();
          await loadShootingScript();
          switchToTab('tabStudio');
          logTerminal(`🎉 Tập phim "${topic}" đã hoàn tất và sẵn sàng trên màn hình Studio!`, 'success');
        });
      } catch (err) {
        logTerminal(`❌ Lỗi mạng: ${err.message}`, 'error');
        if (el.jobStatusPill) {
          el.jobStatusPill.textContent = 'Lỗi mạng';
          el.jobStatusPill.className = 'badge badge-coral';
        }
        if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
      }
    });
  }

  // ---------------------------------------------------------------------------
  // API Fetchers
  // ---------------------------------------------------------------------------

  async function loadEpisodes() {
    try {
      const res = await fetch('/api/episodes');
      if (!res.ok) return;
      const data = await res.json();
      if (el.episodeSelect) {
        el.episodeSelect.innerHTML = '';
        data.episodes.forEach(ep => {
          const opt = document.createElement('option');
          opt.value = ep.fixture_name;
          opt.textContent = `${ep.fixture_name} (${ep.title})`;
          if (ep.fixture_name === state.currentFixture) opt.selected = true;
          el.episodeSelect.appendChild(opt);
        });
      }
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
        if (el.scriptTableBody) {
          el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Chưa có shooting script. Vui lòng bấm "Chạy Planning Pipeline" hoặc "Xuất JSON & Markdown".</td></tr>`;
        }
        if (el.jsonViewer) el.jsonViewer.textContent = '{}';
        return;
      }
      const data = await res.json();
      state.scriptData = data.script;
      renderBeatTimeline(data.script);
      renderShootingScriptTable(data.script);
      if (el.jsonViewer) {
        el.jsonViewer.textContent = JSON.stringify(data.script, null, 2);
      }
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
    if (el.valDuration) el.valDuration.textContent = formatTime(status.total_duration_sec);
    if (el.valBeats) el.valBeats.textContent = status.beat_count;
    if (el.valOverrides) el.valOverrides.textContent = status.overrides_count;
    if (el.overrideCount) el.overrideCount.textContent = status.overrides_count;

    if (status.has_video) {
      if (el.valVideo) {
        el.valVideo.textContent = `Sẵn sàng (${status.video_size_mb} MB)`;
        el.valVideo.className = 'pill-value badge-green';
      }
      if (el.videoPlaceholder) el.videoPlaceholder.classList.add('hidden');
      if (el.mainVideo) el.mainVideo.src = `/api/episodes/${state.currentFixture}/video`;
    } else {
      if (el.valVideo) {
        el.valVideo.textContent = 'Chưa render';
        el.valVideo.className = 'pill-value badge-neutral';
      }
      if (el.videoPlaceholder) el.videoPlaceholder.classList.remove('hidden');
      if (el.mainVideo) el.mainVideo.removeAttribute('src');
    }

    if (el.valAudio) {
      el.valAudio.textContent = status.has_audio ? 'Synthesized' : 'None';
    }
  }

  async function renderOverrides() {
    const overrides = await loadOverrides();
    if (!el.overridesList) return;
    el.overridesList.innerHTML = '';

    if (!overrides.length) {
      el.overridesList.innerHTML = '<p class="empty-hint">Chưa có override nào được áp dụng.</p>';
      return;
    }

    overrides.forEach(ovr => {
      const item = document.createElement('div');
      item.className = 'override-item';
      item.innerHTML = `
        <div class="override-meta">
          <span class="badge badge-gold">Beat ${ovr.beat_id || '?'}</span>
          <span class="override-field">${ovr.field}</span>
          <span class="override-val">${ovr.new_value}</span>
        </div>
        <button class="btn btn-secondary btn-xs btn-delete-override" data-id="${ovr.override_id}">Xóa</button>
      `;
      el.overridesList.appendChild(item);
    });

    el.overridesList.querySelectorAll('.btn-delete-override').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.getAttribute('data-id');
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
    if (!el.beatTrack || !script || !script.beats) return;
    el.beatTrack.innerHTML = '';
    if (el.filterBeatSelect) {
      el.filterBeatSelect.innerHTML = '<option value="all">Tất cả các Beats</option>';
    }

    const totalDur = script.total_duration_sec || 60;

    script.beats.forEach((beat, idx) => {
      const widthPct = Math.max(2, (beat.duration_sec / totalDur) * 100);
      const seg = document.createElement('div');
      seg.className = `beat-seg ${idx === 0 ? 'active' : ''}`;
      seg.style.width = `${widthPct}%`;
      seg.setAttribute('data-beat-id', beat.beat_id);
      seg.innerHTML = `
        <span class="seg-id">B${beat.beat_id.replace('beat_', '')}</span>
        <span class="seg-time">${beat.duration_sec.toFixed(1)}s</span>
      `;

      seg.addEventListener('click', () => {
        document.querySelectorAll('.beat-seg').forEach(s => s.classList.remove('active'));
        seg.classList.add('active');
        updateActiveBeat(beat.beat_id);
        if (el.mainVideo && el.mainVideo.src) {
          el.mainVideo.currentTime = beat.start_sec;
          el.mainVideo.play().catch(() => {});
        }
      });

      el.beatTrack.appendChild(seg);

      if (el.filterBeatSelect) {
        const opt = document.createElement('option');
        opt.value = beat.beat_id;
        opt.textContent = `Beat ${beat.beat_id.replace('beat_', '')} (${beat.visual_family})`;
        el.filterBeatSelect.appendChild(opt);
      }
    });

    if (script.beats.length > 0) {
      updateActiveBeat(script.beats[0].beat_id);
    }
  }

  function updateActiveBeat(beatId) {
    if (!state.scriptData) return;
    const beat = state.scriptData.beats.find(b => b.beat_id === beatId);
    if (!beat) return;

    if (el.activeBeatBadge) el.activeBeatBadge.textContent = beat.beat_id.toUpperCase();
    if (el.infoBeatId) el.infoBeatId.textContent = beat.beat_id;
    if (el.infoFamily) el.infoFamily.textContent = `${beat.visual_family} (${beat.strategy || 'default'})`;
    if (el.infoTime) el.infoTime.textContent = `[${formatTime(beat.start_sec)} - ${formatTime(beat.end_sec)}] (${beat.duration_sec.toFixed(2)}s)`;
    if (el.infoNarration) el.infoNarration.textContent = `"${beat.narration_text}"`;

    // Highlight timeline segment
    document.querySelectorAll('.beat-seg').forEach(s => {
      if (s.getAttribute('data-beat-id') === beatId) s.classList.add('active');
      else s.classList.remove('active');
    });
  }

  function renderShootingScriptTable(script) {
    if (!el.scriptTableBody || !script || !script.beats) return;
    el.scriptTableBody.innerHTML = '';

    if (!script.elements || !script.elements.length) {
      el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Chưa có elements nào.</td></tr>`;
      return;
    }

    const filterBeat = el.filterBeatSelect ? el.filterBeatSelect.value : 'all';
    const query = el.scriptSearch ? el.scriptSearch.value.toLowerCase().trim() : '';

    let visibleCount = 0;
    script.elements.forEach(elem => {
      if (filterBeat !== 'all' && elem.beat_id !== filterBeat) return;
      if (query && !JSON.stringify(elem).toLowerCase().includes(query)) return;

      visibleCount++;
      const tr = document.createElement('tr');

      let sourceBadge = '';
      if (elem.content_source === 'editorial_override') {
        sourceBadge = '<span class="source-pill source-override">[override]</span>';
      } else if (elem.content_source === 'ai_authored') {
        sourceBadge = '<span class="source-pill source-ai">[ai_authored]</span>';
      } else if (elem.content_source === 'raw_entity') {
        sourceBadge = '<span class="source-pill source-raw">[raw]</span>';
      }

      tr.innerHTML = `
        <td><code>${elem.element_id}</code></td>
        <td><span class="badge badge-gold">${elem.beat_id}</span></td>
        <td><code>${elem.element_type}</code></td>
        <td><strong>${elem.content_text || '--'}</strong> ${sourceBadge}</td>
        <td><small class="text-dim">${elem.asset_ref || '--'}</small></td>
        <td><code>${elem.canvas_coords ? JSON.stringify(elem.canvas_coords) : '--'}</code></td>
        <td>${elem.entry_time_sec !== undefined ? elem.entry_time_sec.toFixed(2) + 's' : '--'}</td>
        <td>${elem.exit_time_sec !== undefined ? elem.exit_time_sec.toFixed(2) + 's' : '--'}</td>
        <td><code>${elem.motion_type || '--'}</code></td>
        <td>${elem.motion_params ? JSON.stringify(elem.motion_params) : '--'}</td>
        <td>${elem.typography ? JSON.stringify(elem.typography) : '--'}</td>
        <td>${elem.stop_motion ? JSON.stringify(elem.stop_motion) : '--'}</td>
        <td><small>${elem.attribution || '--'}</small></td>
      `;
      el.scriptTableBody.appendChild(tr);
    });

    if (visibleCount === 0) {
      el.scriptTableBody.innerHTML = `<tr><td colspan="13" class="text-center">Không tìm thấy elements phù hợp với bộ lọc.</td></tr>`;
    }
  }

  // Video timeupdate synchronization
  if (el.mainVideo) {
    el.mainVideo.addEventListener('timeupdate', () => {
      const cur = el.mainVideo.currentTime;
      const dur = el.mainVideo.duration || (state.status ? state.status.total_duration_sec : 0);
      if (el.currentTimeDisplay) {
        el.currentTimeDisplay.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;
      }

      if (state.scriptData && state.scriptData.beats) {
        const currentBeat = state.scriptData.beats.find(b => cur >= b.start_sec && cur < b.end_sec);
        if (currentBeat && el.infoBeatId && el.infoBeatId.textContent !== currentBeat.beat_id) {
          updateActiveBeat(currentBeat.beat_id);
        }
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Revision Studio (Propose & Apply)
  // ---------------------------------------------------------------------------

  if (el.suggestionChips) {
    el.suggestionChips.forEach(chip => {
      chip.addEventListener('click', () => {
        if (el.feedbackInput) {
          el.feedbackInput.value = chip.getAttribute('data-text') || '';
        }
      });
    });
  }

  if (el.btnPropose) {
    el.btnPropose.addEventListener('click', async () => {
      const text = el.feedbackInput ? el.feedbackInput.value.trim() : '';
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
            provider: el.revisionProvider ? el.revisionProvider.value : 'mock',
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
  }

  function renderProposal(prop) {
    if (!el.proposalBox) return;
    el.proposalBox.classList.remove('hidden');
    if (el.propId) el.propId.textContent = prop.proposal_id;
    
    if (prop.is_valid) {
      if (el.propStatusBadge) {
        el.propStatusBadge.textContent = 'VALID (Grounded)';
        el.propStatusBadge.className = 'badge badge-green';
      }
      if (el.btnApplyProposal) {
        el.btnApplyProposal.disabled = false;
        el.btnApplyProposal.style.display = 'block';
      }
      if (el.propRejectionBox) el.propRejectionBox.classList.add('hidden');
    } else {
      if (el.propStatusBadge) {
        el.propStatusBadge.textContent = 'REJECTED';
        el.propStatusBadge.className = 'badge badge-coral';
      }
      if (el.btnApplyProposal) {
        el.btnApplyProposal.disabled = true;
        el.btnApplyProposal.style.display = 'none';
      }
      if (el.propRejectionBox) el.propRejectionBox.classList.remove('hidden');
      if (el.propRejection) el.propRejection.textContent = prop.rejection_reason || 'Rejection reason unknown';
    }

    if (el.propOldVal) el.propOldVal.textContent = prop.old_value || '(none)';
    if (el.propNewVal) el.propNewVal.textContent = prop.new_value || '(none)';
    if (el.propBeat) el.propBeat.textContent = prop.beat_id || '(none)';
    if (el.propTarget) el.propTarget.textContent = prop.target_id || '(none)';
    if (el.propRationale) el.propRationale.textContent = prop.reason || '(none)';
  }

  if (el.btnApplyProposal) {
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
          logTerminal(`✓ Applied revision override: ${state.activeProposal.proposal_id}`, 'success');
          if (el.proposalBox) el.proposalBox.classList.add('hidden');
          if (el.feedbackInput) el.feedbackInput.value = '';
          state.activeProposal = null;

          await loadEpisodeStatus();
          await loadShootingScript();
        } else {
          logTerminal(`Apply failed: ${data.error}`, 'error');
        }
      } catch (err) {
        logTerminal('Apply error: ' + err, 'error');
      } finally {
        el.btnApplyProposal.disabled = false;
        el.btnApplyProposal.textContent = '✅ 1-Click Apply & Lưu Override';
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Pipeline Execution Controls & Terminal
  // ---------------------------------------------------------------------------

  async function executeCommand(commandType, options = {}) {
    switchToTab('tabTerminal');
    logTerminal(`$ videotool ${commandType} ${state.currentFixture}`, 'cmd');

    if (el.jobStatusPill) {
      el.jobStatusPill.textContent = 'Đang chạy...';
      el.jobStatusPill.className = 'badge badge-coral';
    }
    if (el.navJobBadge) {
      el.navJobBadge.classList.remove('hidden');
      el.navJobBadge.textContent = 'RUNNING';
    }

    state.logOffset = 0;

    try {
      const res = await fetch('/api/commands/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: commandType,
          fixture: state.currentFixture,
          options,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        logTerminal(`Command failed to start: ${data.error}`, 'error');
        if (el.jobStatusPill) el.jobStatusPill.textContent = 'Lỗi';
        if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
        return;
      }

      state.activeJobId = data.job_id;
      startLogPolling(data.job_id);
    } catch (err) {
      logTerminal(`Network error executing command: ${err}`, 'error');
      if (el.jobStatusPill) el.jobStatusPill.textContent = 'Lỗi';
      if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
    }
  }

  function startLogPolling(jobId, onComplete = null) {
    if (state.pollingTimer) clearInterval(state.pollingTimer);

    state.pollingTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/commands/jobs/${jobId}?offset=${state.logOffset}`);
        if (!res.ok) return;
        const job = await res.json();

        if (job.lines && job.lines.length) {
          job.lines.forEach(line => {
            let type = 'info';
            if (line.startsWith('$') || line.startsWith('===')) type = 'cmd';
            else if (line.toLowerCase().includes('error') || line.toLowerCase().includes('failed') || line.includes('❌')) type = 'error';
            else if (line.toLowerCase().includes('rendered') || line.toLowerCase().includes('passed') || line.toLowerCase().includes('generated') || line.includes('🎉') || line.includes('✓')) type = 'success';
            else if (line.toLowerCase().includes('warn') || line.startsWith('📝') || line.startsWith('⚙️') || line.startsWith('📋') || line.startsWith('🎬')) type = 'warn';

            logTerminal(line, type);
          });
          state.logOffset = job.next_offset;
        }

        if (job.status === 'completed') {
          clearInterval(state.pollingTimer);
          if (el.jobStatusPill) {
            el.jobStatusPill.textContent = `Hoàn tất (${job.elapsed_sec}s)`;
            el.jobStatusPill.className = 'badge badge-green';
          }
          if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
          logTerminal(`✓ Task finished successfully in ${job.elapsed_sec}s`, 'success');
          
          if (typeof onComplete === 'function') {
            await onComplete();
          } else {
            await loadEpisodeStatus();
            await loadShootingScript();
          }
        } else if (job.status === 'failed') {
          clearInterval(state.pollingTimer);
          if (el.jobStatusPill) {
            el.jobStatusPill.textContent = `Thất bại (exit ${job.exit_code})`;
            el.jobStatusPill.className = 'badge badge-coral';
          }
          if (el.navJobBadge) el.navJobBadge.classList.add('hidden');
          logTerminal(`✗ Task failed with exit code ${job.exit_code}`, 'error');
        }
      } catch (err) {
        clearInterval(state.pollingTimer);
      }
    }, 500);
  }

  function logTerminal(text, type = 'info') {
    if (!el.terminalLog) return;
    const line = document.createElement('div');
    line.className = `term-line term-${type}`;
    line.textContent = text;
    el.terminalLog.appendChild(line);
    el.terminalLog.scrollTop = el.terminalLog.scrollHeight;
  }

  if (el.btnClearConsole) {
    el.btnClearConsole.addEventListener('click', () => {
      if (el.terminalLog) {
        el.terminalLog.innerHTML = '<div class="term-line term-system">Console cleared.</div>';
      }
    });
  }

  // Action Button Listeners
  if (el.btnRunPlan) {
    el.btnRunPlan.addEventListener('click', () => {
      executeCommand('plan', {
        mode: el.planMode ? el.planMode.value : 'final',
        editorial_ai_enabled: el.chkAiEditorial ? el.chkAiEditorial.checked : true,
      });
    });
  }

  if (el.btnRunRender) {
    el.btnRunRender.addEventListener('click', () => {
      executeCommand('render', {
        audio_provider: el.renderAudio ? el.renderAudio.value : 'silence',
        click_track: el.chkClickTrack ? el.chkClickTrack.checked : false,
        no_audio: el.renderAudio ? el.renderAudio.value === 'none' : false,
      });
    });
  }

  if (el.btnGenScript) {
    el.btnGenScript.addEventListener('click', () => {
      executeCommand('shooting-script');
    });
  }

  if (el.btnQuickRender) {
    el.btnQuickRender.addEventListener('click', () => {
      executeCommand('render', { audio_provider: 'silence' });
    });
  }

  // Episode Select Listener
  if (el.episodeSelect) {
    el.episodeSelect.addEventListener('change', async () => {
      state.currentFixture = el.episodeSelect.value;
      await loadEpisodeStatus();
      await loadShootingScript();
    });
  }

  if (el.btnRefresh) {
    el.btnRefresh.addEventListener('click', async () => {
      await loadEpisodes();
      await loadEpisodeStatus();
      await loadShootingScript();
      logTerminal('Refreshed episode list, status and scripts', 'system');
    });
  }

  // Filter & Search
  if (el.filterBeatSelect) {
    el.filterBeatSelect.addEventListener('change', () => {
      if (state.scriptData) renderShootingScriptTable(state.scriptData);
    });
  }
  if (el.scriptSearch) {
    el.scriptSearch.addEventListener('input', () => {
      if (state.scriptData) renderShootingScriptTable(state.scriptData);
    });
  }

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
