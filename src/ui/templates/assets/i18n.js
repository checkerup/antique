/* ANTIQUE UI — i18n (RU / EN / ZH). Load order: this file defines window.t */
(function () {
  "use strict";

  var EN = {
    "brand.sub": "Antidetect Manager",
    "nav.profiles": "Profiles", "nav.groups": "Groups", "nav.proxies": "Proxies",
    "nav.automation": "Automation", "nav.extensions": "Extensions", "nav.import": "Import / Migration",
    "nav.activity": "Activity", "nav.settings": "Settings",
    "sidebar.connected": "Connected", "sidebar.disconnected": "Offline",
    "topbar.newProfile": "New profile", "topbar.theme": "Toggle theme", "topbar.refresh": "Refresh",
    "search.placeholder": "Search profiles…",
    "col.name": "Name", "col.group": "Group", "col.status": "Status", "col.proxy": "Proxy",
    "col.os": "OS / Engine", "col.tags": "Tags", "col.lastActive": "Last launch", "col.launches": "Launches",
    "bulk.start": "Start", "bulk.stop": "Stop", "bulk.detect": "Detect score", "bulk.randomize": "Randomize FP",
    "bulk.export": "Export", "bulk.delete": "Delete",
    "profiles.empty": "No profiles found", "profiles.selected": "{n} selected",
    "status.running": "Running", "status.off": "Off", "status.overdue": "Overdue",
    "profiles.started": "Profile started", "profiles.stopped": "Profile stopped",
    "profiles.deleted": "Deleted", "profiles.detectDone": "Detect-score done",
    "common.cancel": "Cancel", "common.close": "Close", "common.save": "Save",
    "common.confirm": "Confirm", "common.confirmDelete": "Delete {n} profile(s)?",
    "common.error": "Error", "common.loading": "Loading…",
    "common.saved": "Saved", "common.failed": "Failed", "common.start": "Start", "common.stop": "Stop",
    "newprofile.title": "New profile", "newprofile.name": "Name", "newprofile.group": "Group",
    "newprofile.tags": "Tags", "newprofile.os": "OS", "newprofile.engine": "Engine",
    "newprofile.locale": "Locale", "newprofile.proxy": "Proxy", "newprofile.create": "Create",
    "newprofile.created": "Profile created",
    "dtab.overview": "Overview", "dtab.fingerprint": "Fingerprint", "dtab.proxy": "Proxy", "dtab.advanced": "Advanced",
    "d.overview.created": "Created", "d.overview.launches": "Launches", "d.overview.lastLaunch": "Last launch",
    "d.overview.group": "Group", "d.overview.tags": "Tags", "d.overview.remark": "Remark",
    "d.open": "Open",
    "d.fp.ua": "User agent", "d.fp.os": "OS", "d.fp.brand": "UA-CH brands", "d.fp.screen": "Screen",
    "d.fp.engine": "Engine (Chromium core)", "d.fp.languages": "Languages", "d.fp.locale": "Locale",
    "d.fp.screenRes": "Screen resolution", "d.fp.cores": "CPU cores", "d.fp.ram": "Memory (GB)",
    "d.fp.canvas": "Canvas noise", "d.fp.webgl": "WebGL vendor/GPU", "d.fp.audio": "Audio noise",
    "d.fp.refresh": "Refresh fingerprint", "d.fp.rerandomize": "Re-randomize noise seeds",
    "d.proxy.config": "Current config", "d.proxy.check": "Check proxy", "d.proxy.checking": "Checking…",
    "d.proxy.apply": "Apply", "d.proxy.none": "Direct connection (no proxy)",
    "d.proxy.ok": "Proxy OK: {ip}", "d.proxy.fail": "Proxy check failed: {err}",
    "d.advanced.cookieImport": "Import cookies (JSON / Netscape)", "d.advanced.cookieImportBtn": "Import",
    "d.advanced.urls": "URLs (one per line)", "d.advanced.runRobot": "Run robot",
    "d.advanced.extInstall": "Install extension", "d.advanced.extId": "Extension ID or store URL",
    "d.advanced.copyCdV": "Copy CDP / DevTools URL",
    "d.advanced.copyCdV.desc": "DevTools URL for external automation (Playwright/Selenium)",
    "d.advanced.delete": "Delete profile", "d.advanced.deleteConfirm": "Delete profile permanently?",
    "d.advanced.cookieRobotStarted": "Cookie robot started", "d.advanced.cookieImported": "Cookies imported",
    "d.advanced.cdpCopied": "Copied to clipboard",
    "groups.title": "Groups", "groups.newName": "New group name", "groups.create": "Create group",
    "groups.created": "Group created", "groups.deleted": "Group deleted",
    "groups.empty": "No groups yet", "groups.profiles": "{n} profiles",
    "groups.deleteConfirm": "Delete group? Profiles stay, only the folder is removed.",
    "proxies.importTitle": "Import proxies", "proxies.lines": "Lines (host:port or user:pass@host:port)",
    "proxies.kind": "Kind", "proxies.import": "Import", "proxies.poolTitle": "Pool status",
    "proxies.rotate": "Rotate now", "proxies.checkAll": "Check all", "proxies.imported": "{n} proxies imported",
    "proxies.checkedAll": "All proxies checked",
    "automation.title": "Run flow on selected profiles", "automation.targets": "Target profiles",
    "automation.flow": "Flow (JSON steps)", "automation.stopOnError": "Stop on error",
    "automation.run": "Run", "automation.done": "Flow finished: {ok} ok / {fail} failed",
    "automation.noneSelected": "Select profiles first (checkboxes in the table)",
    "extensions.title": "Install extension", "extensions.target": "Target profiles",
    "extensions.id": "ID or URL", "extensions.install": "Install", "extensions.catalog": "Web Store search",
    "extensions.query": "Query", "extensions.search": "Search", "extensions.noneSelected": "Select profiles first",
    "extensions.installed": "Extension installed", "extensions.found": "{n} results",
    "import.title": "Import from AdsPower backup", "import.path": "Backup path", "import.prefix": "Name prefix",
    "import.preview": "Preview", "import.run": "Import", "import.previewing": "Previewing…",
    "import.report": "Import report", "import.cookiesTitle": "Import cookies to profile",
    "import.targetProfile": "Target profile", "import.cookiesFile": "JSON / Netscape file",
    "import.importCookies": "Import cookies", "import.previewReport": "Found {n} profile(s)",
    "import.imported": "Imported {n} profiles",
    "activity.title": "Recent activity", "activity.export": "Export CSV", "activity.empty": "No activity yet",
    "activity.stats.profiles": "Total profiles", "activity.stats.running": "Running now",
    "activity.stats.sessions": "Sessions total", "activity.stats.failures": "Launch failures (24h)",
    "settings.appearance": "Appearance", "settings.theme": "Theme", "settings.language": "Language",
    "settings.server": "Server", "settings.api": "API token (webhook)",
    "settings.webhookUrl": "Webhook URL", "settings.save": "Save", "settings.test": "Test",
    "toast.netErr": "Network error", "toast.serverOff": "Server unreachable",
    "term.web": "Web", "term.socks5": "SOCKS5", "term.direct": "direct", "term.noGroup": "No group",
    "term.on": "on", "term.off": "off",
    "health.healthy": "Connected", "health.warning": "Degraded", "health.critical": "Can't reach the server",

    "settings.mcp": "MCP status", "settings.mcpCopy": "Copy Config", "settings.schedules": "Backup schedules", "settings.resources": "Resource status",
    "common.start": "Start", "common.stop": "Stop", "common.run": "Run", "common.none": "No items", "common.copied": "Copied to clipboard",
    "extensions.installed": "Extension installed", "search.filterNotes": "Filter notes",

    "bulk.randomize": "Randomize", "bulk.audit": "Audit stealth",
    "bulk.massCreate": "Mass create", "bulk.rndSub": "Re-rolls fingerprints for selected profiles. Shared fields get one value across the batch; preserved fields stay untouched.",
    "bulk.rndOs": "Target OS", "bulk.rndShare": "Share across the batch", "bulk.rndPreserve": "Preserve (never randomize)",
    "bulk.rndPin": "Pin exact values (overrides win)", "bulk.rndDone": "Randomized {n} profile(s)",
    "bulk.massCount": "How many", "bulk.massPrefix": "Name prefix", "bulk.massRunning": "Creating {n} profiles…",
    "bulk.massDone": "Created {ok} of {n}", "common.create": "Create", "common.close": "Close",

    "automation.targetsCount": "{n} selected",
    "common.copy": "Copy",
    "d.proxy.applied": "Proxy applied",
    "import.runOk": "Imported {i}, updated {u}, skipped {s}, errors {e}",
    "profiles.created": "Profile created"
  };

  window.ANTIQUE_I18N = { en: EN, ru: {}, zh: {} };

  window.t = function (key, params) {
    var lang = window.__ANTIQUE_LANG || "en";
    var dict = window.ANTIQUE_I18N[lang] || {};
    var str = (dict[key] !== undefined) ? dict[key] : (EN[key] !== undefined ? EN[key] : key);
    if (params) {
      Object.keys(params).forEach(function (k) {
        str = str.split("{" + k + "}").join(String(params[k]));
      });
    }
    return str;
  };
})();
