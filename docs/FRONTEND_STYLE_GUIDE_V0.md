# Frontend Style Guide v0 - Cosmetica 5 ERP/EMR

**Version**: 0.1  
**Last Updated**: 2025-12-22  
**Status**: Draft

---

## Design Principles

### 1. **Value First** - Mostrar valor real desde la primera pantalla
- NO landing pages con video largo
- NO animaciones complejas de bienvenida
- Transición rápida a la interfaz real (login → agenda)

### 2. **Clarity** - UI clara, legible para uso prolongado
- Contraste suficiente (WCAG AA mínimo)
- Tipografía legible (sistema operativo nativo)
- Espaciado generoso en áreas de interacción

### 3. **Density** - Densa donde haga falta
- Tablas compactas (muchos registros visibles)
- Formularios eficientes (campos agrupados lógicamente)
- No diseño "aireado" innecesario en vistas de trabajo

### 4. **Explicitness** - Confirmaciones explícitas en acciones críticas
- Diálogos de confirmación para: delete, finalize, refund
- Estados claros de éxito/error
- No acciones destructivas sin confirmación

### 5. **Real Data** - Sin mockups falsos
- Usar datos reales de API o fixtures claros
- No placeholders de "Lorem ipsum"
- Componentes vacíos muestran mensaje útil

---

## Color Palette

### Base Colors (Sobrios)

```css
/* Neutrals */
--gray-50: #fafafa;
--gray-100: #f5f5f5;
--gray-200: #eeeeee;
--gray-300: #e0e0e0;
--gray-400: #bdbdbd;
--gray-500: #9e9e9e;
--gray-600: #757575;
--gray-700: #616161;
--gray-800: #424242;
--gray-900: #212121;

/* Primary (Professional Blue) */
--primary-50: #e3f2fd;
--primary-100: #bbdefb;
--primary-200: #90caf9;
--primary-300: #64b5f6;
--primary-400: #42a5f5;
--primary-500: #2196f3;  /* Main brand color */
--primary-600: #1e88e5;
--primary-700: #1976d2;
--primary-800: #1565c0;
--primary-900: #0d47a1;

/* Semantic Colors */
--success: #4caf50;     /* Green - Actions completed */
--warning: #ff9800;     /* Orange - Attention needed */
--error: #f44336;       /* Red - Errors, destructive actions */
--info: #2196f3;        /* Blue - Informational */

/* Status Colors (Appointments) */
--status-scheduled: #2196f3;   /* Blue */
--status-confirmed: #4caf50;   /* Green */
--status-checked-in: #ff9800;  /* Orange */
--status-completed: #9e9e9e;   /* Gray */
--status-cancelled: #f44336;   /* Red */
--status-no-show: #757575;     /* Dark gray */

/* Background */
--bg-page: #fafafa;         /* Page background */
--bg-card: #ffffff;         /* Card/panel background */
--bg-hover: #f5f5f5;        /* Hover state */
--bg-selected: #e3f2fd;     /* Selected row */
```

### Usage Guidelines

**Primary Blue**: Acciones principales, enlaces, botones primarios  
**Gray Scale**: Texto, bordes, fondos  
**Success Green**: Confirmaciones, estados completados  
**Warning Orange**: Advertencias, estados intermedios  
**Error Red**: Errores, acciones destructivas  

---

## Typography

### Font Family

```css
/* System Font Stack (nativo, rápido, legible) */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
             "Helvetica Neue", Arial, sans-serif;
```

**Rationale**: Fuentes del sistema operativo (SF Pro en macOS, Segoe UI en Windows, Roboto en Android). Rendimiento óptimo, legibilidad garantizada.

### Font Sizes

```css
--text-xs: 0.75rem;    /* 12px - Labels pequeños, timestamps */
--text-sm: 0.875rem;   /* 14px - Texto secundario, tablas */
--text-base: 1rem;     /* 16px - Texto principal */
--text-lg: 1.125rem;   /* 18px - Subtítulos */
--text-xl: 1.25rem;    /* 20px - Títulos de sección */
--text-2xl: 1.5rem;    /* 24px - Títulos de página */
--text-3xl: 1.875rem;  /* 30px - Headlines */
```

### Font Weights

```css
--font-normal: 400;    /* Texto regular */
--font-medium: 500;    /* Énfasis moderado */
--font-semibold: 600;  /* Títulos, labels */
--font-bold: 700;      /* Headlines, CTA */
```

### Line Heights

```css
--leading-tight: 1.25;  /* Títulos */
--leading-normal: 1.5;  /* Texto principal */
--leading-relaxed: 1.75; /* Párrafos largos */
```

---

## Spacing Scale

```css
--spacing-0: 0;
--spacing-1: 0.25rem;  /* 4px */
--spacing-2: 0.5rem;   /* 8px */
--spacing-3: 0.75rem;  /* 12px */
--spacing-4: 1rem;     /* 16px */
--spacing-5: 1.25rem;  /* 20px */
--spacing-6: 1.5rem;   /* 24px */
--spacing-8: 2rem;     /* 32px */
--spacing-10: 2.5rem;  /* 40px */
--spacing-12: 3rem;    /* 48px */
--spacing-16: 4rem;    /* 64px */
```

**Usage**:
- `spacing-2`: Padding interno de botones pequeños
- `spacing-3`: Gap entre elementos relacionados
- `spacing-4`: Padding de cards, margen entre secciones
- `spacing-6`: Margen vertical entre bloques
- `spacing-8`: Separación entre módulos

---

## Component Patterns

### 1. Buttons

#### Primary Button (Acciones principales)
```tsx
<button className="btn-primary">
  Create Appointment
</button>
```

**Styles**:
```css
.btn-primary {
  background: var(--primary-500);
  color: white;
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: 0.375rem;
  font-weight: var(--font-medium);
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: var(--primary-600);
}

.btn-primary:disabled {
  background: var(--gray-400);
  cursor: not-allowed;
}
```

#### Secondary Button (Acciones secundarias)
```tsx
<button className="btn-secondary">
  Cancel
</button>
```

**Styles**:
```css
.btn-secondary {
  background: white;
  color: var(--gray-700);
  padding: var(--spacing-2) var(--spacing-4);
  border: 1px solid var(--gray-300);
  border-radius: 0.375rem;
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: var(--gray-50);
  border-color: var(--gray-400);
}
```

#### Destructive Button (Acciones críticas)
```tsx
<button className="btn-destructive">
  Delete
</button>
```

**Styles**:
```css
.btn-destructive {
  background: var(--error);
  color: white;
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: 0.375rem;
  font-weight: var(--font-medium);
  border: none;
  cursor: pointer;
}

.btn-destructive:hover {
  background: #d32f2f;
}
```

### 2. Cards

```tsx
<div className="card">
  <div className="card-header">
    <h3>Appointment Details</h3>
  </div>
  <div className="card-body">
    {/* Content */}
  </div>
</div>
```

**Styles**:
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--gray-200);
  border-radius: 0.5rem;
  overflow: hidden;
}

.card-header {
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--gray-200);
  background: var(--gray-50);
}

.card-header h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--gray-900);
  margin: 0;
}

.card-body {
  padding: var(--spacing-4);
}
```

### 3. Tables (Dense)

```tsx
<table className="table">
  <thead>
    <tr>
      <th>Patient</th>
      <th>Time</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>John Doe</td>
      <td>10:00 AM</td>
      <td><span className="badge-scheduled">Scheduled</span></td>
      <td><button>Edit</button></td>
    </tr>
  </tbody>
</table>
```

**Styles**:
```css
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.table thead {
  background: var(--gray-100);
  border-bottom: 2px solid var(--gray-300);
}

.table th {
  padding: var(--spacing-2) var(--spacing-3);
  text-align: left;
  font-weight: var(--font-semibold);
  color: var(--gray-700);
}

.table td {
  padding: var(--spacing-2) var(--spacing-3);
  border-bottom: 1px solid var(--gray-200);
}

.table tbody tr:hover {
  background: var(--bg-hover);
}

.table tbody tr.selected {
  background: var(--bg-selected);
}
```

### 4. Badges (Status Indicators)

```tsx
<span className="badge-scheduled">Scheduled</span>
<span className="badge-confirmed">Confirmed</span>
<span className="badge-cancelled">Cancelled</span>
```

**Styles**:
```css
.badge {
  display: inline-block;
  padding: var(--spacing-1) var(--spacing-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  border-radius: 0.25rem;
}

.badge-scheduled {
  background: #e3f2fd;
  color: #1565c0;
}

.badge-confirmed {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge-checked-in {
  background: #fff3e0;
  color: #e65100;
}

.badge-completed {
  background: var(--gray-200);
  color: var(--gray-700);
}

.badge-cancelled {
  background: #ffebee;
  color: #c62828;
}

.badge-no-show {
  background: var(--gray-300);
  color: var(--gray-800);
}
```

### 5. Forms

```tsx
<form className="form">
  <div className="form-group">
    <label htmlFor="patient">Patient</label>
    <input
      id="patient"
      type="text"
      className="form-input"
      placeholder="Search patient..."
    />
  </div>
  
  <div className="form-group">
    <label htmlFor="date">Date</label>
    <input
      id="date"
      type="date"
      className="form-input"
    />
  </div>
  
  <div className="form-actions">
    <button type="button" className="btn-secondary">Cancel</button>
    <button type="submit" className="btn-primary">Save</button>
  </div>
</form>
```

**Styles**:
```css
.form-group {
  margin-bottom: var(--spacing-4);
}

.form-group label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--gray-700);
  margin-bottom: var(--spacing-2);
}

.form-input {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  font-size: var(--text-base);
  border: 1px solid var(--gray-300);
  border-radius: 0.375rem;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.form-input:disabled {
  background: var(--gray-100);
  cursor: not-allowed;
}

.form-actions {
  display: flex;
  gap: var(--spacing-3);
  justify-content: flex-end;
  margin-top: var(--spacing-6);
}
```

### 6. Modals (Confirmación)

```tsx
<div className="modal-overlay">
  <div className="modal">
    <div className="modal-header">
      <h3>Confirm Action</h3>
    </div>
    <div className="modal-body">
      <p>Are you sure you want to delete this appointment?</p>
    </div>
    <div className="modal-footer">
      <button className="btn-secondary">Cancel</button>
      <button className="btn-destructive">Delete</button>
    </div>
  </div>
</div>
```

**Styles**:
```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 0.5rem;
  min-width: 400px;
  max-width: 600px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.modal-header {
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--gray-200);
}

.modal-header h3 {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
}

.modal-body {
  padding: var(--spacing-4);
}

.modal-footer {
  padding: var(--spacing-4);
  border-top: 1px solid var(--gray-200);
  display: flex;
  gap: var(--spacing-3);
  justify-content: flex-end;
}
```

### 7. Sidebar Navigation

```tsx
<nav className="sidebar">
  <div className="sidebar-header">
    <h2>Cosmetica 5</h2>
  </div>
  <ul className="sidebar-menu">
    <li className="sidebar-item active">
      <a href="/agenda">Agenda</a>
    </li>
    <li className="sidebar-item">
      <a href="/patients">Patients</a>
    </li>
    <li className="sidebar-item">
      <a href="/proposals">Proposals</a>
    </li>
  </ul>
</nav>
```

**Styles**:
```css
.sidebar {
  width: 240px;
  background: var(--gray-900);
  color: white;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
}

.sidebar-header {
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--gray-700);
}

.sidebar-header h2 {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
}

.sidebar-menu {
  list-style: none;
  padding: var(--spacing-2) 0;
  margin: 0;
}

.sidebar-item a {
  display: block;
  padding: var(--spacing-3) var(--spacing-4);
  color: var(--gray-300);
  text-decoration: none;
  font-weight: var(--font-medium);
  transition: all 0.2s;
}

.sidebar-item a:hover {
  background: var(--gray-800);
  color: white;
}

.sidebar-item.active a {
  background: var(--primary-600);
  color: white;
}
```

---

## Layout Structure

```
┌─────────────────────────────────────────────────┐
│ Sidebar (240px)  │  Main Content Area          │
│                  │                              │
│ - Agenda         │  ┌──────────────────────┐   │
│ - Patients       │  │  Page Header         │   │
│ - Encounters     │  └──────────────────────┘   │
│ - Proposals      │                              │
│ - Admin          │  ┌──────────────────────┐   │
│                  │  │  Content             │   │
│                  │  │  (Tables/Forms/Cards)│   │
│                  │  └──────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**CSS Grid Layout**:
```css
.app-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.main-content {
  padding: var(--spacing-6);
  background: var(--bg-page);
  overflow-y: auto;
}

.page-header {
  margin-bottom: var(--spacing-6);
}

.page-header h1 {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--gray-900);
  margin: 0 0 var(--spacing-2) 0;
}

.page-header p {
  color: var(--gray-600);
  margin: 0;
}
```

---

## Responsive Breakpoints

```css
/* Mobile First */
--breakpoint-sm: 640px;   /* Small tablets */
--breakpoint-md: 768px;   /* Tablets */
--breakpoint-lg: 1024px;  /* Laptops */
--breakpoint-xl: 1280px;  /* Desktops */
```

**Usage**:
- Mobile: Sidebar collapses to hamburger menu
- Tablet: Sidebar visible, content adjusts
- Desktop: Full layout with generous spacing

---

## Accessibility

### WCAG AA Compliance
- Contrast ratio: 4.5:1 minimum para texto
- Focus indicators: Visible en todos los elementos interactivos
- Keyboard navigation: Tab order lógico
- Screen reader: Labels en todos los inputs

### Focus Styles
```css
*:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}
```

---

## Animation Guidelines

### Principle: **Subtle, Fast, Purposeful**

**Allowed**:
- Hover transitions (0.2s)
- Modal fade-in (0.3s)
- Toast notifications slide-in (0.3s)

**Not Allowed**:
- Long loading animations (>1s)
- Decorative animations sin propósito
- Auto-playing videos

**Example**:
```css
.transition-fast {
  transition: all 0.2s ease-in-out;
}

.transition-moderate {
  transition: all 0.3s ease-in-out;
}
```

---

## Error Handling

### Inline Errors (Form Validation)
```tsx
<div className="form-group">
  <label htmlFor="email">Email</label>
  <input
    id="email"
    type="email"
    className="form-input error"
    value={email}
  />
  <span className="form-error">Invalid email format</span>
</div>
```

**Styles**:
```css
.form-input.error {
  border-color: var(--error);
}

.form-error {
  display: block;
  margin-top: var(--spacing-1);
  font-size: var(--text-sm);
  color: var(--error);
}
```

### Toast Notifications (Success/Error)
```tsx
<div className="toast-success">
  Appointment created successfully
</div>

<div className="toast-error">
  Failed to create appointment. Please try again.
</div>
```

**Styles**:
```css
.toast {
  position: fixed;
  top: var(--spacing-4);
  right: var(--spacing-4);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: 0.375rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  z-index: 1001;
}

.toast-success {
  background: var(--success);
  color: white;
}

.toast-error {
  background: var(--error);
  color: white;
}
```

---

## Data Display Patterns

### Empty States
```tsx
<div className="empty-state">
  <svg className="empty-state-icon">
    {/* Icon */}
  </svg>
  <h3>No appointments found</h3>
  <p>Create your first appointment to get started</p>
  <button className="btn-primary">Create Appointment</button>
</div>
```

**Styles**:
```css
.empty-state {
  text-align: center;
  padding: var(--spacing-12) var(--spacing-6);
  color: var(--gray-600);
}

.empty-state-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto var(--spacing-4);
  color: var(--gray-400);
}

.empty-state h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--gray-900);
  margin: 0 0 var(--spacing-2) 0;
}

.empty-state p {
  margin: 0 0 var(--spacing-4) 0;
}
```

### Loading States
```tsx
<div className="loading-spinner">
  <div className="spinner"></div>
  <p>Loading appointments...</p>
</div>
```

**Styles**:
```css
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-8);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--gray-200);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

---

## Implementation Notes

### CSS Strategy
- **Use CSS Modules** or **Tailwind CSS** (si el equipo lo prefiere)
- Variables CSS para theming
- Mobile-first responsive

### Component Library
- Considerar usar **Radix UI** o **Headless UI** para primitives (accesibles out-of-the-box)
- NO usar librerías pesadas (Material-UI añade mucho bundle size)

### Icons
- **Lucide React** (lightweight, 1KB per icon)
- OR **Heroicons** (Tailwind's icon set)

---

## References

- **WCAG 2.1 AA**: https://www.w3.org/WAI/WCAG21/quickref/
- **Radix UI**: https://www.radix-ui.com/
- **Lucide Icons**: https://lucide.dev/

---

## Changelog

- **v0.1** (2025-12-22): Initial draft - Core patterns for Agenda MVP
