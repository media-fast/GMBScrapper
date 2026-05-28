/**
 * Client API REST vers le backend FastAPI.
 * Le proxy Vite (/api → :8000) gère le routing en dev.
 */

import axios from "axios";
import type {
  BusinessDetail,
  CampaignResponse,
  HistoryResponse,
  ScrapeProgress,
  ScrapeStartRequest,
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

// ─── Campagne d'appels ───────────────────────────────────────────────
export async function getCampaign(
  status?: string,
): Promise<CampaignResponse> {
  const { data } = await api.get<CampaignResponse>("/campaign", {
    params: status ? { status } : undefined,
  });
  return data;
}

// ─── Historique global ───────────────────────────────────────────────
export async function getHistory(): Promise<HistoryResponse> {
  const { data } = await api.get<HistoryResponse>("/history");
  return data;
}

// ─── Scrape ──────────────────────────────────────────────────────────
export async function startScrape(
  payload: ScrapeStartRequest,
): Promise<{ scrape_id: string }> {
  const { data } = await api.post<{ scrape_id: string }>("/scrapes", payload);
  return data;
}

export async function getScrapeProgress(
  scrapeId: string,
): Promise<ScrapeProgress> {
  const { data } = await api.get<ScrapeProgress>(
    `/scrapes/${scrapeId}/progress`,
  );
  return data;
}
