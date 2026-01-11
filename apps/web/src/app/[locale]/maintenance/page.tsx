'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { getDiagnostics, SystemDiagnostics } from '@/lib/diagnostics';

export default function MaintenancePage() {
  const t = useTranslations();
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const loadDiagnostics = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getDiagnostics();
      setDiagnostics(data);
      setLastUpdate(new Date());
    } catch (err: any) {
      console.error('Error loading diagnostics:', err);
      setError(err.response?.data?.detail || 'Failed to load diagnostics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiagnostics();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadDiagnostics, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !diagnostics) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">System Maintenance</h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600">Loading diagnostics...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">System Maintenance</h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="text-red-800 font-semibold">Error loading diagnostics</p>
            <p className="text-red-600 mt-2">{error}</p>
            <button
              onClick={loadDiagnostics}
              className="mt-4 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!diagnostics) return null;

  const getStatusColor = (status: string) => {
    if (status === 'healthy' || status === 'ok' || status === 'active') return 'text-green-600';
    if (status === 'degraded' || status === 'warning') return 'text-yellow-600';
    return 'text-red-600';
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = 'px-3 py-1 rounded-full text-sm font-semibold';
    if (status === 'healthy' || status === 'ok' || status === 'active') {
      return `${baseClasses} bg-green-100 text-green-800`;
    }
    if (status === 'degraded' || status === 'warning') {
      return `${baseClasses} bg-yellow-100 text-yellow-800`;
    }
    return `${baseClasses} bg-red-100 text-red-800`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">System Maintenance</h1>
            {lastUpdate && (
              <p className="text-gray-600 mt-1">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </p>
            )}
          </div>
          <button
            onClick={loadDiagnostics}
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>

        {/* Services Status */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Service Health</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {diagnostics.services.map((service) => (
                <div key={service.name} className="border rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <h3 className="font-semibold">{service.name}</h3>
                    <span className={getStatusBadge(service.status)}>
                      {service.status}
                    </span>
                  </div>
                  {service.details && (
                    <div className="mt-2 text-sm text-gray-600">
                      {Object.entries(service.details).map(([key, value]) => (
                        <div key={key}>
                          <span className="font-medium">{key}:</span> {String(value)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* System Resources */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Disk Space */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Disk Space</h2>
            </div>
            <div className="p-6">
              <div className="mb-4">
                <div className="flex justify-between mb-2">
                  <span className="text-gray-600">Usage</span>
                  <span className="font-semibold">{diagnostics.disk_space.percent}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full ${
                      diagnostics.disk_space.percent > 90
                        ? 'bg-red-600'
                        : diagnostics.disk_space.percent > 75
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                    }`}
                    style={{ width: `${diagnostics.disk_space.percent}%` }}
                  />
                </div>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total:</span>
                  <span className="font-medium">{diagnostics.disk_space.total}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Used:</span>
                  <span className="font-medium">{diagnostics.disk_space.used}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Free:</span>
                  <span className="font-medium">{diagnostics.disk_space.free}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Database */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Database Connections</h2>
            </div>
            <div className="p-6">
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Total:</span>
                  <span className="text-2xl font-bold">{diagnostics.database.total_connections}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Active:</span>
                  <span className="text-xl font-semibold text-green-600">
                    {diagnostics.database.active_connections}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Idle:</span>
                  <span className="text-xl font-semibold text-gray-500">
                    {diagnostics.database.idle_connections}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Redis & Celery */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Redis */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Redis Cache</h2>
            </div>
            <div className="p-6 space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Connected Clients:</span>
                <span className="font-medium">{diagnostics.redis.connected_clients}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Memory Used:</span>
                <span className="font-medium">{diagnostics.redis.used_memory}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Peak Memory:</span>
                <span className="font-medium">{diagnostics.redis.used_memory_peak}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Uptime:</span>
                <span className="font-medium">{diagnostics.redis.uptime_days} days</span>
              </div>
            </div>
          </div>

          {/* Celery Workers */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold">Celery Workers</h2>
            </div>
            <div className="p-6">
              {diagnostics.celery_workers.map((worker, idx) => (
                <div key={idx} className="mb-4 last:mb-0">
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-medium text-sm truncate">{worker.hostname}</span>
                    <span className={getStatusBadge(worker.status)}>{worker.status}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-gray-600">Active:</span>{' '}
                      <span className="font-medium">{worker.active_tasks}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Processed:</span>{' '}
                      <span className="font-medium">{worker.processed_tasks}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* MinIO Buckets */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold">MinIO Storage Buckets</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {diagnostics.minio_buckets.map((bucket) => (
                <div
                  key={bucket.name}
                  className={`border rounded-lg p-4 ${
                    bucket.accessible ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-semibold">{bucket.name}</h3>
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        bucket.accessible
                          ? 'bg-green-200 text-green-800'
                          : 'bg-red-200 text-red-800'
                      }`}
                    >
                      {bucket.accessible ? 'Accessible' : 'Not Accessible'}
                    </span>
                  </div>
                  {bucket.accessible && (
                    <div className="text-sm text-gray-600">
                      <p>Objects: {bucket.object_count ?? 'N/A'}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Quick Actions</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button className="bg-gray-600 text-white px-4 py-3 rounded-lg hover:bg-gray-700 disabled:opacity-50" disabled>
                Clear Cache
                <p className="text-xs mt-1 opacity-75">Coming soon</p>
              </button>
              <button className="bg-gray-600 text-white px-4 py-3 rounded-lg hover:bg-gray-700 disabled:opacity-50" disabled>
                View Logs
                <p className="text-xs mt-1 opacity-75">Coming soon</p>
              </button>
              <button className="bg-gray-600 text-white px-4 py-3 rounded-lg hover:bg-gray-700 disabled:opacity-50" disabled>
                Restart Services
                <p className="text-xs mt-1 opacity-75">Coming soon</p>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
