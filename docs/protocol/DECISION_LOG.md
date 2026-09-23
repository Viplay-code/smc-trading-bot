# Registro de decisiones — Protocolo Científico V2

**Fecha de consolidación documental:** 2026-09-21
**Documento canónico del estado vigente:** `docs/protocol/NORMATIVE_SPEC.md`

Este registro recoge, en orden, las decisiones humanas ya cerradas del Protocolo V2.

**Etiquetas:** **[N]** decisión humana normativa · **[D]** / **[D+]** hecho matemático
demostrado · **[I]** inferencia · **ND** no demostrado ni refutado.

**Sobre las fechas.** Las decisiones se tomaron en sesiones de trabajo cuya fecha exacta
**no está documentada con certeza** para cada una. Se registra solo la fecha de
consolidación documental. Donde la fecha original consta en la propia decisión, se indica.

**Sobre el alcance de este registro.** Los bloques 0.1 a 0.6 son **resúmenes**: sus
Decision Records completos **no están consolidados todavía**. Los bloques 1 a 9 recogen el
contenido completo tal como se cerró.

---

## 0. Decisiones previas del Protocolo V2 (resumen; DR completo no consolidado)

### 0.1 C1 — Alcance
- **Decisión** [N]: D1.1 a D1.13 y los principios derivados P1.a a P1.d.
- **Contenido registrado:** núcleo general más anexos por clase (D1.1); solo estrategias
  direccionales (D1.2); trayectoria condicional (D1.3); la señal de un activo usa solo
  información de ese activo y de su instrumento, más calendario y tiempo, y queda prohibida
  la información de otros activos, aunque la agregación en cartera sí se permite (D1.4);
  un único instrumento (D1.6); solo órdenes a mercado (D1.7); costes materiales modelados
  (D1.8); límites de T\* (D1.9, D1.10); rescate frente a renovación (D1.11); separación
  entre método y conclusiones (D1.12); el universo se fija por regla en el método y la
  lista concreta pertenece a la muestra (D1.13).
- **Estado:** CLOSED.

### 0.2 C2 — Identidad y falsación
- **Decisión** [N]: G1 = A (marco error-estadístico); G2′ = A; G3 = B (la especificación
  excluye el contexto de evaluación); G4′ = B (reconstruibilidad por un tercero);
  NC1 a NC5.
- **Estado:** CLOSED.

### 0.3 D1.6 — Instrumento
- **Decisión** [N]: Binance USDⓈ-M Futures Perpetual.
- **Estado:** CLOSED.

### 0.4 Y-12a — Costes
- **Decisión** [N]: las órdenes a mercado son taker; usuario regular; sin descuento por
  BNB; 0,05 % por lado; 0,10 % ida y vuelta.
- **Consecuencia registrada:** el coste de v1 (comisión maker 0,02 % y
  `COST_PER_TRADE = 0.0009`) es incompatible con D1.7. **No se recalculó nada** y no se
  modificó `FRAMEWORK.md`, `backtest.py` ni el motor.
- **Estado:** CLOSED.

### 0.5 C5a — Métrica y estimandos
- **Decisión** [N]: C5a-0 a C5a-6 (separación señal/sistema; un horizonte primario;
  horizontes como múltiplos de T\*; retorno bruto sin normalizar; catálogo de funcionales;
  límite de muestreo por clase de funcional; el estimando primario excluye costes).
- **Estado:** CLOSED.

### 0.6 C6 — Moneda, sizing, concurrencia y drawdown (parcial)
- **Decisión** [N]: C6-1 a C6-5 y C6-7 aprobados; C6-6 = b; C6-10 solo en su estructura.
- **Estado:** **C6 sigue OPEN.**

---

---

# Antecedentes normativos de los que depende H3 (§1 a §6)

**Los bloques §1 a §6 NO son decisiones de H3-C-2.** Se cerraron antes de H3-C y se
registran porque H3 depende de ellos: A = One-way, B = aislado, C-1 a C-4, H1, H2
(R-1 a R-6, D-I.1, D-II.1), H3-A, H3-Bβ, AM-3, R-H3-2, H3-C-0 y H3-C-1.

**El estado actual de H3-C-2 es el del bloque §7** (DM-1 a DM-8).

---

## 1. C6-8a / C6-8b — Modo de posición y tipo de margen

| Campo | Contenido |
|---|---|
| **ID** | C6-8a (decisión A) y C6-8b (decisión B) |
| **Componente** | C6-8 — configuración del instrumento |
| **Decisión** | **A = One-way**; **B = aislado** |
| **Tipo** | [N] |
| **Estado** | CLOSED |
| **Motivo normativo registrado** | Menor complejidad de modelado y reconstrucción para el framework. Se registró explícitamente que **no** se afirma que sea más rentable, tenga mejor PF o menor drawdown, sea superior para una familia de señales ni más realista. **No se usó ningún resultado experimental** |
| **Hechos relevantes** | Mecánica documentada de Binance: una posición por símbolo con neteo en One-way; margen dedicado a la posición en aislado; liquidación con precio mark. Su vigencia para 2021–2024 quedó etiquetada como supuesto |
| **Consecuencias** | Una posición neta por símbolo; las señales opuestas netean o reducen; margen dedicado por posición; no se modelan LONG y SHORT simultáneos como exposiciones independientes |
| **Abierto tras la decisión** | C (regla de asignación de margen) y D (tratamiento de la información histórica no reconstruible) |

---

## 2. C — Regla de asignación de margen (C-1 a C-4)

| Campo | Contenido |
|---|---|
| **ID** | C-1, C-2, C-3, C-4 |
| **Componente** | C6-8 · decisión C |
| **Decisión** | **C-1a**: el margen se registra solo al nivel de la posición neta. **C-2b**: se actualiza en cada cambio de la posición neta. **C-3a**: reducción proporcional e inversión modelada como cierre completo más apertura nueva. **C-4a**: el modelo tiene una variable explícita de saldo no asignado |
| **Tipo** | [N] |
| **Estado** | CLOSED (aprobadas provisionalmente para el modelo metodológico de C) |
| **Motivo normativo registrado** | C-1a: no atribuir margen a señales de forma artificial; si C6-8e necesita métricas por señal, la atribución se resolverá allí y no se presentará como mecánica de Binance. C-2b: no introducir una regla de ajuste independiente. C-3a: registrada **expresamente como regla de modelado [I]**, no como mecánica verificada. C-4a: la cantidad concreta queda fuera |
| **Hechos relevantes** | La mecánica exacta de Binance para el ajuste del margen aislado en reducciones e inversiones **no está verificada** (ND) |
| **Consecuencias** | La unidad contable es la posición neta por símbolo; el margen solo cambia con la posición; existe un saldo no asignado explícito |
| **Abierto tras la decisión** | C-5 (margen insuficiente) y C-6 (estado tras liquidación, interfaz con C6-9) |

---

## 3. H1 — Frontera C-5 / C6-8e

| Campo | Contenido |
|---|---|
| **ID** | H1 |
| **Componente** | C6-8 · frontera entre C y C6-8e |
| **Decisión** | El núcleo de C-5 pasa a C6-8e: determinar la viabilidad, comparar margen requerido con margen disponible y decidir la consecuencia ante margen insuficiente. C conserva solo el residuo contable **C-5′**: definir qué constituye el saldo disponible, el orden de liberación y asignación dentro de un evento, y registrar el estado resultante |
| **Tipo** | [N] (ratificación) |
| **Estado** | CLOSED |
| **Motivo normativo registrado** | La consecuencia ante margen insuficiente fija exposición ejecutable; asignarla a C haría que C decidiera ejecución |
| **Abierto tras la decisión** | H2 (saldo disponible y orden contable), H3 (reparto entre competidores), H4 (consecuencia) |

---

## 4. H2 — Saldo disponible y orden contable

| Campo | Contenido |
|---|---|
| **ID** | H2 · R-1 a R-6, D-I, D-II, D-III |
| **Componente** | C6-8 · C-5′ |
| **Decisión** | **R-1 a R-6 ratificadas**: el evento comprende todos los cambios de todos los símbolos en un mismo instante; la agregación de señales de un símbolo en un único cambio neto se deriva de C-1a; la distinción d1/d3 pasa a H4; los costes de una nueva asignación dentro del margen requerido pertenecen a C6-8e/H4; el funding queda como hueco reservado; cualquier asimetría deberá declararse. **D-I.1**: flujo de liberación atómico. **D-II.1**: el saldo disponible excluye el PnL no realizado |
| **Tipo** | [N] |
| **Estado** | CLOSED para R-1 a R-6, D-I y D-II. **D-III sigue OPEN** |
| **Motivo normativo registrado** | D-I.1 y D-II.1 quedaron registradas **expresamente como reglas de modelado [I]**, no como afirmaciones sobre la mecánica de Binance |
| **Consecuencias** | Con D-I.1, la variante secuencial queda contenida en D-III.5 y el registro neto o bruto de la liberación es equivalente. Con D-II.1, el saldo no depende de ningún precio de valoración |
| **Abierto tras la decisión** | D-III (opciones D-III.1 a D-III.4; **D-III.5 quedó descartada** más tarde, por B.1′) |

---

## 5. H3 — Delimitación, forma de la salida y anonimato

| Campo | Contenido |
|---|---|
| **ID** | H3-A, H3-Bβ, AM-3, R-H3-2, H3-C-0 |
| **Componente** | H3 — reparto de margen entre exposiciones concurrentes |
| **Decisión** | **H3-Bβ = B.1′**: anonimato exigido; el reparto no puede depender de la identidad del símbolo. **H3-A = A.1**: la salida es una partición explícita (Pᵢ ≥ 0, Σ Pᵢ ≤ P, remanente P − Σ Pᵢ). **AM-3**: 0 ≤ Pᵢ ≤ rᵢ, sin estado de exceso. **R-H3-2**: H3 actúa después de C6-3. **H3-C-0 = SÍ**: rᵢ forma parte del vector que decide si dos competidores son idénticos |
| **Tipo** | [N] |
| **Estado** | CLOSED |
| **Motivo normativo registrado** | B.1′: el reparto depende solo de atributos definidos de antemano, no de la identidad del activo; se registró que **ni B.1′ ni su alternativa eran obligatorias** según el marco, y que no se introduce ninguna prioridad entre BTC, ETH, SOL ni activos futuros, ni ninguna lista de activos en el método. AM-3: Pᵢ representa el margen asignado, limitado a la necesidad. R-H3-2: H3 recibe exposiciones ya escaladas y no modifica notional ni riesgo. H3-C-0: rᵢ es una entrada fundamental y no debe ignorarse al determinar la simetría |
| **Hechos relevantes** | **B-α** (independencia del orden de enumeración) quedó ratificado como **requisito derivado**, no como elección. **D-III.5 queda descartada** como consecuencia de B.1′ [D+]. Con H3-C-0 desaparece la tensión entre anonimato y tope |
| **Consecuencias** | H3 asigna margen y no decide ejecución, ejecución parcial, notional ni el tratamiento de Pᵢ < rᵢ. La forma de salida "orden de prelación" (A.2) queda descartada |
| **Abierto tras la decisión** | H3-C (criterio), H3-D, H3-E, H4 |

---

## 6. H3-C-1 — Entradas del criterio

| Campo | Contenido |
|---|---|
| **ID** | H3-C-1 |
| **Componente** | H3-C |
| **Decisión** | **C-1a**: el criterio usa solo rᵢ, junto con {rⱼ} y P. Queda excluido usar otros atributos de las exposiciones o de las señales como variables diferenciadoras |
| **Tipo** | [N] |
| **Estado** | CLOSED |
| **Motivo normativo registrado** | El análisis no identificó ninguna necesidad funcional ratificada que requiera atributos adicionales; la alternativa ampliaría el espacio de investigación sin ser una función necesaria de H3; varias de sus capacidades pertenecen a otras capas; los atributos añadirían grados de libertad y dependencias con AM-2, C9 y H3-E; usar información de calidad de señal podría convertir a H3 en un segundo mecanismo de selección; reutilizar información de riesgo ya incorporada en rᵢ por C6-3 podría aplicar dos veces el mismo criterio |
| **Hechos relevantes** | Ninguna decisión ratificada obliga a usar atributos ni a prescindir de ellos [D+] |
| **Consecuencias** | AM-2 (conjunto de atributos admisibles) queda sin objeto dentro de H3-C; H3-E queda muy acotada; H3-C no añade dependencias con C9 |
| **Abierto tras la decisión** | H3-C-2, H3-C-3, H3-C-4 |

---

## 7. H3-C-2 · DM-1 a DM-9 y decisiones auxiliares

Las ocho decisiones comparten componente (H3-C-2, propiedades del criterio f), tipo [N] y
estado CLOSED.

### DM-1 — Uso del recurso
- **Decisión:** **(d)** — se exige **O-EF**: Σ Pᵢ = mín(P, Σ rⱼ).
- **Motivo registrado:** aceptado por el humano con las consecuencias explícitas de §E-2,
  E-4, E-5 y E-7 de `NORMATIVE_SPEC.md`. R_est se acepta como remanente estructural y no
  como desperdicio discrecional.
- **Hechos:** E-1 a E-7. O-EF ⇔ EF-a ∧ EF-b ⇔ "no desperdicio" [D+].
- **Consecuencias:** en abundancia e igualdad el reparto queda determinado; en escasez
  R_H3 = 0; quedan excluidas la regla nula, EQ y N1; B1 y B2 quedan **sin objeto**.

### DM-2 — Consistencia
- **Decisión:** **(a)** — **no** se exige O-CS.
- **Motivo registrado:** preservar el espacio de diseño mientras no exista una necesidad
  demostrada de imponer consistencia bajo reducción del problema.
- **Hechos:** con O-EF, CS-1 y CS-2(σ) coinciden [D+]. O-EF **no** implica O-CS: testigos
  SW½ y SW₁ [D+]. CS-1 queda como formulación de referencia.
- **Consecuencias:** ninguna familia excluida.

### DM-3 — Escala
- **Decisión:** **(b)** — se exige **O-HO**.
- **Motivo registrado:** decisión humana; se registró expresamente que **no** se afirma que
  O-HO sea necesaria ni consecuencia de las demás restricciones.
- **Hechos:** E-8 a E-12. O-HO solo restringe en D\* [D+].
- **Consecuencias:** **SW₁ excluida**, y con ella cualquier regla con umbrales absolutos.
  Si más adelante se eligiera una familia paramétrica, sus parámetros solo podrían ser
  relativos.

### DM-4 — Monotonía en el recurso
- **Decisión:** **(a)** — **no** se exige MR-P.
- **Motivo registrado:** no se incorpora como requisito. Se registró que **no** significa
  que MR-P sea indeseable, que no se renuncia a la monotonía agregada (garantizada por
  O-EF) y que no expresa preferencia por SW½.
- **Hechos:** E-19, E-20. O-EF no implica MR-P (SW½) [D]; MR-P no implica O-HO ni O-CS
  [D+].
- **Consecuencias:** ninguna familia excluida. La implicación O-EF ∧ MR-P ⇒ CT-P queda sin
  efecto normativo.

### DM-5 — Monotonía en las necesidades
- **Decisión:** **(a)** — **no** se exigen MR-own ni MR-others.
- **Motivo registrado:** no se incorporan como restricciones obligatorias; no se afirma que
  sean indeseables.
- **Hechos:** E-13 a E-17. Con n ≥ 3, MR-own ⇒ MR-others sigue siendo ND.
- **Consecuencias:** ninguna familia excluida. Se registró expresamente que la implicación
  MR-others ⇒ OR-award **no cierra ni predetermina DM-6**.

### DM-6 — Orden según la necesidad
- **Decisión:** **(d)** — se exigen **OR-award** y **OR-loss**.
- **Motivo registrado:** las dos pasan a formar parte de las restricciones obligatorias; no
  se afirma que las alternativas sean indeseables.
- **Hechos:** E-24 a E-27. Condición conjunta 0 ≤ Pᵢ − Pⱼ ≤ rᵢ − rⱼ [D+], interpretada como
  consistencia ordinal dentro de cada estado.
- **Consecuencias:** **PMIN y PMAX excluidas**. Espacio resultante: PRO, CEA, CEL y SW½.

### DM-7 — Entrada de competidores
- **Decisión:** **(b)** — se exige **MR-pop**.
- **Motivo normativo registrado:** el mecanismo exigirá que la entrada de nuevos
  competidores no beneficie individualmente a ningún competidor que ya estaba. No se afirma
  que las reglas que la incumplen sean indeseables en general.
- **Hechos:** E-21 a E-23. La versión agregada ya la garantiza O-EF [D+]; PRO, CEA y CEL la
  cumplen [D] / [D+]; SW½ no [D+].
- **Consecuencias:** **SW½ excluida**. Espacio resultante: PRO, CEA y CEL.

### DM-8 — Continuidad
- **Decisión:** **(e)** — se exige **CT-joint**.
- **Motivo normativo registrado:** se quiere que el mecanismo sea continuo respecto del
  estado cuantitativo completo (r, P), de modo que perturbaciones pequeñas y simultáneas de
  las entradas no produzcan saltos en las asignaciones. Se registró expresamente que **no**
  se afirma que CT-joint sea necesaria, ni consecuencia de las demás restricciones, ni que
  su mayor fuerza lógica sea por sí sola una razón.
- **Hechos:** E-28 a E-31. CT-joint ⇒ CT-P y CT-r [D]. **No se afirma** que
  CT-P ∧ CT-r ⇒ CT-joint (ND).
- **Consecuencias:** CT-P y CT-r quedan exigidas **por implicación**. Ninguna familia
  excluida: PRO, CEA y CEL las cumplen. Se activa el caso de B3 (declararlas o no de forma
  explícita), que sigue OPEN. **DM-9 no queda resuelto**: CT-joint ⇒ CT-K sigue siendo ND.

> **Nota de actualización posterior — no forma parte del registro de DM-8.**
>
> El texto de DM-8 se conserva **literal y sin modificar**, como registro histórico de lo
> que se sabía y se decidió en ese momento. Su última afirmación
> —«CT-joint ⇒ CT-K sigue siendo ND»— describe el **estado del conocimiento al cierre
> de DM-8**, no el estado matemático vigente del protocolo.
>
> **Qué ocurrió después.** La auditoría de DM-9 produjo **E-43**, que mediante el testigo
> **SW-n** resolvió esa relación: **CT-joint ⇏ CT-K**, falsa en 𝓔, 𝓔𝓗 y
> 𝓔𝓗𝓞. Dentro de 𝓒 y 𝓒′ la implicación se cumple, pero de forma
> **degenerada**: no porque CT-joint implique CT-K, sino porque la clase ya implica CT-K
> por **E-41**.
>
> **Efecto sobre DM-8: ninguno.** La decisión DM-8 = (e) y sus consecuencias registradas
> no cambian. Lo único superado es la etiqueta **ND** de esa relación concreta.
> Estado vigente: `NORMATIVE_SPEC.md` §E.6 (E-43) y la nota final de §F.

### DM-9 — Continuidad ante la entrada de un competidor (CT-K)
- **Fecha de la decisión:** 2026-09-21 (fecha documentada; a diferencia de DM-1 a DM-8, que
  se cerraron en sesiones cuya fecha exacta no consta).
- **Decisión humana** [N]: **(d)** — **NO se exige CT-K como norma independiente**, y se
  registra formalmente como **teorema [D]** derivado de condiciones ya adoptadas.
- **Motivo normativo registrado:** CT-K **no se adopta como preferencia independiente**. Su
  validez dentro de la clase vigente queda demostrada matemáticamente a partir de
  condiciones que ya fueron elegidas (O-EF por DM-1, AM-3 por H3-C-1 y MR-pop por DM-7). No
  se afirma que CT-K sea deseable ni indeseable por sí misma, ni que su carácter derivado
  sea por sí solo una razón para adoptarla o descartarla.
- **Alcance explícito de lo decidido:** lo que se decide es **el estatus normativo** de
  CT-K, no su verdad matemática. CT-K **es verdadera** para toda regla de 𝓒′; lo que
  se declara es que **no es una norma [N]**.
- **Hechos:** E-40 (T-1a), E-41 (T-1), E-42 (𝓒 ⇒ CT-K, 𝓒′ ⇒ CT-K y
  𝓒′ ∩ {CT-K} = 𝓒′) y E-43 (CT-joint ⇒ CT-K es falsa en 𝓔, 𝓔𝓗 y
  𝓔𝓗𝓞, testigo SW-n). La jerarquía lógica registrada es
  **T-1a ⇒ T-1**, y **no al revés**.
- **Hipótesis registradas:** S-a (f definida para toda cardinalidad finita), S-b (K finito)
  y **S-c** (MR-pop cuantificada sobre todo rₖ > 0, incluidas necesidades arbitrariamente
  pequeñas). **S-c es la dependencia frágil:** una futura restricción de materialidad que
  limitara MR-pop a entrantes con rₖ ≥ δ > 0 dejaría T-1 sin demostración automática. Se
  registra **como dependencia, no como decisión abierta**.
- **Consecuencias:** **ninguna familia excluida y ningún cambio en el espacio de reglas.**
  La decisión no altera 𝓒′ porque 𝓒′ ⇒ CT-K: exigir CT-K y no exigirla
  producen el **mismo conjunto de reglas**, no solo las mismas familias conocidas. PRO, CEA
  y CEL siguen siendo las candidatas. **B3 sigue OPEN** y ahora alcanza también a CT-K,
  junto a CT-P y CT-r. **No se cierra H3-C-3:** CT-K no aporta ningún criterio de selección
  de familia, porque las tres candidatas la cumplen.
- **Procedencia:** auditoría formal de CT-K, revisión adversarial de sus resultados (que
  corrigió la jerarquía T-1a/T-1, rectificó el testigo SW₁ y explicitó S-a/S-b/S-c) y
  versión corregida de la auditoría, previas a esta decisión.

### B3 — Estatus de las propiedades implicadas
- **Fecha de la decisión:** 2026-09-22 (fecha documentada).
- **Decisión humana** [N], en cinco puntos:
  - **P1 = (b)** — **CT-P** se registra como **teorema [D]** derivado, con
    **Γ = {CT-joint}** y referencia **E-28**. **No es una norma [N].**
  - **P2 = (a)** — **CT-r** recibe **el mismo estatus** que CT-P: **teorema [D]**, con
    **Γ = {CT-joint}** y referencia **E-28**. **No es una norma [N].**
  - **P3 = (b)** — **no** se añaden requisitos adicionales de trazabilidad para CT-P ni
    CT-r. Basta con registrar la propiedad, Γ = {CT-joint} y E-28. **No** se crea una
    sección de hipótesis auxiliares equivalente a S-a/S-b/S-c de DM-9.
  - **P4** — se establece una **regla metodológica general reutilizable**, **R-B3**,
    registrada en `NORMATIVE_SPEC.md` §D.
  - **P5 = (a)** — las ramas **OR-award** y **MR-pop** se declaran formalmente
    **sin objeto** dentro de B3.
- **Motivo normativo registrado:** ni CT-P ni CT-r se adoptan como preferencias
  normativas independientes. Ambas son **consecuencias demostradas** de una condición ya
  elegida (CT-joint, por DM-8 = (e)), y el protocolo las registra como tales. No se afirma
  que sean deseables ni indeseables por sí mismas.
- **Alcance explícito de lo decidido:** se decide **el estatus documental-normativo** de
  CT-P y CT-r, no su verdad matemática. Ambas **son verdaderas** para toda regla de
  𝓒′ (E-28); lo que se declara es que **no son normas [N]**.
- **Advertencia registrada:** que CT-P y CT-r reciban el **mismo estatus** (P2 = (a))
  **no** significa que sean equivalentes. Su **independencia mutua** sigue vigente y no se
  modifica: **CT-P ⇏ CT-r** y **CT-r ⇏ CT-P**, con testigos registrados en
  `NORMATIVE_SPEC.md` §F.
- **Hechos:** **E-28** (CT-joint ⇒ CT-P y CT-joint ⇒ CT-r, [D]). Las no-implicaciones
  entre CT-P y CT-r constan en §F y **no se alteran**.
- **Por qué OR-award y MR-pop quedan sin objeto** [D]: su activación dependía de que se
  exigieran MR-own o MR-others (E-16, E-17, E-18), y **DM-5 = (a)** no las exige. Ambas
  fueron decididas **directamente** como normas [N]: **DM-6 = (d)** y **DM-7 = (b)**. B3
  no las reabre.
- **Consecuencias:** **ninguna familia excluida y ningún cambio en el espacio de reglas.**
  𝓒′ ∩ {CT-P} ∩ {CT-r} = 𝓒′ (E-28), de modo que la decisión es de
  registro, no de contenido. PRO, CEA y CEL siguen siendo las candidatas. **H3-C-3 sigue
  OPEN** y B3 no le aporta ningún criterio. **DM-9 = (d) y el estatus de CT-K no se
  modifican.**
- **Procedencia:** auditoría de B3 y Decision Brief preparatorio (preguntas P1 a P5),
  previos a esta decisión.

---

## 8. Decisiones que permanecen OPEN

H3-C-3 · H3-C-4 · H3-D · H3-E · D-III · H4 · C9 · C6 · C3 · C4 · C5b · C7 · C8 ·
C10 · C-5 decisión D (tratamiento histórico R1–R4).

**DM-9 ya no figura en esta lista:** quedó CLOSED con la decisión (d).
**B3 tampoco:** quedó CLOSED con P1 = (b), P2 = (a), P3 = (b), P4 (regla R-B3) y
P5 = (a).

Ver `docs/protocol/NORMATIVE_SPEC.md` §G.

---

## 9. Matriz de trazabilidad de esta consolidación

| Decisión | Fuente reconstruida | Archivo destino | ¿Completamente respaldada? |
|---|---|---|---|
| C1, C2, D1.6, Y-12a, C5a, C6 parcial | Conversación (resumen) | `DECISION_LOG.md` §0 | **Parcial** — resumen; DR completo no consolidado |
| A = One-way, B = aislado | Conversación (DR completo) | `DECISION_LOG.md` §1 | Sí |
| C-1a, C-2b, C-3a, C-4a | Conversación (DR completo) | `DECISION_LOG.md` §2 | Sí |
| H1 | Conversación (DR completo) | `DECISION_LOG.md` §3 | Sí |
| H2 · R-1 a R-6, D-I.1, D-II.1 | Conversación (DR completo) | `DECISION_LOG.md` §4 | Sí |
| H3-A, H3-Bβ, AM-3, R-H3-2, H3-C-0 | Conversación (DR completo) | `DECISION_LOG.md` §5 | Sí |
| H3-C-1 | Conversación (DR completo) | `DECISION_LOG.md` §6 | Sí |
| DM-1 a DM-8 | Conversación (DR completo de cada una) | `DECISION_LOG.md` §7 y `NORMATIVE_SPEC.md` §C, §D | Sí |
| DM-9 | Conversación (auditoría, revisión adversarial y DR completo) | `DECISION_LOG.md` §7 y `NORMATIVE_SPEC.md` §C, §D, §E | Sí. **Las demostraciones de E-40 a E-43 y la verificación numérica de SW-n no están transcritas**: solo constan sus enunciados, hipótesis y alcance |
| B3 (P1 a P5) | Conversación (auditoría, Decision Brief y DR completo) | `DECISION_LOG.md` §7 y `NORMATIVE_SPEC.md` §C.1, §D, §G | Sí. Se apoya únicamente en **E-28**, ya registrado |
| Hechos [D] / [D+] | Conversación (auditorías de cada DM) | `NORMATIVE_SPEC.md` §E | **Parcial** — se registran los enunciados y su alcance; **las demostraciones completas y los cálculos de los testigos no se han transcrito** |
| Relaciones ND | Conversación (auditorías) | `NORMATIVE_SPEC.md` §F | Sí, con su alcance por clase |
| Colisiones de nombres | Auditoría del repositorio (2026-09-21) | `NORMATIVE_SPEC.md` §B | Sí, verificada contra el repositorio |
| Estado de la implementación | Auditoría del repositorio (2026-09-21) | `NORMATIVE_SPEC.md` §H | Sí, verificada contra el repositorio |
| Diferencias con v1 | Auditoría del repositorio (2026-09-21) | `NORMATIVE_SPEC.md` §I | Sí, verificada contra el repositorio |
| Fechas individuales de cada decisión | — | — | **No** — no documentadas con certeza |

**Elementos que siguen requiriendo la conversación:**

1. Las **demostraciones completas** de los hechos [D] / [D+] y las verificaciones
   numéricas de los testigos. Aquí solo constan los enunciados y su alcance.
2. Los **análisis previos a cada decisión** (expedientes, opciones descartadas y
   comparaciones), de los que aquí solo se registra el resultado y el motivo.
3. El **detalle de C1, C2, D1.6, Y-12a, C5a y C6 parcial** (§0).
4. Las **fechas** de cada decisión.
