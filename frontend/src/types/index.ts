// Shared API types mirroring the backend Pydantic schemas (see docs/api-spec.md).

export type CabinClass = "economy" | "premium_economy" | "business" | "first";

export interface FlightAlertCreate {
  origin: string;
  destination: string;
  target_duration_days: number;
  duration_flexibility_days: number;
  earliest_departure_date: string; // ISO date (YYYY-MM-DD)
  latest_departure_date?: string | null;
  latest_return_date: string;
  is_nonstop_required: boolean;
  max_stops?: number | null;
  cabin_class: CabinClass;
  currency: string;
}

export interface FlightAlertRead extends FlightAlertCreate {
  id: string;
  user_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FlightResultRead {
  departure_date: string;
  return_date: string;
  price: number;
  currency: string;
  carrier?: string | null;
  stops: number;
  is_nonstop: boolean;
  deep_link?: string | null;
  provider: string;
  fetched_at: string;
}

export interface AlertResults {
  alert_id: string;
  origin: string;
  destination: string;
  is_nonstop_required: boolean;
  currency: string;
  lowest_price: number | null;
  results: FlightResultRead[];
}
