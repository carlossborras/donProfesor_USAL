/**
 * DONPROFESOR · EduSight (#Hack4Edu) · Cliente API REST + MCP para la aplicación React.
 * Gestiona la autenticación JWT por rol, las vistas SQL, la carga de datos y la conexión con Qwen/LangGraph.
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

export async function loadSampleDatasetApi(token) {
  const response = await fetch("/api/datos/semilla-prueba", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Error al cargar datos de prueba");
  }
  return response.json();
}

export async function clearDatasetApi(token) {
  const response = await fetch("/api/datos/vaciar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Error al vaciar la base de datos");
  }
  return response.json();
}

export async function uploadCsvDatasetApi(token, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/datos/importar-csv", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Error al subir el archivo CSV");
  }
  return response.json();
}

export async function fetchLlmStatusApi(token) {
  const response = await fetch("/api/config/llm", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Error al consultar estado del LLM");
  }
  return response.json();
}

export async function updateLlmConfigApi(token, payload) {
  const response = await fetch("/api/config/llm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Error al actualizar configuración del LLM");
  }
  return response.json();
}
