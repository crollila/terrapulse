"use client";

import { useEffect, useRef } from "react";
import { COLORS } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Props = {
  data: any[];
  layout?: Record<string, any>;
  onPointClick?: (point: any) => void;
  height?: number;
  label: string;
};

const BASE_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: COLORS.ink, family: "inherit", size: 12 },
  margin: { l: 56, r: 16, t: 12, b: 44 },
  hoverlabel: { bgcolor: "#0f172a", bordercolor: "#334155", font: { color: "#e2e8f0" } },
  legend: { orientation: "h", y: 1.12, x: 0, font: { size: 11 } },
  xaxis: { gridcolor: COLORS.grid, zerolinecolor: COLORS.grid },
  yaxis: { gridcolor: COLORS.grid, zerolinecolor: "rgba(148,163,184,0.45)" },
};

function merge(a: Record<string, any>, b: Record<string, any> = {}) {
  const out: Record<string, any> = { ...a, ...b };
  for (const k of ["xaxis", "yaxis", "legend", "margin"]) out[k] = { ...a[k], ...(b[k] ?? {}) };
  return out;
}

/** Thin Plotly wrapper. `data` and `layout` must be memoised by the caller. */
export default function Plot({ data, layout, onPointClick, height = 320, label }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const clickRef = useRef(onPointClick);

  useEffect(() => {
    clickRef.current = onPointClick;
  }, [onPointClick]);

  useEffect(() => {
    let cancelled = false;
    import("plotly.js-dist-min").then((mod: any) => {
      const Plotly = mod.default ?? mod;
      const el = ref.current as any;
      if (cancelled || !el) return;
      // On touch screens a finger dragged across a chart would draw a zoom box and block page
      // scrolling. Turn dragging off there; taps still show values and select points.
      const touch = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;
      Plotly.react(el, data, merge(BASE_LAYOUT, { ...layout, height, ...(touch ? { dragmode: false } : {}) }), {
        displaylogo: false,
        responsive: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
      }).then(() => {
        el.removeAllListeners?.("plotly_click");
        el.on?.("plotly_click", (ev: any) => clickRef.current?.(ev.points?.[0]));
      });
    });
    return () => {
      cancelled = true;
    };
  }, [data, layout, height]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      import("plotly.js-dist-min").then((mod: any) => el && (mod.default ?? mod).purge(el));
    };
  }, []);

  return <div ref={ref} role="img" aria-label={label} style={{ minHeight: height }} className="w-full" />;
}
