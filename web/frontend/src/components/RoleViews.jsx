import React, { useState, useEffect } from "react";
import { runGrantSimulationApi } from "../services/api";

export function DocenteContextTable({ alumnos = [] }) {
  const [filterMode, setFilterMode] = useState("todos");

  const filtered = alumnos.filter((a) => {
    if (filterMode === "distancia") return (a.distancia_hogar_escuela_km || 0) >= 3.0;
    if (filterMode === "trabajo") return (a.horas_trabajo_semanal || 0) > 0;
    if (filterMode === "juntos") return a.beneficiario_juntos === 1;
    if (filterMode === "alerta") return a.necesidad_intervencion === "Alta" || a.necesidad_intervencion === "Media";
    return true;
  });

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Seguimiento contextual de estudiantes (30 variables oficiales · Reto 13)</h2>
          <p>
            Muestra el contexto de desplazamiento, subsidio Juntos, dedicación laboral y calificaciones vigesimales (0-20) sin semáforos estigmatizantes.
          </p>
        </div>
        <div className="filter-pills-row">
          <button
            type="button"
            className={`btn-secondary ${filterMode === "todos" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("todos")}
          >
            Todos ({alumnos.length})
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "distancia" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("distancia")}
          >
            Distancia &ge; 3 km
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "trabajo" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("trabajo")}
          >
            Trabajo semanal (&gt; 0 h)
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "juntos" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("juntos")}
          >
            Programa Juntos
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "alerta" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("alerta")}
          >
            Prioridad de apoyo
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        {alumnos.length === 0 ? (
          <div style={{ padding: "36px 20px", textAlign: "center", color: "#64748b" }}>
            <h3 style={{ fontSize: "15px", color: "#334155", marginBottom: "6px" }}>Base de datos conectada · 0 estudiantes registrados</h3>
            <p style={{ fontSize: "13px" }}>
              La tabla <code>alumnos_hack4edu</code> está lista y limpia. En cuanto tu equipo entregue el archivo CSV o ejecute el modelo predictivo, aparecerán aquí todos los datos del aula.
            </p>
            <div style={{ marginTop: "12px", fontFamily: "monospace", fontSize: "12px", background: "#f1f5f9", display: "inline-block", padding: "6px 12px", borderRadius: "6px" }}>
              Comando de carga: pixi run python db/import_csv.py --csv &lt;archivo.csv&gt;
            </div>
          </div>
        ) : (
          <table className="clean-table">
            <thead>
              <tr>
                <th>Estudiante</th>
                <th>Grado / Edad</th>
                <th>Desplazamiento</th>
                <th>Contexto / Subsidio</th>
                <th>Asistencia (T1/T2)</th>
                <th>Notas (0-20)</th>
                <th>Proyección T3</th>
                <th>Prioridad Modelo</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 25).map((a) => {
                const factores = [];
                if ((a.distancia_hogar_escuela_km || 0) >= 3.0) {
                  factores.push(`${a.distancia_hogar_escuela_km} km (${a.tiempo_desplazamiento || 0} min)`);
                }
                if ((a.horas_trabajo_semanal || 0) > 0) {
                  factores.push(`Trabajo: ${a.horas_trabajo_semanal}h/sem`);
                }
                if (a.internet_hogar === 0) {
                  factores.push("Sin internet");
                }
                if (factores.length === 0) {
                  factores.push("Trayecto regular");
                }

                return (
                  <tr key={a.alumno_id}>
                    <td>
                      <strong>{a.alumno_id}</strong>
                      <div style={{ fontSize: "11px", color: "#64748b" }}>{a.sexo === "M" ? "Varón" : "Mujer"}</div>
                    </td>
                    <td>{a.grado_secundaria}º Sec · {a.edad} años</td>
                    <td>{factores.join(" · ")}</td>
                    <td>
                      {a.beneficiario_juntos === 1 ? (
                        <span style={{ color: "#166534", fontWeight: 600 }}>Programa Juntos</span>
                      ) : (
                        <span style={{ color: "#64748b" }}>Sin subsidio</span>
                      )}
                    </td>
                    <td>
                      <div><strong>{a.asistencia_pct_calculada || 0}%</strong></div>
                      <div style={{ fontSize: "11px", color: "#64748b" }}>
                        Faltas: {a.faltas_totales_calculadas || 0} ({a.faltas_trimestre_1 || 0} T1 / {a.faltas_trimestre_2 || 0} T2)
                      </div>
                    </td>
                    <td>
                      <div><strong>{a.promedio_notas_calculado || 0}</strong> / 20</div>
                      <div style={{ fontSize: "11px", color: "#64748b" }}>
                        T1: {a.nota_trimestre_1_0_20 || "-"} · T2: {a.nota_trimestre_2_0_20 || "-"}
                      </div>
                    </td>
                    <td>
                      {a.prediccion_nota_t3 ? (
                        <div>
                          <div>Nota: <strong>{a.prediccion_nota_t3}</strong>/20</div>
                          <div style={{ fontSize: "11px", color: "#64748b" }}>Faltas: ~{a.prediccion_faltas_t3 || 0}d</div>
                        </div>
                      ) : (
                        <span style={{ color: "#94a3b8" }}>Pendiente</span>
                      )}
                    </td>
                    <td>
                      {a.necesidad_intervencion ? (
                        <span className="tag-context">
                          {a.necesidad_intervencion === "Alta" ? "Revisar esta semana" : "Seguimiento"}
                        </span>
                      ) : (
                        <span style={{ color: "#94a3b8", fontSize: "12px" }}>Ordinaria</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function DirectorGroupsTable({ grupos = [] }) {
  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Consolidado por grados del centro educativo (Escala 0-20 y Reto 13)</h2>
          <p>
            Muestra el promedio de notas, porcentaje de asistencia acumulada y alumnos con alerta de prioridad alta calculados en tiempo real.
          </p>
        </div>
        <span className="badge-neutral">Vista SQL: vista_director</span>
      </div>

      <div className="table-wrapper">
        {grupos.length === 0 ? (
          <div style={{ padding: "30px 20px", textAlign: "center", color: "#64748b" }}>
            Base de datos conectada. Esperando carga de alumnos para calcular los consolidados por grado escolar.
          </div>
        ) : (
          <table className="clean-table">
            <thead>
              <tr>
                <th>Grado Escolar</th>
                <th>Estudiantes</th>
                <th>Asistencia Media</th>
                <th>Promedio Notas (0-20)</th>
                <th>Conectividad Hogar</th>
                <th>Horas Estudio Semanal</th>
                <th>Casos Prioridad Alta</th>
              </tr>
            </thead>
            <tbody>
              {grupos.map((g, idx) => (
                <tr key={idx}>
                  <td>
                    <strong>{g.nombre_grupo}</strong>
                  </td>
                  <td>{g.num_estudiantes} est.</td>
                  <td><strong>{g.asistencia_media_pct}%</strong></td>
                  <td><strong>{g.participacion_aula_pct || g.promedio_notas || 0}</strong> / 20</td>
                  <td>{g.uso_recursos_aula_pct || 0}% con internet</td>
                  <td>{g.horas_formacion_docente || 0} h/sem</td>
                  <td>
                    {g.vinculo_familiar_pct > 0 ? (
                      <span style={{ color: "#991b1b", fontWeight: 700 }}>{g.vinculo_familiar_pct} alertas</span>
                    ) : (
                      <span style={{ color: "#166534" }}>0 alertas</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function DelegadoTerritorialView({ escuelas = [], token }) {
  const [budget, setBudget] = useState(120000);
  const [becasPct, setBecasPct] = useState(45);
  const [formacionPct, setFormacionPct] = useState(35);
  const [simResult, setSimResult] = useState(null);

  const offlinePct = Math.max(0, 100 - becasPct - formacionPct);

  useEffect(() => {
    let active = true;
    if (!token) return;
    runGrantSimulationApi(token, {
      presupuesto_total_eur: Number(budget),
      pct_becas_transporte: Number(becasPct),
      pct_formacion_docente: Number(formacionPct),
      pct_servidores_offline: Number(offlinePct),
    })
      .then((res) => {
        if (active) setSimResult(res);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [budget, becasPct, formacionPct, offlinePct, token]);

  return (
    <>
      <div className="panel-card">
        <div className="panel-header">
          <div>
            <h2>Simulador presupuestario territorial (Focalización rural y Programa Juntos)</h2>
            <p>
              Calcula sobre los datos reales de la BD el impacto de destinar recursos a transporte rural, refuerzo escolar y recursos sin conexión.
            </p>
          </div>
          <span className="badge-neutral">Vista SQL: vista_delegado</span>
        </div>

        <div className="chart-box">
          <div className="sim-grid">
            <div className="sim-control">
              <label htmlFor="sim-budget">
                <strong>Presupuesto disponible: {Number(budget).toLocaleString()} EUR</strong>
              </label>
              <input
                id="sim-budget"
                type="range"
                min="50000"
                max="250000"
                step="10000"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </div>

            <div className="sim-control">
              <label htmlFor="sim-becas">
                <strong>% Transporte rural y comedor: {becasPct}%</strong>
              </label>
              <input
                id="sim-becas"
                type="range"
                min="10"
                max="80"
                step="5"
                value={becasPct}
                onChange={(e) => setBecasPct(Number(e.target.value))}
              />
            </div>

            <div className="sim-control">
              <label htmlFor="sim-formacion">
                <strong>% Refuerzo pedagógico: {formacionPct}% ({offlinePct}% offline)</strong>
              </label>
              <input
                id="sim-formacion"
                type="range"
                min="10"
                max={90 - becasPct}
                step="5"
                value={formacionPct}
                onChange={(e) => setFormacionPct(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="sim-output">
            <strong>Proyección sobre datos reales: </strong>
            {simResult ? simResult.lectura_humanizada : "Calculando..."}
          </div>
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div>
            <h2>Red de centros educativos en UGEL (Rural vs Urbano)</h2>
            <p>
              Información territorial para asignación equitativa de recursos y seguimiento de brechas de acceso.
            </p>
          </div>
          <span className="badge-neutral">Vista SQL: vista_delegado</span>
        </div>

        <div className="table-wrapper">
          {escuelas.length === 0 ? (
            <div style={{ padding: "30px 20px", textAlign: "center", color: "#64748b" }}>
              Base de datos conectada. Esperando carga de datos territoriales de la UGEL.
            </div>
          ) : (
            <table className="clean-table">
              <thead>
                <tr>
                  <th>Centro Educativo</th>
                  <th>Zona</th>
                  <th>Conectividad Hogar</th>
                  <th>Distancia Media</th>
                  <th>Asistencia Media</th>
                  <th>Promedio Notas (0-20)</th>
                  <th>Alertas Prioritarias</th>
                </tr>
              </thead>
              <tbody>
                {escuelas.map((e, idx) => (
                  <tr key={idx}>
                    <td>
                      <strong>{e.nombre_escuela}</strong>
                    </td>
                    <td>{e.zona}</td>
                    <td>{e.conectividad_pct}%</td>
                    <td>{e.brecha_uso_equipamiento_pct || 0} km</td>
                    <td><strong>{e.asistencia_media_pct}%</strong></td>
                    <td>{e.aprendizaje_medio_pts || 0} / 20</td>
                    <td>
                      {e.horas_formacion_docente_media > 0 ? (
                        <span style={{ color: "#991b1b", fontWeight: 700 }}>{e.horas_formacion_docente_media}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
