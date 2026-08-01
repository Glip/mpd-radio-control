(() => {
  const state = {
    instanceId: window.RADIO_DESK.instances[0]?.id || null,
    status: null,
    seeking: false,
    volumeDragging: false,
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  const els = {
    stations: $("#stations"),
    stationName: $("#station-name"),
    nowTitle: $("#now-title"),
    nowMeta: $("#now-meta"),
    stateBadge: $("#state-badge"),
    seek: $("#seek"),
    elapsed: $("#elapsed"),
    duration: $("#duration"),
    volume: $("#volume"),
    volumeVal: $("#volume-val"),
    toggleBtn: $("#toggle-btn"),
    playlist: $("#playlist"),
    uploadStatus: $("#upload-status"),
    liveDot: $("#live-dot"),
    connLabel: $("#conn-label"),
    trackForm: $("#track-form"),
    albumForm: $("#album-form"),
  };

  function fmtTime(sec) {
    if (sec == null || Number.isNaN(Number(sec))) return "0:00";
    const s = Math.max(0, Math.floor(Number(sec)));
    const m = Math.floor(s / 60);
    const r = String(s % 60).padStart(2, "0");
    return `${m}:${r}`;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || res.statusText || "Request failed");
    }
    return data;
  }

  function applyStatus(status) {
    state.status = status;
    const online = !!status.online;
    const current = status.current || {};
    const title = current.title || current.file || (online ? "Тишина в эфире" : "Станция недоступна");
    const artist = current.artist || "";
    const album = current.album || "";

    els.stationName.textContent = status.label || state.instanceId;
    els.nowTitle.textContent = title;
    els.nowMeta.textContent = [artist, album].filter(Boolean).join(" — ")
      || (online ? `${status.host}:${status.port}` : status.error || "offline");

    const st = online ? (status.state || "stop") : "offline";
    els.stateBadge.dataset.state = st;
    els.stateBadge.textContent = st.toUpperCase();
    els.toggleBtn.classList.toggle("is-playing", st === "play");

    els.liveDot.classList.toggle("is-live", st === "play");
    els.connLabel.textContent = online
      ? (st === "play" ? "в эфире" : "онлайн")
      : "оффлайн";

    if (!state.seeking) {
      const dur = Number(status.duration || 0);
      const elapsed = Number(status.elapsed || 0);
      els.seek.max = "1000";
      els.seek.value = String(dur > 0 ? Math.round((elapsed / dur) * 1000) : 0);
      els.elapsed.textContent = fmtTime(elapsed);
      els.duration.textContent = fmtTime(dur);
    }

    if (!state.volumeDragging) {
      if (status.volume != null && status.volume >= 0) {
        els.volume.disabled = false;
        els.volume.value = String(status.volume);
        els.volumeVal.textContent = String(status.volume);
      } else {
        els.volume.disabled = true;
        els.volumeVal.textContent = "n/a";
      }
    }

    for (const chip of $$(".chip[data-option]")) {
      const key = chip.dataset.option;
      chip.classList.toggle("is-on", !!status[key]);
    }
  }

  async function refreshStatus() {
    if (!state.instanceId) return;
    try {
      const status = await api(`/api/instances/${state.instanceId}`);
      applyStatus(status);
    } catch (err) {
      els.connLabel.textContent = "ошибка";
      console.error(err);
    }
  }

  async function refreshPlaylist() {
    if (!state.instanceId) return;
    try {
      const data = await api(`/api/instances/${state.instanceId}/playlist`);
      const currentFile = state.status?.current?.file;
      els.playlist.innerHTML = "";
      if (!data.playlist.length) {
        els.playlist.innerHTML = `<li style="cursor:default;opacity:.65"><span></span><span class="title">Плейлист пуст</span></li>`;
        return;
      }
      data.playlist.forEach((song, idx) => {
        const li = document.createElement("li");
        if (song.file && song.file === currentFile) li.classList.add("is-current");
        li.innerHTML = `
          <span class="idx">${idx + 1}</span>
          <span>
            <span class="title">${escapeHtml(song.title || song.file || "—")}</span>
            <span class="sub">${escapeHtml([song.artist, song.album].filter(Boolean).join(" — "))}</span>
          </span>
          <span class="sub">${fmtTime(song.duration || song.time)}</span>
        `;
        li.addEventListener("click", async () => {
          await api(`/api/instances/${state.instanceId}/play`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pos: idx }),
          });
          await refreshAll();
        });
        els.playlist.appendChild(li);
      });
    } catch (err) {
      console.error(err);
    }
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function refreshAll() {
    await refreshStatus();
    await refreshPlaylist();
  }

  async function runAction(action) {
    if (!state.instanceId) return;
    const path = `/api/instances/${state.instanceId}/${action}`;
    await api(path, { method: "POST" });
    await refreshAll();
  }

  els.stations?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".station");
    if (!btn) return;
    $$(".station").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.instanceId = btn.dataset.id;
    await refreshAll();
  });

  $$(".tbtn[data-action], .chip[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      try {
        if (action === "clear") {
          await api(`/api/instances/${state.instanceId}/playlist/clear`, { method: "POST" });
          await refreshAll();
          return;
        }
        if (action === "update") {
          await api(`/api/instances/${state.instanceId}/update`, { method: "POST" });
          setUploadStatus("База MPD обновляется…", "ok");
          await refreshAll();
          return;
        }
        await runAction(action);
      } catch (err) {
        setUploadStatus(err.message, "error");
      }
    });
  });

  $$(".chip[data-option]").forEach((chip) => {
    chip.addEventListener("click", async () => {
      const option = chip.dataset.option;
      const enabled = !chip.classList.contains("is-on");
      try {
        await api(`/api/instances/${state.instanceId}/options/${option}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        await refreshStatus();
      } catch (err) {
        setUploadStatus(err.message, "error");
      }
    });
  });

  els.volume.addEventListener("pointerdown", () => { state.volumeDragging = true; });
  els.volume.addEventListener("pointerup", () => { state.volumeDragging = false; });
  els.volume.addEventListener("input", () => {
    els.volumeVal.textContent = els.volume.value;
  });
  els.volume.addEventListener("change", async () => {
    try {
      await api(`/api/instances/${state.instanceId}/volume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: Number(els.volume.value) }),
      });
    } catch (err) {
      setUploadStatus(err.message, "error");
    } finally {
      state.volumeDragging = false;
    }
  });

  els.seek.addEventListener("pointerdown", () => { state.seeking = true; });
  els.seek.addEventListener("pointerup", () => { state.seeking = false; });
  els.seek.addEventListener("change", async () => {
    const dur = Number(state.status?.duration || 0);
    if (!dur) return;
    const seconds = (Number(els.seek.value) / 1000) * dur;
    try {
      await api(`/api/instances/${state.instanceId}/seek`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seconds }),
      });
      await refreshStatus();
    } catch (err) {
      setUploadStatus(err.message, "error");
    } finally {
      state.seeking = false;
    }
  });

  $("#refresh-playlist")?.addEventListener("click", refreshPlaylist);

  function setUploadStatus(msg, kind) {
    els.uploadStatus.textContent = msg || "";
    els.uploadStatus.classList.toggle("is-error", kind === "error");
    els.uploadStatus.classList.toggle("is-ok", kind === "ok");
  }

  els.trackForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData();
    if (form.file.files[0]) fd.append("file", form.file.files[0]);
    if (form.subdirectory.value.trim()) {
      fd.append("subdirectory", form.subdirectory.value.trim());
    }
    fd.append("play_now", form.play_now.checked ? "true" : "false");
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    setUploadStatus("Загрузка трека…");
    try {
      const result = await api(`/api/instances/${state.instanceId}/upload/track`, {
        method: "POST",
        body: fd,
      });
      setUploadStatus(`Трек загружен: ${result.file}`, "ok");
      form.reset();
      await refreshAll();
    } catch (err) {
      setUploadStatus(err.message, "error");
    } finally {
      btn.disabled = false;
    }
  });

  els.albumForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData();
    fd.append("album_name", form.album_name.value);
    fd.append("play_now", form.play_now.checked ? "true" : "false");

    const files = form.files.files;
    for (const file of files) fd.append("files", file);
    if (form.archive.files[0]) fd.append("archive", form.archive.files[0]);

    if (!files.length && !form.archive.files[0]) {
      setUploadStatus("Добавьте треки или ZIP-архив", "error");
      return;
    }

    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    setUploadStatus("Загрузка альбома…");
    try {
      const result = await api(`/api/instances/${state.instanceId}/upload/album`, {
        method: "POST",
        body: fd,
      });
      setUploadStatus(`Альбом «${result.album}»: ${result.count} файл(ов)`, "ok");
      form.reset();
      await refreshAll();
    } catch (err) {
      setUploadStatus(err.message, "error");
    } finally {
      btn.disabled = false;
    }
  });

  refreshAll();
  setInterval(refreshStatus, 2500);
})();
