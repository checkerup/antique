/**
 * antique SDK — minimal TypeScript client for the antique anti-detect browser API.
 *
 * Zero-dependency (uses global fetch, available in Node 18+ and all modern browsers).
 * Fully typed with discriminated response types.
 *
 * Quick start:
 *   import { AntiqueClient } from "./client.mjs";
 *   const client = new AntiqueClient({ baseUrl: "http://127.0.0.1:50325" });
 *   const profiles = await client.listProfiles();
 *   const uid = await client.createProfile({ name: "my-profile" });
 *   await client.startProfile(uid);
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

export interface InfoStatus {
  service: string;
  version: string;
  profile_count: number;
  running_count: number;
  running: string[];
}

export interface Profile {
  user_id: string;
  name: string;
  group_id: string;
  status: string;
  debug_port: number | null;
  ws_endpoint: string | null;
  remark: string;
  tags: string[];
  account_status: string | null;
  user_proxy_config: Record<string, unknown> | null;
  fingerprint_config: Record<string, unknown> | null;
  cookies: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface ProfileCreateRequest {
  name: string;
  group_id?: string;
  user_proxy_config?: Record<string, unknown>;
  fingerprint_config?: Record<string, unknown>;
  cookies?: Record<string, unknown>[];
  remark?: string;
  tags?: string[];
  account_status?: string;
  user_id?: string;
  persona?: Record<string, unknown>;
}

export interface StartedProfile {
  user_id: string;
  debug_port: number;
  ws_endpoint: string;
  pid: number;
  session_id: string;
}

export interface StoppedProfile {
  user_id: string;
  stopped: boolean;
}

export interface ActiveProfile {
  user_id: string;
  session_id: string;
  debug_port: number;
  ws_endpoint: string;
  pid: number;
}

// AdsPower envelope: { code: 0, msg: "success", data: {...} }
interface AdsPowerEnvelope<T> {
  code: number;
  msg: string;
  data: T;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class AntiqueAPIError extends Error {
  statusCode: number | null;
  apiCode: number | null;

  constructor(message: string, statusCode: number | null = null, apiCode: number | null = null) {
    super(message);
    this.name = "AntiqueAPIError";
    this.statusCode = statusCode;
    this.apiCode = apiCode;
  }
}

export class ProfileNotFound extends AntiqueAPIError {
  userId: string;

  constructor(userId: string) {
    super(`Profile not found: ${userId}`, 404);
    this.name = "ProfileNotFound";
    this.userId = userId;
  }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export interface ClientOptions {
  baseUrl?: string;
  apiToken?: string;
  timeout?: number;
}

const DEFAULT_BASE_URL = "http://127.0.0.1:50325";
const DEFAULT_TIMEOUT = 30000;

export class AntiqueClient {
  private baseUrl: string;
  private token: string | null;
  private timeout: number;

  constructor(opts: ClientOptions = {}) {
    this.baseUrl = opts.baseUrl ?? DEFAULT_BASE_URL;
    this.token = opts.apiToken ?? null;
    this.timeout = opts.timeout ?? DEFAULT_TIMEOUT;
  }

  private async request(
    method: string,
    path: string,
    params?: Record<string, string | number>,
    body?: unknown,
  ): Promise<unknown> {
    const url = new URL(path, this.baseUrl);
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        url.searchParams.set(k, String(v));
      }
    }

    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    let resp: Response;
    try {
      resp = await fetch(url.toString(), {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (e) {
      throw new AntiqueAPIError(`Transport error: ${e}`);
    } finally {
      clearTimeout(timeoutId);
    }

    return this.checkResponse(resp, method, path);
  }

  private async checkResponse(resp: Response, method: string, path: string): Promise<unknown> {
    if (resp.status >= 400) {
      let msg = `HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        msg = body.detail ?? body.msg ?? msg;
        if (resp.status === 404 && method === "GET" && path.startsWith("/profile/")) {
          const uid = path.split("/").pop() ?? "";
          throw new ProfileNotFound(uid);
        }
      } catch (e) {
        if (e instanceof ProfileNotFound) throw e;
      }
      throw new AntiqueAPIError(String(msg), resp.status);
    }

    const json = await resp.json();

    // AdsPower envelope
    if (json && typeof json === "object" && "code" in json) {
      const env = json as AdsPowerEnvelope<unknown>;
      if (env.code !== 0) {
        throw new AntiqueAPIError(env.msg ?? "unknown error", resp.status, env.code);
      }
      return env.data;
    }

    // Non-envelope (e.g. /health, /info)
    return json;
  }

  // --- Health & Info ---

  async health(): Promise<HealthStatus> {
    return (await this.request("GET", "/health")) as HealthStatus;
  }

  async info(): Promise<InfoStatus> {
    return (await this.request("GET", "/info")) as InfoStatus;
  }

  // --- Profiles CRUD ---

  async listProfiles(opts?: {
    group_id?: string;
    page?: number;
    page_size?: number;
    search?: string;
    tag?: string;
    account_status?: string;
  }): Promise<Profile[]> {
    const params: Record<string, string | number> = {
      page: opts?.page ?? 1,
      page_size: opts?.page_size ?? 100,
    };
    if (opts?.group_id) params.group_id = opts.group_id;
    if (opts?.search) params.search = opts.search;
    if (opts?.tag) params.tag = opts.tag;
    if (opts?.account_status) params.account_status = opts.account_status;

    const data = (await this.request("GET", "/user/list", params)) as { list: Profile[] };
    return data.list ?? [];
  }

  async createProfile(req: ProfileCreateRequest): Promise<string> {
    const data = (await this.request("POST", "/user/create", undefined, {
      group_id: "0",
      ...req,
    })) as { user_id: string };
    return data.user_id;
  }

  async getProfile(userId: string): Promise<Profile> {
    return (await this.request("GET", `/profile/${userId}`)) as Profile;
  }

  async deleteProfile(userId: string): Promise<boolean> {
    const data = (await this.request("POST", "/user/delete", undefined, {
      user_id: userId,
    })) as { deleted: boolean };
    return data.deleted ?? false;
  }

  // --- Start / Stop / Active ---

  async startProfile(
    userId: string,
    opts?: { debug_port?: number; launch_args?: string[] },
  ): Promise<StartedProfile> {
    const body: Record<string, unknown> = { user_id: userId };
    if (opts?.debug_port) body.debug_port = opts.debug_port;
    if (opts?.launch_args) body.launch_args = opts.launch_args;

    return (await this.request("POST", "/user/start", undefined, body)) as StartedProfile;
  }

  async stopProfile(userId: string): Promise<StoppedProfile> {
    return (await this.request("POST", "/user/stop", undefined, {
      user_id: userId,
    })) as StoppedProfile;
  }

  async activeProfiles(): Promise<ActiveProfile[]> {
    const data = (await this.request("GET", "/user/active")) as { list: ActiveProfile[] };
    return data.list ?? [];
  }

  // --- Migration ---

  async importBackupPreview(sourcePath: string): Promise<Record<string, unknown>> {
    return (await this.request("POST", "/user/import/backup/preview", undefined, {
      source_path: sourcePath,
    })) as Record<string, unknown>;
  }

  async importBackup(
    sourcePath: string,
    opts?: { overwrite?: boolean; limit?: number },
  ): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = { source_path: sourcePath };
    if (opts?.overwrite) body.overwrite = opts.overwrite;
    if (opts?.limit) body.limit = opts.limit;

    return (await this.request("POST", "/user/import/backup", undefined, body)) as Record<string, unknown>;
  }
}
