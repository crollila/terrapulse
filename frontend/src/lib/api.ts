// Data access. The same JSON contract is served two ways:
//  - live FastAPI backend when NEXT_PUBLIC_API_URL is set  (GET {url}/api/...)
//  - static JSON exported by `python -m terrapulse.export`  (GET {basePath}/data/....json)
// See docs/API.md.

export type Region = { id: string; name: string; country: string; bbox: [number, number, number, number]; setting: string };
export type Variable = {
  id: string;
  name: string;
  long_name: string;
  units: string;
  definition: string;
  decimals: number;
  source: string; // key into Catalog.sources
  period: [number, number]; // first and last calendar year of this variable's record
};
export type Source = {
  id: string;
  short_name: string;
  dataset: string;
  producer: string;
  access: string;
  access_short: string;
  access_url: string;
  native_grid: string;
  kind: string;
  caveat: string;
  credit: string;
  doi?: string;
};

export type Catalog = {
  period: [number, number];
  min_window_years: number;
  regions: Region[];
  variables: Variable[]; // only variables that have data
  source: Source;
  sources: Record<string, Source>;
};

export type WindowTrend = {
  start: number;
  end: number;
  slope_per_decade: number;
  intercept: number;
  ci_low: number;
  ci_high: number;
  p_value: number;
  significant: boolean;
};

export type Trend = {
  start: number;
  end: number;
  n_months: number;
  ols: {
    slope_per_decade: number;
    intercept: number;
    r_squared: number;
    ci_low: number;
    ci_high: number;
    p_value: number;
    naive_ci_low: number;
    naive_ci_high: number;
    naive_p_value: number;
  };
  theil_sen: { slope_per_decade: number; ci_low: number; ci_high: number };
  mann_kendall: { tau: number; p_value: number; classic_p_value: number; variance_factor: number };
  noise: { residual_std: number; lag1_autocorrelation: number; n_effective: number };
  detectability: { years_needed: number | null; low: number | null; high: number | null; record_years: number; more_years: number | null };
};

export type VerdictCode = "robust" | "date_sensitive" | "mixed" | "not_detected";

export type Analysis = {
  region: Region;
  variable: Variable;
  period: [number, number];
  first_month: string; // "YYYY-MM"
  last_month: string;
  series: {
    t: number[];
    year: number[];
    month: number[];
    value: (number | null)[];
    anomaly: (number | null)[];
    climatology: number[];
    annual_year: number[];
    annual_mean: number[];
  };
  trend: Trend;
  windows: WindowTrend[];
  windows_summary: {
    n_windows: number;
    min_years: number;
    share_same_direction: number;
    share_significant_same_direction: number;
    share_significant_opposite_direction: number;
    slope_min: number;
    slope_max: number;
  };
  verdict: { code: VerdictCode; title: string; text: string; direction: "rising" | "falling" };
  quality: {
    months_total: number;
    months_missing: number;
    coverage: number;
    grid_cells: number;
    min_cells_valid: number;
    lag1_autocorrelation: number;
    n_effective: number;
    units_reported_by_nasa: string;
    months_used: number;
    calendar_months_excluded: number[];
  };
  provenance: {
    request_url: string | null;
    retrieved_utc: string | null;
    api_version: string | null;
    sources: string[];
    grid: { n_cells: number; lat_min: number; lat_max: number; lon_min: number; lon_max: number };
    source: Source;
  };
};

export type OverviewRow = {
  region: string;
  name: string;
  bbox: [number, number, number, number];
  slope_per_decade: number;
  ci_low: number;
  ci_high: number;
  p_value: number;
  mk_p_value: number;
  p_value_fdr: number;
  significant_after_fdr: boolean;
  verdict: VerdictCode;
  verdict_title: string;
};

export type Overview = {
  variable: Variable;
  period: [number, number];
  regions: OverviewRow[];
  multiple_testing: { method: string; n_tests: number; n_significant_raw: number; n_significant_fdr: number };
};

const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const DATA_MODE: "live API" | "static snapshot" = API ? "live API" : "static snapshot";

const cache = new Map<string, Promise<unknown>>();

function get<T>(path: string): Promise<T> {
  const url = API ? `${API}/api/${path}` : `${BASE}/data/${path}.json`;
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`Request failed (${r.status}) for ${url}`);
        return r.json();
      }),
    );
  }
  return cache.get(url) as Promise<T>;
}

export const getCatalog = () => get<Catalog>("catalog");
export const getOverview = (variable: string) => get<Overview>(`overview/${variable}`);
export const getAnalysis = (region: string, variable: string) => get<Analysis>(`analysis/${region}/${variable}`);
