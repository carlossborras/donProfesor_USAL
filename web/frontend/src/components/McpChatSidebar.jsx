import React, { useState } from "react";

const PRESETS = {
  docente: [
    "¿Qué alumnos faltan cuando llueve y viven a más de 3 km?",
    "¿Cómo influye la cosecha y el apoyo laboral en las entregas?",
    "¿Cuál es el efecto protector de la beca en mi tutoría?",
    "¿Qué situaciones prioritarias sugiere revisar el modelo?",
  ],
  director: [
    "¿Cómo se superponen asistencia, lluvia y semanas de cosecha?",
    "¿Qué brecha hay entre dispositivos disponibles y uso real por grupo?",
    "¿Cómo influyen las horas de formación docente en el uso de recursos?",
    "¿Qué grupos tienen menor asistencia en semanas de cosecha?",
  ],
  delegado: [
    "¿Qué escuelas rurales tienen menor conectividad y uso de recursos?",
    "¿Dónde hay mayor brecha entre equipamiento disponible y uso en aula?",
    "¿Qué escuelas necesitan formación docente práctica prioritaria?",
    "¿Cómo se distribuye la asistencia entre centros urbanos y rurales?",
  ],
};

export function McpChatSidebar({
  role,
  mcpView,
  chatHistory,
  onSendMessage,
  actionsLog = [],
  chatLoading,
}) {
  const [question, setQuestion] = useState("");
  const presets = PRESETS[role] || PRESETS.docente;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || chatLoading) return;
    onSendMessage(question.trim());
    setQuestion("");
  };

  return (
    <aside className="mcp-chat-sidebar" aria-label="Consultas en lenguaje natural vía MCP">
      <div className="mcp-header">
        <div className="mcp-title-row">
          <h2>Consulta a tus datos en lenguaje humano</h2>
          <span className="mcp-status-pill">MCP CONECTADO A BD</span>
        </div>
        <p style={{ fontSize: "12px", color: "#475569" }}>
          Pregunta sobre asistencia, lluvia, cosecha, formación docente o recursos. El agente consulta en vivo la vista SQL de tu rol mediante Model Context Protocol.
        </p>
        <div className="mcp-tools-strip">
          <span className="mcp-tool-tag">tool: list_tables()</span>
          <span className="mcp-tool-tag">tool: describe_table()</span>
          <span className="mcp-tool-tag">tool: read_query(SELECT)</span>
        </div>
        <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
          Vistas SQL activas: <code>{mcpView}</code>
        </div>
      </div>

      <div className="mcp-quick-prompts">
        <span className="quick-prompts-label">
          Consultas frecuentes para tu rol (clic para consultar la BD):
        </span>
        <div className="prompt-chips">
          {presets.map((p, idx) => (
            <button
              key={idx}
              type="button"
              className="prompt-chip"
              onClick={() => onSendMessage(p)}
              disabled={chatLoading}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-messages">
        {chatHistory.map((msg, idx) => (
          <div
            key={idx}
            className={`msg-bubble ${msg.sender === "user" ? "msg-user" : "msg-assistant"}`}
          >
            <span className="msg-sender">
              {msg.sender === "user"
                ? "Tu consulta pedagógica"
                : `Respuesta verificada en Base de Datos (rol: ${role})`}
            </span>
            <div>{msg.text}</div>
            {msg.sql && (
              <details className="mcp-trace-box">
                <summary>
                  Ver traza MCP ejecutada ({msg.rowsCount || 0} filas devueltas por SQL)
                </summary>
                <div className="mcp-trace-code">
                  <div>
                    <strong>1. list_tables(rol=&apos;{role}&apos;)</strong> -&gt; [{mcpView}]
                  </div>
                  <div style={{ marginTop: "4px" }}>
                    <strong>2. read_query(sql):</strong>
                  </div>
                  <div>{msg.sql}</div>
                </div>
              </details>
            )}
          </div>
        ))}
        {chatLoading && (
          <div className="msg-bubble msg-assistant">
            <span className="msg-sender">Servidor MCP · donprofesor-db-mcp</span>
            <div>Ejecutando consulta read_query(SELECT) sobre {mcpView}...</div>
          </div>
        )}
      </div>

      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          className="chat-input"
          placeholder="Escribe tu pregunta para consultar la base de datos..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={chatLoading}
        />
        <button type="submit" className="btn-primary" disabled={chatLoading}>
          Consultar
        </button>
      </form>

      <div className="actions-log-card">
        <h3>Registro reciente de decisiones humanas (Trazabilidad ética)</h3>
        <div className="log-list">
          {actionsLog.length === 0 ? (
            <div className="log-entry">
              Aún no hay decisiones registradas para este rol.
            </div>
          ) : (
            actionsLog.slice(0, 4).map((a) => (
              <div className="log-entry" key={a.accion_id}>
                <strong>{a.prediccion_id}</strong> ({a.ambito_id}): {a.decision_tomada} —{" "}
                <em>{a.comentario_pedagogico}</em>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
}
