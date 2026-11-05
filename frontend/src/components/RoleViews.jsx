import React, { useState } from "react";
import { runGrantSimulationApi } from "../services/api.js";
import { formatValue } from "./charts/Charts.jsx";

/* ==========================================================================
   SIMULADOR DE REPARTO DE SUBVENCIONES (delegado territorial)
   No inventa impactos: la API cuenta con datos y predicciones reales de tu UGEL cuántos
   estudiantes encajan en cada línea y cuánto tocaría a cada uno con el reparto elegido.
   ========================================================================== */

export function DelegadoTerritorialView({ token }) {
  const [presupuesto, setPresupuesto] = useState("");
  const [pct, setPct] = useState({ transporte: "", beca: "", refuerzo: "" });
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const suma = ["transporte", "beca", "refuerzo"].reduce((t, k) => t + (Number(pct[k]) || 0), 0);

  const simular = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResultado(
        await runGrantSimulationApi(token, {
          presupuesto_total: Number(presupuesto),
          pct_transporte: Number(pct.transporte) || 0,
          pct_beca: Number(pct.beca) || 0,
          pct_refuerzo: Number(pct.refuerzo) || 0,
        })
      );
    } catch (err) {
      setError(err.message || "No se pudo simular el reparto.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="calm-card">
      <div className="calm-card-header">
        <div>
          <div className="calm-card-title">Simulador de reparto de apoyos</div>
          <div className="calm-card-sub">
            Indica un presupuesto y cómo repartirlo. Verás cuántos estudiantes de tu UGEL encajan en cada línea según sus
            datos y las predicciones del modelo. No estima efectos: eso lo decides tú.
          </div>
        </div>
      </div>
      <form onSubmit={simular} className="form-grid-3" style={{ alignItems: "end" }}>
        <div className="form-group">
          <label htmlFor="sim-presupuesto">Presupuesto total</label>
          <input id="sim-presupuesto" className="form-input" type="number" min="1" step="any" required value={presupuesto} onChange={(e) => setPresupuesto(e.target.value)} />
        </div>
        {[
          ["transporte", "% transporte"],
          ["beca", "% protección beca Juntos"],
          ["refuerzo", "% refuerzo y tutoría"],
        ].map(([k, label]) => (
          <div className="form-group" key={k}>
            <label htmlFor={`sim-${k}`}>{label}</label>
            <input id={`sim-${k}`} className="form-input" type="number" min="0" max="100" step="any" value={pct[k]} onChange={(e) => setPct((p) => ({ ...p, [k]: e.target.value }))} />
          </div>
        ))}
        <div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Suma: {formatValue(suma, " %")} {suma !== 100 && suma > 0 ? "(se reparte en proporción)" : ""}
          </div>
          <button type="submit" className="btn-forest" disabled={busy || !presupuesto || suma <= 0}>
            {busy ? "Calculando…" : "Simular reparto"}
          </button>
        </div>
      </form>
      {error && <div className="alert-error">{error}</div>}
      {resultado && (
        <div style={{ marginTop: 14 }}>
          <p className="pred-frase">{resultado.lectura_humanizada}</p>
          {resultado.lineas?.length > 0 && (
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th>Línea</th>
                    <th>Reparto</th>
                    <th>Importe ({resultado.moneda})</th>
                    <th>Estudiantes que encajan</th>
                    <th>Por estudiante ({resultado.moneda})</th>
                  </tr>
                </thead>
                <tbody>
                  {resultado.lineas.map((l) => (
                    <tr key={l.linea}>
                      <td>{l.etiqueta}</td>
                      <td>{formatValue(l.pct, " %")}</td>
                      <td>{formatValue(l.importe, "", 0)}</td>
                      <td>{l.estudiantes}</td>
                      <td>{l.por_estudiante === null ? <span className="muted">Nadie encaja</span> : formatValue(l.por_estudiante, "", 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
