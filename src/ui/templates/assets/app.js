/* ANTIQUE UI v2 — app logic (vanilla JS, no deps) */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var $$ = function (sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fetchJSON(url, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || (j && j.code !== 0 && j.code !== undefined)) {
          throw new Error((j && (j.msg || j.message)) || ("HTTP " + r.status));
        }
        return j;
      });
    });
  }

  function toast(msg, kind) {
    var w = $("#toast-wrap");
    var el = document.createElement("div");
    el.className = "toast " + (kind || "ok");
    el.textContent = msg;
    w.appendChild(el);
    setTimeout(function () { el.remove(); }, 4200);
  }

  var state = {
    profiles: [], groups: [], running: new Set(), selected: new Set(),
    sortKey: "name", sortAsc: true, filter: "", filterGroup: "",
    lang: "en", theme: "dark",
    drawerUid: null, screen: "profiles"
  };

  function applyI18n() {
    $$("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      el.textContent = t(key);
    });
    $$("[data-i18n-ph]").forEach(function (el) {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
    });
    $$("[data-i18n-title]").forEach(function (el) {
      el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
    });
  }

  function setLang(lang) {
    state.lang = lang;
    window.__ANTIQUE_LANG = lang;
    localStorage.setItem("antique.lang", lang);
    $$("#lang-switch button").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-lang") === lang); });
    applyI18n();
    renderTable(); renderGroups(); renderActivity(); renderTargets();
  }

  function setTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("antique.theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1117" : "#f7f6f3");
    var sel = $("#set-theme"); if (sel) sel.value = theme;
  }

  function showScreen(name) {
    state.screen = name;
    $$(".nav-item").forEach(function (el) { el.classList.toggle("active", el.getAttribute("data-screen") === name); });
    $$(".screen").forEach(function (el) { el.classList.toggle("active", el.id === "screen-" + name); });
    var titles = { profiles: "nav.profiles", groups: "nav.groups", proxies: "nav.proxies", automation: "nav.automation", extensions: "nav.extensions", import: "nav.import", activity: "nav.activity", settings: "nav.settings" };
    $("#screen-title").textContent = t(titles[name] || "nav.profiles");
    if (name === "activity") renderActivity();
    if (name === "settings") renderSettings();
    if (name === "proxies") renderTargets();
  }

  function boot() {
    state.lang = localStorage.getItem("antique.lang") || "en";
    state.theme = localStorage.getItem("antique.theme") || "dark";
    window.__ANTIQUE_LANG = state.lang;
    setTheme(state.theme);
    setLang(state.lang);
    $$("#lang-switch button").forEach(function (b) {
      b.addEventListener("click", function () { setLang(b.getAttribute("data-lang")); });
    });
    $("#theme-toggle").addEventListener("click", function () {
      setTheme(state.theme === "dark" ? "light" : "dark");
    });
    $("#refresh-btn").addEventListener("click", function () { refreshAll(); });
    $("#new-profile-btn").addEventListener("click", openNewProfile);
    $("#global-search").addEventListener("input", function (e) {
      state.filter = e.target.value.toLowerCase();
      renderTable();
    });
    var rf = document.getElementById("remark-filter");
    if (rf) rf.addEventListener("input", function (e) {
      state.filterRemark = e.target.value.toLowerCase();
      renderTable();
    });
    $$(".nav-item").forEach(function (el) {
      el.addEventListener("click", function () { showScreen(el.getAttribute("data-screen")); });
    });
    $("#sel-all").addEventListener("change", function (e) {
      var on = e.target.checked;
      visibleProfiles().forEach(function (p) { if (on) state.selected.add(p.user_id); else state.selected.delete(p.user_id); });
      renderTable(); renderTargets();
    });
    $$("[data-bulk]").forEach(function (b) {
      b.addEventListener("click", function () { doBulk(b.getAttribute("data-bulk")); });
    });
    $$("table.profiles th[data-sort]").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.getAttribute("data-sort");
        if (state.sortKey === k) state.sortAsc = !state.sortAsc;
        else { state.sortKey = k; state.sortAsc = true; }
        renderTable();
      });
    });
    $("#drawer-close").addEventListener("click", closeDrawer);
    $("#drawer-backdrop").addEventListener("click", closeDrawer);
    $$(".dtab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $$(".dtab").forEach(function (x) { x.classList.toggle("active", x === tab); });
        var panelId = "dpanel-" + tab.getAttribute("data-dtab");
        $$(".dtab-panel").forEach(function (x) { x.classList.toggle("active", x.id === panelId); });
        renderDrawerTab(tab.getAttribute("data-dtab"));
      });
    });
    $("#np-cancel").addEventListener("click", function () { $("#modal-new-profile").classList.remove("show"); });
    $("#np-create").addEventListener("click", createProfile);
    bindForms();
    bindBulkToolbar();
    refreshAll();
    heartbeat();
    setInterval(heartbeat, 15000);
  }

  function heartbeat() {
    fetchJSON("/info").then(function (r) {
      var d = r.data || {};
      var label = $("#health-label");
      var dot = $("#health-dot");
      if (dot) { dot.classList.remove("down", "warn"); dot.classList.add("healthy"); }
      if (label) label.textContent = t("health.healthy") + (d.version ? " · v" + d.version : "");
    }).catch(function () {
      var label = $("#health-label");
      var dot = $("#health-dot");
      if (dot) { dot.classList.remove("healthy", "warn"); dot.classList.add("down", "critical"); }
      if (label) label.textContent = t("health.critical");
    });
  }

  // ============ data ============
  function refreshAll() {
    Promise.all([loadProfiles(), loadGroups(), loadRunning(), loadInfo()])
      .then(function () { renderTable(); renderGroups(); renderTargets(); })
      .catch(function (e) { toast(t("toast.netErr") + ": " + e.message, "err"); });
  }

  function loadProfiles() {
    return fetchJSON("/user/list?page_size=1000").then(function (r) {
      state.profiles = (r.data && r.data.list) || [];
    });
  }

  function loadGroups() {
    return fetchJSON("/group/list").then(function (r) {
      state.groups = (r.data && r.data.list) || [];
    });
  }

  function loadRunning() {
    return fetchJSON("/user/active").then(function (r) {
      var list = (r.data && (r.data.list || r.data)) || [];
      state.running = new Set(list.map(function (x) { return x.user_id || x; }));
    });
  }

  function loadInfo() {
    return fetchJSON("/info").then(function (r) {
      var d = r.data || {};
      $("#ver-label").textContent = d.version || "";
      $("#health-dot").classList.remove("down");
    });
  }

  function visibleProfiles() {
    return state.profiles.filter(function (p) {
      if (state.filter) {
        var hay = ((p.name || "") + " " + (p.user_id || "") + " " + (p.remark || "") + " " + (p.tags || []).join(" ")).toLowerCase();
        if (hay.indexOf(state.filter) === -1) return false;
      }
      if (state.filterGroup && p.group_name !== state.filterGroup) return false;
      if (state.filterRemark) {
        var rk = (p.remark || "").toLowerCase();
        if (rk.indexOf(state.filterRemark) === -1) return false;
      }
      return true;
    });
  }

  function byUid(uid) {
    return state.profiles.filter(function (p) { return p.user_id === uid; })[0];
  }

  // ============ table ============
  function avatarColors(uid) {
    var h = 0;
    for (var i =  0; i < uid.length; i++) h = (h * 31 + uid.charCodeAt(i)) >>> 0;
    var hue = h % 360;
    return { bg: "oklch(30% 0.06 " + hue + ")", ink: "oklch(80% 0.09 " + hue + ")" };
  }

  function initials(name) {
    if (!name) return "?";
    var parts = String(name).split(/[\s_-]+/).filter(Boolean);
    return (parts[0] ? parts[0][0] : "?") + (parts[1] ? parts[1][0] : "");
  }

  function fmtDate(ts) {
    if (!ts) return "—";
    try {
      var d = new Date(ts);
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString().slice(0, 5);
    } catch (e) { return String(ts); }
  }

  function renderTable() {
    var tbody = $("#profiles-tbody");
    if (!tbody) return;
    var list = visibleProfiles();
    $("#nav-profile-count").textContent = state.profiles.length || "";
    $("#sel-info").textContent = state.selected.size ? t("profiles.selected", { n: state.selected.size }) : "";
    if (!list.length) {
      if (state.loading) {
        tbody.innerHTML = '<tr><td colspan="10"><div class="skeleton" style="width:40%"></div></td></tr><tr><td colspan="10"><div class="skeleton" style="width:70%"></div></td></tr><tr><td colspan="10"><div class="skeleton" style="width:55%"></div></td></tr>';
        $("#profiles-empty").hidden = true;
        return;
      }
      tbody.innerHTML = "";
      $("#profiles-empty").hidden = false;
      return;
    }
    $("#profiles-empty").hidden = true;
    var sorted = list.slice().sort(function (a, b) {
      var ka = a[state.sortKey], kb = b[state.sortKey];
      if (ka == null) ka = ""; if (kb == null) kb = "";
      ka = String(ka).toLowerCase(); kb = String(kb).toLowerCase();
      var c = ka < kb ? -1 : (ka > kb ? 1 : 0);
      return state.sortAsc ? c : -c;
    });
    tbody.innerHTML = sorted.map(rowHTML).join("");
    bindRowEvents();
  }

  function rowHTML(p) {
    var uid = p.user_id;
    var running = state.running.has(uid);
    var colors = avatarColors(uid);
    var pc = p.user_proxy_config;
    var proxyStr = pc && pc.proxy_type !== "direct" && pc.proxy_host
      ? esc(pc.proxy_type + "://" + pc.proxy_host + ":" + (pc.proxy_port || ""))
      : '<span class="mono" style="opacity:.55">' + esc(t("term.direct")) + "</span>";
    var status = running
      ? '<span class="status-badge running">' + esc(t("status.running")) + "</span>"
      : '<span class="status-badge off">' + esc(t("status.off")) + "</span>";
    var fp = p.fingerprint_config || {};
    var os = fp.os || fp.os_family || "windows";
    var engine = fp.browser_core || fp.engine || "chromium";
    var launches = p.launch_count != null ? p.launch_count : ((p.statistic || {}).launch_count) || 0;
    var last = p.last_launch_time || ((p.statistic || {}).last_launch_time) || "";
    var tags = (p.tags || []).slice(0, 3).map(function (tg) {
      return '<span class="tag-chip">' + esc(tg) + "</span>";
    }).join("");
    return '<tr data-uid="' + esc(uid) + '">' +
      '<td><input type="checkbox" class="row-sel"' + (state.selected.has(uid) ? " checked" : "") + "></td>" +
      '<td><div class="cell-profile"><div class="avatar" style="background:' + colors.bg + ";color:" + colors.ink + '">' + esc(initials(p.name)) + '</div><div><div class="p-name">' + esc(p.name || uid) + '</div><div class="p-tags">' + tags + "</div></div></div></td>" +
      "<td>" + (p.group_name ? esc(p.group_name) : '<span style="opacity:.4">' + esc(t("term.noGroup")) + "</span>") + "</td>" +
      "<td>" + status + "</td>" +
      "<td>" + proxyStr + "</td>" +
      "<td>" + esc(os + " / " + engine) + "</td>" +
      "<td>" + (tags || "") + "</td>" +
      '<td><span class="mono" style="opacity:.8">' + esc(fmtDate(last)) + "</span></td>" +
      "<td>" + esc(String(launches)) + "</td>" +
      '<td><div class="cell-actions">' +
      '<button class="btn small" data-act="start" aria-label="' + (running ? "Stop profile" : "Start profile") + '">' + esc(running ? t("common.stop") : t("common.start")) + "</button>" +
      '<button class="btn small" data-act="drawer" aria-label="Manage profile">⚙</button>' +
      "</div></td>" +
      "</tr>";
  }

  function bindRowEvents() {
    $$("#profiles-tbody tr").forEach(function (tr) {
      var uid = tr.getAttribute("data-uid");
      tr.querySelector(".row-sel").addEventListener("change", function (e) {
        if (e.target.checked) state.selected.add(uid); else state.selected.delete(uid);
        $("#sel-info").textContent = state.selected.size ? t("profiles.selected", { n: state.selected.size }) : "";
        tr.classList.toggle("selected", e.target.checked);
        renderTargets();
      });
      tr.addEventListener("dblclick", function () { openDrawer(uid); });
      tr.querySelectorAll("[data-act]").forEach(function (btn) {
        btn.addEventListener("click", function (ev) {
          ev.stopPropagation();
          if (btn.getAttribute("data-act") === "start") toggleStart(uid, btn);
          else openDrawer(uid);
        });
      });
    });
  }

  function toggleStart(uid, btn) {
    var running = state.running.has(uid);
    if (btn) btn.disabled = true;
    var call = running
      ? fetchJSON("/user/bulk/stop", { method: "POST", body: JSON.stringify({ user_ids: [uid] }) })
      : fetchJSON("/user/start", { method: "POST", body: JSON.stringify({ user_id: uid }) });
    return call.then(function () {
      toast(running ? t("profiles.stopped") : t("profiles.started"));
      return loadRunning();
    }).then(renderTable).catch(function (e) {
      toast(e.message, "err");
    }).finally(function () { if (btn) btn.disabled = false; });
  }

  // ============ bulk ============
  function doBulk(kind) {
    var uids = Array.from(state.selected);
    if (!uids.length) { toast(t("automation.noneSelected"), "err"); return; }
    if (kind === "delete" && !confirm(t("common.confirmDelete", { n: uids.length }))) return;
    var url, body;
    if (kind === "start") { url = "/user/bulk/start"; body = { user_ids: uids }; }
    else if (kind === "stop") { url = "/user/bulk/stop"; body = { user_ids: uids }; }
    else if (kind === "delete") { url = "/user/bulk/delete"; body = { user_ids: uids }; }
    else if (kind === "export") { url = "/user/bulk/export"; body = { user_ids: uids }; }
    else if (kind === "detect") { url = "/user/bulk/detect-score"; body = { user_ids: uids }; }
    else if (kind === "randomize") { url = "/user/bulk/fingerprint/randomize"; body = { user_ids: uids }; }
    fetchJSON(url, { method: "POST", body: JSON.stringify(body) })
      .then(function (r) {
        if (kind === "export") downloadExport(r);
        else if (kind === "detect") toastDetect(r);
        else toast(t("common.saved"));
        refreshAll();
      })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function downloadExport(r) {
    try {
      var data = r.data || {};
      var text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
      var blob = new Blob([text], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "antique-profiles-export.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) { toast(e.message, "err"); }
  }

  function toastDetect(r) {
    var d = r.data || {};
    toast(t("profiles.detectDone") + (d.summary ? ": " + d.summary : ""));
  }

  // ============ drawer ============
  function openDrawer(uid) {
    state.drawerUid = uid;
    var p = byUid(uid);
    if (!p) return;
    var colors = avatarColors(uid);
    var av = $("#drawer-avatar");
    av.style.background = colors.bg;
    av.style.color = colors.ink;
    av.textContent = initials(p.name);
    $("#drawer-name").textContent = p.name || uid;
    $("#drawer-uid").textContent = uid;
    $("#drawer-backdrop").classList.add("show");
    $("#drawer").classList.add("show");
    renderDrawerTab("overview");
  }

  function closeDrawer() {
    state.drawerUid = null;
    $("#drawer-backdrop").classList.remove("show");
    $("#drawer").classList.remove("show");
  }

  function renderDrawerTab(tab) {
    var p = byUid(state.drawerUid);
    if (!p) return;
    var root = $("#dpanel-" + tab);
    if (!root) return;
    if (tab === "overview") renderOverviewTab(p, root);
    else if (tab === "fingerprint") renderFingerprintTab(p, root);
    else if (tab === "proxy") renderProxyTab(p, root);
    else if (tab === "advanced") renderAdvancedTab(p, root);
  }

  function kvRow(k, v, mono) {
    return '<tr><th>' + esc(k) + '</th><td class="' + (mono ? "mono" : "") + '">' + esc(v) + "</td></tr>";
  }

  function renderOverviewTab(p, root) {
    var launches = p.launch_count != null ? p.launch_count : ((p.statistic || {}).launch_count) || 0;
    var last = p.last_launch_time || ((p.statistic || {}).last_launch_time) || "";
    root.innerHTML =
      '<table class="kv-table">' +
      kvRow(t("d.overview.created"), fmtDate(p.created_at), true) +
      kvRow(t("d.overview.group"), p.group_name || t("term.noGroup")) +
      kvRow(t("d.overview.launches"), String(launches)) +
      kvRow(t("d.overview.lastLaunch"), fmtDate(last)) +
      kvRow(t("d.overview.tags"), (p.tags || []).join(", ") || "—") +
      kvRow(t("d.overview.remark"), p.remark || "—") +
      "</table>" +
      '<div class="actions-row">' +
      '<button class="btn" data-dact="start" aria-label="Start or stop profile" aria-label-stop="Stop profile">' + esc(t(state.running.has(p.user_id) ? "common.stop" : "common.start")) + "</button>" +
      '<button class="btn" data-dact="detect" aria-label="Diagnose profile">' + esc(t("bulk.detect")) + "</button>" +
      '<button class="btn danger" data-dact="delete" aria-label="Delete profile">' + esc(t("d.advanced.delete")) + "</button>" +
      "</div>";
    bindDrawerActions(root);
  }

  function renderFingerprintTab(p, root) {
    var fp = p.fingerprint_config || {};
    var ua = fp.ua || fp.user_agent || "";
    var brands = ((fp.ua_ch || {}).brands) || ((fp.user_agent_metadata || {}).brands) || [];
    var brandsStr = (brands || []).map(function (b) { return b.brand + " " + (b.version || ""); }).join(", ");
    var noise = fp.noise || {};
    var screen = fp.screen || "";
    if (typeof screen === "object") screen = (screen.width || "?") + "x" + (screen.height || "?");
    var webgl = fp.webgl || {};
    if (typeof webgl === "string") webgl = { vendor: webgl, renderer: "" };
    root.innerHTML =
      '<table class="kv-table">' +
      kvRow(t("d.fp.ua"), ua || "auto", true) +
      kvRow(t("d.fp.os"), fp.os || fp.os_family || "windows") +
      kvRow(t("d.fp.brand"), brandsStr || "auto", true) +
      kvRow(t("d.fp.engine"), fp.browser_core || fp.engine || "chromium") +
      kvRow(t("d.fp.languages"), (fp.languages || []).join(", ") || "auto") +
      kvRow(t("d.fp.locale"), fp.locale || "auto") +
      kvRow(t("d.fp.screenRes"), screen ? screen + "px" : "auto") +
      kvRow(t("d.fp.cores"), String(fp.hardware_concurrency || fp.cores || "auto")) +
      kvRow(t("d.fp.ram"), String(fp.device_memory || fp.ram || "auto")) +
      kvRow(t("d.fp.canvas"), noiseLabel(noise.canvas != null ? noise.canvas : fp.canvas_noise)) +
      kvRow(t("d.fp.webgl"), (webgl.vendor || "auto") + " / " + (webgl.renderer || "auto")) +
      kvRow(t("d.fp.audio"), noiseLabel(noise.audio != null ? noise.audio : fp.audio_noise)) +
      "</table>" +
      '<div class="actions-row">' +
      '<button class="btn" data-dact="rerandomize">' + esc(t("d.fp.rerandomize")) + "</button>" +
      "</div>";
    bindDrawerActions(root);
  }

  function noiseLabel(v) {
    if (v == null) return "auto";
    if (typeof v === "boolean") return v ? t("term.on") : t("term.off");
    return String(v);
  }

  function renderProxyTab(p, root) {
    var pc = p.user_proxy_config || {};
    var isDirect = !pc.proxy_type || pc.proxy_type === "direct";
    var cur = isDirect ? t("d.proxy.none") : pc.proxy_type + "://" + pc.proxy_host + ":" + (pc.proxy_port || "") + (pc.proxy_user ? " (" + pc.proxy_user + ")" : "");
    root.innerHTML =
      '<table class="kv-table">' +
      kvRow(t("d.proxy.config"), cur, true) +
      "</table>" +
      '<div class="field" style="margin-top:12px"><label>' + esc(t("newprofile.proxy")) + '</label><input id="d-proxy-str" placeholder="user:pass@host:port" value="' + esc(proxyToString(pc)) + '"></div>' +
      '<div class="actions-row">' +
      '<button class="btn" data-dact="proxy-check">' + esc(t("d.proxy.check")) + "</button>" +
      '<button class="btn primary" data-dact="proxy-apply">' + esc(t("d.proxy.apply")) + "</button>" +
      "</div>" +
      '<div class="mono" id="proxy-check-result" style="margin-top:10px;font-size:11.5px;color:var(--muted);word-break:break-all"></div>';
    bindDrawerActions(root);
  }

  function proxyToString(pc) {
    if (!pc || !pc.proxy_type || pc.proxy_type === "direct") return "";
    var s = pc.proxy_host + ":" + pc.proxy_port;
    if (pc.proxy_user) s += ":" + pc.proxy_user + ":" + (pc.proxy_password || "");
    return s;
  }

  function renderAdvancedTab(p, root) {
    root.innerHTML =
      '<div class="card"><h2>' + esc(t("d.advanced.cookieImport")) + "</h2>" +
      '<div class="field"><label>JSON</label><textarea id="d-cookies-text" rows="4"></textarea></div>' +
      '<div class="actions-row"><button class="btn primary" data-dact="cookie-import">' + esc(t("d.advanced.cookieImportBtn")) + "</button></div></div>" +
      '<div class="card"><h2>' + esc(t("d.advanced.urls")) + "</h2>" +
      '<div class="field"><label>URLs</label><textarea id="d-robot-urls" rows="4" placeholder="https://google.com"></textarea></div>' +
      '<div class="actions-row"><button class="btn" data-dact="cookie-robot">' + esc(t("d.advanced.runRobot")) + "</button></div></div>" +
      '<div class="card"><h2>' + esc(t("d.advanced.extInstall")) + "</h2>" +
      '<div class="field"><label>' + esc(t("d.advanced.extId")) + '</label><input id="d-ext-id" placeholder="nkbihfbeogaeaoehlefnkodbefgpgknn"></div>' +
      '<div class="actions-row"><button class="btn" data-dact="ext-install">' + esc(t("d.advanced.extInstall")) + "</button></div></div>" +
      '<div class="card"><h2>' + esc(t("d.advanced.copyCdV")) + "</h2>" +
      '<div class="actions-row"><button class="btn" data-dact="copy-cdp" aria-label="Attach debugger">Copy</button></div>' +
      '<div class="mono" id="d-cdp-out" style="font-size:11px;color:var(--muted);margin-top:6px;word-break:break-all"></div></div>';
    bindDrawerActions(root);
  }

  // ============ drawer actions ============
  function bindDrawerActions(root) {
    root.querySelectorAll("[data-dact]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var act = btn.getAttribute("data-dact");
        var uid = state.drawerUid;
        if (act === "start") toggleStart(uid, btn);
        else if (act === "detect") detectOne(uid);
        else if (act === "delete") deleteProfile(uid);
        else if (act === "rerandomize") randomizeOne(uid);
        else if (act === "cookie-robot") runCookieRobot(uid);
        else if (act === "cookie-import") importCookies(uid);
        else if (act === "ext-install") installExtFor(uid);
        else if (act === "copy-cdp") copyCdp(uid);
        else if (act === "proxy-check") checkProxy(uid);
        else if (act === "proxy-apply") applyProxy(uid);
      });
    });
  }

  function detectOne(uid) {
    fetchJSON("/user/" + uid + "/detect-score").then(function (r) {
      var d = (r.data && (r.data.summary || r.data)) || {};
      toast(t("bulk.detect") + ": " + (d.score != null ? d.score : (d.result || "ok")));
      loadProfiles().then(renderTable);
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function randomizeOne(uid) {
    fetchJSON("/user/bulk/fingerprint/randomize", { method: "POST", body: JSON.stringify({ user_ids: [uid] }) })
      .then(function () { toast(t("bulk.randomize")); loadProfiles().then(renderTable); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function deleteProfile(uid) {
    if (!confirm(t("common.confirmDelete", { n: 1 }))) return;
    fetchJSON("/user/delete", { method: "POST", body: JSON.stringify({ user_id: uid }) })
      .then(function () { toast(t("profiles.deleted")); closeDrawer(); refreshAll(); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function runCookieRobot(uid) {
    var urls = ($("#d-robot-urls") && $("#d-robot-urls").value.trim()) || "";
    var body = { user_ids: [uid] };
    if (urls) body.urls = urls.split(/\s+/).filter(Boolean);
    fetchJSON("/user/bulk/cookie-robot", { method: "POST", body: JSON.stringify(body) })
      .then(function () { toast(t("d.advanced.cookieRobotStarted")); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function importCookies(uid) {
    var txt = ($("#d-cookies-text") && $("#d-cookies-text").value.trim()) || "";
    if (!txt) { toast(t("toast.netErr"), "err"); return; }
    fetchJSON("/user/import/cookies", { method: "POST", body: JSON.stringify({ user_id: uid, cookies: txt }) })
      .then(function () { toast(t("d.advanced.cookieImportBtn")); refreshAll(); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function installExtFor(uid) {
    var id = ($("#d-ext-id") && $("#d-ext-id").value.trim()) || "";
    if (!id) { toast("ID?", "err"); return; }
    fetchJSON("/extension/install", { method: "POST", body: JSON.stringify({ user_ids: [uid], webstore_id: id }) })
      .then(function () { toast(t("extensions.installed")); refreshAll(); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function copyCdp(uid) {
    fetchJSON("/user/" + uid + "/debugger").then(function (r) {
      var d = r.data || {};
      var ws = d.ws_endpoint || d.debugger_url || d.ws || "";
      var out = $("#d-cdp-out");
      if (out) out.textContent = ws || "—";
      if (ws) navigator.clipboard.writeText(ws).then(function () { toast(t("common.copy") || "Copied"); });
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function checkProxy(uid) {
    var out = $("#proxy-check-result");
    if (out) { out.textContent = "..."; out.style.color = "var(--muted)"; }
    fetchJSON("/user/" + uid + "/proxy/check", { method: "POST" }).then(function (r) {
      var d = r.data || {};
      if (out) { out.textContent = (d.ip || d.ipv4 || "?") + " " + (d.country || d.region || ""); out.style.color = "var(--good)"; }
    }).catch(function (e) {
      if (out) { out.textContent = e.message; out.style.color = "var(--bad)"; }
    });
  }

  function applyProxy(uid) {
    var str = ($("#d-proxy-str") && $("#d-proxy-str").value.trim()) || "";
    if (!str) { toast(t("d.proxy.none"), "err"); return; }
    var parsed = parseProxy(str);
    if (!parsed) { toast("host:port?", "err"); return; }
    fetchJSON("/user/update", { method: "POST", body: JSON.stringify({ user_id: uid, user_proxy_config: parsed }) })
      .then(function () { toast(t("d.proxy.applied")); refreshAll(); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function parseProxy(str) {
    var m = String(str).trim().match(/^(?:(\w+):\/\/)?(?:([^:@\s]+):([^@\s]+)@)?([\w.-]+):(\d+)$/);
    if (!m) return null;
    return {
      proxy_type: m[1] || "http",
      proxy_host: m[4],
      proxy_port: parseInt(m[5], 10),
      proxy_user: m[2] || "",
      proxy_password: m[3] || ""
    };
  }

  // ============ new profile modal ============
  function openNewProfile() {
    var sel = $("#np-group");
    sel.innerHTML = state.groups.map(function (g) {
      return '<option value="' + esc(g.group_id) + '">' + esc(g.group_name) + "</option>";
    }).join("") + '<option value="0">' + esc(t("term.noGroup")) + "</option>";
    var eng = $("#np-engine");
    var engines = ["chromium", "firefox", "webkit"];
    if (eng && !eng.options.length) {
      eng.innerHTML = engines.map(function (e) { return '<option value="' + e + '">' + e + "</option>"; }).join("");
    }
    $("#modal-new-profile").classList.add("show");
  }

  function createProfile() {
    var name = $("#np-name").value.trim();
    if (!name) { toast(t("newprofile.name") + "?", "err"); return; }
    var payload = { name: name, group_id: $("#np-group").value || "0", remark: "" };
    var tags = $("#np-tags").value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (tags.length) payload.tags = tags;
    var os = $("#np-os").value;
    var engine = $("#np-engine").value;
    if (engine !== "chromium") payload.fingerprint_config = { browser_core: engine };
    var osEngines = { windows: ["chrome", "chromium"], macos: ["safari", "chrome"], linux: ["firefox", "chromium"], android: ["chrome"], ios: ["safari"] };
    var fp = { os_family: os };
    if (engine && engine !== "chromium") fp.browser_core = engine;
    payload.fingerprint_config = fp;
    var proxyStr = $("#np-proxy").value.trim();
    if (proxyStr) {
      var parsed = parseProxy(proxyStr);
      if (parsed) payload.user_proxy_config = parsed;
      else { toast("Proxy: user:pass@host:port", "err"); return; }
    }
    var locale = $("#np-locale").value.trim();
    if (locale) payload.fingerprint_config.locale = locale;
    var btn = $("#np-create");
    if (btn) { btn.disabled = true; btn.classList.add("loading"); }
    fetchJSON("/user/create", { method: "POST", body: JSON.stringify(payload) })
      .then(function () {
        $("#modal-new-profile").classList.remove("show");
        toast(t("profiles.created"));
        refreshAll();
      })
      .catch(function (e) { toast(e.message, "err"); })
      .finally(function () { if (btn) { btn.disabled = false; btn.classList.remove("loading"); } });
  }

  // ============ groups screen ============
  function renderGroups() {
    var wrap = $("#groups-list");
    if (!wrap) return;
    var html = state.groups.map(function (g) {
      var count = state.profiles.filter(function (p) { return p.group_name === g.group_name; }).length;
      return '<div class="group-row"><span>' + esc(g.group_name) + '</span><span class="mono" style="opacity:.6">' + count + '</span><button class="btn small danger" data-gdel="' + esc(g.group_id) + '">✕</button></div>';
    }).join("");
    wrap.innerHTML = html || '<div class="empty-note">' + esc(t("groups.empty")) + "</div>";
    wrap.querySelectorAll("[data-gdel]").forEach(function (b) {
      b.addEventListener("click", function () {
        if (!confirm(t("common.confirmDelete", { n: 1 }))) return;
        fetchJSON("/group/delete", { method: "POST", body: JSON.stringify({ group_id: b.getAttribute("data-gdel") }) })
          .then(function () { toast(t("common.saved")); refreshAll(); })
          .catch(function (e) { toast(e.message, "err"); });
      });
    });
  }

  // ============ activity screen ============
  function renderActivity() {
    var wrap = $("#activity-list");
    if (!wrap) return;
    fetchJSON("/activity?limit=50").then(function (r) {
      var items = (r.data && (r.data.list || r.data)) || [];
      state.activity = items;
      var stats = { total: items.length, launch: 0, stop: 0, create: 0, error: 0 };
      items.forEach(function (it) {
        var k = String(it.kind || it.action || "");
        if (k.indexOf("launch") >= 0 || k.indexOf("start") >= 0) stats.launch++;
        else if (k.indexOf("stop") >= 0) stats.stop++;
        else if (k.indexOf("create") >= 0) stats.create++;
        if (it.level === "error" || it.status === "error") stats.error++;
      });
      var wrapStats = $("#activity-stats");
      if (wrapStats) wrapStats.innerHTML = [
        ["activity.statTotal", stats.total], ["activity.statLaunch", stats.launch],
        ["activity.statStop", stats.stop], ["activity.statError", stats.error]
      ].map(function (pair) {
        return '<div class="stat-card"><div class="stat-num">' + pair[1] + '</div><div class="stat-label">' + esc(t(pair[0])) + "</div></div>";
      }).join("");
      wrap.innerHTML = items.length
        ? items.map(function (it) {
            return '<div class="activity-item"><span class="act-time">' + esc(fmtDate(it.created_at || it.ts)) + '</span><span class="act-uid">' + esc(it.user_id || it.uid || "—") + '</span><span>' + esc(it.kind || it.action || "") + " " + esc(it.detail || it.message || "") + "</span></div>";
          }).join("")
        : '<div class="empty-note">' + esc(t("activity.empty")) + "</div>";
    }).catch(function (e) {
      wrap.innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>";
    });
  }

  // ============ targets & forms ============
  function renderTargets() {
    var f = $("#flow-targets"), e = $("#ext-targets");
    var n = state.selected.size;
    var txt = n ? t("automation.targetsCount", { n: n }) : "—";
    if (f) f.textContent = txt;
    if (e) e.textContent = txt;
  }

  function bindForms() {
    var el;
    el = $("#group-create-btn"); if (el) el.addEventListener("click", function () {
      var name = $("#group-new-name").value.trim();
      if (!name) return;
      fetchJSON("/group/create", { method: "POST", body: JSON.stringify({ group_name: name }) })
        .then(function () { toast(t("common.saved")); $("#group-new-name").value = ""; refreshAll(); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#proxy-import-btn"); if (el) el.addEventListener("click", function () {
      var text = $("#proxy-lines").value.trim();
      if (!text) return;
      var body = { proxy_list: text };
      var kind = $("#proxy-kind") && $("#proxy-kind").value;
      if (kind) body.kind = kind;
      fetchJSON("/user/bulk/proxy/import", { method: "POST", body: JSON.stringify(body) })
        .then(function (r) { toast(t("common.saved")); $("#proxy-lines").value = ""; refreshAll(); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#proxy-rotate-btn"); if (el) el.addEventListener("click", function () {
      fetchJSON("/proxy/providers/rotate", { method: "POST" })
        .then(function () { toast(t("common.saved")); refreshAll(); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#proxy-check-btn"); if (el) el.addEventListener("click", function () {
      fetchJSON("/proxy/providers/check", { method: "POST" })
        .then(function () { toast(t("common.saved")); refreshAll(); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#flow-run-btn"); if (el) el.addEventListener("click", function () { runFlow(); });
    el = $("#ext-install-btn"); if (el) el.addEventListener("click", function () {
      var ids = Array.from(state.selected);
      var id = $("#ext-id").value.trim();
      if (!ids.length || !id) { toast(t("automation.noneSelected"), "err"); return; }
      fetchJSON("/extension/install", { method: "POST", body: JSON.stringify({ user_ids: ids, webstore_id: id }) })
        .then(function () { toast(t("extensions.installed")); refreshAll(); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#ext-search-btn"); if (el) el.addEventListener("click", function () {
      var q = $("#ext-search-q").value.trim();
      if (!q) return;
      fetchJSON("/extension/webstore/search?q=" + encodeURIComponent(q)).then(function (r) {
        var items = (r.data && (r.data.list || r.data)) || [];
        $("#ext-results").innerHTML = items.length ? items.map(function (x) {
          return '<div class="activity-item"><span>' + esc(x.name) + '</span><span class="mono" style="opacity:.6">' + esc(x.id) + '</span><button class="btn small" data-ext="' + esc(x.id) + '">' + esc(t("extensions.install")) + "</button></div>";
        }).join("") : '<div class="empty-note">' + esc(t("activity.empty")) + "</div>";
        $$("#ext-results [data-ext]").forEach(function (b) {
          b.addEventListener("click", function () {
            $("#ext-id").value = b.getAttribute("data-ext");
            toast(t("extensions.install") + ": " + b.getAttribute("data-ext"));
          });
        });
      }).catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#migrate-preview-btn"); if (el) el.addEventListener("click", function () {
      var path = $("#migrate-path").value.trim();
      if (!path) return;
      fetchJSON("/user/import/backup/preview", { method: "POST", body: JSON.stringify({ path: path }) })
        .then(function (r) {
          var d = r.data || {};
          $("#migrate-report").innerHTML = '<div class="empty-note">' + esc(
            (d.total != null ? "Total: " + d.total + " " : "") +
            (d.imported != null ? "Importable: " + d.imported : "")
          ) + "</div>";
        })
        .catch(function (e) { $("#migrate-report").innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
    });
    el = $("#migrate-run-btn"); if (el) el.addEventListener("click", function () {
      var path = $("#migrate-path").value.trim();
      if (!path) return;
      var prefix = $("#migrate-prefix").value.trim();
      var body = { source_path: path, overwrite: false };
      if (prefix) body.name_prefix = prefix;
      fetchJSON("/user/import/backup", { method: "POST", body: JSON.stringify(body) })
        .then(function (r) {
          var d = r.data || {};
          $("#migrate-report").innerHTML = '<div class="empty-note">' + esc(
            t("import.runOk", { i: d.imported_count, u: d.updated_count, s: d.skipped_count, e: d.error_count })
          ) + "</div>";
          refreshAll();
        })
        .catch(function (e) { $("#migrate-report").innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
    });
    el = $("#cookie-import-btn"); if (el) el.addEventListener("click", function () {
      var sel = $("#cookie-target");
      var uid = sel && sel.value;
      if (!uid) { toast(t("automation.noneSelected"), "err"); return; }
      importCookies(uid);
    });
    el = $("#cookie-target");
    if (el) {
      el.innerHTML = state.profiles.map(function (pr) {
        return '<option value="' + esc(pr.user_id) + '">' + esc(pr.name) + "</option>";
      }).join("");
    }
    el = $("#activity-export-btn"); if (el) el.addEventListener("click", function () {
      fetchJSON("/activity/export", { method: "POST", body: JSON.stringify({ format: "csv" }) })
        .then(function (r) {
          var text = typeof r.data === "string" ? r.data : JSON.stringify(r.data || {});
          var blob = new Blob([text], { type: "text/csv" });
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "antique-activity.csv";
          document.body.appendChild(a);
          a.click();
          a.remove();
        })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#set-theme"); if (el) el.addEventListener("change", function (e) { setTheme(e.target.value); });
    el = $("#set-lang"); if (el) el.addEventListener("change", function (e) { setLang(e.target.value); });
    el = $("#set-webhook-save"); if (el) el.addEventListener("click", function () {
      var url = $("#set-webhook").value.trim();
      fetchJSON("/settings/webhook", { method: "POST", body: JSON.stringify({ url: url }) })
        .then(function () { toast(t("common.saved")); })
        .catch(function (e) { toast(e.message, "err"); });
    });
    el = $("#set-webhook-test"); if (el) el.addEventListener("click", function () {
      fetchJSON("/settings/webhook/test", { method: "POST" })
        .then(function () { toast("OK"); })
        .catch(function (e) { toast(e.message, "err"); });
    });
  }

  function runFlow() {
    var uids = Array.from(state.selected);
    if (!uids.length) { toast(t("automation.noneSelected"), "err"); return; }
    var flowStr = $("#flow-json").value.trim();
    if (!flowStr) { toast(t("automation.flow") + "?", "err"); return; }
    var flow;
    try { flow = JSON.parse(flowStr); }
    catch (e) { toast("JSON: " + e.message, "err"); return; }
    var body = { user_ids: uids };
    if (Array.isArray(flow)) body.steps = flow;
    else if (typeof flow === "string") body.flow = flow;
    else body.flow = flow;
    var stop = $("#flow-stop-on-error") && $("#flow-stop-on-error").checked;
    if (stop != null) body.stop_on_error = stop;
    var rep = $("#flow-report");
    if (rep) rep.textContent = "…";
    fetchJSON("/sync/run", { method: "POST", body: JSON.stringify(body) })
      .then(function (r) {
        var d = r.data || {};
        if (rep) rep.textContent = JSON.stringify(d, null, 2).slice(0, 2000);
        toast(t("common.saved"));
      })
      .catch(function (e) { if (rep) rep.textContent = e.message; toast(e.message, "err"); });
  }

  // ============ settings ============
  function renderSettings() {
    fetchJSON("/info").then(function (r) {
      var d = r.data || {};
      $("#settings-server-info").innerHTML =
        '<table class="kv-table">' +
        kvRow("version", d.version || "—", true) +
        kvRow("API", d.api_port || d.port || "—", true) +
        kvRow("profiles", String(state.profiles.length)) +
        "</table>";
      $("#set-theme").value = state.theme;
      $("#set-lang").value = state.lang;
    }).catch(function (e) { toast(e.message, "err"); });
    fetchJSON("/settings/webhook").then(function (r) {
      var d = r.data || {};
      if (d.url) $("#set-webhook").value = d.url;
    }).catch(function () {});
    loadMcp();
    loadSchedules();
    loadResources();
  }


  function bindBulkToolbar() {
    var el;
    el = $("#bulk-randomize-btn"); if (el) el.addEventListener("click", function () {
      if (!state.selected.size) { toast(t("automation.noneSelected"), "err"); return; }
      openModal("#modal-randomize");
    });
    el = $("#rnd-overrides-enabled"); if (el) el.addEventListener("change", function (e) {
      var cb = e.target;
      $("#rnd-overrides-panel").style.display = cb.checked ? "block" : "none";
    });
    el = $("#rnd-submit"); if (el) el.addEventListener("click", submitRandomize);
    el = $("#bulk-audit-btn"); if (el) el.addEventListener("click", bulkAudit);
    el = $("#mass-create-btn"); if (el) el.addEventListener("click", function () { openModal("#modal-mass"); });
    el = $("#mass-submit"); if (el) el.addEventListener("click", submitMassCreate);
    document.querySelectorAll("#modal-randomize .actions-row .btn:not(.primary), #modal-mass .actions-row .btn:not(.primary), #modal-audit .actions-row .btn").forEach(function (b) {
      b.addEventListener("click", function () { closeModal("#" + b.closest(".modal-backdrop").id); });
    });
    var m;
    m = $("#mcp-start-btn"); if (m) m.addEventListener("click", mcpStart);
    m = $("#mcp-stop-btn"); if (m) m.addEventListener("click", mcpStop);
    m = $("#mcp-copy-btn"); if (m) m.addEventListener("click", mcpCopyConfig);
    m = $("#ext-search-btn"); if (m) m.addEventListener("click", searchWebStore);
  }

  // ============ service worker (PWA) ============
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    try {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    } catch (e) { /* noop */ }
  }

  // ============ global shortcuts ============
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var closed = false;
    if (document.getElementById("drawer") && document.getElementById("drawer").classList.contains("show")) {
      document.getElementById("drawer").classList.remove("show");
      var bb = document.getElementById("drawer-backdrop");
      if (bb) bb.classList.remove("show");
      closed = true;
    }
    document.querySelectorAll(".modal-backdrop.show").forEach(function (m) {
      m.classList.remove("show");
      closed = true;
    });
    if (closed) e.preventDefault();
  });

  function auditProfile(uid) { auditOne(uid); }
  function auditModal() { openModal("#modal-audit"); }
  function startProfile(uid) { drawerAct("start", uid); }
  function openWindow(uid) { drawerAct("start", uid); }

  // aliases for the classic API surface
  function startProfile(uid) { drawerAct("start", uid); }
  function openWindow(uid) { drawerAct("start", uid); }

  // ============ MCP / schedules / resources / webstore ============
  function loadMcp() {
    var box = $("#mcp-summary"), tools = $("#mcp-tools");
    if (!box) return;
    fetchJSON("/mcp/status").then(function (r) {
      var d = r.data || {};
      var bits = ['<span class="status ' + (d.running ? "ok" : "bad") + '">' + (d.running ? "running" : "stopped") + "</span>"];
      bits.push("transport " + esc(d.transport || "stdio"));
      if (d.pid) bits.push("pid " + d.pid);
      if (d.running && d.uptime_s !== undefined && d.uptime_s !== null) bits.push("up " + Math.round(d.uptime_s) + "s");
      var tc = d.tool_count !== undefined ? d.tool_count : (d.tools || []).length;
      bits.push(tc + " tools");
      if (d.error) bits.push('<span class="status warn">' + esc(d.error) + "</span>");
      box.innerHTML = bits.join(" · ");
      var names = (d.tools || []).map(function (x) { return esc(typeof x === "string" ? x : x.name); });
      if (names.length) names = names.slice(0, 40);
      if (tools) tools.textContent = names.join(", ");
    }).catch(function (e) { box.innerHTML = '<span class="status bad">' + esc(e.message) + "</span>"; });
  }
  function mcpStart() {
    fetchJSON("/mcp/start", { method: "POST", body: "{}" }).then(function () { toast(t("common.done")); loadMcp(); })
      .catch(function (e) { toast(e.message, "err"); });
  }
  function mcpStop() {
    fetchJSON("/mcp/stop", { method: "POST", body: "{}" }).then(function () { toast(t("common.done")); loadMcp(); })
      .catch(function (e) { toast(e.message, "err"); });
  }
  function mcpCopyConfig() {
    fetchJSON("/mcp/config").then(function (r) {
      var d = r.data || {};
      var text = JSON.stringify(d.config || d, null, 2);
      navigator.clipboard.writeText(text).then(function () { toast(t("common.copied")); });
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function loadSchedules() {
    var box = $("#schedule-list");
    if (!box) return;
    fetchJSON("/backup/schedules").then(function (r) {
      var items = (r.data || {}).schedules || (r.data || {}).items || [];
      box.innerHTML = items.length
        ? items.map(function (s) {
            return '<div class="activity-item"><span>' + esc(s.name || s.id || "") + '</span><span class="muted">' + esc(s.cron || s.interval || "") + '</span><button class="btn small" data-run-schedule="' + esc(s.id || s.name || "") + '">' + esc(t("common.run")) + "</button></div>";
          }).join("")
        : '<div class="empty-note">' + esc(t("common.none")) + "</div>";
      $$("#schedule-list [data-run-schedule]").forEach(function (b) {
        b.addEventListener("click", function () { runSchedule(b.getAttribute("data-run-schedule")); });
      });
    }).catch(function (e) { box.innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
  }
  function runSchedule(id) {
    fetchJSON("/backup/schedules/" + encodeURIComponent(id) + "/run", { method: "POST", body: "{}" })
      .then(function () { toast(t("common.done")); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function loadResources() {
    var box = $("#resource-status");
    if (!box) return;
    fetchJSON("/resource/status").then(function (r) {
      var d = r.data || {};
      var bits = [];
      if (d.open_browser_profiles !== undefined) bits.push({ k: "browsers", v: d.open_browser_profiles });
      if (d.disk_free_gb !== undefined) bits.push({ k: "disk", v: d.disk_free_gb + " GB" });
      if (d.memory_percent !== undefined) bits.push({ k: "mem", v: Math.round(d.memory_percent) + "%" });
      box.innerHTML = bits.length
        ? '<table class="kv-table">' + bits.map(function (b) { return "<tr><td>" + esc(b.k) + "</td><td class='mono'>" + esc(String(b.v)) + "</td></tr>"; }).join("") + "</table>"
        : '<div class="empty-note">' + esc(t("common.none")) + "</div>";
    }).catch(function (e) { box.innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
  }

  function searchWebStore() {
    var q = $("#ext-search-q").value.trim();
    if (!q) { toast(t("extensions.query") + "?", "err"); return; }
    var out = $("#ext-results");
    out.innerHTML = '<div class="empty-note">…</div>';
    fetchJSON("/extension/webstore/search?q=" + encodeURIComponent(q) + "&limit=5").then(function (r) {
      var items = (r.data || {}).results || [];
      out.innerHTML = items.length
        ? items.map(function (x) {
            return '<div class="activity-item"><span>' + esc(x.name || x.webstore_id) + '</span><span class="muted">' + esc(x.webstore_id || "") + '</span><button class="btn small" data-ws-install="' + esc(x.webstore_id) + '">' + esc(t("extensions.install")) + "</button></div>";
          }).join("")
        : '<div class="empty-note">' + esc(t("common.none")) + "</div>";
      $$("#ext-results [data-ws-install]").forEach(function (b) {
        b.addEventListener("click", function () { installWebStore(b.getAttribute("data-ws-install")); });
      });
    }).catch(function (e) { out.innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
  }
  function installWebStore(webstore_id) {
    if (!state.selected.size) { toast(t("automation.noneSelected"), "err"); return; }
    var uids = Array.from(state.selected);
    fetchJSON("/extension/install", { method: "POST", body: JSON.stringify({ user_ids: uids, webstore_id: webstore_id }) })
      .then(function () { toast(t("extensions.installed")); })
      .catch(function (e) { toast(e.message, "err"); });
  }

  // ============ randomize / audit / mass create ============
  // ============ randomize / audit / mass create ============
  function collectRndOverrides() {
    if (!$("#rnd-overrides-enabled").checked) return null;
    var num = function (id) { var n = parseInt($(id).value, 10); return isFinite(n) ? n : undefined; };
    var raw = {
      user_agent: $("#rnd-ov-user-agent").value.trim() || undefined,
      platform: $("#rnd-ov-platform").value.trim() || undefined,
      screen_width: num("#rnd-ov-screen-width"),
      screen_height: num("#rnd-ov-screen-height"),
      hardware_concurrency: num("#rnd-ov-hardware-concurrency"),
      device_memory: num("#rnd-ov-device-memory"),
      webgl_vendor: $("#rnd-ov-webgl-vendor").value.trim() || undefined,
      webgl_renderer: $("#rnd-ov-webgl-renderer").value.trim() || undefined,
      timezone: $("#rnd-ov-timezone").value.trim() || undefined
    };
    var langs = $("#rnd-ov-languages").value.trim();
    if (langs) raw.languages = langs.split(",").map(function (x) { return x.trim(); }).filter(Boolean);
    var out = {};
    Object.keys(raw).forEach(function (k) { if (raw[k] !== undefined) out[k] = raw[k]; });
    return Object.keys(out).length ? out : null;
  }

  function submitRandomize() {
    var uids = Array.from(state.selected);
    if (!uids.length) { toast(t("automation.noneSelected"), "err"); return; }
    var checked = function (sel) { return Array.from(document.querySelectorAll(sel)).filter(function (c) { return c.checked; }).map(function (c) { return c.value; }); };
    var body = {
      user_ids: uids,
      os_family: $("#rnd-os").value,
      shared_fields: checked("#modal-randomize .rnd-shared:checked"),
      preserve_fields: checked("#modal-randomize .rnd-preserve:checked")
    };
    var ov = collectRndOverrides();
    if (ov) body.overrides = ov;
    fetchJSON("/user/bulk/fingerprint/randomize", { method: "POST", body: JSON.stringify(body) })
      .then(function (r) {
        var d = r.data || {};
        closeModal("#modal-randomize");
        toast(t("bulk.rndDone", { n: d.updated_count || 0 }));
        refreshAll();
      })
      .catch(function (e) { toast(e.message, "err"); });
  }

  function auditOne(uid, name) {
    var box = $("#audit-body");
    openModal("#modal-audit");
    box.innerHTML = '<div class="empty-note">…</div>';
    fetchJSON("/user/" + uid + "/detect-score").then(function (r) {
      var d = r.data || {};
      var score = d.score !== undefined ? d.score : "?";
      var cls = score >= 80 ? "ok" : "warn";
      var rows = (d.checks || d.findings || []).map(function (c) {
        return '<div class="activity-item"><span>' + esc(name || uid) + '</span><span class="' + ((c.ok || c.passed) ? "status ok" : "status bad") + '">' + ((c.ok || c.passed) ? "ok" : "fail") + '</span><span class="muted">' + esc(c.name || c.check || "") + " " + esc(c.detail || c.message || "") + "</span></div>";
      }).join("");
      box.innerHTML = '<div class="stat-card"><div class="stat-num">' + score + '</div><div class="stat-label">' + esc(name || uid) + '</div></div>' + rows;
    }).catch(function (e) { box.innerHTML = '<div class="empty-note">' + esc(e.message) + "</div>"; });
  }

  function bulkAudit() {
    var uids = Array.from(state.selected);
    if (!uids.length) { toast(t("automation.noneSelected"), "err"); return; }
    var box = $("#audit-body");
    openModal("#modal-audit");
    box.innerHTML = "";
    var done = 0, total = uids.length;
    uids.forEach(function (uid) {
      var p = byUid(uid);
      fetchJSON("/user/" + uid + "/detect-score").then(function (r) {
        var d = r.data || {};
        var score = d.score !== undefined ? d.score : "?";
        var row = document.createElement("div");
        row.className = "activity-item";
        row.innerHTML = '<span>' + esc(p ? p.name : uid) + '</span><span class="status ' + (score >= 80 ? "ok" : "warn") + '">' + score + "</span>";
        box.appendChild(row);
      }).catch(function (e) {
        var row = document.createElement("div");
        row.className = "activity-item";
        row.innerHTML = '<span>' + esc(p ? p.name : uid) + '</span><span class="status bad">' + esc(e.message) + "</span>";
        box.appendChild(row);
      }).then(function () {
        done++;
        if (done === total) { /* all settled */ }
      });
    });
  }

  function submitMassCreate() {
    var count = parseInt($("#mass-count").value, 10) || 0;
    var prefix = $("#mass-prefix").value.trim() || "profile";
    var os = $("#mass-os").value;
    if (count < 1) { toast(t("bulk.massCount") + "?", "err"); return; }
    if (count > 500) count = 500;
    closeModal("#modal-mass");
    toast(t("bulk.massRunning", { n: count }));
    var okc = 0;
    var chain = Promise.resolve();
    for (var i = 1; i <= count; i++) {
      (function (n) {
        chain = chain.then(function () {
          return fetchJSON("/user/create", { method: "POST", body: JSON.stringify({ name: prefix + "-" + n, fingerprint_config: { os_family: os } }) })
            .then(function () { okc++; })
            .catch(function () {});
        });
      })(i);
    }
    chain.then(function () {
      toast(t("bulk.massDone", { ok: okc, n: count }));
      refreshAll();
    });
  }

  function openModal(sel) { var m = $(sel); if (m) m.classList.add("show"); }
  function closeModal(sel) { var m = $(sel); if (m) m.classList.remove("show"); }

  // ============ go ============
  boot();
  window.addEventListener("DOMContentLoaded", function () { });
})();
