import React, { useCallback, useEffect, useState } from "react";
import { fetchPredictionsApi, recalculatePredictionsApi } from "../services/api.js";
import { BarChart, ChartCard, GroupedBarChart, HorizontalBars, formatValue } from "./charts/Charts.jsx";

/* ==========================================================================
   PESTAÑA «PREDICCIONES»
   Todo sale de GET /api/predicciones (modelo LightGBM + Random Forest del equipo), ya filtrado
   por el ámbito del token. Las secciones llegan ordenadas por el interés de cada rol:
   las de interés alto van arriba y destacadas; las de interés bajo, al final y compactas.
   El docente ve niveles por estudiante (alto/medio/bajo), nunca porcentajes individuales.
   ========================================================================== */

const TITULOS = {
  docente: "Qué prevé el modelo para tu clase.",
  director: "Qué prevé el modelo para tu escuela.",
  delegado: "Qué prevé el modelo para tu UGEL.",
};

const NIVEL_TXT = { alto: "Alto", medio: "Medio", bajo: "Bajo", alta: "Alta", media: "Media", baja: "Baja" };

function Nivel({ valor }) {
  if (!valor) return <span className="muted">—</span>;
  return <span className={`nivel-badge nivel-${valor}`}>{NIVEL_TXT[valor] || valor}</span>;
}

function grafico(seccion, notaAprobatoria) {
  const s = seccion;
  if (s.niveles) {
    return (
      <BarChart
        data={[
          { label: "Alto", value: s.niveles.alto },
          { label: "Medio", value: s.niveles.medio },
          { label: "Bajo", value: s.niveles.bajo },
        ]}
        decimals={0}
        color="#9b5d4a"
        height={180}
      />
    );
  }
  if (s.clases) {
    return (
      <BarChart
        data={[
          { label: "Alta", value: s.clases.Alta },
          { label: "Media", value: s.clases.Media },
          { label: "Baja", value: s.clases.Baja },
        ]}
        decimals={0}
        color="#1f6351"
        height={180}
      />
    );
  }
  if (s.previstas) {
    const esNota = s.id === "notas";
    return (
      <GroupedBarChart
        categories={["1.er trim.", "2.º trim.", "3.er trim."]}
        series={[
          { name: "Real", values: [s.reales?.t1, s.reales?.t2, null], color: "#6f8f86" },
          { name: "Prevista por perfil", values: [s.previstas.t1, s.previstas.t2, s.previstas.t3], color: esNota ? "#1f6351" : "#c08a3e" },
        ]}
        max={esNota ? 20 : undefined}
        refLine={esNota ? notaAprobatoria : undefined}
        refLabel={esNota ? "Aprobado" : undefined}
        height={200}
      />
    );
  }
  return null;
}

function Seccion({ s, notaAprobatoria }) {
  const compacta = s.interes === "baja";
  if (compacta) {
    return (
      <div className="pred-compacta">
        <div className="pred-compacta-title">{s.titulo}</div>
        {(s.frases || []).map((f, i) => (
          <div key={i} className="pred-compacta-text">{f}</div>
        ))}
        {!s.frases?.length && <div className="muted">Sin datos.</div>}
      </div>
    );
  }
  return (
    <div className={`calm-card pred-card pred-${s.interes}`}>
      <div className="pred-card-head">
        <div className="calm-card-title">{s.titulo}</div>
        {s.interes === "alta" && <span className="pred-interes">Prioritario para ti</span>}
      </div>
      {(s.frases || []).map((f, i) => (
        <p key={i} className={i === 0 ? "pred-frase-principal" : "pred-frase"}>{f}</p>
      ))}
      {!s.frases?.length && <p className="muted">Sin datos suficientes.</p>}
      {s.interes === "alta" && grafico(s, notaAprobatoria)}
    </div>
  );
}

function TablaDocente({ alumnos = [] }) {
  const [soloRevision, setSoloRevision] = useState(false);
  const visibles = soloRevision ? alumnos.filter((a) => a.sugerir_revision) : alumnos;
  return (
    <div className="calm-card">
      <div className="calm-card-header">
        <div>
          <div className="calm-card-title">Tu clase, estudiante a estudiante</div>
          <div className="calm-card-sub">
            Niveles orientativos (sin porcentajes), ordenados por código: no es un ranking. Las previsiones salen del perfil
            de matrícula de cada estudiante (distancia, familia, trabajo…); el modelo no usa sus notas ni faltas reales.
          </div>
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
              <th>Necesidad de intervención</th>
              <th>Desánimo</th>
              <th>Notas reales T1 y T2</th>
              <th>Nota T3 prevista por perfil</th>
              <th>Faltas T3 previstas por perfil</th>
              <th>Abandono</th>
              <th>Repetición</th>
              <th className="col-baja">Pérdida de beca</th>
              <th>Qué puede estar influyendo</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((a) => (
              <tr key={a.alumno_id}>
                <td className="mono">{a.alumno_id}</td>
                {a.prediccion_pendiente ? (
                  <td colSpan={8} className="muted">Predicción pendiente (el modelo no estaba disponible al guardarlo).</td>
                ) : (
                  <>
                    <td><Nivel valor={a.necesidad} /></td>
                    <td><Nivel valor={a.desanimo} /></td>
                    <td>
                      {a.nota_t1 === null && a.nota_t2 === null ? (
                        <span className="muted">Sin notas aún</span>
                      ) : (
                        <>{formatValue(a.nota_t1)} · {formatValue(a.nota_t2)}</>
                      )}
                    </td>
                    <td><strong>{formatValue(a.nota_t3_prevista)}</strong></td>
                    <td>{formatValue(a.faltas_t3_previstas, "", 0)}</td>
                    <td><Nivel valor={a.abandono} /></td>
                    <td><Nivel valor={a.repeticion} /></td>
                    <td className="col-baja">{a.beca ? <Nivel valor={a.beca} /> : <span className="muted">No aplica</span>}</td>
                  </>
                )}
                <td>
                  {a.factores?.length ? (
                    <ul className="factor-list">
                      {a.factores.map((f, i) => (
                        <li key={i} title={f.sugerencia || ""}>{f.texto}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="muted">{a.sugerir_revision ? "—" : "Sin revisión sugerida"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TablaDesglose({ titulo, sub, desglose, etiquetaGrupo }) {
  const grupos = desglose?.grupos || [];
  const ocultos = desglose?.ocultos || [];
  return (
    <div className="calm-card">
      <div className="calm-card-header">
        <div>
          <div className="calm-card-title">{titulo}</div>
          <div className="calm-card-sub">{sub}</div>
        </div>
      </div>
      {grupos.length > 0 && (
        <div className="dash-grid" style={{ marginBottom: 12 }}>
          <ChartCard title="Abandonos esperados" subtitle="Suma de probabilidades del modelo">
            <HorizontalBars data={grupos.map((g) => ({ label: g.label, value: g.abandonos_esperados }))} />
          </ChartCard>
          <ChartCard title="Necesidad de intervención alta" subtitle="Número de estudiantes">
            <HorizontalBars data={grupos.map((g) => ({ label: g.label, value: g.necesidad_alta }))} decimals={0} />
          </ChartCard>
        </div>
      )}
      <div className="dash-table-wrap">
        <table className="dash-table">
          <thead>
            <tr>
              <th>{etiquetaGrupo}</th>
              <th>Estudiantes</th>
              <th>Abandono alto</th>
              <th>Abandonos esperados</th>
              <th>Pérdida de beca alta</th>
              <th>Repetición alta</th>
              <th>Necesidad alta / media</th>
              <th>Faltas T3 previstas</th>
              <th>Suspenso T3 previsto</th>
              <th>Desánimo medio</th>
            </tr>
          </thead>
          <tbody>
            {grupos.map((g) => (
              <tr key={g.label}>
                <td>{g.label}</td>
                <td>{g.n}{g.con_prediccion < g.n ? <span className="muted"> ({g.con_prediccion} con predicción)</span> : null}</td>
                <td>{formatValue(g.pct_abandono_alto, " %")}</td>
                <td>{formatValue(g.abandonos_esperados)}</td>
                <td>{g.familias_juntos ? formatValue(g.pct_beca_alto, " %") : <span className="muted">Sin familias Juntos</span>}</td>
                <td>{formatValue(g.pct_repeticion_alto, " %")}</td>
                <td>{g.necesidad_alta} / {g.necesidad_media}</td>
                <td>{formatValue(g.faltas_t3_previstas, " d")}</td>
                <td>{formatValue(g.pct_suspenso_t3, " %")}</td>
                <td>{formatValue(g.desanimo_medio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!grupos.length && <div className="muted" style={{ padding: 12 }}>No hay grupos con datos suficientes.</div>}
      </div>
      {ocultos.length > 0 && (
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Ocultos por privacidad (menos de la cifra mínima de estudiantes): {ocultos.join(", ")}.
        </div>
      )}
    </div>
  );
}

export function PredictionsView({ token, role, onUnauthorized, refreshKey = 0, onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchPredictionsApi(token));
    } catch (err) {
      if (err.status === 401) {
        onUnauthorized?.();
        return;
      }
      setError(err.message || "No se pudieron cargar las predicciones.");
    } finally {
      setLoading(false);
    }
  }, [token, onUnauthorized]);

  useEffect(() => {
    cargar();
  }, [cargar, refreshKey]);

  const recalcular = async (soloPendientes) => {
    setBusy(true);
    setAviso(null);
    try {
      const r = await recalculatePredictionsApi(token, soloPendientes);
      setAviso(r.message);
      await cargar();
      onChanged?.();
    } catch (err) {
      setAviso(err.message || "No se pudieron recalcular las predicciones.");
    } finally {
      setBusy(false);
    }
  };

  const secciones = data?.secciones || [];
  const principales = secciones.filter((s) => s.interes !== "baja");
  const secundarias = secciones.filter((s) => s.interes === "baja");
  const modelo = data?.modelo;

  return (
    <main className="edusight-content">
      <div className="section-kicker">PREDICCIONES DEL MODELO</div>
      <h1 className="hero-serif-title">{TITULOS[role] || "Predicciones."}</h1>
      <p className="hero-subtitle">
        Estimaciones del modelo del equipo (LightGBM + Random Forest) a partir de los datos de cada estudiante.
        Son orientativas: ayudan a priorizar, no deciden por ti.
      </p>

      {modelo && !modelo.disponible && (
        <div className="alert-warn">
          <strong>El modelo predictivo no está disponible.</strong> {modelo.error || ""} No se muestran predicciones
          inventadas: los estudiantes guardados quedan pendientes hasta que el modelo vuelva a estar disponible.
        </div>
      )}

      <div className="pred-toolbar">
        <span className="muted">
          {data ? (
            <>
              {data.total ?? "—"} estudiantes · {data.con_prediccion} con predicción
              {data.pendientes ? ` · ${data.pendientes} pendientes` : ""}
              {modelo?.version ? ` · modelo ${modelo.version}` : ""}
            </>
          ) : null}
        </span>
        <span style={{ display: "flex", gap: 8 }}>
          {data?.pendientes > 0 && (
            <button type="button" className="btn-tiny-action" disabled={busy || !modelo?.disponible} onClick={() => recalcular(true)}>
              Calcular pendientes
            </button>
          )}
          <button type="button" className="btn-tiny-action" disabled={busy || !modelo?.disponible} onClick={() => recalcular(false)}>
            {busy ? "Recalculando…" : "Recalcular predicciones"}
          </button>
        </span>
      </div>
      {aviso && <div className="alert-info">{aviso}</div>}

      {loading && <div className="calm-card muted">Cargando predicciones…</div>}
      {error && <div className="alert-error">{error}</div>}
      {!loading && data?.mensaje && <div className="calm-card muted">{data.mensaje}</div>}

      {!loading && principales.length > 0 && (
        <div className="pred-grid">
          {principales.map((s) => (
            <Seccion key={s.id} s={s} notaAprobatoria={data.nota_aprobatoria} />
          ))}
        </div>
      )}

      {!loading && role === "docente" && data?.tablas?.alumnos?.length > 0 && <TablaDocente alumnos={data.tablas.alumnos} />}
      {!loading && role === "director" && data?.tablas?.grados && (
        <TablaDesglose titulo="Por grado" sub="Datos agregados de cada grado de tu escuela." desglose={data.tablas.grados} etiquetaGrupo="Grado" />
      )}
      {!loading && role === "delegado" && data?.tablas?.escuelas && (
        <>
          <TablaDesglose titulo="Por escuela" sub="Datos agregados de cada escuela de tu UGEL." desglose={data.tablas.escuelas} etiquetaGrupo="Escuela" />
          <TablaDesglose titulo="Por zona" sub="Rural frente a urbana." desglose={data.tablas.zonas} etiquetaGrupo="Zona" />
        </>
      )}

      {!loading && secundarias.length > 0 && (
        <div className="pred-secundarias">
          <div className="pred-secundarias-title">Otros indicadores</div>
          <div className="pred-secundarias-grid">
            {secundarias.map((s) => (
              <Seccion key={s.id} s={s} notaAprobatoria={data.nota_aprobatoria} />
            ))}
          </div>
        </div>
      )}

      {data?.umbrales && (
        <p className="muted" style={{ fontSize: 12, marginTop: 16 }}>
          Cómo se leen los niveles: probabilidad alta ≥ {data.umbrales.riesgo_alto_pct} %, media ≥ {data.umbrales.riesgo_medio_pct} %;
          desánimo alto ≥ {data.umbrales.desanimo_alto} y medio ≥ {data.umbrales.desanimo_medio} (escala 0–10).
          {role !== "docente" ? ` Los grupos con menos de ${data.k_minimo} estudiantes no se muestran.` : ""}
        </p>
      )}
    </main>
  );
}
