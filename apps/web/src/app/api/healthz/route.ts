/**
 * Healthcheck API route for frontend.
 * Checks backend connectivity.
 */
import { NextResponse } from 'next/server';
import { checkBackendHealth } from '@/lib/api';

export async function GET() {
  try {
    const backendHealth = await checkBackendHealth();
    
    return NextResponse.json({
      status: 'ok',
      backend: backendHealth.status === 'ok' ? 'connected' : 'degraded',
      details: backendHealth,
    });
  } catch (error: any) {
    return NextResponse.json({
      status: 'error',
      backend: 'disconnected',
      error: error.message,
    }, { status: 503 });
  }
}
