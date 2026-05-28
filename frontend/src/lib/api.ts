/**
 * Client API REST vers le backend FastAPI.
 * Le proxy Vite (/api → :8000) gère le routing en dev.
 */

import axios from "axios";
import type {
  BusinessDetail,
  SearchBusinessesResponse,
  SearchSummary,
} from "./types";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

// ─── Searches ─────────────────────────────────────────────────────────
export async function listSearches(limit = 100): Promise<SearchSummary[]> {
  const { data } = await api.get<SearchSummary[]>("/searches", {
    params: { limit },
  });
  return data;
}

export async function getSearchBusinesses(
  searchId: number,
): Promise<SearchBusinessesResponse> {
  const { data } = await api.get<SearchBusinessesResponse>(
    `/searches/${searchId}/businesses`,
  );
  return data;
}

// ─── Businesses ───────────────────────────────────────────────────────
export async function getBusinessDetail(
  dedupKey: string,
): Promise<BusinessDetail> {
  const { data } = await api.get<BusinessDetail>(
    `/businesses/${encodeURIComponent(dedupKey)}`,
  );
  return data;
}
