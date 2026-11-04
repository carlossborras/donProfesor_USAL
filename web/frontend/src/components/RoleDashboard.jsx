import React, { useCallback, useEffect, useState } from "react";
import { fetchRoleDashboard } from "../services/api.js";
import {
  BarChart,
  ChartCard,
  GroupedBarChart,
  HorizontalBars,
  ScatterChart,
  formatValue,
} from "./charts/Charts.jsx";

/* ==========================================================================
   PANEL CON GRÁFICOS POR ROL («Cómo vamos»)
   Los datos llegan ya filtrados por el ámbito del token (GET /api/dashboard).
   ========================================================================== */

const TITULOS = {
  docente: "Cómo va tu grupo.",
  director: "Cómo va tu escuela.",
  delegado: "Cómo va tu UGEL.",
};

function describeScope(rol, scope = {}) {
  if (rol === "docente") return `${scope.grado_secundaria ?? "?"}.º de secundaria · ${scope.escuela_id ?? "sin escuela"}`;
  if (rol === "director") return `Escuela ${scope.escuela_id ?? "sin asignar"} · agregado por grados`;
  return `${scope.ugel ?? "UGEL sin asignar"} · agregado por escuelas`;
}

function KpiRow({ kpis = [] }) {
  if (!kpis.length) return null;
  return (
    <div className="kpi-calm-grid">
      {kpis.map((k) => (
        <div className="kpi-calm-card" key={k.id}>
          <div className="kpi-calm-label">{k.label}</div>
          <div className="kpi-calm-value">{typeof k.value === "string" ? k.value : formatValue(k.value, k.unit)}</div>
          {k.note && <div className="kpi-calm-context">{k.note}</div>}
        </div>
      ))}
    </div>
  );
}

/* ----------------------------- DOCENTE ---------------------------------- */

function DocentePanel({ data }) {
  const c = data.charts || {};
  const alumnos = data.tablas?.alumnos || [];
  const [soloRevision, setSoloRevision] = useState(false);
  const visibles = soloRevision ? alumnos.filter((a) => a.sugerir_revision) : alumnos;
  const isEmpty = (arr) => !arr || arr.every((d) => !d.value);

  return (
    <>
      <div className="dash-grid">
        <ChartCard title="Notas medias por trimestre" subtitle="Escala 0–20 · la línea marca el aprobado (11)">
          <BarChart data={c.notas_por_trimestre || []} max={20} refLine={data.nota_aprobatoria} refLabel="Aprobado" unit="" />
        </ChartCard>
        <ChartCard title="Faltas medias por estudiante" subtitle="Comparación entre trimestres">
          <BarChart data={c.faltas_por_trimestre || []} unit=" d" color="#c08a3e" />
        </ChartCard>
        <ChartCard title="¿Cómo se reparte la asistencia?" subtitle="Número de estudiantes por tramo" empty={isEmpty(c.distribucion_asistencia)}>
          <BarChart data={c.distribucion_asistencia || []} decimals={0} color="#3e7b67" />
        </ChartCard>
        <ChartCard title="¿Cómo se reparten las notas?" subtitle="Número de estudiantes por tramo de promedio" empty={isEmpty(c.distribucion_notas)}>
          <BarChart data={c.distribucion_notas || []} decimals={0} color="#6f8f86" />
        </ChartCard>
        <ChartCard
          title="Asistencia y distancia a la escuela"
          subtitle="Cada punto es un estudiante (sin nombre)"
          empty={!(c.asistencia_vs_distancia || []).length}
        >
          <ScatterChart points={c.asistencia_vs_distancia || []} xLabel="Distancia hogar–escuela (km)" yLabel="Asistencia (%)" yMax={100} xUnit=" km" yUnit=" %" />
        </ChartCard>
        <ChartCard title="Contexto de tu grupo" subtitle="Número de estudiantes en cada situación" empty={isEmpty(c.contexto)}>
          <HorizontalBars data={c.contexto || []} decimals={0} />
        </ChartCard>
      </div>

      <div className="calm-card">
        <div className="calm-card-header">
          <div>
            <div className="calm-card-title">Tu grupo, estudiante a estudiante</div>
            <div className="calm-card-sub">Ordenado por código: sin rankings ni semáforos.</div>
          </div>
          <label className="dash-toggle">
            <input type="checkbox" checked={soloRevision} onChange={(e) => setSoloRevision(e.target.checked)} />
            Solo sugerencias de revisión
          </label>
        </div>
        <div className="dash-table-wrap">
          <table className="dash-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Asistencia</th>
                <th>Faltas T1 → T2</th>
                <th>Nota T1 → T2</th>
                <th>Promedio</th>
                <th>Sugerencia</th>
                <th>Factores a tener en cuenta</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((a) => (
                <tr key={a.alumno_id}>
                  <td className="mono">{a.alumno_id}</td>
                  <td>{formatValue(a.asistencia_pct, " %")}</td>
                  <td>{formatValue(a.faltas_t1, "", 0)} → {formatValue(a.faltas_t2, "", 0)}</td>
                  <td>{formatValue(a.nota_t1)} → {formatValue(a.nota_t2)}</td>
                  <td>{formatValue(a.promedio)}</td>
                  <td>{a.sugerir_revision ? <span className="tag-review">Sugerir revisión</span> : <span className="muted">—</span>}</td>
                  <td>
                    {a.factores?.length ? (
                      <ul className="factor-list">
                        {a.factores.map((f) => <li key={f}>{f}</li>)}
                      </ul>
                    ) : (
                      <span className="muted">—</span>
                    )}
                    {a.recomendacion && <div className="factor-reco">Idea: {a.recomendacion}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ----------------------------- DIRECTOR --------------------------------- */

function DirectorPanel({ data }) {
  const c = data.charts || {};
  const grados = data.tablas?.grados || [];
  const ocultos = data.tablas?.grados_ocultos || [];
  const sinGrados = !grados.length;

  return (
    <>
      <div className="dash-grid">
        <ChartCard title="Asistencia media por grado" subtitle="Porcentaje" empty={sinGrados}>
          <BarChart data={c.asistencia_por_grado || []} max={100} unit=" %" />
        </ChartCard>
        <ChartCard title="Notas medias por grado" subtitle="1.er vs 2.º trimestre · aprobado en 11" empty={sinGrados}>
          <GroupedBarChart categories={c.notas_por_grado?.categorias || []} series={c.notas_por_grado?.series || []} max={20} refLine={data.nota_aprobatoria} refLabel="Aprobado" />
        </ChartCard>
        <ChartCard title="Faltas medias por grado" subtitle="Un salto en el 2.º trimestre puede coincidir con la cosecha" empty={sinGrados}>
          <GroupedBarChart categories={c.faltas_por_grado?.categorias || []} series={c.faltas_por_grado?.series || []} unit=" d" />
        </ChartCard>
        <ChartCard title="Sugerencias de revisión por grado" subtitle="Para coordinar apoyos con cada tutor/a" empty={sinGrados}>
          <BarChart data={c.revision_por_grado || []} decimals={0} color="#c08a3e" />
        </ChartCard>
        <ChartCard title="Internet en casa por grado" subtitle="Porcentaje de estudiantes" empty={sinGrados}>
          <BarChart data={c.internet_por_grado || []} max={100} unit=" %" color="#6f8f86" />
        </ChartCard>
      </div>

      <div className="calm-card">
        <div className="calm-card-title">Resumen por grado</div>
        <div className="calm-card-sub">Solo grados con {data.k_minimo} o más estudiantes.</div>
        <div className="dash-table-wrap">
          <table className="dash-table">
            <thead>
              <tr>
                <th>Grado</th><th>Estudiantes</th><th>Asistencia</th><th>Nota T1 → T2</th>
                <th>Aprobados</th><th>Internet</th><th>Sugerencias</th><th>Juntos</th>
              </tr>
            </thead>
            <tbody>
              {grados.map((g) => (
                <tr key={g.grado}>
                  <td>{g.label}</td>
                  <td>{g.n}</td>
                  <td>{formatValue(g.asistencia_pct, " %")}</td>
                  <td>{formatValue(g.nota_t1)} → {formatValue(g.nota_t2)}</td>
                  <td>{formatValue(g.aprobados_pct, " %")}</td>
                  <td>{formatValue(g.internet_pct, " %")}</td>
                  <td>{g.revision}</td>
                  <td>{g.juntos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {ocultos.length > 0 && (
          <div className="dash-note">
            Grados ocultos por tener menos de {data.k_minimo} estudiantes: {ocultos.map((o) => o.label).join(", ")}.
          </div>
        )}
      </div>
    </>
  );
}

/* ----------------------------- DELEGADO --------------------------------- */

function DelegadoPanel({ data }) {
  const c = data.charts || {};
  const escuelas = data.tablas?.escuelas || [];
  const ocultas = data.tablas?.escuelas_ocultas || [];
  const brechas = data.tablas?.brechas || [];
  const sinEscuelas = !escuelas.length;

  return (
    <>
      <div className="dash-grid">
        <ChartCard title="Asistencia media por escuela" subtitle="Porcentaje" empty={sinEscuelas}>
          <BarChart data={c.asistencia_por_escuela || []} max={100} unit=" %" />
        </ChartCard>
        <ChartCard title="Internet en casa por escuela" subtitle="La línea marca el umbral de brecha (50 %)" empty={sinEscuelas}>
          <BarChart data={c.internet_por_escuela || []} max={100} unit=" %" refLine={50} refLabel="Brecha" color="#6f8f86" />
        </ChartCard>
        <ChartCard title="Rural y urbana" subtitle="Asistencia e internet en casa (%)" empty={!(c.comparativa_zonas?.series || []).length}>
          <GroupedBarChart categories={c.comparativa_zonas?.categorias || []} series={c.comparativa_zonas?.series || []} max={100} unit=" %" />
        </ChartCard>
        <ChartCard title="Sugerencias de revisión por escuela" subtitle="Para orientar el acompañamiento territorial" empty={sinEscuelas}>
          <BarChart data={c.revision_por_escuela || []} decimals={0} color="#c08a3e" />
        </ChartCard>
      </div>

      <div className="calm-card">
        <div className="calm-card-title">Escuelas con brechas</div>
        <div className="calm-card-sub">Menos del 50 % con internet en casa o distancia media mayor de 3 km.</div>
        {brechas.length === 0 ? (
          <div className="chart-empty">Ninguna escuela supera los umbrales de brecha.</div>
        ) : (
          <ul className="gap-list">
            {brechas.map((e) => (
              <li key={e.escuela_id}>
                <strong>{e.escuela_id}</strong> · {e.distrito} ({e.zona}) — {e.brechas.join(" · ")}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="calm-card">
        <div className="calm-card-title">Resumen por escuela</div>
        <div className="calm-card-sub">Solo escuelas con {data.k_minimo} o más estudiantes.</div>
        <div className="dash-table-wrap">
          <table className="dash-table">
            <thead>
              <tr>
                <th>Escuela</th><th>Distrito</th><th>Zona</th><th>Estudiantes</th><th>Asistencia</th>
                <th>Nota media</th><th>Internet</th><th>Distancia media</th><th>Sugerencias</th><th>Juntos</th>
              </tr>
            </thead>
            <tbody>
              {escuelas.map((e) => (
                <tr key={e.escuela_id}>
                  <td className="mono">{e.escuela_id}</td>
                  <td>{e.distrito}</td>
                  <td>{e.zona}</td>
                  <td>{e.n}</td>
                  <td>{formatValue(e.asistencia_pct, " %")}</td>
                  <td>{formatValue(e.promedio)}</td>
                  <td>{formatValue(e.internet_pct, " %")}</td>
                  <td>{formatValue(e.distancia_km, " km", 2)}</td>
                  <td>{e.revision}</td>
                  <td>{e.juntos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {ocultas.length > 0 && (
          <div className="dash-note">
            {ocultas.length} escuela(s) ocultas por tener menos de {data.k_minimo} estudiantes.
          </div>
        )}
      </div>
    </>
  );
}

/* ----------------------------- CONTENEDOR ------------------------------- */

export function RoleDashboard({ token, role, onUnauthorized, refreshKey = 0 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchRoleDashboard(token));
    } catch (err) {
      if (err.status === 401 && onUnauthorized) {
        onUnauthorized();
        return;
      }
      setError(err.message || "No se pudo cargar el panel.");
    } finally {
      setLoading(false);
    }
  }, [token, onUnauthorized]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const rol = data?.rol || role;

  return (
    <main className="edusight-content">
      <div className="section-kicker">PANORAMA · {describeScope(rol, data?.scope)}</div>
      <h1 className="hero-serif-title">{TITULOS[rol] || "Cómo vamos."}</h1>
      <p className="hero-subtitle">{data?.aviso || "Indicadores calculados con los datos de tu ámbito."}</p>

      {loading && <div className="calm-card chart-empty">Cargando tu panel…</div>}
      {error && (
        <div className="calm-card auth-error" role="alert">
          {error}{" "}
          <button type="button" className="btn-outline-calm" onClick={load}>Reintentar</button>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <KpiRow kpis={data.kpis} />
          {!data.hay_datos ? (
            <div className="calm-card chart-empty">
              {data.mensaje || "Todavía no hay datos para tu ámbito."} Cuando se carguen los datos, verás aquí tus gráficos.
            </div>
          ) : (
            <>
              {rol === "docente" && <DocentePanel data={data} />}
              {rol === "director" && <DirectorPanel data={data} />}
              {rol === "delegado" && <DelegadoPanel data={data} />}
            </>
          )}
        </>
      )}
    </main>
  );
}
