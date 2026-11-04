import React from "react";

/* ==========================================================================
   GRÁFICOS SVG LIGEROS (sin dependencias nuevas)
   Paleta y tipografía del diseño EduSight. Todos aceptan datos vacíos.
   ========================================================================== */

export const CHART_COLORS = ["#1f6351", "#c08a3e", "#6f8f86", "#9b5d4a", "#3e7b67"];

const fmt = (v, unit = "", dec = 1) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  const txt = Number.isInteger(n) ? String(n) : n.toFixed(dec).replace(".", ",");
  return `${txt}${unit}`;
};

const niceMax = (values, fallback = 1) => {
  const max = Math.max(0, ...values.filter((v) => v !== null && v !== undefined).map(Number));
  if (max <= 0) return fallback;
  const pow = 10 ** Math.floor(Math.log10(max));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (max <= step * pow) return step * pow;
  }
  return 10 * pow;
};

export function ChartCard({ title, subtitle, children, empty, emptyText = "Sin datos todavía." }) {
  return (
    <div className="calm-card chart-card">
      <div className="chart-card-head">
        <div className="calm-card-title">{title}</div>
        {subtitle && <div className="calm-card-sub">{subtitle}</div>}
      </div>
      {empty ? <div className="chart-empty">{emptyText}</div> : children}
    </div>
  );
}

/** Barras verticales. data = [{label, value}] */
export function BarChart({ data = [], unit = "", max, refLine, refLabel, color = CHART_COLORS[0], height = 220, decimals = 1 }) {
  const W = 520;
  const H = height;
  const pad = { top: 18, right: 12, bottom: 34, left: 40 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const top = max ?? niceMax([...data.map((d) => d.value), refLine ?? 0]);
  const slot = innerW / Math.max(1, data.length);
  const barW = Math.min(56, slot * 0.6);
  const y = (v) => pad.top + innerH - (Math.max(0, Number(v) || 0) / top) * innerH;
  const ticks = [0, top / 2, top];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Gráfico de barras">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="chart-grid" />
          <text x={pad.left - 6} y={y(t) + 4} className="chart-axis" textAnchor="end">{fmt(t, "", 0)}</text>
        </g>
      ))}
      {data.map((d, i) => {
        const cx = pad.left + slot * i + slot / 2;
        const hasValue = d.value !== null && d.value !== undefined;
        return (
          <g key={d.label}>
            {hasValue && (
              <rect x={cx - barW / 2} y={y(d.value)} width={barW} height={pad.top + innerH - y(d.value)} rx="3" fill={d.color || color}>
                <title>{`${d.label}: ${fmt(d.value, unit, decimals)}`}</title>
              </rect>
            )}
            <text x={cx} y={(hasValue ? y(d.value) : pad.top + innerH) - 6} className="chart-value" textAnchor="middle">
              {fmt(d.value, unit, decimals)}
            </text>
            <text x={cx} y={H - 12} className="chart-axis" textAnchor="middle">{d.label}</text>
          </g>
        );
      })}
      {refLine !== undefined && refLine !== null && (
        <g>
          <line x1={pad.left} x2={W - pad.right} y1={y(refLine)} y2={y(refLine)} className="chart-ref" />
          {refLabel && (
            <text x={W - pad.right} y={y(refLine) - 5} className="chart-ref-label" textAnchor="end">{refLabel}</text>
          )}
        </g>
      )}
    </svg>
  );
}

/** Barras agrupadas. categories = ["1.º", ...]; series = [{name, values: [...]}] */
export function GroupedBarChart({ categories = [], series = [], unit = "", max, refLine, refLabel, height = 240, decimals = 1 }) {
  const W = 520;
  const H = height;
  const pad = { top: 18, right: 12, bottom: 34, left: 40 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const all = series.flatMap((s) => s.values || []);
  const top = max ?? niceMax([...all, refLine ?? 0]);
  const slot = innerW / Math.max(1, categories.length);
  const groupW = Math.min(120, slot * 0.75);
  const barW = groupW / Math.max(1, series.length);
  const y = (v) => pad.top + innerH - (Math.max(0, Number(v) || 0) / top) * innerH;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Gráfico de barras agrupadas">
        {[0, top / 2, top].map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="chart-grid" />
            <text x={pad.left - 6} y={y(t) + 4} className="chart-axis" textAnchor="end">{fmt(t, "", 0)}</text>
          </g>
        ))}
        {categories.map((cat, ci) => {
          const gx = pad.left + slot * ci + (slot - groupW) / 2;
          return (
            <g key={cat}>
              {series.map((s, si) => {
                const v = (s.values || [])[ci];
                if (v === null || v === undefined) return null;
                return (
                  <rect key={s.name} x={gx + barW * si + 1} y={y(v)} width={barW - 2} height={pad.top + innerH - y(v)} rx="2" fill={s.color || CHART_COLORS[si % CHART_COLORS.length]}>
                    <title>{`${cat} · ${s.name}: ${fmt(v, unit, decimals)}`}</title>
                  </rect>
                );
              })}
              <text x={gx + groupW / 2} y={H - 12} className="chart-axis" textAnchor="middle">{cat}</text>
            </g>
          );
        })}
        {refLine !== undefined && refLine !== null && (
          <g>
            <line x1={pad.left} x2={W - pad.right} y1={y(refLine)} y2={y(refLine)} className="chart-ref" />
            {refLabel && <text x={W - pad.right} y={y(refLine) - 5} className="chart-ref-label" textAnchor="end">{refLabel}</text>}
          </g>
        )}
      </svg>
      <ChartLegend items={series.map((s, i) => ({ label: s.name, color: s.color || CHART_COLORS[i % CHART_COLORS.length] }))} />
    </div>
  );
}

/** Barras horizontales (para conteos con etiquetas largas). data = [{label, value}] */
export function HorizontalBars({ data = [], unit = "", max, color = CHART_COLORS[0], decimals = 1 }) {
  const top = max ?? niceMax(data.map((d) => d.value));
  return (
    <div className="hbars">
      {data.map((d) => {
        const pct = Math.max(0, Math.min(100, ((Number(d.value) || 0) / top) * 100));
        return (
          <div className="hbar-row" key={d.label}>
            <div className="hbar-label">{d.label}</div>
            <div className="hbar-track">
              <div className="hbar-fill" style={{ width: `${pct}%`, background: d.color || color }} />
            </div>
            <div className="hbar-value">{fmt(d.value, unit, decimals)}</div>
          </div>
        );
      })}
    </div>
  );
}

/** Dispersión. points = [{x, y}] */
export function ScatterChart({ points = [], xLabel = "", yLabel = "", xMax, yMax, xUnit = "", yUnit = "", height = 240 }) {
  const W = 520;
  const H = height;
  const pad = { top: 14, right: 16, bottom: 40, left: 44 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const mx = xMax ?? niceMax(points.map((p) => p.x));
  const my = yMax ?? niceMax(points.map((p) => p.y));
  const sx = (v) => pad.left + (Math.max(0, Number(v) || 0) / mx) * innerW;
  const sy = (v) => pad.top + innerH - (Math.max(0, Number(v) || 0) / my) * innerH;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Gráfico de dispersión">
      {[0, my / 2, my].map((t) => (
        <g key={`y${t}`}>
          <line x1={pad.left} x2={W - pad.right} y1={sy(t)} y2={sy(t)} className="chart-grid" />
          <text x={pad.left - 6} y={sy(t) + 4} className="chart-axis" textAnchor="end">{fmt(t, "", 0)}</text>
        </g>
      ))}
      {[0, mx / 2, mx].map((t) => (
        <text key={`x${t}`} x={sx(t)} y={pad.top + innerH + 16} className="chart-axis" textAnchor="middle">{fmt(t, "", 1)}</text>
      ))}
      {points.map((p, i) => (
        <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="5" className="chart-dot">
          <title>{`${fmt(p.x, xUnit, 1)} · ${fmt(p.y, yUnit, 1)}`}</title>
        </circle>
      ))}
      <text x={pad.left + innerW / 2} y={H - 4} className="chart-axis-title" textAnchor="middle">{xLabel}</text>
      <text x={12} y={pad.top + innerH / 2} className="chart-axis-title" textAnchor="middle" transform={`rotate(-90 12 ${pad.top + innerH / 2})`}>
        {yLabel}
      </text>
    </svg>
  );
}

export function ChartLegend({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="chart-legend">
      {items.map((it) => (
        <span key={it.label} className="chart-legend-item">
          <span className="chart-legend-swatch" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

export { fmt as formatValue };
