import React, { useState, useEffect } from "react";
import { runGrantSimulationApi } from "../services/api";

export function DocenteContextTable({ alumnos = [], onLoadSample }) {
  const [filterMode, setFilterMode] = useState("todos");

  const filtered = alumnos.filter((a) => {
    if (filterMode === "distancia") return (a.distancia_hogar_escuela_km || 0) >= 3.0;
    if (filterMode === "trabajo") return (a.horas_trabajo_semanal || 0) > 0;
    if (filterMode === "juntos") return a.beneficiario_juntos === 1;
    if (filterMode === "alerta")
      return a.necesidad_intervencion === "Alta" || a.necesidad_intervencion === "Media";
    return true;
  });

  return (
    <div>
      <div className="calm-card-header">
        <div>
          <h2 className="calm-card-title">
            Seguimiento contextual del grupo (30 variables oficiales + 7 predictivas)
          </h2>
          <p className="calm-card-sub">
            Desplazamiento, subsidio Juntos, dedicación laboral y calificaciones vigesimales (0-20) sin semáforos estigmatizantes.
          </p>
        </div>
        <div className="filter-pills-row">
          <button
            type="button"
            className={`btn-outline-calm ${filterMode === "todos" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("todos")}
          >
            Todos ({alumnos.length})
          </button>
          <button
            type="button"
            className={`btn-outline-calm ${filterMode === "distancia" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("distancia")}
          >
            Distancia &ge; 3 km
          </button>
          <button
            type="button"
            className={`btn-outline-calm ${filterMode === "trabajo" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("trabajo")}
          >
            Trabajo semanal (&gt; 0 h)
          </button>
          <button
            type="button"
            className={`btn-outline-calm ${filterMode === "juntos" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("juntos")}
          >
            Programa Juntos
          </button>
          <button
            type="button"
            className={`btn-outline-calm ${filterMode === "alerta" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("alerta")}
          >
            Prioridad de apoyo
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        {alumnos.length === 0 ? (
          <div style={{ padding: "32px 20px", textAlign: "center", color: "#5e6c65" }}>
            <h3 style={{ fontFamily: "var(--font-serif)", fontSize: "20px", color: "#1c2a24", marginBottom: "8px", fontWeight: 500 }}>
              Base de datos conectada · 0 estudiantes registrados actualmente
            </h3>
            <p style={{ fontSize: "13.5px", maxWidth: "560px", margin: "0 auto 16px" }}>
              La tabla <code>alumnos_hack4edu</code> está limpia. Puedes subir el archivo CSV del equipo o cargar ahora mismo 30 estudiantes de prueba para explorar las consultas SQL en vivo.
            </p>
            {onLoadSample && (
              <button type="button" className="btn-forest" onClick={onLoadSample}>
                Cargar 30 estudiantes de prueba en la Base de Datos
              </button>
            )}
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
                <th>Acompañamiento</th>
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
                  factores.push("Sin internet en casa");
                }
                if (factores.length === 0) {
                  factores.push("Trayecto regular");
                }

                return (
                  <tr key={a.alumno_id}>
                    <td>
                      <strong>{a.alumno_id}</strong>
                      <div style={{ fontSize: "11px", color: "#6b7871" }}>
                        {a.sexo === "M" ? "Varón" : "Mujer"}
                      </div>
                    </td>
                    <td>
                      {a.grado_secundaria}° Sec · {a.edad} años
                    </td>
                    <td>{factores.join(" · ")}</td>
                    <td>
                      {a.beneficiario_juntos === 1 ? (
                        <span style={{ color: "#1f6351", fontWeight: 600 }}>Programa Juntos</span>
                      ) : (
                        <span style={{ color: "#6b7871" }}>Sin subsidio</span>
                      )}
                    </td>
                    <td>
                      <div>
                        <strong>{a.asistencia_pct_calculada || 0}%</strong>
                      </div>
                      <div style={{ fontSize: "11px", color: "#6b7871" }}>
                        Faltas: {a.faltas_totales_calculadas || 0} ({a.faltas_trimestre_1 || 0} T1 /{" "}
                        {a.faltas_trimestre_2 || 0} T2)
                      </div>
                    </td>
                    <td>
                      <div>
                        <strong>{a.promedio_notas_calculado || 0}</strong> / 20
                      </div>
                      <div style={{ fontSize: "11px", color: "#6b7871" }}>
                        T1: {a.nota_trimestre_1_0_20 ?? "-"} · T2: {a.nota_trimestre_2_0_20 ?? "-"}
                      </div>
                    </td>
                    <td>
                      {a.prediccion_nota_t3 ? (
                        <div>
                          <div>
                            Nota: <strong>{a.prediccion_nota_t3}</strong>/20
                          </div>
                          <div style={{ fontSize: "11px", color: "#6b7871" }}>
                            Faltas est.: ~{a.prediccion_faltas_t3 || 0}d
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: "#6b7871" }}>Pendiente</span>
                      )}
                    </td>
                    <td>
                      {a.necesidad_intervencion ? (
                        <span className="tag-context">
                          {a.necesidad_intervencion === "Alta"
                            ? "Para revisar esta semana"
                            : "Seguimiento cercano"}
                        </span>
                      ) : (
                        <span style={{ color: "#6b7871", fontSize: "12px" }}>Continuidad regular</span>
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

export function DirectorGroupsTable({ grupos = [], onLoadSample }) {
  return (
    <div>
      <div className="calm-card-header">
        <div>
          <h2 className="calm-card-title">
            Consolidado por grados del centro educativo (Escala 0-20)
          </h2>
          <p className="calm-card-sub">
            Promedio de notas, asistencia acumulada y prioridades de acompañamiento calculados mediante SQL en <code>vista_director</code>.
          </p>
        </div>
        <span className="tag-context">Vista SQL: vista_director</span>
      </div>

      <div className="table-wrapper">
        {grupos.length === 0 ? (
          <div style={{ padding: "30px 20px", textAlign: "center", color: "#5e6c65" }}>
            <p style={{ marginBottom: "14px" }}>
              Base de datos conectada (0 registros). Carga datos de prueba o sube el archivo CSV para ver las cohortes del centro.
            </p>
            {onLoadSample && (
              <button type="button" className="btn-forest" onClick={onLoadSample}>
                Cargar 30 estudiantes de prueba
              </button>
            )}
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
                <th>Estudio Semanal</th>
                <th>Para Revisar</th>
              </tr>
            </thead>
            <tbody>
              {grupos.map((g, idx) => (
                <tr key={idx}>
                  <td>
                    <strong>{g.nombre_grupo}</strong>
                  </td>
                  <td>{g.num_estudiantes} est.</td>
                  <td>
                    <strong>{g.asistencia_media_pct}%</strong>
                  </td>
                  <td>
                    <strong>{g.participacion_aula_pct || g.promedio_notas || 0}</strong> / 20
                  </td>
                  <td>{g.uso_recursos_aula_pct || 0}% con internet</td>
                  <td>{g.horas_formacion_docente || 0} h/sem</td>
                  <td>
                    {g.vinculo_familiar_pct > 0 ? (
                      <span className="tag-context">{g.vinculo_familiar_pct} casos</span>
                    ) : (
                      <span style={{ color: "#1f6351" }}>Estable</span>
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

export function DelegadoTerritorialView({ escuelas = [], token, onLoadSample }) {
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
      <div className="calm-card">
        <div className="calm-card-header">
          <div>
            <h2 className="calm-card-title">
              Simulador presupuestario territorial (Transporte rural y Programa Juntos)
            </h2>
            <p className="calm-card-sub">
              Estima sobre los registros de la BD el impacto de destinar recursos a transporte escolar, acompañamiento docente y servidores sin conexión.
            </p>
          </div>
          <span className="tag-context">Vista SQL: vista_delegado</span>
        </div>

        <div>
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
                <strong>
                  % Refuerzo pedagógico: {formacionPct}% ({offlinePct}% offline)
                </strong>
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
            <strong>Proyección sobre la base de datos: </strong>
            {simResult ? simResult.lectura_humanizada : "Calculando..."}
          </div>
        </div>
      </div>

      <div className="calm-card">
        <div className="calm-card-header">
          <div>
            <h2 className="calm-card-title">Red de centros educativos en UGEL (Rural vs Urbano)</h2>
            <p className="calm-card-sub">
              Comparativa territorial de asistencia, conectividad doméstica y distancia media de desplazamiento.
            </p>
          </div>
          <span className="tag-context">Vista SQL: vista_delegado</span>
        </div>

        <div className="table-wrapper">
          {escuelas.length === 0 ? (
            <div style={{ padding: "30px 20px", textAlign: "center", color: "#5e6c65" }}>
              <p style={{ marginBottom: "14px" }}>
                Base de datos conectada (0 registros). Carga los 30 estudiantes de prueba o sube un archivo CSV para ver las escuelas de la red.
              </p>
              {onLoadSample && (
                <button type="button" className="btn-forest" onClick={onLoadSample}>
                  Cargar 30 estudiantes de prueba
                </button>
              )}
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
                  <th>Casos Para Revisar</th>
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
                    <td>
                      <strong>{e.asistencia_media_pct}%</strong>
                    </td>
                    <td>{e.aprendizaje_medio_pts || 0} / 20</td>
                    <td>
                      {e.horas_formacion_docente_media > 0 ? (
                        <span className="tag-context">{e.horas_formacion_docente_media}</span>
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
