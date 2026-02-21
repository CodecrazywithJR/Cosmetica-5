/**
 * API Client — Enterprise JWT implementation
 *
 * Access token is injected via tokenProvider (set by AuthContext).
 * No localStorage reads. No direct auth dependency.
 * 401 → single refresh attempt → retry once → throw.
 */

const API_BASE_URL =
  (typeof window !== 'undefined'
    ? (window as any).ENV?.NEXT_PUBLIC_API_BASE_URL
    : undefined) ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

// ---------------------------------------------------------------------------
// Token provider — set by AuthContext on mount
// ---------------------------------------------------------------------------
let tokenProvider: () => string | null = () => null;

export const setTokenProvider = (provider: () => string | null): void => {
  tokenProvider = provider;
};

// ---------------------------------------------------------------------------
// Refresh handler — set by AuthContext on mount
// ---------------------------------------------------------------------------
let refreshHandler: (() => Promise<boolean>) | null = null;

export const setRefreshHandler = (handler: () => Promise<boolean>): void => {
  refreshHandler = handler;
};

// ---------------------------------------------------------------------------
// Refresh lock — ensures only one refresh call is in flight at a time
// ---------------------------------------------------------------------------
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

function acquireRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    // Another request already triggered refresh — piggyback on it
    return refreshPromise;
  }
  isRefreshing = true;
  refreshPromise = (refreshHandler ? refreshHandler() : Promise.resolve(false)).finally(() => {
    isRefreshing = false;
    refreshPromise = null;
  });
  return refreshPromise;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface RequestOptions extends RequestInit {
  params?: Record<string, any>;
  _retry?: boolean; // internal flag — prevents infinite retry loop
}

// ---------------------------------------------------------------------------
// ApiClient class
// ---------------------------------------------------------------------------
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private buildUrl(endpoint: string, params?: Record<string, any>): string {
    const url = new URL(endpoint, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    return url.toString();
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, _retry = false, ...fetchOptions } = options;
    const url = this.buildUrl(endpoint, params);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (fetchOptions.headers) {
      Object.entries(fetchOptions.headers as Record<string, string>).forEach(
        ([key, value]) => {
          if (typeof value === 'string') headers[key] = value;
        }
      );
    }

    // Inject access token from memory (never localStorage)
    const token = tokenProvider();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, { ...fetchOptions, headers });

    // -------------------------------------------------------------------
    // 401 handling: attempt token refresh once, then retry
    // -------------------------------------------------------------------
    if (response.status === 401 && !_retry) {
      const refreshed = await acquireRefresh();
      if (refreshed) {
        // Retry the original request exactly once with the new token
        return this.request<T>(endpoint, { ...options, _retry: true });
      }
      // Refresh failed — build and throw error without retrying
      const err: any = new Error('HTTP 401');
      err.response = { status: 401, statusText: 'Unauthorized', data: { detail: 'Session expired.' } };
      throw err;
    }

    if (!response.ok) {
      const error: any = new Error(`HTTP ${response.status}`);
      error.response = { status: response.status, statusText: response.statusText };
      try {
        const contentType = response.headers.get('content-type');
        if (contentType?.includes('application/json')) {
          error.response.data = await response.json();
        } else {
          await response.text(); // drain
          error.response.data = {
            detail: `Server returned ${response.status}. Endpoint may not exist.`,
            url,
          };
        }
      } catch {
        error.response.data = { detail: response.statusText };
      }
      throw error;
    }

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
      throw new Error(`Expected JSON response but got ${contentType || 'unknown'}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'POST', body: JSON.stringify(data) });
  }

  async patch<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'PATCH', body: JSON.stringify(data) });
  }

  async put<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'PUT', body: JSON.stringify(data) });
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
}

const apiClient = new ApiClient(API_BASE_URL);
export default apiClient;
