[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md) [![Русский](https://img.shields.io/badge/lang-Русский-red.svg)](README.ru.md) [![中文](https://img.shields.io/badge/lang-中文-green.svg)](README.zh.md)

# antique

**РЎР°РјРѕС…РѕСЃС‚РёСЂСѓРµРјС‹Р№ open-source Р°РЅР°Р»РѕРі AdsPower вЂ” РјСѓР»СЊС‚Рё-РїСЂРѕС„РёР»СЊРЅР°СЏ С„РµСЂРјР° Р±СЂР°СѓР·РµСЂРѕРІ СЃ РїРѕРґРјРµРЅРѕР№ fingerprint, СЂРѕС‚Р°С†РёРµР№ РїСЂРѕРєСЃРё, РёРјРїРѕСЂС‚РѕРј .adb-Р±Р°РЅРґР»РѕРІ Рё СЃРѕРІРјРµСЃС‚РёРјС‹Рј СЃ AdsPower REST API.**

> РЎРѕР±СЂР°РЅ Р°РІС‚РѕРЅРѕРјРЅРѕ, С‡С‚РѕР±С‹ Р·Р°РјРµРЅРёС‚СЊ РїР»Р°С‚РЅСѓСЋ РїРѕРґРїРёСЃРєСѓ AdsPower С‚РµРј Р¶Рµ UX Рё С„РѕСЂРјРѕР№ API, Р±РµР· Р»РёС†РµРЅР·РёР№, РїРѕР»РЅРѕСЃС‚СЊСЋ Р»РѕРєР°Р»СЊРЅРѕ.


---

## РЎРѕРґРµСЂР¶Р°РЅРёРµ

1. [Р§С‚Рѕ СЌС‚Рѕ С‚Р°РєРѕРµ (TL;DR РґР»СЏ Р°РіРµРЅС‚РѕРІ)](#1-С‡С‚Рѕ-СЌС‚Рѕ-С‚Р°РєРѕРµ-tldr-РґР»СЏ-Р°РіРµРЅС‚РѕРІ)
2. [Р‘С‹СЃС‚СЂС‹Р№ СЃС‚Р°СЂС‚](#2-Р±С‹СЃС‚СЂС‹Р№-СЃС‚Р°СЂС‚)
3. [РћР±Р·РѕСЂ Р°СЂС…РёС‚РµРєС‚СѓСЂС‹](#3-РѕР±Р·РѕСЂ-Р°СЂС…РёС‚РµРєС‚СѓСЂС‹)
4. [РљР°СЂС‚Р° РјРѕРґСѓР»РµР№](#4-РєР°СЂС‚Р°-РјРѕРґСѓР»РµР№)
5. [РњРѕРґРµР»СЊ РґР°РЅРЅС‹С… Рё СЃС…РµРјР° С…СЂР°РЅРёР»РёС‰Р°](#5-РјРѕРґРµР»СЊ-РґР°РЅРЅС‹С…-Рё-СЃС…РµРјР°-С…СЂР°РЅРёР»РёС‰Р°)
6. [Р–РёР·РЅРµРЅРЅС‹Р№ С†РёРєР» РїСЂРѕС„РёР»СЏ](#6-Р¶РёР·РЅРµРЅРЅС‹Р№-С†РёРєР»-РїСЂРѕС„РёР»СЏ)
7. [РЎРїСЂР°РІРѕС‡РЅРёРє РїРѕ CLI](#7-СЃРїСЂР°РІРѕС‡РЅРёРє-РїРѕ-cli)
8. [РЎРїСЂР°РІРѕС‡РЅРёРє РїРѕ REST API](#8-СЃРїСЂР°РІРѕС‡РЅРёРє-РїРѕ-rest-api)
9. [Р¤РѕСЂРјР°С‚С‹ РёРјРїРѕСЂС‚Р°/СЌРєСЃРїРѕСЂС‚Р° cookies](#9-С„РѕСЂРјР°С‚С‹-РёРјРїРѕСЂС‚Р°СЌРєСЃРїРѕСЂС‚Р°-cookies)
10. [РЎРёСЃС‚РµРјР° fingerprint](#10-СЃРёСЃС‚РµРјР°-fingerprint)
11. [РџРѕР»РЅС‹Р№ РїРѕС‚РѕРє РёРјРїРѕСЂС‚Р° РїСЂРѕС„РёР»СЏ (.adb)](#11-РїРѕР»РЅС‹Р№-РїРѕС‚РѕРє-РёРјРїРѕСЂС‚Р°-РїСЂРѕС„РёР»СЏ-adb)
12. [CDP-РјСѓР»СЊС‚РёРїР»РµРєСЃРѕСЂ](#12-cdp-РјСѓР»СЊС‚РёРїР»РµРєСЃРѕСЂ)
13. [РЎС‚СЂСѓРєС‚СѓСЂР° РєР°С‚Р°Р»РѕРіР° data](#13-СЃС‚СЂСѓРєС‚СѓСЂР°-РєР°С‚Р°Р»РѕРіР°-data)
14. [РўРµСЃС‚РёСЂРѕРІР°РЅРёРµ](#14-С‚РµСЃС‚РёСЂРѕРІР°РЅРёРµ)
15. [РР·РІРµСЃС‚РЅС‹Рµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ Рё roadmap](#15-РёР·РІРµСЃС‚РЅС‹Рµ-РѕРіСЂР°РЅРёС‡РµРЅРёСЏ-Рё-roadmap)
16. [РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ](#16-РїРµСЂРµРјРµРЅРЅС‹Рµ-РѕРєСЂСѓР¶РµРЅРёСЏ)
17. [Р›РёС†РµРЅР·РёСЏ](#17-Р»РёС†РµРЅР·РёСЏ)

---

## 1. Р§С‚Рѕ СЌС‚Рѕ С‚Р°РєРѕРµ (TL;DR РґР»СЏ Р°РіРµРЅС‚РѕРІ)

antique вЂ” СЌС‚Рѕ Python-СЃРµСЂРІРёСЃ, РєРѕС‚РѕСЂС‹Р№:

- РЎРѕР·РґР°С‘С‚ РёР·РѕР»РёСЂРѕРІР°РЅРЅС‹Рµ РєРѕРЅС‚РµРєСЃС‚С‹ Chromium (Playwright `launch_persistent_context`) РґР»СЏ РєР°Р¶РґРѕРіРѕ РїСЂРѕС„РёР»СЏ вЂ” Сѓ РєР°Р¶РґРѕРіРѕ РїСЂРѕС„РёР»СЏ СЃРІРѕР№ user data dir, cookies, localStorage, IndexedDB.
- Р“РµРЅРµСЂРёСЂСѓРµС‚ РІРЅСѓС‚СЂРµРЅРЅРµ-СЃРѕРіР»Р°СЃРѕРІР°РЅРЅС‹Рµ browser fingerprint (UA, navigator, screen, timezone, locale, WebGL vendor/renderer, audio + canvas noise seeds) Рё РёРЅР¶РµРєС‚РёС‚ JS init script, С‡С‚РѕР±С‹ РїР°С‚С‡РёС‚СЊ Р±СЂР°СѓР·РµСЂ РїСЂРё Р·Р°РіСЂСѓР·РєРµ.
- РЎРѕС…СЂР°РЅСЏРµС‚ РїСЂРѕС„РёР»Рё РІ SQLite (`data/antique.db`) вЂ” proxies, fingerprints, cookies, tags, sessions, import bookkeeping.
- РРјРїРѕСЂС‚РёСЂСѓРµС‚ `.adb`-Р±Р°РЅРґР»С‹ РїСЂРѕС„РёР»РµР№, СЌРєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅРЅС‹Рµ РёР· AdsPower (cookies + LocalStorage + IndexedDB). РРјРїРѕСЂС‚ РёСЃРїРѕР»СЊР·СѓРµС‚ РЅР°С‚РёРІРЅРѕРµ С‡С‚РµРЅРёРµ Chromium РІРјРµСЃС‚Рѕ С…СЂСѓРїРєРѕРіРѕ РїР°СЂСЃРёРЅРіР° LevelDB вЂ” РјС‹ РєРѕРїРёСЂСѓРµРј РёСЃС…РѕРґРЅС‹Рµ РґРёСЂРµРєС‚РѕСЂРёРё РІ Playwright `user_data_dir` Рё РїРѕР·РІРѕР»СЏРµРј Chromium С‡РёС‚Р°С‚СЊ РёС… СЃР°РјРѕСЃС‚РѕСЏС‚РµР»СЊРЅРѕ.
- РџСЂРµРґРѕСЃС‚Р°РІР»СЏРµС‚ СЃРѕРІРјРµСЃС‚РёРјС‹Р№ СЃ AdsPower REST API РЅР° `http://127.0.0.1:<port>/...`, С‚Р°Рє С‡С‚Рѕ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ СЃРєСЂРёРїС‚С‹, РєРѕС‚РѕСЂС‹Рµ СѓР¶Рµ СЂР°Р±РѕС‚Р°СЋС‚ СЃ AdsPower, РјРѕРіСѓС‚ РїРµСЂРµРєР»СЋС‡РёС‚СЊСЃСЏ, РїРѕРјРµРЅСЏРІ С‚РѕР»СЊРєРѕ Р±Р°Р·РѕРІС‹Р№ URL.
- Р’РєР»СЋС‡Р°РµС‚ РѕРґРЅРѕСЃС‚СЂР°РЅРёС‡РЅС‹Р№ РґР°С€Р±РѕСЂРґ РЅР° `/` (РёР»Рё `/dashboard`) Рё FastAPI Swagger РЅР° `/docs`.
- 270+ С‚РµСЃС‚РѕРІ pytest СѓСЃРїРµС€РЅРѕ РїСЂРѕР№РґРµРЅРѕ.
- РЎРјРµРЅСЏРµРјС‹Рµ Р±СЂР°СѓР·РµСЂРЅС‹Рµ РґРІРёР¶РєРё: Chromium, Google Chrome, Microsoft Edge, Firefox, Camoufox (РіР»СѓР±РѕРєРёР№ СЃС‚РµР»СЃ РЅР° СѓСЂРѕРІРЅРµ РґРІРёР¶РєР°), WebKit.
- РРјРїРѕСЂС‚ СЂРµР·РµСЂРІРЅС‹С… РєРѕРїРёР№ AdsPower РІ РѕРґРёРЅ РєР»РёРє (РєР°Рє С†РµР»РѕР№ РїР°РїРєРё Р±СЌРєР°РїР°, С‚Р°Рє Рё РѕС‚РґРµР»СЊРЅРѕРіРѕ РїСЂРѕС„РёР»СЏ) СЃ СЃРѕС…СЂР°РЅРµРЅРёРµРј user_id, РєСѓРє, РїСЂРѕРєСЃРё Рё С‚РµРіРѕРІ.
- Р”Р°С€Р±РѕСЂРґ СЃ РїРѕРґРґРµСЂР¶РєРѕР№ СЃРІРµС‚Р»РѕР№/С‚РµРјРЅРѕР№ С‚РµРјС‹, РІС‹Р±РѕСЂРѕРј РґРІРёР¶РєР° Рё С„Р»РѕСѓ РёРјРїРѕСЂС‚Р° AdsPower.
- РњР°СЃСЃРѕРІС‹Рµ РѕРїРµСЂР°С†РёРё: Р·Р°РїСѓСЃРє/РѕСЃС‚Р°РЅРѕРІРєР°/СѓРґР°Р»РµРЅРёРµ/СЌРєСЃРїРѕСЂС‚ РЅРµСЃРєРѕР»СЊРєРёС… РїСЂРѕС„РёР»РµР№, РјР°СЃСЃРѕРІС‹Р№ РёРјРїРѕСЂС‚ Рё РЅР°Р·РЅР°С‡РµРЅРёРµ РїСЂРѕРєСЃРё.
- РњРµРЅРµРґР¶РµСЂ РіСЂСѓРїРї Рё С‚РµРіРѕРІ.
- РџСЂРѕРІРµСЂРєР° СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚Рё РїСЂРѕРєСЃРё СЃ РґРµС‚РµРєС†РёРµР№ IP Рё РёР·РјРµСЂРµРЅРёРµРј Р·Р°РґРµСЂР¶РєРё (latency).
- Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ С„РёРЅРіРµСЂРїСЂРёРЅС‚Р° РїСЂСЏРјРѕ РёР· РІРµР±-РёРЅС‚РµСЂС„РµР№СЃР° РґР°С€Р±РѕСЂРґР°.

**Р§РµРј СЌС‚РѕС‚ РїСЂРѕРµРєС‚ РќР• СЏРІР»СЏРµС‚СЃСЏ (РїРѕРєР°):**
- РќРµ headless-С„РµСЂРјР° Р±СЂР°СѓР·РµСЂРѕРІ РЅР° С‚С‹СЃСЏС‡Рё РїСЂРѕС„РёР»РµР№ вЂ” СЂР°СЃСЃС‡РёС‚Р°РЅР° РЅР° РґРµСЃСЏС‚РєРё РїСЂРѕС„РёР»РµР№ РЅР° РјР°С€РёРЅСѓ.
- РќРµ РјСѓР»СЊС‚РёРїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРёР№ auth-СЃР»РѕР№ вЂ” РѕРґРЅРѕРїСЂРѕС†РµСЃСЃРЅС‹Р№, Р±РµР· auth РІ REST API РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ, Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ Р»РѕРєР°Р»СЊРЅРѕ.
- РќРµ РїСЂРѕРІР°Р№РґРµСЂ РїСЂРѕРєСЃРё вЂ” РёСЃРїРѕР»СЊР·СѓРµС‚ РїСЂРѕРєСЃРё, РєРѕС‚РѕСЂС‹Рµ РІС‹ РїСЂРµРґРѕСЃС‚Р°РІР»СЏРµС‚Рµ СЃР°РјРё.

**РљРѕРіРґР° РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ:** РєРѕРіРґР° РЅСѓР¶РЅР° СЃРѕРІРјРµСЃС‚РёРјР°СЏ СЃ AdsPower Р»РѕРєР°Р»СЊРЅР°СЏ С„РµСЂРјР° Р±СЂР°СѓР·РµСЂРѕРІ СЃ РїРѕР»РЅРѕР№ РёР·РѕР»СЏС†РёРµР№ РїСЂРѕС„РёР»РµР№, РєРѕРЅС‚СЂРѕР»РµРј fingerprint Рё РёРјРїРѕСЂС‚РѕРј .adb-Р±Р°РЅРґР»РѕРІ вЂ” Р±РµР· РѕРїР»Р°С‚С‹ AdsPower.

**РљРѕРіРґР° РќР• РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ:** РєРѕРіРґР° РЅСѓР¶РЅС‹ >100 РѕРґРЅРѕРІСЂРµРјРµРЅРЅС‹С… РєРѕРЅС‚РµРєСЃС‚РѕРІ Р±СЂР°СѓР·РµСЂР° РЅР° РѕРґРЅРѕР№ РјР°С€РёРЅРµ, РєРѕРіРґР° РЅСѓР¶РµРЅ cross-process sharing РїСЂРѕС„РёР»РµР№, РёР»Рё РєРѕРіРґР° РЅСѓР¶РЅРѕ СѓРїСЂР°РІР»СЏРµРјРѕРµ РѕР±Р»Р°С‡РЅРѕРµ СЂРµС€РµРЅРёРµ.

---

## 2. Р‘С‹СЃС‚СЂС‹Р№ СЃС‚Р°СЂС‚

### РўСЂРµР±РѕРІР°РЅРёСЏ

- Python 3.10+
- Windows / macOS / Linux
- Playwright (`pip install playwright && playwright install chromium`)

### РЈСЃС‚Р°РЅРѕРІРєР°

```bash
git clone https://github.com/<your-org>/antique
cd antique
python -m venv .venv && source .venv/bin/activate   # РёР»Рё .venv\Scripts\activate РЅР° Windows
pip install -e .
playwright install chromium
```

### Р—Р°РїСѓСЃРє СЃРµСЂРІРµСЂР°

```bash
python -m src.cli serve --ui-port 8080
```

Р­С‚Рѕ РґР°С‘С‚ РІР°Рј:

- Dashboard: <http://127.0.0.1:8080/>
- REST API: <http://127.0.0.1:8080/user/list>
- API docs: <http://127.0.0.1:8080/docs>
- Health: <http://127.0.0.1:8080/health>

### РЎРѕР·РґР°С‚СЊ РїСЂРѕС„РёР»СЊ Рё Р·Р°РїСѓСЃС‚РёС‚СЊ РµРіРѕ

```bash
# Create a profile
python -m src.cli create "My first profile" --tags test

# List profiles
python -m src.cli list

# Launch (prints debug port + websocket endpoint)
python -m src.cli start <user_id>

# Stop
python -m src.cli stop <user_id>
```

РР»Рё С‡РµСЂРµР· REST API:

```bash
curl -X POST http://127.0.0.1:8080/user/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Profile 1", "tags": ["test"]}'

curl -X POST http://127.0.0.1:8080/user/start \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<user_id>"}'
```

### РРјРїРѕСЂС‚ AdsPower `.adb`-Р±Р°РЅРґР»Р°

```bash
# Cookies only (fast, works with .txt/.json/.adb/.zip/.tar.gz)
python -m src.cli import-cookies path/to/bundle.adb --name "Imported"

# Full profile вЂ” copies LocalStorage + IndexedDB into the new profile
python -m src.cli import-cookies path/to/bundle.adb --full --name "Full import"
```

---

## 3. РћР±Р·РѕСЂ Р°СЂС…РёС‚РµРєС‚СѓСЂС‹

```
                            в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
                            в”‚           FastAPI app            в”‚
                            в”‚   (src/api/server.py + routes)   в”‚
                            в”њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”¤
                            в”‚                                  в”‚
        REST /user/*  в”Ђв”Ђв”Ђв–є   в”‚  ProfileStore (SQLite)           в”‚
        WS /devtools/* в”Ђв”Ђв”Ђв–є  в”‚  BrowserLauncher (Playwright)    в”‚
                            в”‚  CDPProxy (CDP multiplexer)      в”‚
                            в”‚                                  в”‚
                            в””в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”
                                      в”‚          в”‚
                                      в–ј          в–ј
                             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
                             в”‚  data/                  в”‚
                             в”‚  в”њв”Ђ antique.db       в”‚  в†ђ profiles, sessions, tags, groups
                             в”‚  в””в”Ђ profiles/<user_id>/ в”‚  в†ђ Playwright user_data_dir per profile
                             в”‚      в”њв”Ђ Default/         в”‚  в†ђ cookies, cache, Local Storage, IndexedDB
                             в”‚      в””в”Ђ ...              в”‚
                             в””в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”
                                      в”‚
                                      в–ј
                             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
                             в”‚  Chromium (one per      в”‚
                             в”‚  running profile)       в”‚
                             в””в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”
```

**РўСЂРё СЃР»РѕСЏ:**

1. **Storage layer** (`src/core/storage.py`, `src/core/profile.py`) вЂ” SQLModel/SQLite. РџСЂРѕС„РёР»Рё, СЃРµСЃСЃРёРё, С‚РµРіРё, РіСЂСѓРїРїС‹, proxy/fingerprint/cookies РєР°Рє JSON-РєРѕРґРёСЂРѕРІР°РЅРЅС‹Рµ РєРѕР»РѕРЅРєРё.
2. **Browser layer** (`src/core/browser.py`, `src/core/cdp.py`, `src/core/fingerprint.py`, `src/core/cookie.py`) вЂ” Playwright persistent contexts, РёРЅР¶РµРєС†РёСЏ fingerprint JS, CDP multiplexer, РёРјРїРѕСЂС‚ cookie/РїСЂРѕС„РёР»СЏ.
3. **Interface layer** (`src/api/server.py`, `src/api/routes.py`, `src/cli.py`, `src/ui/dashboard.py`) вЂ” FastAPI REST + WS, typer CLI, РѕРґРЅРѕСЃС‚СЂР°РЅРёС‡РЅС‹Р№ HTML-dashboard.

---

## 4. РљР°СЂС‚Р° РјРѕРґСѓР»РµР№

```
src/
в”њв”Ђв”Ђ __init__.py
в”њв”Ђв”Ђ cli.py                         в†ђ typer CLI (serve, create, list, start, stop, delete,
в”‚                                    import-cookies, reimport, export-cookies, fingerprint)
в”њв”Ђв”Ђ core/
в”‚   в”њв”Ђв”Ђ __init__.py
в”‚   в”њв”Ђв”Ђ storage.py                 в†ђ SQLModel models (ProfileRecord, SessionRecord, TagRecord,
в”‚   в”‚                                 GroupRecord) + engine/session helpers
в”‚   в”њв”Ђв”Ђ profile.py                 в†ђ Profile dataclass (public) + ProfileStore (CRUD)
в”‚   в”њв”Ђв”Ђ fingerprint.py             в†ђ Fingerprint dataclass + generate_fingerprint() + JS init
в”‚   в”‚                                 script template + Playwright launch options
в”‚   в”њв”Ђв”Ђ proxy.py                   в†ђ ProxyConfig + parse_proxy() + AdsPowerв†”Playwright
в”‚   в”‚                                 shape conversion
в”‚   в”њв”Ђв”Ђ cookie.py                  в†ђ Cookie dataclass, Netscape/JSON/.adb parsers,
в”‚   в”‚                                 LocalStorage + IndexedDB extraction/copying
в”‚   в”њв”Ђв”Ђ browser.py                 в†ђ BrowserLauncher вЂ” Р·Р°РїСѓСЃРєР°РµС‚ РёР·РѕР»РёСЂРѕРІР°РЅРЅС‹Рµ РєРѕРЅС‚РµРєСЃС‚С‹ Chromium,
в”‚   в”‚                                 СЃРѕС…СЂР°РЅСЏРµС‚ СЃРµСЃСЃРёРё, РїСЂРёРјРµРЅСЏРµС‚ РёРјРїРѕСЂС‚РёСЂРѕРІР°РЅРЅРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ
в”‚   в”њв”Ђв”Ђ cdp.py                     в†ђ CDPProxy вЂ” РјСѓР»СЊС‚РёРїР»РµРєСЃРёСЂСѓРµС‚ РѕРґРёРЅ РїРѕСЂС‚ РѕС‚Р»Р°РґРєРё РґР»СЏ
в”‚   в”‚                                 СЂР°Р·РЅС‹С… user_id, РїСЂРµРґРѕСЃС‚Р°РІР»СЏРµС‚ СЂРѕСѓС‚С‹ /json/list + WS
в”‚   в”њв”Ђв”Ђ automation.py              в†ђ Cookie Robot / no-code С„Р»РѕСѓ-СЂР°РЅРЅРµСЂ (РјРѕРґРµР»СЊ Step,
в”‚   в”‚                                 parse_flow, cookie_robot_flow, FlowRunner)
в”‚   в”њв”Ђв”Ђ portable.py                в†ђ РџРѕСЂС‚Р°С‚РёРІРЅС‹Р№ СЌРєСЃРїРѕСЂС‚/РёРјРїРѕСЂС‚ РїСЂРѕС„РёР»РµР№ .antq (build_bundle,
в”‚   в”‚                                 export_profile, import_profile)
в”‚   в”њв”Ђв”Ђ geo.py                     в†ђ РџСЂРёРІСЏР·РєР° Рє СЃС‚СЂР°РЅРµ/РІС‹С…РѕРґСѓ РїСЂРѕРєСЃРё в†’ С‚Р°Р№РјР·РѕРЅР°/Р»РѕРєР°Р»СЊ/СЏР·С‹РєРё/РіРµРѕ
в”‚   в”‚                                 (geo_for_country, geo_from_proxy, apply_geo_to_fingerprint)
в”‚   в”њв”Ђв”Ђ proxy_pool.py              в†ђ РџСѓР» РїСЂРѕРєСЃРё + СЂРѕС‚Р°С†РёСЏ/failover (sticky/round_robin/random)
в”‚   в”њв”Ђв”Ђ detect.py                  в†ђ РЎРµР»С„-С‚РµСЃС‚ РјР°СЃРєРёСЂРѕРІРєРё / РґРµС‚РµРєС‚-С…Р°СЂРЅРµСЃСЃ (build_collector_script, score_report)
в”‚   в”њв”Ђв”Ђ engines.py                 в†ђ Р РµРµСЃС‚СЂ Р±СЂР°СѓР·РµСЂРЅС‹С… РґРІРёР¶РєРѕРІ (EngineSpec, resolve_engine, list_engines)
в”‚   в”њв”Ђв”Ђ sync.py                    в†ђ РЎРёРЅС…СЂРѕРЅРЅР°СЏ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёСЏ РЅР° РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРѕС„РёР»РµР№ (run_sync_flow, FlowTask)
в”‚   в”њв”Ђв”Ђ fingerprint_ops.py         в†ђ СѓРјРЅР°СЏ РјР°СЃСЃРѕРІР°СЏ СЂР°РЅРґРѕРјРёР·Р°С†РёСЏ, РѕР±С‰РёРµ/СЃРѕС…СЂР°РЅСЏРµРјС‹Рµ РіСЂСѓРїРїС‹ РїРѕР»РµР№
в”‚   в”њв”Ђв”Ђ socks_bridge.py            в†ђ РїРµС‚Р»РµРІРѕР№ SOCKS5-РјРѕСЃС‚ Р°РІС‚РѕСЂРёР·Р°С†РёРё РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃ AdsPower/Chromium
в”‚   в”њв”Ђв”Ђ operations.py              в†ђ РјР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РїРѕ С€Р°Р±Р»РѕРЅСѓ, Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹Рµ AES-GCM СЃРЅРёРјРєРё, РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ Р±СЌРєР°РїРѕРІ Рё Р°СѓРґРёС‚
в”‚   в”њв”Ђв”Ђ providers.py               в†ђ РїСЂРѕРІР°Р№РґРµСЂС‹ РїСЂРѕРєСЃРё (File/JSON/HTTP-JSON)
в”‚   в””в”Ђв”Ђ backup_scheduler.py        в†ђ РїР»Р°РЅРёСЂРѕРІС‰РёРє Р»РѕРєР°Р»СЊРЅС‹С… Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹С… СЂРµР·РµСЂРІРЅС‹С… РєРѕРїРёР№
в”њв”Ђв”Ђ api/
в”‚   в”њв”Ђв”Ђ __init__.py
в”‚   в”њв”Ђв”Ђ server.py                  в†ђ FastAPI app factory, CORS, mount UI + API routes
в”‚   в””в”Ђв”Ђ routes.py                  в†ђ All REST endpoints + WS handlers
в””в”Ђв”Ђ ui/
    в”њв”Ђв”Ђ __init__.py
    в”њв”Ђв”Ђ dashboard.py               в†ђ Single-page HTML dashboard router
    в””в”Ђв”Ђ templates/
        в””в”Ђв”Ђ index.html             в†ђ Dashboard SPA (vanilla JS + fetch())

tests/
в”њв”Ђв”Ђ test_fingerprint.py            в†ђ Fingerprint generation, init script injection
в”њв”Ђв”Ђ test_cookie.py                 в†ђ Cookie parsing (all formats) + .adb bundle handling
в”њв”Ђв”Ђ test_profile.py                в†ђ ProfileStore CRUD
в”њв”Ђв”Ђ test_proxy.py                  в†ђ Proxy config validation
в”њв”Ђв”Ђ test_storage.py                в†ђ SQLite engine + migrations
в””в”Ђв”Ђ test_profile_import.py         в†ђ Full-profile .adb import flow (NEW)
```

---

## 5. РњРѕРґРµР»СЊ РґР°РЅРЅС‹С… Рё СЃС…РµРјР° С…СЂР°РЅРёР»РёС‰Р°

Р‘Р°Р·Р° РґР°РЅРЅС‹С…: `data/antique.db` (SQLite, РѕРґРёРЅ С„Р°Р№Р»).

### РўР°Р±Р»РёС†С‹

```sql
-- Profiles: one row per browser profile
CREATE TABLE profiles (
    user_id                  TEXT PRIMARY KEY,    -- 8-char base36 random id
    name                     TEXT NOT NULL,
    group_id                 TEXT NOT NULL DEFAULT '0',
    user_proxy_config        TEXT NOT NULL DEFAULT '{}',  -- JSON
    fingerprint_config       TEXT NOT NULL DEFAULT '{}',  -- JSON of Fingerprint dataclass
    cookies                  TEXT NOT NULL DEFAULT '[]',  -- JSON list of cookie dicts
    tags                     TEXT NOT NULL DEFAULT '[]',  -- JSON list of strings
    remark                   TEXT NOT NULL DEFAULT '',
    import_source_path       TEXT NOT NULL DEFAULT '',   -- path to extracted .adb bundle
    initial_state_applied    INTEGER NOT NULL DEFAULT 0, -- bool: has LocalStorage/IDB been copied?
    created_at               DATETIME,
    updated_at               DATETIME,
    last_launched_at         DATETIME,
    launch_count             INTEGER NOT NULL DEFAULT 0
);

-- Sessions: one row per running browser
CREATE TABLE sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES profiles(user_id),
    debug_port   INTEGER NOT NULL,
    ws_endpoint  TEXT NOT NULL,
    pid          INTEGER,
    started_at   DATETIME,
    status       TEXT NOT NULL DEFAULT 'running'   -- running | stopped | crashed
);

CREATE TABLE tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT UNIQUE NOT NULL,
    color TEXT NOT NULL DEFAULT '#888888'
);

CREATE TABLE groups (
    group_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
```

### РџРѕС‡РµРјСѓ JSON-РєРѕРґРёСЂРѕРІР°РЅРЅС‹Рµ РєРѕР»РѕРЅРєРё?

Proxies, fingerprints Рё cookies вЂ” СЌС‚Рѕ РіРµС‚РµСЂРѕРіРµРЅРЅС‹Рµ dicts/lists СЃРѕ РјРЅРѕР¶РµСЃС‚РІРѕРј РѕРїС†РёРѕРЅР°Р»СЊРЅС‹С… РїРѕР»РµР№. JSON-РєРѕРґРёСЂРѕРІР°РЅРЅС‹Рµ TEXT-РєРѕР»РѕРЅРєРё РїРѕР·РІРѕР»СЏСЋС‚ РёР·Р±РµР¶Р°С‚СЊ sparse-tables-of-many-columns Рё СѓРїСЂРѕС‰Р°СЋС‚ РјРёРіСЂР°С†РёРё. Р¦РµРЅР°: РЅРµС‚ SQL-СѓСЂРѕРІРЅСЏ РґР»СЏ Р·Р°РїСЂРѕСЃРѕРІ РїРѕ РїРѕР»СЏРј fingerprint, РЅРѕ РѕРЅ РЅР°Рј Рё РЅРµ РЅСѓР¶РµРЅ.

### Profile dataclass vs ProfileRecord

- `Profile` (РІ `src/core/profile.py`) вЂ” РїСѓР±Р»РёС‡РЅС‹Р№ dataclass. РћС‚РґРµР»С‘РЅ РѕС‚ storage, С‡С‚РѕР±С‹ API РЅРµ СѓС‚РµРєР°Р» SQLModel РЅР°СЂСѓР¶Сѓ.
- `ProfileRecord` (РІ `src/core/storage.py`) вЂ” СЃРѕС…СЂР°РЅСЏРµРјР°СЏ СЃС‚СЂРѕРєР°. `_record_to_profile()` СЃРѕР±РёСЂР°РµС‚ `Profile` РёР· `ProfileRecord`.

---

## 6. Р–РёР·РЅРµРЅРЅС‹Р№ С†РёРєР» РїСЂРѕС„РёР»СЏ

```
             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
             в”‚ created  в”‚  в†ђ POST /user/create, cli create, import-cookies
             в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                  в”‚
                  в–ј
             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
             в”‚ idle     в”‚  в†ђ profile exists, browser not running
             в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                  в”‚  POST /user/start  or  cli start
                  в–ј
             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
             в”‚ running  в”‚  в†ђ Playwright persistent context is live
             в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                  в”‚  POST /user/stop  or  cli stop
                  в–ј
             в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
             в”‚ stopped  в”‚  в†ђ context closed, SessionRecord.status = 'stopped'
             в””в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”

   (any state) в”Ђв”Ђв–є deleted   в†ђ POST /user/delete, cli delete (cascades to sessions)
```

### Р–РёР·РЅРµРЅРЅС‹Р№ С†РёРєР» РёРјРїРѕСЂС‚Р° РїРѕР»РЅРѕРіРѕ РїСЂРѕС„РёР»СЏ (РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ)

```
  created в†’ import_source_path set в†’ (first launch) в†’ LocalStorage/IDB copied
                                                             в†’ initial_state_applied = True
                                                             в†’ (later launches skip the copy)
```

Р¤Р»Р°Рі `initial_state_applied` РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РјС‹ РєРѕРїРёСЂСѓРµРј `Local Storage/leveldb/` Рё `IndexedDB/` РёСЃС…РѕРґРЅРѕРіРѕ Р±Р°РЅРґР»Р° С‚РѕР»СЊРєРѕ РѕРґРёРЅ СЂР°Р·. Р”Р»СЏ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РёРјРїРѕСЂС‚Р° РЅСѓР¶РЅС‹ `cli reimport <user_id>` РёР»Рё `POST /user/{id}/reimport`, РєРѕС‚РѕСЂС‹Рµ СЃР±СЂР°СЃС‹РІР°СЋС‚ С„Р»Р°Рі.

---

## 7. РЎРїСЂР°РІРѕС‡РЅРёРє РїРѕ CLI

```text
python -m src.cli serve [--ui-port 8080] [--cdp-port 5555] [--host 127.0.0.1] [--headless]
python -m src.cli list [--search TEXT] [--group ID] [--tag TEXT]
python -m src.cli create NAME [--group ID] [--proxy-type TYPE] [--proxy-host HOST]
                          [--proxy-port PORT] [--proxy-user U] [--proxy-password P]
                          [--remark TEXT] [--tags t1,t2] [--user-id ID]
                          [--fingerprint-seed SEED]
python -m src.cli start USER_ID [--port DEBUG_PORT]
python -m src.cli stop USER_ID
python -m src.cli delete USER_ID [--yes]
python -m src.cli import-cookies PATH [--name NAME] [--proxy-type TYPE] [--full]
python -m src.cli reimport USER_ID
python -m src.cli export-cookies USER_ID [--format json|netscape] [--out FILE]
python -m src.cli export-profile USER_ID [--out FILE.antq]
python -m src.cli import-profile FILE.antq [--name NAME] [--user-id ID]
python -m src.cli warm USER_ID [--url URL ...] [--urls FILE] [--dwell-min MS] [--dwell-max MS] [--scrolls N] [--headless]
python -m src.cli run-flow USER_ID FLOW.json [--stop-on-error] [--headless]
python -m src.cli detect-test USER_ID [--url URL] [--headless]   # СЃРµР»С„-С‚РµСЃС‚ РјР°СЃРєРёСЂРѕРІРєРё СЃ РѕС†РµРЅРєРѕР№ A-F
python -m src.cli create ... [--geo-country US|DE|RU|...]        # СЃРѕР·РґР°РЅРёРµ РїСЂРѕС„РёР»СЏ СЃ РїСЂРёРІСЏР·РєРѕР№ Рє СЃС‚СЂР°РЅРµ
python -m src.cli engines                                        # СЃРїРёСЃРѕРє РїРѕРґРґРµСЂР¶РёРІР°РµРјС‹С… РґРІРёР¶РєРѕРІ Рё РёС… СЃС‚РµР»СЃ-СѓСЂРѕРІРЅРµР№
python -m src.cli create ... [--engine chromium|chrome|edge|firefox|camoufox|webkit] # СЃРѕР·РґР°РЅРёРµ СЃ СѓРєР°Р·Р°РЅРёРµРј РґРІРёР¶РєР°
python -m src.cli import-backup PATH [--overwrite] [--limit N]   # РёРјРїРѕСЂС‚ РїР°РїРєРё СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё AdsPower
python -m src.cli set-status USER_ID STATUS                     # РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР°: new|warming|active|limited|banned|retired
python -m src.cli sync FLOW.json -u USER_ID -u USER_ID [...]    # РѕРґРёРЅ С„Р»РѕСѓ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёРё СЃСЂР°Р·Сѓ РЅР° РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРѕС„РёР»РµР№
python -m src.cli create ... [--status active]                  # СЃРѕР·РґР°РЅРёРµ СЃ СѓРєР°Р·Р°РЅРёРµРј СЃС‚Р°С‚СѓСЃР°
python -m src.cli clone USER_ID [--name NAME] [--user-id NEW_ID] # РєР»РѕРЅРёСЂРѕРІР°РЅРёРµ РїСЂРѕС„РёР»СЏ
python -m src.cli bulk-status USER_ID [USER_ID ...] STATUS      # РјР°СЃСЃРѕРІРѕРµ РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃРѕРІ Р°РєРєР°СѓРЅС‚РѕРІ
python -m src.cli list ... [--sort name|launches|...] [--order asc|desc] # РІС‹РІРѕРґ СЃРїРёСЃРєР° СЃ СЃРѕСЂС‚РёСЂРѕРІРєРѕР№
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
python -m src.cli preview-backup PATH                                # РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ Р±СЌРєР°РїР° AdsPower Р±РµР· Р·Р°РїРёСЃРё
python -m src.cli template-create TEMPLATE.json [--count N] [--seed S] # РјР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РїРѕ С€Р°Р±Р»РѕРЅСѓ
python -m src.cli snapshot-export PATH                               # СЃРѕР·РґР°РЅРёРµ Р·Р°С€РёС„СЂРѕРІР°РЅРЅРѕРіРѕ СЃРЅРёРјРєР° РїСЂРѕС„РёР»РµР№ (AES-GCM)
python -m src.cli snapshot-import PATH [--overwrite]                 # РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РїСЂРѕС„РёР»РµР№ РёР· Р·Р°С€РёС„СЂРѕРІР°РЅРЅРѕРіРѕ СЃРЅРёРјРєР°
python -m src.cli activity [--user USER_ID] [--limit N]              # РІС‹РІРѕРґ РёСЃС‚РѕСЂРёРё Р°СѓРґРёС‚Р° Р°РєС‚РёРІРЅРѕСЃС‚Рё
python -m src.cli backup-schedule DESTINATION [--interval-minutes MIN] # СЂРµРіРёСЃС‚СЂР°С†РёСЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ Р·Р°С€РёС„СЂРѕРІР°РЅРЅРѕРіРѕ СЂР°СЃРїРёСЃР°РЅРёСЏ
python -m src.cli backup-schedules                                   # РІС‹РІРѕРґ СЃРїРёСЃРєР° Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅРЅС‹С… СЂР°СЃРїРёСЃР°РЅРёР№ СЂРµР·РµСЂРІРЅРѕРіРѕ РєРѕРїРёСЂРѕРІР°РЅРёСЏ
```

### РљРѕРґС‹ РІРѕР·РІСЂР°С‚Р°

- `0` вЂ” СѓСЃРїРµС…
- `1` вЂ” РѕС€РёР±РєР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ Р°СЂРіСѓРјРµРЅС‚С‹, РїСЂРѕС„РёР»СЊ РЅРµ РЅР°Р№РґРµРЅ, РЅРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚)
- РЅРµРЅСѓР»РµРІРѕР№ РѕС‚ typer РґР»СЏ РѕС€РёР±РѕРє shell

### РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ

РЎРјРѕС‚СЂРёС‚Рµ [РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ](#16-РїРµСЂРµРјРµРЅРЅС‹Рµ-РѕРєСЂСѓР¶РµРЅРёСЏ).

---

## 8. РЎРїСЂР°РІРѕС‡РЅРёРє РїРѕ REST API

Base URL: `http://127.0.0.1:<ui-port>` (С‚РѕС‚ Р¶Рµ РїРѕСЂС‚ РѕР±СЃР»СѓР¶РёРІР°РµС‚ UI + API; AdsPower РёСЃРїРѕР»СЊР·СѓРµС‚ 50325 РѕС‚РґРµР»СЊРЅРѕ).

Р’СЃРµ РѕС‚РІРµС‚С‹ РёСЃРїРѕР»СЊР·СѓСЋС‚ С„РѕСЂРјСѓ AdsPower: `{"code": 0, "msg": "success", "data": {...}}`.

### Health

```http
GET /health
в†’ {"status": "ok", "service": "antique", "version": "0.1.0"}
```

### РџСЂРѕС„РёР»Рё

```http
POST /user/create
Body: {
  "name": "string",
  "group_id": "0" (optional),
  "user_proxy_config": {"proxy_type":"http","proxy_host":"...","proxy_port":...} (optional),
  "fingerprint_config": {...} (optional, partial Fingerprint allowed),
  "cookies": [{"name":"x","value":"y","domain":".example.com",...}] (optional),
  "remark": "string" (optional),
  "tags": ["string"] (optional),
  "user_id": "string" (optional, generated if omitted)
}
в†’ {code:0, msg:"success", data:{id, user_id, name}}

POST /user/update
Body: {user_id, name?, group_id?, user_proxy_config?, fingerprint_config?,
       cookies?, remark?, tags?}
в†’ {code:0, msg:"success", data:{id, user_id, name}}

GET /user/list?group_id=&page=1&page_size=100&search=&tag=
в†’ {code:0, msg:"success", data:{list:[Profile...], total, page, page_size}}

POST /user/delete
Body: {user_id}
в†’ {code:0, msg:"success", data:{user_id, deleted:true}}

POST /user/start
Body: {user_id, debug_port? (optional), launch_args? (optional, unused)}
в†’ {code:0, msg:"success", data:{user_id, debug_port, ws_endpoint, pid, session_id}}

POST /user/stop
Body: {user_id}
в†’ {code:0, msg:"success", data:{user_id, stopped:true|false}}

GET /user/active
в†’ {code:0, msg:"success", data:{list:[{user_id, session_id, debug_port,
                                        ws_endpoint, pid}]}}

POST /user/import
Body: {name, source_path}   OR   multipart file=@bundle.adb
в†’ creates a profile from an AdsPower bundle (cookies-only by default,
  set Content-Type with multipart to use the full extraction path)

POST /user/{user_id}/reimport
в†’ resets initial_state_applied so the next launch re-copies LocalStorage/IDB
  from the saved bundle path
```

### Geo / proxy-pool / portable / detect / chain (v0.2)

```http
GET  /geo/countries
в†’ {code:0, data:{countries:["US","DE",...]}}

POST /user/{user_id}/geo/match      Body: {country?: "DE"}   # РµСЃР»Рё РЅРµ РїРµСЂРµРґР°РЅРѕ, Р±РµСЂРµС‚СЃСЏ РёР· РїСЂРѕРєСЃРё РїСЂРѕС„РёР»СЏ
в†’ СЃРёРЅС…СЂРѕРЅРёР·РёСЂСѓРµС‚ timezone/locale/languages/geolocation Рё СЃРѕС…СЂР°РЅСЏРµС‚ РІ fingerprint

POST /proxy/pool/next               Body: {proxy_list, strategy?: sticky|round_robin|random, user_id?}
в†’ {code:0, data:{proxy:{...}, assigned, server}}   # РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ РїСЂРёРІСЏР·С‹РІР°РµС‚ Рє user_id

POST /user/{user_id}/export/portable
в†’ {code:0, data:{bundle:{...}}}   # .antq Р±Р°РЅРґР» (fingerprint+proxy+cookies+tags)

POST /user/import/portable          Body: {bundle:{...}, name?, user_id?}
в†’ {code:0, data:{user_id, name, cookie_count}}

POST /detect/score                  Body: {signals:{...}, expected?:{...}}
в†’ {code:0, data:{score, grade, ok, checks, failures}}   # С‡РёСЃС‚С‹Р№ СЃРєРѕСЂРёРЅРі СЃРєСЂС‹С‚РЅРѕСЃС‚Рё, Р±РµР· Р±СЂР°СѓР·РµСЂР°

GET  /engine/list
в†’ {code:0, data:{list:[{key,label,base,stealth,channel,needs_install,supports_extensions,supports_cdp}]}}

POST /user/import/backup            Body: {source_path, overwrite?, limit?}
в†’ {code:0, data:{imported_count, updated_count, skipped_count, error_count, cookie_sources, ...}}

POST /user/import/backup/preview    Body: {source_path}
в†’ {code:0, data:{profiles:[...], total_count, groups:[...], tags:[...]}}  # РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ Р±СЌРєР°РїР° AdsPower

POST /user/template/create          Body: {template, count, seed?}
в†’ {code:0, data:{created_count, user_ids:[...]}}  # РјР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РїРѕ С€Р°Р±Р»РѕРЅСѓ

POST /user/snapshot/export          Body: {path, password, overwrite?}
в†’ {code:0, data:{path}}                           # СЃРѕР·РґР°РЅРёРµ Р·Р°С€РёС„СЂРѕРІР°РЅРЅРѕРіРѕ СЃРЅРёРјРєР° (AES-GCM)

POST /user/snapshot/import          Body: {path, password, overwrite?}
в†’ {code:0, data:{imported_count, updated_count, skipped_count}} # РёРјРїРѕСЂС‚ СЃРЅРёРјРєР°

GET  /activity?user_id=...&action=...&limit=...  в†’ СЃРїРёСЃРѕРє СЃРѕР±С‹С‚РёР№ РёСЃС‚РѕСЂРёРё Р°СѓРґРёС‚Р° Р°РєС‚РёРІРЅРѕСЃС‚Рё СЃ С„РёР»СЊС‚СЂР°С†РёРµР№

POST /activity/export               Body: {path, user_id?, action?}
в†’ {code:0, data:{path, count}}      # СЌРєСЃРїРѕСЂС‚ РѕС‚С„РёР»СЊС‚СЂРѕРІР°РЅРЅС‹С… СЃРѕР±С‹С‚РёР№ Р°РєС‚РёРІРЅРѕСЃС‚Рё РІ JSON-С„Р°Р№Р»

GET  /resource/status                в†’ СЃС‚Р°С‚РёСЃС‚РёРєР° СЂРµСЃСѓСЂСЃРѕРІ (PID, РєРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РїСѓС‰РµРЅРЅС‹С… РїСЂРѕС„РёР»РµР№)

GET  /mcp/status                     в†’ СЃС‚Р°С‚СѓСЃ MCP-СЃРµСЂРІРµСЂР° Рё СЃРїРёСЃРѕРє РґРѕСЃС‚СѓРїРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ

GET  /proxy/providers/kinds          в†’ РїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Рµ Р»РѕРєР°Р»СЊРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ РїСЂРѕРєСЃРё (file, json, http-json)

POST /proxy/providers/test          Body: {name, kind, source, enabled?}
в†’ {code:0, data:{provider, count, proxies:[...]}} # С‚РµСЃС‚ Р·Р°РіСЂСѓР·РєРё РїСЂРѕРєСЃРё РёР· Р»РѕРєР°Р»СЊРЅРѕРіРѕ РїСЂРѕРІР°Р№РґРµСЂР°

POST /backup/schedules              Body: {destination, interval_minutes}
в†’ {code:0, data:{schedule:{schedule_id, destination, interval_minutes, enabled, next_run_at, last_run_at}}} # РґРѕР±Р°РІР»РµРЅРёРµ СЂР°СЃРїРёСЃР°РЅРёСЏ

GET  /backup/schedules              в†’ РїРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° РІСЃРµС… СЂР°СЃРїРёСЃР°РЅРёР№ СЂРµР·РµСЂРІРЅРѕРіРѕ РєРѕРїРёСЂРѕРІР°РЅРёСЏ

POST /backup/schedules/run          Body: {schedule_id, password}
в†’ {code:0, data:{schedule:{...}}}   # СЂСѓС‡РЅРѕР№ Р·Р°РїСѓСЃРє Р·Р°С€РёС„СЂРѕРІР°РЅРЅРѕРіРѕ СЂРµР·РµСЂРІРЅРѕРіРѕ РєРѕРїРёСЂРѕРІР°РЅРёСЏ РїРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ

POST /group/create                  Body: {group_id, name, sort_order?, parent_id?}
в†’ {code:0, data:{group_id, name}}                 # СЃРѕР·РґР°РЅРёРµ РіСЂСѓРїРїС‹ (РїРѕРґРґРµСЂР¶РёРІР°РµС‚ parent_id РґР»СЏ РІР»РѕР¶РµРЅРЅРѕСЃС‚Рё)

POST /group/update                  Body: {group_id, name, sort_order?, parent_id?}
в†’ {code:0, data:{group_id, name}}                 # РёР·РјРµРЅРµРЅРёРµ РіСЂСѓРїРїС‹

POST /group/delete                  Body: {group_id} (embed=True)
в†’ {code:0, data:{group_id, deleted:true}}         # СѓРґР°Р»РµРЅРёРµ РіСЂСѓРїРїС‹

GET  /extension/list                в†’ СЃРїРёСЃРѕРє РІСЃРµС… СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹С… РіР»РѕР±Р°Р»СЊРЅС‹С… СЂР°СЃС€РёСЂРµРЅРёР№

POST /extension/install             Body: {source}
в†’ {code:0, data:{ext_id, name, version}} # СѓСЃС‚Р°РЅРѕРІРєР° СЂР°СЃРїР°РєРѕРІР°РЅРЅРѕРіРѕ РєР°С‚Р°Р»РѕРіР°, .crx РёР»Рё РїРѕ Web Store ID

POST /extension/uninstall           Body: {ext_id} (embed=True)
в†’ {code:0, data:{ext_id, uninstalled:true}} # СѓРґР°Р»РµРЅРёРµ СЂР°СЃС€РёСЂРµРЅРёСЏ

POST /user/{user_id}/extensions     Body: List[str] (IDs СЂР°СЃС€РёСЂРµРЅРёР№)
в†’ {code:0, data:{user_id, extensions:[...]}} # РїСЂРёРІСЏР·РєР° СЂР°СЃС€РёСЂРµРЅРёР№ Рє РїСЂРѕС„РёР»СЋ

GET  /user/{user_id}/extensions     в†’ РїРѕР»СѓС‡РёС‚СЊ ID СЂР°СЃС€РёСЂРµРЅРёР№, РЅР°Р·РЅР°С‡РµРЅРЅС‹С… РїСЂРѕС„РёР»СЋ

POST /user/clone                    Body: {user_id, name?, user_id_override?}
в†’ {code:0, data:{user_id, name, source_user_id}}

POST /user/bulk/status              Body: {user_ids:[...], account_status}
в†’ {code:0, data:{results:[{user_id, ok, error?}], updated_count}}

POST /user/bulk/fingerprint/randomize
Body: {user_ids:[...], os_family?, shared_fields?:["screen","gpu",...], preserve_fields?:["engine",...], seed?}
в†’ {code:0, data:{updated_count, user_ids:[...]}}

GET  /status/list                   в†’ СЃРїРёСЃРѕРє РїСЂРµРґСѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹С… СЃС‚Р°С‚СѓСЃРѕРІ Р°РєРєР°СѓРЅС‚РѕРІ
POST /user/{user_id}/status         Body: {account_status}
POST /user/{user_id}/screenshot     в†’ {code:0, data:{base64_png}}   # Live View СЃРєСЂРёРЅС€РѕС‚ (РїСЂРѕС„РёР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°РїСѓС‰РµРЅ)
GET  /user/{user_id}/cdp            в†’ {code:0, data:{webSocketDebuggerUrl, debug_port, ...}}  # РїРѕР»СѓС‡РµРЅРёРµ СЂРµР°Р»СЊРЅРѕРіРѕ CDP
POST /sync/run                      Body: {user_ids:[...], flow:[...], stop_on_error?, max_concurrency?}
в†’ {code:0, data:{ok, succeeded, total, results:[{user_id, ok, completed, total, error}]}}
```

### Р¤РѕСЂРјР° РїСЂРѕС„РёР»СЏ, РІРѕР·РІСЂР°С‰Р°РµРјР°СЏ `/user/list`

```json
{
  "user_id": "k7m3x9p2",
  "name": "Profile 1",
  "group_id": "0",
  "created_at": "2026-06-30T10:00:00",
  "updated_at": "2026-06-30T10:00:00",
  "last_launched_at": null,
  "launch_count": 0,
  "remark": "",
  "tags": [],
  "user_proxy_config": {},
  "fingerprint_config": {},
  "cookies": [],
  "status": "Inactive",
  "debug_port": null,
  "ws_endpoint": null
}
```

### CDP multiplexer

```http
GET /json/version
в†’ {Browser, Protocol-Version, User-Agent, webSocketDebuggerUrl, ...}

GET /json/list?user_id=<id>
в†’ [{id, type:"page", title, url, webSocketDebuggerUrl, description}, ...]

WS /devtools/page/{user_id}/{target_id}
в†’ Chromium DevTools Protocol websocket
```

---

## 9. Р¤РѕСЂРјР°С‚С‹ РёРјРїРѕСЂС‚Р°/СЌРєСЃРїРѕСЂС‚Р° cookies

### РџРѕРґРґРµСЂР¶РёРІР°РµРјС‹Рµ С„РѕСЂРјР°С‚С‹ РёРјРїРѕСЂС‚Р°

| Format | Detection | Notes |
|---|---|---|
| Netscape `cookies.txt` | `.txt` extension | curl/wget format; tabs or spaces |
| Playwright/CDP JSON | `.json` extension | list of `{name, value, domain, ...}` dicts |
| AdsPower `.adb` | `.adb` / `.zip` / `.tar` / `.tgz` / folder | cookies + LocalStorage + IndexedDB |

### РџРѕРґРґРµСЂР¶РёРІР°РµРјС‹Рµ С„РѕСЂРјР°С‚С‹ СЌРєСЃРїРѕСЂС‚Р°

- `json` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ) вЂ” С„РѕСЂРјР° Playwright/Chrome DevTools
- `netscape` вЂ” СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ `cookies.txt`, СЃРѕРІРјРµСЃС‚РёРјС‹Р№ СЃ curl

### РђРІС‚РѕРѕРїСЂРµРґРµР»РµРЅРёРµ РІ `import_cookies(path)`

```python
def import_cookies(path):
    p = Path(path)
    if p.is_dir() or p.suffix.lower() in (".adb", ".zip", ".tar", ".tgz"):
        return import_adspower_profile(p)
    if p.suffix.lower() == ".json":
        return import_cookies_json(p.read_text())
    return import_cookies_netscape(p.read_text())
```

### РџР°СЂСЃРёРЅРі AdsPower `.adb`

`.adb` вЂ” СЌС‚Рѕ Р±Р°РЅРґР» Chrome user-profile (РїР°РїРєР°, `.zip` РёР»Рё `.tar.gz`). РўР°Р±Р»РёС†Р° cookies Chromium РЅР°С…РѕРґРёС‚СЃСЏ РІ `<profile>/Default/Cookies` (SQLite).

РџР°СЂСЃРµСЂ:

1. Р Р°СЃРїР°РєРѕРІС‹РІР°РµС‚ Р°СЂС…РёРІ РІРѕ РІСЂРµРјРµРЅРЅСѓСЋ РґРёСЂРµРєС‚РѕСЂРёСЋ (РµСЃР»Рё РЅСѓР¶РЅРѕ).
2. РС‰РµС‚ С„Р°Р№Р»С‹ `*/Cookies`; РїСЂРµРґРїРѕС‡РёС‚Р°РµС‚ `Default/Cookies`, РёРЅР°С‡Рµ РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ Рє `Profile 1/2/3/Cookies`.
3. РћС‚РєСЂС‹РІР°РµС‚ SQLite DB РІ RO-СЂРµР¶РёРјРµ (`file:...?mode=ro`); РµСЃР»Рё Р·Р°Р»РѕС‡РµРЅР° вЂ” РѕС‚РєР°С‚С‹РІР°РµС‚СЃСЏ РЅР° РїСЂРёРІР°С‚РЅСѓСЋ РІСЂРµРјРµРЅРЅСѓСЋ РєРѕРїРёСЋ.
4. Р§РёС‚Р°РµС‚ С‚Р°Р±Р»РёС†Сѓ cookies. РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РІР°СЂРёР°С†РёРё СЃС…РµРјС‹ (РІ СЃС‚Р°СЂРѕРј Chrome РЅРµС‚ РєРѕР»РѕРЅРѕРє `samesite` Рё `is_persistent`).
5. РљРѕРЅРІРµСЂС‚РёСЂСѓРµС‚ `expires_utc` Chrome (Windows FILETIME, РјРёРєСЂРѕСЃРµРєСѓРЅРґС‹ СЃ 1601-01-01) РІ Unix epoch-СЃРµРєСѓРЅРґС‹.

---

## 10. РЎРёСЃС‚РµРјР° fingerprint

`Fingerprint` вЂ” СЌС‚Рѕ СЃРѕРіР»Р°СЃРѕРІР°РЅРЅС‹Р№ РЅР°Р±РѕСЂ Р°С‚СЂРёР±СѓС‚РѕРІ, РІРёРґРёРјС‹С… Р±СЂР°СѓР·РµСЂСѓ:

- **Identity**: User-Agent, navigator.platform/vendor/oscpu, С„Р»Р°Рі webdriver
- **Screen**: width/height/colorDepth/pixelRatio + window.innerWidth/Height
- **Locale / timezone**: navigator.languages, Intl timezone
- **WebGL**: СЃС‚СЂРѕРєРё vendor + renderer (С‡РµСЂРµР· `WEBGL_debug_renderer_info`)
- **WebGPU**: РІРµРЅРґРѕСЂ/Р°СЂС…РёС‚РµРєС‚СѓСЂР°/РѕРїРёСЃР°РЅРёРµ Р°РґР°РїС‚РµСЂР° (С‡РµСЂРµР· `navigator.gpu.requestAdapter().requestAdapterInfo()`), СЃРѕРіР»Р°СЃРѕРІР°РЅРѕ СЃ WebGL GPU; РїСЂРѕС„РёР»Рё СЃРѕ РІСЃС‚СЂРѕРµРЅРЅС‹Рј (software) СЂРµРЅРґРµСЂРѕРј РѕС‚РєР»СЋС‡Р°СЋС‚ `navigator.gpu`
- **РЁСЂРёС„С‚С‹**: Р±РµР»С‹Р№ СЃРїРёСЃРѕРє СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹С… С€СЂРёС„С‚РѕРІ РїРѕРґ РєР°Р¶РґСѓСЋ РћРЎ, С„РѕСЂСЃРёСЂСѓРµС‚СЃСЏ С‡РµСЂРµР· `document.fonts.check`
- **Audio**: РґРµС‚РµСЂРјРёРЅРёСЂРѕРІР°РЅРЅС‹Р№ noise seed РґР»СЏ РґР¶РёС‚С‚РµСЂР° AudioContext
- **Canvas**: РґРµС‚РµСЂРјРёРЅРёСЂРѕРІР°РЅРЅС‹Р№ noise seed РґР»СЏ РїРёРєСЃРµР»СЊРЅРѕРіРѕ РґР¶РёС‚С‚РµСЂР° `toDataURL`/`toBlob`
- **WebRTC**: РїСЂРµРґРѕС‚РІСЂР°С‰РµРЅРёРµ СѓС‚РµС‡РєРё IP вЂ” `webrtc_mode` (`block` | `real` | `proxy`), Р»РµРіР°СЃРё-С„Р»Р°Рі `block_webrtc_ip` РїРѕ-РїСЂРµР¶РЅРµРјСѓ СѓС‡РёС‚С‹РІР°РµС‚СЃСЏ
- **Plugins**: СЂРµР°Р»РёСЃС‚РёС‡РЅС‹Р№ СЃРїРёСЃРѕРє РїР»Р°РіРёРЅРѕРІ Chrome (2-5 Р·Р°РїРёСЃРµР№)
- **Connection**: type/downlink/rtt (Network Information API)
- **Hardware**: hardwareConcurrency, deviceMemory

### Р“РµРЅРµСЂР°С†РёСЏ

```python
from src.core.fingerprint import generate_fingerprint

fp = generate_fingerprint()                                  # random
fp = generate_fingerprint(seed="my-profile-1")               # deterministic
fp = generate_fingerprint(os_family="macos")                 # macOS UA + screen
```

РџСЂР°РІРёР»Р° СЃРѕРіР»Р°СЃРѕРІР°РЅРЅРѕСЃС‚Рё:
- РЎРµРјРµР№СЃС‚РІРѕ РћРЎ в†” UA в†” platform в†” vendor в†” screen
- Locale в†” РїСѓР» timezone (РЅР°РїСЂРёРјРµСЂ, `en-GB` в†’ `Europe/London`)
- WebGL vendor в†” renderer (NVIDIA vendor РЅРёРєРѕРіРґР° РЅРµ СЃРѕС‡РµС‚Р°РµС‚СЃСЏ СЃ Apple GPU)
- Р’РµСЂСЃРёРё UA СЃРІРµР¶РёРµ (Chrome 118-132)

### РРЅР¶РµРєС†РёСЏ

Р”РІР° СЃР»РѕСЏ:

1. **Launch args** (`to_playwright_launch_options`) вЂ” РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚ proxy, locale, UA, timezone, СЂР°Р·РјРµСЂ РѕРєРЅР°, viewport, device scale factor. Р’С‹РїРѕР»РЅСЏРµС‚СЃСЏ РїСЂРё СЃС‚Р°СЂС‚Рµ Chromium.

2. **JS init script** (`build_init_script`) вЂ” РїР°С‚С‡РёС‚ `Navigator.prototype`, `HTMLCanvasElement.prototype`, `AudioContext.prototype`, `RTCPeerConnection.prototype` Рё С‚.Рґ. РІ РєР°Р¶РґРѕРј РЅРѕРІРѕРј РґРѕРєСѓРјРµРЅС‚Рµ. Canvas/audio noise РёСЃРїРѕР»СЊР·СѓРµС‚ Mulberry32, РїРѕСЃРµСЏРЅРЅС‹Р№ `audio_noise_seed` Рё `canvas_noise_seed` fingerprint РґР»СЏ РІРѕСЃРїСЂРѕРёР·РІРѕРґРёРјРѕСЃС‚Рё.

### РћРіСЂР°РЅРёС‡РµРЅРёСЏ

- WebGL read-only РґР»СЏ unmasked РїРѕР»РµР№ РІ Chromium вЂ” РјС‹ РїР°С‚С‡РёРј `getParameter` Рё `getExtension`, РЅРѕ РµСЃР»Рё СЃС‚СЂР°РЅРёС†Р° РёСЃРїРѕР»СЊР·СѓРµС‚ `WEBGL_debug_renderer_info` РёРЅР°С‡Рµ, РїР°С‚С‡ РјРѕР¶РЅРѕ РѕР±РѕР№С‚Рё.
- Canvas noise РјСЏРіРєРёР№ (В±2 РЅР° РєР°РЅР°Р») вЂ” СЃРёР»СЊРЅС‹Р№ С€СѓРј Р»РѕРјР°РµС‚ РІРёР·СѓР°Р»СЊРЅС‹Р№ СЂРµРЅРґРµСЂРёРЅРі РЅР° РЅРµРєРѕС‚РѕСЂС‹С… СЃР°Р№С‚Р°С…. РЈРІРµР»РёС‡РёРІР°Р№С‚Рµ noise РїРѕ РїСЂРѕС„РёР»СЋ, РµСЃР»Рё РЅСѓР¶РЅРѕ.
- РЁСЂРёС„С‚С‹ С„РѕСЂСЃРёСЂСѓСЋС‚СЃСЏ С‡РµСЂРµР· `document.fonts.check` (СЌРјСѓР»СЏС†РёСЏ РїРµСЂРµС‡РёСЃР»РµРЅРёСЏ С‡РµСЂРµР· РёР·РјРµСЂРµРЅРёРµ СЂР°Р·РјРµСЂРѕРІ РІРѕР·РІСЂР°С‰Р°РµС‚ Р±РµР»С‹Р№ СЃРїРёСЃРѕРє). Р“Р»СѓР±РѕРєРёРµ РїСЂРѕРІРµСЂРєРё С€СЂРёС„С‚РѕРІ С‡РµСЂРµР· СЂР°Р·РјРµСЂС‹ canvas, РѕР±С…РѕРґСЏС‰РёРµ `document.fonts`, РїРѕРєР° РїРѕР»РЅРѕСЃС‚СЊСЋ РЅРµ СЃРєСЂС‹С‚С‹.
- РџРѕРґРјРµРЅР° WebGPU РїР°С‚С‡РёС‚ `requestAdapterInfo()` / `adapter.info`, РЅРѕ РЅРµ РїРµСЂРµРїРёСЃС‹РІР°РµС‚ РЅРёР·РєРѕСѓСЂРѕРІРЅРµРІС‹Рµ Р»РёРјРёС‚С‹/С„СѓРЅРєС†РёРё `GPUAdapter`.
- РЎС‚РµР»СЃ Р±РµР·РіРѕР»РѕРІРѕРіРѕ СЂРµР¶РёРјР° (headless stealth) СЏРІР»СЏРµС‚СЃСЏ Р±Р°Р·РѕРІС‹Рј: РїР°С‚С‡Р°С‚СЃСЏ РѕСЃРЅРѕРІРЅС‹Рµ РґРµС‚РµРєС‚С‹ (`window.chrome`, permissions API), РЅРѕ РіР»СѓР±РѕРєРёРµ С‚Р°Р№РјРёРЅРіРё СЂРµРЅРґРµСЂРёРЅРіР° Рё СЃРїРµС†РёС„РёС‡РЅС‹Рµ РґР»СЏ GPU С‚РµСЃС‚С‹ РІ headless-СЂРµР¶РёРјРµ РјРѕРіСѓС‚ РїР°Р»РёС‚СЊСЃСЏ.
- WebRTC РїРѕРґРґРµСЂР¶РёРІР°РµС‚ С‚СЂРё СЂРµР¶РёРјР° (`webrtc_mode`): `block` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ вЂ” СЃР±РѕСЂ ICE-РєР°РЅРґРёРґР°С‚РѕРІ РїРѕРґР°РІР»СЏРµС‚СЃСЏ С†РµР»РёРєРѕРј, РЅРё host-, РЅРё reflexive-РєР°РЅРґРёРґР°С‚С‹ РЅРµ РІС‹РґР°СЋС‚СЃСЏ), `real` (Р±РµР· РїРѕРґРјРµРЅС‹) Рё `proxy` (host-РєР°РЅРґРёРґР°С‚С‹ РїРµСЂРµРїРёСЃС‹РІР°СЋС‚СЃСЏ РЅР° `webrtc_public_ip`).

---

## 11. РџРѕР»РЅС‹Р№ РїРѕС‚РѕРє РёРјРїРѕСЂС‚Р° РїСЂРѕС„РёР»СЏ (.adb)

РџРѕС‚РѕРє РґР»СЏ РёРјРїРѕСЂС‚Р° РїРѕР»РЅРѕРіРѕ РїСЂРѕС„РёР»СЏ:

```
1. POST /user/import  (РёР»Рё  cli import-cookies --full PATH)
   в†“
2. profile created (user_id assigned)
   в†“
3. .adb bundle extracted to  data/profiles/imports/<user_id>/
   в†“
4. Cookies parsed from <user_id>/Default/Cookies, written to profile.cookies
   в†“
5. profile.import_source_path = "<user_id>"   в†ђ bookmark for launcher
   в†“
6. (later) POST /user/start
   в†“
7. BrowserLauncher._maybe_apply_imported_state(profile, user_dir):
     - if import_source_path set AND initial_state_applied is False:
       - find_profile_default_dir(<user_id>)
       - copytree Local Storage/leveldb  в†’  user_dir/Default/Local Storage/leveldb
       - copytree IndexedDB              в†’  user_dir/Default/IndexedDB
       - mark_initial_state_applied(user_id)
   в†“
8. Chromium С‡РёС‚Р°РµС‚ РґРёСЂРµРєС‚РѕСЂРёРё РЅР°С‚РёРІРЅРѕ Рё РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РёС… С‚Р°Рє, Р±СѓРґС‚Рѕ РѕРЅ
   СЃР°Рј РёС… Р·Р°РїРёСЃР°Р» вЂ” Р±РµР· РїР°СЂСЃРµСЂР° LevelDB, Р±РµР· Snappy codec, Р±РµР· version drift.
```

### РџРѕС‡РµРјСѓ РєРѕРїРёСЂРѕРІР°С‚СЊ, Р° РЅРµ РїР°СЂСЃРёС‚СЊ?

Chrome в‰Ґ 61 С…СЂР°РЅРёС‚ `localStorage` РІ Snappy-СЃР¶Р°С‚РѕРј LevelDB. IndexedDB РёСЃРїРѕР»СЊР·СѓРµС‚ V8 structured-clone values. Р РµР°Р»РёР·Р°С†РёСЏ РґРµРєРѕРґРµСЂР°:

- РџСЂРёРІСЏР·Р°РЅР° Рє РІРµСЂСЃРёРё (РєРѕРґРёСЂРѕРІР°РЅРёРµ Chrome РјРµРЅСЏРµС‚СЃСЏ РјРµР¶РґСѓ РІРµСЂСЃРёСЏРјРё).
- РќРµ РґСЂСѓР¶РёС‚ СЃ Windows (`plyvel` С‚СЂРµР±СѓРµС‚ РЅР°С‚РёРІРЅС‹С… СЃР±РѕСЂРѕРє LevelDB + Snappy).
- РҐСЂСѓРїРєР°СЏ (РѕРґРёРЅ Р±Р°Р№С‚ РЅРµ РЅР° РјРµСЃС‚Рµ вЂ” Рё РІРµСЃСЊ РїСЂРѕС„РёР»СЊ РЅРµ Р·Р°РіСЂСѓР·РёС‚СЃСЏ).

РљРѕРїРёСЂРѕРІР°С‚СЊ РґРёСЂРµРєС‚РѕСЂРёРё verbatim вЂ” С‚СѓРїРѕ, РЅР°РґС‘Р¶РЅРѕ Рё СЂР°Р±РѕС‚Р°РµС‚ РґР»СЏ РєР°Р¶РґРѕР№ РІРµСЂСЃРёРё Chromium, РєРѕС‚РѕСЂСѓСЋ РїРѕСЃС‚Р°РІР»СЏРµС‚ Playwright.

### РџРѕРІС‚РѕСЂРЅС‹Р№ РёРјРїРѕСЂС‚

РџРѕСЃР»Рµ РїРѕРІС‚РѕСЂРЅРѕРіРѕ СЌРєСЃРїРѕСЂС‚Р° `.adb`:

```bash
python -m src.cli reimport <user_id>
# РёР»Рё
curl -X POST http://127.0.0.1:8080/user/<user_id>/reimport
```

Р­С‚Рѕ СЃР±СЂР°СЃС‹РІР°РµС‚ `initial_state_applied = False`. РЎР»РµРґСѓСЋС‰РёР№ Р·Р°РїСѓСЃРє СЃС‚РёСЂР°РµС‚ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ `Local Storage/leveldb/` Рё `IndexedDB/` (РїРѕС‚РѕРјСѓ С‡С‚Рѕ `force=True` СѓСЃС‚Р°РЅР°РІР»РёРІР°РµС‚СЃСЏ РІРЅСѓС‚СЂРё `apply_initial_state_to_user_data` РїСЂРё РїРѕРІС‚РѕСЂРЅРѕРј РїСЂРёРјРµРЅРµРЅРёРё) Рё РєРѕРїРёСЂСѓРµС‚ Р·Р°РЅРѕРІРѕ РёР· Р±Р°РЅРґР»Р°.

### Р¤Р»Р°Рі force

`apply_initial_state_to_user_data(..., force=True)` РїРµСЂРµР·Р°РїРёСЃС‹РІР°РµС‚ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ РґРёСЂРµРєС‚РѕСЂРёРё. Launcher РёСЃРїРѕР»СЊР·СѓРµС‚ `force=False` РїСЂРё РїРµСЂРІРѕРј РїСЂРёРјРµРЅРµРЅРёРё (С‡С‚РѕР±С‹ СЃР»СѓС‡Р°Р№РЅРѕ РЅРµ Р·Р°С‚РµСЂРµС‚СЊ С‚РѕР»СЊРєРѕ С‡С‚Рѕ СЃРєРѕРїРёСЂРѕРІР°РЅРЅРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ), Р° РїРѕС‚РѕРє reimport СЏРІРЅРѕ РїРµСЂРµРєР»СЋС‡Р°РµС‚ СЌС‚Рѕ.

---

## 12. CDP multiplexer

Playwright РІР»Р°РґРµРµС‚ РїСЂРѕС†РµСЃСЃРѕРј Chromium РЅР° РїСЂРѕС„РёР»СЊ, РЅРѕ РІРЅРµС€РЅСЏСЏ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёСЏ (Selenium, Puppeteer, РєР°СЃС‚РѕРјРЅС‹Рµ СЃРєСЂРёРїС‚С‹) С…РѕС‡РµС‚ РѕРґРЅСѓ CDP-РєРѕРЅРµС‡РЅСѓСЋ С‚РѕС‡РєСѓ РЅР° РїСЂРѕС„РёР»СЊ. `CDPProxy` (`src/core/cdp.py`) РјСѓР»СЊС‚РёРїР»РµРєСЃРёСЂСѓРµС‚:

- `GET /json/version` вЂ” РІРѕР·РІСЂР°С‰Р°РµС‚ С„РµР№РєРѕРІС‹Р№ version payload, СѓРєР°Р·С‹РІР°СЋС‰РёР№ РЅР° `ws://127.0.0.1:5555/devtools/browser`
- `GET /json/list?user_id=<id>` вЂ” СЃРїРёСЃРѕРє СЃС‚СЂР°РЅРёС† РґР»СЏ РїСЂРѕС„РёР»СЏ
- `WS /devtools/page/{user_id}/{target_id}` вЂ” РїСЂРѕРєСЃРёСЂСѓРµС‚ websocket-СЃРѕРµРґРёРЅРµРЅРёРµ Рє РЅСѓР¶РЅРѕР№ СЃС‚СЂР°РЅРёС†Рµ Playwright

Р—Р°РјРµС‡Р°РЅРёРµ: WS-РєРѕРЅРµС‡РЅР°СЏ С‚РѕС‡РєР° **СЃРёРјСѓР»РёСЂРѕРІР°РЅРЅР°СЏ** вЂ” СЂРµР°Р»СЊРЅС‹Р№ CDP-С‚СЂР°С„РёРє РёРґС‘С‚ С‡РµСЂРµР· РєРѕРЅС‚РµРєСЃС‚ Playwright, Р° РЅРµ С‡РµСЂРµР· РЅР°СЃС‚РѕСЏС‰РёР№ Chrome debug port. Р­С‚Рѕ СЂР°Р±РѕС‚Р°РµС‚ РґР»СЏ Р±СЂР°СѓР·РµСЂРЅРѕР№ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёРё, РєРѕС‚РѕСЂРѕР№ РЅРµ РЅСѓР¶РЅС‹ РЅРёР·РєРѕСѓСЂРѕРІРЅРµРІС‹Рµ С„РёС‡Рё РїСЂРѕС‚РѕРєРѕР»Р°.

Р”Р»СЏ РЅР°СЃС‚РѕСЏС‰РµРіРѕ CDP РЅР°РїСЂР°РІСЊС‚Рµ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёСЋ РЅР° per-profile websocket, РІРѕР·РІСЂР°С‰Р°РµРјС‹Р№ `POST /user/start`:

```json
{"ws_endpoint": "ws://127.0.0.1:50321/devtools/browser", "debug_port": 50321}
```

---

## 13. РЎС‚СЂСѓРєС‚СѓСЂР° РєР°С‚Р°Р»РѕРіР° data

```
data/
в”њв”Ђв”Ђ antique.db                 в†ђ SQLite (profiles, sessions, tags, groups)
в””в”Ђв”Ђ profiles/
    в”њв”Ђв”Ђ <user_id>/                в†ђ Playwright user_data_dir for the profile
    в”‚   в”њв”Ђв”Ђ Default/
    в”‚   в”‚   в”њв”Ђв”Ђ Cookies
    в”‚   в”‚   в”њв”Ђв”Ђ Local Storage/leveldb/...
    в”‚   в”‚   в”њв”Ђв”Ђ IndexedDB/...
    в”‚   в”‚   в””в”Ђв”Ђ (all Chromium user-data files)
    в”‚   в””в”Ђв”Ђ ...
    в””в”Ђв”Ђ imports/
        в””в”Ђв”Ђ <user_id>/            в†ђ Extracted .adb bundle (full-profile imports)
            в”њв”Ђв”Ђ Default/...
            в””в”Ђв”Ђ ...
```

Override С‡РµСЂРµР· `ANTIQUE_DATA_DIR=/some/path` (env var).

---

## 14. РўРµСЃС‚РёСЂРѕРІР°РЅРёРµ

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

**300+ С‚РµСЃС‚РѕРІ** (РЅР° СЃР°РјРѕРј РґРµР»Рµ СЃРµР№С‡Р°СЃ 310):

- `test_storage.py` вЂ” SQLite engine, tables
- `test_profile.py` вЂ” ProfileStore CRUD, full-profile fields, session bookkeeping
- `test_fingerprint.py` вЂ” Fingerprint generation + init script injection
- `test_proxy.py` вЂ” ProxyConfig validation + Playwright shape conversion
- `test_cookie.py` вЂ” Cookie parsing (Netscape/JSON/.adb), LocalStorage/IndexedDB extraction
- `test_profile_import.py` вЂ” Full-profile import flow
- `test_webgpu_fonts.py` вЂ” РїРѕРґРјРµРЅР° WebGPU Р°РґР°РїС‚РµСЂР° + РіРµРЅРµСЂР°С†РёСЏ Рё РёРЅР¶РµРєС†РёСЏ Р±РµР»РѕРіРѕ СЃРїРёСЃРєР° С€СЂРёС„С‚РѕРІ
- `test_automation.py` вЂ” Cookie Robot / РїР°СЂСЃРµСЂ С„Р»РѕСѓ, Р±РёР»РґРµСЂ Рё СЂР°РЅРЅРµСЂ РЅР° С„РµР№РєРѕРІРѕР№ СЃС‚СЂР°РЅРёС†Рµ
- `test_portable.py` вЂ” РїРѕСЂС‚Р°С‚РёРІРЅС‹Р№ СЌРєСЃРїРѕСЂС‚/РёРјРїРѕСЂС‚ РїСЂРѕС„РёР»РµР№ .antq
- `test_geo.py` вЂ” СЃРѕРїРѕСЃС‚Р°РІР»РµРЅРёРµ СЃС‚СЂР°РЅР°/РїСЂРѕРєСЃРё в†’ С‚Р°Р№РјР·РѕРЅР°/Р»РѕРєР°Р»СЊ/РіРµРѕР»РѕРєР°С†РёСЏ
- `test_proxy_pool.py` вЂ” СЃС‚СЂР°С‚РµРіРёРё СЂРѕС‚Р°С†РёРё РїСЂРѕРєСЃРё-РїСѓР»Р° + РѕС‚РєР°Р·РѕСѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ
- `test_detect.py` вЂ” СЃРµР»С„-С‚РµСЃС‚ РјР°СЃРєРёСЂРѕРІРєРё / РґРµС‚РµРєС‚-С…Р°СЂРЅРµСЃСЃ
- `test_console.py` вЂ” С„РёРєСЃ РІС‹РІРѕРґР° UTF-8 РІ Windows-РєРѕРЅСЃРѕР»СЊ + ASCII-С„РѕР»Р±СЌРє
- `test_api_endpoints.py` вЂ” HTTP-С‚РµСЃС‚С‹ API (TestClient): СЂРµРіСЂРµСЃСЃРёРё СЂР°СЃС€РёСЂРµРЅРёР№, РіРµРѕ-РјР°С‚С‡РёРЅРі, РїСЂРѕРєСЃРё-РїСѓР», СЌРєСЃРїРѕСЂС‚, СЃРєРѕСЂРёРЅРі СЃРєСЂС‹С‚РЅРѕСЃС‚Рё
- `test_auth.py` вЂ” Р°РІС‚РѕСЂРёР·Р°С†РёСЏ РїРѕ API + Origin-guard (DNS-rebinding, Bearer-С‚РѕРєРµРЅ, СЂР°Р·СЂРµС€РµРЅРЅС‹Рµ С…РѕСЃС‚С‹)
- `test_engines.py` вЂ” СЂРµРµСЃС‚СЂ Р±СЂР°СѓР·РµСЂРЅС‹С… РґРІРёР¶РєРѕРІ: СЃРїРµС†РёС„РёРєР°С†РёРё, РєР°РїР°Р±РёР»РёС‚Рё, Р°Р»РёР°СЃС‹, РІС‹Р±РѕСЂ РїСЂРёРѕСЂРёС‚РµС‚РѕРІ, Р·Р°РїСѓСЃРє Р»Р°СѓРЅС‡РµСЂРѕРІ
- `test_sync.py` вЂ” СЃРёРЅС…СЂРѕРЅРЅР°СЏ Р°РІС‚РѕРјР°С‚РёР·Р°С†РёСЏ РЅР° РЅРµСЃРєРѕР»СЊРєРѕ РїСЂРѕС„РёР»РµР№ (РєРѕРЅРєСѓСЂРµРЅС‚РЅРѕСЃС‚СЊ, РёР·РѕР»СЏС†РёСЏ РѕС€РёР±РѕРє)
- `test_status_liveview.py` вЂ” СЃС‚Р°С‚СѓСЃС‹ Р°РєРєР°СѓРЅС‚РѕРІ, СЃРєСЂРёРЅС€РѕС‚С‹ Live View, РїСЂРѕРІРµСЂРєРё СЌРЅРґРїРѕРёРЅС‚РѕРІ CDP Рё СЃРєСЂРёРЅС€РѕС‚РѕРІ
- `test_import_launch_and_randomize.py` вЂ” СЂРµРіСЂРµСЃСЃРёСЏ РёРјРїРѕСЂС‚РёСЂРѕРІР°РЅРЅС‹С… РїСЂРѕС„РёР»РµР№, РїРµС‚Р»РµРІРѕР№ SOCKS5 РјРѕСЃС‚, СѓРјРЅР°СЏ bulk-СЂР°РЅРґРѕРјРёР·Р°С†РёСЏ
- `test_ui_release_040.py` вЂ” РїСЂРѕРІРµСЂРєР° СЌР»РµРјРµРЅС‚РѕРІ РёРЅС‚РµСЂС„РµР№СЃР° СЂРµР»РёР·Р° 0.4.0
- `test_sort_clone_features.py` вЂ” СЃРѕСЂС‚РёСЂРѕРІРєР° РїСЂРѕС„РёР»РµР№, РєР»РѕРЅРёСЂРѕРІР°РЅРёРµ Рё РіСЂСѓРїРїРѕРІРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ СЃС‚Р°С‚СѓСЃРѕРІ
- `test_operations_release.py` вЂ” РјР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РїРѕ С€Р°Р±Р»РѕРЅСѓ, Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹Рµ snapshots, Р°СѓРґРёС‚ РёСЃС‚РѕСЂРёРё Р°РєС‚РёРІРЅРѕСЃС‚Рё (С„РёР»СЊС‚СЂР°С†РёСЏ Рё СЌРєСЃРїРѕСЂС‚ РІ JSON), Р»РѕРєР°Р»СЊРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ РїСЂРѕРєСЃРё (File/JSON/HTTP-JSON), CRUD РіСЂСѓРїРї, РїР»Р°РЅРёСЂРѕРІС‰РёРє Р»РѕРєР°Р»СЊРЅС‹С… СЂРµР·РµСЂРІРЅС‹С… РєРѕРїРёР№, РєР°С‚Р°Р»РѕРі СЂР°СЃС€РёСЂРµРЅРёР№ Рё РёРЅС‚РµРіСЂР°С†РёСЏ MCP-СЃС‚Р°С‚СѓСЃР° (РќРћР’РћР• РІ 0.9.0)

Р—Р°РїСѓСЃС‚РёС‚СЊ С‚РѕР»СЊРєРѕ РЅРѕРІС‹Рµ РЅР°Р±РѕСЂС‹ С‚РµСЃС‚РѕРІ:

```bash
python -m pytest tests/test_operations_release.py tests/test_sort_clone_features.py tests/test_import_launch_and_randomize.py tests/test_ui_release_040.py -v
```

---

## 15. Р РµР»РёР· РїР°СЂРёС‚РµС‚Р° С„СѓРЅРєС†РёР№ 0.6.0

Р”РѕР±Р°РІР»РµРЅС‹ С„СѓРЅРєС†РёРё РїР°СЂРёС‚РµС‚Р° СЃ AdsPower: РїСЂРµРґРІР°СЂРёС‚РµР»СЊРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ AdsPower Р±СЌРєР°РїР° Р±РµР· РёРјРїРѕСЂС‚Р° (dry-run), С€Р°Р±Р»РѕРЅС‹ РїСЂРѕС„РёР»РµР№ Рё РјР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ, Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹Рµ AES-GCM СЂРµР·РµСЂРІРЅС‹Рµ СЃРЅРёРјРєРё (snapshots), СЃРёСЃС‚РµРјРЅР°СЏ РёСЃС‚РѕСЂРёСЏ РґРµР№СЃС‚РІРёР№ (Р°СѓРґРёС‚ СЃРѕР±С‹С‚РёР№), Р»РѕРєР°Р»СЊРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ РїСЂРѕРєСЃРё РёР· С„Р°Р№Р»РѕРІ/JSON, CRUD РіСЂСѓРїРї, СЌРЅРґРїРѕРёРЅС‚С‹ РјРѕРЅРёС‚РѕСЂРёРЅРіР° СЃРёСЃС‚РµРјРЅС‹С… СЂРµСЃСѓСЂСЃРѕРІ Рё СЃС‚Р°С‚СѓСЃР° MCP-СЃРµСЂРІРµСЂР°, Р° С‚Р°РєР¶Рµ РїР°РЅРµР»СЊ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ (Tools) РІ РёРЅС‚РµСЂС„РµР№СЃРµ РґР°С€Р±РѕСЂРґР°. РќРѕРІС‹Рµ С‚РµСЃС‚С‹ РЅР°С…РѕРґСЏС‚СЃСЏ РІ `tests/test_operations_release.py`.

## 16. Р РµР»РёР· РїР°СЂРёС‚РµС‚Р° С„СѓРЅРєС†РёР№ 0.7.0

Р”РѕР±Р°РІР»РµРЅС‹ СЂР°СЃС€РёСЂРµРЅРЅС‹Рµ С„СѓРЅРєС†РёРё РїР°СЂРёС‚РµС‚Р° СЃ AdsPower: РїРѕР»РЅРѕС†РµРЅРЅР°СЏ Р·Р°РїРёСЃСЊ СЃРѕР±С‹С‚РёР№ Р°СѓРґРёС‚Р° Р°РєС‚РёРІРЅРѕСЃС‚Рё (РїСЂРё СЃРѕР·РґР°РЅРёРё, РѕР±РЅРѕРІР»РµРЅРёРё, Р·Р°РїСѓСЃРєРµ, РѕСЃС‚Р°РЅРѕРІРєРµ, СѓРґР°Р»РµРЅРёРё, РёРјРїРѕСЂС‚Рµ Р±СЌРєР°РїРѕРІ Рё РїР°РєРµС‚РЅРѕР№ СЃРјРµРЅРµ СЃС‚Р°С‚СѓСЃР°), РїР»Р°РЅРёСЂРѕРІС‰РёРє Р»РѕРєР°Р»СЊРЅС‹С… Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹С… СЂРµР·РµСЂРІРЅС‹С… РєРѕРїРёР№ (СЃ AES-GCM С€РёС„СЂРѕРІР°РЅРёРµРј Рё РёРЅС‚РµСЂРІР°Р»СЊРЅС‹Рј Р·Р°РїСѓСЃРєРѕРј Р±РµР· СЃРєСЂС‹С‚С‹С… РґРµРјРѕРЅРѕРІ С‡РµСЂРµР· cron РёР»Рё РїР»Р°РЅРёСЂРѕРІС‰РёРє Windows), HTTP JSON РїСЂРѕРІР°Р№РґРµСЂ РїСЂРѕРєСЃРё РґР»СЏ РїРѕРґРіСЂСѓР·РєРё РґРёРЅР°РјРёС‡РµСЃРєРёС… СЃРїРёСЃРєРѕРІ РїСЂРѕРєСЃРё РёР· РІРЅРµС€РЅРёС… API, Р° С‚Р°РєР¶Рµ РґРµС‚Р°Р»СЊРЅС‹Рµ resource-РјРµС‚СЂРёРєРё СЃРёСЃС‚РµРјРЅС‹С… СЂРµСЃСѓСЂСЃРѕРІ (PID, RSS-РїР°РјСЏС‚СЊ, РїСЂРѕС†РµСЃСЃРѕСЂРЅРѕРµ РІСЂРµРјСЏ) СЃ Р±РµР·РѕРїР°СЃРЅС‹Рј fallback-СЂРµР¶РёРјРѕРј РґР»СЏ Windows.

## 17. Р РµР»РёР· РїР°СЂРёС‚РµС‚Р° С„СѓРЅРєС†РёР№ 0.8.0

Р”РѕР±Р°РІР»РµРЅС‹ РІР»РѕР¶РµРЅРЅС‹Рµ РїР°РїРєРё/РіСЂСѓРїРїС‹ (РїРѕРґРґРµСЂР¶РєР° РёРµСЂР°СЂС…РёРё РіСЂСѓРїРї С‡РµСЂРµР· РїРѕР»Рµ `parent_id` РІ С‚Р°Р±Р»РёС†Рµ `groups`), РїРѕР»РЅРѕС†РµРЅРЅР°СЏ РёРЅС‚РµРіСЂР°С†РёСЏ РїР°РЅРµР»Рё РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ (Tools Workspace) РІ РІРµР±-РёРЅС‚РµСЂС„РµР№СЃ РґР°С€Р±РѕСЂРґР° (РґР»СЏ РїСЂРѕСЃРјРѕС‚СЂР° Р°СѓРґРёС‚Р° СЃРѕР±С‹С‚РёР№, СЃРёСЃС‚РµРјРЅС‹С… СЂРµСЃСѓСЂСЃРѕРІ, СЂР°СЃРїРёСЃР°РЅРёР№ Р±СЌРєР°РїРѕРІ Рё dry-run РёРјРїРѕСЂС‚Р° AdsPower), Р° С‚Р°РєР¶Рµ РґРµС‚Р°Р»СЊРЅС‹Р№ СЃРєРІРѕР·РЅРѕР№ С‡РµРєР»РёСЃС‚ РІР»Р°РґРµР»СЊС†Р° РІ `docs/OWNER-FULL-TEST-CHECKLIST.md` РґР»СЏ СЂСѓС‡РЅРѕРіРѕ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ РѕС‚ A РґРѕ H.

## 18. Р РµР»РёР· РїР°СЂРёС‚РµС‚Р° С„СѓРЅРєС†РёР№ 0.9.0

Р”РѕР±Р°РІР»РµРЅС‹: С„РёР»СЊС‚СЂР°С†РёСЏ Р»РѕРіРѕРІ Р°РєС‚РёРІРЅРѕСЃС‚Рё (activity) РїРѕ РїСЂРѕС„РёР»СЋ Рё С‚РёРїСѓ РґРµР№СЃС‚РІРёСЏ, СЌРєСЃРїРѕСЂС‚ Р°РєС‚РёРІРЅРѕСЃС‚Рё РІ JSON С‡РµСЂРµР· API Рё UI РґР°С€Р±РѕСЂРґР°, РїРѕР»РЅРѕС†РµРЅРЅС‹Р№ РєР°С‚Р°Р»РѕРі СЂР°СЃС€РёСЂРµРЅРёР№ (Extension Catalog) РІ Tools РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РіР»РѕР±Р°Р»СЊРЅС‹РјРё РїР»Р°РіРёРЅР°РјРё (СѓСЃС‚Р°РЅРѕРІРєР° unpacked РєР°С‚Р°Р»РѕРіРѕРІ Рё Chrome Web Store ID), РёРЅС‚РµРіСЂР°С†РёСЏ СЃС‚Р°С‚СѓСЃР° MCP-СЃРµСЂРІРµСЂР° РїСЂСЏРјРѕ РІ UI (СЃ РїРѕРґРґРµСЂР¶РєРѕР№ С‚СЂР°РЅСЃРїРѕСЂС‚Р° stdio), Р° С‚Р°РєР¶Рµ РѕР±РЅРѕРІР»РµРЅРЅС‹Р№ СЃРєРІРѕР·РЅРѕР№ С‡РµРєР»РёСЃС‚ РІР»Р°РґРµР»СЊС†Р° `docs/OWNER-FULL-TEST-CHECKLIST.md` Рё РјР°С‚СЂРёС†Р° РІРѕР·РјРѕР¶РЅРѕСЃС‚РµР№.

## 19. Р РµР»РёР· 1.0.0 вЂ” РЈРїСЂР°РІР»РµРЅРёРµ РїР°РїРєР°РјРё Рё СЃС‚Р°Р±РёР»РёР·Р°С†РёСЏ

Р”РѕР±Р°РІР»РµРЅС‹: РїРѕР»РЅРѕС†РµРЅРЅС‹Р№ `GET /group/tree` РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёРµСЂР°СЂС…РёРё РїР°РїРѕРє РІ РІРёРґРµ РґРµСЂРµРІР°, Р±РµР·РѕРїР°СЃРЅРѕРµ СѓРґР°Р»РµРЅРёРµ РіСЂСѓРїРї-СЂРѕРґРёС‚РµР»РµР№ Рё Р·Р°С‰РёС‚Р° default-РіСЂСѓРїРїС‹ РѕС‚ СѓРґР°Р»РµРЅРёСЏ, РїРѕРґРґРµСЂР¶РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ Рё СѓРґР°Р»РµРЅРёСЏ РїР°РїРѕРє РїСЂСЏРјРѕ РёР· UI РІ РїР°РЅРµР»Рё Tools, РєРЅРѕРїРєР° СѓРґР°Р»РµРЅРёСЏ СЂР°СЃС€РёСЂРµРЅРёСЏ (extension uninstall) РІ РєР°С‚Р°Р»РѕРіРµ Tools, СЂР°СЃС€РёСЂРµРЅРЅС‹Р№ `OWNER-FULL-TEST-CHECKLIST.md` СЃ С€Р°РіР°РјРё РїСЂРѕРІРµСЂРєРё РёРµСЂР°СЂС…РёРё РіСЂСѓРїРї Рё РєР°С‚Р°Р»РѕРіР° СЂР°СЃС€РёСЂРµРЅРёР№, РѕР±РЅРѕРІР»С‘РЅРЅС‹Р№ РѕС‚С‡С‘С‚ `docs/RELEASE-1.0.0-REPORT.md` Рё РјР°С‚СЂРёС†Р° РїР°СЂРёС‚РµС‚Р°.

## 20. РР·РІРµСЃС‚РЅС‹Рµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ Рё roadmap

### РЎРґРµР»Р°РЅРѕ (РІ СЌС‚РѕР№ СЃР±РѕСЂРєРµ)

- [x] Multi-profile isolated Chromium contexts
- [x] Fingerprint generation + JS injection
- [x] HTTP/HTTPS/SOCKS5 proxies
- [x] Cookie import (Netscape, JSON, .adb bundle)
- [x] Cookie export (Netscape, JSON)
- [x] Full .adb profile import (cookies + LocalStorage + IndexedDB)
- [x] Re-import flow (`cli reimport`, `POST /user/{id}/reimport`)
- [x] AdsPower-compatible REST API
- [x] CDP multiplexer (simulated)
- [x] Single-page dashboard
- [x] **РњРµРЅРµРґР¶РµСЂ СЂР°СЃС€РёСЂРµРЅРёР№** (СѓСЃС‚Р°РЅРѕРІРєР° РёР· СЂР°СЃРїР°РєРѕРІР°РЅРЅС‹С… РїР°РїРѕРє, .crx, Chrome Web Store; РЅР°Р·РЅР°С‡РµРЅРёРµ РЅР° РїСЂРѕС„РёР»СЊ)
- [x] **MCP-СЃРµСЂРІРµСЂ** (JSON-RPC 2.0 С‡РµСЂРµР· stdio, 12 РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ: list/open/close/navigate/screenshot/execute_script/cookies/proxy_check)
- [x] **РџРѕРґРґРµСЂР¶РєР° РЅРµСЃРєРѕР»СЊРєРёС… РґРІРёР¶РєРѕРІ** (Chromium, Firefox, Camoufox/ShardX; РЅР° РєР°Р¶РґС‹Р№ РїСЂРѕС„РёР»СЊ РёР»Рё С‡РµСЂРµР· env-var)
- [x] **Client Hints** (Sec-CH-UA Р·Р°РіРѕР»РѕРІРєРё С‡РµСЂРµР· РєР°СЃС‚РѕРјРЅС‹Рµ Р°СЂРіСѓРјРµРЅС‚С‹ Р±СЂР°СѓР·РµСЂР°, Р°РІС‚РѕРіРµРЅРµСЂР°С†РёСЏ РёР· С„РёРЅРіРµСЂРїСЂРёРЅС‚Р°)
- [x] **Р Р°СЃС€РёСЂРµРЅРёСЏ РЅР° РїСЂРѕС„РёР»СЊ** (`--load-extension` + `--disable-extensions-except` РїСЂРё Р·Р°РїСѓСЃРєРµ)
- [x] **РџРѕРґРјРµРЅР° WebGPU С„РёРЅРіРµСЂРїСЂРёРЅС‚Р°** (СЃРѕРіР»Р°СЃРѕРІР°РЅРѕ СЃ WebGL GPU)
- [x] **РџРѕРґРјРµРЅР° С€СЂРёС„С‚РѕРІ** (С‡РµСЂРµР· Р±РµР»С‹Р№ СЃРїРёСЃРѕРє РїРѕРґ РєР°Р¶РґСѓСЋ РћРЎ РІ `document.fonts.check`)
- [x] **Cookie Robot / Р°РІС‚РѕРјР°С‚РёР·Р°С†РёСЏ Р±РµР· РєРѕРґР°** (`warm`, `run-flow`; РјРѕРґРµР»СЊ С€Р°РіРѕРІ РІ JSON)
- [x] **РџРѕСЂС‚Р°С‚РёРІРЅС‹Р№ СЌРєСЃРїРѕСЂС‚/РёРјРїРѕСЂС‚ РїСЂРѕС„РёР»РµР№** (Р±Р°РЅРґР»С‹ `.antq`)
- [x] **РџСЂРёРІСЏР·РєР° Рє Р“Р•Рћ** (СЃРѕРіР»Р°СЃРѕРІР°РЅРёРµ С‚Р°Р№РјР·РѕРЅС‹/Р»РѕРєР°Р»Рё/СЏР·С‹РєРѕРІ/РіРµРѕР»РѕРєР°С†РёРё РїРѕРґ СЃС‚СЂР°РЅСѓ РёР»Рё РІС‹С…РѕРґ РїСЂРѕРєСЃРё, `src/core/geo.py`)
- [x] **РџРѕРґРјРµРЅР° РіРµРѕР»РѕРєР°С†РёРё** (`navigator.geolocation` СЃРѕРІРїР°РґР°РµС‚ СЃ РіРµРѕ-РїСЂРѕС„РёР»РµРј)
- [x] **Р РѕС‚Р°С†РёСЏ Рё РѕС‚РєР°Р·РѕСѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ РїСЂРѕРєСЃРё** (РїСѓР» СЃРѕ СЃС‚СЂР°С‚РµРіРёСЏРјРё sticky/round_robin/random, `src/core/proxy_pool.py`)
- [x] **Headless-СЃС‚РµР»СЃ** (РїРѕРґРјРµРЅР° Р·Р°РіР»СѓС€РµРє `window.chrome`/`chrome.runtime` + СЃРѕРіР»Р°СЃРѕРІР°РЅРЅРѕСЃС‚СЊ `permissions.query`)
- [x] **Р”РµС‚РµРєС‚-С…Р°СЂРЅРµСЃСЃ** (СЃРµР»С„-С‚РµСЃС‚ РјР°СЃРєРёСЂРѕРІРєРё `detect-test` СЃ РѕС†РµРЅРєРѕР№ РѕС‚С‡РµС‚Р° 0-100, `src/core/detect.py`)
- [x] **РћРїС†РёРѕРЅР°Р»СЊРЅР°СЏ Р°РІС‚РѕСЂРёР·Р°С†РёСЏ РїРѕ С‚РѕРєРµРЅСѓ** (РїРµСЂРµРјРµРЅРЅР°СЏ `ANTIQUE_API_TOKEN` + Р·Р°С‰РёС‚Р° РѕС‚ Cross-Origin/DNS-rebinding)
- [x] **Р¤РёРєСЃ РєРѕРґРёСЂРѕРІРєРё РІ РєРѕРЅСЃРѕР»Рё Windows** (РІС‹РІРѕРґ UTF-8 СЃ ASCII-С„РѕР»Р±СЌРєРѕРј Р±РµР· РїР°РґРµРЅРёР№ `UnicodeEncodeError`)
- [x] **РЎРјРµРЅСЏРµРјС‹Рµ Р±СЂР°СѓР·РµСЂРЅС‹Рµ РґРІРёР¶РєРё** (Chromium/Chrome/Edge/Firefox/Camoufox/WebKit, `src/core/engines.py`, `/engine/list`, `create --engine`)
- [x] **Р”РІРёР¶РѕРє Camoufox deep-stealth** (Gecko-СѓСЂРѕРІРµРЅСЊ РїРѕРґРјРµРЅС‹ РѕС‚РїРµС‡Р°С‚РєРѕРІ; РѕС‚РєР°С‚С‹РІР°РµС‚СЃСЏ РЅР° СЃС‚Р°РЅРґР°СЂС‚РЅС‹Р№ Firefox, РµСЃР»Рё РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ)
- [x] **РРјРїРѕСЂС‚ Р±СЌРєР°РїР° AdsPower РІ РѕРґРёРЅ РєР»РёРє** (РІСЃРµР№ РїР°РїРєРё Р±СЌРєР°РїР° РёР»Рё РѕРґРЅРѕРіРѕ РїСЂРѕС„РёР»СЏ; CLI `import-backup` + `/user/import/backup` + РґР°С€Р±РѕСЂРґ)
- [x] **Р РµРґРёР·Р°Р№РЅ РґР°С€Р±РѕСЂРґР°** (РїРѕРґРґРµСЂР¶РєР° С‚РµРјРЅРѕР№/СЃРІРµС‚Р»РѕР№ С‚РµРјС‹, РІС‹Р±РѕСЂ РґРІРёР¶РєР°, РёРјРїРѕСЂС‚ РёР· Р±СЌРєР°РїР° AdsPower, РІСЃРїР»С‹РІР°СЋС‰РёРµ СѓРІРµРґРѕРјР»РµРЅРёСЏ)
- [x] **РЎС‚Р°С‚СѓСЃС‹ Р°РєРєР°СѓРЅС‚РѕРІ** (`new`/`warming`/`active`/`limited`/`banned`/`retired`) СЃ С„РёР»СЊС‚СЂР°С†РёРµР№ (`/status/list`, `/user/{id}/status`, CLI `set-status`)
- [x] **Live View** (Р¶РёРІС‹Рµ СЃРєСЂРёРЅС€РѕС‚С‹ Р·Р°РїСѓС‰РµРЅРЅРѕРіРѕ РїСЂРѕС„РёР»СЏ РїСЂСЏРјРѕ РёР· РґР°С€Р±РѕСЂРґР° РёР»Рё С‡РµСЂРµР· `/user/{id}/screenshot`)
- [x] **Р РµР°Р»СЊРЅС‹Р№ CDP РЅР° РїСЂРѕС„РёР»СЊ** (СѓРЅРёРєР°Р»СЊРЅС‹Р№ РїРѕСЂС‚ РґР»СЏ РєР°Р¶РґРѕРіРѕ Chromium-РїСЂРѕС„РёР»СЏ, РґРѕСЃС‚СѓРїРµРЅ С‡РµСЂРµР· `/user/{id}/cdp`)
- [x] **РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РЅРµСЃРєРѕР»СЊРєРёС… РїСЂРѕС„РёР»РµР№** (РѕРґРЅРѕРІСЂРµРјРµРЅРЅС‹Р№ Р·Р°РїСѓСЃРє РѕРґРЅРѕРіРѕ С„Р»РѕСѓ С€Р°РіРѕРІ РЅР° РіСЂСѓРїРїРµ РїСЂРѕС„РёР»РµР№, `src/core/sync.py`, CLI `sync`, `/sync/run`)
- [x] **Docker РєРѕРЅС‚РµР№РЅРµСЂРёР·Р°С†РёСЏ** (РґРѕР±Р°РІР»РµРЅ `Dockerfile`, `docker-compose.yml`, `docker compose up`)
- [x] **РЎРѕСЂС‚РёСЂРѕРІРєР° РїСЂРѕС„РёР»РµР№ РІ UI, API Рё CLI** (РїРѕ 13 РїР°СЂР°РјРµС‚СЂР°Рј, СЃ Р·Р°РїРѕРјРёРЅР°РЅРёРµРј РЅР°РїСЂР°РІР»РµРЅРёСЏ asc/desc)
- [x] **РљР»РѕРЅРёСЂРѕРІР°РЅРёРµ РїСЂРѕС„РёР»РµР№** (РєРѕРїРёСЂРѕРІР°РЅРёРµ РјРµС‚Р°РґР°РЅРЅС‹С…, РѕС‚РїРµС‡Р°С‚РєРѕРІ, РїСЂРѕРєСЃРё, РєСѓРє Рё С‚РµРіРѕРІ С‡РµСЂРµР· UI Manage/Clone, API `/user/clone` РёР»Рё CLI `clone`)
- [x] **РњР°СЃСЃРѕРІРѕРµ РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃРѕРІ Р°РєРєР°СѓРЅС‚РѕРІ** (С‡РµСЂРµР· UI, API `/user/bulk/status` РёР»Рё CLI `bulk-status`)
- [x] **РЈРјРЅР°СЏ СЂР°РЅРґРѕРјРёР·Р°С†РёСЏ РѕС‚РїРµС‡Р°С‚РєРѕРІ** (СЃ СЃРѕС…СЂР°РЅРµРЅРёРµРј РІС‹Р±СЂР°РЅРЅС‹С… РіСЂСѓРїРї РїРѕР»РµР№ РІ UI/API)
- [x] **РџРµС‚Р»РµРІРѕР№ Р°РІС‚РѕСЂРёР·Р°С†РёРѕРЅРЅС‹Р№ SOCKS5-РјРѕСЃС‚** (РґР»СЏ РѕР±С…РѕРґР° РѕРіСЂР°РЅРёС‡РµРЅРёР№ Р°РІС‚РѕСЂРёР·Р°С†РёРё РїСЂРѕРєСЃРё РІ Chromium)
- [x] **РџСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ Р±СЌРєР°РїРѕРІ AdsPower Р±РµР· РёРјРїРѕСЂС‚Р° (dry-run)** (API `/user/import/backup/preview`, CLI `preview-backup`)
- [x] **РњР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РїРѕ С€Р°Р±Р»РѕРЅСѓ** (API `/user/template/create`, CLI `template-create`)
- [x] **Р—Р°С€РёС„СЂРѕРІР°РЅРЅС‹Рµ AES-GCM СЃРЅРёРјРєРё** (API `/user/snapshot/export` Рё `/user/snapshot/import`, CLI `snapshot-export` Рё `snapshot-import`)
- [x] **РСЃС‚РѕСЂРёСЏ Р°РєС‚РёРІРЅРѕСЃС‚Рё Рё Р°СѓРґРёС‚** (API `/activity`, CLI `activity`, РґРµС‚Р°Р»СЊРЅС‹Рµ СЃРѕР±С‹С‚РёСЏ Р°СѓРґРёС‚Р°, С„РёР»СЊС‚СЂР°С†РёСЏ РїРѕ РїСЂРѕС„РёР»СЋ/РґРµР№СЃС‚РІРёСЋ, СЌРєСЃРїРѕСЂС‚ РІ JSON)
- [x] **Р›РѕРєР°Р»СЊРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ РїСЂРѕРєСЃРё** (File/JSON/HTTP-JSON, API `/proxy/providers/test`)
- [x] **CRUD РіСЂСѓРїРї** (`/group/create`, `/group/update`, `/group/delete`, РїРѕРґРґРµСЂР¶РєР° РІР»РѕР¶РµРЅРЅС‹С… РїР°РїРѕРє `parent_id`)
- [x] **РњРѕРЅРёС‚РѕСЂРёРЅРі СЂРµСЃСѓСЂСЃРѕРІ Рё СЃС‚Р°С‚СѓСЃ MCP** (`/resource/status`, `/mcp/status`, РґРµС‚Р°Р»СЊРЅС‹Рµ РјРµС‚СЂРёРєРё RSS/CPU, СЃС‚Р°С‚СѓСЃ MCP РІ UI)
- [x] **РџР»Р°РЅРёСЂРѕРІС‰РёРє Р·Р°С€РёС„СЂРѕРІР°РЅРЅС‹С… СЂРµР·РµСЂРІРЅС‹С… РєРѕРїРёР№** (API `/backup/schedules`, CLI `backup-schedule`)
- [x] **РџР°РЅРµР»СЊ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ UI (Tools Workspace)** (Р°СѓРґРёС‚ СЃРѕР±С‹С‚РёР№ СЃ С„РёР»СЊС‚СЂР°С†РёРµР№ Рё СЌРєСЃРїРѕСЂС‚РѕРј, СЃРёСЃС‚РµРјРЅС‹Рµ СЂРµСЃСѓСЂСЃС‹, СЂР°СЃРїРёСЃР°РЅРёСЏ, РєР°С‚Р°Р»РѕРі СЂР°СЃС€РёСЂРµРЅРёР№)
- [x] **РљР°С‚Р°Р»РѕРі СЂР°СЃС€РёСЂРµРЅРёР№** (Extension Catalog РІ UI Tools, СѓСЃС‚Р°РЅРѕРІРєР° unpacked Рё Chrome Web Store ID, СЃРѕРїРѕСЃС‚Р°РІР»РµРЅРёРµ СЃ РїСЂРѕС„РёР»РµРј)
- [x] **РРµСЂР°СЂС…РёСЏ РіСЂСѓРїРї (РїР°РїРєРё)** (`GET /group/tree`, Р±РµР·РѕРїР°СЃРЅРѕРµ СѓРґР°Р»РµРЅРёРµ СЂРѕРґРёС‚РµР»СЊСЃРєРёС… РіСЂСѓРїРї, Р·Р°С‰РёС‚Р° default-РіСЂСѓРїРїС‹, UI update/delete РїР°РїРѕРє)
- [x] **Р§РµРєР»РёСЃС‚ РІР»Р°РґРµР»СЊС†Р° (Owner Checklist)** (`docs/OWNER-FULL-TEST-CHECKLIST.md`)
- [x] 313+ С‚РµСЃС‚РѕРІ pytest РїСЂРѕР№РґРµРЅС‹

### РР·РІРµСЃС‚РЅС‹Рµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ

- **Р РµР°Р»СЊРЅС‹Р№ CDP РЅР° РїСЂРѕС„РёР»СЊ** РґРѕСЃС‚СѓРїРµРЅ РїРѕ Р°РґСЂРµСЃСѓ `GET /user/{id}/cdp` (РґР»СЏ РґРІРёР¶РєРѕРІ Chromium). РЈСЃС‚Р°СЂРµРІС€РёР№ РјСѓР»СЊС‚РёРїР»РµРєСЃРѕСЂ `/json/list` + `/devtools/page/...` РїРѕ-РїСЂРµР¶РЅРµРјСѓ СЏРІР»СЏРµС‚СЃСЏ СЃРёРјСѓР»РёСЂРѕРІР°РЅРЅС‹Рј вЂ” СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РЅРѕРІС‹Р№ `/user/{id}/cdp` РёР»Рё РІРµР±СЃРѕРєРµС‚ РёР· `POST /user/start`.
- **API-Р°РІС‚РѕСЂРёР·Р°С†РёСЏ РѕРїС†РёРѕРЅР°Р»СЊРЅР°.** Р—Р°РґР°Р№С‚Рµ `ANTIQUE_API_TOKEN` РґР»СЏ С‚СЂРµР±РѕРІР°РЅРёСЏ Bearer-С‚РѕРєРµРЅР°; РµСЃР»Рё РЅРµ Р·Р°РґР°РЅРѕ, РґРѕСЃС‚СѓРї РѕС‚РєСЂС‹С‚ Р»РѕРєР°Р»СЊРЅРѕ РЅР° `127.0.0.1` (РІСЃРµ РµС‰Рµ Р·Р°С‰РёС‰РµРЅРѕ Cross-Origin РіР°СЂРґРѕРј). Р РѕР»РµР№ Рё РјСѓР»СЊС‚РёРїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РЅРµС‚.
- **РќРµС‚ РёРЅС‚РµРіСЂР°С†РёРё СЃ РїСЂРѕРІР°Р№РґРµСЂР°РјРё РїСЂРѕРєСЃРё.** РџСЂРѕРєСЃРё РїРѕСЃС‚Р°РІР»СЏСЋС‚СЃСЏ РїСѓР»РѕРј; Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєР°СЏ СЂРѕС‚Р°С†РёСЏ РїРѕРІРµСЂС… РІР°С€РµРіРѕ РїСѓР»Р° СЂРµР°Р»РёР·РѕРІР°РЅР°.
- **РЎС‚РµР»СЃ Р±РµР·РіРѕР»РѕРІРѕРіРѕ СЂРµР¶РёРјР° (headless stealth) Р±Р°Р·РѕРІС‹Р№.** Р’РЅРµРґСЂРµРЅС‹ РїР°С‚С‡Рё РЅР° `window.chrome` Рё permissions, РЅРѕ РіР»СѓР±РѕРєРёРµ С‚РµСЃС‚С‹ С‚Р°Р№РјРёРЅРіРѕРІ Рё GPU РІ headless-СЂРµР¶РёРјРµ РјРѕРіСѓС‚ РїР°Р»РёС‚СЊСЃСЏ.
- **РЈ WebRTC С‚СЂРё СЂРµР¶РёРјР°** (`webrtc_mode`): `block` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ вЂ” СЃР±РѕСЂ РєР°РЅРґРёРґР°С‚РѕРІ РїРѕРґР°РІР»СЏРµС‚СЃСЏ, Р»РѕРєР°Р»СЊРЅС‹Р№ IP РЅРµ СѓС‚РµРєР°РµС‚), `real` (Р±РµР· РїРѕРґРјРµРЅС‹) Рё `proxy` (host-РєР°РЅРґРёРґР°С‚С‹ РїРµСЂРµРїРёСЃС‹РІР°СЋС‚СЃСЏ РЅР° `webrtc_public_ip`). Р”Р»СЏ `proxy` РЅСѓР¶РµРЅ РїСѓР±Р»РёС‡РЅС‹Р№ IP РІ РїСЂРѕС„РёР»Рµ; Р±РµР· РЅРµРіРѕ СЂРµР¶РёРј РѕС‚РєР»РѕРЅСЏРµС‚СЃСЏ, Р° РЅРµ РїРѕРЅРёР¶Р°РµС‚СЃСЏ РјРѕР»С‡Р°.
- **Р”Р»СЏ Camoufox С‚СЂРµР±СѓРµС‚СЃСЏ РѕС‚РґРµР»СЊРЅР°СЏ СѓСЃС‚Р°РЅРѕРІРєР°.** Р—Р°РїСѓСЃС‚РёС‚Рµ `pip install camoufox && python -m camoufox fetch`. Р‘РµР· СѓСЃС‚Р°РЅРѕРІРєРё РґРІРёР¶РѕРє `camoufox` Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РѕС‚РєР°С‚С‹РІР°РµС‚СЃСЏ РЅР° bundled Firefox (СЃС‚Р°РЅРґР°СЂС‚РЅС‹Р№ СЃС‚РµР»СЃ РІРјРµСЃС‚Рѕ РіР»СѓР±РѕРєРѕРіРѕ).
- **Р”Р»СЏ РґРІРёР¶РєРѕРІ Chrome/Edge С‚СЂРµР±СѓРµС‚СЃСЏ СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹Р№ СЂРµР°Р»СЊРЅС‹Р№ Р±СЂР°СѓР·РµСЂ** РІ СЃРёСЃС‚РµРјРµ. РРЅР°С‡Рµ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ СЃС‚Р°РЅРґР°СЂС‚РЅС‹Р№ `chromium`.
- **Р”РІРёР¶РєРё Firefox/Camoufox/WebKit РЅРµ РїРѕРґРґРµСЂР¶РёРІР°СЋС‚ per-profile CDP Рё Р·Р°РіСЂСѓР·РєСѓ СЂР°СЃС€РёСЂРµРЅРёР№ .crx** вЂ” СЌС‚Рё РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё СЌРєСЃРєР»СЋР·РёРІРЅС‹ РґР»СЏ Chromium.

### Roadmap

- [x] **РќР°СЃС‚РѕСЏС‰РёР№ CDP РЅР° РїСЂРѕС„РёР»СЊ** вЂ” СѓРЅРёРєР°Р»СЊРЅС‹Р№ `--remote-debugging-port` РЅР° РїСЂРѕС„РёР»СЊ, РІС‹РґР°РµС‚СЃСЏ С‡РµСЂРµР· `/user/{id}/cdp`.
- [x] **Live View, СЃС‚Р°С‚СѓСЃС‹ Р°РєРєР°СѓРЅС‚РѕРІ, СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ, Docker** вЂ” РґРѕР±Р°РІР»РµРЅС‹ РІ 0.3.0.
- [x] **РџРѕРґРјРµРЅР° WebRTC IP С‡РµСЂРµР· ICE-РєР°РЅРґРёРґР°С‚С‹** вЂ” `webrtc_mode: proxy` РїРµСЂРµРїРёСЃС‹РІР°РµС‚ host-РєР°РЅРґРёРґР°С‚С‹ РЅР° `webrtc_public_ip` РїСЂРѕС„РёР»СЏ.
- [x] **РРЅС‚РµРіСЂР°С†РёСЏ MCP РІ UI** вЂ” РѕС‚РѕР±СЂР°Р¶РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° MCP РІ РїР°РЅРµР»Рё РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ (0.9.0).
- [x] **РџРѕРёСЃРє Рё СѓСЃС‚Р°РЅРѕРІРєР° СЂР°СЃС€РёСЂРµРЅРёР№** вЂ” РєР°С‚Р°Р»РѕРі СЂР°СЃС€РёСЂРµРЅРёР№ (unpacked, Web Store ID) РґРѕР±Р°РІР»РµРЅ РІ 0.9.0.
- [x] **РРµСЂР°СЂС…РёСЏ РіСЂСѓРїРї `/group/tree`** вЂ” РґРµСЂРµРІРѕ РїР°РїРѕРє, Р±РµР·РѕРїР°СЃРЅРѕРµ СѓРґР°Р»РµРЅРёРµ, update/delete РІ UI (1.0.0).
- [ ] **FingerprintJS-РёРЅС‚РµРіСЂР°С†РёСЏ** вЂ” РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ fingerprintjs/fingerprintjs РґР»СЏ РїСЂРѕРІРµСЂРєРё РѕР±РЅР°СЂСѓР¶РµРЅРёСЏ.

---

## 20. РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ

| Variable | Default | Purpose |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | Root for `antique.db` + profile user data dirs |
| `ANTIQUE_DB` | `<data_dir>/antique.db` | SQLite path override |
| `ANTIQUE_BROWSER_CHANNEL` | (unset, uses bundled Chromium) | Playwright browser channel: `chrome`, `msedge`, `chromium-beta` |
| `ANTIQUE_API_TOKEN` | (unset, open) | Р•СЃР»Рё Р·Р°РґР°РЅ, REST API С‚СЂРµР±СѓРµС‚ Р·Р°РіРѕР»РѕРІРѕРє `Authorization: Bearer <token>` |
| `ANTIQUE_ALLOWED_ORIGINS` | (unset) | Р Р°Р·РґРµР»РµРЅРЅС‹Р№ Р·Р°РїСЏС‚С‹РјРё СЃРїРёСЃРѕРє СЂР°Р·СЂРµС€РµРЅРЅС‹С… РїРѕРґСЃС‚СЂРѕРє Origin РґР»СЏ СѓРґР°Р»РµРЅРЅРѕРіРѕ/С‚СѓРЅРЅРµР»СЊРЅРѕРіРѕ РґРѕСЃС‚СѓРїР° (РЅР°РїСЂРёРјРµСЂ, `ngrok-free.app`). Localhost СЂР°Р·СЂРµС€РµРЅ РІСЃРµРіРґР°. РўСЂРµР±СѓРµС‚СЃСЏ, РµСЃР»Рё РґР°С€Р±РѕСЂРґ РѕС‚РєСЂС‹РІР°РµС‚СЃСЏ С‡РµСЂРµР· РІРЅРµС€РЅРёР№ С‚СѓРЅРЅРµР»СЊ, РёРЅР°С‡Рµ Origin-guard РІС‹РґР°СЃС‚ 403. |
| `ANTIDETECT_ENGINE` | `chromium` | Р”РµС„РѕР»С‚РЅС‹Р№ Р±СЂР°СѓР·РµСЂРЅС‹Р№ РґРІРёР¶РѕРє: `chromium`, `firefox`, `camoufox` |
| `PYTHONIOENCODING` | (auto UTF-8) | CLI СЃР°Рј С„РѕСЂСЃРёСЂСѓРµС‚ UTF-8 РІС‹РІРѕРґ; Р·Р°РґР°РІР°Р№С‚Рµ `utf-8` С‚РѕР»СЊРєРѕ РµСЃР»Рё РѕС‚РєР»СЋС‡Р°РµС‚Рµ С„РёРєСЃ |
| `HOST` (CLI only) | `127.0.0.1` | Bind address for `serve` |
| `UI_PORT` (CLI only) | `8080` | Port for `serve` |

---

## 21. Р›РёС†РµРЅР·РёСЏ

MIT вЂ” СЃРјРѕС‚СЂРёС‚Рµ `LICENSE`.