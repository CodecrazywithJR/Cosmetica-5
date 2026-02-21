/**
 * System diagnostics
 */

export interface SystemDiagnostics {
  apiStatus: 'ok' | 'error';
  apiBaseUrl: string;
  timestamp: string;
}

export async function getDiagnostics(): Promise<SystemDiagnostics> {
  const apiBaseUrl = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/healthz/`, {
      method: 'GET',
    });
    
    return {
      apiStatus: response.ok ? 'ok' : 'error',
      apiBaseUrl,
      timestamp: new Date().toISOString(),
    };
  } catch (e) {
    return {
      apiStatus: 'error',
      apiBaseUrl,
      timestamp: new Date().toISOString(),
    };
  }
}
