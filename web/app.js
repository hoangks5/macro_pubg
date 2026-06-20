// ===== VVIP PUBG front-end logic =====
let WEAPONS = [];
let ATTACHMENTS = {};
let KEY_OPTIONS = [];
let CONFIG = null;

function api() { return window.pywebview.api; }

// ---------- Tabs ----------
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ---------- Tab 1: system info ----------
async function loadSystemInfo() {
  const info = await api().get_system_info();
  const grid = document.getElementById('infoGrid');
  const cards = [
    ['Hệ điều hành', info.os],
    ['Tên máy', info.hostname],
    ['CPU', info.cpu_name],
    ['Nhân / Luồng', `${info.cpu_cores} nhân · ${info.cpu_threads} luồng`],
    ['Xung nhịp CPU', info.cpu_freq],
    ['RAM', info.ram_total],
    ['GPU', info.gpu.join(' | ')],
    ['Kiến trúc', info.arch],
  ];
  let html = cards.map(([t, v]) =>
    `<div class="card"><h3>${t}</h3><div class="val">${v || '—'}</div></div>`).join('');

  if (info.disks && info.disks.length) {
    html += `<div class="card full"><h3>Ổ đĩa</h3>` +
      info.disks.map(d =>
        `<div class="disk-row"><span>${d.device}</span><span>${d.free} trống / ${d.total} (${d.percent}%)</span></div>`
      ).join('') + `</div>`;
  }
  grid.innerHTML = html;
}

async function refreshLive() {
  try {
    const s = await api().get_live_stats();
    document.getElementById('cpuPct').textContent = s.cpu_percent.toFixed(0) + '%';
    document.getElementById('ramPct').textContent = s.ram_percent.toFixed(0) + '%';
    document.getElementById('cpuBar').style.width = s.cpu_percent + '%';
    document.getElementById('ramBar').style.width = s.ram_percent + '%';
    document.getElementById('ramText').textContent = `${s.ram_used} / ${s.ram_total}`;
  } catch (e) {}
}

// ---------- Tab 2: weapons ----------
// Đổ option phụ kiện cho 1 ô súng, lọc theo loại súng (AR/SMG/SR...).
async function fillAttachOptions(slot, weaponId, selected) {
  let allowed = ATTACHMENTS;
  if (weaponId) {
    try { allowed = await api().get_allowed_attachments(weaponId); }
    catch (e) { allowed = ATTACHMENTS; }
  }
  slot.querySelectorAll('.att-sel').forEach(sel => {
    const cat = sel.dataset.cat;
    const list = allowed[cat] || [];
    sel.innerHTML = list.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    const want = (selected && selected[cat]) || 'none';
    sel.value = list.some(a => a.id === want) ? want : 'none';
    sel.disabled = list.length <= 1;   // slot bị khoá (chỉ còn "— Không —")
  });
}

async function buildSelects() {
  for (const slot of document.querySelectorAll('.slot')) {
    const idx = +slot.dataset.slot;
    const wsel = slot.querySelector('.weapon-sel');
    wsel.innerHTML = '<option value="">— Chọn súng —</option>' +
      WEAPONS.map(w => `<option value="${w.id}">${w.name} (${w.type})</option>`).join('');

    const cfg = CONFIG.slot_config[idx];
    const wid = cfg ? (cfg.weapon_id || '') : '';
    wsel.value = wid;
    await fillAttachOptions(slot, wid, cfg && cfg.attachments);

    // gắn sự kiện 1 lần (selects giữ nguyên node, chỉ đổi options)
    if (!slot.dataset.bound) {
      wsel.addEventListener('change', async () => {
        await fillAttachOptions(slot, wsel.value, null);  // đổi súng -> reset phụ kiện
        saveSlot(idx, slot);
      });
      slot.querySelectorAll('.att-sel').forEach(sel =>
        sel.addEventListener('change', () => saveSlot(idx, slot)));
      slot.dataset.bound = '1';
    }

    renderProfile(slot, CONFIG.profiles[idx]);
  }
}

async function saveSlot(idx, slot) {
  const weaponId = slot.querySelector('.weapon-sel').value;
  const attachments = {};
  slot.querySelectorAll('.att-sel').forEach(sel => attachments[sel.dataset.cat] = sel.value);
  const profile = await api().update_slot(idx, weaponId, attachments);
  renderProfile(slot, profile);
}

function renderProfile(slot, p) {
  const box = slot.querySelector('.profile');
  if (!p) { box.innerHTML = '<div class="empty">Chưa chọn súng</div>'; return; }
  const phaseRows = (p.phases || []).map(ph =>
    `<div class="pf-row"><span>Viên ${ph.label}</span><b>${ph.pull_per_sec.toFixed(0)} px/s</b></div>`).join('');
  box.innerHTML = `
    <div class="pf-row"><span>Loại / Tốc độ bắn</span><span>${p.type} · ${p.rpm} RPM (${p.shots_per_sec}/s)</span></div>
    <div class="pf-row"><span>Giảm giật phụ kiện</span><span>×${p.mult}</span></div>
    <div class="pf-sep">Lực kéo dọc theo giai đoạn băng</div>
    ${phaseRows}`;
}

function highlightActive(idx) {
  document.querySelectorAll('.slot').forEach(s =>
    s.classList.toggle('active', +s.dataset.slot === idx));
}

// ---------- Controls ----------
function bindControls() {
  const master = document.getElementById('masterToggle');
  master.checked = CONFIG.enabled;
  updateStatus(CONFIG.enabled);
  master.addEventListener('change', async () => {
    const v = await api().set_enabled(master.checked);
    updateStatus(v);
  });

  const sens = document.getElementById('sens');
  sens.value = CONFIG.sensitivity;
  document.getElementById('sensVal').textContent = (+CONFIG.sensitivity).toFixed(2);
  sens.addEventListener('input', () => {
    document.getElementById('sensVal').textContent = (+sens.value).toFixed(2);
  });
  sens.addEventListener('change', async () => {
    const profiles = await api().set_sensitivity(+sens.value);
    document.querySelectorAll('.slot').forEach(s =>
      renderProfile(s, profiles[+s.dataset.slot]));
  });

}

// ---------- Tab 3: settings ----------
function bindSettings() {
  const ads = document.getElementById('adsChk');
  ads.checked = CONFIG.require_ads;
  ads.addEventListener('change', () => api().set_require_ads(ads.checked));

  const hip = document.getElementById('hip');
  hip.value = CONFIG.hipfire_mult;
  document.getElementById('hipVal').textContent = (+CONFIG.hipfire_mult).toFixed(2);
  hip.addEventListener('input', () =>
    document.getElementById('hipVal').textContent = (+hip.value).toFixed(2));
  hip.addEventListener('change', () => api().set_hipfire_mult(+hip.value));

  // phím nóng
  const keyOpts = KEY_OPTIONS.map(k => `<option value="${k.vk}">${k.name}</option>`).join('');
  const s1 = document.getElementById('keySlot1');
  const s2 = document.getElementById('keySlot2');
  const st = document.getElementById('keyToggle');
  const so = document.getElementById('keyOverlay');
  [s1, s2, st, so].forEach(sel => sel.innerHTML = keyOpts);
  s1.value = CONFIG.vk_slot1;
  s2.value = CONFIG.vk_slot2;
  st.value = CONFIG.vk_toggle;
  so.value = CONFIG.vk_overlay;
  const sendKeys = () => api().set_hotkeys(+s1.value, +s2.value, +st.value, +so.value);
  [s1, s2, st, so].forEach(sel => sel.addEventListener('change', sendKeys));

  const ccw = document.getElementById('ccwChk');
  if (ccw) {
    ccw.checked = !!CONFIG.ccw_enabled;
    ccw.addEventListener('change', async () => {
      ccw.checked = await api().set_ccw_enabled(ccw.checked);
    });
  }
  const ccwCd = document.getElementById('ccwCd');
  if (ccwCd) {
    ccwCd.value = CONFIG.ccw_cooldown ?? 2;
    document.getElementById('ccwCdVal').textContent = (+ccwCd.value).toFixed(1);
    ccwCd.addEventListener('input', () =>
      document.getElementById('ccwCdVal').textContent = (+ccwCd.value).toFixed(1));
    ccwCd.addEventListener('change', () => api().set_ccw_cooldown(+ccwCd.value));
  }

  // overlay
  const overlayBtn = document.getElementById('overlayBtn');
  syncOverlayBtn(!!CONFIG.overlay_visible);
  overlayBtn.addEventListener('click', async () => {
    const v = await api().toggle_overlay();
    syncOverlayBtn(v);
  });

  // auto-detect
  const auto = document.getElementById('autoChk');
  auto.checked = !!CONFIG.auto_detect;
  auto.addEventListener('change', () => api().set_auto_detect(auto.checked));

  const test = document.getElementById('testChk');
  test.checked = !!CONFIG.test_mode;
  if (!CONFIG.has_shot) {
    test.disabled = true;
    test.parentElement.title = 'Chưa có shot.png trong thư mục app';
  }
  test.addEventListener('change', () => api().set_test_mode(test.checked));

  document.getElementById('detectBtn').addEventListener('click', async () => {
    document.getElementById('detectMsg').textContent = '⏳ Đang nhận diện...';
    const r = await api().detect_now();
    showDetect(r);
    await refreshAfterDetect();
  });

  buildWeaponTable();
  buildAttachTable();

  // nút lưu / reset
  document.getElementById('saveBtn').addEventListener('click', async () => {
    await api().save_now();
    flash('✅ Đã lưu cấu hình vào config.json');
  });
  document.getElementById('resetBtn').addEventListener('click', async () => {
    CONFIG = await api().reset_config();
    // nạp lại dữ liệu súng/phụ kiện (đã xóa chỉnh sửa)
    WEAPONS = await api().get_weapons();
    ATTACHMENTS = await api().get_attachments();
    await rebuildAll();
    buildWeaponTable();
    buildAttachTable();
    flash('↺ Đã khôi phục mặc định');
  });
}

// cập nhật ô profile của cả 2 slot (sau khi sửa hệ số)
function updateBothProfiles(profiles) {
  if (!profiles) return;
  document.querySelectorAll('.slot').forEach(s =>
    renderProfile(s, profiles[+s.dataset.slot]));
}

function weaponName(id) {
  const w = WEAPONS.find(x => x.id === id);
  return w ? w.name : '—';
}

let _overlayOn = null;
function syncOverlayBtn(on) {
  const btn = document.getElementById('overlayBtn');
  if (!btn || _overlayOn === on) return;
  _overlayOn = on;
  btn.textContent = on ? '🟢 Overlay: ĐANG HIỆN (bấm để ẩn)' : '🖥️ Bật / tắt Overlay';
  btn.classList.toggle('primary', !on);
}

function attName(cat, id) {
  const f = (ATTACHMENTS[cat] || []).find(x => x.id === id);
  return f ? f.name : id;
}

// tóm tắt phụ kiện nhận diện được của 1 ô
function attSummary(a) {
  if (!a) return '';
  const parts = [];
  ['scope', 'muzzle', 'grip', 'stock', 'mag'].forEach(cat => {
    const id = a[cat];
    if (id && id !== 'none') parts.push(attName(cat, id));
  });
  return parts.length ? ` <span class="att-tag">[${parts.join(' · ')}]</span>` : '';
}

// hiển thị kết quả nhận diện
function showDetect(r) {
  const el = document.getElementById('detectMsg');
  if (!el || !r) return;
  const tag = r.test_mode ? '🧪 (test ảnh) ' : '';
  const atts = r.attachments || [];
  const l1 = r.slots[0] ? `✅ ${weaponName(r.slots[0])}${attSummary(atts[0])}` : `❌ (OCR: "${r.texts[0] || ''}")`;
  const l2 = r.slots[1] ? `✅ ${weaponName(r.slots[1])}${attSummary(atts[1])}` : `❌ (OCR: "${r.texts[1] || ''}")`;
  el.innerHTML = `${tag}Ô1: ${l1}<br>Ô2: ${l2}`;
}

// nạp lại config + cập nhật 2 dropdown súng sau khi nhận diện
async function refreshAfterDetect() {
  CONFIG = await api().get_config();
  await buildSelects();
  highlightActive(CONFIG.active_slot);
}

// bảng chỉnh chỉ số súng
function buildWeaponTable() {
  const tb = document.getElementById('weaponTable');
  tb.innerHTML = WEAPONS.map(w => {
    const ph = w.recoil_phases || [w.recoil, w.recoil, w.recoil, w.recoil];
    return `
    <tr data-id="${w.id}">
      <td>${w.name}</td>
      <td>${w.type}</td>
      <td><input class="num" data-f="rpm" type="number" min="1" step="10" value="${w.rpm}"></td>
      <td><input class="num ph" data-p="0" type="number" min="0" step="0.5" value="${ph[0]}"></td>
      <td><input class="num ph" data-p="1" type="number" min="0" step="0.5" value="${ph[1]}"></td>
      <td><input class="num ph" data-p="2" type="number" min="0" step="0.5" value="${ph[2]}"></td>
      <td><input class="num ph" data-p="3" type="number" min="0" step="0.5" value="${ph[3]}"></td>
    </tr>`;
  }).join('');

  tb.querySelectorAll('tr').forEach(tr => {
    const id = tr.dataset.id;
    tr.querySelectorAll('input.num').forEach(inp => {
      inp.addEventListener('change', async () => {
        const rpm = +tr.querySelector('[data-f="rpm"]').value;
        const phases = [...tr.querySelectorAll('input.ph')].map(x => +x.value);
        const profiles = await api().update_weapon(id, rpm, phases);
        updateBothProfiles(profiles);
      });
    });
  });
}

// bảng chỉnh hệ số phụ kiện
function buildAttachTable() {
  const tb = document.getElementById('attachTable');
  const labels = { scope: 'Scope', muzzle: 'Họng', grip: 'Tay cầm', stock: 'Báng', mag: 'Băng đạn' };
  let rows = '';
  Object.keys(ATTACHMENTS).forEach(cat => {
    ATTACHMENTS[cat].forEach(a => {
      rows += `
        <tr data-cat="${cat}" data-id="${a.id}">
          <td class="grp">${labels[cat] || cat}</td>
          <td>${a.name}</td>
          <td><input class="num" data-f="vert" type="number" min="0" step="0.01" value="${a.vert}"></td>
          <td class="note">${a.desc || ''}</td>
        </tr>`;
    });
  });
  tb.innerHTML = rows;

  tb.querySelectorAll('tr').forEach(tr => {
    const cat = tr.dataset.cat, id = tr.dataset.id;
    const inp = tr.querySelector('input.num');
    inp.addEventListener('change', async () => {
      const profiles = await api().update_attachment(cat, id, +inp.value);
      updateBothProfiles(profiles);
    });
  });
}

function flash(msg) {
  const el = document.getElementById('saveMsg');
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; }, 2500);
}

// vẽ lại toàn bộ UI từ CONFIG (sau khi reset)
async function rebuildAll() {
  await buildSelects();
  bindControls();
  // đồng bộ lại các control ở settings
  document.getElementById('adsChk').checked = CONFIG.require_ads;
  document.getElementById('hip').value = CONFIG.hipfire_mult;
  document.getElementById('hipVal').textContent = (+CONFIG.hipfire_mult).toFixed(2);
  document.getElementById('keySlot1').value = CONFIG.vk_slot1;
  document.getElementById('keySlot2').value = CONFIG.vk_slot2;
  document.getElementById('keyToggle').value = CONFIG.vk_toggle;
  document.getElementById('keyOverlay').value = CONFIG.vk_overlay;
  const ccw = document.getElementById('ccwChk');
  if (ccw) ccw.checked = !!CONFIG.ccw_enabled;
  const ccwCd = document.getElementById('ccwCd');
  if (ccwCd) {
    ccwCd.value = CONFIG.ccw_cooldown ?? 2;
    document.getElementById('ccwCdVal').textContent = (+ccwCd.value).toFixed(1);
  }
  document.getElementById('autoChk').checked = !!CONFIG.auto_detect;
  document.getElementById('testChk').checked = !!CONFIG.test_mode;
  highlightActive(CONFIG.active_slot);
}

function updateStatus(on) {
  document.getElementById('statusDot').className = 'dot ' + (on ? 'on' : 'off');
  document.getElementById('statusText').textContent = on ? 'BẬT' : 'TẮT';
  document.getElementById('masterToggle').checked = on;
}

// đồng bộ trạng thái từ engine (F8, đổi ô bằng phím 1/2, nhận diện qua Tab)
let _lastDetectVer = 0;
async function pollStatus() {
  try {
    const s = await api().get_status();
    updateStatus(s.enabled);
    highlightActive(s.active_slot);
    if (typeof s.overlay_visible === 'boolean') syncOverlayBtn(s.overlay_visible);
    const ccw = document.getElementById('ccwChk');
    if (ccw && typeof s.ccw_enabled === 'boolean') ccw.checked = s.ccw_enabled;
    // nhận diện qua Tab (chạy ở engine) -> refresh giao diện
    if (typeof s.detect_version === 'number' && s.detect_version !== _lastDetectVer) {
      _lastDetectVer = s.detect_version;
      if (s.detect_last) showDetect(s.detect_last);
      await refreshAfterDetect();
    }
  } catch (e) {}
}

// ---------- Init ----------
async function init() {
  WEAPONS = await api().get_weapons();
  ATTACHMENTS = await api().get_attachments();
  KEY_OPTIONS = await api().get_key_options();
  CONFIG = await api().get_config();

  await loadSystemInfo();
  await buildSelects();
  bindControls();
  bindSettings();
  highlightActive(CONFIG.active_slot);

  refreshLive();
  setInterval(refreshLive, 1500);
  setInterval(pollStatus, 400);
}

window.addEventListener('pywebviewready', init);
