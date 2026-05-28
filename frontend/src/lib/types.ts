/**
 * Types TypeScript miroir des schémas Pydantic backend.
 * Si tu changes backend/schemas.py, mets à jour ici aussi.
 */

export type CreditColor = "red" | "orange" | "yellow" | "green" | "gray";

export interface SearchSummary {
  id: number;
  query: string;
  cities: string | null;
  ran_at: string;
  total: number;
  new_count: number;
}

export interface BusinessSummary {
  dedup_key: string;
  name: string;
  bce_number: string | null;
  vat_number: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  city: string | null;
  locality: string | null;
  postal_code: string | null;
  category: string | null;
  managers: string | null;
  rating: number | null;
  reviews_count: number | null;
  google_rank: number | null;
  call_status: string | null;
  credit_color: CreditColor | null;
  credit_label: string | null;
  credit_reasons: string | null;
}

export interface BusinessDetail extends BusinessSummary {
  legal_form: string | null;
  bce_status: string | null;
  creation_date: string | null;
  capital: string | null;
  nace_activities: string | null;
  gmaps_url: string | null;
  nbb_url: string | null;
  nbb_year: string | null;
  nbb_deposit_date: string | null;
  nbb_model_type: string | null;
  nbb_deposits_count: number | null;
  credit_score: number | null;
  credit_computed_at: string | null;
  has_seo_audit: boolean;
  has_credit_ai_report: boolean;
}

export interface SearchBusinessesResponse {
  items: BusinessSummary[];
  total: number;
  credit_counts: Partial<Record<CreditColor, number>>;
}

export interface CampaignBusiness extends BusinessSummary {
  call_notes: string | null;
  last_call_at: string | null;
  callback_date: string | null;
}

export interface CampaignResponse {
  items: CampaignBusiness[];
  total: number;
  status_counts: Record<string, number>;
}

export interface HistoryStats {
  total_searches: number;
  total_businesses: number;
  total_called: number;
}

export interface HistoryResponse {
  stats: HistoryStats;
  searches: SearchSummary[];
}
