# Informe de Evaluación de la Rúbrica #Hack4Edu y Diagnóstico del Sistema Actual en Perú

Este informe analiza la situación real de los sistemas estatales de gestión e intervención educativa en el Perú, evalúa qué problemas estructurales resuelve **DONPROFESOR (EduSight)** frente a ellos, califica el estado actual del proyecto contra los cuatro criterios de la **Rúbrica Oficial (Modalidad Innovadora + Reto 13 ProFuturo)** y define las mejoras concretas recomendadas para blindar la máxima puntuación ante el jurado.

---

## 1. Diagnóstico de la Situación y Problemas del Sistema Actual en Perú

En el Perú existen tres grandes pilares institucionales vinculados al seguimiento escolar y la retención estudiantil: **SIAGIE** (MINEDU), **Alerta Escuela** (MINEDU) y el **Programa Juntos** (MIDIS). Sin embargo, los datos oficiales del Censo Educativo (**ESCALE 2025**), el **INEI**, la **Defensoría del Pueblo** y las evaluaciones del **Banco Mundial** demuestran por qué el sistema actual fracasa en prevenir a tiempo la interrupción de estudios (que afecta cada año a cerca del 3 % de los 2,24 millones de alumnos de secundaria pública, superando los 67.000 adolescentes anuales).

### 1.1. SIAGIE: Un repositorio administrativo pasivo ("cementerio de datos")
* **Qué es:** El Sistema de Información de Apoyo a la Gestión de la Institución Educativa (SIAGIE) es la plataforma oficial donde todos los colegios del país registran obligatoriamente nóminas de matrícula, asistencia y actas de evaluación trimestrales.
* **Problemas reales:**
  1. **Flujo unidireccional sin retorno pedagógico:** El docente invierte decenas de horas subiendo datos por obligación burocrática, pero el sistema no le devuelve ninguna alerta, análisis ni recomendación para su aula.
  2. **Detección puramente post-mortem:** Solo consolida calificaciones al cierre de cada trimestre o a fin de año, cuando el estudiante que se ausentó por campañas agrícolas (siembra/cosecha entre mayo y agosto) o trabajo adolescente ya ha abandonado la escuela.
  3. **Colapso y fricción operativa:** Requiere conexión estable a internet para cargar actas, obligando a los docentes de zonas rurales a desplazarse kilómetros hasta capitales de distrito con cabinas o señal móvil para cumplir con los plazos del MINEDU.

### 1.2. Alerta Escuela (MINEDU): El fracaso de la "Caja Negra" dependiente de Internet
* **Qué es:** La herramienta de alerta temprana creada por el Ministerio de Educación dentro del ecosistema SIAGIE para clasificar a los estudiantes según su nivel de riesgo de abandono.
* **Problemas documentados:**
  1. **Adopción real del 7 % (Banco Mundial):** Según la evaluación de impacto documentada por el Banco Mundial sobre sistemas de alerta temprana en el Perú, **solo el 7 % de los directores y docentes** con alumnos en riesgo llegó a consultar la plataforma.
  2. **Opacidad algorítmica (Caja Negra):** La plataforma asignaba etiquetas o colores de riesgo sin explicar qué factores concretos pesaban en cada estudiante ni ofrecer pautas pedagógicas accionables. Para un tutor de aula, ver un porcentaje o un semáforo rojo sin contexto no permite diseñar una tutoría familiar.
  3. **Fuga de datos (*Data Leakage*) y ceguera en Día Cero:** Depende de inasistencias acumuladas y notas previas ya registradas; no actúa preventivamente en marzo (inicio del año escolar) a partir de la realidad socioeconómica y geográfica del hogar.

### 1.3. Brecha de Conectividad Estructural (ESCALE 2025)
* De los **10.468 colegios públicos de secundaria** del Perú (que atienden a 2.244.622 estudiantes), **7.336 centros son rurales** (632.575 estudiantes).
* Según estadísticas oficiales de **ESCALE (MINEDU 2025)**, **solo el 27,3 % de los locales escolares públicos cuenta con conexión a internet**. En regiones andinas como Cajamarca, la cobertura cae al **18,2 %** (más del 81 % de las escuelas desconectadas).
* Cualquier solución de Inteligencia Artificial basada exclusivamente en la nube (SaaS tradicional o APIs remotas obligatorias) deja fuera de forma automática a más de 7 de cada 10 escuelas públicas peruanas.

### 1.4. Desconexión con el Programa Juntos (MIDIS)
* El programa de transferencias monetarias condicionadas **Juntos** entrega un incentivo bimestral a familias en pobreza o pobreza extrema bajo la condición de asegurar al menos el **85 % de asistencia escolar**.
* **Problema actual:** El cruce de asistencia entre la escuela, el SIAGIE y el padrón de Juntos tarda meses. Cuando el sistema estatal detecta que el alumno bajó del 85 %, la familia pierde la transferencia económica de golpe, agravando la crisis económica del hogar y empujando definitivamente al menor al trabajo adolescente. El docente en el aula no tiene una alerta anticipada de que un alumno está a pocas faltas de perder el subsidio familiar.

### 1.5. Marco Legal Estricto de Protección de Datos de Menores (DS N.º 016-2024-JUS)
* Desde marzo de 2025 está vigente el nuevo Reglamento de la **Ley N.º 29733** de Protección de Datos Personales (Decreto Supremo N.º 016-2024-JUS).
* Subir datos socioeconómicos sensibles de menores de edad (ingresos familiares, violencia, trabajo infantil, salud o ubicación exacta) a servidores en la nube de terceros sin consentimiento expreso e infraestructura auditada vulnera la normativa peruana.

---

## 2. ¿Qué Soluciona Realmente DONPROFESOR frente al Sistema Peruano Actual?

Nuestra plataforma ha sido diseñada específicamente para atacar las cinco causas por las que fracasaron o se quedaron cortos SIAGIE y Alerta Escuela:

| Dimensión | Sistema Actual en Perú (SIAGIE / Alerta Escuela) | Qué hace y soluciona DONPROFESOR (EduSight) |
| :--- | :--- | :--- |
| **Momento de predicción** | **Reactivo (Tardío):** Espera a que fallen las notas o la asistencia del 1.er y 2.º trimestre. | **Predictivo desde Día Cero + Ciclo Completo:** Nuestro modelo híbrido (`modelo_ml.py` + `modelo.joblib`) predice desde el día de la matrícula usando variables estructurales (distancia, trabajo adolescente, cosecha, hogar) y se actualiza cada trimestre. |
| **Explicabilidad y Ética (Anti-Caja Negra)** | **Opaco y estigmatizante:** Semáforos y porcentajes de riesgo sin desglose de causas (adopción del 7 %). | **Explicabilidad Local y Lenguaje Pedagógico:** En la vista del docente (`App.jsx`) se eliminan los porcentajes punitivos y se muestran los **3 factores concretos** que influyen en el alumno, ocultando el sexo como justificación y exigiendo **Human-in-the-Loop** (`auditoria.py`). |
| **Conectividad e Infraestructura** | **Dependiente de Internet (Cloud):** Inoperante en el 72,7 % de locales públicos sin red. | **Arquitectura Edge-First (100 % Local):** Base de datos SQLite en el equipo del colegio (`esquema_sqlite.sql`) y motor ML local que corre en milisegundos en cualquier PC o laptop escolar sin internet. |
| **Protección del Subsidio Juntos** | **Punitivo a posteriori:** La familia pierde el bono cuando ya superó el límite de faltas. | **Escudo Preventivo del Subsidio Juntos:** El motor (`motor_inferencia.py`) calcula en tiempo real la probabilidad de pérdida del bono Juntos antes de que el alumno cruce el umbral del 85 % de asistencia, avisando al tutor para intervenir con la familia. |
| **Privacidad Legal (Ley 29733)** | **Exposición de identidades:** Listados nominales sin anonimización diferencial por cargo. | **Privacidad por Diseño y K-Anonimato (>= 5):** Pseudonimización automática (`ALU-XXXXX`), vistas segmentadas por rol y bloqueo matemático de agregados con menos de 5 alumnos en Dirección y UGEL (`politicas.py`). |
| **Gestión Territorial (UGEL)** | **Ceguera presupuestaria:** Sin herramientas para asignar recursos antes de las campañas agrícolas. | **Mapa Territorial y Simulador Presupuestario en Soles (S/):** La vista de Delegado UGEL permite simular el retorno de inversión (transporte escolar rural, becas alimentarias, refuerzo) en Soles peruanos sobre los centros de la provincia. |

---

## 3. Evaluación del Proyecto frente a la Rúbrica Oficial (#Hack4Edu + Premio ProFuturo)

### Criterio 1: Creatividad e Innovación (Peso: 40 % — El bloque decisivo)
* **Cómo lo llevamos hoy: MUY ALTO (9/10).**
* **Fortalezas actuales:**
  1. **Enfoque "Anti-Alerta Escuela":** Mientras el 95 % de los equipos en hackathones de deserción escolar construyen "otro dashboard con semáforos rojos y porcentajes de riesgo", nosotros rompemos ese paradigma con una interfaz de **Calma Pedagógica** para el profesor: cero semáforos estigmatizantes en el aula, lenguaje humano y foco en los 3 factores accionables.
  2. **Doble horizonte predictivo (Día Cero vs. Ciclo Completo) sin *Data Leakage*:** La distinción explícita entre predecir el día de la matrícula (solo con variables de contexto rural/familiar) y predecir durante el curso (`modelo_ml.py`) demuestra madurez científica real.
  3. **Resolución del "Sesgo de Intervención" (Falso Error):** En el documento de transferibilidad y en la tabla `registro_accion_humana` abordamos un problema clásico de la IA en políticas públicas: si el modelo predice que un alumno va a abandonar, el profesor interviene y el alumno **no abandona**, un sistema ingenuo cree que el modelo "se equivocó" al reentrenar. Registrar el acuerdo pedagógico permite separar el éxito de la intervención humana del error del modelo.
  4. **Arquitectura Multi-Rol con K-Anonimato y Simulador Presupuestario:** Conectar en una misma plataforma la tutoría del docente, el diagnóstico por grado del director y la asignación presupuestaria en Soles del delegado UGEL es altamente diferencial.
* **Qué nos falta para el 10/10 en este criterio:**
  * Hacer visible en la interfaz (con un botón o panel real) la **exportación del paquete de fin de curso para reentrenamiento con control de sesgo de intervención**, conectando lo que dice el `Informe_breve_de_transferibilidad.docx` con la tabla `registro_accion_humana` que ya tenemos en SQLite.

### Criterio 2: Acabado y Calidad Final (Peso: 20 %)
* **Cómo lo llevamos hoy: ALTO (8,5/10).**
* **Fortalezas actuales:**
  1. **Aplicación 100 % funcional y conectada de extremo a extremo:** Login real con JWT y roles (`docente`, `director`, `delegado`), aislamiento de grupos por profesor (`docente_id`), alta manual, importación CSV, gráficas dinámicas conectadas a SQLite, inferencia con `modelo.joblib` real y registro persistente de acuerdos de acompañamiento.
  2. **Diseño visual cuidado ("Cuaderno Cálido"):** Tipografía editorial (`Fraunces` + `Plus Jakarta Sans`), libre de jerga técnica informática para el docente.
  3. **Suite de pruebas automatizadas:** 36 tests pasando en `tests/` que validan privacidad, K-anonimato, inferencia y rutas API.
* **Riesgos / Puntos débiles actuales que debemos pulir:**
  1. **Comportamiento del asistente "Lo hablamos" cuando no hay servidor vLLM externo:** Si durante la demo ante el jurado el servidor remoto `http://172.25.144.238:8001/v1` no está accesible o da *timeout*, el chat devuelve un texto de respaldo bastante genérico. Deberíamos enriquecer el motor local de respaldo en `cliente_llm.py` y `grafo_agentes.py` para que consulte las herramientas SQL reales del aula y responda con datos exactos de los alumnos del profesor incluso en modo 100 % offline sin servidor GPU externo.
  2. **Coherencia de marca (EduSight vs. DONPROFESOR):** En la interfaz aparece "EduSight · Faro Educativo" mientras que en los documentos Word del repositorio se alterna entre el nombre del equipo/proyecto y el sistema. Conviene unificar o dejar claro en los documentos y la app que **EduSight (por el equipo DonProfesor)** es el nombre del producto.

### Criterio 3: Transferibilidad al Mercado (Peso: 20 %)
* **Cómo lo llevamos hoy: MUY ALTO en documentación (9,5/10), mejorable en integración directa en la app (8/10).**
* **Fortalezas actuales:**
  * El documento `Informe_breve_de_transferibilidad.docx` es sobresaliente: incluye presupuesto real de levantamiento de datos en Perú (S/ 144.400 para 4.000 encuestas con sueldos INEI de S/ 2.300/mes), modelo de licencias B2G escalonado (S/ 10/alumno/año regional = 0,16 % del gasto público por estudiante de S/ 6.266; S/ 5/alumno nacional) y vía B2B (S/ 200/mes colegios privados).
* **Qué cambio haría brillar la transferibilidad en la demo técnica:**
  * **Compatibilidad nativa con nóminas SIAGIE en el importador CSV:** Hoy todos los colegios peruanos descargan y suben hojas de cálculo de **SIAGIE**. Si nuestro botón `Importar CSV` indica explícitamente *"Compatible con plantilla estándar o exportación SIAGIE (MINEDU)"* y el backend reconoce automáticamente alias de columnas típicas de SIAGIE/Perú, eliminamos la principal objeción de adopción del jurado ("¿el profesor tendrá que picar los datos dos veces, en SIAGIE y aquí?").

### Criterio 4: Educación Digital con IA en Países Desfavorecidos + Premio ProFuturo (Peso: 20 % + Premio Especial)
* **Cómo lo llevamos hoy: ALTO (8,8/10).**
* **Por qué encaja de lleno con ProFuturo:**
  1. **ProFuturo ya opera en 3.609 escuelas en Perú** mediante su **Maleta Digital Offline** (servidor local con laptop docente y tablets que funcionan sin internet). Nuestro sistema está construido exactamente para correr dentro de ese servidor local (SQLite + modelo ligero `joblib` en CPU sin requerir internet ni GPUs caras en el colegio).
  2. **Contextualización en la realidad rural andina y amazónica:** Variables específicas de campañas agrícolas (`impacto_cosecha`), distancia en kilómetros y días de lluvia, idioma materno (quechua/aimara vs. castellano), conectividad en el hogar y beca **Juntos**.
  3. **IA centrada en el docente (empoderamiento, no sustitución):** Cumple la premisa central de ProFuturo y UNESCO: la IA no reemplaza ni puentea al maestro rural, sino que le ahorra carga burocrática y le da contexto pedagógico para acompañar mejor a sus estudiantes.

---

## 4. Plan de Cambios Recomendados (Qué deberíamos hacer ahora mismo)

1. **Asistente "Lo hablamos" 100 % inteligente en modo Offline (sin depender del servidor vLLM remoto):**
   * Hacer que el modo local de `grafo_agentes.py` analice la pregunta del docente o director contra los datos reales de SQLite (alumnos con mayor caída de notas, alumnos en riesgo de perder el bono Juntos, impacto de cosecha o distancia, resumen del grupo) y construya una respuesta pedagógica detallada con las cifras exactas de su clase, sin fallar jamás aunque no haya internet ni servidor GPU.

2. **Cerrar el "Ciclo de Mejora Continua" (Exportación de Fin de Curso con Intervenciones Humanas):**
   * Añadir un endpoint `/api/v1/estudiantes/exportar-ciclo-mejora` y un botón en la interfaz para descargar el CSV anonimizado que cruza las predicciones de los alumnos con los acuerdos pedagógicos registrados por los profesores (`registro_accion_humana`).

3. **Soporte y mención explícita a SIAGIE (MINEDU) en la importación de datos:**
   * Adaptar el importador CSV (`estudiantes.py` y el modal en `App.jsx`) para que acepte directamente cabeceras habituales de nóminas de SIAGIE / padrón escolar y muestre una plantilla descargable compatible.

4. **Destacar la integración con la "Maleta Digital ProFuturo" y el blindaje de la Beca Juntos en la vista de Delegado/Director:**
   * Asegurar que los indicadores de alumnos protegidos frente a la pérdida del **Programa Juntos** y la operatividad en **entornos sin internet (Modo Local / Maleta Digital)** sean visibles de un vistazo para maximizar los puntos del **Reto 13 ProFuturo** y del criterio de **Educación digital con IA en países desfavorecidos (20 %)**.
