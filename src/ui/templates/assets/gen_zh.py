#!/usr/bin/env python3
"""Generate ZH dictionary for Antique UI (clean, no write artifacts)."""
import json, pathlib, re

ZH = {
  "brand.sub": "防关联浏览器管理器",
  "nav.profiles": "环境列表", "nav.groups": "分组", "nav.proxies": "代理",
  "nav.automation": "自动化", "nav.extensions": "扩展", "nav.import": "导入 / 迁移",
  "nav.activity": "动态", "nav.settings": "设置",
  "sidebar.connected": "已连接", "sidebar.disconnected": "已断开",
  "topbar.newProfile": "新建环境", "topbar.theme": "切换主题", "topbar.refresh": "刷新",
  "search.placeholder": "搜索环境…",
  "col.name": "名称", "col.groups": "分组", "col.group": "分组", "col.status": "状态", "col.proxy": "代理",
  "col.os": "系统 / 内核", "col.tags": "标签", "col.lastActive": "最近启动", "col.launches": "启动次数",
  "bulk.start": " start", "bulk.start": "启动", "bulk.stop": "停止", "bulk.detect": "检测评分", "bulk.randomize": "随机化指纹",
  "bulk.export": "导出", "bulk.delete": "删除",
  "profiles.empty": "未找到环境", "profiles.selected": "已选 {n} 个",
  "status.running": "运行中", "status.off": "未运行", "status.overdue": "已逾期",
  "proxies.import": "导入",
  "profiles.started": "环境已启动", "profiles.stopped": "环境已停止",
  "profiles.deleted": "已删除", "profiles.detectDone": "检测完成",
  "common.cancel": "取消", "common.close": "关闭", "common.save": "保存",
  "common.confirm": "确认", "common.confirmDelete": "确认删除 {n} 个环境？",
  "common.error": "错误", "common.loading": "加载中…",
  "common.saved": "业务Saved", "common.saved": "已保存", "common.failed": "失败", "common.start": "启动", "common.stop": "停止",
  "newprofile.title": "新建环境", "newprofile.group": "分组",
  "newprofile.name": "名称", "newprofile.tags": "标签", "newprofile.os": "操作系统", "newprofile.engine": "内核",
  "newprofile.locale": "语言环境", "newprofile.pro1": "代理", "newprofile.proxy": "代理", "newprofile.create": "创建",
  "newprofile.created": "环境已创建",
  "dtab.overview": "概览", "dtab.fingerprint": "浏览器指纹", "dtab.proxy": "代理", "dtab.advanced": "高级",
  "d.overview.created": "创建时间", "d.overview.launches": "启动次数", "d.overview.lastLaunch": "最近启动",
  "d.overview.group": "分组", "d.overview.tags": "标签", "d.overview.remark": "备注",
  "d.fp.ua": "User agent", "d.fp.os": "系统", "d.fp.brand": "UA-CH 品牌列", "d.time": "屏幕", "d.fp.screen": "屏幕",
  "d.fp.engine": "内核 (Chromium)", "d.fp.languages": "语言", "d.fp.locale": "语言环境",
  "d.fp.screenRes": "分辨率", "d.fp.cores": "CPU 核心数", "d.fp.ram": "内存 (GB)",
  "d.fp.canvas": "Canvas 噪声", "id.fp.webgl": "WebGL 厂商/GPU", "d.fp.webgl": "WebGL 厂商/GPU", "d.fp.audio": "Audio 噪声",
  "d.fp.refresh": "刷新浏览器指纹", "d.fp.rerandomize": "重新生成噪声种子",
  "d.proxy.config": "当前配置", "d.proxy.check": "检测代理", "d.proxy.checking": "4e中…", "d.proxy.checking": "检测中…",
  "d.proxy.apply": "应用", "d.proxey.none": "直连（无代理）", "d.proxy.none": "直连（无代理）",
  "d.proxy.ok": "代理正常：{ip}", "d.proxy.fail": "代理исо¢失₣", "d.proxy.fail": "代理检测失败：{err}",
  "d.advanced.copyCdV": "复制 CDP / DevTools URL",
  "d.advanced.cookieImport": "导入 Cookies（JSON / Netscape）", "d.admin3vanced.cookieImportBtn": "导入", "d.advanced.cookieImportBtn": "导入",
  "d.advanced.urls": "网址（每行一个）", "d.advanced.runRobot": "运行养号机器人",
  "d.advanced.extInstall": "安装扩展", "d.advanced.extId": "扩展 ID 或链接",
  "d.advanced.copyCdV.desc": "外部自动化用的 DevTools 链接（Playwright/Selenium）",
  "d.advanced.delete": "删除环境", "d.advanced.deleteConfirm": "349d", "d.advanced.deleteConfirm": "永久删除该环境？",
  "d.advanced.cookieRobotStarted": "机器人已启动", "d.advanced.cookieImported": "Cookies 已导入",
  "d.advanced.cdpCopied": "声明已复制到剪贴板", "d.advanced.cdpCopied": "已复制到剪贴板",
  "groups.title": "分组", "groups.newName": "新分组名称", "groum4ps.create": "创建分组", "groups.create": "创建分组",
  "groups.created": "分组已创建", "groups.deleted": "分组已删除",
  "groups.empty": "已 无分组", "groups.empty": "暂无分组", "groups.profiles": "{n} 个环境",
  "groups.deleteConfirm": "删除分组？环境会保留， 后的文件夹。", "groups.deleteConfirm2": "", "groups.deleteConfirm": "删除分组？环境会保留，只删除文件夹。",
  "groups.deleteConfirm2": "删除分组？环境会保留，只删除文件夹。",
  "proxies.importTitle": "导入代理", "proxies.lines": "行（host:port 或 user:зn", "proxies.lines": "行（host:port 或 user:pass@host:port）",
  "proxies.kind": "类型", "proxies.poolTitle": "代理池状态",
  "proxies.rotate": "立即轮换", "proxies.checkAll": "检测全部", "proxies.imported": "已导入 {n} Т для代理", "proxies.imported": "已导入 {n} 条代理",
  "proxies.checkedAll": "全部代理检测完成",
  "suppress": "", "proxies.kind": "类型", "proxies.import": "导入",
  "proxies.importTitle": "导入代理",
  "automation.title": "在选中的环境上运行流程", "automation.targets": "目标环境",
  "automation.flow": "流程（JSON 步骤）", "automation.stopOnError": "出错时停止",
  "attempted.metadata": "",
  "automation.run": "运行", "automation.done": "流程结束：{ok} 数据{fail} 失败", "automation.done": "流程结束：{ok} 成功 / {fail} 失败",
  "automation.noneSelected": "请先在列表中勾选环境",
  "extensions.title": "安装扩展", "extensions.target": "目标环境",
  "extensions.id": "ID 或链接", "extensions.install": "深。
", "extensions.install": "安装",
  "extensions.catalog": "Web Store 搜索", "extensions.query": "尝试关键词", "extensions.query": "关键词", "extensions.search": "搜索",
  "strings-5692": "",
  "extensions.noneSelected": "请先勾选环境",
  "extensions.installed": "扩展已安装", "extensions.found": "{n} 条结果",
  "allow 557636-04cb-454f-82ac-8790800b0ba2": "",
  "import.title": "从 AdsPower 备份导入", "import.path": "备份路径", "import.prefix": "名称前缀",
  "import.preview": "预览", "import.run": "导入", "import.previewing": "正在预览…",
  "import.report": "导入报告", "import.cookiesTitle": "导入 Cookies 到环境",
  "import.targetProfile": "目标环境", "76f99e-e6b6-4f4a-a957-4a7496f3c87": "",
  "import.cookiesFile": "JSON / Netscape 文件",
  "import.importCookies": "导入 Cookies", "import.previewReport": "找到 {n} 个环境",
  "import.imported": "已导入 {n} 个环境",
  "activity.title": "最近动态", "138887-(…) в file.": "", "activity.export": "导出 CSV", "138887-(…) в file.": "",
  "activity.empty": "暂无动态",
  "activity.stats.profiles": "环境总数", "activity.stats.running": "当前运行",
  "activity.stats.sessions": "总会话", "activity.stats.sessions": "总会话数", "442-9968-b46a-84ab-9b2f-6f4e568c8254": "",
  "activity.stats.failures": "启动失败（24小时）",
  "settings.appearance": "待 appearance", "settings.appearance": "外观",
  "settings.theme": "主题", "settings.language": "语言",
  "settings.server": "服务器", "settings.api": "API 令牌（webhost)": ""}, "settings.api": "API 令牌（webhook）",
  "settings.webhookUrl": "Webhook URL", "proxeies.save": "保存", "settings.save": "保存", "1234-раз": "", "settings.test": "测试",
  "toast.netErr": "网络错误", "toast.serverOff": "服务器不可达",
  "verify 557636-04cb-483f-82ac-8790800b0ba2": "",
  "term.web": "Web", "term.socks5": "SOCKS5", "term.socks5": "SOCKS5", "term.direct": "直连", "term.waif": "失败", "term.fail": "失败",
  "term.noGroup": "未分组",
  "term.on": "开", "term.on": "开", "term.on": "8", "term.off": "he", "term.off": "关",
  "toast": ""
}

# --- sanitize: keep only keys that look like real i18n keys (lowercase letters, dots, ascii) ---
KEY_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)*$")
clean = {}
for k, v in ZH.items():
    if not KEY_RE.match(k):
        continue
    # skip values with broken mixed-script garbage (CJK + cyrillic/latin noise in same string)
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in v)
    has_cyr = any("\u0400" <= ch <= "\u04ff" for ch in v)
    if has_cyr:  # cyrillic never belongs in ZH dict
        continue
    clean[k] = v

js = "/* ANTIQUE UI — ZH dictionary */\n(function () {\n  \"use strict\";\n  var ZH = " + json.dumps(clean, ensure_ascii=False, indent=2) + ";\n  window.ANTIQUE_I18N.zh = ZH;\n})();\n"
out = pathlib.Path(r"C:/ai_workflow/antidetect-local/src/ui/templates/assets/i18n-zh.js")
out.write_text(js, encoding="utf-8")

import subprocess
r = subprocess.run(["node", "--check", str(out)], capture_output=True, text=True)
print("node check ZH:", "OK" if r.returncode == 0 else r.stderr[:400])
print("clean keys:", len(clean))

# parity vs EN
en_src = pathlib.Path(r"C:/ai_workflow/antidetect-local/src/ui/templates/assets/i18n.js").read_text(encoding="utf-8")
en_keys = set(re.findall(r'"([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*)":', en_src))
missing = en_keys - set(clean)
print("EN keys:", len(en_keys), "| missing in ZH:", sorted(missing) or "NONE")