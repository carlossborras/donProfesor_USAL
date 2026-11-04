import React, { useState, useEffect } from "react";
import { runGrantSimulationApi } from "../services/api";

export function DocenteContextTable({ alumnos = [] }) {
  const [filterMode, setFilterMode] = useState("todos");

  const filtered = alumnos.filter((a) => {
    if (filterMode === "lluvia") return a.distancia_km >= 3.0;
    if (filterMode === "cosecha") return a.apoyo_cosecha_familiar === 1 || a.segundo_empleo_familiar === 1;
    if (filterMode === "beca") return a.tiene_beca === 1;
    return true;
  });

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Seguimiento contextual del grupo 2º B (Sin rankings ni semáforos por estudiante)</h2>
          <p>
            Muestra los factores contextuales de traslado, beca, apoyo agrícola y continuidad de entregas para orientar el acompañamiento.
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
            className={`btn-secondary ${filterMode === "lluvia" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("lluvia")}
          >
            Distancia &gt; 3 km
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "cosecha" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("cosecha")}
          >
            Cosecha / Apoyo vespertino
          </button>
          <button
            type="button"
            className={`btn-secondary ${filterMode === "beca" ? "active-filter" : ""}`}
            onClick={() => setFilterMode("beca")}
          >
            Con beca protectora
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="clean-table">
          <thead>
            <tr>
              <th>Código Tutoría</th>
              <th>Distancia</th>
              <th>Factores Contextuales Observados</th>
              <th>Cobertura de Apoyo</th>
              <th>Participación Aula</th>
              <th>Continuidad Entregas</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 14).map((a) => {
              const factores = [];
              if (a.distancia_km >= 3.0) {
                factores.push(`Distancia ${a.distancia_km} km (${a.faltas_dias_lluvia} faltas lluvia)`);
              }
              if (a.apoyo_cosecha_familiar === 1) {
                factores.push(`Calendario cosecha (${a.faltas_semanas_cosecha} faltas)`);
              }
              if (a.segundo_empleo_familiar === 1) {
                factores.push("Apoyo laboral vespertino");
              }
              if (a.acceso_internet_hogar === 0) {
                factores.push("Sin internet en hogar (requiere guía offline)");
              }
              if (factores.length === 0) {
                factores.push("Trayecto cercano y asistencia regular");
              }

              return (
                <tr key={a.codigo_seguimiento}>
                  <td>
                    <strong>{a.codigo_seguimiento}</strong>
                  </td>
                  <td>{a.distancia_km} km</td>
                  <td>{factores.join(" · ")}</td>
                  <td>{a.tiene_beca === 1 ? "Beca activa (Factor protector)" : "Sin beca asignada"}</td>
                  <td>{a.participacion_actividades_pct}%</td>
                  <td>{a.continuidad_entregas_pct}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DirectorGroupsTable({ grupos = [] }) {
  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Comparativa entre grupos del centro y reparto de recursos (I.E. Valle Verde)</h2>
          <p>
            Relación entre las horas de formación práctica docente, la utilización de equipamiento del centro y la asistencia por grupo.
          </p>
        </div>
        <span className="badge-neutral">Vista SQL: vista_director (k &gt;= 26)</span>
      </div>

      <div className="table-wrapper">
        <table className="clean-table">
          <thead>
            <tr>
              <th>Grupo</th>
              <th>Tutoría</th>
              <th>Cohorte (k)</th>
              <th>Asistencia</th>
              <th>Formación Docente</th>
              <th>Uso Recursos (vs 84% disp.)</th>
              <th>Participación</th>
              <th>Vínculo Familiar</th>
            </tr>
          </thead>
          <tbody>
            {grupos.map((g) => (
              <tr key={g.grupo_id}>
                <td>
                  <strong>{g.nombre_grupo}</strong>
                </td>
                <td>{g.docente_tutor}</td>
                <td>{g.num_estudiantes} est.</td>
                <td>{g.asistencia_media_pct}%</td>
                <td>
                  <strong>{g.horas_formacion_docente} h</strong>
                </td>
                <td>
                  <strong>{g.uso_recursos_aula_pct}%</strong> (Brecha:{" "}
                  {Number(g.brecha_recursos_sin_usar_pct).toFixed(1)}%)
                </td>
                <td>{g.participacion_aula_pct}%</td>
                <td>{g.vinculo_familiar_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
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
            <h2>Mapa territorial de escuelas con brechas de conectividad/recursos y simulador de subvenciones</h2>
            <p>
              Representación espacial de los 12 centros cabecera de la red según zona (Rural, Periurbana, Urbana) y simulador de impacto presupuestario.
            </p>
          </div>
          <span className="badge-neutral">Vista SQL: vista_delegado (k &gt;= 98)</span>
        </div>

        <div className="chart-box">
          <div className="legend-row">
            <div className="legend-entry">
              <span className="legend-swatch" style={{ background: "#b45309" }} />
              <span>Escuela Rural (Prioridad transporte y servidor offline)</span>
            </div>
            <div className="legend-entry">
              <span className="legend-swatch" style={{ background: "#2563eb" }} />
              <span>Escuela Periurbana (Prioridad mentoría docente)</span>
            </div>
            <div className="legend-entry">
              <span className="legend-swatch" style={{ background: "#0d9488" }} />
              <span>Escuela Urbana (Nodo mentor de red)</span>
            </div>
          </div>

          <svg
            viewBox="0 0 760 185"
            width="100%"
            height="185"
            style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px" }}
          >
            {escuelas.map((e, idx) => {
              const x = 68 + (idx % 4) * 176 + (idx % 2) * 20;
              const y = 44 + Math.floor(idx / 4) * 52;
              const fill =
                e.zona === "Rural" ? "#b45309" : e.zona === "Periurbana" ? "#2563eb" : "#0d9488";
              return (
                <g key={e.escuela_id}>
                  <circle cx={x} cy={y} r="11" fill={fill} opacity="0.18" />
                  <circle cx={x} cy={y} r="5.5" fill={fill} />
                  <text x={x + 12} y={y - 2} fontSize="10.5" fontWeight="600" fill="#0f172a">
                    {e.nombre_escuela}
                  </text>
                  <text x={x + 12} y={y + 11} fontSize="9.5" fill="#475569">
                    {e.zona} · Conectividad {e.conectividad_pct}% · Uso rec. {e.tasa_uso_recursos_pct}%
                  </text>
                </g>
              );
            })}
          </svg>

          <div className="sim-grid">
            <div className="sim-control">
              <label htmlFor="sim-budget">
                <strong>Presupuesto de subvención (EUR): {Number(budget).toLocaleString()}</strong>
              </label>
              <input
                id="sim-budget"
                type="range"
                min="60000"
                max="240000"
                step="10000"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </div>

            <div className="sim-control">
              <label htmlFor="sim-becas">
                <strong>% Becas Transporte y Comedor Rural: {becasPct}%</strong>
              </label>
              <input
                id="sim-becas"
                type="range"
                min="10"
                max="70"
                step="5"
                value={becasPct}
                onChange={(e) => setBecasPct(Number(e.target.value))}
              />
            </div>

            <div className="sim-control">
              <label htmlFor="sim-formacion">
                <strong>
                  % Mentoría Docente ({formacionPct}%) y Offline ({offlinePct}%)
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
            <strong>Proyección del Simulador Territorial: </strong>
            {simResult
              ? simResult.lectura_humanizada
              : "Calculando proyección territorial de impacto..."}
          </div>
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div>
            <h2>Matriz territorial de centros educativos (Conectividad, Formación Docente y Uso de Recursos)</h2>
            <p>
              Datos agregados con garantía de k-anonimato para orientar el reparto equitativo de recursos y acompañamiento.
            </p>
          </div>
          <span className="badge-neutral">Vista SQL: vista_delegado</span>
        </div>

        <div className="table-wrapper">
          <table className="clean-table">
            <thead>
              <tr>
                <th>Centro Educativo</th>
                <th>Zona</th>
                <th>Conectividad</th>
                <th>Disp. Equipos</th>
                <th>Uso Efectivo (y Brecha)</th>
                <th>Formación Docente</th>
                <th>Asistencia</th>
                <th>Aprendizaje</th>
              </tr>
            </thead>
            <tbody>
              {escuelas.map((e) => (
                <tr key={e.escuela_id}>
                  <td>
                    <strong>{e.nombre_escuela}</strong>
                  </td>
                  <td>{e.zona}</td>
                  <td>{e.conectividad_pct}%</td>
                  <td>{e.dispositivos_disponibles_pct}%</td>
                  <td>
                    <strong>{e.tasa_uso_recursos_pct}%</strong> (Brecha:{" "}
                    {Number(e.brecha_uso_equipamiento_pct).toFixed(1)}%)
                  </td>
                  <td>{e.horas_formacion_docente_media} h</td>
                  <td>{e.asistencia_media_pct}%</td>
                  <td>{e.aprendizaje_medio_pts} pts</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
