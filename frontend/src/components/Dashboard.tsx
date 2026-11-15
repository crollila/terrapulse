"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Plot from "./Plot";
import { DATA_MODE, getAnalysis, getCatalog, getOverview, type Analysis, type Catalog, type CrosscheckCode, type Overview, type VerdictCode } from "@/lib/api";
import { COLORS, pEq, pct, pval, sig, signed, trendColor } from "@/lib/format";

const RegionMap = dynamic(() => import("./RegionMap"), { ssr: false });

const REPO = "https://github.com/crollila/terrapulse";

const CASES = [
  {
    id: "arctic",
    title: "How fast is the Arctic warming?",
    hint: "Northern Alaska warms fastest of the eight regions, and a second NASA record agrees.",
    region: "north-slope",
    variable: "T2M",
  },
  {
    id: "known-issue",
    title: "A real trend, the wrong size?",
    hint: "Amazon rainfall falls in two records, but twice as fast in MERRA-2. A documented 2005 data change accounts for much of the gap.",
    region: "rondonia",
    variable: "PRECTOTCORR",
  },
  {
    id: "dates",
    title: "A trend that depends on the dates",
    hint: "Sahel rainfall: try different start years in the date-range check.",
    region: "central-sahel",
    variable: "PRECTOTCORR",
  },
  {
    id: "notyet",
    title: "No trend, or not enough data?",
    hint: "Murray–Darling rainfall: see how many years of data it would take to detect a trend this size.",
    region: "murray-darling",
    variable: "PRECTOTCORR",
  },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Issue #3: the comparison region is drawn in violet, so it stays apart from the
// primary region (which keeps its direction colour: amber up, sky blue down, grey
// when not significant) in the legend and on the chart even where the two cross.
const COMPARE_COLOR = "#a78bfa";

const VERDICT_STYLE: Record<VerdictCode, { label: string; cls: string }> = {
  robust: { label: "Holds across dates", cls: "border-emerald-400/50 bg-emerald-400/10 text-emerald-200" },
  date_sensitive: { label: "Depends on dates", cls: "border-amber-400/50 bg-amber-400/10 text-amber-200" },
  mixed: { label: "Tests disagree", cls: "border-violet-400/50 bg-violet-400/10 text-violet-200" },
  not_detected: { label: "Not detected", cls: "border-slate-400/50 bg-slate-400/10 text-slate-200" },
};

// How the second-opinion box is tinted: green when an independent record agrees, amber when it
// does not confirm or disagrees on size, red when it contradicts, grey when nothing was checked.
const CROSS_STYLE: Record<CrosscheckCode, { box: string; text: string }> = {
  agrees: { box: "border-emerald-400/40 bg-emerald-400/5", text: "text-emerald-200" },
  agrees_none: { box: "border-emerald-400/40 bg-emerald-400/5", text: "text-emerald-200" },
  direction_only: { box: "border-amber-400/50 bg-amber-400/5", text: "text-amber-200" },
  missed: { box: "border-amber-400/50 bg-amber-400/5", text: "text-amber-200" },
  not_confirmed: { box: "border-amber-400/60 bg-amber-400/10", text: "text-amber-200" },
  conflict: { box: "border-red-400/60 bg-red-500/10", text: "text-red-200" },
  none: { box: "border-slate-600/70 bg-slate-800/40", text: "text-slate-200" },
};

// Short region name for chart legends, where the full names do not fit.
const shortName = (a: Analysis) => a.region.short_name ?? a.region.name;

// What an independent dataset says about a region's full-record trend, in one sentence.
// Used by the comparison caption so that a second region is never shown without it.
function secondOpinion(a: Analysis): string {
  const c = a.crosscheck;
  if (!c) return "";
  const label = c.label.charAt(0).toLowerCase() + c.label.slice(1);
  return ` Second opinion (full record): ${label}.${c.known_issue ? " A known data issue affects this result." : ""}`;
}

// True when independent data does not back a region's trend as it stands.
function weaklySupported(a: Analysis): boolean {
  const code = a.crosscheck?.code;
  return code === "not_confirmed" || code === "direction_only" || code === "missed" || code === "conflict" || !!a.crosscheck?.known_issue;
}

const lat = (v: number) => `${Math.abs(v)}°${v < 0 ? "S" : "N"}`;
const lon = (v: number) => `${Math.abs(v)}°${v < 0 ? "W" : "E"}`;

function Card({ title, sub, children, className = "" }: { title?: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-700/60 bg-slate-900/70 p-4 ${className}`}>
      {title && <h2 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h2>}
      {sub && <p className="mt-1 text-xs leading-relaxed text-slate-400">{sub}</p>}
      {children}
    </section>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2">
      <div className="tp-fine uppercase tracking-wider text-slate-400">{label}</div>
      <div className="mt-0.5 font-mono text-base text-slate-50">{value}</div>
      {note && <div className="tp-fine text-slate-400">{note}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [variable, setVariable] = useState("T2M");
  const [region, setRegion] = useState("upper-colorado");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [view, setView] = useState<"anomaly" | "raw">("anomaly");
  const [error, setError] = useState<string | null>(null);
  // Issue #3: the region to compare with, if any. Its data is fetched with the same
  // getAnalysis(region, variable) call as the primary region; no backend change needed.
  const [compareRegion, setCompareRegion] = useState<string | null>(null);
  const [compareAnalysis, setCompareAnalysis] = useState<Analysis | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  useEffect(() => {
    getCatalog().then(setCatalog).catch((e) => setError(String(e.message ?? e)));
  }, []);

  useEffect(() => {
    let live = true;
    getOverview(variable)
      .then((o) => live && setOverview(o))
      .catch((e) => live && setError(String(e.message ?? e)));
    return () => {
      live = false;
    };
  }, [variable]);

  useEffect(() => {
    let live = true;
    getAnalysis(region, variable)
      .then((a) => live && setAnalysis(a))
      .catch((e) => live && setError(String(e.message ?? e)));
    return () => {
      live = false;
    };
  }, [region, variable]);

  useEffect(() => {
    if (!compareRegion) return;
    let live = true;
    getAnalysis(compareRegion, variable)
      .then((a) => {
        if (!live) return;
        setCompareAnalysis(a);
        setCompareError(null);
      })
      .catch((e) => live && setCompareError(String(e.message ?? e)));
    return () => {
      live = false;
    };
  }, [compareRegion, variable]);

  const ready = analysis && analysis.region.id === region && analysis.variable.id === variable ? analysis : null;
  const compareReady =
    compareAnalysis && compareRegion && compareAnalysis.region.id === compareRegion && compareAnalysis.variable.id === variable
      ? compareAnalysis
      : null;
  const variableInfo = catalog?.variables.find((v) => v.id === variable);
  // Each variable has its own record length (NDVI starts in 2000, the MERRA-2 variables in 1981).
  const period = useMemo<[number, number]>(() => variableInfo?.period ?? catalog?.period ?? [1981, 2025], [variableInfo, catalog]);
  const [start, end] = range ?? period;
  const minYears = catalog?.min_window_years ?? 15;
  const isFull = start === period[0] && end === period[1];
  const units = ready?.variable.units ?? "";

  const win = useMemo(() => ready?.windows.find((w) => w.start === start && w.end === end) ?? null, [ready, start, end]);
  const win2 = useMemo(
    () => compareReady?.windows.find((w) => w.start === start && w.end === end) ?? null,
    [compareReady, start, end],
  );
  // The point of the comparison (issue #3): one variable can trend in opposite
  // directions in different places. Say so plainly in the caption when it happens.
  const oppositeDirections = win && win2 ? win.slope_per_decade * win2.slope_per_decade < 0 : false;

  const seriesPlot = useMemo(() => {
    if (!ready || !win) return null;
    const s = ready.series;
    const y = view === "anomaly" ? s.anomaly : s.value;
    // Without a comparison the legend keeps its plain names. With one, the legend lists
    // only one line per region, under its short name; the thin monthly lines and the
    // 95% bands are explained in the caption, so the legend fits one row on a phone.
    const comparing = !!compareReady;
    const tag = comparing ? `${shortName(ready)} · ` : "";
    const tag2 = compareReady ? `${shortName(compareReady)} · ` : "";
    const data: unknown[] = [
      {
        x: s.t,
        y,
        type: "scatter",
        mode: "lines",
        name: comparing ? `${tag}monthly` : view === "anomaly" ? "Monthly anomaly" : "Monthly value",
        showlegend: !comparing,
        line: { color: "rgba(148,163,184,0.75)", width: 1 },
        hovertemplate: `%{x:.2f}: %{y:.3f} ${units}<extra></extra>`,
      },
    ];
    if (view === "raw" && s.annual_year.length > 0) {
      data.push({
        x: s.annual_year.map((v) => v + 0.5),
        y: s.annual_mean,
        type: "scatter",
        mode: "lines+markers",
        name: comparing ? `${tag}annual mean` : "Annual mean",
        line: { color: COLORS.ink, width: 2 },
        marker: { size: 4 },
        hovertemplate: `%{x:.0f}: %{y:.3f} ${units}<extra></extra>`,
      });
      // Raw values sit at different levels in different places, so the comparison
      // overlays the second region's annual mean rather than its monthly values.
      if (compareReady && compareReady.series.annual_year.length > 0) {
        data.push({
          x: compareReady.series.annual_year.map((v) => v + 0.5),
          y: compareReady.series.annual_mean,
          type: "scatter",
          mode: "lines+markers",
          name: `${tag2}annual mean`,
          line: { color: COMPARE_COLOR, width: 2, dash: "dash" },
          marker: { size: 4 },
          hovertemplate: `%{x:.0f}: %{y:.3f} ${units}<extra></extra>`,
        });
      }
    } else if (view !== "raw") {
      if (compareReady) {
        data.push({
          x: compareReady.series.t,
          y: compareReady.series.anomaly,
          type: "scatter",
          mode: "lines",
          name: `${tag2}monthly`,
          showlegend: false,
          line: { color: "rgba(167,139,250,0.75)", width: 1, dash: "dot" },
          hovertemplate: `%{x:.2f}: %{y:.3f} ${units}<extra></extra>`,
        });
      }
      const x0 = start;
      const x1 = end + 1;
      const b = win.slope_per_decade / 10;
      const mid = (x0 + x1) / 2;
      const ymid = win.intercept + b * mid;
      const line = (slope: number) => [ymid + (slope / 10) * (x0 - mid), ymid + (slope / 10) * (x1 - mid)];
      const color = trendColor(win.slope_per_decade, win.significant);
      const lo = line(win.ci_low);
      const hi = line(win.ci_high);
      data.push(
        {
          x: [x0, x1, x1, x0],
          y: [lo[0], lo[1], hi[1], hi[0]],
          type: "scatter",
          fill: "toself",
          mode: "lines",
          line: { width: 0 },
          fillcolor: color + "33",
          name: "95% range of slope",
          showlegend: !comparing,
          hoverinfo: "skip",
        },
        {
          x: [x0, x1],
          y: line(win.slope_per_decade),
          type: "scatter",
          mode: "lines",
          name: comparing ? `${tag}trend` : "Trend",
          line: { color, width: 3 },
          hoverinfo: "skip",
        },
      );
      if (compareReady && win2) {
        const b2 = win2.slope_per_decade / 10;
        const ymid2 = win2.intercept + b2 * mid;
        const line2 = (slope: number) => [ymid2 + (slope / 10) * (x0 - mid), ymid2 + (slope / 10) * (x1 - mid)];
        const lo2 = line2(win2.ci_low);
        const hi2 = line2(win2.ci_high);
        data.push(
          {
            x: [x0, x1, x1, x0],
            y: [lo2[0], lo2[1], hi2[1], hi2[0]],
            type: "scatter",
            fill: "toself",
            mode: "lines",
            line: { width: 0 },
            fillcolor: COMPARE_COLOR + "26",
            name: `${tag2}95% range of slope`,
            showlegend: false,
            hoverinfo: "skip",
          },
          {
            x: [x0, x1],
            y: line2(win2.slope_per_decade),
            type: "scatter",
            mode: "lines",
            name: `${tag2}trend`,
            line: { color: COMPARE_COLOR, width: 3, dash: "dash" },
            hoverinfo: "skip",
          },
        );
      }
    }
    return {
      data,
      layout: {
        xaxis: { title: { text: "Year" }, range: [period[0], period[1] + 1] },
        yaxis: { title: { text: view === "anomaly" ? `Difference from normal (${units})` : `${ready.variable.name} (${units})` } },
        margin: { t: 10, b: 84, l: 68 },
        legend: { orientation: "h", y: -0.24, x: 0 },
      },
    };
  }, [ready, win, win2, compareReady, view, start, end, units, period]);

  const heatPlot = useMemo(() => {
    if (!ready) return null;
    const starts = [...new Set(ready.windows.map((w) => w.start))].sort((a, b) => a - b);
    const ends = [...new Set(ready.windows.map((w) => w.end))].sort((a, b) => a - b);
    const z: (number | null)[][] = starts.map(() => ends.map(() => null));
    const text: string[][] = starts.map(() => ends.map(() => ""));
    const nsX: number[] = [];
    const nsY: number[] = [];
    let zmax = 0;
    for (const w of ready.windows) {
      const i = starts.indexOf(w.start);
      const j = ends.indexOf(w.end);
      z[i][j] = w.slope_per_decade;
      text[i][j] = `${w.start}–${w.end}<br>${signed(w.slope_per_decade)} ${units}/decade<br>${pEq(w.p_value)}${w.significant ? "" : " (not significant)"}`;
      zmax = Math.max(zmax, Math.abs(w.slope_per_decade));
      if (!w.significant) {
        nsX.push(w.end);
        nsY.push(w.start);
      }
    }
    return {
      data: [
        {
          type: "heatmap",
          x: ends,
          y: starts,
          z,
          text,
          hovertemplate: "%{text}<extra></extra>",
          zmin: -zmax,
          zmax,
          colorscale: [
            [0, "#0369a1"],
            [0.5, "#1e293b"],
            [1, "#d97706"],
          ],
          colorbar: { title: { text: `${units}/decade`, side: "right" }, thickness: 10, len: 0.9 },
          xgap: 1,
          ygap: 1,
        },
        {
          type: "scatter",
          mode: "markers",
          x: nsX,
          y: nsY,
          marker: { symbol: "x-thin", size: 5, line: { color: "rgba(226,232,240,0.55)", width: 1 } },
          hoverinfo: "skip",
          name: "not significant",
          showlegend: false,
        },
        {
          type: "scatter",
          mode: "markers",
          x: [end],
          y: [start],
          marker: { symbol: "square-open", size: 13, line: { color: "#ffffff", width: 2 } },
          hoverinfo: "skip",
          showlegend: false,
        },
      ],
      layout: {
        xaxis: { title: { text: "End year" }, dtick: 5 },
        yaxis: { title: { text: "Start year" }, dtick: 5, autorange: "reversed" },
        margin: { r: 8 },
      },
    };
  }, [ready, start, end, units]);

  const forestPlot = useMemo(() => {
    if (!overview || overview.variable.id !== variable) return null;
    const rows = [...overview.regions].sort((a, b) => a.slope_per_decade - b.slope_per_decade);
    return {
      data: [
        {
          type: "scatter",
          mode: "markers",
          y: rows.map((r) => r.name),
          x: rows.map((r) => r.slope_per_decade),
          customdata: rows.map((r) => r.region),
          error_x: {
            type: "data",
            symmetric: false,
            array: rows.map((r) => r.ci_high - r.slope_per_decade),
            arrayminus: rows.map((r) => r.slope_per_decade - r.ci_low),
            color: "rgba(226,232,240,0.6)",
            thickness: 1.5,
          },
          marker: {
            size: rows.map((r) => (r.region === region ? 14 : 10)),
            color: rows.map((r) => trendColor(r.slope_per_decade, r.p_value < 0.05 && r.mk_p_value < 0.05)),
            line: { color: rows.map((r) => (r.region === region ? "#ffffff" : "rgba(0,0,0,0)")), width: 2 },
          },
          hovertemplate: `%{y}<br>%{x:.3f} ${overview.variable.units}/decade<extra></extra>`,
        },
      ],
      layout: {
        xaxis: { title: { text: `Trend, ${period[0]}–${period[1]} (${overview.variable.units} per decade)` }, zeroline: true },
        yaxis: { automargin: true, ticksuffix: "  " },
        margin: { l: 210 },
        showlegend: false,
      },
    };
  }, [overview, variable, region, period]);

  function pick(regionId: string, variableId: string) {
    setRegion(regionId);
    setVariable(variableId);
    setRange(null);
    setView("anomaly");
    // A region cannot be compared with itself.
    if (compareRegion === regionId) {
      setCompareRegion(null);
      setCompareAnalysis(null);
      setCompareError(null);
    }
  }

  // Issue #3 welcome polish: download the series behind the time-series chart
  // (primary region, plus the comparison region when one is selected) as CSV.
  function downloadCsv() {
    if (!ready) return;
    const header = ["year", "month", `${ready.region.name} anomaly (${units})`, `${ready.region.name} value (${units})`];
    if (compareReady) header.push(`${compareReady.region.name} anomaly (${units})`, `${compareReady.region.name} value (${units})`);
    const rows: string[][] = [header];
    const s = ready.series;
    const cs = compareReady?.series;
    for (let i = 0; i < s.t.length; i++) {
      const row = [
        String(s.year[i]),
        String(s.month[i]),
        s.anomaly[i] == null ? "" : String(s.anomaly[i]),
        s.value[i] == null ? "" : String(s.value[i]),
      ];
      if (compareReady && cs) {
        row.push(cs.anomaly[i] == null ? "" : String(cs.anomaly[i]), cs.value[i] == null ? "" : String(cs.value[i]));
      }
      rows.push(row);
    }
    const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = compareReady
      ? `terrapulse-${ready.region.id}-vs-${compareReady.region.id}-${variable}.csv`
      : `terrapulse-${ready.region.id}-${variable}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const years = useMemo(() => Array.from({ length: period[1] - period[0] + 1 }, (_, i) => period[0] + i), [period]);
  const t = ready?.trend;
  const det = t?.detectability;
  const source = ready?.provenance.source;
  const cross = ready?.crosscheck;
  const regionInfo = catalog?.regions.find((r) => r.id === region);
  const landOnly = variable === "NDVI" || variable === "GWETROOT"; // these have values over land only
  const excludedMonths = ready?.quality.calendar_months_excluded ?? [];
  const credits = catalog?.sources ? Object.values(catalog.sources).map((s) => s.credit).join("; ") : "NASA GMAO MERRA-2 via NASA POWER";

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pb-16 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3 py-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-sky-300">Earth System Trend Detective</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white sm:text-4xl">TerraPulse</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300">
            Find a trend in NASA Earth-system data. Then find out whether you should believe it: is it bigger than the noise, and does it survive a
            different choice of dates?
          </p>
        </div>
        <nav className="tp-nav flex gap-4 text-sm text-slate-300">
          <a className="hover:text-white" href="#method">Method</a>
          <a className="hover:text-white" href="#data">Data</a>
          <a className="hover:text-white" href={REPO}>Code</a>
        </nav>
      </header>

      {error && (
        <p role="alert" className="mb-4 rounded-lg border border-red-400/50 bg-red-500/10 p-3 text-sm text-red-200">
          Could not load data: {error}
        </p>
      )}

      <Card title="Start with a case file" sub="Four worked examples. Each one sets the place and the variable for you; then explore on your own.">
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {CASES.map((c) => {
            const active = c.region === region && c.variable === variable;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => pick(c.region, c.variable)}
                aria-pressed={active}
                className={`rounded-lg border p-3 text-left transition ${active ? "border-sky-400 bg-sky-400/10" : "border-slate-700 bg-slate-800/50 hover:border-slate-500"}`}
              >
                <div className="text-sm font-medium text-slate-100">{c.title}</div>
                <div className="mt-1 text-xs text-slate-400">{c.hint}</div>
              </button>
            );
          })}
        </div>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3" title="1 · What and where?">
          <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Variable">
            {catalog?.variables.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => pick(region, v.id)}
                aria-pressed={v.id === variable}
                className={`rounded-full border px-3 py-1 text-sm transition ${v.id === variable ? "border-sky-400 bg-sky-400/15 text-white" : "border-slate-600 text-slate-300 hover:border-slate-400"}`}
              >
                {v.name}
              </button>
            ))}
          </div>
          {variableInfo && (
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              <span className="text-slate-200">{variableInfo.name}</span> ({variableInfo.units}): {variableInfo.definition}
            </p>
          )}
          <div className="relative mt-3 h-[340px] overflow-hidden rounded-lg border border-slate-700/60 sm:h-[400px]">
            {overview && <RegionMap rows={overview.regions} selected={region} onSelect={(id) => pick(id, variable)} />}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <span>Full-record trend ({period[0]}–{period[1]}):</span>
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.up }} />significant increase</span>
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.down }} />significant decrease</span>
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS.none }} />not significant</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            A region is coloured when both tests give p &lt; 0.05 for that region on its own. This is before the correction for testing{" "}
            {overview?.multiple_testing.n_tests ?? 8} regions at once; section 5 gives the corrected count. Colours show this dataset&rsquo;s own
            result. Open a region to see whether a second dataset agrees.
          </p>
          <label className="mt-3 block text-xs text-slate-400">
            Region
            <select
              value={region}
              onChange={(e) => pick(e.target.value, variable)}
              className="mt-1 block w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-100"
            >
              {catalog?.regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} — {r.country}
                </option>
              ))}
            </select>
          </label>
          {regionInfo && (
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              <span className="text-slate-200">{regionInfo.name}.</span> {regionInfo.setting} The region is the rectangle {lon(regionInfo.bbox[0])}–
              {lon(regionInfo.bbox[2])}, {lat(regionInfo.bbox[1])}–{lat(regionInfo.bbox[3])} drawn on the map, not an exact basin or border.
            </p>
          )}
        </Card>

        <Card className="lg:col-span-2" title="2 · The verdict">
          {!ready || !t ? (
            <p className="mt-4 text-sm text-slate-400">Loading analysis…</p>
          ) : (
            <>
              <p className="mt-2 text-xs text-slate-400">
                {ready.region.name} · {ready.variable.name} · {period[0]}–{period[1]}
              </p>
              <span className={`mt-3 inline-block rounded-full border px-3 py-1 text-xs font-medium ${VERDICT_STYLE[ready.verdict.code].cls}`}>
                {VERDICT_STYLE[ready.verdict.code].label}
              </span>
              <h3 className="mt-2 text-lg font-semibold leading-snug text-white">{ready.verdict.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">{ready.verdict.text}</p>
              {cross && (
                <div className={`mt-3 rounded-md border p-2.5 ${cross.known_issue ? CROSS_STYLE.not_confirmed.box : CROSS_STYLE[cross.code].box}`}>
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="tp-fine uppercase tracking-wider text-slate-400">Second opinion</span>
                    <span className={`text-xs font-semibold ${CROSS_STYLE[cross.code].text}`}>{cross.label}</span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-300">{cross.text}</p>
                  {cross.dataset && (
                    <p className="mt-1 tp-fine leading-relaxed text-slate-400">
                      {cross.dataset.kind} {cross.dataset.caveat}{" "}
                      <a className="text-sky-300 hover:underline" href={cross.dataset.url}>
                        About {cross.dataset.name} ↗
                      </a>
                    </p>
                  )}
                  {cross.known_issue && (
                    <div className="mt-2 border-t border-amber-400/30 pt-2">
                      <p className="text-xs font-semibold text-amber-200">{cross.known_issue.title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-300">{cross.known_issue.text}</p>
                      <p className="mt-1 tp-fine leading-relaxed text-slate-400">
                        Sources:{" "}
                        {cross.known_issue.sources.map((src, i) => (
                          <span key={src.url}>
                            {i > 0 && "; "}
                            <a className="text-sky-300 hover:underline" href={src.url}>
                              {src.label} ↗
                            </a>
                          </span>
                        ))}
                        . {cross.known_issue.credit}
                      </p>
                    </div>
                  )}
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Stat label="Rate of change" value={`${signed(t.ols.slope_per_decade)}`} note={`${units} per decade`} />
                <Stat label="95% confidence range" value={`${signed(t.ols.ci_low)} to ${signed(t.ols.ci_high)}`} note="allows for persistence" />
                <Stat label="t-test p-value" value={pval(t.ols.p_value)} note={`naive: ${pval(t.ols.naive_p_value)}`} />
                <Stat label="Mann–Kendall p-value" value={pval(t.mann_kendall.p_value)} note={`uncorrected: ${pval(t.mann_kendall.classic_p_value)}`} />
                <Stat label="Sen's slope" value={signed(t.theil_sen.slope_per_decade)} note={`${units} per decade`} />
                <Stat label="Date windows agreeing" value={pct(ready.windows_summary.share_same_direction)} note={`of ${ready.windows_summary.n_windows} windows`} />
              </div>
              <p className="mt-2 tp-fine leading-relaxed text-slate-400">
                <span className="text-slate-200">What a p-value means:</span> if there were no real trend, how often chance alone would give a slope at
                least this steep. Below 0.05 (less than 1 time in 20) counts as statistically significant. It is not the chance that the trend is real,
                and it cannot tell whether the dataset itself is right.
              </p>
              {det?.years_needed != null && (
                <div className="mt-4">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>Years of data needed to detect a trend this size</span>
                    <span className="font-mono text-slate-200">≈ {Math.round(det.years_needed)} yr</span>
                  </div>
                  <div className="relative mt-1 h-2.5 rounded-full bg-slate-700">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, (det.record_years / Math.max(det.years_needed, det.record_years)) * 100)}%`,
                        background: det.record_years >= det.years_needed ? "#34d399" : COLORS.none,
                      }}
                    />
                  </div>
                  <p className="mt-1 tp-fine text-slate-400">
                    Record: {Number.isInteger(det.record_years) ? det.record_years : det.record_years.toFixed(1)} years. Plausible range {Math.round(det.low ?? 0)}–{Math.round(det.high ?? 0)} years (Weatherhead et al. 1998).
                  </p>
                </div>
              )}
              <p className="mt-4 border-t border-slate-700/60 pt-3 tp-fine leading-relaxed text-slate-400">
                A significant trend describes what changed in this dataset. It does not say why it changed.
              </p>
            </>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title="3 · The evidence: time series"
          sub="Monthly values have a strong seasonal cycle that hides slow change. Removing each calendar month's average leaves the anomaly, where a trend is visible."
        >
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
            <div className="inline-flex overflow-hidden rounded-md border border-slate-600" role="group" aria-label="Series view">
              {(["anomaly", "raw"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  aria-pressed={view === v}
                  className={`px-3 py-1.5 ${view === v ? "bg-sky-500/20 text-white" : "text-slate-300 hover:bg-slate-800"}`}
                >
                  {v === "anomaly" ? "Seasonal cycle removed" : "Raw monthly values"}
                </button>
              ))}
            </div>
            <label className="text-slate-400">
              From{" "}
              <select
                value={start}
                onChange={(e) => {
                  const s = Number(e.target.value);
                  setRange([s, Math.max(end, s + minYears - 1)]);
                }}
                className="rounded border border-slate-600 bg-slate-800 px-1.5 py-1 text-slate-100"
              >
                {years.filter((y) => y <= period[1] - minYears + 1).map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
            </label>
            <label className="text-slate-400">
              to{" "}
              <select
                value={end}
                onChange={(e) => {
                  const en = Number(e.target.value);
                  setRange([Math.min(start, en - minYears + 1), en]);
                }}
                className="rounded border border-slate-600 bg-slate-800 px-1.5 py-1 text-slate-100"
              >
                {years.filter((y) => y >= period[0] + minYears - 1).map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
            </label>
            {!isFull && (
              <button type="button" onClick={() => setRange(null)} className="text-sky-300 hover:underline">
                Reset to full record
              </button>
            )}
            <label className="text-slate-400">
              Compare with{" "}
              <select
                value={compareRegion ?? ""}
                onChange={(e) => {
                  const v = e.target.value || null;
                  setCompareRegion(v);
                  if (!v) setCompareAnalysis(null);
                  setCompareError(null);
                }}
                className="rounded border border-slate-600 bg-slate-800 px-1.5 py-1 text-slate-100"
                aria-label="Compare with another region"
              >
                <option value="">None</option>
                {catalog?.regions
                  .filter((r) => r.id !== region)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} — {r.country}
                    </option>
                  ))}
              </select>
            </label>
            <button type="button" onClick={downloadCsv} disabled={!ready} className="text-sky-300 hover:underline disabled:text-slate-500">
              Download data as CSV
            </button>
          </div>
          {compareError && (
            <p role="alert" className="mt-2 text-xs text-amber-200">
              Could not load the comparison region: {compareError}
            </p>
          )}
          {compareRegion && !compareReady && !compareError && <p className="mt-2 text-xs text-slate-400">Loading comparison…</p>}
          {seriesPlot && <Plot data={seriesPlot.data} layout={seriesPlot.layout} height={340} label={`Time series of ${ready?.variable.name} for ${ready?.region.name}`} />}
          {win && (
            <p className="text-xs leading-relaxed text-slate-300" aria-live="polite">
              <span className="font-medium text-white">
                {start}–{end}:
              </span>{" "}
              {compareReady && ready && <>{ready.region.name}: </>}
              {signed(win.slope_per_decade)} {units} per decade (95% range {signed(win.ci_low)} to {signed(win.ci_high)}), {pEq(win.p_value)} —{" "}
              {win.significant ? "statistically significant" : "not statistically significant"}.
              {compareReady && ready && secondOpinion(ready)}
              {compareReady && win2 && (
                <>
                  {" "}
                  {compareReady.region.name}: {signed(win2.slope_per_decade)} {units} per decade (95% range {signed(win2.ci_low)} to {signed(win2.ci_high)}), {pEq(win2.p_value)} —{" "}
                  {win2.significant ? "statistically significant" : "not statistically significant"}.
                  {secondOpinion(compareReady)}
                </>
              )}
              {compareReady && !win2 && <> {compareReady.region.name}: no trend can be computed for these years.</>}
              {oppositeDirections && ready && compareReady && win2 && (
                <>
                  {" "}
                  <span className="font-medium text-white">Opposite directions in this dataset:</span> {ready.variable.name} is{" "}
                  {win.slope_per_decade > 0 ? "rising" : "falling"} in {ready.region.name} and {win2.slope_per_decade > 0 ? "rising" : "falling"} in{" "}
                  {compareReady.region.name}
                  {win.significant && win2.significant
                    ? "; both trends are statistically significant here."
                    : win.significant || win2.significant
                      ? "; only one of the two is statistically significant."
                      : "; neither is statistically significant, so the difference may be chance."}
                  {weaklySupported(ready) || weaklySupported(compareReady)
                    ? " An independent dataset does not fully back both trends (see each second opinion), so do not treat this contrast as established."
                    : !ready.crosscheck || ready.crosscheck.code === "none"
                      ? " No second dataset was checked for this variable, so the contrast rests on one dataset."
                      : ""}
                </>
              )}
              {compareReady &&
                (view === "anomaly"
                  ? " On the chart, thin lines are monthly values and shaded bands show the 95% range of each slope."
                  : " On the chart, the thin line is the monthly value for the first region.")}
              {!isFull && " Custom date ranges use the persistence-adjusted t-test; the verdict card always describes the full record."}
            </p>
          )}
        </Card>

        <Card
          className="lg:col-span-2"
          title="4 · Did you just pick good dates?"
          sub={`Each square is one choice of start and end year (${minYears}+ years). Colour is the trend; × marks windows that are not significant. If the picture is one colour, the trend does not depend on the dates. Click a square to test that window.`}
        >
          {heatPlot && (
            <Plot
              data={heatPlot.data}
              layout={heatPlot.layout}
              height={360}
              label="Heat map of trend for every start and end year"
              onPointClick={(p) => {
                if (p && typeof p.x === "number" && typeof p.y === "number" && p.x - p.y + 1 >= minYears) setRange([p.y, p.x]);
              }}
            />
          )}
          {ready && (
            <p className="text-xs leading-relaxed text-slate-300">
              {pct(ready.windows_summary.share_significant_same_direction)} of windows show a significant trend in the same direction as the full record,{" "}
              {pct(ready.windows_summary.share_significant_opposite_direction)} a significant trend in the opposite direction. Slopes range from{" "}
              {signed(ready.windows_summary.slope_min)} to {signed(ready.windows_summary.slope_max)} {units} per decade.
            </p>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title={`5 · Where is ${overview?.variable.name.toLowerCase() ?? "it"} changing?`}
          sub="Full-record trend and 95% confidence range for every region. A range that crosses zero is not significant. Click a point to open that region."
        >
          {forestPlot && (
            <Plot
              data={forestPlot.data}
              layout={forestPlot.layout}
              height={330}
              label="Trend and confidence interval for each region"
              onPointClick={(p) => p?.customdata && pick(String(p.customdata), variable)}
            />
          )}
          {overview && (
            <p className="text-xs leading-relaxed text-slate-300">
              Testing {overview.multiple_testing.n_tests} regions at once makes a chance &ldquo;discovery&rdquo; more likely.{" "}
              {overview.multiple_testing.n_significant_raw} pass the t-test on their own; {overview.multiple_testing.n_significant_fdr} remain after a
              false-discovery-rate correction (Benjamini–Hochberg).
            </p>
          )}
        </Card>

        <Card className="lg:col-span-2" title="6 · Data quality and provenance">
          {ready && (
            <div id="data">
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {[
                  ["Dataset", source?.short_name ?? "NASA MERRA-2 reanalysis"],
                  ["Accessed through", `${source?.access_short ?? "NASA POWER API"} ${ready.provenance.api_version ?? ""}`.trim()],
                  ["Grid cells averaged", `${ready.quality.grid_cells} (area-weighted)`],
                  ["Native grid", ready.provenance.source.native_grid],
                  ...(ready.region.land_share != null
                    ? [
                        [
                          "Land in the region box",
                          ready.region.land_share > 0.995
                            ? "all land"
                            : `${pct(ready.region.land_share)}; ${landOnly ? "only land is averaged" : "sea is included in this average"}`,
                        ],
                      ]
                    : []),
                  // Fields added later are optional here: a browser may briefly hold an older cached JSON after a deploy.
                  ...(ready.first_month && ready.last_month ? [["Record", `${ready.first_month} to ${ready.last_month}`]] : []),
                  ["Months with data", `${ready.quality.months_total - ready.quality.months_missing} of ${ready.quality.months_total} (${pct(ready.quality.coverage)})`],
                  ...(excludedMonths.length
                    ? [["Calendar months left out", `${excludedMonths.map((m) => MONTHS[m - 1]).join(", ")} (data in too few years)`]]
                    : []),
                  ["Units reported by NASA", ready.quality.units_reported_by_nasa],
                  ["Month-to-month persistence", `r₁ = ${sig(ready.quality.lag1_autocorrelation, 2)}`],
                  ["Effective sample size", `${Math.round(ready.quality.n_effective)} of ${ready.quality.months_used ?? ready.quality.months_total} months`],
                  ["Retrieved (UTC)", ready.provenance.retrieved_utc ? ready.provenance.retrieved_utc.replace("T", " ").slice(0, 16) : "not recorded"],
                  ["Served from", DATA_MODE],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-slate-400">{k}</dt>
                    <dd className="text-slate-100">{v}</dd>
                  </div>
                ))}
              </dl>
              {ready.provenance.request_url ? (
                <a className="mt-3 inline-block break-all text-xs text-sky-300 hover:underline" href={ready.provenance.request_url}>
                  Exact NASA POWER request for this series ↗
                </a>
              ) : (
                source?.access_url && (
                  <a className="mt-3 inline-block break-all text-xs text-sky-300 hover:underline" href={source.access_url}>
                    NASA record for this dataset ↗
                  </a>
                )
              )}
              <p className="mt-3 rounded-md border border-amber-400/30 bg-amber-400/5 p-2 tp-fine leading-relaxed text-amber-100/90">
                {source?.caveat ??
                  "MERRA-2 is a reanalysis: a model constrained by satellite and ground observations, not a direct measurement. Changes in the observing system over time (new satellites, fewer rain gauges) can create or hide trends, especially for precipitation and soil wetness. Check important results against an independent dataset."}
              </p>
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-4" title="How TerraPulse decides">
        <div id="method" className="mt-3 grid gap-4 text-xs leading-relaxed text-slate-300 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <h3 className="font-medium text-white">Remove the seasons</h3>
            <p className="mt-1">Each month is compared with the {period[0]}–{period[1]} average for that calendar month, so January is only compared with other Januaries.</p>
          </div>
          <div>
            <h3 className="font-medium text-white">Measure the slope two ways</h3>
            <p className="mt-1">A least-squares line gives the rate of change. Sen&rsquo;s slope, the median of all pairwise slopes, checks that a few extreme months are not driving it.</p>
          </div>
          <div>
            <h3 className="font-medium text-white">Test it honestly</h3>
            <p className="mt-1">A warm month tends to follow a warm month, so {ready?.quality.months_used ?? 540} months hold less independent information than they seem to. Both the t-test and the Mann–Kendall test are corrected for this persistence.</p>
          </div>
          <div>
            <h3 className="font-medium text-white">Try to break it</h3>
            <p className="mt-1">The trend is recomputed for all {ready?.windows_summary.n_windows ?? 496} start/end-year windows, and across regions with a false-discovery correction. Where nothing is detected, we estimate how long a record would be needed. For rainfall and temperature the same trend is also computed from an independent record, and the verdict says whether the two agree.</p>
          </div>
        </div>
        <p className="mt-4 text-xs leading-relaxed text-slate-300">
          <span className="font-medium text-white">Detected is not validated.</span> A verdict says a trend is statistically detectable in one
          dataset. Saying the environment really changed by that amount needs more: an independent record that agrees, and a check for known
          problems in how the data were made. In the south-western Amazon both rainfall records fall, but a documented 2005 change in the rain
          gauges behind MERRA-2 accounts for much of its faster rate. TerraPulse never says why a trend happened.
        </p>
        <p className="mt-4 text-xs text-slate-400">
          Full methodology, formulas, tests and limitations:{" "}
          <a className="text-sky-300 hover:underline" href={`${REPO}/blob/main/docs/METHODOLOGY.md`}>docs/METHODOLOGY.md</a>.
        </p>
      </Card>

      <footer className="mt-8 text-center tp-fine leading-relaxed text-slate-500">
        TerraPulse · Team Orbital Alpha · NASA Space Apps Challenge 2026 · MIT License. Data: {credits}; second opinions: GPCP v2.3 and NASA GISTEMP v4 via NOAA PSL; imagery: NASA GIBS.
        Built with SI coding assistance (Anthropic Claude); see the repository for the full disclosure. Not an official NASA product.
      </footer>
    </div>
  );
}
