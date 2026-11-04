import React from "react";

export function EthicalBanner({ sqlSecurity, dbStatus }) {
  const dbRole = sqlSecurity?.db_role || "role_docente";
  const grantedViews = sqlSecurity?.granted_views?.join(", ") || "vista_docente, vista_avisos_predictivos";
  const totalAlu = dbStatus?.total_alumnos_cargados ?? 0;
  const dbModeLabel = dbStatus?.is_provisional
    ? `BD Real Conectada (donprofesor.db · ${totalAlu} alumnos)`
    : `BD PostgreSQL Conectada (${totalAlu} alumnos)`;

  return (
    <div className="fixed-ethical-banner" role="region" aria-label="Aviso ético y permisos de base de datos">
      <div className="ethical-statement">
        <strong>Aviso pedagógico permanente:</strong> «La decisión es tuya; el modelo puede equivocarse». Prohibidas las decisiones automáticas, rankings o semáforos sobre estudiantes.
      </div>
      <div className="security-badges">
        <span className="sql-pill">{dbModeLabel}</span>
        <span className="sql-pill">Rol SQL: {dbRole}</span>
        <span className="sql-pill">GRANT SELECT: {grantedViews}</span>
      </div>
    </div>
  );
}
