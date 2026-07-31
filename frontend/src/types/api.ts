/** Mirrors backend/app/schemas/*.py. Hand-maintained for this pass; see
 * docs/05-architecture.md for the plan to generate these from the backend's
 * OpenAPI schema once the API surface stabilizes past the donation flow. */

export interface PublicEvent {
  id: string;
  title: string;
  slug: string;
  description: string | null;
  banner_url: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface DonorInput {
  full_name: string;
  mobile_number: string;
  email?: string;
  address?: string;
  pan_number?: string;
}

export interface DonationInitiateRequest {
  event_id: string | null;
  donor: DonorInput;
  amount_in_paise: number;
  purpose?: string;
}

export interface DonationInitiateResponse {
  donation_id: string;
  razorpay_order_id: string;
  razorpay_key_id: string;
  amount_in_paise: number;
  currency: string;
}

export type DonationStatus = "pending" | "success" | "failed" | "refunded";

export interface DonationStatusResponse {
  status: DonationStatus;
  receipt_number: string | null;
  receipt_download_url: string | null;
}

// --- Admin ---------------------------------------------------------------

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export type EventStatus = "draft" | "active" | "closed";

export interface AdminEvent {
  id: string;
  title: string;
  slug: string;
  description: string | null;
  banner_url: string | null;
  status: EventStatus;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventCreateInput {
  title: string;
  slug: string;
  description?: string | null;
  banner_url?: string | null;
  status?: EventStatus;
  start_date?: string | null;
  end_date?: string | null;
}

export type EventUpdateInput = Partial<EventCreateInput>;

export interface AdminDonationListItem {
  id: string;
  donor_name: string;
  donor_mobile: string;
  event_title: string | null;
  amount_in_paise: number;
  status: DonationStatus;
  purpose: string | null;
  receipt_number: string | null;
  created_at: string;
}

export interface AdminPayment {
  razorpay_order_id: string;
  razorpay_payment_id: string | null;
  status: string;
  method: string | null;
  failure_reason: string | null;
  captured_at: string | null;
}

export interface AdminReceipt {
  receipt_number: string;
  duplicate_count: number;
  emailed_at: string | null;
  download_url: string;
}

export interface AdminDonationDetail {
  id: string;
  organization_id: string;
  donor_id: string;
  donor_snapshot: Record<string, string>;
  event_id: string | null;
  event_title: string | null;
  amount_in_paise: number;
  currency: string;
  purpose: string | null;
  status: DonationStatus;
  created_at: string;
  payment: AdminPayment | null;
  receipt: AdminReceipt | null;
}

export interface DashboardSummary {
  today_total_in_paise: number;
  week_total_in_paise: number;
  month_total_in_paise: number;
  year_total_in_paise: number;
  all_time_total_in_paise: number;
  total_donation_count: number;
  recent_donations: AdminDonationListItem[];
}

export interface DonorListItem {
  id: string;
  full_name: string;
  mobile_number: string;
  email: string | null;
  total_donated_in_paise: number;
  donation_count: number;
  last_donation_at: string | null;
}

export interface DonorDonationHistoryItem {
  id: string;
  amount_in_paise: number;
  status: DonationStatus;
  purpose: string | null;
  event_title: string | null;
  receipt_number: string | null;
  created_at: string;
}

export interface DonorDetail {
  id: string;
  full_name: string;
  mobile_number: string;
  email: string | null;
  address: string | null;
  pan_number: string | null;
  created_at: string;
  donations: DonorDonationHistoryItem[];
}

export type AdminRole = "super_admin" | "admin" | "treasurer" | "coordinator" | "viewer";

export interface AdminUserListItem {
  id: string;
  email: string;
  full_name: string;
  roles: AdminRole[];
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AdminUserCreateInput {
  email: string;
  full_name: string;
  password: string;
  roles: AdminRole[];
}

export interface AdminUserUpdateInput {
  full_name?: string;
  roles?: AdminRole[];
  is_active?: boolean;
}

export interface AuditLogEntry {
  id: string;
  actor_admin_user_id: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  signature_image_url: string | null;
  contact_email: string | null;
  pan_number: string | null;
  address: string | null;
  receipt_prefix: string;
  status: string;
}

export type OrganizationUpdateInput = Partial<
  Pick<Organization, "name" | "logo_url" | "signature_image_url" | "contact_email" | "pan_number" | "address" | "receipt_prefix">
>;
