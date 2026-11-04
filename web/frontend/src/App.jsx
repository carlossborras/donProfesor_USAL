import React, { useState, useEffect, useCallback } from "react";
import {
  loginRole,
  fetchDashboardPanel,
  fetchMcpMetadata,
  sendMcpChatQuestion,
  registerPedagogicalAction,
} from "./services/api.js";
import { EthicalBanner } from "./components/EthicalBanner.jsx";
import { Navbar } from "./components/Navbar.jsx";
import { KpiGrid } from "./components/KpiGrid.jsx";
import { PredictiveAlertsPanel } from "./components/PredictiveAlertsPanel.jsx";
import { RainHarvestChart } from "./components/RainHarvestChart.jsx";
import {
  DocenteContextTable,
  DirectorGroupsTable,
  DelegadoTerritorialView,
} from "./components/RoleViews.jsx";
import { McpChatSidebar } from "./components/McpChatSidebar.jsx";
import { LoginModal, ActionModal } from "./components/Modals.jsx";

export function App() {
  const [activeRole, setActiveRole] = useState("docente");
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [panelData, setPanelData] = useState(null);
  const [mcpMeta, setMcpMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState(null);

  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "assistant",
      text: "Bienvenido al espacio de consulta en lenguaje natural conectado por Model Context Protocol (MCP) a la base de datos. Selecciona una pregunta frecuente o escribe tu consulta sobre asistencia, lluvia, cosecha, formación docente, recursos o participación.",
      sql: null,
      rowsCount: 0,
    },
  ]);

  const authenticateAndLoadRole = useCallback(async (roleToLoad) => {
    setLoading(true);
    setError(null);
    try {
      const authRes = await loginRole(roleToLoad, "donprofesor2026");
      setToken(authRes.access_token);
      setUser(authRes.user);
      setActiveRole(roleToLoad);

      const [panelRes, mcpRes] = await Promise.all([
        fetchDashboardPanel(authRes.access_token),
        fetchMcpMetadata(authRes.access_token),
      ]);
      setPanelData(panelRes);
      setMcpMeta(mcpRes);
    } catch (err) {
      setError(err.message || "Error al conectar con el backend de DONPROFESOR");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    authenticateAndLoadRole("docente");
  }, [authenticateAndLoadRole]);

  const handleSelectRole = async (newRole) => {
    setLoginModalOpen(false);
    await authenticateAndLoadRole(newRole);
    setChatHistory([
      {
        sender: "assistant",
        text: `Sesión cambiada al rol ${newRole.toUpperCase()}. El servidor MCP consulta ahora exclusivamente las vistas SQL autorizadas para tu ámbito.`,
        sql: null,
        rowsCount: 0,
      },
    ]);
  };

  const handleSendChatQuestion = async (questionText) => {
    if (!token) return;
    setChatHistory((prev) => [...prev, { sender: "user", text: questionText }]);
    setChatLoading(true);
    try {
      const res = await sendMcpChatQuestion(token, questionText);
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

  const handleSaveHumanAction = async (payload) => {
    if (!token) return;
    await registerPedagogicalAction(token, payload);
    const refreshed = await fetchDashboardPanel(token);
    setPanelData(refreshed);
  };

  const sqlSecurity = panelData?.sql_security || {};
  const dbStatus = panelData?.db_status || {};
  const grantedViewsText = (sqlSecurity.granted_views || ["vista_docente"]).join(", ");

  return (
    <div className="app-shell">
      <EthicalBanner sqlSecurity={sqlSecurity} dbStatus={dbStatus} />

      <Navbar
        activeRole={activeRole}
        user={user}
        sqlSecurity={sqlSecurity}
        onSelectRole={handleSelectRole}
        onOpenLoginModal={() => setLoginModalOpen(true)}
      />

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => authenticateAndLoadRole(activeRole)}
          >
            Reintentar conexión
          </button>
        </div>
      )}

      <main className="main-container">
        <KpiGrid kpis={panelData?.kpis || []} />

        <div className="workspace-grid">
          <div className="left-column">
            <PredictiveAlertsPanel
              alerts={panelData?.avisos_predictivos || []}
              onOpenActionModal={(alertItem) => setSelectedAlert(alertItem)}
            />

            {(activeRole === "docente" || activeRole === "director") &&
              (panelData?.serie_lluvia_cosecha || []).length > 0 && (
                <RainHarvestChart
                  serie={panelData?.serie_lluvia_cosecha || []}
                  role={activeRole}
                />
              )}

            {activeRole === "docente" && (
              <DocenteContextTable alumnos={panelData?.alumnos_contexto || []} />
            )}

            {activeRole === "director" && (
              <DirectorGroupsTable grupos={panelData?.grupos_centro || []} />
            )}

            {activeRole === "delegado" && (
              <DelegadoTerritorialView
                escuelas={panelData?.escuelas_red || []}
                token={token}
              />
            )}
          </div>

          <McpChatSidebar
            role={activeRole}
            mcpView={grantedViewsText}
            mcpMeta={mcpMeta}
            chatHistory={chatHistory}
            onSendMessage={handleSendChatQuestion}
            actionsLog={panelData?.acciones_humanas || []}
            chatLoading={chatLoading}
          />
        </div>
      </main>

      <LoginModal
        isOpen={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        currentRole={activeRole}
        onSelectRole={handleSelectRole}
      />

      <ActionModal
        isOpen={Boolean(selectedAlert)}
        alertItem={selectedAlert}
        onClose={() => setSelectedAlert(null)}
        onSubmit={handleSaveHumanAction}
      />
    </div>
  );
}
