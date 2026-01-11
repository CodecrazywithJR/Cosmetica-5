DOMAIN_MODEL.md (vFinal)
0) Convenciones globales
PK: UUID para entidades principales.
Timestamps: created_at, updated_at en todo.
Soft delete (tablas críticas):
is_deleted bool default false, deleted_at nullable, deleted_by_user_id nullable.
Auditoría básica:
created_by_user_id, y donde aplique updated_by_user_id.
Concurrencia: row_version int default 1 (o ETag por updated_at en API).
Buckets MinIO:
clinical: fotos médicas
marketing: media para web/redes
documents: PDFs y adjuntos internos (facturas, consentimientos, adjuntos de visita)
Idiomas soportados: ru|fr|en|uk|hy|es
1) Configuración y multi-sede
app_settings (single row)
id UUID PK
default_country_code CHAR(2) default FR
default_currency string default EUR
default_language enum default fr
enabled_languages JSON array
timezone string default Europe/Paris
created_at, updated_at
clinic_location
id UUID PK
name
address_line1 nullable
city nullable
postal_code nullable
country_code CHAR(2) nullable
timezone default Europe/Paris
is_active bool default true
created_at, updated_at
2) Identidad, roles, profesionales
auth_user
id UUID PK
email unique
password_hash
is_active
last_login_at nullable
created_at, updated_at
auth_role
id UUID PK
name unique: admin|practitioner|reception|marketing|accounting
created_at
auth_user_role
user_id FK -> auth_user
role_id FK -> auth_role
Unique (user_id, role_id)
practitioner
id UUID PK
user_id FK -> auth_user unique
display_name
specialty default "Dermatology"
is_active bool default true
created_at, updated_at
3) Clinical: pacientes, tutores, visitas
referral_source
id UUID PK
code unique (ej: instagram|google_maps|friend|doctor|walk_in|website|other)
label string
is_active bool default true
created_at, updated_at
patient
id UUID PK
first_name
last_name
full_name_normalized nullable (index)
birth_date nullable
sex nullable enum: female|male|other|unknown
email nullable (index)
phone nullable
phone_e164 nullable (index)
Dirección:
address_line1 nullable
city nullable
postal_code nullable
country_code CHAR(2) nullable (index)
Preferencias:
preferred_language enum (uno)
preferred_contact_method nullable enum: phone_call|sms|whatsapp|email
preferred_contact_time nullable
contact_opt_out bool default false
Calidad/duplicados:
identity_confidence enum default low: low|medium|high
is_merged bool default false
merged_into_patient_id FK -> patient nullable
merge_reason nullable
Marketing/estadística:
referral_source_id FK -> referral_source nullable
referral_details nullable
notes nullable
row_version int default 1
Soft delete fields
created_by_user_id FK -> auth_user nullable
created_at, updated_at
Índices
(last_name, first_name)
email, phone_e164, country_code, full_name_normalized
patient_guardian
id UUID PK
patient_id FK -> patient
full_name
relationship
phone nullable
email nullable
address_line1 nullable
city nullable
postal_code nullable
country_code CHAR(2) nullable
created_at, updated_at
encounter
id UUID PK
patient_id FK -> patient
practitioner_id FK -> practitioner nullable
location_id FK -> clinic_location nullable
type enum:
medical_consult|cosmetic_consult|aesthetic_procedure|follow_up|sale_only
status enum: draft|finalized|cancelled
occurred_at datetime
chief_complaint nullable
assessment nullable
plan nullable
internal_notes nullable
Firma futura (no usada en v1): signed_at nullable, signed_by_user_id nullable
row_version int default 1
Soft delete fields
created_by_user_id FK -> auth_user nullable
created_at, updated_at
4) Consentimientos (clave para fotos/marketing/contacto)
consent
id UUID PK
patient_id FK -> patient
consent_type enum:
clinical_photos|marketing_photos|newsletter|marketing_messages
status enum: granted|revoked
granted_at datetime
revoked_at nullable
document_id FK -> document nullable
created_at, updated_at
5) Documentos (unificados) y adjuntos de visita
document
id UUID PK
storage_bucket fixed "documents"
object_key
content_type
size_bytes
sha256 nullable
title nullable
Soft delete fields
created_by_user_id FK -> auth_user nullable
created_at, updated_at
encounter_document
encounter_id FK -> encounter
document_id FK -> document
kind enum: consent_copy|lab_result|instruction|other
Unique (encounter_id, document_id)
6) Fotos dermatológicas (clínicas, inmutables, M:N con visitas)
clinical_photo
id UUID PK
patient_id FK -> patient
taken_at nullable
photo_kind enum: clinical|before|after
clinical_context nullable enum: baseline|follow_up|post_procedure|other
body_area nullable
notes nullable
source_device nullable
Storage:
storage_bucket fixed "clinical"
object_key
thumbnail_object_key nullable (async)
content_type
size_bytes
sha256 nullable
visibility enum default clinical_only (v1)
Soft delete fields
created_by_user_id FK -> auth_user nullable
created_at, updated_at
encounter_photo
encounter_id FK -> encounter
photo_id FK -> clinical_photo
relation_type enum: attached|comparison
Unique (encounter_id, photo_id)
Reglas
Original inmutable.
Fotos pueden existir sin visita y/o asociarse a múltiples visitas.
7) Agenda y citas (Calendly + manual)
appointment
id UUID PK
patient_id FK -> patient nullable
practitioner_id FK -> practitioner nullable
location_id FK -> clinic_location nullable
encounter_id FK -> encounter nullable
source enum: calendly|manual
external_id nullable unique (Calendly)
status enum: scheduled|confirmed|attended|no_show|cancelled
scheduled_start datetime
scheduled_end datetime
notes nullable
cancellation_reason nullable
no_show_reason nullable
Soft delete fields
created_at, updated_at
8) Commerce: catálogo, impuestos, proveedores, compras, inventario, ventas
Impuestos
tax_rate
id UUID PK
country_code CHAR(2) nullable
name
rate_percent decimal(5,2)
is_active bool
created_at, updated_at
Catálogo
product_category
id UUID PK
name unique
created_at, updated_at
product
id UUID PK
sku nullable unique
barcode nullable
name
category_id FK -> product_category nullable
type enum: product|service
description nullable
unit_price_excl_tax decimal(10,2)
tax_rate_id FK -> tax_rate
track_lots bool default false
track_expiry bool default false
is_active bool default true
created_at, updated_at
Proveedores y compras (SAP-lite)
supplier
id UUID PK
name (unique recomendado)
legal_name nullable
vat_number nullable
email nullable
phone nullable
address_line1 nullable
city nullable
postal_code nullable
country_code CHAR(2) nullable
notes nullable
is_active bool default true
created_at, updated_at
purchase_order
id UUID PK
supplier_id FK -> supplier
location_id FK -> clinic_location nullable
status enum: draft|ordered|partially_received|received|cancelled
ordered_at nullable
expected_at nullable
reference nullable
currency default EUR
notes nullable
created_by_user_id FK -> auth_user nullable
created_at, updated_at
purchase_order_line
id UUID PK
purchase_order_id FK -> purchase_order
product_id FK -> product (solo type=product)
quantity_ordered decimal(10,2)
unit_cost decimal(10,2)
tax_rate_percent decimal(5,2) snapshot
quantity_received decimal(10,2) default 0
created_at, updated_at
goods_receipt
id UUID PK
purchase_order_id FK -> purchase_order
received_at datetime
received_by_user_id FK -> auth_user nullable
notes nullable
created_at, updated_at
goods_receipt_line
id UUID PK
goods_receipt_id FK -> goods_receipt
purchase_order_line_id FK -> purchase_order_line
product_id FK -> product
lot_id FK -> inventory_lot nullable
quantity_received decimal(10,2)
expires_at date nullable
unit_cost decimal(10,2)
created_at, updated_at
Inventario por lotes/caducidad
inventory_lot
id UUID PK
product_id FK -> product
lot_code
expires_at date nullable
created_at, updated_at
Unique (product_id, lot_code)
stock_move
id UUID PK
location_id FK -> clinic_location nullable
product_id FK -> product
lot_id FK -> inventory_lot nullable
move_type enum: in|out|adjustment
quantity decimal(10,2)
unit_cost decimal(10,2) nullable (entradas)
reason nullable
occurred_at datetime
Referencia tipada:
reference_type enum: sale|goods_receipt|adjustment|purchase_order|other
reference_id UUID nullable
created_by_user_id FK -> auth_user nullable
created_at, updated_at
Reglas
goods_receipt_line crea automáticamente stock_move(in) (tipo SAP).
sale pagada crea automáticamente stock_move(out).
Ventas + factura obligatoria
sale
id UUID PK
location_id FK -> clinic_location nullable
Cliente:
sold_to_patient_id FK -> patient nullable
sold_to_name nullable
referral_source_id FK -> referral_source nullable (opcional)
status enum: draft|paid|cancelled|refunded
sold_at datetime nullable (cuando pasa a paid)
currency default EUR
Totales snapshot:
subtotal_excl_tax decimal(10,2)
tax_total decimal(10,2)
total_incl_tax decimal(10,2)
row_version int default 1
Soft delete fields
created_by_user_id FK -> auth_user nullable
created_at, updated_at
Constraint lógico
Debe existir sold_to_patient_id o sold_to_name.
sale_line
id UUID PK
sale_id FK -> sale
product_id FK -> product
Snapshot:
product_type_snapshot enum product|service
description_snapshot nullable
unit_price_excl_tax_snapshot decimal(10,2)
tax_rate_percent_snapshot decimal(5,2)
quantity decimal(10,2)
line_total_incl_tax decimal(10,2)
created_at, updated_at
sale_line_lot
(obligatorio si product.track_lots=true)
id UUID PK
sale_line_id FK -> sale_line
lot_id FK -> inventory_lot
quantity decimal(10,2)
Unique (sale_line_id, lot_id)
Pagos (mixtos + comisiones)
payment_method
id UUID PK
code unique: cash|card|bank_transfer|other
name
is_active bool
created_at, updated_at
card_fee_rule
id UUID PK
provider string (ej: SumUp)
country_code CHAR(2) nullable
fee_percent decimal(5,2)
fee_fixed_amount decimal(10,2) default 0
currency default EUR
effective_from date
effective_to nullable
is_active bool
payment
id UUID PK
sale_id FK -> sale
payment_method_id FK -> payment_method
amount_gross decimal(10,2)
fee_amount decimal(10,2) default 0
fee_percent decimal(5,2) nullable (snapshot)
amount_net decimal(10,2) (computed = gross - fee)
paid_at datetime
currency default EUR
provider nullable
provider_reference nullable
created_by_user_id FK -> auth_user nullable
created_at, updated_at
Regla
Se permiten pagos mixtos. En backend se valida que la suma de amount_gross cubra el total.
Facturación
document_sequence
id UUID PK
document_type enum: invoice|credit_note|receipt
country_code CHAR(2)
prefix string
next_number int
Unique (document_type, country_code, prefix)
invoice
id UUID PK
sale_id FK -> sale unique
invoice_number unique
issued_at datetime
billing_name string
billing_address_line1 nullable
billing_city nullable
billing_postal_code nullable
billing_country_code CHAR(2)
document_id FK -> document nullable (PDF)
created_at, updated_at
Regla
Al pasar sale a paid, se crea invoice siempre.
9) Website/CMS (público) + Leads
website_settings
id UUID PK (single row)
clinic_name
phone nullable
email nullable
address_line1 nullable
city nullable
postal_code nullable
country_code CHAR(2) nullable
opening_hours nullable
default_language enum
enabled_languages JSON array
instagram_url nullable
created_at, updated_at
marketing_media_asset
id UUID PK
storage_bucket fixed "marketing"
object_key
content_type
size_bytes
alt_text nullable
language nullable
created_at, updated_at
cms_page
id UUID PK
language enum
slug
title
status enum: draft|published
content text/JSON
seo_title nullable
seo_description nullable
og_media_asset_id FK -> marketing_media_asset nullable
published_at nullable
created_at, updated_at
Unique (language, slug)
cms_post
id UUID PK
language enum
slug
title
status enum: draft|published
excerpt nullable
content text/JSON
cover_media_asset_id FK -> marketing_media_asset nullable
tags JSON array nullable
published_at nullable
created_at, updated_at
Unique (language, slug)
cms_service
id UUID PK
language enum
slug
name
status enum: draft|published
description text/JSON
price_hint nullable
order_index int default 0
created_at, updated_at
Unique (language, slug)
cms_staff_member
id UUID PK
language enum
name
role
bio text nullable
photo_media_asset_id FK -> marketing_media_asset nullable
order_index int default 0
status enum: draft|published
created_at, updated_at
cms_promotion
id UUID PK
language enum
title
status enum: draft|published
content text/JSON
starts_at nullable
ends_at nullable
created_at, updated_at
public_lead
id UUID PK
type enum: contact|appointment_request|newsletter
name nullable
email nullable
phone nullable
message nullable
preferred_language nullable enum
country_code CHAR(2) nullable
source default "website"
status enum: new|handled|spam
created_at, updated_at
10) Social (Instagram) MVP Manual Pack
social_account
id UUID PK
provider enum: instagram_meta
display_name nullable
status enum: disconnected|connected|expired
token_encrypted nullable (futuro)
token_expires_at nullable
created_at, updated_at
social_media_asset
id UUID PK
storage_bucket fixed "marketing"
object_key
content_type
size_bytes
created_at, updated_at
social_post
id UUID PK
language enum
caption text
hashtags nullable
status enum: draft|ready|scheduled|published|manual_only|failed
scheduled_at nullable
published_external_id nullable
error_log nullable
created_by_user_id FK -> auth_user nullable
created_at, updated_at
social_post_asset
post_id FK -> social_post
asset_id FK -> social_media_asset
order_index int
Unique (post_id, asset_id)
MVP
Manual Publish Pack: caption + presigned URLs de assets (marketing).
11) Operación: diagnósticos + auditoría
audit_log
id UUID PK
actor_user_id FK -> auth_user nullable
action enum: create|update|delete|view|export
entity_type string
entity_id UUID
timestamp datetime
metadata_json nullable (ip, user_agent, fields_changed)
(Persistir “diagnósticos” es opcional; el endpoint /ops/diagnostics puede ser sin DB.)
Reglas atómicas (para implementación backend)
Pagar venta (sale -> paid) debe ser transaccional:
validar stock disponible (y lotes si aplica)
crear payment(s) + calcular comisiones si método card
crear stock_move out
crear invoice + asignar document_sequence
Recibir compra (goods_receipt) crea stock_move in automáticamente.
Separación estricta de buckets:
clinical_photo -> clinical
cms/social -> marketing
PDFs/adjuntos -> documents
Siguiente paso (para Copilot, sin que se líe)
Crear apps Django: clinical, commerce, website, social, ops, core (settings/locations).
Generar modelos + migraciones fieles a este documento.
Exponer endpoints CRUD mínimos + /healthz + /ops/diagnostics.
OpenAPI schema.
Frontend ERP consume OpenAPI tipado, sin hardcodear URLs.