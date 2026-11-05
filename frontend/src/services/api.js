/**
 * DONPROFESOR · EduSight (#Hack4Edu) · Cliente API REST + MCP para la aplicación React.
 * Gestiona la autenticación JWT por rol, las vistas SQL, la carga de datos y la conexión con Qwen/LangGraph.
 */

export async function fetchDashboardPanel(token) {
  const response = await fetch("/api/panel", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new ApiError("No se pudo cargar el panel del rol activo", response.status);
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

export function registerPedagogicalAction(token, payload) {
  return requestJson("/api/acciones", { method: "POST", token, body: payload });
}

export function runGrantSimulationApi(token, payload) {
  return requestJson("/api/simular-subvencion", { method: "POST", token, body: payload });
}

export function loadSampleDatasetApi(token) {
  return requestJson("/api/datos/semilla-prueba", { method: "POST", token });
}

export function clearDatasetApi(token) {
  return requestJson("/api/datos/vaciar", { method: "POST", token });
}

export function createStudentApi(token, studentData) {
  return requestJson("/api/datos/alumno", { method: "POST", token, body: studentData });
}

export function pasteStudentDataApi(token, dataText) {
  return requestJson("/api/datos/pegar", { method: "POST", token, body: { data_text: dataText } });
}

export async function uploadCsvDatasetApi(token, file) {
  const formData = new FormData();
  formData.append("file", file);
  let response;
  try {
    response = await fetch("/api/datos/importar-csv", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
  } catch (_err) {
    throw new ApiError("No se puede conectar con el servidor. Comprueba que la API está arrancada.", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(describeValidationError(data.detail) || "Error al subir el archivo CSV", response.status);
  }
  return data;
}

export function fetchLlmStatusApi(token) {
  return requestJson("/api/config/llm", { token });
}

/* Modelo predictivo y pestaña «Predicciones» */
export function fetchModelStatusApi(token) {
  return requestJson("/api/modelo/estado", { token });
}

export function fetchModelFieldsApi(token) {
  return requestJson("/api/modelo/campos", { token });
}

export function fetchPredictionsApi(token) {
  return requestJson("/api/predicciones", { token });
}

export function recalculatePredictionsApi(token, soloPendientes = false) {
  return requestJson(`/api/predicciones/recalcular?solo_pendientes=${soloPendientes ? "true" : "false"}`, {
    method: "POST",
    token,
  });
}

/* ==========================================================================
   AUTENTICACIÓN (registro / login / sesión) Y PANELES CON GRÁFICOS POR ROL
   ========================================================================== */

/** Error con el código HTTP, para que la interfaz pueda distinguir 401 (sesión caducada) y 403. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function describeValidationError(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && d.msg ? String(d.msg).replace(/^Value error, /, "") : ""))
      .filter(Boolean)
      .join(" ");
  }
  return typeof detail === "string" ? detail : "";
}

async function requestJson(url, { method = "GET", token, body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (_err) {
    throw new ApiError("No se puede conectar con el servidor. Comprueba que la API está arrancada.", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = describeValidationError(data.detail) || `Error ${response.status}`;
    throw new ApiError(message, response.status);
  }
  return data;
}

export function loginUser(username, password) {
  return requestJson("/api/auth/login", { method: "POST", body: { username, password } });
}

export function registerUser(payload) {
  return requestJson("/api/auth/register", { method: "POST", body: payload });
}

export function fetchCurrentUser(token) {
  return requestJson("/api/auth/me", { token });
}

export function fetchRegistrationOptions() {
  return requestJson("/api/auth/opciones-registro");
}

export function fetchRoleDashboard(token) {
  return requestJson("/api/dashboard", { token });
}
