'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import Unauthorized from '@/components/unauthorized';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import apiClient from '@/lib/api-client';

interface FormData {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  confirmPassword: string;
  roles: string[];
  is_active: boolean;
  // Practitioner fields (optional)
  create_practitioner: boolean;
  display_name: string;
  specialty: string;
  calendly_url: string;
}

interface PasswordResponse {
  id: number;
  email: string;
  temporary_password: string;
}

export default function CreateUserPage({ params: { locale } }: { params: { locale: string } }) {
  const { user, hasRole } = useAuth();
  const router = useRouter();
  const t = useTranslations('users');
  const tCommon = useTranslations('common');

  const [formData, setFormData] = useState<FormData>({
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    confirmPassword: '',
    roles: [],
    is_active: true,
    create_practitioner: false,
    display_name: '',
    specialty: '',
    calendly_url: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [calendlyWarnings, setCalendlyWarnings] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);

  // Authorization check
  const isAdmin = hasRole(ROLES.ADMIN);
  if (!isAdmin) {
    return <Unauthorized />;
  }

  // Available roles
  const availableRoles = [
    { value: ROLES.ADMIN, label: t('fields.roles.admin') },
    { value: ROLES.PRACTITIONER, label: t('fields.roles.practitioner') },
    { value: ROLES.RECEPTION, label: t('fields.roles.reception') },
    { value: ROLES.MARKETING, label: t('fields.roles.marketing') },
    { value: ROLES.ACCOUNTING, label: t('fields.roles.accounting') },
  ];

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

    // Password validation
    if (!formData.password) {
      newErrors.password = t('validation.passwordRequired');
    } else if (formData.password.length < 8 || formData.password.length > 16) {
      newErrors.password = t('validation.passwordLength');
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      newErrors.confirmPassword = t('validation.confirmPasswordRequired');
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = t('validation.passwordMismatch');
    }

    // Roles validation
    if (formData.roles.length === 0) {
      newErrors.roles = t('validation.rolesRequired');
    }

    // Practitioner validation
    if (formData.create_practitioner) {
      if (!formData.display_name.trim()) {
        newErrors.display_name = t('validation.displayNameRequired');
      }
      if (!formData.specialty.trim()) {
        newErrors.specialty = t('validation.specialtyRequired');
      }
      
      // Calendly URL warnings (non-blocking)
      if (formData.calendly_url.trim()) {
        const warnings: string[] = [];
        if (!formData.calendly_url.startsWith('https://calendly.com/')) {
          warnings.push(t('validation.calendlyUrlFormat'));
        }
        const parts = formData.calendly_url.replace('https://calendly.com/', '').split('/');
        if (parts.length < 1 || !parts[0]) {
          warnings.push(t('validation.calendlyUrlSlug'));
        }
        setCalendlyWarnings(warnings);
      }
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

    try {
      const payload: any = {
        email: formData.email.trim(),
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        password: formData.password,
        roles: formData.roles,
        is_active: formData.is_active,
      };

      // Add practitioner data if checkbox is checked OR if calendly_url has value
      if (formData.create_practitioner || formData.calendly_url.trim()) {
        const practitionerData: any = {};
        if (formData.display_name.trim()) {
          practitionerData.display_name = formData.display_name.trim();
        }
        if (formData.specialty.trim()) {
          practitionerData.specialty = formData.specialty.trim();
        }
        if (formData.calendly_url.trim()) {
          practitionerData.calendly_url = formData.calendly_url.trim();
        }
        if (Object.keys(practitionerData).length > 0) {
          payload.practitioner_data = practitionerData;
        }
      }

      const response = await apiClient.post<PasswordResponse>('/api/v1/users/', payload);

      // Show temporary password
      setTempPassword(response.data.temporary_password);
    } catch (error: any) {
      if (error.response?.data) {
        const apiErrors = error.response.data;
        const newErrors: Record<string, string> = {};

        // Map API errors to form fields
        Object.keys(apiErrors).forEach((key) => {
          const errorMessage = Array.isArray(apiErrors[key])
            ? apiErrors[key][0]
            : apiErrors[key];
          
          if (key === 'practitioner_data') {
            // Handle nested practitioner errors
            if (typeof errorMessage === 'object') {
              Object.keys(errorMessage).forEach((practKey) => {
                newErrors[practKey] = Array.isArray(errorMessage[practKey])
                  ? errorMessage[practKey][0]
                  : errorMessage[practKey];
              });
            }
          } else {
            newErrors[key] = errorMessage;
          }
        });

        setErrors(newErrors);
      } else {
        setErrors({ general: t('messages.createError') });
      }
    } finally {
      setIsSubmitting(false);
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
    router.push(routes.users.list(locale as Locale));
  };

  // Show practitioner section if ADMIN or PRACTITIONER role is selected OR if checkbox is checked
  const showPractitionerSection = formData.roles.includes(ROLES.ADMIN) || formData.roles.includes(ROLES.PRACTITIONER) || formData.create_practitioner;

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
          <h1 className="text-2xl font-bold">{t('new.title')}</h1>
        </div>

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

          {/* Password */}
          <div className="mb-4">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              {t('fields.password')} <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              id="password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${
                errors.password ? 'border-red-500' : 'border-gray-300'
              }`}
              disabled={isSubmitting}
              placeholder={t('validation.passwordLength')}
            />
            {errors.password && <p className="mt-1 text-sm text-red-600">{errors.password}</p>}
          </div>

          {/* Confirm Password */}
          <div className="mb-4">
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              {t('fields.confirmPassword')} <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={formData.confirmPassword}
              onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
              className={`w-full px-3 py-2 border rounded-md ${
                errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
              }`}
              disabled={isSubmitting}
            />
            {errors.confirmPassword && (
              <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
            )}
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

          {/* Practitioner Section */}
          {showPractitionerSection && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="text-lg font-semibold mb-4">{t('practitioner.title')}</h3>

              {/* Create Practitioner Checkbox */}
              <div className="mb-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.create_practitioner}
                    onChange={(e) => handleInputChange('create_practitioner', e.target.checked)}
                    className="mr-2"
                    disabled={isSubmitting}
                  />
                  <span className="text-sm font-medium text-gray-700">
                    {t('practitioner.createPractitioner')}
                  </span>
                </label>
              </div>

              {formData.create_practitioner && (
                <>
                  {/* Display Name */}
                  <div className="mb-4">
                    <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 mb-1">
                      {t('practitioner.displayName')} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="display_name"
                      value={formData.display_name}
                      onChange={(e) => handleInputChange('display_name', e.target.value)}
                      className={`w-full px-3 py-2 border rounded-md ${
                        errors.display_name ? 'border-red-500' : 'border-gray-300'
                      }`}
                      disabled={isSubmitting}
                    />
                    {errors.display_name && (
                      <p className="mt-1 text-sm text-red-600">{errors.display_name}</p>
                    )}
                  </div>

                  {/* Specialty */}
                  <div className="mb-4">
                    <label htmlFor="specialty" className="block text-sm font-medium text-gray-700 mb-1">
                      {t('practitioner.specialty')} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="specialty"
                      value={formData.specialty}
                      onChange={(e) => handleInputChange('specialty', e.target.value)}
                      className={`w-full px-3 py-2 border rounded-md ${
                        errors.specialty ? 'border-red-500' : 'border-gray-300'
                      }`}
                      disabled={isSubmitting}
                    />
                    {errors.specialty && <p className="mt-1 text-sm text-red-600">{errors.specialty}</p>}
                  </div>

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
                </>
              )}
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
              {isSubmitting ? tCommon('actions.saving') : t('actions.create')}
            </button>
          </div>
        </form>

        {/* Temporary Password Modal */}
        {tempPassword && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
              <h2 className="text-xl font-bold mb-4">{t('messages.userCreated')}</h2>
              <p className="text-sm text-gray-600 mb-4">{t('messages.temporaryPassword')}</p>
              
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
                {t('messages.passwordWarning')}
              </p>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
