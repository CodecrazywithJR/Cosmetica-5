'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import Unauthorized from '@/components/unauthorized';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import apiClient from '@/lib/api-client';

interface UserData {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  is_active: boolean;
  is_practitioner: boolean;
  must_change_password: boolean;
  practitioner_data: {
    id: number;
    display_name: string;
    specialty: string;
    calendly_url: string | null;
  } | null;
}

interface FormData {
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  is_active: boolean;
  calendly_url: string;
}

interface PasswordResetResponse {
  temporary_password: string;
}

export default function EditUserPage() {
  const { id, locale } = useParams();
  const router = useRouter();
  const { user, hasRole } = useAuth();
  const t = useTranslations('users');
  const tCommon = useTranslations('common');

  const [userData, setUserData] = useState<UserData | null>(null);
  const [formData, setFormData] = useState<FormData>({
    email: '',
    first_name: '',
    last_name: '',
    roles: [],
    is_active: true,
    calendly_url: '',
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResettingPassword, setIsResettingPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [calendlyWarnings, setCalendlyWarnings] = useState<string[]>([]);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Available roles
  const availableRoles = [
    { value: ROLES.ADMIN, label: t('fields.roles.admin') },
    { value: ROLES.PRACTITIONER, label: t('fields.roles.practitioner') },
    { value: ROLES.RECEPTION, label: t('fields.roles.reception') },
    { value: ROLES.MARKETING, label: t('fields.roles.marketing') },
    { value: ROLES.ACCOUNTING, label: t('fields.roles.accounting') },
  ];

  // Load user data
  useEffect(() => {
    const fetchUser = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get<UserData>(`/api/v1/users/${id}/`);
        const user = response.data;
        
        setUserData(user);
        setFormData({
          email: user.email,
          first_name: user.first_name,
          last_name: user.last_name,
          roles: user.roles,
          is_active: user.is_active,
          calendly_url: (user.practitioner?.calendly_url || user.practitioner_data?.calendly_url) || '',
        });
      } catch (error: any) {
        if (error.response?.status === 404) {
          setErrors({ general: t('messages.userNotFound') });
        } else {
          setErrors({ general: t('messages.loadError') });
        }
      } finally {
        setIsLoading(false);
      }
    };

    if (id) {
      fetchUser();
    }
  }, [id, t]);

  const handleInputChange = (field: keyof FormData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    
    // Clear error for this field
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }

    // Clear calendly warnings when URL changes
    if (field === 'calendly_url') {
      setCalendlyWarnings([]);
    }

    // Clear success message on any change
    if (successMessage) {
      setSuccessMessage(null);
    }
  };

  const handleRoleChange = (role: string) => {
    // Single role selection: replace array with selected role
    setFormData((prev) => ({ ...prev, roles: [role] }));

    // Clear role error
    if (errors.roles) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors.roles;
        return newErrors;
      });
    }

    // Clear success message
    if (successMessage) {
      setSuccessMessage(null);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Email validation
    if (!formData.email.trim()) {
      newErrors.email = t('validation.emailRequired');
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t('validation.emailInvalid');
    }

    // Name validation
    if (!formData.first_name.trim()) {
      newErrors.first_name = t('validation.firstNameRequired');
    }
    if (!formData.last_name.trim()) {
      newErrors.last_name = t('validation.lastNameRequired');
    }

    // Roles validation
    if (formData.roles.length === 0) {
      newErrors.roles = t('validation.rolesRequired');
    }

    // Calendly URL warnings (non-blocking)
    if (formData.calendly_url.trim()) {
      const warnings: string[] = [];
      if (!formData.calendly_url.startsWith('https://calendly.com/')) {
        warnings.push(t('validation.calendlyUrlFormat'));
      }
      const parts = formData.calendly_url.replace('https://calendly.com/', '').split('/');
      if (parts.length < 2 || !parts[1]) {
        warnings.push(t('validation.calendlyUrlSlug'));
      }
      setCalendlyWarnings(warnings);
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});
    setSuccessMessage(null);

    try {
      const payload: any = {
        email: formData.email.trim(),
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        roles: formData.roles,
        is_active: formData.is_active,
      };

      // Add practitioner data to update or delete calendly_url
      if (userData?.practitioner || userData?.practitioner_data || formData.calendly_url.trim()) {
        payload.practitioner_data = {
          calendly_url: formData.calendly_url.trim() || null,
        };
      }

      await apiClient.patch(`/api/v1/users/${id}/`, payload);
      setSuccessMessage(t('messages.updateSuccess'));
      
      // Reload user data to reflect changes
      const response = await apiClient.get<UserData>(`/api/v1/users/${id}/`);
      const user = response.data;
      setUserData(user);
      
      // Sync formData with reloaded data to reflect saved state in UI
      setFormData({
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        roles: user.roles,
        is_active: user.is_active,
        calendly_url: (user.practitioner?.calendly_url || user.practitioner_data?.calendly_url) || '',
      });
    } catch (error: any) {
      if (error.response?.data) {
        const apiErrors = error.response.data;
        const newErrors: Record<string, string> = {};

        // Handle "last admin" error
        if (error.response.status === 400 && 
            (apiErrors.roles || apiErrors.is_active || apiErrors.non_field_errors)) {
          const errorMsg = apiErrors.roles?.[0] || 
                          apiErrors.is_active?.[0] || 
                          apiErrors.non_field_errors?.[0] ||
                          apiErrors.detail;
          
          if (errorMsg && (errorMsg.includes('admin') || errorMsg.includes('último'))) {
            newErrors.general = t('messages.lastAdminError');
          }
        }

        // Map other API errors to form fields
        if (Object.keys(newErrors).length === 0) {
          Object.keys(apiErrors).forEach((key) => {
            const errorMessage = Array.isArray(apiErrors[key])
              ? apiErrors[key][0]
              : apiErrors[key];
            
            if (key === 'practitioner_data') {
              if (typeof errorMessage === 'object' && errorMessage !== null) {
                Object.keys(errorMessage).forEach((practKey) => {
                  const practError = errorMessage[practKey];
                  newErrors[practKey] = Array.isArray(practError)
                    ? String(practError[0])
                    : String(practError);
                });
              }
            } else {
              // Convert to string safely
              newErrors[key] = typeof errorMessage === 'string' 
                ? errorMessage 
                : typeof errorMessage === 'object' && errorMessage !== null
                  ? JSON.stringify(errorMessage)
                  : String(errorMessage);
            }
          });
        }

        // If no specific errors found, show generic error
        if (Object.keys(newErrors).length === 0) {
          newErrors.general = t('messages.updateError');
        }

        setErrors(newErrors);
      } else {
        setErrors({ general: t('messages.updateError') });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async () => {
    if (!confirm(t('messages.confirmPasswordReset'))) {
      return;
    }

    setIsResettingPassword(true);
    setErrors({});

    try {
      const response = await apiClient.post<PasswordResetResponse>(
        `/api/v1/users/${id}/reset-password/`,
        {}
      );
      
      setTempPassword(response.data.temporary_password);
    } catch (error: any) {
      if (error.response?.data?.detail) {
        setErrors({ general: error.response.data.detail });
      } else {
        setErrors({ general: t('messages.resetPasswordError') });
      }
    } finally {
      setIsResettingPassword(false);
    }
  };

  const handleCopyPassword = async () => {
    if (tempPassword) {
      try {
        await navigator.clipboard.writeText(tempPassword);
        setCopiedToClipboard(true);
        setTimeout(() => setCopiedToClipboard(false), 2000);
      } catch (error) {
        console.error('Failed to copy password:', error);
      }
    }
  };

  const handleClosePasswordModal = () => {
    setTempPassword(null);
    setCopiedToClipboard(false);
  };

  // Authorization check (after all hooks)
  const isAdmin = hasRole(ROLES.ADMIN);
  if (!isAdmin) {
    return <Unauthorized />;
  }

  if (isLoading) {
    return (
      <AppLayout>
        <div className="container mx-auto py-6 px-4">
          <div className="flex justify-center items-center h-64">
            <div className="text-gray-600">{tCommon('loading')}</div>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (!userData) {
    return (
      <AppLayout>
        <div className="container mx-auto py-6 px-4">
          <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
            {errors.general || t('messages.userNotFound')}
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="container mx-auto py-6 px-4">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push(routes.users.list(locale as Locale))}
            className="text-sm text-gray-600 hover:text-gray-900 mb-2"
          >
            ← {t('list.title')}
          </button>
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold">{t('edit.title')}</h1>
            <button
              onClick={handleResetPassword}
              disabled={isResettingPassword}
              className="px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 disabled:bg-gray-400"
            >
              {isResettingPassword ? tCommon('loading') : t('actions.resetPassword')}
            </button>
          </div>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded text-green-700">
            {successMessage}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 max-w-2xl">
          {/* General Error */}
          {errors.general && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700">
              {errors.general}
            </div>
          )}

          {/* Email */}
          <div className="mb-4">
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              {t('fields.email')} <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              id="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${
                errors.email ? 'border-red-500' : 'border-gray-300'
              }`}
              disabled={isSubmitting}
            />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
          </div>

          {/* First Name */}
          <div className="mb-4">
            <label htmlFor="first_name" className="block text-sm font-medium text-gray-700 mb-1">
              {t('fields.firstName')} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="first_name"
              value={formData.first_name}
              onChange={(e) => handleInputChange('first_name', e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${
                errors.first_name ? 'border-red-500' : 'border-gray-300'
              }`}
              disabled={isSubmitting}
            />
            {errors.first_name && <p className="mt-1 text-sm text-red-600">{errors.first_name}</p>}
          </div>

          {/* Last Name */}
          <div className="mb-4">
            <label htmlFor="last_name" className="block text-sm font-medium text-gray-700 mb-1">
              {t('fields.lastName')} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="last_name"
              value={formData.last_name}
              onChange={(e) => handleInputChange('last_name', e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${
                errors.last_name ? 'border-red-500' : 'border-gray-300'
              }`}
              disabled={isSubmitting}
            />
            {errors.last_name && <p className="mt-1 text-sm text-red-600">{errors.last_name}</p>}
          </div>

          {/* Roles */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('fields.roles.label')} <span className="text-red-500">*</span>
            </label>
            <p className="text-sm text-gray-600 mb-3">{t('fields.roles.description')}</p>
            <div className="space-y-2">
              {availableRoles.map((role) => (
                <label key={role.value} className="flex items-center">
                  <input
                    type="radio"
                    name="role"
                    value={role.value}
                    checked={formData.roles.includes(role.value)}
                    onChange={() => handleRoleChange(role.value)}
                    className="mr-2"
                    disabled={isSubmitting}
                  />
                  <span className="text-sm">{role.label}</span>
                </label>
              ))}
            </div>
            {errors.roles && <p className="mt-1 text-sm text-red-600">{errors.roles}</p>}
          </div>

          {/* Is Active */}
          <div className="mb-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => handleInputChange('is_active', e.target.checked)}
                className="mr-2"
                disabled={isSubmitting}
              />
              <span className="text-sm font-medium text-gray-700">{t('fields.isActive')}</span>
            </label>
          </div>

          {/* Must Change Password Indicator */}
          {userData.must_change_password && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-sm text-yellow-800">
                ⚠️ {t('messages.mustChangePasswordActive')}
              </p>
            </div>
          )}

          {/* Practitioner Section */}
          {(formData.roles.includes(ROLES.ADMIN) || 
            formData.roles.includes(ROLES.PRACTITIONER) || 
            userData.practitioner || 
            userData.practitioner_data) && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="text-lg font-semibold mb-4">{t('practitioner.title')}</h3>

              {userData.practitioner_data && (
                <div className="mb-3 text-sm text-gray-600">
                  <p><strong>{t('practitioner.displayName')}:</strong> {userData.practitioner_data.display_name}</p>
                  <p><strong>{t('practitioner.specialty')}:</strong> {userData.practitioner_data.specialty}</p>
                </div>
              )}

              {!userData.practitioner_data && (
                <p className="text-sm text-gray-600 mb-3">{t('practitioner.noPractitioner')}</p>
              )}

              {/* Calendly URL */}
              <div className="mb-4">
                <label htmlFor="calendly_url" className="block text-sm font-medium text-gray-700 mb-1">
                  {t('practitioner.calendlyUrl')}
                </label>
                <input
                  type="url"
                  id="calendly_url"
                  value={formData.calendly_url}
                  onChange={(e) => handleInputChange('calendly_url', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  disabled={isSubmitting}
                  placeholder="https://calendly.com/username/event"
                />
                {calendlyWarnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {calendlyWarnings.map((warning, index) => (
                      <p key={index} className="text-sm text-yellow-600 flex items-start">
                        <span className="mr-1">⚠️</span>
                        <span>{warning}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Buttons */}
          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={() => router.push(routes.users.list(locale as Locale))}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              disabled={isSubmitting}
            >
              {tCommon('actions.cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              disabled={isSubmitting}
            >
              {isSubmitting ? tCommon('actions.saving') : t('actions.save')}
            </button>
          </div>
        </form>

        {/* Temporary Password Modal */}
        {tempPassword && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
              <h2 className="text-xl font-bold mb-4">{t('messages.passwordReset')}</h2>
              <p className="text-sm text-gray-600 mb-4">{t('messages.passwordResetInstructions')}</p>
              
              <div className="bg-gray-50 border border-gray-200 rounded p-4 mb-4">
                <p className="text-sm text-gray-500 mb-1">{t('fields.password')}</p>
                <p className="text-lg font-mono font-bold break-all">{tempPassword}</p>
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={handleCopyPassword}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  {copiedToClipboard ? t('messages.passwordCopied') : t('actions.copyPassword')}
                </button>
                <button
                  onClick={handleClosePasswordModal}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  {tCommon('actions.close')}
                </button>
              </div>

              <p className="text-xs text-gray-500 mt-4 text-center">
                {t('messages.passwordShareSecurely')}
              </p>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
