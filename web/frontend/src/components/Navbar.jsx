import React from "react";

export function Navbar({ activeRole, user, sqlSecurity, onSelectRole, onOpenLoginModal }) {
  const roles = [
    { id: "docente", label: "Panel Docente" },
    { id: "director", label: "Panel Dirección" },
    { id: "delegado", label: "Panel Delegado Territorial" },
  ];

  return (
    <>
      <header className="top-header">
        <div className="brand-group">
          <div className="brand-monogram">DP</div>
          <div className="brand-titles">
            <h1>DONPROFESOR · Cuaderno de Acompañamiento y Analítica Educativa</h1>
            <p>Interpretación comprensible de asistencia, aprendizaje, formación docente, recursos y participación</p>
          </div>
        </div>

        <div className="header-controls">
          <div className="role-switcher" role="tablist" aria-label="Selector de panel por rol">
            {roles.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`role-tab ${activeRole === r.id ? "active" : ""}`}
                onClick={() => onSelectRole(r.id)}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="session-box">
            <span>
              {user ? `${user.nombre_completo} · ${user.rol.toUpperCase()} (JWT)` : "Sesión activa"}
            </span>
            <button type="button" className="btn-login-open" onClick={onOpenLoginModal}>
              Cambiar usuario JWT
            </button>
          </div>
        </div>
      </header>

      <div className="scope-bar">
        <div className="scope-details">
          Ámbito autorizado por token JWT: <strong>{user?.titulo_cargo || "Tutoría 2º B"}</strong> · Filtro SQL:{" "}
          <code>{sqlSecurity?.scope_filter || "grupo_id = 'ESC-01-2B'"}</code>
        </div>
        <div>
          <span>Privacidad por diseño: Vistas SQL restringidas por rol · Sin exposición de datos personales</span>
        </div>
      </div>
    </>
  );
}
