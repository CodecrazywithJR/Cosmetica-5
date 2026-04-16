/**
 * Treatment Session Detail Page
 * Clinical workspace for viewing/editing a treatment session.
 * - Draft: editable notes, photos, complete/cancel actions
 * - Completed/Cancelled: fully read-only, no actions
 * Fully internationalized with next-intl (namespace: treatmentSession)
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { RBACGuard } from '@/components/rbac-guard';
import { DataState } from '@/components/data-state';
import { ROLES } from '@/lib/auth-context';
import { type Locale } from '@/lib/routing';
import {
  useTreatmentSession,
  useUpdateTreatmentSession,
  useCompleteTreatmentSession,
  useCancelTreatmentSession,
  type TreatmentSession,
} from '@/lib/hooks/use-treatment-sessions';

// ─── Status badge ────────────────────────────────────────

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: '#fef3c7', text: '#92400e' },
  completed: { bg: '#d1fae5', text: '#065f46' },
  cancelled: { bg: '#fee2e2', text: '#991b1b' },
};

function StatusBadge({ status, label }: { status: string; label: string }) {
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.draft;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 12px',
        borderRadius: 9999,
        fontSize: 13,
        fontWeight: 600,
        letterSpacing: '0.01em',
        backgroundColor: colors.bg,
        color: colors.text,
      }}
    >
      {label}
    </span>
  );
}

// ─── Confirmation modal ──────────────────────────────────

function ConfirmModal({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  loading,
  variant = 'primary',
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
  variant?: 'primary' | 'danger';
}) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.35)',
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '32px 28px 24px',
          maxWidth: 420,
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: '0 0 12px', fontSize: 18, fontWeight: 600 }}>{title}</h3>
        <p style={{ margin: '0 0 24px', fontSize: 14, color: '#6b7280', lineHeight: 1.5 }}>
          {message}
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            disabled={loading}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              background: '#fff',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 500,
              color: '#374151',
            }}
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={variant === 'danger' ? 'btn-danger' : 'btn-primary'}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? '...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Notes editor with autosave ──────────────────────────

function NotesEditor({
  session,
  readOnly,
}: {
  session: TreatmentSession;
  readOnly: boolean;
}) {
  const t = useTranslations('treatmentSession');
  const updateSession = useUpdateTreatmentSession();
  const [notes, setNotes] = useState(session.notes ?? '');
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef(session.notes ?? '');

  // Sync from server when session changes externally
  useEffect(() => {
    if (session.notes !== lastSavedRef.current) {
      setNotes(session.notes ?? '');
      lastSavedRef.current = session.notes ?? '';
    }
  }, [session.notes]);

  const saveNotes = useCallback(
    async (value: string) => {
      if (value === lastSavedRef.current) return;
      setSaveState('saving');
      try {
        await updateSession.mutateAsync({ id: session.id, data: { notes: value } });
        lastSavedRef.current = value;
        setSaveState('saved');
        setTimeout(() => setSaveState('idle'), 2000);
      } catch {
        setSaveState('idle');
      }
    },
    [session.id, updateSession],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setNotes(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => saveNotes(value), 1500);
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <section style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0, color: '#1f2937' }}>
          {t('editor.title')}
        </h2>
        {saveState !== 'idle' && (
          <span
            style={{
              fontSize: 12,
              color: saveState === 'saving' ? '#9ca3af' : '#10b981',
              fontWeight: 500,
              transition: 'opacity 0.3s',
            }}
          >
            {saveState === 'saving' ? t('editor.saving') : t('editor.saved')}
          </span>
        )}
      </div>
      <textarea
        value={notes}
        onChange={handleChange}
        readOnly={readOnly}
        placeholder={t('editor.placeholder')}
        style={{
          width: '100%',
          minHeight: 200,
          padding: 16,
          borderRadius: 10,
          border: '1px solid #e5e7eb',
          fontSize: 14,
          lineHeight: 1.7,
          resize: 'vertical',
          fontFamily: 'inherit',
          color: '#1f2937',
          backgroundColor: readOnly ? '#f9fafb' : '#fff',
          outline: 'none',
          transition: 'border-color 0.15s',
        }}
        onFocus={(e) => {
          if (!readOnly) e.currentTarget.style.borderColor = '#93c5fd';
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = '#e5e7eb';
        }}
      />
    </section>
  );
}

// ─── Photo dropzone (local state only) ───────────────────

function PhotoDropzone({
  readOnly,
}: {
  readOnly: boolean;
}) {
  const t = useTranslations('treatmentSession');
  const [photos, setPhotos] = useState<{ name: string; url: string }[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList) => {
    const newPhotos = Array.from(files)
      .filter((f) => f.type.startsWith('image/'))
      .map((f) => ({ name: f.name, url: URL.createObjectURL(f) }));
    setPhotos((prev) => [...prev, ...newPhotos]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (readOnly || !e.dataTransfer.files.length) return;
    handleFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!readOnly) setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleClick = () => {
    if (!readOnly) fileInputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) handleFiles(e.target.files);
    e.target.value = '';
  };

  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 10, color: '#1f2937' }}>
        {t('photos.title')}
      </h2>

      {/* Drop area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        style={{
          border: `2px dashed ${isDragOver ? '#60a5fa' : '#d1d5db'}`,
          borderRadius: 12,
          padding: '32px 16px',
          textAlign: 'center',
          cursor: readOnly ? 'default' : 'pointer',
          backgroundColor: isDragOver ? '#eff6ff' : '#fafafa',
          transition: 'all 0.15s',
          opacity: readOnly ? 0.5 : 1,
        }}
      >
        <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.4 }}>📷</div>
        <div style={{ fontSize: 14, color: '#6b7280', fontWeight: 500 }}>{t('photos.dropHere')}</div>
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{t('photos.uploadHint')}</div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleInputChange}
          style={{ display: 'none' }}
          disabled={readOnly}
        />
      </div>

      {/* Preview thumbnails */}
      {photos.length > 0 && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
          {photos.map((photo, i) => (
            <div
              key={i}
              style={{
                width: 80,
                height: 80,
                borderRadius: 8,
                overflow: 'hidden',
                border: '1px solid #e5e7eb',
                position: 'relative',
              }}
            >
              <img
                src={photo.url}
                alt={photo.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>
          ))}
        </div>
      )}

      {photos.length === 0 && (
        <p style={{ fontSize: 13, color: '#9ca3af', marginTop: 10 }}>{t('photos.noPhotos')}</p>
      )}
    </section>
  );
}

// ─── Session actions ─────────────────────────────────────

function SessionActions({
  session,
  onCompleted,
  onCancelled,
}: {
  session: TreatmentSession;
  onCompleted: () => void;
  onCancelled: () => void;
}) {
  const t = useTranslations('treatmentSession');
  const completeSession = useCompleteTreatmentSession();
  const cancelSession = useCancelTreatmentSession();
  const [modal, setModal] = useState<'complete' | 'cancel' | null>(null);

  if (session.status !== 'draft') return null;

  const handleComplete = async () => {
    try {
      await completeSession.mutateAsync(session.id);
      setModal(null);
      onCompleted();
    } catch {
      // error stays in mutation state
    }
  };

  const handleCancel = async () => {
    try {
      await cancelSession.mutateAsync(session.id);
      setModal(null);
      onCancelled();
    } catch {
      // error stays in mutation state
    }
  };

  return (
    <>
      <section style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <button
          className="btn-primary"
          onClick={() => setModal('complete')}
          style={{ padding: '10px 24px', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
        >
          {t('actions.complete')}
        </button>
        <button
          onClick={() => setModal('cancel')}
          style={{
            padding: '10px 24px',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 500,
            border: '1px solid #d1d5db',
            background: '#fff',
            color: '#6b7280',
            cursor: 'pointer',
          }}
        >
          {t('actions.cancel')}
        </button>
      </section>

      <ConfirmModal
        open={modal === 'complete'}
        title={t('confirm.completeTitle')}
        message={t('confirm.completeMessage')}
        confirmLabel={t('confirm.yes')}
        cancelLabel={t('confirm.no')}
        onConfirm={handleComplete}
        onCancel={() => setModal(null)}
        loading={completeSession.isPending}
      />

      <ConfirmModal
        open={modal === 'cancel'}
        title={t('confirm.cancelTitle')}
        message={t('confirm.cancelMessage')}
        confirmLabel={t('confirm.yes')}
        cancelLabel={t('confirm.no')}
        onConfirm={handleCancel}
        onCancel={() => setModal(null)}
        loading={cancelSession.isPending}
        variant="danger"
      />
    </>
  );
}

// ─── Header ──────────────────────────────────────────────

function SessionHeader({ session }: { session: TreatmentSession }) {
  const t = useTranslations('treatmentSession');
  const locale = useLocale();

  const formattedDate = session.performed_at
    ? new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(session.performed_at))
    : '—';

  return (
    <header style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#111827' }}>
          {session.package_name}
        </h1>
        <StatusBadge
          status={session.status}
          label={t(`status.${session.status}` as 'status.draft' | 'status.completed' | 'status.cancelled')}
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px 32px',
          fontSize: 14,
          color: '#4b5563',
        }}
      >
        <div>
          <span style={{ fontWeight: 500, color: '#9ca3af', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {t('header.patient')}
          </span>
          <div style={{ marginTop: 2 }}>{session.patient}</div>
        </div>
        <div>
          <span style={{ fontWeight: 500, color: '#9ca3af', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {t('header.practitioner')}
          </span>
          <div style={{ marginTop: 2 }}>{session.practitioner_name ?? '—'}</div>
        </div>
        <div>
          <span style={{ fontWeight: 500, color: '#9ca3af', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {t('header.performedAt')}
          </span>
          <div style={{ marginTop: 2 }}>{formattedDate}</div>
        </div>
      </div>
    </header>
  );
}

// ─── Main page ───────────────────────────────────────────

export default function TreatmentSessionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const t = useTranslations('treatmentSession');
  const id = params.id as string;

  const { data: session, isLoading, error } = useTreatmentSession(id);

  const readOnly = session?.status !== 'draft';

  return (
    <AppLayout>
      <RBACGuard roles={[ROLES.PRACTITIONER, ROLES.ADMIN]}>
        {/* Back link */}
        <div style={{ marginBottom: 16 }}>
          <button
            onClick={() => router.back()}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: 14,
              color: '#6b7280',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            ← {t('actions.back')}
          </button>
        </div>

        <DataState
          isLoading={isLoading}
          error={error as Error | null}
          errorTitle={t('error.loading')}
        >
          {session && (
            <div style={{ maxWidth: 760, margin: '0 auto' }}>
              <SessionHeader session={session} />

              <NotesEditor session={session} readOnly={readOnly} />

              <PhotoDropzone readOnly={readOnly} />

              <SessionActions
                session={session}
                onCompleted={() => {
                  // Refetch will happen via query invalidation
                }}
                onCancelled={() => {
                  // Refetch will happen via query invalidation
                }}
              />
            </div>
          )}
        </DataState>
      </RBACGuard>
    </AppLayout>
  );
}
