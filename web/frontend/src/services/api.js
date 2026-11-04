/**
 * DONPROFESOR (#Hack4Edu) · Cliente API REST + MCP para la aplicación React.
 * Gestiona la autenticación JWT por rol y las llamadas a las vistas de la Base de Datos.
 */

export async function loginRole(username, password = "donprofesor2026") {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Error al iniciar sesión con JWT");
  }
  return response.json();
}

export async function fetchDashboardPanel(token) {
  const response = await fetch("/api/panel", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("No se pudo cargar el panel del rol activo");
  }
  return response.json();
}

export async function fetchMcpMetadata(token) {
  const response = await fetch("/api/mcp/tools", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("No se pudo obtener el estado del servidor MCP");
  }
  return response.json();
}

export async function sendMcpChatQuestion(token, question) {
  const response = await fetch("/api/chat-mcp", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    throw new Error("Error al consultar el Servidor MCP desde el Chat");
  }
  return response.json();
}

export async function registerPedagogicalAction(token, payload) {
  const response = await fetch("/api/acciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("No se pudo registrar la decisión pedagógica");
  }
  return response.json();
}

export async function runGrantSimulationApi(token, payload) {
  const response = await fetch("/api/simular-subvencion", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Error al ejecutar la simulación de subvenciones");
  }
  return response.json();
}
