# API Versioning Design Document

**Status**: Accepted
**Date**: 2026-09-02
**Version**: 1.0
**Author**: P5 SDK Foundation

---

## 1. Overview

This document describes the API versioning strategy for the **antique** anti-detect browser platform. The goal is to provide a stable, predictable contract for SDK consumers and automation integrations while allowing the underlying REST API to evolve.

### Current State

- **API version**: Unversioned (root-level paths: `/user/create`, `/health`, etc.)
- **Server version**: 1.0.1
- **Compatibility**: AdsPower-compatible local API on port 50325
- **SDK**: New Python SDK (`antique_sdk`) and TypeScript SDK added in P5

### Problem Statement

The current API has no version prefix. Breaking changes to request/response shapes, endpoint paths, or authentication semantics would silently break every consumer. We need:

1. A versioned API surface (`/api/v1/...`) that SDKs can target
2. Backward compatibility with the existing AdsPower-compatible root endpoints
3. A deprecation/migration path for existing scripts
4. Contract guarantees enforced by automated tests

---

## 2. Versioning Scheme

### Semantic Versioning for API

We adopt **semantic versioning** for the API contract:

| Change Type | Version Bump | Example |
|---|---|---|
| **Breaking** | Major (v1 → v2) | Remove endpoint, change response shape |
| **Additive** | Minor (v1.0 → v1.1) | New endpoint, new optional field |
| **Fix** | Patch (v1.0.0 → v1.0.1) | Bug fix, no contract change |

### Version Encoding

- **Path-based**: `/api/v1/user/create` — the primary versioning mechanism
- **Header-based** (advisory): `X-API-Version: 1` on all v1 responses
- **Discovery**: `GET /api/v1/version` returns `{"api_version": "1.0.0", "status": "stable"}`

### Version Lifecycle

| Stage | Meaning | Duration |
|---|---|---|
| `stable` | Production-ready, backward-compatible guarantees | Indefinite |
| `deprecated` | Still functional, will be removed in next major | 6 months |
| `sunset` | Scheduled for removal, returns `Sunset` header | 3 months |
| `removed` | Returns 410 Gone | — |

---

## 3. Dual-Endpoint Strategy

### Root Endpoints (Legacy / AdsPower Compatible)

The existing root-level endpoints (`/user/create`, `/health`, etc.) remain unchanged for backward compatibility with AdsPower scripts. These are the **legacy compatibility surface**:

- **No version prefix** — same as AdsPower API
- **No version header** — no version guarantee
- **Not recommended for new SDK consumers**
- **Will be frozen** — no new endpoints added here, only bug fixes

### Versioned Endpoints (Stable Contract)

New endpoints under `/api/v1/` provide the **stable contract surface**:

- **Version prefix** — `/api/v1/user/create`
- **Version header** — `X-API-Version: 1` on all responses
- **Contract-guaranteed** — shapes validated by OpenAPI snapshot tests
- **Recommended for all new SDK consumers**

### Endpoint Mapping

| Legacy (Root) | Versioned (v1) |
|---|---|
| `GET /health` | `GET /api/v1/health` |
| `GET /info` | `GET /api/v1/version` |
| `POST /user/create` | `POST /api/v1/user/create` |
| `GET /user/list` | `GET /api/v1/user/list` |
| `POST /user/start` | `POST /api/v1/user/start` |
| `POST /user/stop` | `POST /api/v1/user/stop` |
| `GET /user/active` | `GET /api/v1/user/active` |
| `POST /user/import/backup` | `POST /api/v1/user/import/backup` |
| `POST /user/import/backup/preview` | `POST /api/v1/user/import/backup/preview` |

---

## 4. Implementation Architecture

### v1 Router Module

The versioned API is implemented as an **additive router module** (`src/api/v1_router.py`) that can be mounted into the FastAPI app with a single line:

```python
# In server.py create_app(), after the existing include_router call:
from .v1_router import router as v1_router
app.include_router(v1_router, prefix="/api/v1")
```

**Key design decisions:**

1. **No modification to `routes.py` or `server.py`** — the v1 router is a companion module
2. **Delegation pattern** — v1 endpoints delegate to the same business logic as root endpoints (when wired)
3. **Version stamping** — every v1 response includes `"api_version": "1.0.0"` in the JSON body
4. **Pydantic models** — request bodies use typed Pydantic models with validation

### Current State (P5)

The v1 router is **implemented but not yet wired** into the server. It:

- Is importable and independently testable
- Has 20 passing tests (`tests/test_v1_router.py`)
- Has 25 OpenAPI contract tests (`tests/test_openapi_contract.py`)
- Returns stub responses that document the v1 contract shape
- Can be activated with the single `include_router` line above

### Future Wiring

When the server team wires the v1 router:

1. Add the `include_router` line to `server.py`'s `create_app()`
2. Replace stub responses with delegation to `ProfileStore` / `BrowserLauncher`
3. Add the `X-API-Version` response header via middleware
4. Add deprecation headers (`Deprecation: true`, `Sunset: <date>`) to root endpoints

---

## 5. SDK Strategy

### Python SDK (`antique_sdk`)

Located at `sdk/antique_sdk/`. Key features:

- **Typed client** with dataclass models for all major entities
- **httpx transport injection** for testability (MockTransport in tests)
- **Bearer token auth** support
- **Error hierarchy**: `AntiqueError` → `AntiqueAPIError` → `ProfileNotFound`
- **Context manager** support (`with AntiqueClient(...) as client:`)
- **Raw request escape hatch** for endpoints not yet wrapped

### TypeScript SDK

Located at `sdk/ts/antique_sdk.ts`. Key features:

- **Zero runtime dependencies** (uses global `fetch`)
- **Full type definitions** with interfaces
- **Error hierarchy** mirroring the Python SDK
- **Contract tests** that validate structure without a build step

### SDK Versioning Policy

SDKs version independently from the API:

- SDK version `0.1.0` targets API v1
- SDK will add a `api_version` option to pin/verify the server contract
- Breaking SDK changes bump the SDK major version (not the API version)

---

## 6. Contract Testing Strategy

### OpenAPI Snapshot Tests

`tests/test_openapi_contract.py` validates:

- All expected v1 paths exist in the OpenAPI schema
- HTTP methods are correct (GET/POST)
- Request body schemas have required fields
- All endpoints declare a 200 response
- The schema can be serialized to a snapshot file for diff-based regression

### Runtime Contract Tests

`tests/test_v1_router.py` validates:

- Every v1 response includes `api_version` field
- Endpoint shapes match the documented contract
- Pagination parameters work correctly

### SDK Mock Transport Tests

`tests/test_sdk.py` validates:

- Client sends correct HTTP methods and paths
- Bearer token is injected when configured
- AdsPower envelope is parsed (code=0 → success, code≠0 → error)
- 404s on profile lookups raise `ProfileNotFound`
- 5xx responses raise `AntiqueAPIError` with status code
- Context manager opens and closes properly

---

## 7. Deprecation Policy

### When v2 is Introduced

1. **v1 stays at `/api/v1/`** — no path change, no breaking changes
2. **v2 goes to `/api/v2/`** — new contract, potentially breaking
3. **Root endpoints get `Deprecation: true` header** — still functional
4. **`/api/v1/version` response gains `deprecated: true`** — programmatic detection
5. **SDK adds `api_version` option** — consumers pin to v1 or opt into v2

### Sunset Timeline

| Phase | Duration | Behavior |
|---|---|---|
| v1 stable | Indefinite | Full support |
| v1 deprecated (v2 released) | 6 months | `Deprecation` header, docs updated |
| v1 sunset | 3 months | `Sunset: <date>` header, warnings in logs |
| v1 removed | — | 410 Gone, migration guide published |

---

## 8. Migration Path for Existing Scripts

### Current AdsPower-compatible Scripts

No action needed. Root endpoints (`/user/create`, etc.) remain unchanged.

### New Automation / SDK Consumers

Use the typed SDK:

**Python:**
```python
from antique_sdk import AntiqueClient

with AntiqueClient(base_url="http://127.0.0.1:50325") as client:
    profiles = client.list_profiles()
    uid = client.create_profile(name="my-profile")
    client.start_profile(uid)
```

**TypeScript:**
```typescript
import { AntiqueClient } from "./antique_sdk.ts";

const client = new AntiqueClient({ baseUrl: "http://127.0.0.1:50325" });
const profiles = await client.listProfiles();
const uid = await client.createProfile({ name: "my-profile" });
await client.startProfile(uid);
```

### When v1 Router is Wired

Point SDKs at `http://127.0.0.1:50325/api/v1` for versioned responses. The SDK will support a `versioned=True` option that prepends `/api/v1` to all paths.

---

## 9. Files Created/Modified in P5

| File | Type | Purpose |
|---|---|---|
| `sdk/antique_sdk/__init__.py` | New | Python SDK package init |
| `sdk/antique_sdk/client.py` | New | Typed httpx client with transport injection |
| `sdk/antique_sdk/exceptions.py` | New | Error hierarchy |
| `sdk/antique_sdk/models.py` | New | Dataclass models for all entities |
| `sdk/ts/antique_sdk.ts` | New | TypeScript SDK source |
| `sdk/ts/test_contract.mjs` | New | TS contract tests (run with node) |
| `src/api/v1_router.py` | New | Additive /api/v1 versioned router |
| `tests/conftest.py` | New | Makes SDK importable for pytest |
| `tests/test_sdk.py` | New | 30 Python SDK tests |
| `tests/test_v1_router.py` | New | 20 v1 router tests |
| `tests/test_openapi_contract.py` | New | 25 OpenAPI contract tests |
| `docs/API-VERSIONING.md` | New | This document |

**No existing files modified.** All work is additive and isolated.

---

## 10. Test Results Summary

| Test Suite | Tests | Status |
|---|---|---|
| `tests/test_sdk.py` | 30 | ✅ All pass |
| `tests/test_v1_router.py` | 20 | ✅ All pass |
| `tests/test_openapi_contract.py` | 25 | ✅ All pass |
| `sdk/ts/test_contract.mjs` | 30 | ✅ All pass |
| **Total** | **105** | **✅ All pass** |
