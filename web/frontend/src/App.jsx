import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  loginRole,
  fetchDashboardPanel,
  fetchMcpMetadata,
  sendMcpChatQuestion,
  registerPedagogicalAction,
  loadSampleDatasetApi,
  clearDatasetApi,
  uploadCsvDatasetApi,
  fetchLlmStatusApi,
  updateLlmConfigApi,
} from "./services/api.js";
import {
  DocenteContextTable,
  DirectorGroupsTable,
  DelegadoTerritorialView,
} from "./components/RoleViews.jsx";
import { RainHarvestChart } from "./components/RainHarvestChart.jsx";

/* ==========================================================================
   PISTAS INTERACTIVAS DE REFERENCIA (FIGMA) POR ROL
   Permiten usar y probar el flujo completo incluso con la BD en 0 registros,
   y se combinan con las alertas reales cuando se importan datos en la BD.
   ========================================================================== */

const FIGMA_PISTAS_BY_ROLE = {
  docente: [
    {
      id: "A-204",
      alumno_id: "A-204",
      kickerCard: "Estudiante A-204",
      kickerDetail: "ESTUDIANTE A-204",
      title: "Las notas han bajado 1,4 puntos",
      lead: "Las ausencias durante la cosecha y el camino hasta la escuela pueden estar influyendo.",
      factors: [
        { label: "Faltas en semanas de cosecha", pct: 42 },
        { label: "Más de 4,2 km en días de lluvia", pct: 35 },
        { label: "Sin dispositivo ni internet en casa", pct: 23 },
      ],
      defaultDecision: "Adaptación temporal de entregas durante semanas de cosecha y lluvia",
      helperPrompt:
        "Estoy revisando el caso del Estudiante A-204: sus notas han bajado 1,4 puntos y acumula faltas en semanas de cosecha viviendo a más de 4,2 km. ¿Qué medidas de acompañamiento me sugieres?",
    },
    {
      id: "A-219",
      alumno_id: "A-219",
      kickerCard: "Estudiante A-219",
      kickerDetail: "ESTUDIANTE A-219",
      title: "Su progreso se mantiene estable gracias a la beca",
      lead: "El apoyo del programa Juntos y el seguimiento familiar están sosteniendo su asistencia por encima del 88%.",
      factors: [
        { label: "Asistencia continuada con beca Juntos", pct: 55 },
        { label: "Apoyo familiar en estudio semanal", pct: 28 },
        { label: "Distancia moderada al centro (2,1 km)", pct: 17 },
      ],
      defaultDecision: "Refuerzo positivo en tutoría familiar y seguimiento de beca Juntos",
      helperPrompt:
        "El Estudiante A-219 mantiene su progreso estable gracias a la beca Juntos. ¿Cómo podemos consolidar este efecto protector en la tutoría?",
    },
    {
      id: "AULA-2B-TABLETS",
      alumno_id: "AULA-2B",
      kickerCard: "Oportunidad para tu aula",
      kickerDetail: "OPORTUNIDAD PARA TU AULA",
      title: "Tablets sin conexión libres el jueves a tercera hora",
      lead: "El lote de tablets con material precargado está disponible para reforzar con quienes no tienen internet en casa.",
      factors: [
        { label: "Alumnado del grupo sin internet en el hogar", pct: 48 },
        { label: "Contenidos offline sincronizados para 2°B", pct: 32 },
        { label: "Disponibilidad de aula móvil este jueves", pct: 20 },
      ],
      defaultDecision: "Reserva de tablets sin conexión el jueves a 3ª hora para refuerzo",
      helperPrompt:
        "Tenemos tablets sin conexión libres el jueves a tercera hora para 2°B. ¿Cómo organizo la sesión para apoyar al alumnado sin internet en casa?",
    },
  ],
  director: [
    {
      id: "COHORTE-3SEC",
      alumno_id: "GRADO-3SEC",
      kickerCard: "Cohorte 3° Secundaria",
      kickerDetail: "COHORTE 3° SECUNDARIA",
      title: "La asistencia baja un 11% en semanas de lluvia intensa",
      lead: "El alumnado que se desplaza desde veredas rurales a más de 3 km concentra la mayor parte de ausencias.",
      factors: [
        { label: "Trayectos rurales superiores a 3,5 km", pct: 46 },
        { label: "Coincidencia con calendario agrícola local", pct: 34 },
        { label: "Hogar sin conectividad para aviso previo", pct: 20 },
      ],
      defaultDecision: "Activación de calendario flexible y guías impresas en semanas de lluvia",
      helperPrompt:
        "En dirección vemos que 3° de Secundaria baja su asistencia en semanas de lluvia y cosecha. ¿Qué medidas organizativas podemos coordinar en el centro?",
    },
    {
      id: "RECURSOS-OFFLINE",
      alumno_id: "CENTRO-VALLE-VERDE",
      kickerCard: "Equipamiento del centro",
      kickerDetail: "EQUIPAMIENTO DEL CENTRO",
      title: "Margen para ampliar el préstamo de material offline",
      lead: "El 38% de las tablets con recursos locales tiene horas libres los martes y jueves por la mañana.",
      factors: [
        { label: "Estudiantes sin conectividad doméstica", pct: 50 },
        { label: "Horas disponibles de carrito de tablets", pct: 30 },
        { label: "Docentes con taller de uso pedagógico", pct: 20 },
      ],
      defaultDecision: "Redistribución horaria de tablets sin conexión para 2° y 3° de Secundaria",
      helperPrompt:
        "¿Qué brecha hay entre dispositivos disponibles y uso real por grupo en nuestro centro educativo?",
    },
    {
      id: "PROTECCION-JUNTOS",
      alumno_id: "BECAS-CENTRO",
      kickerCard: "Continuidad educativa",
      kickerDetail: "CONTINUIDAD EDUCATIVA",
      title: "Seguimiento preventivo de requisitos de beca Juntos",
      lead: "Revisar a tiempo las ausencias justificadas evita que 6 familias pierdan el subsidio escolar este trimestre.",
      factors: [
        { label: "Faltas pendientes de justificación médica o climática", pct: 45 },
        { label: "Riesgo estadístico de pérdida de subsidio", pct: 35 },
        { label: "Necesidad de contacto con tutoría familiar", pct: 20 },
      ],
      defaultDecision: "Coordinación con tutores para actualizar justificaciones de asistencia",
      helperPrompt:
        "¿Qué grupos del centro concentran mayor riesgo de pérdida de beca Juntos y cómo podemos prevenirlo?",
    },
  ],
  delegado: [
    {
      id: "UGEL-RURAL-SUR",
      alumno_id: "RED-RURAL-SUR",
      kickerCard: "Red Rural Andina Sur",
      kickerDetail: "RED RURAL ANDINA SUR",
      title: "Prioridad de transporte escolar en 4 centros rurales",
      lead: "Las escuelas con distancia media superior a 4 km muestran la mayor sensibilidad climática en asistencia.",
      factors: [
        { label: "Distancia hogar-escuela superior a 4 km", pct: 49 },
        { label: "Impacto de lluvias en caminos vecinales", pct: 31 },
        { label: "Población beneficiaria del programa Juntos", pct: 20 },
      ],
      defaultDecision: "Focalización de partida de transporte y comedor rural en 4 centros",
      helperPrompt:
        "¿Qué escuelas rurales de la UGEL tienen menor conectividad y mayor distancia media de desplazamiento?",
    },
    {
      id: "SERVIDORES-OFFLINE-UGEL",
      alumno_id: "RED-CONECTIVIDAD",
      kickerCard: "Infraestructura pedagógica",
      kickerDetail: "INFRAESTRUCTURA PEDAGÓGICA",
      title: "Servidores locales sin internet para zonas sin cobertura",
      lead: "Instalar repositorios offline en centros rurales compensa la falta de internet doméstico en el 72% del alumnado.",
      factors: [
        { label: "Hogares rurales sin acceso a internet", pct: 54 },
        { label: "Aprovechamiento de equipamiento ya entregado", pct: 28 },
        { label: "Acompañamiento técnico a docentes", pct: 18 },
      ],
      defaultDecision: "Dotación de servidores de contenido offline y talleres docentes",
      helperPrompt:
        "¿Dónde hay mayor brecha entre equipamiento disponible y conectividad en las escuelas de la red?",
    },
    {
      id: "FORMACION-DOCENTE-RED",
      alumno_id: "RED-FORMACION",
      kickerCard: "Acompañamiento docente",
      kickerDetail: "ACOMPAÑAMIENTO DOCENTE",
      title: "Comunidades de práctica entre escuelas cercanas",
      lead: "Los centros que comparten materiales adaptados al calendario agrícola mejoran un 9% la retención en T3.",
      factors: [
        { label: "Adaptación curricular en época de cosecha", pct: 44 },
        { label: "Horas de co-docencia entre centros", pct: 33 },
        { label: "Estabilidad de calificaciones en T2 y T3", pct: 23 },
      ],
      defaultDecision: "Impulso de red de intercambio pedagógico entre escuelas de la UGEL",
      helperPrompt:
        "¿Cómo se distribuye la asistencia y el rendimiento entre centros urbanos y rurales de la UGEL?",
    },
  ],
};

const ROLE_META = {
  docente: {
    label: "Docente",
    scopeTitle: "Aula 2°B · I.E. Valle Verde",
    heroSubtitle: "Tres pistas para acompañar a tu grupo esta semana. Tú eliges por dónde empezar.",
  },
  director: {
    label: "Director",
    scopeTitle: "Dirección · I.E. Valle Verde",
    heroSubtitle: "Tres prioridades del centro educativo para coordinar con tu equipo docente esta semana.",
  },
  delegado: {
    label: "Delegado",
    scopeTitle: "UGEL Sur · Red de 12 Escuelas",
    heroSubtitle: "Tres focos territoriales para orientar recursos de transporte, becas y conectividad rural.",
  },
};

const CHAT_PRESETS = {
  docente: [
    "¿Qué alumnos faltan cuando llueve y viven a más de 3 km?",
    "¿Cómo influye la cosecha y el apoyo laboral en las entregas?",
    "¿Cuál es el efecto protector de la beca en mi tutoría?",
    "¿Qué situaciones prioritarias sugiere revisar el modelo?",
  ],
  director: [
    "¿Cómo se superponen asistencia, lluvia y semanas de cosecha?",
    "¿Qué brecha hay entre dispositivos disponibles y uso real por grupo?",
    "¿Qué grados tienen más casos de prioridad alta en el centro?",
    "¿Qué grupos tienen menor asistencia en el segundo trimestre?",
  ],
  delegado: [
    "¿Qué escuelas rurales tienen menor conectividad y uso de recursos?",
    "¿Cómo se distribuye la asistencia entre centros urbanos y rurales?",
    "¿Dónde priorizar becas de transporte escolar según la distancia?",
    "¿Qué escuelas concentran más casos de prioridad de acompañamiento?",
  ],
};

function mapDbAlertToPista(item, index) {
  const code = item.codigo_seguimiento || item.alumno_id || item.prediccion_id || `ALU-${index + 1}`;
  return {
    id: item.prediccion_id || code,
    alumno_id: code,
    kickerCard: `Estudiante ${code}`,
    kickerDetail: `ESTUDIANTE ${code}`,
    title: item.titulo_humano || `Prioridad de acompañamiento (${code})`,
    lead:
      item.descripcion_situacion ||
      item.recomendacion_pedagogica ||
      "Observación generada a partir de las variables de asistencia, desplazamiento y rendimiento.",
    factors: [
      {
        label: item.factor_1_texto || "Ausentismo acumulado en trimestres previos",
        pct: Number(item.factor_1_peso) || 45,
      },
      {
        label: item.factor_2_texto || "Distancia hogar-escuela y tiempo de traslado",
        pct: 35,
      },
      {
        label: item.factor_3_texto || "Contexto socioeconómico y conectividad en hogar",
        pct: 20,
      },
    ],
    defaultDecision:
      item.recomendacion_pedagogica ||
      "Adaptación temporal de entregas y tutoría con la familia",
    helperPrompt: `Analiza la situación del estudiante ${code} en la base de datos (${item.titulo_humano || "riesgo detectado"}) y dime qué factores influyen y cómo acompañarle.`,
    fromDatabase: true,
    estado_revision: item.estado_revision,
  };
}

export function App() {
  const [activeRole, setActiveRole] = useState("docente");
  const [activeNav, setActiveNav] = useState("revisar"); // "revisar" | "comovamos" | "lohablamos"
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
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

  // Modal "Sobre esta ayuda" / Configuración LLM & Datos
  const [aboutModalOpen, setAboutModalOpen] = useState(false);
  const [llmUrlInput, setLlmUrlInput] = useState("http://172.25.144.238:8001/v1");
  const [llmModelInput, setLlmModelInput] = useState("donprofesor-llm");
  const [llmKeyInput, setLlmKeyInput] = useState("");
  const [savingLlm, setSavingLlm] = useState(false);
  const [dataBusy, setDataBusy] = useState(false);
  const fileInputRef = useRef(null);

  // Chat state ("Lo hablamos")
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "assistant",
      text: "Hola. Estoy conectado al servidor MCP de base de datos y al agente ReAct (LangGraph). Puedes consultarme sobre cualquier estudiante, tendencia de asistencia, impacto de lluvia y cosecha o becas Juntos.",
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

  const authenticateAndLoadRole = useCallback(async (roleToLoad) => {
    setLoading(true);
    setError(null);
    try {
      const authRes = await loginRole(roleToLoad, "donprofesor2026");
      setToken(authRes.access_token);
      setUser(authRes.user);
      setActiveRole(roleToLoad);
      setSelectedPistaIdx(0);
      setAccompanimentOpen(false);

      const [panelRes, mcpRes, llmRes] = await Promise.all([
        fetchDashboardPanel(authRes.access_token),
        fetchMcpMetadata(authRes.access_token),
        fetchLlmStatusApi(authRes.access_token).catch(() => null),
      ]);
      setPanelData(panelRes);
      setMcpMeta(mcpRes);
      if (llmRes) {
        setLlmStatus(llmRes);
        if (llmRes.base_url) setLlmUrlInput(llmRes.base_url);
        if (llmRes.model_name) setLlmModelInput(llmRes.model_name);
      }
    } catch (err) {
      setError(err.message || "Error al conectar con el servidor de DONPROFESOR");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    authenticateAndLoadRole("docente");
  }, [authenticateAndLoadRole]);

  const handleSelectRole = async (newRole) => {
    if (newRole === activeRole && token) return;
    await authenticateAndLoadRole(newRole);
    setChatHistory([
      {
        sender: "assistant",
        text: `Has cambiado a la vista de ${ROLE_META[newRole]?.label || newRole}. El servidor MCP consulta ahora exclusivamente las vistas SQL autorizadas para tu rol.`,
        sql: null,
        rowsCount: 0,
      },
    ]);
  };

  // Construir lista de pistas (de la BD real si hay filas, o las 3 pistas interactivas de Figma si la BD tiene 0 filas)
  const dbAlerts = panelData?.avisos_predictivos || [];
  const activePistas =
    dbAlerts.length > 0
      ? dbAlerts.slice(0, 6).map(mapDbAlertToPista)
      : FIGMA_PISTAS_BY_ROLE[activeRole] || FIGMA_PISTAS_BY_ROLE.docente;

  const currentPista = activePistas[selectedPistaIdx] || activePistas[0];

  useEffect(() => {
    if (currentPista) {
      setDecisionText(currentPista.defaultDecision);
      setCommentText("");
    }
  }, [currentPista]);

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
          sql: trace.sql_executed || res.sql_executed,
          rowsCount: trace.rows_returned ?? 0,
          mcpTrace: trace,
        },
      ]);
    } catch (_err) {
      setChatHistory((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "No se pudo completar la consulta en el servidor MCP en este momento.",
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
      setSelectedPistaIdx(0);
      showToast(res.message || "Archivo CSV importado correctamente.");
    } catch (err) {
      showToast(err.message || "Error al importar el archivo CSV.");
    } finally {
      setDataBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSaveLlmConfig = async (e) => {
    e.preventDefault();
    if (!token) return;
    setSavingLlm(true);
    try {
      const updated = await updateLlmConfigApi(token, {
        base_url: llmUrlInput,
        model_name: llmModelInput,
        api_key: llmKeyInput,
      });
      setLlmStatus(updated);
      showToast("Configuración de Qwen / vLLM actualizada.");
    } catch (err) {
      showToast(err.message || "No se pudo actualizar la configuración del LLM.");
    } finally {
      setSavingLlm(false);
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
            {/* Icono vectorial del Faro Educativo (fiel al diseño de Figma) */}
            <svg
              width="34"
              height="38"
              viewBox="0 0 34 38"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M13 13H21L23 34H11L13 13Z"
                stroke="#1F6351"
                strokeWidth="1.7"
                strokeLinejoin="round"
              />
              <path d="M9 34H25" stroke="#1F6351" strokeWidth="1.7" strokeLinecap="round" />
              <rect
                x="14"
                y="7"
                width="6"
                height="6"
                stroke="#1F6351"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path
                d="M12 7L17 3L22 7"
                stroke="#1F6351"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M4 10L9 10" stroke="#1F6351" strokeWidth="1.6" strokeLinecap="round" />
              <path d="M25 10L30 10" stroke="#1F6351" strokeWidth="1.6" strokeLinecap="round" />
              <path d="M5.5 5.5L9.5 7.5" stroke="#1F6351" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M28.5 5.5L24.5 7.5" stroke="#1F6351" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M12.2 21H21.8" stroke="#1F6351" strokeWidth="1.4" />
              <path d="M11.6 28H22.4" stroke="#1F6351" strokeWidth="1.4" />
            </svg>
            <div>
              <div className="edusight-brand-name">EduSight</div>
              <div className="edusight-brand-sub">FARO EDUCATIVO</div>
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
            Región Andina Sur
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

            <span className="db-pill" title="Estado en tiempo real de la tabla alumnos_hack4edu">
              BD Real: <strong>{totalAlumnos} estudiantes</strong>
            </span>

            {totalAlumnos === 0 ? (
              <button
                type="button"
                className="btn-tiny-action"
                onClick={handleLoadSampleData}
                disabled={dataBusy}
              >
                {dataBusy ? "Cargando..." : "Cargar 30 alumnos de prueba"}
              </button>
            ) : (
              <button
                type="button"
                className="btn-tiny-action"
                onClick={handleClearDatabase}
                disabled={dataBusy}
              >
                {dataBusy ? "Vaciando..." : "Vaciar BD (0 alumnos)"}
              </button>
            )}

            <button
              type="button"
              className="btn-tiny-action"
              onClick={() => fileInputRef.current?.click()}
              disabled={dataBusy}
            >
              Subir CSV
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
            <span className="role-switch-label">Estás en la vista de</span>
            <div className="role-tabs-group" role="tablist" aria-label="Cambiar rol activo">
              {["docente", "director", "delegado"].map((rKey) => (
                <button
                  key={rKey}
                  type="button"
                  role="tab"
                  aria-selected={activeRole === rKey}
                  className={`role-tab-link ${activeRole === rKey ? "active" : ""}`}
                  onClick={() => handleSelectRole(rKey)}
                >
                  {ROLE_META[rKey].label}
                </button>
              ))}
            </div>
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

            <div className="master-detail-header">
              <span className="master-detail-header-left">
                {activePistas.length === 3
                  ? "Tres cosas que conviene mirar"
                  : `${activePistas.length} situaciones que conviene mirar`}
                {totalAlumnos === 0 && (
                  <span
                    style={{
                      marginLeft: "10px",
                      fontSize: "11.5px",
                      fontWeight: 500,
                      color: "#5a7066",
                      background: "#e4eee9",
                      padding: "2px 8px",
                      borderRadius: "4px",
                    }}
                  >
                    Casos interactivos de referencia (BD en 0 filas)
                  </span>
                )}
              </span>
              <span className="master-detail-header-right">Elige una para verla con calma</span>
            </div>

            <div className="master-detail-grid">
              {/* LISTA IZQUIERDA (01, 02, 03) */}
              <div className="master-list">
                {activePistas.map((pista, idx) => {
                  const isSelected = idx === selectedPistaIdx;
                  const numStr = String(idx + 1).padStart(2, "0");
                  const isDone =
                    completedIds[pista.id] ||
                    pista.estado_revision === "Acuerdo registrado";

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
                    Estas cifras son orientativas. Una conversación ayuda a entender lo que los datos no cuentan.
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
                          onChange={(e) => setDecisionText(e.target.value)}
                        >
                          <option value={currentPista.defaultDecision}>
                            {currentPista.defaultDecision}
                          </option>
                          <option value="Conversación cercana con la familia y entrega de guía impresa">
                            Conversación cercana con la familia y entrega de guía impresa
                          </option>
                          <option value="Flexibilización de entregas en semanas de lluvia o cosecha">
                            Flexibilización de entregas en semanas de lluvia o cosecha
                          </option>
                          <option value="Reserva de equipamiento sin conexión para refuerzo en aula">
                            Reserva de equipamiento sin conexión para refuerzo en aula
                          </option>
                          <option value="Descartar pista tras contrastar el contexto directo en el aula">
                            Descartar pista tras contrastar el contexto directo en el aula
                          </option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor="notes-acomp">Tu nota personal (opcional)</label>
                        <textarea
                          id="notes-acomp"
                          className="form-textarea"
                          rows={2}
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
          </main>
        )}

        {/* ==================================================================
            VISTA 2: "CÓMO VAMOS" (ANALÍTICA SQL EN VIVO, 37 VARIABLES, SIMULADOR)
           ================================================================== */}
        {activeNav === "comovamos" && (
          <main className="edusight-content">
            <div className="section-kicker">PANORAMA DEL GRUPO Y CONTEXTO</div>
            <h1 className="hero-serif-title">Cómo vamos esta semana.</h1>
            <p className="hero-subtitle">
              Indicadores calculados mediante SQL sobre las 37 variables oficiales de Hack4Edu (Reto 13) para la vista de {roleInfo.label}.
            </p>

            {/* KPIs */}
            <div className="kpi-calm-grid">
              {(panelData?.kpis || []).map((k, idx) => (
                <div className="kpi-calm-card" key={idx}>
                  <div className="kpi-calm-label">{k.label}</div>
                  <div className="kpi-calm-value">{k.value}</div>
                  <div className="kpi-calm-context">{k.context}</div>
                </div>
              ))}
            </div>

            {/* GRÁFICO DE ASISTENCIA / LLUVIA SI EXISTEN DATOS */}
            {(activeRole === "docente" || activeRole === "director") &&
              (panelData?.serie_lluvia_cosecha || []).length > 0 && (
                <div className="calm-card">
                  <RainHarvestChart
                    serie={panelData?.serie_lluvia_cosecha || []}
                    role={activeRole}
                  />
                </div>
              )}

            {/* TABLAS ESPECÍFICAS SEGÚN EL ROL ACTIVO */}
            {activeRole === "docente" && (
              <div className="calm-card">
                <DocenteContextTable
                  alumnos={panelData?.alumnos_contexto || []}
                  onLoadSample={handleLoadSampleData}
                />
              </div>
            )}

            {activeRole === "director" && (
              <div className="calm-card">
                <DirectorGroupsTable
                  grupos={panelData?.grupos_centro || []}
                  onLoadSample={handleLoadSampleData}
                />
              </div>
            )}

            {activeRole === "delegado" && (
              <DelegadoTerritorialView
                escuelas={panelData?.escuelas_red || []}
                token={token}
                onLoadSample={handleLoadSampleData}
              />
            )}
          </main>
        )}

        {/* ==================================================================
            VISTA 3: "LO HABLAMOS" (CHAT AGENTE REACT LANGGRAPH + MCP + QWEN)
           ================================================================== */}
        {activeNav === "lohablamos" && (
          <main className="edusight-content">
            <div className="section-kicker">ACOMPAÑAMIENTO CONVERSACIONAL · MCP + LANGGRAPH</div>
            <h1 className="hero-serif-title">Lo hablamos con calma.</h1>
            <p className="hero-subtitle">
              Consulta en lenguaje natural sobre tu aula, centro o territorio. El agente ReAct utiliza el servidor MCP sobre las vistas SQL autorizadas ({grantedViewsText}).
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
                          : `Ayudante EduSight · Rol ${roleInfo.label}`}
                      </span>
                      <div style={{ whiteSpace: "pre-line" }}>{msg.text}</div>

                      {msg.sql && (
                        <details className="mcp-trace-box">
                          <summary>
                            Ver traza MCP y Agente ReAct ({msg.rowsCount ?? 0} filas devueltas por SQL)
                          </summary>
                          <div className="mcp-trace-code">
                            <div>
                              <strong>Framework:</strong>{" "}
                              {msg.mcpTrace?.framework || "LangGraph ReAct"}
                            </div>
                            {msg.mcpTrace?.qwen_status && (
                              <div>
                                <strong>Estado LLM:</strong> {msg.mcpTrace.qwen_status}
                              </div>
                            )}
                            <div>
                              <strong>Tools ejecutadas:</strong>{" "}
                              {(msg.mcpTrace?.tools_called || []).join(" -> ")}
                            </div>
                            <div style={{ marginTop: "4px" }}>
                              <strong>SQL ejecutado en vista ({grantedViewsText}):</strong>
                            </div>
                            <div>{msg.sql}</div>
                          </div>
                        </details>
                      )}
                    </div>
                  ))}

                  {chatLoading && (
                    <div className="msg-bubble msg-assistant">
                      <span className="msg-sender">Agente ReAct · LangGraph + MCP</span>
                      <div>Consultando herramientas MCP sobre {grantedViewsText}...</div>
                    </div>
                  )}
                </div>

                <form className="chat-input-row" onSubmit={handleChatFormSubmit}>
                  <input
                    type="text"
                    className="chat-text-input"
                    placeholder="Escribe aquí tu consulta sobre asistencia, cosecha, becas o notas..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={chatLoading}
                  />
                  <button type="submit" className="btn-forest" disabled={chatLoading}>
                    Consultar
                  </button>
                </form>
              </div>

              {/* COLUMNA DERECHA: CONEXIÓN QWEN/VLLM Y REGISTRO DE DECISIONES */}
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div className="calm-card" style={{ marginBottom: 0, padding: "20px" }}>
                  <div
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      color: "#1f6351",
                      marginBottom: "6px",
                    }}
                  >
                    CONEXIÓN LANGGRAPH · QWEN (VLLM)
                  </div>
                  <div style={{ fontSize: "12.5px", color: "#4e5d55", marginBottom: "12px" }}>
                    {llmStatus?.detail ||
                      "Conectado a 172.25.144.238:8001 (modelo donprofesor-llm)."}
                  </div>

                  <form onSubmit={handleSaveLlmConfig}>
                    <div className="form-group" style={{ marginTop: "8px" }}>
                      <label htmlFor="llm-url">Endpoint OpenAI / vLLM</label>
                      <input
                        id="llm-url"
                        type="text"
                        className="form-input"
                        value={llmUrlInput}
                        onChange={(e) => setLlmUrlInput(e.target.value)}
                      />
                    </div>
                    <div className="form-group" style={{ marginTop: "10px" }}>
                      <label htmlFor="llm-model">Nombre del modelo en vLLM</label>
                      <input
                        id="llm-model"
                        type="text"
                        className="form-input"
                        value={llmModelInput}
                        onChange={(e) => setLlmModelInput(e.target.value)}
                      />
                    </div>
                    <div className="form-group" style={{ marginTop: "10px" }}>
                      <label htmlFor="llm-key">API Key (si vLLM tiene --api-key activo)</label>
                      <input
                        id="llm-key"
                        type="password"
                        className="form-input"
                        placeholder="Pega aquí la API key de tu compañero..."
                        value={llmKeyInput}
                        onChange={(e) => setLlmKeyInput(e.target.value)}
                      />
                    </div>
                    <button
                      type="submit"
                      className="btn-outline-calm"
                      style={{ width: "100%", marginTop: "12px" }}
                      disabled={savingLlm}
                    >
                      {savingLlm ? "Verificando..." : "Actualizar y verificar conexión Qwen"}
                    </button>
                  </form>
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
                      {actionsLog.slice(0, 5).map((a) => (
                        <div
                          key={a.accion_id}
                          style={{
                            fontSize: "12.5px",
                            paddingBottom: "8px",
                            borderBottom: "1px solid #e8e7df",
                          }}
                        >
                          <strong style={{ color: "#1f6351" }}>{a.prediccion_id}</strong>:{" "}
                          {a.decision_tomada}
                          {a.comentario_pedagogico && (
                            <div style={{ color: "#6b7871", fontSize: "11.5px", marginTop: "2px" }}>
                              {a.comentario_pedagogico}
                            </div>
                          )}
                        </div>
                      ))}
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

      {/* MODAL "SOBRE ESTA AYUDA" */}
      {aboutModalOpen && (
        <div className="modal-backdrop" onClick={() => setAboutModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Sobre EduSight · DONPROFESOR (#Hack4Edu 2026)</h3>
            <p style={{ fontSize: "13.5px", color: "#4e5d55", marginTop: "8px" }}>
              Esta plataforma acompaña a docentes, equipos directivos y coordinadores de UGEL sin sustituir nunca el juicio profesional humano ni etiquetar a los estudiantes.
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
                <strong>Rol SQL activo:</strong> <code>role_{activeRole}</code> ({grantedViewsText})
              </div>
              <div>
                <strong>Registros en alumnos_hack4edu:</strong> {totalAlumnos} estudiantes (30 variables de contexto + 7 variables objetivo)
              </div>
              <div>
                <strong>Servidor MCP:</strong> <code>{mcpMeta?.mcp_server_name || "donprofesor-db-mcp"}</code> (list_tables, describe_table, read_query)
              </div>
              <div>
                <strong>Agente ReAct (LangGraph):</strong>{" "}
                <code>{llmStatus?.base_url || "http://172.25.144.238:8001/v1"}</code> (modelo{" "}
                <code>{llmStatus?.model_name || "donprofesor-llm"}</code>)
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
