import logoLibro from "./assets/logo_libro_sin_fondo.png";
import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  fetchDashboardPanel,
  fetchMcpMetadata,
  sendMcpChatQuestion,
  registerPedagogicalAction,
  loadSampleDatasetApi,
  clearDatasetApi,
  uploadCsvDatasetApi,
  fetchLlmStatusApi,
} from "./services/api.js";
import { DelegadoTerritorialView } from "./components/RoleViews.jsx";
import { RoleDashboard } from "./components/RoleDashboard.jsx";
import { StudentEntryModal } from "./components/StudentEntryModal.jsx";
import { PredictionsView } from "./components/PredictionsView.jsx";

const ROLE_META = {
  docente: {
    label: "Docente",
    scopeTitle: "Tutoría de aula",
    heroSubtitle: "Pistas y situaciones prioritarias para acompañar a tu grupo esta semana.",
  },
  director: {
    label: "Director",
    scopeTitle: "Dirección de centro",
    heroSubtitle: "Prioridades del centro educativo para coordinar con tu equipo docente.",
  },
  delegado: {
    label: "Delegado",
    scopeTitle: "Red territorial educativa",
    heroSubtitle: "Focos territoriales para orientar recursos de transporte, becas y conectividad.",
  },
};

const CHAT_PRESETS = {
  docente: [
    "¿Qué estudiantes viven a más de 3 km o tardan más de 30 minutos en llegar?",
    "¿Quiénes han aumentado sus faltas del 1.er al 2.º trimestre?",
    "¿Qué estudiantes trabajan fuera del horario escolar?",
    "¿Qué estudiantes tienen una nota prevista del 3.er trimestre por debajo de 11?",
  ],
  director: [
    "¿Qué grados tienen más casos de necesidad de intervención alta?",
    "¿Cómo es la asistencia media de cada grado?",
    "¿Qué grados tienen menos internet en casa?",
    "¿Qué nota media se prevé para el 3.er trimestre en cada grado?",
  ],
  delegado: [
    "¿Qué escuelas rurales tienen menor conectividad?",
    "¿Cómo se distribuye la asistencia entre centros urbanos y rurales?",
    "¿Qué escuelas tienen mayor distancia media entre casa y escuela?",
    "¿Qué escuelas concentran más casos de necesidad de intervención alta?",
  ],
};

function mapDbAlertToPista(item, index) {
  const code = item.codigo_seguimiento || item.alumno_id || item.prediccion_id;
  const factors = [];

  if (Array.isArray(item.factores) && item.factores.length > 0) {
    for (const f of item.factores) {
      factors.push({
        label: f.texto || f.label,
        pct: Math.round(Number(f.peso ?? f.pct) || 0),
      });
    }
  } else {
    if (item.factor_principal_riesgo || item.factor_1_texto) {
      factors.push({
        label: item.factor_principal_riesgo || item.factor_1_texto,
        pct: Math.round(Number(item.factor_1_peso) || 0),
      });
    }
    if (item.factor_2_texto) {
      factors.push({
        label: item.factor_2_texto,
        pct: Math.round(Number(item.factor_2_peso) || 0),
      });
    }
    if (item.factor_3_texto) {
      factors.push({
        label: item.factor_3_texto,
        pct: Math.round(Number(item.factor_3_peso) || 0),
      });
    }
  }


  return {
    id: item.prediccion_id || code,
    alumno_id: code,
    kickerCard: `Estudiante ${code}`,
    kickerDetail: `ESTUDIANTE ${code}`,
    title: item.titulo_humano || `Prioridad de acompañamiento (${code})`,
    lead:
      [item.categoria_contexto, item.descripcion_situacion].filter(Boolean).join(" · ") ||
      "El modelo sugiere revisar esta situación.",
    factors,
    defaultDecision: item.recomendacion_pedagogica || "",
    helperPrompt: `Analiza la situación del estudiante ${code} en los registros de aula y sugiéreme recomendaciones de acompañamiento pedagógico.`,
    fromDatabase: true,
    estado_revision: item.estado_revision,
  };
}

export function App({ session, onLogout }) {
  // El rol y el ámbito vienen de la sesión (token JWT): no se pueden cambiar desde la interfaz.
  const activeRole = session?.user?.rol || "docente";
  const [activeNav, setActiveNav] = useState("revisar"); // "revisar" | "comovamos" | "predicciones" | "lohablamos"
  const token = session?.token || null;
  const user = session?.user || null;
  const [dashboardRefresh, setDashboardRefresh] = useState(0);
  const [panelData, setPanelData] = useState(null);
  const [mcpMeta, setMcpMeta] = useState(null);
  const [llmStatus, setLlmStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toastMsg, setToastMsg] = useState(null);

  // Master-detail state ("Para revisar")
  const [selectedPistaIdx, setSelectedPistaIdx] = useState(0);
  const [accompanimentOpen, setAccompanimentOpen] = useState(false);
  const [decisionText, setDecisionText] = useState("");
  const [commentText, setCommentText] = useState("");
  const [savingAction, setSavingAction] = useState(false);
  const [completedIds, setCompletedIds] = useState({});

  // Modal "Sobre esta ayuda" y gestión de datos
  const [aboutModalOpen, setAboutModalOpen] = useState(false);
  const [studentModalOpen, setStudentModalOpen] = useState(false);
  const [dataBusy, setDataBusy] = useState(false);
  const fileInputRef = useRef(null);

  // Chat state ("Lo hablamos")
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "assistant",
      text: "Hola. Soy tu asistente de aula. Puedes preguntarme por la asistencia, las notas, las predicciones o el contexto de tus estudiantes. Respondo solo con los datos de tu ámbito.",
      sql: null,
      rowsCount: 0,
      mcpTrace: null,
    },
  ]);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => {
      setToastMsg((prev) => (prev === msg ? null : prev));
    }, 4000);
  };

  const handleSessionExpired = useCallback(() => {
    onLogout?.("Tu sesión ha caducado. Vuelve a iniciar sesión.");
  }, [onLogout]);

  const loadRoleData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    setSelectedPistaIdx(0);
    setAccompanimentOpen(false);
    try {
      const [panelRes, mcpRes, llmRes] = await Promise.all([
        fetchDashboardPanel(token),
        fetchMcpMetadata(token).catch(() => null),
        fetchLlmStatusApi(token).catch(() => null),
      ]);
      setPanelData(panelRes);
      setMcpMeta(mcpRes);
      if (llmRes) {
        setLlmStatus(llmRes);
      }
    } catch (err) {
      if (err.status === 401) {
        handleSessionExpired();
        return;
      }
      setError(err.message || "Error al conectar con el servidor de DONPROFESOR");
    } finally {
      setLoading(false);
    }
  }, [token, handleSessionExpired]);

  useEffect(() => {
    loadRoleData();
  }, [loadRoleData]);

  // Construir lista de alertas exclusivamente de la base de datos real
  const activePistas = useMemo(() => {
    const dbAlerts = panelData?.avisos_predictivos || [];
    return dbAlerts.map(mapDbAlertToPista);
  }, [panelData?.avisos_predictivos]);

  const currentPista = activePistas[selectedPistaIdx] || activePistas[0] || null;

  useEffect(() => {
    if (currentPista) {
      setDecisionText(currentPista.defaultDecision || "");
      setCommentText("");
    }
  }, [currentPista?.id]);

  const handleSaveAccompaniment = async (e) => {
    e.preventDefault();
    if (!token || !currentPista) return;
    setSavingAction(true);
    try {
      await registerPedagogicalAction(token, {
        alumno_id: currentPista.alumno_id,
        decision_tomada: decisionText,
        comentario_pedagogico:
          commentText.trim() || "Acompañamiento anotado desde el espacio 'Para revisar'.",
      });
      setCompletedIds((prev) => ({ ...prev, [currentPista.id]: true }));
      setAccompanimentOpen(false);
      const refreshed = await fetchDashboardPanel(token);
      setPanelData(refreshed);
      setDashboardRefresh((k) => k + 1);
      showToast(`Acompañamiento guardado en la base de datos para ${currentPista.kickerCard}.`);
    } catch (err) {
      showToast(err.message || "No se pudo guardar la anotación.");
    } finally {
      setSavingAction(false);
    }
  };

  const handleAskHelperAboutPista = async (pista) => {
    setActiveNav("lohablamos");
    await handleSendChatQuestion(pista.helperPrompt);
  };

  const handleSendChatQuestion = async (questionText) => {
    const q = (questionText || "").trim();
    if (!q || !token) return;
    setChatHistory((prev) => [...prev, { sender: "user", text: q }]);
    setChatLoading(true);
    try {
      const res = await sendMcpChatQuestion(token, q);
      const trace = res.mcp_trace || {};
      setChatHistory((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: res.reply || res.answer,
        },
      ]);
    } catch (_err) {
      setChatHistory((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "No se pudo obtener respuesta del asistente en este momento. Por favor, intenta de nuevo en unos instantes.",
          sql: null,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleChatFormSubmit = (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const q = chatInput.trim();
    setChatInput("");
    handleSendChatQuestion(q);
  };

  const handleLoadSampleData = async () => {
    if (!token || dataBusy) return;
    setDataBusy(true);
    try {
      const res = await loadSampleDatasetApi(token);
      const refreshed = await fetchDashboardPanel(token);
      setPanelData(refreshed);
      setDashboardRefresh((k) => k + 1);
      setSelectedPistaIdx(0);
      showToast(res.message || "30 estudiantes cargados en la base de datos.");
    } catch (err) {
      showToast(err.message || "Error al cargar datos de prueba.");
    } finally {
      setDataBusy(false);
    }
  };

  const handleClearDatabase = async () => {
    if (!token || dataBusy) return;
    setDataBusy(true);
    try {
      const res = await clearDatasetApi(token);
      const refreshed = await fetchDashboardPanel(token);
      setPanelData(refreshed);
      setDashboardRefresh((k) => k + 1);
      setSelectedPistaIdx(0);
      showToast(res.message || "Base de datos vaciada (0 registros).");
    } catch (err) {
      showToast(err.message || "Error al vaciar la base de datos.");
    } finally {
      setDataBusy(false);
    }
  };

  const handleUploadCsvFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;
    setDataBusy(true);
    try {
      const res = await uploadCsvDatasetApi(token, file);
      const refreshed = await fetchDashboardPanel(token);
      setPanelData(refreshed);
      setDashboardRefresh((k) => k + 1);
      setSelectedPistaIdx(0);
      showToast(res.message || "Archivo CSV importado correctamente.");
    } catch (err) {
      showToast(err.message || "Error al importar el archivo CSV.");
    } finally {
      setDataBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const totalAlumnos = panelData?.db_status?.total_alumnos_cargados ?? 0;
  const sqlSecurity = panelData?.sql_security || {};
  const grantedViewsText = (sqlSecurity.granted_views || ["vista_docente"]).join(", ");
  const roleInfo = ROLE_META[activeRole] || ROLE_META.docente;
  const actionsLog = panelData?.acciones_humanas || [];

  return (
    <div className="edusight-shell">
      {/* ====================================================================
          BARRA LATERAL IZQUIERDA (DISEÑO FIGMA EDUSIGHT · DONPROFESOR)
         ==================================================================== */}
      <aside className="edusight-sidebar" aria-label="Navegación principal">
        <div>
          <div className="edusight-brand">
            {/* Isotipo digital del libro inteligente DonProfesor */}
            <img
              src={logoLibro}
              alt="DonProfesor"
              className="edusight-brand-logo"
            />
            <div>
              <div className="edusight-brand-name">DONPROFESOR</div>
              <div className="edusight-brand-sub">AGENTE EDUCATIVO</div>
            </div>
          </div>

          <div className="edusight-nav-kicker">TU ESPACIO</div>
          <nav className="edusight-nav-list">
            <button
              type="button"
              className={`edusight-nav-btn ${activeNav === "revisar" ? "active" : ""}`}
              onClick={() => setActiveNav("revisar")}
            >
              <span className="edusight-nav-btn-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="16" rx="2" />
                  <path d="M8 12l3 3 5-5" />
                </svg>
                <span>Para revisar</span>
              </span>
              <span className="edusight-nav-badge">{activePistas.length}</span>
            </button>

            <button
              type="button"
              className={`edusight-nav-btn ${activeNav === "comovamos" ? "active" : ""}`}
              onClick={() => setActiveNav("comovamos")}
            >
              <span className="edusight-nav-btn-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 3v18h18" />
                  <path d="M7 15l4-4 4 3 5-6" />
                </svg>
                <span>Cómo vamos</span>
              </span>
              {totalAlumnos > 0 && <span className="edusight-nav-badge">{totalAlumnos}</span>}
            </button>

            <button
              type="button"
              className={`edusight-nav-btn ${activeNav === "predicciones" ? "active" : ""}`}
              onClick={() => setActiveNav("predicciones")}
            >
              <span className="edusight-nav-btn-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 7v5l3 3" />
                </svg>
                <span>Predicciones</span>
              </span>
            </button>

            <button
              type="button"
              className={`edusight-nav-btn ${activeNav === "lohablamos" ? "active" : ""}`}
              onClick={() => setActiveNav("lohablamos")}
            >
              <span className="edusight-nav-btn-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span>Lo hablamos</span>
              </span>
            </button>
          </nav>
        </div>

        <div className="edusight-sidebar-footer">
          <div className="edusight-motto">
            Más tiempo
            <br />
            para enseñar.
          </div>
          <div className="edusight-motto-sub">
            {user?.escuela_id ? `Centro escolar: ${user.escuela_id}` : "Entorno activo"}
            <br />
            Un apoyo para tu día a día.
          </div>
        </div>
      </aside>

      {/* ====================================================================
          ÁREA PRINCIPAL (TOPBAR + VISTAS + FOOTER ÉTICO)
         ==================================================================== */}
      <div className="edusight-main">
        {/* TOPBAR SUPERIOR */}
        <header className="edusight-topbar">
          <div className="topbar-left">
            <span className="status-dot" />
            <span className="scope-title">{roleInfo.scopeTitle}</span>

            <span className="db-pill" title="Estudiantes registrados en la plataforma">
              Estudiantes registrados: <strong>{totalAlumnos}</strong>
            </span>

            {totalAlumnos === 0 ? (
              <button
                type="button"
                className="btn-tiny-action"
                onClick={handleLoadSampleData}
                disabled={dataBusy}
              >
                {dataBusy ? "Cargando..." : "Cargar datos de demostración"}
              </button>
            ) : (
              <button
                type="button"
                className="btn-tiny-action"
                onClick={handleClearDatabase}
                disabled={dataBusy}
              >
                {dataBusy ? "Limpiando..." : "Limpiar datos"}
              </button>
            )}

            <button
              type="button"
              className="btn-tiny-action"
              onClick={() => fileInputRef.current?.click()}
              disabled={dataBusy}
            >
              Importar CSV
            </button>
            <button
              type="button"
              className="btn-tiny-action"
              onClick={() => setStudentModalOpen(true)}
              disabled={dataBusy}
            >
              + Añadir estudiante
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              onChange={handleUploadCsvFile}
            />
          </div>

          <div className="topbar-right">
            <div className="session-chip" title={user?.titulo_cargo || ""}>
              <span className="session-name">{user?.nombre_completo || user?.username}</span>
              <span className="session-role">{ROLE_META[activeRole]?.label || activeRole}</span>
            </div>
            <button type="button" className="btn-outline-calm btn-logout" onClick={() => onLogout?.()}>
              Cerrar sesión
            </button>
          </div>
        </header>

        {/* AVISO FLOTANTE DE CONFIRMACIÓN */}
        {toastMsg && (
          <div
            style={{
              background: "#1f6351",
              color: "#ffffff",
              padding: "10px 44px",
              fontSize: "13px",
              fontWeight: 500,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>{toastMsg}</span>
            <button
              type="button"
              onClick={() => setToastMsg(null)}
              style={{
                background: "transparent",
                border: "none",
                color: "#ffffff",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Cerrar
            </button>
          </div>
        )}

        {error && (
          <div
            style={{
              background: "#fef2f2",
              color: "#991b1b",
              padding: "12px 44px",
              borderBottom: "1px solid #fecaca",
              fontSize: "13px",
            }}
          >
            {error}
          </div>
        )}

        {/* ==================================================================
            VISTA 1: "PARA REVISAR" (FIEL AL DISEÑO DE FIGMA)
           ================================================================== */}
        {activeNav === "revisar" && (
          <main className="edusight-content">
            <div className="section-kicker">TU DÍA A DÍA</div>
            <h1 className="hero-serif-title">Un poco de atención hace mucho.</h1>
            <p className="hero-subtitle">{roleInfo.heroSubtitle}</p>

            {activePistas.length === 0 ? (
              <div
                className="calm-card"
                style={{
                  padding: "48px 32px",
                  textAlign: "center",
                  maxWidth: "640px",
                  margin: "40px auto",
                  background: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e2ded4",
                  boxShadow: "0 2px 12px rgba(0,0,0,0.03)",
                }}
              >
                <div
                  style={{
                    width: "56px",
                    height: "56px",
                    borderRadius: "50%",
                    background: "#eef5f2",
                    color: "#1f6351",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 20px",
                  }}
                >
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                </div>
                <h3
                  style={{
                    fontFamily: "Newsreader, serif",
                    fontSize: "24px",
                    color: "#192823",
                    marginBottom: "10px",
                    fontWeight: 500,
                  }}
                >
                  Sin alertas prioritarias pendientes
                </h3>
                <p
                  style={{
                    color: "#5a7066",
                    fontSize: "14px",
                    lineHeight: "1.6",
                    marginBottom: "28px",
                    maxWidth: "520px",
                    marginLeft: "auto",
                    marginRight: "auto",
                  }}
                >
                  Actualmente no hay estudiantes con avisos de acompañamiento prioritario registrados. En cuanto importes el archivo con las calificaciones y asistencia de tu grupo, el sistema identificará qué alumnos pueden necesitar apoyo personalizado.
                </p>
                <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn-forest"
                    style={{ padding: "10px 20px", fontSize: "14px", cursor: "pointer" }}
                    onClick={() => setStudentModalOpen(true)}
                  >
                    + Registrar estudiante
                  </button>
                  <button
                    type="button"
                    className="btn-outline-calm"
                    style={{ padding: "10px 20px", fontSize: "14px", cursor: "pointer" }}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Importar archivo CSV
                  </button>
                  <button
                    type="button"
                    className="btn-outline-calm"
                    style={{ padding: "10px 20px", fontSize: "14px", cursor: "pointer" }}
                    onClick={handleLoadSampleData}
                    disabled={dataBusy}
                  >
                    {dataBusy ? "Cargando..." : "Cargar datos de demostración"}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="master-detail-header">
                  <span className="master-detail-header-left">
                    {activePistas.length} situaciones que conviene revisar
                  </span>
                  <span className="master-detail-header-right">Elige una para verla con calma</span>
                </div>

                <div className="master-detail-grid">
                  {/* LISTA IZQUIERDA */}
                  <div className="master-list">
                {activePistas.map((pista, idx) => {
                  const isSelected = idx === selectedPistaIdx;
                  const numStr = String(idx + 1).padStart(2, "0");
                  const isDone =
                    completedIds[pista.id] ||
                    pista.estado_revision === "Revisado";

                  return (
                    <button
                      key={pista.id}
                      type="button"
                      className={`pista-card ${isSelected ? "selected" : ""}`}
                      onClick={() => {
                        setSelectedPistaIdx(idx);
                        setAccompanimentOpen(false);
                      }}
                    >
                      <div className="pista-card-top">
                        <span>
                          {pista.kickerCard}
                          {isDone && (
                            <strong style={{ color: "#1f6351", marginLeft: "6px" }}>
                              · Acompañado
                            </strong>
                          )}
                        </span>
                        <span className="pista-num">{numStr}</span>
                      </div>
                      <div className="pista-title">{pista.title}</div>
                      <div className="pista-link">
                        <span>Ver qué está pasando</span>
                        <span aria-hidden="true">&rarr;</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* DETALLE DERECHO */}
              {currentPista && (
                <div className="detail-panel">
                  <div className="detail-kicker">
                    {currentPista.kickerDetail} · {selectedPistaIdx + 1} DE {activePistas.length}
                  </div>
                  <h2 className="detail-serif-title">{currentPista.title}</h2>
                  <p className="detail-lead">{currentPista.lead}</p>

                  <hr className="detail-divider" />

                  <div className="factors-section-title">Qué puede estar influyendo</div>

                  {currentPista.factors.length === 0 && (
                    <p className="factors-disclaimer">El modelo no ha destacado factores concretos para este estudiante.</p>
                  )}
                  {currentPista.factors.map((f, fIdx) => (
                    <div className="factor-bar-item" key={fIdx}>
                      <div className="factor-bar-header">
                        <span>{f.label}</span>
                        <span className="factor-bar-pct">{f.pct}%</span>
                      </div>
                      <div className="factor-bar-track">
                        <div
                          className="factor-bar-fill"
                          style={{ width: `${Math.min(100, Math.max(5, f.pct))}%` }}
                        />
                      </div>
                    </div>
                  ))}

                  <p className="factors-disclaimer">
                    El porcentaje indica cuánto pesa cada factor en la sugerencia del modelo para este estudiante; no es una probabilidad. Una conversación ayuda a entender lo que los datos no cuentan.
                  </p>

                  <div className="detail-actions-row">
                    <button
                      type="button"
                      className="btn-forest"
                      onClick={() => setAccompanimentOpen((prev) => !prev)}
                    >
                      Anotar cómo le vas a acompañar
                    </button>

                    <button
                      type="button"
                      className="btn-link-underline"
                      onClick={() => handleAskHelperAboutPista(currentPista)}
                    >
                      Pensarlo con el ayudante &#8599;
                    </button>
                  </div>

                  <div className="detail-footnote">
                    No se enviará ningún mensaje ni se tomará una decisión por ti.
                  </div>

                  {/* FORMULARIO DESPLEGABLE PARA GUARDAR EN LA BD REAL */}
                  {accompanimentOpen && (
                    <form
                      className="accompaniment-inline-box"
                      onSubmit={handleSaveAccompaniment}
                    >
                      <div
                        style={{
                          fontSize: "13px",
                          fontWeight: 600,
                          color: "#1c2a24",
                          marginBottom: "10px",
                        }}
                      >
                        Registrar acuerdo de acompañamiento ({currentPista.kickerCard})
                      </div>

                      <div className="form-group" style={{ marginTop: "8px" }}>
                        <label htmlFor="select-acomp">Medida pedagógica elegida por ti</label>
                        <select
                          id="select-acomp"
                          className="form-select"
                          value={decisionText}
                          required
                          onChange={(e) => setDecisionText(e.target.value)}
                        >
                          <option value="">— Elige una medida —</option>
                          {Array.from(
                            new Set(
                              [
                                currentPista.defaultDecision,
                                "Conversación cercana con la familia y entrega de guía impresa",
                                "Flexibilización temporal de entregas y plazos",
                                "Reserva de equipamiento sin conexión para refuerzo en aula",
                                "Refuerzo académico en grupos pequeños y tutoría individual",
                                "Descartar pista tras contrastar el contexto directo en el aula",
                              ].filter(Boolean)
                            )
                          ).map((op) => (
                            <option key={op} value={op}>
                              {op}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor="notes-acomp">Tu nota personal (opcional)</label>
                        <textarea
                          id="notes-acomp"
                          className="form-textarea"
                          rows={3}
                          placeholder="Escribe aquí lo que has hablado con el estudiante o su familia..."
                          value={commentText}
                          onChange={(e) => setCommentText(e.target.value)}
                        />
                      </div>

                      <div
                        style={{
                          display: "flex",
                          gap: "10px",
                          marginTop: "14px",
                        }}
                      >
                        <button
                          type="submit"
                          className="btn-forest"
                          style={{ padding: "9px 16px" }}
                          disabled={savingAction}
                        >
                          {savingAction ? "Guardando..." : "Guardar en Base de Datos"}
                        </button>
                        <button
                          type="button"
                          className="btn-outline-calm"
                          onClick={() => setAccompanimentOpen(false)}
                        >
                          Cancelar
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              )}
            </div>
            </>
            )}
          </main>
        )}

        {/* ==================================================================
            VISTA 2: "CÓMO VAMOS" (ANALÍTICA SQL EN VIVO, 37 VARIABLES, SIMULADOR)
           ================================================================== */}
        {activeNav === "comovamos" && (
          <>
            <RoleDashboard
              token={token}
              role={activeRole}
              onUnauthorized={handleSessionExpired}
              refreshKey={dashboardRefresh}
            />
            {activeRole === "delegado" && (
              <main className="edusight-content" style={{ paddingTop: 0 }}>
                <DelegadoTerritorialView token={token} />
              </main>
            )}
          </>
        )}

        {/* ==================================================================
            VISTA 3: "PREDICCIONES" (MODELO LIGHTGBM + RANDOM FOREST POR ROL)
           ================================================================== */}
        {activeNav === "predicciones" && (
          <PredictionsView
            token={token}
            role={activeRole}
            onUnauthorized={handleSessionExpired}
            refreshKey={dashboardRefresh}
            onChanged={loadRoleData}
          />
        )}

        {/* ==================================================================
            VISTA 4: "LO HABLAMOS" (CHAT AGENTE REACT LANGGRAPH + MCP + QWEN)
           ================================================================== */}
        {activeNav === "lohablamos" && (
          <main className="edusight-content">
            <div className="section-kicker">ORIENTACIÓN Y CONSULTA PEDAGÓGICA</div>
            <h1 className="hero-serif-title">Lo hablamos con calma.</h1>
            <p className="hero-subtitle">
              Conversa con el asistente para comprender mejor la situación de tu grupo o centro. Las respuestas se basan exclusivamente en los datos de tu ámbito escolar.
            </p>

            <div className="chat-workspace-grid">
              {/* COLUMNA IZQUIERDA: CONVERSACIÓN */}
              <div className="chat-main-box">
                <div className="chat-prompts-bar">
                  <div
                    style={{
                      fontSize: "11.5px",
                      fontWeight: 600,
                      color: "#5a7066",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Preguntas habituales en la vista de {roleInfo.label}:
                  </div>
                  <div className="prompt-chips">
                    {(CHAT_PRESETS[activeRole] || CHAT_PRESETS.docente).map((p, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="prompt-chip"
                        onClick={() => handleSendChatQuestion(p)}
                        disabled={chatLoading}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="chat-messages-area">
                  {chatHistory.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`msg-bubble ${
                        msg.sender === "user" ? "msg-user" : "msg-assistant"
                      }`}
                    >
                      <span className="msg-sender">
                        {msg.sender === "user"
                          ? "Tu consulta pedagógica"
                          : `Ayudante DONPROFESOR · Rol ${roleInfo.label}`}
                      </span>
                      <div style={{ whiteSpace: "pre-line" }}>{msg.text}</div>

                    </div>
                  ))}

                  {chatLoading && (
                    <div className="msg-bubble msg-assistant">
                      <span className="msg-sender">Asistente DONPROFESOR</span>
                      <div>Consultando los registros del aula...</div>
                    </div>
                  )}
                </div>

                <form className="chat-input-row" onSubmit={handleChatFormSubmit}>
                  <input
                    type="text"
                    className="chat-text-input"
                    placeholder="Escribe aquí tu consulta sobre asistencia, notas, becas o predicciones..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={chatLoading}
                  />
                  <button type="submit" className="btn-forest" disabled={chatLoading}>
                    Consultar
                  </button>
                </form>
              </div>

              {/* COLUMNA DERECHA: ASISTENTE EDUCATIVO Y REGISTRO DE DECISIONES */}
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div className="calm-card" style={{ marginBottom: 0, padding: "20px" }}>
                  <div
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      color: "#1f6351",
                      marginBottom: "8px",
                    }}
                  >
                    ASISTENTE PEDAGÓGICO DE AULA
                  </div>
                  <p style={{ fontSize: "13px", color: "#4e5d55", lineHeight: "1.5", margin: 0 }}>
                    Este espacio te orienta sobre la asistencia y rendimiento de tu grupo, ayudándote a contextualizar situaciones de vulnerabilidad o necesidades de acompañamiento.
                  </p>
                  <div
                    style={{
                      marginTop: "14px",
                      padding: "10px 12px",
                      background: llmStatus?.status === "ok" ? "#eef7f3" : "#fbf9f4",
                      borderRadius: "6px",
                      border: `1px solid ${llmStatus?.status === "ok" ? "#c8e6d9" : "#e8e3d6"}`,
                      fontSize: "12px",
                      color: llmStatus?.status === "ok" ? "#1b5e20" : "#6c5835",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <span
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: llmStatus?.status === "ok" ? "#2e7d32" : "#9e9e9e",
                        display: "inline-block",
                      }}
                    />
                    <span>
                      {llmStatus?.status === "ok"
                        ? "Asistente inteligente disponible"
                        : "Asistente en modo consulta escolar"}
                    </span>
                  </div>
                </div>

                <div className="calm-card" style={{ marginBottom: 0, padding: "20px" }}>
                  <div
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      color: "#5a7066",
                      marginBottom: "10px",
                    }}
                  >
                    ACOMPAÑAMIENTOS ANOTADOS ({actionsLog.length})
                  </div>
                  {actionsLog.length === 0 ? (
                    <div style={{ fontSize: "12.5px", color: "#6b7871" }}>
                      Aún no has registrado acuerdos en la base de datos. Puedes anotarlos desde &laquo;Para revisar&raquo;.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {actionsLog.slice(0, 5).map((a) => {
                        const studentLabel = a.alumno_id
                          ? (a.alumno_id.startsWith("ALU-") || a.alumno_id.startsWith("alu-")
                              ? `Estudiante ${a.alumno_id}`
                              : a.alumno_id)
                          : (a.prediccion_id ? `Estudiante ${a.prediccion_id}` : "Estudiante");
                        return (
                          <div
                            key={a.accion_id}
                            style={{
                              fontSize: "12.5px",
                              paddingBottom: "8px",
                              borderBottom: "1px solid #e8e7df",
                            }}
                          >
                            <strong style={{ color: "#1f6351" }}>{studentLabel}</strong>:{" "}
                            {a.decision_tomada}
                            {a.comentario_pedagogico && (
                              <div style={{ color: "#6b7871", fontSize: "11.5px", marginTop: "2px" }}>
                                {a.comentario_pedagogico}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </main>
        )}

        {/* ==================================================================
            PIE DE PÁGINA ÉTICO (FIEL AL DISEÑO DE FIGMA)
           ================================================================== */}
        <footer className="edusight-footer">
          <div>
            <span className="footer-strong-green">Tú conoces a tu grupo. Tú decides.</span>{" "}
            Esta ayuda puede equivocarse; no decide ni clasifica a estudiantes.
          </div>
          <button
            type="button"
            className="footer-about-link"
            onClick={() => setAboutModalOpen(true)}
          >
            Sobre esta ayuda
          </button>
        </footer>
      </div>

      {/* MODAL REGISTRO DE ESTUDIANTE (MANUAL O PEGAR EXCEL) */}
      {studentModalOpen && (
        <StudentEntryModal
          token={token}
          userRole={activeRole}
          currentSchoolId={user?.escuela_id}
          currentGrade={user?.grado_secundaria}
          currentUgel={user?.ugel}
          onClose={() => setStudentModalOpen(false)}
          onSuccess={(msg) => {
            showToast(msg);
            loadRoleData();
            setDashboardRefresh((k) => k + 1);
          }}
        />
      )}

      {/* MODAL "SOBRE ESTA AYUDA" */}
      {aboutModalOpen && (
        <div className="modal-backdrop" onClick={() => setAboutModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Sobre DONPROFESOR (#Hack4Edu 2026)</h3>
            <p style={{ fontSize: "13.5px", color: "#4e5d55", marginTop: "8px" }}>
              Esta plataforma acompaña a docentes, equipos directivos y coordinadores territoriales sin sustituir nunca el juicio profesional humano ni etiquetar a los estudiantes.
            </p>

            <div
              style={{
                marginTop: "16px",
                padding: "14px",
                background: "#f3f2ec",
                borderRadius: "6px",
                fontSize: "12.5px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <div>
                <strong>Perfil de acceso:</strong> {ROLE_META[activeRole]?.label || activeRole} ({roleInfo.scopeTitle})
              </div>
              <div>
                <strong>Estudiantes en seguimiento:</strong> {totalAlumnos} alumnos registrados
              </div>
              <div>
                <strong>Privacidad de aula:</strong> Consultas limitadas a tu ámbito de responsabilidad educativa.
              </div>
              <div>
                <strong>Acompañamiento humano:</strong> Las sugerencias son orientativas; la decisión final siempre es del docente.
              </div>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="btn-forest"
                onClick={() => setAboutModalOpen(false)}
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
