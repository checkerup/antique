[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md) [![Русский](https://img.shields.io/badge/lang-Русский-red.svg)](README.ru.md) [![中文](https://img.shields.io/badge/lang-中文-green.svg)](README.zh.md)

# antique

**дёЂдёЄи‡Єж‰з®ЎгЂЃејЂжєђзљ„ AdsPower ж›їд»Јж–№жЎ€ вЂ”вЂ” е¤љ profile жµЏи§€е™Ёе†њењєпјЊе…·е¤‡ fingerprint дјЄиЈ…гЂЃproxy иЅ®жЌўгЂЃ.adb bundle еЇје…ҐпјЊд»ҐеЏЉ AdsPower е…је®№зљ„ REST APIгЂ‚**

> и‡Єдё»жћ„е»єпјЊз”ЁдєЋж›їд»Јд»иґ№зљ„ AdsPower и®ўй…пјЊдїќжЊЃз›ёеђЊзљ„ UX е’Њ API жЋҐеЏЈпјЊж— йњЂжЋ€жќѓпјЊе®Ње…Ёжњ¬ењ°иїђиЎЊгЂ‚


---

## з›®еЅ•

1. [иї™жЇд»Ђд№€пј€з»™ agent зљ„ TL;DRпј‰](#1-иї™жЇд»Ђд№€з»™-agent-зљ„-tldr)
2. [еї«йЂџејЂе§‹](#2-еї«йЂџејЂе§‹)
3. [жћ¶жћ„ж¦‚и§€](#3-жћ¶жћ„ж¦‚и§€)
4. [жЁЎеќ—з»“жћ„](#4-жЁЎеќ—з»“жћ„)
5. [ж•°жЌ®жЁЎећ‹дёЋе­е‚Ё schema](#5-ж•°жЌ®жЁЎећ‹дёЋе­е‚Ё-schema)
6. [Profile з”џе‘Ѕе‘Ёжњџ](#6-profile-з”џе‘Ѕе‘Ёжњџ)
7. [CLI еЏ‚иЂѓ](#7-cli-еЏ‚иЂѓ)
8. [REST API еЏ‚иЂѓ](#8-rest-api-еЏ‚иЂѓ)
9. [Cookie еЇје…Ґ / еЇје‡єж јејЏ](#9-cookie-еЇје…Ґ--еЇје‡єж јејЏ)
10. [Fingerprint зі»з»џ](#10-fingerprint-зі»з»џ)
11. [е®Њж•ґ profileпј€.adbпј‰еЇје…ҐжµЃзЁ‹](#11-е®Њж•ґ-profileadb-еЇје…ҐжµЃзЁ‹)
12. [CDP multiplexer](#12-cdp-multiplexer)
13. [ж•°жЌ®з›®еЅ•еёѓе±Ђ](#13-ж•°жЌ®з›®еЅ•еёѓе±Ђ)
14. [жµ‹иЇ•](#14-жµ‹иЇ•)
15. [е·ІзџҐй™ђе€¶дёЋ roadmap](#15-е·ІзџҐй™ђе€¶дёЋ-roadmap)
16. [зЋЇеўѓеЏй‡Џ](#16-зЋЇеўѓеЏй‡Џ)
17. [License](#17-license)

---

## 1. иї™жЇд»Ђд№€пј€з»™ agent зљ„ TL;DRпј‰

antique жЇдёЂдёЄ Python жњЌеЉЎпјЊеЉџиѓЅе¦‚дё‹пјљ

- дёєжЇЏдёЄ profile еђЇеЉЁз‹¬з«‹зљ„ Chromium contextпј€Playwright `launch_persistent_context`пј‰вЂ”вЂ” жЇЏдёЄ profile ж‹Ґжњ‰и‡Єе·±зљ„ user data dirгЂЃcookiesгЂЃlocalStorageгЂЃIndexedDBгЂ‚
- з”џж€ђе†…йѓЁдёЂи‡ґзљ„ browser fingerprintпј€UAгЂЃnavigatorгЂЃscreenгЂЃtimezoneгЂЃlocaleгЂЃWebGL vendor/rendererгЂЃaudio + canvas noise seedпј‰пјЊе№¶жіЁе…Ґ JS init script ењЁеђЇеЉЁж—¶еЇ№жµЏи§€е™Ёиї›иЎЊ patchгЂ‚
- ењЁ SQLiteпј€`data/antique.db`пј‰дё­жЊЃд№…еЊ– profile вЂ”вЂ” еЊ…ж‹¬ proxyгЂЃfingerprintгЂЃcookiesгЂЃtagsгЂЃsessions д»ҐеЏЉеЇје…Ґз›ёе…ізљ„е…ѓж•°жЌ®гЂ‚
- еЇје…Ґд»Ћ AdsPower еЇје‡єзљ„ `.adb` profile bundleпј€cookies + LocalStorage + IndexedDBпј‰гЂ‚еЇје…Ґй‡‡з”ЁеЋџз”џ Chromium иЇ»еЏ–пјЊиЂЊйќћи„†еј±зљ„ LevelDB и§Јжћђ вЂ”вЂ” ж€‘д»¬жЉЉжєђз›®еЅ•ж‹·иґќе€° Playwright зљ„ `user_data_dir`пјЊи®© Chromium и‡Єе·±иЇ»еЏ–гЂ‚
- ењЁ `http://127.0.0.1:<port>/...` дёЉжљґйњІ AdsPower е…је®№зљ„ REST APIпјЊе› ж­¤е·Із»ЏеЇ№жЋҐ AdsPower зљ„зЋ°жњ‰и„љжњ¬еЏЄйњЂдї®ж”№ base URL еЌіеЏЇе€‡жЌўгЂ‚
- ењЁ `/`пј€ж€– `/dashboard`пј‰жЏђдѕ›дёЂдёЄеЌ•йЎµ dashboardпјЊењЁ `/docs` жЏђдѕ› FastAPI SwaggerгЂ‚
- 340+ дёЄ pytest жµ‹иЇ•йЂљиї‡гЂ‚
- еЏЇж›ґжЌўзљ„жµЏи§€е™Ёеј•ж“ЋпјљChromium, Google Chrome, Microsoft Edge, Firefox, Camoufoxпј€еј•ж“Ћзє§ж·±е±‚йІе…іиЃ”пј‰, WebKitгЂ‚
- дёЂй”®ејЏ AdsPower е¤‡д»ЅеЇје…Ґпј€еЇје…Ґж•ґдёЄе¤‡д»Ѕз›®еЅ•ж€–еЌ•дёЄ profileпј‰пјЊдїќз•™ user_id, cookies, proxy, tagsгЂ‚
- ж”ЇжЊЃдє®и‰І/жљ—и‰Ідё»йўгЂЃеј•ж“ЋйЂ‰ж‹©е™ЁгЂЃAdsPower еЇје…ҐгЂЃзЅ‘йЎµз«Ї Live ViewгЂЃд»ҐеЏЉиґ¦еЏ·зЉ¶жЂЃж ‡з­ѕзљ„ DashboardгЂ‚
- Live Viewпј€иїђиЎЊдё­ profile зљ„е®ћж—¶ж€Єе›ѕпј‰гЂЃзњџе®ћзљ„ profile зє§е€« CDP з«ЇеЏЈгЂЃе№¶еЏ‘е¤љ profile и‡ЄеЉЁеЊ–еђЊж­Ґпј€ењЁе¤љ profile й—ґеђЊж­ҐиїђиЎЊеђЊдёЂжµЃзЁ‹пј‰пјЊд»ҐеЏЉ Docker дёЂй”®иїђиЎЊгЂ‚
- ж‰№й‡Џж“ЌдЅњпјљж”ЇжЊЃж‰№й‡ЏеђЇеЉЁ/еЃњж­ў/е€ й™¤/еЇје‡є profileпјЊж‰№й‡ЏеЇје…Ґе’Ње€†й…Ќд»Јзђ†гЂ‚
- е€†з»„з®Ўзђ†дёЋиї‡ж»¤гЂ‚
- д»Јзђ†еЃҐеє·еє¦жЈЂжџҐпј€жЈЂжµ‹е‡єеЏЈ IP дёЋзЅ‘з»ње»¶иїџпј‰гЂ‚
- з›ґжЋҐењЁ Dashboard з•Њйќўзј–иѕ‘жЊ‡зє№дїЎжЃЇгЂ‚

**е®ѓиїдёЌжЇпј€е°љжњЄе®ћзЋ°зљ„еЉџиѓЅпј‰пјљ**

- дёЌжЇдёєж•°еЌѓдёЄ profile и®ѕи®Ўзљ„ж— е¤ґжµЏи§€е™Ёе†њењє вЂ”вЂ” и®ѕи®Ўз›®ж ‡жЇеЌ•жњєе‡ еЌЃдёЄ profileгЂ‚
- дёЌжЇе¤љз”Ёж€·й‰ґжќѓе±‚ вЂ”вЂ” еЌ•иї›зЁ‹пјЊREST API й»и®¤ж— й‰ґжќѓпјЊжњ¬ењ°иїђиЎЊгЂ‚
- дёЌжЇ proxy provider вЂ”вЂ” дЅїз”ЁдЅ жЏђдѕ›зљ„ proxyгЂ‚

**дЅ•ж—¶дЅїз”Ёе®ѓпјљ** еЅ“йњЂи¦ЃдёЂдёЄ AdsPower е…је®№зљ„жњ¬ењ°жµЏи§€е™Ёе†њењєпјЊе…·е¤‡е®Њж•ґ profile йљ”з¦»гЂЃfingerprint жЋ§е€¶е’Њ .adb bundle еЇје…ҐиѓЅеЉ›ж—¶ вЂ”вЂ” е№¶дё”дёЌжѓідёє AdsPower д»иґ№гЂ‚

**дЅ•ж—¶дёЌи¦ЃдЅїз”Ёе®ѓпјљ** еЅ“дЅ йњЂи¦ЃеЌ•еЏ°жњєе™ЁдёЉ >100 дёЄе№¶еЏ‘ browser contextгЂЃйњЂи¦Ѓи·Ёиї›зЁ‹ profile е…±дє«пјЊж€–иЂ…йњЂи¦ЃдёЂдёЄж‰з®Ўдє‘ж–№жЎ€ж—¶гЂ‚

---

## 2. еї«йЂџејЂе§‹

### зЋЇеўѓи¦Ѓж±‚

- Python 3.10+
- Windows / macOS / Linux
- Playwrightпј€`pip install playwright && playwright install chromium`пј‰

### е®‰иЈ…

```bash
git clone https://github.com/<your-org>/antique
cd antique
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
playwright install chromium
```

### еђЇеЉЁжњЌеЉЎ

```bash
python -m src.cli serve --ui-port 8080
```

иї™е°†дёєдЅ жЏђдѕ›пјљ

- Dashboardпјљ<http://127.0.0.1:8080/>
- REST APIпјљ<http://127.0.0.1:8080/user/list>
- API ж–‡жЎЈпјљ<http://127.0.0.1:8080/docs>
- еЃҐеє·жЈЂжџҐпјљ<http://127.0.0.1:8080/health>

### е€›е»єдёЂдёЄ profile е№¶еђЇеЉЁе®ѓ

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

ж€–иЂ…йЂљиї‡ REST APIпјљ

```bash
curl -X POST http://127.0.0.1:8080/user/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Profile 1", "tags": ["test"]}'

curl -X POST http://127.0.0.1:8080/user/start \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<user_id>"}'
```

### еЇје…ҐдёЂдёЄ AdsPower `.adb` bundle

```bash
# Cookies only (fast, works with .txt/.json/.adb/.zip/.tar.gz)
python -m src.cli import-cookies path/to/bundle.adb --name "Imported"

# Full profile вЂ” copies LocalStorage + IndexedDB into the new profile
python -m src.cli import-cookies path/to/bundle.adb --full --name "Full import"
```

---

## 3. жћ¶жћ„ж¦‚и§€

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

**дё‰е±‚жћ¶жћ„пјљ**

1. **е­е‚Ёе±‚**пј€`src/core/storage.py`гЂЃ`src/core/profile.py`пј‰вЂ”вЂ” SQLModel/SQLiteгЂ‚ProfileгЂЃsessionгЂЃtagгЂЃgroupпјЊд»ҐеЏЉ proxy/fingerprint/cookies д»Ґ JSON зј–з Ѓе€—зљ„еЅўејЏе­е‚ЁгЂ‚
2. **жµЏи§€е™Ёе±‚**пј€`src/core/browser.py`гЂЃ`src/core/cdp.py`гЂЃ`src/core/fingerprint.py`гЂЃ`src/core/cookie.py`пј‰вЂ”вЂ” Playwright persistent contextгЂЃfingerprint JS жіЁе…ҐгЂЃCDP multiplexerгЂЃcookie/profile еЇје…ҐгЂ‚
3. **жЋҐеЏЈе±‚**пј€`src/api/server.py`гЂЃ`src/api/routes.py`гЂЃ`src/cli.py`гЂЃ`src/ui/dashboard.py`пј‰вЂ”вЂ” FastAPI REST + WSгЂЃtyper CLIгЂЃеЌ•йЎµ HTML dashboardгЂ‚

---

## 4. жЁЎеќ—з»“жћ„

```
src/
в”њв”Ђв”Ђ __init__.py
в”њв”Ђв”Ђ cli.py                         в†ђ typer CLI (serve, create, list, start, stop, delete,
в”‚                                    import-cookies, reimport, export-cookies, fingerprint)
в”њв”Ђв”Ђ core/
в”‚   в”њв”Ђв”Ђ __init__.py
в”‚   в”њв”Ђв”Ђ storage.py                 в†ђ SQLModel models (ProfileRecord, SessionRecord, TagRecord,
в”‚   в”‚                                 GroupRecord) + engine/session helpers
в”‚   в”њв”Ђв”Ђ profile.py                 в†ђ Profile dataclassпј€е…¬ејЂпј‰+ ProfileStoreпј€CRUDпј‰
в”‚   в”њв”Ђв”Ђ fingerprint.py             в†ђ Fingerprint dataclass + generate_fingerprint() + JS init
в”‚   в”‚                                 script жЁЎжќї + Playwright launch options
в”‚   в”њв”Ђв”Ђ proxy.py                   в†ђ ProxyConfig + parse_proxy() + AdsPowerв†”Playwright
в”‚   в”‚                                 ж јејЏдє’иЅ¬
в”‚   в”њв”Ђв”Ђ cookie.py                  в†ђ Cookie dataclassгЂЃNetscape/JSON/.adb parserгЂЃ
в”‚   в”‚                                 LocalStorage + IndexedDB жЉЅеЏ–дёЋж‹·иґќ
в”‚   в”њв”Ђв”Ђ browser.py                 в†ђ BrowserLauncher вЂ”вЂ” еђЇеЉЁ persistent Chromium contextпјЊи®°еЅ• sessionпјЊеє”з”ЁеЇје…Ґзљ„е€ќе§‹зЉ¶жЂЃ
в”‚   в”њв”Ђв”Ђ cdp.py                     в†ђ CDPProxy вЂ”вЂ” ењЁе¤љдёЄ user_id й—ґе¤Ќз”ЁеЌ•дёЄ debug portпјЊжљґйњІ /json/list + WS и·Їз”±
в”‚   в”њв”Ђв”Ђ automation.py              в†ђ Cookie Robot / ж— д»Јз Ѓи‡ЄеЉЁеЊ–жµЃзЁ‹ж‰§иЎЊе™Ёпј€Step жЁЎећ‹пјЊparse_flowпјЊcookie_robot_flowпјЊFlowRunnerпј‰
в”‚   в”њв”Ђв”Ђ portable.py                в†ђ дѕїжђєејЏ .antq й…ЌзЅ®ж–‡д»¶еЇје…Ґ/еЇје‡єпј€build_bundleпјЊexport_profileпјЊimport_profileпј‰
в”‚   в”њв”Ђв”Ђ geo.py                     в†ђ ењ°зђ†дЅЌзЅ®еЊ№й…Ќпјље›Ѕе®¶/е‡єеЏЈд»Јзђ† в†’ ж—¶еЊє/иЇ­иЁЂ/з»Џзє¬еє¦ (geo_for_country, geo_from_proxy, apply_geo_to_fingerprint)
в”‚   в”њв”Ђв”Ђ proxy_pool.py              в†ђ д»Јзђ†ж± е’ЊиЅ®жЌўз­–з•Ґпј€sticky/round_robin/randomпј‰
в”‚   в”њв”Ђв”Ђ detect.py                  в†ђ жЊ‡зє№йІе…іиЃ”и‡ЄжЈЂжњєе€¶пј€build_collector_script, score_reportпј‰
в”‚   в”њв”Ђв”Ђ engines.py                 в†ђ жµЏи§€е™Ёеј•ж“ЋжіЁе†ЊиЎЁ (EngineSpec, resolve_engine, list_engines)
в”‚   в”њв”Ђв”Ђ sync.py                    в†ђ е¤љ profile еђЊж­Ґи‡ЄеЉЁеЊ–е¤„зђ†е™Ё (run_sync_flow, FlowTask)
в”‚   в”њв”Ђв”Ђ fingerprint_ops.py         в†ђ ж™єиѓЅж‰№й‡ЏжЊ‡зє№йљЏжњєеЊ–пјЊж”ЇжЊЃе­—ж®µз»„е…±дє«/й”Ѓе®љ
в”‚   в”њв”Ђв”Ђ socks_bridge.py            в†ђ жњ¬ењ° SOCKS5 д»Јзђ†жЋ€жќѓжЎҐжЋҐе™Ёпј€и§Је†і Chromium дёЌж”ЇжЊЃеё¦иґ¦еЏ·еЇ†з Ѓзљ„ SOCKS5 й—®йўпј‰
в”‚   в”њв”Ђв”Ђ operations.py              в†ђ жЁЎжќїж‰№й‡Џе€›е»єгЂЃAES-GCM еЉ еЇ†еї«з…§гЂЃе¤‡д»Ѕйў„и§€дёЋж“ЌдЅње®Ўи®Ў
в”‚   в”њв”Ђв”Ђ providers.py               в†ђ жњ¬ењ°/иїњзЁ‹д»Јзђ†жєђжЏђеЏ–е™Ёпј€ж”ЇжЊЃ File/JSON/HTTP-JSONпј‰
в”‚   в””в”Ђв”Ђ backup_scheduler.py        в†ђ жњ¬ењ°еЉ еЇ†е¤‡д»Ѕи®Ўе€’з®Ўзђ†е™Ёпј€ж”ЇжЊЃ AES-GCM дёЋе¤љж—¶ж®µи®ѕзЅ®пј‰
в”њв”Ђв”Ђ api/
в”‚   в”њв”Ђв”Ђ __init__.py
в”‚   в”њв”Ђв”Ђ server.py                  в†ђ FastAPI app factoryгЂЃCORSгЂЃжЊ‚иЅЅ UI дёЋ API и·Їз”±
в”‚   в””в”Ђв”Ђ routes.py                  в†ђ ж‰Ђжњ‰ REST з«Їз‚№ + WS handler
в””в”Ђв”Ђ ui/
    в”њв”Ђв”Ђ __init__.py
    в”њв”Ђв”Ђ dashboard.py               в†ђ еЌ•йЎµ HTML dashboard и·Їз”±
    в””в”Ђв”Ђ templates/
        в””в”Ђв”Ђ index.html             в†ђ Dashboard SPAпј€еЋџз”џ JS + fetch()пј‰

tests/
в”њв”Ђв”Ђ test_fingerprint.py            в†ђ Fingerprint з”џж€ђгЂЃinit script жіЁе…Ґ
в”њв”Ђв”Ђ test_cookie.py                 в†ђ Cookie и§Јжћђпј€ж‰Ђжњ‰ж јејЏпј‰+ .adb bundle е¤„зђ†
в”њв”Ђв”Ђ test_profile.py                в†ђ ProfileStore CRUD
в”њв”Ђв”Ђ test_proxy.py                  в†ђ Proxy config ж ЎйЄЊ
в”њв”Ђв”Ђ test_storage.py                в†ђ SQLite engine + иїЃз§»
в””в”Ђв”Ђ test_profile_import.py         в†ђ е®Њж•ґ profile .adb еЇје…ҐжµЃзЁ‹пј€ж–°еўћпј‰
```

---

## 5. ж•°жЌ®жЁЎећ‹дёЋе­е‚Ё schema

ж•°жЌ®еє“пјљ`data/antique.db`пј€SQLiteпјЊеЌ•ж–‡д»¶пј‰гЂ‚

### иЎЁз»“жћ„

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

### дёєд»Ђд№€и¦Ѓз”Ё JSON зј–з Ѓе€—пјџ

ProxyгЂЃfingerprint е’Њ cookies йѓЅжЇеј‚жћ„зљ„ dict/listпјЊеЊ…еђ«е¤§й‡ЏеЏЇйЂ‰е­—ж®µгЂ‚JSON зј–з Ѓзљ„ TEXT е€—йЃїе…Ќдє†гЂЊзЁЂз–ЏиЎЁ + е¤§й‡Џе€—гЂЌзљ„й—®йўпјЊд№џи®©иїЃз§»еЏеѕ—з®ЂеЌ•гЂ‚д»Јд»·жЇпјљж— жі•ењЁ SQL е±‚йќўжџҐиЇў fingerprint е­—ж®µпјЊдЅ†ж€‘д»¬е№¶дёЌйњЂи¦Ѓиї™з§ЌжџҐиЇўгЂ‚

### Profile dataclass vs ProfileRecord

- `Profile`пј€ењЁ `src/core/profile.py`пј‰вЂ”вЂ” е…¬ејЂзљ„ dataclassгЂ‚дёЋе­е‚Ёи§ЈиЂ¦пјЊйЃїе…Ќ API жі„жјЏ SQLModel з»†иЉ‚гЂ‚
- `ProfileRecord`пј€ењЁ `src/core/storage.py`пј‰вЂ”вЂ” жЊЃд№…еЊ–зљ„иЎЊгЂ‚`_record_to_profile()` з”± `ProfileRecord` жћ„е»є `Profile`гЂ‚

---

## 6. Profile з”џе‘Ѕе‘Ёжњџ

```
           в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
           в”‚ created  в”‚  в†ђ POST /user/create, cli create, import-cookies
           в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                в”‚
                в–ј
           в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
           в”‚ idle     в”‚  в†ђ profile е·Іе­ењЁпјЊдЅ†жµЏи§€е™ЁжњЄеђЇеЉЁ
           в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                в”‚  POST /user/start  or  cli start
                в–ј
           в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
           в”‚ running  в”‚  в†ђ Playwright persistent context е¤„дєЋжґ»и·ѓзЉ¶жЂЃ
           в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”
                в”‚  POST /user/stop  or  cli stop
                в–ј
           в”Њв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”ђ
           в”‚ stopped  в”‚  в†ђ context е·Іе…ій—­пјЊSessionRecord.status = 'stopped'
           в””в”Ђв”Ђв”Ђв”Ђв”¬в”Ђв”Ђв”Ђв”Ђв”Ђв”

 (any state) в”Ђв”Ђв–є deleted   в†ђ POST /user/delete, cli deleteпј€зє§иЃ”е€ й™¤ sessionsпј‰
```

### е®Њж•ґ profile еЇје…Ґз”џе‘Ѕе‘Ёжњџпј€йўќе¤–пј‰

```
 created в†’ import_source_path е·Іи®ѕзЅ® в†’ (й¦–ж¬ЎеђЇеЉЁ) в†’ ж‹·иґќ LocalStorage/IDB
                                                     в†’ initial_state_applied = True
                                                     в†’ (еђЋз»­еђЇеЉЁи·іиї‡ж‹·иґќ)
```

`initial_state_applied` ж ‡еї—зЎ®дїќж€‘д»¬еЏЄж‹·иґќжєђ bundle зљ„ `Local Storage/leveldb/` е’Њ `IndexedDB/` дёЂж¬ЎгЂ‚й‡Ќж–°еЇје…ҐйњЂи¦ЃдЅїз”Ё `cli reimport <user_id>` ж€– `POST /user/{id}/reimport`пјЊе®ѓд»¬дјљй‡ЌзЅ®иЇҐж ‡еї—гЂ‚

---

## 7. CLI еЏ‚иЂѓ

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
python -m src.cli engines                                        # е€—е‡єж”ЇжЊЃзљ„жµЏи§€е™Ёеј•ж“ЋеЏЉе…¶йІе…іиЃ”з­‰зє§
python -m src.cli create ... [--engine chromium|chrome|edge|firefox|camoufox|webkit] # е€›е»єжЊ‡е®љеј•ж“Ћзљ„ profile
python -m src.cli import-backup PATH [--overwrite] [--limit N]   # еЇје…Ґ AdsPower е¤‡д»Ѕз›®еЅ•
python -m src.cli clone USER_ID [--name NAME] [--user-id NEW_ID] # е…‹йљ† profile (е¤Ќе€¶жЊ‡зє№гЂЃд»Јзђ†гЂЃCookie еЏЉж ‡з­ѕ)
python -m src.cli bulk-status USER_ID [USER_ID ...] STATUS      # ж‰№й‡Џдї®ж”№иґ¦еЏ·зЉ¶жЂЃ
python -m src.cli list ... [--sort name|launches|...] [--order asc|desc] # ж”ЇжЊЃ 13 з§Ќе­—ж®µжЋ’еєЏе’ЊеЌ‡й™ЌеєЏйЂ‰ж‹©
python -m src.cli fingerprint [--seed SEED] [--os windows|macos|linux]
python -m src.cli preview-backup PATH                                # йў„и§€ AdsPower е¤‡д»Ѕз›®еЅ•иЂЊдёЌе®ћй™…еЇје…Ґ
python -m src.cli template-create TEMPLATE.json [--count N] [--seed S] # дЅїз”Ё JSON жЁЎжќїж‰№й‡Џе€›е»є profile
python -m src.cli snapshot-export PATH                               # еЇје‡є AES-GCM еЉ еЇ†зљ„ profile е¤‡д»Ѕеї«з…§
python -m src.cli snapshot-import PATH [--overwrite]                 # д»ЋеЉ еЇ†еї«з…§дё­жЃўе¤Ќ profile е¤‡д»Ѕ
python -m src.cli activity [--user USER_ID] [--limit N]              # жџҐзњ‹ж“ЌдЅње®Ўи®ЎеЋ†еЏІж—Ґеї—
python -m src.cli backup-schedule DESTINATION [--interval-minutes MIN] # жіЁе†Њжњ¬ењ°еЉ еЇ†е¤‡д»Ѕи®Ўе€’жµЃзЁ‹
python -m src.cli backup-schedules                                   # е€—е‡єж‰Ђжњ‰жіЁе†Њзљ„е¤‡д»Ѕи®Ўе€’
```

### йЂЂе‡єз Ѓ

- `0` вЂ”вЂ” ж€ђеЉџ
- `1` вЂ”вЂ” з”Ёж€·й”™иЇЇпј€еЏ‚ж•°зјєе¤±гЂЃжњЄж‰ѕе€° profileгЂЃж јејЏж— ж•€пј‰
- йќћй›¶ вЂ”вЂ” typer е›  shell й”™иЇЇиї”е›ћ

### зЋЇеўѓеЏй‡Џ

еЏ‚и§Ѓ [зЋЇеўѓеЏй‡Џ](#16-зЋЇеўѓеЏй‡Џ)гЂ‚

---

## 8. REST API еЏ‚иЂѓ

Base URLпјљ`http://127.0.0.1:<ui-port>`пј€еђЊдёЂз«ЇеЏЈеђЊж—¶жЏђдѕ› UI е’Њ APIпј›AdsPower ењЁ 50325 дёЉз‹¬з«‹жЏђдѕ›пј‰гЂ‚

ж‰Ђжњ‰ response еќ‡дЅїз”Ё AdsPower ж јејЏпјљ`{"code": 0, "msg": "success", "data": {...}}`гЂ‚

### Health

```http
GET /health
в†’ {"status": "ok", "service": "antique", "version": "0.1.0"}
```

### Profiles

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

### Geo / proxy-pool / portable / detect / chain / sync

```http
GET  /geo/countries
в†’ {code:0, data:{countries:["US","DE",...]}}

POST /user/{user_id}/geo/match      Body: {country?: "DE"}   # и‹Ґдёєз©єпјЊе€™д»ЋиЇҐ profile з»‘е®љзљ„д»Јзђ†е›Ѕе®¶и‡ЄеЉЁжЋЁеЇј
в†’ еЇ№йЅђж—¶еЊє/иЇ­иЁЂ/ењ°зђ†дЅЌзЅ®пј›жЊЃд№…еЊ–е№¶е†™е…Ґ fingerprint

POST /proxy/pool/next               Body: {proxy_list, strategy?: sticky|round_robin|random, user_id?}
в†’ {code:0, data:{proxy:{...}, assigned, server}}   # йЂ‰ж‹©жЂ§з»‘е®љд»Јзђ†з»™жЊ‡е®љзљ„ user_id

POST /user/{user_id}/export/portable
в†’ {code:0, data:{bundle:{...}}}   # .antq ж‰“еЊ…ж•°жЌ® (fingerprint+proxy+cookies+tags)

POST /user/import/portable          Body: {bundle:{...}, name?, user_id?}
в†’ {code:0, data:{user_id, name, cookie_count}}

POST /detect/score                  Body: {signals:{...}, expected?:{...}}
в†’ {code:0, data:{score, grade, ok, checks, failures}}   # зєЇжЊ‡зє№жЈЂжµ‹иЇ„е€†пјЊж— йњЂиїђиЎЊжµЏи§€е™Ё

GET  /engine/list
в†’ {code:0, data:{list:[{key,label,base,stealth,channel,needs_install,supports_extensions,supports_cdp}]}}

POST /user/import/backup            Body: {source_path, overwrite?, limit?}
в†’ {code:0, data:{imported_count, updated_count, skipped_count, error_count, ...}}

POST /user/import/backup/preview    Body: {source_path}
в†’ {code:0, data:{profiles:[...], total_count, groups:[...], tags:[...]}} # йў„и§€ AdsPower е¤‡д»Ѕ

POST /user/template/create          Body: {template, count, seed?}
в†’ {code:0, data:{created_count, user_ids:[...]}}  # жЁЎжќїж‰№й‡Џе€›е»є

POST /user/snapshot/export          Body: {path, password, overwrite?}
в†’ {code:0, data:{path}}                           # еЇје‡єеЉ еЇ†еї«з…§ (AES-GCM)

POST /user/snapshot/import          Body: {path, password, overwrite?}
в†’ {code:0, data:{imported_count, updated_count, skipped_count}} # еЇје…ҐеЉ еЇ†еї«з…§

GET  /activity?user_id=...&action=...&limit=...  в†’ иЋ·еЏ–ж“ЌдЅње®Ўи®Ўж—Ґеї—е€—иЎЁ (ж”ЇжЊЃз”Ёж€·дёЋеЉЁдЅњиї‡ж»¤)

POST /activity/export               Body: {path, user_id?, action?}
в†’ {code:0, data:{path, count}}      # е°†ж“ЌдЅње®Ўи®Ўж—Ґеї—еЇје‡єдёє JSON ж–‡д»¶

GET  /resource/status                в†’ иЋ·еЏ–зі»з»џиµ„жєђеЌ з”ЁзЉ¶жЂЃ (PIDгЂЃжґ»еЉЁиї›зЁ‹ж•°)

GET  /mcp/status                     в†’ иЋ·еЏ– MCP жњЌеЉЎз«ЇиїђиЎЊзЉ¶жЂЃеЏЉж”ЇжЊЃзљ„е·Ґе…·е€—иЎЁ

GET  /proxy/providers/kinds          в†’ иЋ·еЏ–ж”ЇжЊЃзљ„жњ¬ењ°д»Јзђ†жєђз±»ећ‹е€—иЎЁ (file, json, http-json)

POST /proxy/providers/test          Body: {name, kind, source, enabled?}
в†’ {code:0, data:{provider, count, proxies:[...]}} # жµ‹иЇ•еЉ иЅЅжњ¬ењ°д»Јзђ†жєђж•°жЌ®

POST /backup/schedules              Body: {destination, interval_minutes}
в†’ {code:0, data:{schedule:{schedule_id, destination, interval_minutes, enabled, next_run_at, last_run_at}}} # еўћеЉ е¤‡д»Ѕи®Ўе€’

GET  /backup/schedules              в†’ иЋ·еЏ–е·ІжіЁе†Ње¤‡д»Ѕи®Ўе€’е€—иЎЁ

POST /backup/schedules/run          Body: {schedule_id, password}
в†’ {code:0, data:{schedule:{...}}}   # ж‰‹еЉЁи§¦еЏ‘жЊ‡е®љеї«з…§е¤‡д»Ѕд»»еЉЎ

POST /group/create                  Body: {group_id, name, sort_order?, parent_id?}
в†’ {code:0, data:{group_id, name}}                 # е€›е»єе€†з»„ (ж”ЇжЊЃ parent_id е®ћзЋ°еµЊеҐ—е€†з»„)

POST /group/update                  Body: {group_id, name, sort_order?, parent_id?}
в†’ {code:0, data:{group_id, name}}                 # ж›ґж–°е€†з»„

POST /group/delete                  Body: {group_id} (embed=True)
в†’ {code:0, data:{group_id, deleted:true}}         # е€ й™¤е€†з»„

GET  /extension/list                в†’ иЋ·еЏ–е·Іе®‰иЈ…зљ„е…Ёе±Ђж‰©е±•зЁ‹еєЏе€—иЎЁ

POST /extension/install             Body: {source}
в†’ {code:0, data:{ext_id, name, version}} # йЂљиї‡жњ¬ењ°з›®еЅ•гЂЃ.crx ж–‡д»¶ж€– Chrome Web Store ID е®‰иЈ…ж‰©е±•зЁ‹еєЏ

POST /extension/uninstall           Body: {ext_id} (embed=True)
в†’ {code:0, data:{ext_id, uninstalled:true}} # еЌёиЅЅж‰©е±•зЁ‹еєЏ

POST /user/{user_id}/extensions     Body: List[str] (ж‰©е±•зЁ‹еєЏ ID е€—иЎЁ)
в†’ {code:0, data:{user_id, extensions:[...]}} # дёє profile е€†й…Ќж‰©е±•зЁ‹еєЏ

GET  /user/{user_id}/extensions     в†’ иЋ·еЏ–е€†й…Ќз»™иЇҐ profile зљ„ж‰©е±•зЁ‹еєЏ ID е€—иЎЁ

POST /user/clone                    Body: {user_id, name?, user_id_override?}
в†’ {code:0, data:{user_id, name, source_user_id}}

POST /user/bulk/status              Body: {user_ids:[...], account_status}
в†’ {code:0, data:{results:[{user_id, ok, error?}], updated_count}}

POST /user/bulk/fingerprint/randomize
Body: {user_ids:[...], os_family?, shared_fields?:["screen","gpu",...], preserve_fields?:["engine",...], seed?}
в†’ {code:0, data:{updated_count, user_ids:[...]}}

GET  /status/list                   в†’ йў„и®ѕиґ¦еЏ·зЉ¶жЂЃе€—иЎЁ
POST /user/{user_id}/status         Body: {account_status}
POST /user/{user_id}/screenshot     в†’ {code:0, data:{base64_png}}   # Live View ж€Єе›ѕ (йњЂе¤„дєЋиїђиЎЊзЉ¶жЂЃ)
GET  /user/{user_id}/cdp            в†’ {code:0, data:{webSocketDebuggerUrl, debug_port, ...}}  # зњџе®ћзљ„ CDP
POST /sync/run                      Body: {user_ids:[...], flow:[...], stop_on_error?, max_concurrency?}
в†’ {code:0, data:{ok, succeeded, total, results:[{user_id, ok, completed, total, error}]}}
```

### `/user/list` иї”е›ћзљ„ profile еЅўзЉ¶

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

## 9. Cookie еЇје…Ґ / еЇје‡єж јејЏ

### ж”ЇжЊЃзљ„еЇје…Ґж јејЏ

| ж јејЏ | жЈЂжµ‹ж–№ејЏ | иЇґжЋ |
|---|---|---|
| Netscape `cookies.txt` | `.txt` еђЋзјЂ | curl/wget ж јејЏпј›дЅїз”Ё tab ж€–з©єж ј |
| Playwright/CDP JSON | `.json` еђЋзјЂ | `{name, value, domain, ...}` dict зљ„е€—иЎЁ |
| AdsPower `.adb` | `.adb` / `.zip` / `.tar` / `.tgz` / ж–‡д»¶е¤№ | cookies + LocalStorage + IndexedDB |

### ж”ЇжЊЃзљ„еЇје‡єж јејЏ

- `json`пј€й»и®¤пј‰вЂ”вЂ” Playwright/Chrome DevTools ж јејЏ
- `netscape` вЂ”вЂ” йЂљз”Ё curl е…је®№зљ„ `cookies.txt`

### `import_cookies(path)` дё­зљ„и‡ЄеЉЁжЈЂжµ‹

```python
def import_cookies(path):
    p = Path(path)
    if p.is_dir() or p.suffix.lower() in (".adb", ".zip", ".tar", ".tgz"):
        return import_adspower_profile(p)
    if p.suffix.lower() == ".json":
        return import_cookies_json(p.read_text())
    return import_cookies_netscape(p.read_text())
```

### и§Јжћђ AdsPower `.adb`

`.adb` жЇдёЂдёЄ Chrome user-profile bundleпј€ж–‡д»¶е¤№гЂЃ`.zip` ж€– `.tar.gz`пј‰гЂ‚Chromium cookies иЎЁдЅЌдєЋ `<profile>/Default/Cookies`пј€SQLiteпј‰гЂ‚

Parser жµЃзЁ‹пјљ

1. е°†еЅ’жЎЈи§ЈеЋ‹е€°дёґж—¶з›®еЅ•пј€е¦‚йњЂи¦Ѓпј‰гЂ‚
2. йЃЌеЋ†жџҐж‰ѕ `*/Cookies` ж–‡д»¶пј›дје…€йЂ‰ж‹© `Default/Cookies`пјЊе›ћйЂЂе€° `Profile 1/2/3/Cookies`гЂ‚
3. д»Ґ RO жЁЎејЏж‰“ејЂ SQLite DBпј€`file:...?mode=ro`пј‰пј›и‹Ґиў«й”Ѓе®ље€™е›ћйЂЂе€°дёЂд»Ѕз§Ѓжњ‰дёґж—¶ж‹·иґќгЂ‚
4. иЇ»еЏ– cookies иЎЁгЂ‚е¤„зђ† schema е·®еј‚пј€ж—§з‰€ Chrome зјєе°‘ `samesite` е’Њ `is_persistent` е€—пј‰гЂ‚
5. е°† Chrome зљ„ `expires_utc`пј€Windows FILETIMEпјЊи‡Є 1601-01-01 иµ·зљ„еѕ®з§’ж•°пј‰иЅ¬жЌўдёє Unix epoch з§’гЂ‚

---

## 10. Fingerprint зі»з»џ

`Fingerprint` жЇдёЂз»„е†…йѓЁдёЂи‡ґзљ„гЂЃжµЏи§€е™ЁеЏЇи§Ѓе±ћжЂ§пјљ

- **Identity**пјљUser-AgentгЂЃnavigator.platform/vendor/oscpuгЂЃwebdriver flag
- **Screen**пјљwidth/height/colorDepth/pixelRatio + window.innerWidth/Height
- **Locale / timezone**пјљnavigator.languagesгЂЃIntl timezone
- **WebGL**пјљvendor + renderer е­—з¬¦дёІпј€йЂљиї‡ `WEBGL_debug_renderer_info`пј‰
- **WebGPU**пјљadapter vendor/architecture/descriptionпј€йЂљиї‡ `navigator.gpu.requestAdapter().requestAdapterInfo()`пј‰пјЊдёЋ WebGL GPU дёЂи‡ґпј›дЅїз”ЁиЅЇд»¶жёІжџ“зљ„ profile дјљз¦Ѓз”Ё `navigator.gpu`
- **Fonts**пјљжЇЏдёЄ OS з‹¬з«‹зљ„ж–‡д»¶е­—дЅ“з™ЅеђЌеЌ•пјЊйЂљиї‡ `document.fonts.check` ејєе€¶ж‰§иЎЊ
- **Audio**пјљз”ЁдєЋ AudioContext jitter зљ„зЎ®е®љжЂ§ noise seed
- **Canvas**пјљз”ЁдєЋ `toDataURL`/`toBlob` еѓЏзґ жЉ–еЉЁ зљ„зЎ®е®љжЂ§ noise seed
- **WebRTC**пјљйІж­ў IP жі„жјЏ вЂ”вЂ” `webrtc_mode`пј€`block` | `real` | `proxy`пј‰пјЊд»Ќе…је®№ж—§зљ„ `block_webrtc_ip` ж ‡еї—
- **Plugins**пјљйЂјзњџзљ„ Chrome plugin е€—иЎЁпј€2-5 жќЎпј‰
- **Connection**пјљtype/downlink/rttпј€Network Information APIпј‰
- **Hardware**пјљhardwareConcurrencyгЂЃdeviceMemory

### з”џж€ђ

```python
from src.core.fingerprint import generate_fingerprint

fp = generate_fingerprint()                                  # йљЏжњє
fp = generate_fingerprint(seed="my-profile-1")               # зЎ®е®љжЂ§
fp = generate_fingerprint(os_family="macos")                 # macOS UA + screen
```

дёЂи‡ґжЂ§и§„е€™пјљ

- OS family в†” UA в†” platform в†” vendor в†” screen
- Locale в†” timezone ж± пј€дѕ‹е¦‚ `en-GB` в†’ `Europe/London`пј‰
- WebGL vendor в†” rendererпј€NVIDIA vendor ж°ёиїњдёЌдјљдёЋ Apple GPU й…ЌеЇ№пј‰
- UA з‰€жњ¬дЅїз”Ёиѕѓж–°зљ„ Chromeпј€118-132пј‰

### жіЁе…Ґ

дё¤е±‚жњєе€¶пјљ

1. **Launch args**пј€`to_playwright_launch_options`пј‰вЂ”вЂ” е¤„зђ† proxyгЂЃlocaleгЂЃUAгЂЃtimezoneгЂЃзЄ—еЏЈе¤§е°ЏгЂЃviewportгЂЃdevice scale factorгЂ‚ењЁ Chromium еђЇеЉЁж—¶и®ѕзЅ®гЂ‚

2. **JS init script**пј€`build_init_script`пј‰вЂ”вЂ” ењЁжЇЏдёЄж–°ж–‡жЎЈдёЉ patch `Navigator.prototype`гЂЃ`HTMLCanvasElement.prototype`гЂЃ`AudioContext.prototype`гЂЃ`RTCPeerConnection.prototype` з­‰гЂ‚Canvas/audio noise дЅїз”Ё Mulberry32 з®—жі•пјЊз”± fingerprint зљ„ `audio_noise_seed` е’Њ `canvas_noise_seed` ж’­з§ЌпјЊдїќиЇЃеЏЇе¤ЌзЋ°гЂ‚

### е±Ђй™ђжЂ§

- WebGL ењЁ Chromium дёЉеЇ№жњЄжЋ©з Ѓе­—ж®µжЇеЏЄиЇ»зљ„ вЂ”вЂ” ж€‘д»¬ patch `getParameter` е’Њ `getExtension`пјЊдЅ†е¦‚жћњйЎµйќўд»Ґе…¶д»–ж–№ејЏдЅїз”Ё `WEBGL_debug_renderer_info`пјЊpatch еЏЇд»Ґиў«з»•иї‡гЂ‚
- Canvas noise е№…еє¦иѕѓиЅ»пј€жЇЏйЂљйЃ“ В±2пј‰вЂ”вЂ” ејє noise дјљз ґеќЏжџђдє›з«™з‚№зљ„и§†и§‰жёІжџ“гЂ‚е¦‚жњ‰йњЂи¦ЃеЏЇжЊ‰ profile еўћеЉ  noiseгЂ‚
- е­—дЅ“йЂљиї‡ `document.fonts.check` ејєе€¶ж‰§иЎЊпј€йЂљиї‡е°єеЇёжµ‹й‡Џзљ„е­—дЅ“жћљдёѕе°†иї”е›ћз™ЅеђЌеЌ•пј‰гЂ‚з›®е‰Ќе°љжњЄе®Ње…Ёи¦†з›–з»•иї‡ `document.fonts` зљ„ж·±е±‚ canvas е°єеЇёе­—дЅ“жЋўжµ‹гЂ‚
- WebGPU дјЄиЈ…д»… patch дє† `requestAdapterInfo()` / `adapter.info`пјЊе№¶дёЌй‡Ќе†™еє•е±‚зљ„ `GPUAdapter` й™ђе€¶/з‰№жЂ§гЂ‚
- ж— е¤ґжЁЎејЏйІе…іиЃ”пј€headless stealthпј‰е±ћдєЋеџєзЎЂжЂ§и§„йЃїпјље·І patch `window.chrome` д»ҐеЏЉ permissions APIпјЊдЅ†ж·±е±‚зљ„жёІжџ“ж—¶еєЏпј€paint timingпј‰д»ҐеЏЉз‰№е®љдєЋ GPU зЎ¬д»¶зљ„ж— е¤ґз‰№еѕЃеЏЇиѓЅдјљиў«ж ‡и®°гЂ‚
- WebRTC ж”ЇжЊЃдё‰з§ЌжЁЎејЏпј€`webrtc_mode`пј‰пјљ`block`пј€й»и®¤ вЂ”вЂ” е®Ње…ЁжЉ‘е€¶ ICE еЂ™йЂ‰ж”¶й›†пјЊhost дёЋ reflexive еЂ™йЂ‰йѓЅдёЌдјљжљґйњІпј‰гЂЃ`real`пј€дёЌеЃљж”№еЉЁпј‰гЂЃ`proxy`пј€е°† host еЂ™йЂ‰й‡Ќе†™дёє `webrtc_public_ip`пј‰гЂ‚

---

## 11. е®Њж•ґ profileпј€.adbпј‰еЇје…ҐжµЃзЁ‹

е®Њж•ґ profile еЇје…Ґзљ„жµЃзЁ‹е¦‚дё‹пјљ

```
1. POST /user/import  (or  cli import-cookies --full PATH)
   в†“
2. profile created (user_id assigned)
   в†“
3. .adb bundle extracted to  data/profiles/imports/<user_id>/
   в†“
4. Cookies parsed from <user_id>/Default/Cookies, written to profile.cookies
   в†“
5. profile.import_source_path = "<user_id>"   в†ђ дѕ› launcher дЅїз”Ё
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
8. Chromium reads the directories natively and treats them as if it had
   written them itself вЂ” no LevelDB parser, no Snappy codec, no version drift.
```

### дёєд»Ђд№€йЂ‰ж‹©гЂЊж‹·иґќгЂЌиЂЊдёЌжЇгЂЊи§ЈжћђгЂЌпјџ

Chrome в‰Ґ 61 е°† `localStorage` е­е‚ЁењЁ Snappy еЋ‹зј©зљ„ LevelDB дё­гЂ‚IndexedDB дЅїз”Ё V8 structured-clone еЂјгЂ‚й‡Ќж–°е®ћзЋ°и§Јз Ѓе™Ёж„Џе‘ізќЂпјљ

- дёЋз‰€жњ¬иЂ¦еђ€пј€Chrome зљ„зј–з ЃењЁеђ„з‰€жњ¬й—ґеЏ‘з”џеЏеЊ–пј‰гЂ‚
- еЇ№ Windows дёЌеЏ‹еҐЅпј€`plyvel` йњЂи¦ЃеЋџз”џ LevelDB + Snappy жћ„е»єпј‰гЂ‚
- и„†еј±пј€дёЂдёЄе­—иЉ‚й”™дЅЌпјЊж•ґдёЄ profile е°±ж— жі•еЉ иЅЅпј‰гЂ‚

еЋџж ·ж‹·иґќиї™дє›з›®еЅ•жЇдёЂз§ЌгЂЊз¬Ёж‹™дЅ†еЏЇйќ гЂЌзљ„ж–№жЎ€пјЊеЇ№ Playwright й™„её¦зљ„ж‰Ђжњ‰ Chromium з‰€жњ¬йѓЅжњ‰ж•€гЂ‚

### й‡Ќж–°еЇје…Ґ

ењЁ `.adb` й‡Ќж–°еЇје‡єд№‹еђЋпјљ

```bash
python -m src.cli reimport <user_id>
# or
curl -X POST http://127.0.0.1:8080/user/<user_id>/reimport
```

иї™дјље°† `initial_state_applied` й‡ЌзЅ®дёє `False`гЂ‚дё‹ж¬ЎеђЇеЉЁж—¶дјљж“¦й™¤зЋ°жњ‰зљ„ `Local Storage/leveldb/` е’Њ `IndexedDB/`пј€е› дёєењЁ `apply_initial_state_to_user_data` е†…йѓЁе†Ќж¬Ўеє”з”Ёж—¶и®ѕзЅ®дє† `force=True`пј‰пјЊз„¶еђЋд»Ћ bundle й‡Ќж–°ж‹·иґќгЂ‚

### Force ж ‡еї—

`apply_initial_state_to_user_data(..., force=True)` дјљи¦†з›–зЋ°жњ‰з›®еЅ•гЂ‚Launcher ењЁй¦–ж¬Ўеє”з”Ёж—¶дЅїз”Ё `force=False`пј€йЃїе…Ќж„Џе¤–и¦†з›–е€ље€љж‹·иґќзљ„зЉ¶жЂЃпј‰пјЊиЂЊ reimport жµЃзЁ‹дјљжѕејЏзї»иЅ¬иЇҐж ‡еї—гЂ‚

---

## 12. CDP multiplexer

Playwright ж‹Ґжњ‰жЇЏдёЄ profile зљ„ Chromium иї›зЁ‹пјЊдЅ†е¤–йѓЁи‡ЄеЉЁеЊ–пј€SeleniumгЂЃPuppeteerгЂЃи‡Єе®љд№‰и„љжњ¬пј‰еёЊжњ›жЇЏдёЄ profile ж‹Ґжњ‰дёЂдёЄ CDP endpointгЂ‚`CDPProxy`пј€`src/core/cdp.py`пј‰е®ћзЋ°дє†д»Ґдё‹ multiplexerпјљ

- `GET /json/version` вЂ”вЂ” иї”е›ћдёЂдёЄдјЄ version payloadпјЊжЊ‡еђ‘ `ws://127.0.0.1:5555/devtools/browser`
- `GET /json/list?user_id=<id>` вЂ”вЂ” е€—е‡єжџђдёЄ profile зљ„йЎµйќў
- `WS /devtools/page/{user_id}/{target_id}` вЂ”вЂ” е°† websocket д»Јзђ†е€°ж­ЈзЎ®зљ„ Playwright йЎµйќў

жіЁж„ЏпјљWS endpoint жЇ **жЁЎж‹џ** зљ„ вЂ”вЂ” зњџе®ћзљ„ CDP жµЃй‡Џиµ° Playwright зљ„ contextпјЊиЂЊдёЌжЇдёЂдёЄзњџж­Јзљ„ Chrome debug portгЂ‚еЇ№дєЋдёЌйњЂи¦Ѓеє•е±‚еЌЏи®®з‰№жЂ§зљ„гЂЊй™„еЉ е€°жµЏи§€е™ЁгЂЌејЏи‡ЄеЉЁеЊ–жќҐиЇґиї™е·Із»Џе¤џз”ЁгЂ‚

е¦‚жћњйњЂи¦Ѓзњџж­Јзљ„ CDPпјЊиЇ·е°†и‡ЄеЉЁеЊ–жЊ‡еђ‘ `POST /user/start` иї”е›ћзљ„ per-profile websocketпјљ

```json
{"ws_endpoint": "ws://127.0.0.1:50321/devtools/browser", "debug_port": 50321}
```

---

## 13. ж•°жЌ®з›®еЅ•еёѓе±Ђ

```
data/
в”њв”Ђв”Ђ antique.db                 в†ђ SQLite (profiles, sessions, tags, groups, backup_scheduler.py)
в””в”Ђв”Ђ profiles/
    в”њв”Ђв”Ђ <user_id>/                в†ђ иЇҐ profile зљ„ Playwright user_data_dir
    в”‚   в”њв”Ђв”Ђ Default/
    в”‚   в”‚   в”њв”Ђв”Ђ Cookies
    в”‚   в”‚   в”њв”Ђв”Ђ Local Storage/leveldb/...
    в”‚   в”‚   в”њв”Ђв”Ђ IndexedDB/...
    в”‚   в”‚   в””в”Ђв”Ђ (all Chromium user-data files)
    в”‚   в””в”Ђв”Ђ ...
    в””в”Ђв”Ђ imports/
        в””в”Ђв”Ђ <user_id>/            в†ђ и§ЈеЋ‹еђЋзљ„ .adb bundleпј€е®Њж•ґ profile еЇје…Ґпј‰
            в”њв”Ђв”Ђ Default/...
            в””в”Ђв”Ђ ...
```

еЏЇйЂљиї‡зЋЇеўѓеЏй‡Џ `ANTIQUE_DATA_DIR=/some/path` и¦†з›–гЂ‚

---

## 14. жµ‹иЇ•

```bash
python -m pytest                    # all tests
python -m pytest tests/test_cookie.py -v
python -m pytest -k adb             # only .adb-related tests
```

**300+ дёЄжµ‹иЇ•**пј€з›®е‰Ќе…± 310 дёЄпј‰пјљ

- `test_storage.py` вЂ”вЂ” SQLite engineгЂЃtables
- `test_profile.py` вЂ”вЂ” ProfileStore CRUDгЂЃе®Њж•ґ profile е­—ж®µгЂЃsession и®°еЅ•
- `test_fingerprint.py` вЂ”вЂ” Fingerprint з”џж€ђ + init script жіЁе…Ґ
- `test_proxy.py` вЂ”вЂ” ProxyConfig ж ЎйЄЊ + Playwright ж јејЏдє’иЅ¬
- `test_cookie.py` вЂ”вЂ” Cookie и§Јжћђпј€Netscape/JSON/.adbпј‰гЂЃLocalStorage/IndexedDB жЉЅеЏ–
- `test_profile_import.py` вЂ”вЂ” е®Њж•ґ profile еЇје…ҐжµЃзЁ‹
- `test_webgpu_fonts.py` вЂ”вЂ” WebGPU adapter дјЄиЈ… + font з™ЅеђЌеЌ•з”џж€ђдёЋжіЁе…Ґ
- `test_automation.py` вЂ”вЂ” Cookie Robot / flow иЇ­жі•и§ЈжћђгЂЃжћ„е»єдёЋж‰§иЎЊ
- `test_portable.py` вЂ”вЂ” дѕїжђєејЏ `.antq` еЇје‡єдёЋеЇје…ҐйЄЊиЇЃ
- `test_geo.py` вЂ”вЂ” е›Ѕе®¶/е‡єеЏЈд»Јзђ†дёЋж—¶еЊє/иЇ­иЁЂ/ењ°зђ†дЅЌзЅ®и‡ЄеЉЁеЇ№йЅђ
- `test_proxy_pool.py` вЂ”вЂ” д»Јзђ†ж± иЅ®жЌўз­–з•ҐеЏЉеЃҐеє·еє¦е®№зЃѕжµ‹иЇ•
- `test_detect.py` вЂ”вЂ” жЊ‡зє№йІе…іиЃ”и‡ЄжЈЂжњєе€¶
- `test_console.py` вЂ”вЂ” Windows з»€з«Ї UTF-8 иѕ“е‡єй‡Ќжћ„дёЋ ASCII е›ћйЂЂйЄЊиЇЃ
- `test_api_endpoints.py` вЂ”вЂ” HTTP зє§е€« API жµ‹иЇ• (TestClient)пјљж‰©е±•з»„д»¶е›ћеЅ’гЂЃењ°зђ†еЊ№й…ЌгЂЃд»Јзђ†ж± гЂЃдѕїжђєејЏеЇје…ҐеЇје‡єгЂЃжЈЂжµ‹иЇ„е€†
- `test_auth.py` вЂ”вЂ” API й‰ґжќѓ + жќҐжєђдїќжЉ¤ (DNS-rebindingгЂЃBearer д»¤з‰ЊгЂЃйљ§йЃ“е…Ѓи®ёе€—иЎЁ)
- `test_engines.py` вЂ”вЂ” жµЏи§€е™Ёеј•ж“ЋжіЁе†ЊиЎЁпјљи§„ж јгЂЃиѓЅеЉ›гЂЃе€«еђЌи§ЈжћђгЂЃдје…€е†іи®®гЂЃеђЇеЉЁе™ЁеЇ№жЋҐ
- `test_sync.py` вЂ”вЂ” и·Ё profile еђЊж­Ґи‡ЄеЉЁеЊ–жµЃзЁ‹жµ‹иЇ• (е№¶еЏ‘жЋ§е€¶гЂЃеј‚еёёйљ”з¦»)
- `test_status_liveview.py` вЂ”вЂ” иґ¦еЏ·зЉ¶жЂЃгЂЃLive View ж€Єе›ѕгЂЃCDP иїћжЋҐжЈЂжµ‹дёЋж€Єе›ѕеј‚еёёи·Їеѕ„жµ‹иЇ•
- `test_import_launch_and_randomize.py` вЂ”вЂ” еЇје…ҐеђЋеђЇеЉЁе›ћеЅ’гЂЃжњ¬ењ°её¦еЇ† SOCKS5 д»Јзђ†жЎҐжЋҐгЂЃж‰№й‡ЏжЊ‡зє№ж™єиѓЅйљЏжњєеЊ– (0.4.0 ж–°еўћ)
- `test_ui_release_040.py` вЂ”вЂ” еЇ№еЏ‘еёѓз‰€ 0.4.0 UI ж ёеїѓе…ѓзґ зљ„йќ™жЂЃдёЋиЎЊдёєй›†ж€ђжµ‹иЇ• (0.4.0 ж–°еўћ)
- `test_sort_clone_features.py` вЂ”вЂ” profile жЋ’еєЏйЂ‰ж‹©гЂЃе¤Ќе€¶е…‹йљ†еЏЉж‰№й‡Џиґ¦еЏ·зЉ¶жЂЃж›ґж–°жµ‹иЇ•
- `test_operations_release.py` вЂ”вЂ” жЁЎжќїж‰№й‡Џе€›е»єгЂЃAES-GCM еЉ еЇ†еї«з…§гЂЃж“ЌдЅње®Ўи®Ўж—Ґеї—пј€ж”ЇжЊЃиї‡ж»¤дёЋ JSON еЇје‡єпј‰гЂЃжњ¬ењ°/иїњзЁ‹д»Јзђ†жєђжµ‹иЇ•пј€еЊ…еђ« HTTP-JSONпј‰гЂЃе€†з»„ CRUDгЂЃжњ¬ењ°еЉ еЇ†е¤‡д»Ѕи®Ўе€’з®Ўзђ†гЂЃж‰©е±•з›®еЅ•еЏЉ MCP зЉ¶жЂЃз›‘жµ‹жµ‹иЇ• (0.9.0 ж–°еўћ)

д»…иїђиЎЊжњЂж–°зљ„жµ‹иЇ•еҐ—д»¶пјљ

```bash
python -m pytest tests/test_operations_release.py tests/test_sort_clone_features.py tests/test_import_launch_and_randomize.py tests/test_ui_release_040.py -v
```

---

## 15. 0.6.0 з‰€жњ¬еЉџиѓЅеЏ‘еёѓ

ж–°еўћдє†дёЋ AdsPower зљ„еЉџиѓЅеЇ№йЅђпјљAdsPower е¤‡д»Ѕ data ж— еЇје…Ґйў„и§€ (dry-run)гЂЃй…ЌзЅ®жЁЎжќїдёЋж‰№й‡Џе€›е»єгЂЃAES-GCM еЉ еЇ†еї«з…§е¤‡д»ЅеЇје‡є/еЇје…ҐгЂЃж“ЌдЅњеЋ†еЏІе®Ўи®Ўж—Ґеї—гЂЃжњ¬ењ°ж–‡д»¶/JSONд»Јзђ†жєђиЅ®жЌўжЏђеЏ–гЂЃи‡Єе®љд№‰е€†з»„зљ„ CRUD еўће€ ж”№жџҐгЂЃзі»з»џиµ„жєђеЌ з”Ёе’Њ MCP з›‘жЋ§з«Їз‚№пјЊд»ҐеЏЉзЅ‘йЎµз«Ї Dashboard зљ„ Tools е·Ґе…·з®±жЋ§е€¶йќўжќїгЂ‚ж–°жµ‹иЇ•еҐ—д»¶дЅЌдєЋ `tests/test_operations_release.py`гЂ‚

## 16. 0.7.0 з‰€жњ¬еЉџиѓЅеЏ‘еёѓ

ж–°еўћдє†ж‰©е±•зљ„ AdsPower еЉџиѓЅеЇ№йЅђпјљж”ЇжЊЃе®Њж•ґзљ„зі»з»џж“ЌдЅњеЋ†еЏІе®Ўи®Ўпј€ењЁе€›е»єгЂЃдї®ж”№гЂЃеђЇеЉЁгЂЃеЃњж­ўгЂЃе€ й™¤гЂЃеЇје…Ґе¤‡д»ЅеЏЉж‰№й‡Џж›ґж–°зЉ¶жЂЃж—¶и‡ЄеЉЁи®°еЅ•иЇ¦з»† audit ж—Ґеї—пј‰гЂЃжњ¬ењ°еЉ еЇ†е¤‡д»Ѕи®Ўе€’з®Ўзђ†е™Ёпј€ж”ЇжЊЃ AES-GCM еї«з…§е¤‡д»ЅеЏЉе®љжњџд»»еЉЎжіЁе†ЊпјЊж— йњЂй©»з•™е®€жЉ¤иї›зЁ‹пјЊеЏЇйЂљиї‡ Windows д»»еЉЎи®Ўе€’зЁ‹еєЏ or cron е®љжњџи°ѓз”Ёпј‰гЂЃHTTP JSON иїњзЁ‹д»Јзђ†жєђжЏђеЏ–е™Ёпј€ж”ЇжЊЃд»ЋеЉЁжЂЃ API иЋ·еЏ–д»Јзђ†ж± пј‰пјЊд»ҐеЏЉж›ґзІѕз»†зљ„ CPU дёЋ RSS е†…е­жЂ§иѓЅжЊ‡ж ‡з»џи®Ўз»џи®ЎпјЊењЁ Windows дё‹жЏђдѕ›е®‰е…Ёзљ„е›ћйЂЂжњєе€¶гЂ‚

## 17. 0.8.0 з‰€жњ¬еЉџиѓЅеЏ‘еёѓ

ж–°еўћдє†еµЊеҐ—ж–‡д»¶е¤№/еµЊеҐ—е€†з»„пј€ењЁ `groups` иЎЁдё­йЂљиї‡ `parent_id` е®ћзЋ°ж–‡д»¶е¤№е±‚зє§з®Ўзђ†еЉџиѓЅпј‰гЂЃзЅ‘йЎµз«Їе¤§е·Ґе…·з®±йќўжќїпј€Tools Workspaceпј‰зљ„е®Њж•ґй›†ж€ђпј€еЏЇз›ґжЋҐењЁ UI дє¤дє’з•ЊйќўжµЏи§€ж“ЌдЅње®Ўи®ЎгЂЃзі»з»џз‰©зђ†иµ„жєђгЂЃеї«з…§е¤‡д»Ѕи®Ўе€’д»ҐеЏЉ AdsPower е¤‡д»Ѕе№Іи·‘йў„и§€пј‰пјЊе№¶жЏђдѕ›дє†ењЁ `docs/OWNER-FULL-TEST-CHECKLIST.md` дё­зљ„зі»з»џе…ЁйќўеЉџиѓЅйЄЊж”¶жµ‹иЇ•ж–№жЎ€пј€A и‡і H з« иЉ‚пј‰гЂ‚

## 18. 0.9.0 з‰€жњ¬еЉџиѓЅеЏ‘еёѓ

ж–°еўћдє†д»Ґдё‹еЉџиѓЅпјљж”ЇжЊЃжЊ‰ Profile е’Њж“ЌдЅњз±»ећ‹еЇ№жґ»еЉЁж—Ґеї—пј€Activity Logпј‰иї›иЎЊиї‡ж»¤пј›ж”ЇжЊЃйЂљиї‡ API е’Њ UI е°†жґ»еЉЁж—Ґеї—еЇје‡єдёє JSON ж јејЏпј›ењЁ Tools дё­ж–°еўћдє†ж‰©е±•зЁ‹еєЏз›®еЅ•пј€Extension Catalogпј‰еЉџиѓЅпјЊж”ЇжЊЃжџҐзњ‹е·Іе®‰иЈ…зљ„ж‰©е±•зЁ‹еєЏе№¶иѓЅйЂљиї‡и§ЈеЋ‹з›®еЅ•ж€– Chrome Web Store ID иї›иЎЊе®‰иЈ…пј›й›†ж€ђдє† MCP жњЌеЉЎзљ„зЉ¶жЂЃжѕз¤єеЏЉ stdio зЉ¶жЂЃпј›е®Ње–„дє†ењЁ `docs/OWNER-FULL-TEST-CHECKLIST.md` е’Њ `docs/RELEASE-0.9.0-REPORT.md` дё­зљ„и‡ЄеЉЁеЊ–дёЋж“ЌдЅњйЄЊж”¶з”Ёдѕ‹гЂ‚

## 19. 1.0.0 з‰€жњ¬еЉџиѓЅеЏ‘еёѓ

ж–°еўћдє†д»Ґдё‹еЉџиѓЅпјље®Њж•ґзљ„ `GET /group/tree` API д»Ґе±‚зє§ж ‘еЅўејЏиЋ·еЏ–еµЊеҐ—е€†з»„з»“жћ„пј›е®‰е…Ёе€ й™¤з€¶з»„йЂ»иѕ‘пј€е€ й™¤з€¶з»„ж—¶и‡ЄеЉЁе°†е­ђз»„жЏђеЌ‡и‡ідёЉдёЂе±‚пј‰д»ҐеЏЉйІж­ў default е€†з»„иў«е€ й™¤зљ„дїќжЉ¤жњєе€¶пј›ењЁ Tools йќўжќїж”ЇжЊЃз›ґжЋҐж›ґж–°е’Ње€ й™¤ж–‡д»¶е¤№пј€е€†з»„пј‰пј›ењЁ Extension Catalog дё­ж–°еўћеЌёиЅЅжЊ‰й€•пј›ж‰©е±•дє† `docs/OWNER-FULL-TEST-CHECKLIST.md`пј€еЊ…еђ«з»„е±‚зє§е’Њж‰©е±•з›®еЅ•йЄЊиЇЃж­ҐйЄ¤пј‰е№¶ж›ґж–°дє† `docs/RELEASE-1.0.0-REPORT.md` е’ЊеЉџиѓЅеЇ№з…§зџ©йµгЂ‚

## 20. е·ІзџҐй™ђе€¶дёЋ roadmap

### е·Іе®Њж€ђпј€жњ¬ж¬Ўжћ„е»єпј‰

- [x] е¤љ profile йљ”з¦» of Chromium context
- [x] Fingerprint з”џж€ђ + JS жіЁе…Ґ
- [x] HTTP/HTTPS/SOCKS5 proxy
- [x] Cookie еЇје…Ґпј€NetscapeгЂЃJSONгЂЃ.adb bundleпј‰
- [x] Cookie еЇје‡єпј€NetscapeгЂЃJSONпј‰
- [x] е®Њж•ґ .adb profile еЇје…Ґпј€cookies + LocalStorage + IndexedDBпј‰
- [x] й‡Ќж–°еЇје…ҐжµЃзЁ‹пј€`cli reimport`гЂЃ`POST /user/{id}/reimport`пј‰
- [x] AdsPower е…је®№зљ„ REST API
- [x] CDP multiplexerпј€жЁЎж‹џпј‰
- [x] еЌ•йЎµ dashboard
- [x] **ж‰©е±•з®Ўзђ†е™Ё**пј€ж”ЇжЊЃд»Ћи§ЈеЋ‹з›®еЅ•гЂЃ.crxгЂЃChrome Web Store е®‰иЈ…пј›ж”ЇжЊЃ profile е€†й…Ќпј‰
- [x] **MCP жњЌеЉЎз«Ї**пј€еџєдєЋ stdio зљ„ JSON-RPC 2.0пјЊжЏђдѕ› 12 дёЄе·Ґе…·пјљlist/open/close/navigate/screenshot/execute_script/cookies/proxy_check з­‰пј‰
- [x] **е¤љжµЏи§€е™Ёеј•ж“Ћж”ЇжЊЃ**пј€ChromiumгЂЃFirefoxгЂЃCamoufox/ShardXпј›ж”ЇжЊЃжЊ‰ profile ж€–зЋЇеўѓеЏй‡ЏжЊ‡е®љпј‰
- [x] **Client Hints**пј€йЂљиї‡и‡Єе®љд№‰жµЏи§€е™ЁеђЇеЉЁеЏ‚ж•°дјЄиЈ… Sec-CH-UA иЇ·ж±‚е¤ґпјЊеџєдєЋ fingerprint и‡ЄеЉЁз”џж€ђпј‰
- [x] **Profile зє§ж‰©е±•еЉ иЅЅ**пј€еђЇеЉЁж—¶еЉ иЅЅ `--load-extension` дёЋ `--disable-extensions-except`пј‰
- [x] **WebGPU fingerprint дјЄиЈ…**пј€дёЋ WebGL GPU дёЂи‡ґпј‰
- [x] **е­—дЅ“ fingerprint дјЄиЈ…**пј€жЇЏдёЄ OS з‹¬з«‹зљ„е­—дЅ“з™ЅеђЌеЌ•пј‰
- [x] **Cookie Robot / ж— д»Јз Ѓи‡ЄеЉЁеЊ–жµЃзЁ‹**пј€ж”ЇжЊЃ `warm` йў„зѓ­гЂЃ`run-flow` ж‰§иЎЊпјЊжЏђдѕ› JSON иЇ­жі•ж­ҐйЄ¤пј‰
- [x] **дѕїжђєејЏ profile еЇје‡є/еЇје…Ґ**пј€дЅїз”Ё `.antq` еЋ‹зј©еЊ…иїЃз§» fingerprint + proxy + cookies + tagsпј‰
- [x] **ењ°зђ†дЅЌзЅ®еЊ№й…Ќ (Geo matching)**пј€и‡ЄеЉЁж №жЌ®е›Ѕе®¶/е‡єеЏЈд»Јзђ† IP еЇ№йЅђж—¶еЊєгЂЃиЇ­иЁЂе’Њз»Џзє¬еє¦пјЊ`src/core/geo.py`пј‰
- [x] **ењ°зђ†е®љдЅЌдјЄиЈ…**пј€`navigator.geolocation` зљ„еќђж ‡дёЋзІѕеє¦е’Њењ°зђ†й…ЌзЅ®дїќжЊЃдёЂи‡ґпј‰
- [x] **д»Јзђ†иЅ®жЌўдёЋеЃҐеє·е®№зЃѕ**пј€жЏђдѕ› sticky/round_robin/random з­–з•Ґзљ„д»Јзђ†ж± пјЊ`src/core/proxy_pool.py`пј‰
- [x] **Headless йљђиє« (Headless stealth)**пј€ж”ЇжЊЃ `window.chrome`/`chrome.runtime` жЋҐеЏЈд»їзњџдёЋ `permissions.query` жЋҐеЏЈдёЂи‡ґжЂ§пј‰
- [x] **йІе…іиЃ”жЈЂжµ‹иЇ„дј°**пј€`detect-test` е·Ґе…·пјЊжЏђдѕ› 0-100 з»јеђ€иЇ„е€†дёЋ A-F иЇ„зє§жЉҐе‘ЉпјЊ`src/core/detect.py`пј‰
- [x] **еЏЇж›ґжЌўжµЏи§€е™Ёеј•ж“Ћ** (Chromium/Chrome/Edge/Firefox/Camoufox/WebKit жіЁе†ЊиЎЁ, `src/core/engines.py`, `/engine/list`, `create --engine`)
- [x] **Camoufox ж·±еє¦йљђиє«еј•ж“Ћ** (Gecko зє§жЊ‡зє№дјЄиЈ…пј›и‹ҐжњЄе®‰иЈ…пјЊе€™е›ћйЂЂи‡іжЌ†з»‘ Firefox)
- [x] **дёЂй”® AdsPower е¤‡д»ЅеЇје…Ґ** (ж”ЇжЊЃеЇје…Ґж•ґж–‡д»¶е¤№ж€–еЌ• profile; CLI `import-backup` + `/user/import/backup` + зЅ‘йЎµз«Ї)
- [x] **иґ¦еЏ·зЉ¶жЂЃж ‡иЇ†** (`new`/`warming`/`active`/`limited`/`banned`/`retired`) еЏЉиї‡ж»¤жњєе€¶
- [x] **Live View** (ењЁ Dashboard з›ґи§‚йў„и§€ж­ЈењЁиїђиЎЊзљ„ profile е®ћж—¶ж€Єе›ѕ)
- [x] **зњџе®ћзљ„ CDP жњЌеЉЎ** (дёєжЇЏдёЄ Chromium profile жЏђдѕ›з‹¬еЌ зљ„ CDP и°ѓиЇ•з«ЇеЏЈ)
- [x] **и·Ё profile еђЊж­ҐжЋ§е€¶** (е№¶еЏ‘еђЊж­Ґж‰§иЎЊз›ёеђЊж­ҐйЄ¤, `src/core/sync.py`)
- [x] **Docker е®№е™ЁйѓЁзЅІж”ЇжЊЃ**
- [x] **е¤ље­—ж®µжЋ’еєЏжњєе€¶** (DashboardгЂЃREST API дёЋ CLI ж”ЇжЊЃ 13 з§Ќе±ћжЂ§жЋ’еєЏеЏЉеЌ‡й™ЌеєЏ)
- [x] **Profile е…‹йљ†е¤Ќе€¶** (ж”ЇжЊЃдёЂй”®е®Њж•ґе¤Ќе€¶жЊ‡зє№гЂЃд»Јзђ†гЂЃCookie дёЋж ‡з­ѕ)
- [x] **ж‰№й‡ЏзЉ¶жЂЃдї®ж”№** (ж”ЇжЊЃењЁ Dashboard з•ЊйќўгЂЃAPI е’Њ CLI ж‰№й‡Џж›ґж–°иґ¦еЏ·зЉ¶жЂЃ)
- [x] **ж™єиѓЅж‰№й‡ЏйљЏжњєеЊ–жЊ‡зє№** (еЏЇй”Ѓе®љйѓЁе€†е­—ж®µж€–и·Ё profile е…±дє«з›ёеђЊзљ„жЊ‡зє№з‰№еѕЃе­—ж®µ)
- [x] **её¦еЇ† SOCKS5 д»Јзђ†жЎҐ** (е€©з”Ё loopback з®ЎйЃ“йЂЏжЋд»Јзђ†и§Је†іеЋџз”џ Chromium еЇ№ socks иґ¦еЏ·еЇ†з Ѓзљ„ж ЎйЄЊзјєй™·)
- [x] **AdsPower е¤‡д»Ѕйў„и§€ (dry-run)** (ж”ЇжЊЃењЁзЅ‘йЎµ/API/CLIйў„и§€AdsPowerе¤‡д»Ѕж•°жЌ®иЂЊдёЌе®ћй™…е†™е…Ґеє“)
- [x] **жЁЎжќїж‰№й‡Џе€›е»є** (ж”ЇжЊЃдЅїз”Ё JSON жЁЎжќїиї›иЎЊ profile ж‰№й‡Џе€›е»єдёЋжЊ‡зє№йљЏжњєз”џж€ђ)
- [x] **AES-GCM еЉ еЇ†еї«з…§** (ж”ЇжЊЃеЇје‡єе’ЊеЇје…Ґз»Џиї‡еЇ†з ЃдїќжЉ¤зљ„ profile еЋ‹зј©е¤‡д»Ѕеї«з…§)
- [x] **ж“ЌдЅњеЋ†еЏІе®Ўи®Ў** (еђЋеЏ°и‡ЄеЉЁи®°еЅ•ж“ЌдЅњж—Ґеї—пјЊж”ЇжЊЃ API еЏЉ CLI жџҐиЇўеЋ†еЏІи®°еЅ•пјЊж”ЇжЊЃж ёеїѓж“ЌдЅњзљ„ audit дє‹д»¶)
- [x] **жњ¬ењ°д»Јзђ†жєђжЏђеЏ–** (ж”ЇжЊЃж–‡д»¶/JSON/HTTP-JSONеЅўејЏзљ„д»Јзђ†жєђиЅ®жЌўжЏђеЏ–)
- [x] **CRUDе€†з»„з®Ўзђ†** (ж”ЇжЊЃењЁеђЋеЏ°дёЋ API иї›иЎЊи‡Єе®љд№‰е€†з»„зљ„е€›е»єгЂЃдї®ж”№е’Ње€ й™¤)
- [x] **иµ„жєђзЉ¶жЂЃдёЋ MCP з›‘жЋ§** (ж”ЇжЊЃжџҐиЇў PIDгЂЃжґ»еЉЁжµЏи§€е™Ёиї›зЁ‹ж•°д»ҐеЏЉ MCP tools ж е°„пјЊж”ЇжЊЃ CPU/RSS иµ„жєђж¶€иЂ—иЇ¦з»†жЊ‡ж ‡)
- [x] **жњ¬ењ°еЉ еЇ†е¤‡д»Ѕи®Ўе€’з®Ўзђ†е™Ё** (API `/backup/schedules`пјЊж”ЇжЊЃ AES-GCM е¤‡д»Ѕи‡ЄеЉЁи·‘д»»еЉЎпјЊж— йњЂе®€жЉ¤иї›зЁ‹)
- [x] **зЅ‘йЎµз«Їе·Ґе…·з®±йќўжќї (Tools Workspace)** (ж“ЌдЅње®Ўи®ЎгЂЃиї‡ж»¤дёЋеЇје‡єгЂЃзі»з»џиµ„жєђгЂЃе¤‡д»Ѕи®Ўе€’гЂЃж‰©е±•з›®еЅ•еЏЉ MCP зЉ¶жЂЃе·Іе…ЁйѓЁй›†ж€ђ)
- [x] **ж‰©е±•з›®еЅ•** (Extension CatalogпјЊж”ЇжЊЃжњ¬ењ° unpacked з›®еЅ•гЂЃWeb Store ID е®‰иЈ…дёЋеЌёиЅЅпјЊеЏЉ profile е€†й…Ќ)
- [x] **е€†з»„е±‚зє§з»“жћ„** (`GET /group/tree`пјЊе®‰е…Ёе€ й™¤з€¶з»„пјЊдїќжЉ¤ default е€†з»„пјЊUI update/delete ж–‡д»¶е¤№ вЂ” 1.0.0)
- [x] 313+ дёЄ pytest жµ‹иЇ•йЂљиї‡

### е·ІзџҐй™ђе€¶

- **жЁЎж‹џзљ„ CDP multiplexerгЂ‚** `/json/list` + `/devtools/page/...` з«Їз‚№е№¶жІЎжњ‰жљґйњІзњџж­Јзљ„ Chrome debug port дѕ›е¤–йѓЁи‡ЄеЉЁеЊ–дЅїз”Ё вЂ”вЂ” иЇ·ж”№з”Ё `POST /user/start` иї”е›ћзљ„ per-profile websocketгЂ‚
- **API й‰ґжќѓдёєеЏЇйЂ‰жњєе€¶гЂ‚** и®ѕзЅ® `ANTIQUE_API_TOKEN` зЋЇеўѓеЏй‡ЏеђЋж–№и¦Ѓж±‚жЏђдѕ› Bearer д»¤з‰Њпј›е¦‚жњЄи®ѕзЅ®пјЊе€™й»и®¤еЇ№ `127.0.0.1` ејЂж”ѕпј€дЅ†д»ЌеЏ—и·Ёеџџ Cross-Origin з­–з•ҐдїќжЉ¤пј‰гЂ‚еЌ•иї›зЁ‹пјЊжљ‚дёЌж”ЇжЊЃе¤љз”Ёж€·и§’и‰ІгЂ‚
- **жІЎжњ‰ proxy provider з›ґиїћй›†ж€ђгЂ‚** д»Јзђ†йњЂи¦Ѓз”±ж‚Ёд»Ґд»Јзђ†ж± ж–№ејЏжЏђдѕ›пј›ж€‘д»¬ж”ЇжЊЃеЇ№е·Іжњ‰зљ„д»Јзђ†ж± иї›иЎЊи‡ЄеЉЁиЅ®жЌўдёЋж•…йљње€‡жЌўгЂ‚
- **Headless йљђж·±дёєе°ЅеЉ›иЂЊдёєпј€Best-effortпј‰гЂ‚** е·ІдјЄиЈ… permissions е’Њ `window.chrome` жЊ‡ж ‡пјЊдЅ†жћЃе…¶еє•е±‚зљ„жёІжџ“ж—¶еєЏпј€paint timingпј‰д»ҐеЏЉз‰№е®љзљ„ GPU зЎ¬д»¶жЊ‡зє№з›®е‰Ќе°љжњЄе®Ње…Ёж¶µз›–гЂ‚
- **WebRTC жњ‰дё‰з§ЌжЁЎејЏ**пј€`webrtc_mode`пј‰пјљ`block`пј€й»и®¤ вЂ”вЂ” жЉ‘е€¶еЂ™йЂ‰ж”¶й›†пјЊжњ¬ењ° IP дёЌдјљжі„жјЏпј‰гЂЃ`real`пј€дёЌеЃљж”№еЉЁпј‰гЂЃ`proxy`пј€е°† host еЂ™йЂ‰й‡Ќе†™дёє `webrtc_public_ip`пј‰гЂ‚`proxy` йњЂи¦ЃењЁй…ЌзЅ®ж–‡д»¶дё­и®ѕзЅ®е…¬зЅ‘ IPпј›жњЄи®ѕзЅ®ж—¶дјљз›ґжЋҐж‹’з»ќпјЊиЂЊдёЌжЇйќ™й»й™Ќзє§гЂ‚
- **Camoufox йњЂи¦Ѓйўќе¤–е®‰иЈ…гЂ‚** `pip install camoufox && python -m camoufox fetch`гЂ‚и‹ҐжњЄе®‰иЈ…пјЊ`camoufox` еј•ж“Ћдјљи‡ЄеЉЁе›ћйЂЂи‡іжЌ†з»‘зљ„ Firefoxпј€ж ‡е‡†йІе…іиЃ”иЂЊйќћж·±еє¦пј‰гЂ‚
- **Chrome/Edge еј•ж“ЋйњЂи¦Ѓжњ¬ењ°е®‰иЈ…дє†еЇ№еє”зљ„зњџе®ћжµЏи§€е™ЁгЂ‚** еђ¦е€™е»єи®®дЅїз”Ёй»и®¤зљ„ `chromium`гЂ‚
- **Firefox/Camoufox/WebKit еј•ж“ЋдёЌж”ЇжЊЃ per-profile CDP д»ҐеЏЉеЉ иЅЅ .crx ж‰©е±•гЂ‚** иї™дє›иѓЅеЉ›д»…й™ђ ChromiumгЂ‚

### Roadmap

- [x] **жЇЏдёЄ profile зљ„зњџе®ћ CDP** вЂ” дёєжЇЏдёЄ profile е€†й…ЌдёЂдёЄе”ЇдёЂзљ„ `--remote-debugging-port`гЂ‚
- [x] **WebRTC д»Јзђ†е¤–зЅ‘ IP й‡Ќе†™** вЂ” `webrtc_mode: proxy` е°† host еЂ™йЂ‰й‡Ќе†™дёєй…ЌзЅ®ж–‡д»¶зљ„ `webrtc_public_ip`гЂ‚
- [x] **MCP жњЌеЉЎзљ„ UI й›†ж€ђ** вЂ” ж”ЇжЊЃд»Ћ dashboard Tools йќўжќїжџҐзњ‹ stdio иїђиЎЊзЉ¶жЂЃ (0.9.0)гЂ‚
- [x] **ж‰©е±• Web Store жµЏи§€е™Ё** вЂ” ж‰©е±•з›®еЅ•еЉџиѓЅпј€ж”ЇжЊЃ unpacked з›®еЅ•дёЋ Web Store IDпј‰е·ІењЁ Tools дё­й›†ж€ђ (0.9.0)гЂ‚
- [x] **е€†з»„е±‚зє§ `/group/tree`** вЂ” е±‚зє§ж ‘еЅўе€†з»„гЂЃе®‰е…Ёе€ й™¤гЂЃUI update/delete ж–‡д»¶е¤№ (1.0.0)гЂ‚
- [ ] **FingerprintJS йЄЊиЇЃй›†ж€ђ** вЂ” еј•е…Ґ fingerprintjs/fingerprintjs жЈЂжµ‹еҐ—д»¶д»Ґиї›иЎЊйІе…іиЃ”ж•€жћњжЈЂйЄЊгЂ‚

---

## 20. зЋЇеўѓеЏй‡Џ

| еЏй‡Џ | й»и®¤еЂј | з”ЁйЂ” |
|---|---|---|
| `ANTIQUE_DATA_DIR` | `./data` | `antique.db` + profile user data dir зљ„ж №з›®еЅ• |
| `ANTIQUE_DB` | `<data_dir>/antique.db` | SQLite и·Їеѕ„и¦†з›– |
| `ANTIQUE_BROWSER_CHANNEL` | пј€жњЄи®ѕзЅ®пјЊдЅїз”Ёж‰“еЊ… of Chromiumпј‰ | Playwright browser channelпјљ`chrome`гЂЃ`msedge`гЂЃ`chromium-beta` |
| `ANTIQUE_API_TOKEN` | пј€жњЄи®ѕзЅ®пјЊе…¬ејЂпј‰ | е¦‚жћњи®ѕзЅ®пјЊж‰Ђжњ‰ REST API е°†ж ЎйЄЊ `Authorization: Bearer <token>` иЇ·ж±‚е¤ґ |
| `ANTIQUE_ALLOWED_ORIGINS` | пј€жњЄи®ѕзЅ®пј‰ | е…Ѓи®ёиї›иЎЊиїњзЁ‹/йљ§йЃ“и®їй—®зљ„йўќе¤–зљ„дїЎд»» Origin е­—з¬¦дёІе­ђдёІзљ„йЂ—еЏ·е€†йљ”е€—иЎЁпј€е¦‚ `ngrok-free.app`пј‰гЂ‚Localhost е§‹з»€еЏ—дїЎд»»гЂ‚е¦‚жћњйЂљиї‡е¤–йѓЁйљ§йЃ“пј€е¦‚ ngrokпј‰ж‰“ејЂ dashboard еї…йЎ»й…ЌзЅ®ж­¤йЎ№пјЊеђ¦е€™ Origin-guard е°†иї”е›ћ 403 й”™иЇЇгЂ‚ |
| `ANTIDETECT_ENGINE` | `chromium` | й»и®¤жµЏи§€е™Ёеј•ж“Ћпјљ`chromium`гЂЃ`firefox`гЂЃ`camoufox` |
| `PYTHONIOENCODING` | пј€и‡ЄеЉЁ UTF-8пј‰ | CLI е†…йѓЁдјљи‡ЄеЉЁжЋҐз®Ўзј–з Ѓе¤„зђ†е№¶ејєе€¶иї›иЎЊ UTF-8 ж‰“еЌ°иѕ“е‡єпјЊй™¤йќћиЇҐеЉџиѓЅиў«еЃњз”Ёеђ¦е€™ж— йњЂи®ѕзЅ® |
| `HOST`пј€д»… CLIпј‰ | `127.0.0.1` | `serve` зљ„з»‘е®љењ°еќЂ |
| `UI_PORT`пј€д»… CLIпј‰ | `8080` | `serve` зљ„з«ЇеЏЈ |

---

## 21. License

MIT вЂ”вЂ” еЏ‚и§Ѓ `LICENSE`гЂ‚