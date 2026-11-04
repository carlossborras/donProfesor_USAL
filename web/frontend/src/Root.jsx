import React, { useCallback, useEffect, useState } from "react";
import { App } from "./App.jsx";
import { AuthScreen } from "./components/AuthScreen.jsx";
import { fetchCurrentUser } from "./services/api.js";

/* ==========================================================================
   PUERTA DE ACCESO: sin sesión -> AuthScreen; con sesión -> App del rol.
   La sesión se guarda en sessionStorage (se borra al cerrar la pestaña).
   ========================================================================== */

const STORAGE_KEY = "donprofesor.session";

function readStoredSession() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed?.token && parsed?.user ? parsed : null;
  } catch (_err) {
    return null;
  }
}

export function Root() {
  const [session, setSession] = useState(readStoredSession);
  const [checking, setChecking] = useState(Boolean(readStoredSession()));
  const [notice, setNotice] = useState(null);

  const saveSession = useCallback((next) => {
    if (next) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else sessionStorage.removeItem(STORAGE_KEY);
    setSession(next);
  }, []);

  // Al recargar, comprobar que el token sigue siendo válido
  useEffect(() => {
    const stored = readStoredSession();
    if (!stored) return;
    fetchCurrentUser(stored.token)
      .then((res) => saveSession({ token: stored.token, user: res.user }))
      .catch(() => {
        saveSession(null);
        setNotice("Tu sesión ha caducado. Vuelve a iniciar sesión.");
      })
      .finally(() => setChecking(false));
  }, [saveSession]);

  const handleAuthenticated = useCallback(
    (authRes) => {
      setNotice(null);
      saveSession({ token: authRes.access_token, user: authRes.user });
    },
    [saveSession]
  );

  const handleLogout = useCallback(
    (reason) => {
      saveSession(null);
      setNotice(typeof reason === "string" ? reason : null);
    },
    [saveSession]
  );

  if (checking) {
    return <div className="auth-loading">Comprobando tu sesión…</div>;
  }
  if (!session) {
    return <AuthScreen onAuthenticated={handleAuthenticated} notice={notice} />;
  }
  // key: si cambia el usuario se monta una App nueva (sin estado del anterior)
  return <App key={session.user.username} session={session} onLogout={handleLogout} />;
}
