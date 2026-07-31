/**
 * Typed fetch client for the FastAPI backend.
 *
 * Identity travels in headers, never in a cookie: the Clerk session JWT as `Authorization:
 * Bearer` (ADR-0004, cross-origin), or `X-Dev-User` in local mode (ADR-0008). Which one is
 * decided by `lib/auth`; this client only forwards what it is given.
 * FastAPI error bodies are `{ detail: ... }`: `detail` is a string for our HTTPExceptions, but
 * a list for metadata-validation (422) and for FastAPI's own body validation (422). We
 * normalize both into `ApiError`.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  /** Field-scoped messages when the backend returned a validation list. */
  fieldErrors?: Record<string, string>;

  constructor(status: number, message: string, fieldErrors?: Record<string, string>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

interface FastApiValidationItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

function normalizeError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown })?.detail;

  if (typeof detail === "string") {
    return new ApiError(status, detail);
  }

  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    const messages: string[] = [];
    for (const raw of detail) {
      // Two shapes: FastAPI's {loc,msg,type} and content-registry's plain strings.
      if (typeof raw === "string") {
        messages.push(raw);
        continue;
      }
      const item = raw as FastApiValidationItem;
      const field = item.loc?.filter((p) => p !== "body").join(".") ?? "";
      const msg = item.msg ?? "invalid value";
      if (field) fieldErrors[field] = msg;
      messages.push(field ? `${field}: ${msg}` : msg);
    }
    return new ApiError(status, messages.join("; ") || "Validation failed", fieldErrors);
  }

  return new ApiError(status, `Request failed (${status})`);
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Identity headers for this call; built by `useAuthHeaders()` (lib/auth). */
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = "GET", body, headers, signal } = options;

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      /* non-JSON error body */
    }
    throw normalizeError(response.status, parsed);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
