import React, { useEffect, useState } from "react";
import { fetchRegistrationOptions, loginUser, registerUser } from "../services/api.js";

/* ==========================================================================
   PANTALLA DE ACCESO: INICIAR SESIÓN / CREAR CUENTA
   El rol y el ámbito (escuela, grado, UGEL) se fijan al registrarse y viajan
   en el token: cada persona solo verá la vista y los datos de su rol.
   ========================================================================== */

const ROLES_POR_DEFECTO = [
  { id: "docente", label: "Docente", ambito: "Tu grupo: escuela y grado" },
  { id: "director", label: "Director/a", ambito: "Tu escuela, por grados" },
  { id: "delegado", label: "Delegado/a UGEL", ambito: "Tu UGEL, por escuelas" },
];

const REGISTRO_INICIAL = {
  nombre_completo: "",
  username: "",
  password: "",
  password2: "",
  rol: "docente",
  escuela_id: "",
  grado_secundaria: "",
  ugel: "",
  titulo_cargo: "",
  codigo_invitacion: "",
};

function Brand() {
  return (
    <div className="auth-brand">
      <svg width="34" height="38" viewBox="0 0 34 38" fill="none" aria-hidden="true">
        <path d="M13 13H21L23 34H11L13 13Z" stroke="#1F6351" strokeWidth="1.7" strokeLinejoin="round" />
        <path d="M9 34H25" stroke="#1F6351" strokeWidth="1.7" strokeLinecap="round" />
        <rect x="14" y="7" width="6" height="6" stroke="#1F6351" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M12 7L17 3L22 7" stroke="#1F6351" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 10L9 10" stroke="#1F6351" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M25 10L30 10" stroke="#1F6351" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <div>
        <div className="edusight-brand-name">DONPROFESOR</div>
        <div className="edusight-brand-sub">EDUSIGHT · FARO EDUCATIVO</div>
      </div>
    </div>
  );
}

export function AuthScreen({ onAuthenticated, notice }) {
  const [mode, setMode] = useState("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [login, setLogin] = useState({ username: "", password: "" });
  const [reg, setReg] = useState(REGISTRO_INICIAL);
  const [options, setOptions] = useState({ roles: ROLES_POR_DEFECTO, escuelas: [], ugels: [], grados: [1, 2, 3, 4, 5], requiere_codigo: {} });

  useEffect(() => {
    fetchRegistrationOptions()
      .then((o) => setOptions((prev) => ({ ...prev, ...o })))
      .catch(() => {});
  }, []);

  const switchMode = (m) => {
    setMode(m);
    setError(null);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onAuthenticated(await loginUser(login.username.trim(), login.password));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const setField = (field) => (e) => setReg((r) => ({ ...r, [field]: e.target.value }));

  const handleRegister = async (e) => {
    e.preventDefault();
    setError(null);
    if (reg.password !== reg.password2) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    const payload = {
      nombre_completo: reg.nombre_completo.trim(),
      username: reg.username.trim().toLowerCase(),
      password: reg.password,
      rol: reg.rol,
      titulo_cargo: reg.titulo_cargo.trim() || null,
      codigo_invitacion: reg.codigo_invitacion.trim() || null,
      escuela_id: reg.rol !== "delegado" ? reg.escuela_id.trim() || null : null,
      grado_secundaria: reg.rol === "docente" && reg.grado_secundaria ? Number(reg.grado_secundaria) : null,
      ugel: reg.ugel.trim() || null,
    };
    setBusy(true);
    try {
      onAuthenticated(await registerUser(payload));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const necesitaCodigo = Boolean(options.requiere_codigo?.[reg.rol]);
  const rolInfo = options.roles.find((r) => r.id === reg.rol);

  return (
    <div className="auth-shell">
      <div className="auth-side">
        <Brand />
        <h1 className="hero-serif-title auth-title">Más tiempo para enseñar.</h1>
        <p className="hero-subtitle">
          Cada persona entra con su cuenta y ve solo lo que le corresponde: el docente, su grupo; la dirección, su escuela
          por grados; la UGEL, sus escuelas. Los datos agregados ocultan los grupos de menos de 5 estudiantes.
        </p>
        <div className="auth-ethics">
          <strong>Tú conoces a tu grupo. Tú decides.</strong> Esta ayuda puede equivocarse; no decide ni clasifica a estudiantes.
        </div>
      </div>

      <div className="auth-card">
        <div className="auth-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "login"} className={`auth-tab ${mode === "login" ? "active" : ""}`} onClick={() => switchMode("login")}>
            Iniciar sesión
          </button>
          <button type="button" role="tab" aria-selected={mode === "register"} className={`auth-tab ${mode === "register" ? "active" : ""}`} onClick={() => switchMode("register")}>
            Crear cuenta
          </button>
        </div>

        {notice && !error && <div className="auth-notice">{notice}</div>}
        {error && <div className="auth-error" role="alert">{error}</div>}

        {mode === "login" ? (
          <form onSubmit={handleLogin} className="auth-form">
            <div className="form-group">
              <label htmlFor="login-user">Usuario</label>
              <input id="login-user" className="form-input" autoComplete="username" required value={login.username} onChange={(e) => setLogin((l) => ({ ...l, username: e.target.value }))} />
            </div>
            <div className="form-group">
              <label htmlFor="login-pass">Contraseña</label>
              <input id="login-pass" type="password" className="form-input" autoComplete="current-password" required value={login.password} onChange={(e) => setLogin((l) => ({ ...l, password: e.target.value }))} />
            </div>
            <button type="submit" className="btn-forest auth-submit" disabled={busy}>
              {busy ? "Entrando…" : "Entrar"}
            </button>
            <p className="auth-hint">
              ¿No tienes cuenta?{" "}
              <button type="button" className="auth-link" onClick={() => switchMode("register")}>Créala aquí</button>
            </p>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="auth-form">
            <div className="form-group">
              <label htmlFor="reg-rol">Soy…</label>
              <div className="auth-roles" id="reg-rol">
                {options.roles.map((r) => (
                  <button key={r.id} type="button" className={`auth-role ${reg.rol === r.id ? "active" : ""}`} onClick={() => setReg((s) => ({ ...s, rol: r.id }))}>
                    <span className="auth-role-name">{r.label}</span>
                    <span className="auth-role-scope">{r.ambito}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="reg-name">Nombre y apellidos</label>
              <input id="reg-name" className="form-input" required minLength={3} value={reg.nombre_completo} onChange={setField("nombre_completo")} />
            </div>

            <div className="auth-row">
              <div className="form-group">
                <label htmlFor="reg-user">Usuario</label>
                <input id="reg-user" className="form-input" autoComplete="username" required minLength={3} maxLength={40} title="Letras, números, punto, guion o guion bajo" value={reg.username} onChange={setField("username")} />
              </div>
              <div className="form-group">
                <label htmlFor="reg-cargo">Cargo (opcional)</label>
                <input id="reg-cargo" className="form-input" maxLength={140} value={reg.titulo_cargo} onChange={setField("titulo_cargo")} />
              </div>
            </div>

            {reg.rol !== "delegado" && (
              <div className="auth-row">
                <div className="form-group">
                  <label htmlFor="reg-escuela">Código de tu escuela</label>
                  <input id="reg-escuela" className="form-input" list="escuelas-conocidas" required placeholder="p. ej. ESC-01" value={reg.escuela_id} onChange={setField("escuela_id")} />
                  <datalist id="escuelas-conocidas">
                    {options.escuelas.map((e) => <option key={e} value={e} />)}
                  </datalist>
                </div>
                {reg.rol === "docente" && (
                  <div className="form-group">
                    <label htmlFor="reg-grado">Grado que tutorizas</label>
                    <select id="reg-grado" className="form-input" required value={reg.grado_secundaria} onChange={setField("grado_secundaria")}>
                      <option value="">Elige…</option>
                      {options.grados.map((g) => <option key={g} value={g}>{g}.º de secundaria</option>)}
                    </select>
                  </div>
                )}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="reg-ugel">UGEL{reg.rol === "delegado" ? "" : " (opcional)"}</label>
              <input id="reg-ugel" className="form-input" list="ugels-conocidas" required={reg.rol === "delegado"} placeholder="p. ej. UGEL-CUSCO" value={reg.ugel} onChange={setField("ugel")} />
              <datalist id="ugels-conocidas">
                {options.ugels.map((u) => <option key={u} value={u} />)}
              </datalist>
            </div>

            <div className="auth-row">
              <div className="form-group">
                <label htmlFor="reg-pass">Contraseña</label>
                <input id="reg-pass" type="password" className="form-input" autoComplete="new-password" required minLength={8} value={reg.password} onChange={setField("password")} />
              </div>
              <div className="form-group">
                <label htmlFor="reg-pass2">Repite la contraseña</label>
                <input id="reg-pass2" type="password" className="form-input" autoComplete="new-password" required minLength={8} value={reg.password2} onChange={setField("password2")} />
              </div>
            </div>
            <div className="auth-hint">Mínimo 8 caracteres, con letras y números.</div>

            {necesitaCodigo && (
              <div className="form-group">
                <label htmlFor="reg-code">Código de invitación</label>
                <input id="reg-code" className="form-input" required value={reg.codigo_invitacion} onChange={setField("codigo_invitacion")} />
              </div>
            )}

            <button type="submit" className="btn-forest auth-submit" disabled={busy}>
              {busy ? "Creando cuenta…" : `Crear cuenta de ${rolInfo?.label?.toLowerCase() || reg.rol}`}
            </button>
            <p className="auth-hint">
              ¿Ya tienes cuenta?{" "}
              <button type="button" className="auth-link" onClick={() => switchMode("login")}>Inicia sesión</button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
