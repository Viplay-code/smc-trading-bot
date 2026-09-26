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
Decision Records completos **no están consolidados todavía**. Los bloques 1 a 10 recogen el
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

> **Nota de consolidación posterior — no forma parte del registro de C6-8a/b.**
>
> Este registro no transcribió la **regla de neutralidad** que el humano fijó al preparar
> la matriz de C6-8a (§7, 2026-09-17). Texto literal:
>
> «Todas las decisiones deben quedar formuladas como una única configuración
> metodológica uniforme para todas las familias. No debe existir: una configuración para
> SMC; otra para Donchian; otra para una familia que eventualmente resulte prometedora. La
> configuración debe fijarse antes de observar resultados de la familia evaluada.»
>
> Su alcance histórico son las decisiones de esa matriz. Su **extensión a H3-C-3** es una
> decisión humana posterior (**N-H3**, §8). El contenido de este registro no cambia.

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

### R-B3 · Interpretación de la condición 1 («demostración registrada»)
- **Fecha:** 2026-09-25 (fecha documentada).
- **Decisión humana** [N], interpretación adoptada: **R-a**. Texto literal:

  > «En R-B3, condición 1, «demostración registrada» significa que el hecho consta en el
  > repositorio con su enunciado, su alcance y una referencia demostrativa, aunque la
  > demostración completa no esté transcrita en el repositorio.»

- **Naturaleza:** interpretación [N] de R-B3 (B3 · P4). No es una norma sustantiva nueva
  sobre CT-P, CT-r ni CT-K, ni una deducción [D]: la auditoría mostró que el corpus no
  fijaba el significado de «demostración registrada».
- **Límite:** la condición sigue exigiendo que exista una demostración. R-B3 sigue sin
  autorizar la etiqueta [D] para afirmaciones no demostradas. Lo que se interpreta es solo
  qué significa que esa demostración esté «registrada».
- **Fundamento documental:**
  - primera frase de R-B3: al aplicarla, «se registran la propiedad, su antecedente lógico
    Γ y su referencia demostrativa»;
  - `NORMATIVE_SPEC.md` §A: [D] es un «Hecho matemático demostrado en sesiones anteriores
    a la que cerró la decisión»;
  - `NORMATIVE_SPEC.md` §E, «Alcance de este registro»: se transcriben «sus enunciados y su
    alcance o clase, no las demostraciones», y las demostraciones completas siguen en el
    material de las sesiones de trabajo.
- **Coherencia con las aplicaciones registradas** (DM-9 = (d), B3 · P1 y P2): es una
  consecuencia de esta interpretación, no su fundamento. La auditoría identificó que usarla
  como fundamento sería circular.
- **Lecturas no adoptadas:** R-b (la demostración completa debe estar transcrita en el
  repositorio) y R-c (la demostración consta en el material de las sesiones y el
  repositorio la referencia).
- **No retroactividad:** es una aclaración interpretativa. No modifica el texto de R-B3 ni
  los registros de B3, DM-8 ni DM-9; no cambia B3 · P1 a P5, E-28 ni E-40 a E-42; no
  cambia ningún estatus [D] a [N] ni a ND; no transcribe demostraciones; no cambia el
  significado matemático de CT-P, CT-r ni CT-K; no reabre ninguna decisión cerrada.
- **Procedencia:** Decision Brief de B3, auditoría de la condición 1 de R-B3 (que
  identificó la ambigüedad), Decision Memo sobre R-a, R-b y R-c, y decisión humana.

---

## 8. H3-C-3 · Objeto (O), universo (U), arquitectura (T-0), neutralidad (N-H3), evidencia de R (R-EV), arquitectura de R_regla (G-1), G-2 (sin objeto), alcance de F2 respecto de una φ enumerativa y lugar de la declaración de T-c

### O — Objeto de selección de H3-C-3
- **Fecha de la decisión:** 2026-09-23 (fecha documentada).
- **Decisión humana** [N]: **O = C**. H3-C-3 selecciona una **entrada** de un catálogo
  heterogéneo, Cat, con type : Cat → {RULE, FAMILY}. Definiciones en
  `NORMATIVE_SPEC.md` §B.
- **Estatus epistémico:** **el expediente dejó O indeterminado; el humano resolvió la
  ambigüedad adoptando C.** El expediente **no** demuestra O = C: es una decisión humana
  de diseño del protocolo.
- **Antecedentes registrados:** la tabla fundacional del catálogo mezclaba reglas de forma
  cerrada (PRO, CEA, CEL, EQ) con familias parametrizadas sobre atributos (F-W, F-PRI,
  F-H). El vocabulario osciló entre «familia» y «regla». H3-C-4 se formuló originalmente
  solo para F-W, F-PRI y F-H.
- **Contenido:**
  - RULE designa una regla: rule(e) ∈ ℱ. FAMILY designa una familia parametrizada:
    mem(e) = {f_θ : θ ∈ Θ_e}. rule y mem tienen **dominios disjuntos**; Θ_e solo está
    definido para FAMILY.
  - out(e) = rule(e) si e es RULE; out(e, θ) = f_θ si e es FAMILY y θ está fijado.
  - **No existe la convención de «familia unitaria».**
  - **PRO, CEA y CEL son RULE.** **F-W, F-PRI y F-H son FAMILY**, con Θ_e = ND (sus
    parámetros originales dependían de atributos excluidos por C-1a). EQ, regla nula, PMIN,
    PMAX, SW½ y SW₁ son RULE. type(F-OPT) es **ND**.
  - H3-C-4 solo se activa si la entrada seleccionada es FAMILY.
  - 𝓒′ sigue siendo una clase de **reglas**. La admisibilidad de una entrada FAMILY queda
    **ND**. También queda **ND** si existe una entrada FAMILY para las reglas de
    conmutación (SW); SW½ y SW₁ siguen excluidas una a una como RULE.
- **Consecuencias:** ninguna regla se excluye ni se añade; 𝓒′ no cambia. H3-C-3 pasa a
  ser «selección de entrada»; la etiqueta «selección de familia» queda superada.
- **Procedencia:** auditoría histórica, semántica y ontológica del nodo O, auditoría de
  opciones y Decision Brief, previas a la decisión; auditoría de cierre, posterior.

### U — Universo de selección de H3-C-3 (U-A + C₁)
- **Fecha de la decisión:** 2026-09-23 (fecha documentada).
- **Decisión humana** [N]: **U = {PRO, CEA, CEL}**, definido por lista (alternativa U-A),
  con la cláusula de revisión **C₁**.
- **Estatus epistémico:** U y C₁ son decisiones humanas de diseño; el expediente no las
  demuestra. **U no se deriva** de DM-7, aunque coincida con su «Espacio resultante».
  No existe regla de construcción de U.
- **Pertenencia:** PRO ∈ U, CEA ∈ U, CEL ∈ U. F-W ∉ U, F-PRI ∉ U, F-H ∉ U. Estas tres
  **siguen en Cat y no están excluidas**: no incumplen ninguna norma y están fuera de U
  solo por alcance.
- **Hechos:** ∀e ∈ U: type(e) = RULE ∧ out(e) = rule(e) = f_e ∈ ℱ [D].
  ∀e ∈ U: rule(e) ∈ 𝓒′ [D] (E-32 más verificación directa de C-1a, B.1′, B-α, AM-3 y
  A.1). rule[U] ⊊ 𝓒′ [D] (AVG ∈ 𝓒′ por E-37, AVG ∉ rule[U]).
  U ∩ type⁻¹(FAMILY) = ∅ [D].
- **Notación registrada:** **no** se escribe U ⊆ 𝓒′ (U contiene entradas y 𝓒′
  reglas) ni rule(e) = e (una entrada es un nombre, no una regla).
- **C₁ (texto completo en `NORMATIVE_SPEC.md` §D):**
  1. U queda CLOSED en su alcance actual.
  2. U no crece automáticamente.
  3. Cualquier modificación de U requiere una decisión humana explícita.
  4. Añadir o quitar cualquier entrada, sea RULE o FAMILY, requiere reabrir U.
  5. Especificar Θ_e de una FAMILY no implica que entre en U.
  6. La compatibilidad con 𝓒′ no implica pertenencia a U.
  7. C₁ no reabre por sí misma O ni ninguna decisión normativa anterior.
  8. Si U cambia, debe evaluarse el efecto sobre T, R y H3-C-3; cómo se propaga es ND.
- **Consecuencias:** **H3-C-4 sigue OPEN, pero es inalcanzable bajo el U vigente**
  (e\* ∈ U ⇒ type(e\*) = RULE). Seleccionar dentro de U determina la regla en el mismo
  acto. **No se selecciona entre PRO, CEA y CEL:** T y R siguen OPEN, y E-38 sigue
  vigente (ninguna propiedad registrada distingue entre las tres).
- **Qué no se reabre:** O = C, H3-C-0, H3-C-1 (C-1a), 𝓒′, DM-1 a DM-9, B3, R-B3, E-32,
  E-38 ni ninguna exclusión cerrada.
- **Procedencia:** auditoría del nodo U, auditoría comparativa U-A / U-B con Decision
  Brief, y auditoría de cierre de U.

> **Nota de actualización posterior — no forma parte del registro de U.**
>
> El registro de U se conserva **literal**. Su frase «T y R siguen OPEN» y la mención de T
> en el punto 8 de C₁ describen el estado **en la fecha en que U se cerró**, cuando T era
> un nodo de trabajo.
>
> **Qué ocurrió después.** T-0 se cerró con la decisión **B** (registro siguiente): T no es
> un nodo vigente. La referencia a T en el punto 8 de C₁ queda **sin objeto**; la
> obligación de evaluar el efecto de un cambio de U sobre **R y H3-C-3** sigue vigente.
>
> **Efecto sobre U y C₁: ninguno.** U = {PRO, CEA, CEL} y C₁ no cambian.

### T-0 — Arquitectura de la decisión de H3-C-3 (decisión B)
- **Fecha de la decisión:** 2026-09-23 (fecha documentada).
- **Decisión humana** [N]: se adopta la **arquitectura B** como arquitectura vigente del
  protocolo: **O + U + R → H3-C-3**, con **R = (R_regla, R_motivo)**. La naturaleza de la
  razón **no** es un nodo T independiente. **T-0 queda CLOSED.** T no es un nodo vigente.
- **Estatus epistémico:** **el expediente no determina A ni B. El humano adopta B como
  arquitectura vigente del protocolo porque es compatible con el expediente y reproduce la
  estructura histórica de registro sin introducir un nodo independiente no requerido.**
- **Alternativa no adoptada:** **A**, O + U + T + R → H3-C-3, con T como nodo previo e
  independiente.
- **Antecedentes registrados:**
  - T no existía en el expediente histórico: la ficha de H3-C-3 no indicaba con qué clase de
    razón se elige. Surgió en los encargos del **2026-09-22**: la tipología (normativa,
    modelado/representación, empírica, metodológica) en el encargo de la auditoría de
    H3-C-3, que pedía determinar «cuál(es)» correspondían; el símbolo T y
    𝒯 = {normativa, modelado, empírica, metodológica} en el encargo de la auditoría de
    arquitectura. Ninguna decisión [N] lo adoptó como nodo.
  - En los precedentes, el humano declaró la naturaleza **en el mismo acto** de decidir y
    el registro la anotó como atributo: D1.6 («decisión de alcance de V1»), C-3a, D-I.1 y
    D-II.1 («regla de modelado [I]»), y el campo «Motivo» de DM-1 a DM-9 y de B3.
- **Contenido:**
  - **R_regla**: parte operativa. Si H3-C-3 termina por selección, aplicada a U da una única
    e\* ∈ U, con type(e\*) = RULE.
  - **R_motivo**: naturaleza o motivo de la decisión, registrado **en el mismo acto** que
    R_regla.
- **Destino de las tres funciones que representaba T:**
  1. **Naturaleza de la razón** → pasa a **R_motivo**, atributo registrado en el mismo acto
     que R_regla.
  2. **Diferimiento** → **no** pasa a R_motivo, **no** es un tipo de R y **no** es un valor
     de T. Es una situación procedimental de H3-C-3, representada con el estado existente
     **OPEN**. Si en el futuro se decide diferir, la instrucción y su condición se
     registrarán explícitamente en ese momento.
  3. **Compromiso previo con una vía** → **no** forma parte de la arquitectura vigente. Si
     alguna vez hiciera falta, requeriría una nueva decisión procedimental explícita.
- **Retiro de 𝒯:** la tipología queda **retirada como estructura del protocolo**. **No** es
  taxonomía de R_motivo. Se conserva solo como historia de auditoría.
- **R sigue OPEN.** Adoptar B no define R. Siguen sin resolver: criterio de selección,
  evidencia admisible, forma exacta de R_regla, vocabulario de R_motivo, tratamiento de
  empates, cualquier condición de diferimiento y la selección entre PRO, CEA y CEL.
- **Consecuencias:** **H3-C-3 sigue OPEN.** **H3-C-4 sigue OPEN**, inalcanzable bajo el U
  vigente. **𝓒′ no cambia**: B trata sobre cómo se decide entre entradas, no sobre
  ningún predicado de f.
- **Qué no se reabre:** O = C, U = {PRO, CEA, CEL}, C₁, C-1a, 𝓒′, DM-1 a DM-9, B3, R-B3,
  E-32 ni E-38. Las menciones de T en textos cerrados se conservan con nota posterior
  (registro de U y C₁).
- **Revisión:** B solo puede revisarse mediante una **decisión humana explícita de
  reapertura de la arquitectura**. No existe ninguna condición automática, plazo, evento
  ni prueba de revisión.
- **Procedencia:** auditoría del nodo T, auditoría de legitimidad y ontología de T (T-0) y
  auditoría de cierre de la decisión B.

### N-H3 — Extensión de la regla de neutralidad de C6-8a/b a H3-C-3
- **Fecha de la decisión:** 2026-09-23 (fecha documentada).
- **Origen [E]:** regla fijada por el humano el **2026-09-17** en la matriz de decisión de
  C6-8a, §7. Texto literal:

  > «Todas las decisiones deben quedar formuladas como una única configuración
  > metodológica uniforme para todas las familias. No debe existir: una configuración para
  > SMC; otra para Donchian; otra para una familia que eventualmente resulte prometedora. La
  > configuración debe fijarse antes de observar resultados de la familia evaluada.»

  Alcance histórico: las decisiones de esa matriz (A, B, C y D de C6-8).
- **Hecho epistemológico:** el expediente **no establecía ni deducía** que la regla
  alcanzara H3. H3 desciende de la decisión C (C-5 → H1 → H3), pero no existe ninguna
  regla registrada por la que las subdecisiones posteriores hereden las condiciones de C.
  D1.1 («núcleo general más anexos por clase») impide tratar la uniformidad entre familias
  como principio general del que deducirla.
- **Decisión humana** [N]: la regla de neutralidad de C6-8a/b **se extiende explícitamente a
  H3-C-3**. **Es [N], no [E] ni [D].**
- **Consecuencias, y solo estas:**
  - **N-H3-1:** La entrada seleccionada e\* debe quedar fijada antes de observar resultados
    de la familia de estrategias evaluada. Por tanto, R no puede seleccionar PRO/CEA/CEL
    utilizando resultados experimentales de las familias de estrategias que posteriormente
    serán evaluadas con esa configuración.
  - **N-H3-2:** existe **una única e\* para todas las familias de estrategias**. No puede haber
    una e\* para SMC, otra para Donchian ni otra para cualquier otra familia. La selección de
    H3-C-3 es una configuración común a las familias de estrategias.
- **Significado de «familias»:** familias de estrategias o señales (SMC, Donchian y las que
  se evalúen después). **No** son entradas con type(e) = FAMILY del catálogo (F-W, F-PRI,
  F-H), ni PRO, CEA o CEL. La neutralidad **no selecciona ni excluye** ninguna entrada de U.
- **Lo que N-H3 no implica:** que R sea determinista; que R sea una función; que R sea
  reconstruible por un tercero; que haga falta evidencia para seleccionar e\*; ninguna forma
  concreta de R_regla (A, B o C); ninguna preferencia ni exclusión entre PRO, CEA y CEL.
- **Efecto sobre R:** R sigue **OPEN**, con su espacio de diseño restringido por N-H3-1 y
  N-H3-2. Siguen OPEN el criterio, la forma de R_regla, los empates y la selección entre
  PRO, CEA y CEL. El determinismo de R sigue OPEN y su reconstruibilidad, ND / OPEN. La
  evidencia admisible sigue OPEN, pero **ya excluye** los resultados experimentales de las
  familias evaluadas para seleccionar e\*. Queda **ND** si otras formas de evidencia (por
  ejemplo, simulaciones calibradas con resultados de una familia) cuentan como
  «resultados de la familia evaluada».
- **Efecto sobre H3-C-3:** sigue **OPEN**. e\* deberá ser **única, común a las familias de
  estrategias y fijada antes de observar sus resultados**.
- **Qué no se reabre:** O, U, C₁, T-0 / B, 𝓒′, DM-1 a DM-9, B3, R-B3, E-32, E-38 ni
  C6-8a/b. N-H3 es una norma nueva sobre el nodo OPEN H3-C-3 / R.
- **Procedencia:** auditoría de R, auditoría de precisión (determinismo, dominio y
  reconstruibilidad), auditoría del alcance de la regla de C6-8a/b y auditoría del acto
  normativo necesario para resolver su extensión.

### N-H3 · U — Interpretación de N-H3-1: independencia de uso
- **Fecha de la decisión:** 2026-09-24 (fecha documentada).
- **Decisión humana** [N]: la ambigüedad entre «antes de observar» y «sin usar ni
  condicionarse a» se resuelve con la lectura **U, independencia de uso**. Formulación
  literal:

  > «e\* debe quedar fijada sin utilizar, ajustar ni condicionar su selección a resultados
  > experimentales de las familias de estrategias que posteriormente serán evaluadas con esa
  > configuración.»

- **Razones registradas por el humano (literales):**
  - «No queremos excluir SMC ni Donchian de H3 simplemente porque sus resultados v1 ya
    existen y ya fueron observados.»
  - «Queremos proteger la independencia de la selección de e\*, no imponer una barrera
    temporal que haga imposible evaluar familias cuyos resultados históricos ya existen.»
  - «La existencia previa de resultados no invalida por sí misma la futura evaluación.»
  - «Lo que queda prohibido es utilizar esos resultados, directa o indirectamente, para
    seleccionar e\*.»

  Las razones se registran como motivo; **el alcance operativo es el texto de N-H3-1**.
- **Lecturas no adoptadas:**
  - **T absoluta:** e\* debe fijarse antes de observar cualquier resultado de una familia que
    posteriormente será evaluada.
  - **T acotada:** e\* debe fijarse antes de observar resultados producidos por la
    evaluación de esa familia con la configuración de H3.
- **Formulación original de N-H3-1 (2026-09-23), conservada como historia:**

  > «La entrada seleccionada e\* debe quedar fijada antes de observar resultados de la familia
  > de estrategias evaluada. Por tanto, R no puede seleccionar PRO/CEA/CEL utilizando
  > resultados experimentales de las familias de estrategias que posteriormente serán
  > evaluadas con esa configuración.»

- **Siguen ND:** la periferia de «resultados» (qué productos de ejecutar una familia, sin
  medir desempeño, cuentan como resultados); la familia de calibración (una familia cuyos
  resultados se usan y que nunca se evalúa con esa configuración); los generadores de
  exposición y las simulaciones calibradas con una familia. **También sigue ND** si la
  lectura U rige la regla original de C6-8a/b.
- **Procedencia:** auditorías del alcance semántico de N-H3-1, de las lecturas T y U, de
  la lectura T acotada, de implementación y de revisión de la redacción mínima.

### R-EV — Evidencia admisible para R (Alternativa C)
- **Fecha de la decisión:** 2026-09-24 (fecha documentada).
- **Decisión humana** [N], texto literal:

  > «Para fundamentar R en H3-C-3 se adopta la Alternativa C: E1 + E2 + E3 + E4 + E5.
  > Además, E13 (fuentes documentales externas) es admisible únicamente como evidencia
  > documental/descriptiva, no como criterio automático de selección de e\* ni como sustituto
  > de una decisión normativa del protocolo. E6, E7, E8, E9, E10, E11 y E12 quedan fuera del
  > conjunto de evidencia admisible para R. En particular, E10 y E12 permanecen excluidas
  > por N-H3-1.»

- **Precisión humana del mismo día:** E14 (declaración humana sin evidencia) queda
  **incluida**, como en la definición de la Alternativa C del Decision Brief (C = B + E5, y
  B incluye E14).
- **Precisión humana del mismo día — límites de E13:** una fuente externa puede aportar
  definiciones, caracterizaciones, axiomas, propiedades matemáticas, resultados teóricos y
  antecedentes documentales sobre las reglas. No puede usarse como fundamento de R para
  aportar resultados de desempeño, backtests, resultados de trading, simulaciones, métricas
  operativas, resultados empíricos de ejecución, evidencia calibrada con familias ni ningún
  otro resultado que funcionalmente pertenezca a E6 a E12. La decisión C no cambia.
- **Estatus epistémico:** el expediente no determinaba qué evidencia es admisible para R.
  Es una decisión humana [N].
- **Alternativas no adoptadas** (Decision Brief): A (solo normativa), B (sin análisis
  computacional), D (con simulación sintética), E (con evidencia empírica no vinculada a
  familias evaluadas), F (con clases ND) y G (con resultados de desempeño de familias
  evaluadas).
- **Contenido:** tabla de clases E1 a E14 y límites de E5 en `NORMATIVE_SPEC.md` §D. Los
  límites de E5 (sin probabilidades, pesos ni frecuencias; sin datos de mercado ni
  ejecución de familias; sin motor de backtest ni métricas de trading) precisan la frontera
  con E6 a E9 a partir de las definiciones del Decision Brief.
- **Consecuencias:** H3-C-3 puede resolverse sin depender de H4, D-III, H3-D, C6, C9 ni
  C10. R-EV no cambia U ni 𝓒′. La selección de e\* queda separada de la evaluación
  posterior de las familias.
- **Cuestiones abiertas que se mantienen:** si un motivo que cita una propiedad de E3 es
  exigencia (DM nueva) o descripción; si los motivos que no describen el comportamiento de f
  son admisibles dentro de E4. **Resuelta por esta decisión:** la admisibilidad de E13, solo
  como evidencia documental o descriptiva. **Sin objeto:** la elección de distribuciones y
  métricas de simulación, porque E6 queda excluida. **No activadas y siguen ND:** ND-2,
  ND-3, ND-4 y la aplicación de U a la regla original de C6-8a/b.
- **Qué no se reabre:** H3-C-2, O, U, C₁, T-0 / B, N-H3, 𝓒′, DM-1 a DM-9, B3, R-B3, E-32 ni
  E-38.
- **Procedencia:** auditoría de dependencias de H3, auditoría de admisibilidad de evidencia
  para R, Decision Brief neutral y auditoría de consistencia previa a este registro.

### G-1 — Arquitectura de R_regla (F2, criterio único)
- **Fecha de la decisión:** 2026-09-24 (fecha documentada).
- **Decisión humana** [N], texto literal:

  > «G-1 = F2, Criterio único. R_regla adopta la arquitectura:
  > `R_regla(Ev) = argmax_{e∈U} φ(rule(e))` donde `φ` todavía NO está definido. La decisión G-1 debe
  > entenderse estrictamente como una decisión de arquitectura, no de contenido.»

- **Sobre F7**, texto literal: «NO incorpores F7 en G-1. La cuestión de permitir
  `⊥ = no-selección` queda para G-3, porque incorporarla ahora resolvería parcialmente G-3.»
- **Estatus epistémico:** el expediente no determinaba la arquitectura de R_regla. Es una
  decisión humana [N].
- **Alternativas no adoptadas** (Decision Brief de G-1): F1 (declarativa), F3
  (lexicográfica), F4 (agregación multicriterio), F5 (filtro más declaración) y F6 (función
  de elección). F7 (variante con diferimiento) no se incorpora: su cuestión queda en G-3.
- **Comprobación de consistencia previa:** sin conflicto con O, U, T-0, N-H3-1, N-H3-2,
  R-EV ni C₁.8. La forma no introduce por sí misma dependencias con H4, D-III, H3-D, H3-E
  ni C6.
- **Contenido:** fórmula, términos, hechos [D] sobre la forma y cuestiones abiertas en
  `NORMATIVE_SPEC.md` §D. Aviso de nombres: G-1 a G-11 no son G1, G2′, G3, G4′ ni G7 de C2;
  en particular, G-4 no es G4′.
- **Lo que G-1 no decide** (enumeración humana): PRO, CEA ni CEL; e\*; el contenido de φ;
  las clases E3, E4 o E5 concretas que utilizará φ; Z1; Z2; G-3; G-4; G-6; G-7; G-8; G-9;
  G-9′; G-10; G-11; F7. G-2 tampoco queda decidida.
- **Consecuencias:** **R sigue OPEN** y **H3-C-3 sigue OPEN**. De lo que el registro T-0
  dejaba sin resolver, queda fijada la arquitectura de R_regla; su contenido (φ) sigue
  abierto.
- **Qué no se reabre:** O, U, C₁, T-0 / B, N-H3, R-EV, H3-C-2, 𝓒′, DM-1 a DM-9, B3, R-B3,
  E-32 ni E-38.
- **Procedencia:** auditoría de R, Decision Brief de G-1 y auditoría de consistencia previa
  a este registro.

### G-2 — Sin objeto (D-a)
- **Fecha de la decisión:** 2026-09-25 (fecha documentada).
- **Decisión humana** [N], texto literal: «G-2 → D-a: SIN OBJETO».
- **Justificación registrada por el humano** (literal):
  - «F2 ya garantiza formalmente la invariancia de R_regla respecto de identificadores y del
    orden de enumeración.»
  - «Esa propiedad se registra como una deducción [D], no como una nueva norma.»
  - «G-2 no tiene otra función normativa indispensable.»
  - «Los contenidos residuales pertenecen a G-3, G-4, G-5/Z2, G-6, G-7, G-8 y G-9/G-9′
    según lo establecido en las auditorías.»
  - «La cuestión F2 vs F1 sobre si φ puede enumerar valores sobre U permanece ND y NO debe
    resolverse ahora.»
  - «G-1 NO se reabre.»
- **Estatus epistémico:** la decisión sobre el destino del identificador es [N]. La
  invariancia es **[D]** por R-B3: Γ = {G-1 (F2)}, con la demostración registrada en
  `NORMATIVE_SPEC.md` §D. **No es una norma nueva.**
- **Alternativas no adoptadas** (auditoría documental de G-2): D-b (mantener G-2 con un
  contenido reformulado elevado a norma) y D-c (eliminar el identificador y reasignar sus
  contenidos).
- **Contenido:** enunciado, Γ y demostración de la invariancia, y remisiones, en
  `NORMATIVE_SPEC.md` §D; fila en §G. G-2 sale de la tabla «Siguen abiertas» de G-1.
- **Remisiones** («sin objeto» no significa «decidido»): desempates → G-3;
  reconstruibilidad → G-4; identificadores como motivo → G-5 (Z2); motivo → G-6;
  preregistro → G-7; composición → G-8; instancias y tolerancia → G-9 / G-9′. Esos nodos
  siguen abiertos y sin cambios.
- **Lo que G-2 no decide:** ninguna restricción sobre cómo se define φ; el contenido de φ;
  G-3 a G-11; PRO, CEA ni CEL; e\*. La cuestión F2 / F1 (si φ puede enumerar valores sobre
  U) **sigue ND**, separada de G-2.
- **Qué no se reabre:** G-1, O, U, C₁, T-0 / B, N-H3, R-EV, H3-C-2, 𝓒′, DM-1 a DM-9, B3
  ni R-B3. La numeración G-3 a G-11 se mantiene.
- **Procedencia:** Decision Brief de G-2, auditoría semántica y formal de G2-0, G2-A,
  G2-B1 y G2-C1, auditoría de la función normativa de G-2 y auditoría documental de D-a
  y D-c.

### Alcance de F2 respecto de una φ enumerativa — resolución interpretativa
- **Fecha:** 2026-09-25 (fecha documentada).
- **Acto humano** (paráfrasis): aceptación de la conclusión de la auditoría interpretativa,
  según la cual la cuestión se resuelve como cuestión interpretativa, y autorización de su
  registro. La cuestión se registra **sin número ND**, para no confundirla con la serie ND-2,
  ND-3 y ND-4, que procede de otra familia de ambigüedades.
- **Pregunta:** si F2 admite una φ que enumere valores sobre rule[U], o si alguna norma
  cerrada lo impide.
- **Estatus epistémico:** resolución **[D]** derivada de normas cerradas. **No es [N]**. El
  acto humano autoriza su registro, pero no añade contenido normativo.
- **Antecedente conservado:** en la justificación de G-2, la cuestión quedó ND («permanece
  ND y NO debe resolverse ahora»). Ese texto se conserva como historia, sin modificarlo. La
  cuestión se resolvió después, en las auditorías posteriores sobre ella.
- **Lecturas examinadas:** L1 (textual), que se deriva sin premisas no registradas. L2
  (exclusión), que no se deriva: requiere P-L2a (la no adopción de una alternativa excluye
  su efecto) y P-L2b (un criterio de «φ enumerativa»). Como regla general, P-L2a choca con
  R-EV, donde B, no adoptada, está contenida en C.
- **Corrección registrada:** el primer Decision Brief sobre esta cuestión concluyó que hacía
  falta una decisión normativa. La auditoría interpretativa posterior corrigió esa
  conclusión.
- **Contenido:** enunciado, Γ, derivación y límites en `NORMATIVE_SPEC.md` §D. F1 queda
  excluida como forma de R_regla; no se fija un significado general de «alternativa no
  adoptada».
- **Lo que no hace:** no reabre G-1, G-2 ni R-EV; no exige una φ enumerativa; no decide el
  contenido de φ; no cambia el conjunto de e\*; no crea una libertad normativa nueva; no
  resuelve G-3 a G-11.
- **Procedencia:** Decision Brief sobre esta cuestión, auditoría interpretativa L1 / L2 y
  auditoría de impacto documental.

### Lugar de la declaración de T-c respecto de Ev — interpretación
- **Fecha:** 2026-09-25 (fecha documentada).
- **Decisión humana** [N], lectura β, texto literal:

  > «Para efectos de T-c, cuando una declaración humana se utiliza para resolver un empate
  > `|A| ≥ 2`, la declaración debe tratarse como un acto humano externo a `Ev`, posterior al
  > cálculo de `A`.»
  >
  > «Importante: esta decisión NO debe interpretarse como autorización para seleccionar
  > cualquier elemento de `U`. T-c solo puede resolver la multiplicidad existente dentro de
  > `A`.»

  Estructura: Ev → A = argmax_{e∈U} φ(rule(e)); solo si |A| ≥ 2, T-c → e\* ∈ A.
- **Aviso de nombres:** α y β designan aquí las dos lecturas del Decision Brief sobre el
  lugar de la declaración de T-c. No confundir con **B-α** (independencia del orden de
  enumeración, H3-C-1) ni con **H3-Bβ** (anonimato, `NORMATIVE_SPEC.md` §C.2).
- **Naturaleza:** interpretación [N], no deducida del corpus. Es **condicional a T-c**: queda
  sin objeto si G-3.2 no adopta T-c.
- **Interpretación de alcance adoptada con β** [N]. El texto de estos hechos no cambia; se
  fija su alcance:
  1. «F2 tiene dominio Ev y es un caso de la forma C; su codominio es U, salvo lo que decida
     G-3» (`NORMATIVE_SPEC.md` §D, G-1): vale para el **núcleo argmax**, en el que Ev
     determina A. Si |A| ≥ 2 con T-c, el valor de R_regla depende además del acto,
     restringido a A.
  2. «La forma solo usa U, rule y Ev… Una dependencia así solo podría venir del contenido
     de φ (G-10)»: exacto para el núcleo. Con β, una dependencia de nodos OPEN también
     podría venir del motivo del acto, y queda igualmente bajo G-10.
  3. «N-H3-2 se cumple por la forma»: vale para el núcleo. Para el acto, N-H3-2 se cumple
     porque la norma lo exige directamente.
  4. Paso 4 de la derivación sobre el alcance de F2, «Con F2, R_regla queda determinada
     por φ»: la premisa vale para el núcleo. La conclusión (E14 es admisible para
     fundamentar φ) no cambia.
- **Papel del acto** [D]: es externo a Ev y posterior al cálculo de A, y solo puede elegir
  e\* ∈ A. No es evidencia E14 dentro de Ev, ni entrada de φ, ni criterio de selección
  (E13). Su motivo se fundamenta solo con evidencia admisible según R-EV, que puede incluir
  E14 como fundamento, y se registra como R_motivo en el mismo acto (T-0, E14). N-H3-1 y
  N-H3-2 se le aplican directamente. No es un diferimiento ni un nodo T.
- **Consecuencia condicional para G-4** [D]: si G-3.2 adopta T-c, G-4 no podrá exigir el
  determinismo respecto de Ev para R_regla completa. G-4 sigue OPEN.
- **Lectura no adoptada:** α (la declaración como elemento de Ev, evidencia E14 dentro del
  dominio de R_regla).
- **Sigue ND (n1):** si el acto T-c ocurre una sola vez; si puede repetirse, por evento o a
  lo largo del tiempo; cuándo queda fijada e\*; si R_regla puede reaplicarse con otra Ev.
  No está asignada a ningún nodo y queda fuera de G-3.
- **Lo que no resuelve:** no modifica G-1, G-2, R-EV, E13, E14 ni T-0; no decide G-3.1
  (I-1 o I-2), G-3.2 (T-c o T-e) ni G-3.3 (⊥); no decide qué ocurre si no existe
  declaración; no decide G-4 ni G-6; no resuelve φ, A = ∅ ni n1; no introduce condiciones
  nuevas de G-3.2.
- **Procedencia:** auditoría de las combinaciones C1 a C4 de G-3, auditoría α / β, auditoría
  procedimental, Decision Brief de α / β, decisión humana, auditoría post-β y Decision
  Brief de registro.

---

## 9. Decisiones que permanecen OPEN

H3-C-3 (R) · H3-C-4 · H3-D · H3-E · D-III · H4 · C9 · C6 · C3 · C4 · C5b · C7 · C8 ·
C10 · C-5 decisión D (tratamiento histórico R1–R4).

**DM-9 ya no figura en esta lista:** quedó CLOSED con la decisión (d).
**B3 tampoco:** quedó CLOSED con P1 = (b), P2 = (a), P3 = (b), P4 (regla R-B3) y
P5 = (a).
**R-B3, condición 1:** interpretación [N] adoptada (R-a): «demostración registrada» es el
hecho con enunciado, alcance y referencia demostrativa en el repositorio, sin necesidad de
transcribir la demostración completa.
**O y U** quedaron CLOSED (§8). **T-0** quedó CLOSED con la decisión B: T no es un nodo
vigente. **N-H3** quedó CLOSED: extiende la regla de neutralidad de C6-8a/b a H3-C-3.
**R-EV** quedó CLOSED: la evidencia admisible para R es la de la Alternativa C.
**G-1** quedó CLOSED: R_regla tiene la arquitectura F2 (criterio único); φ sigue sin definir.
**G-2** quedó **sin objeto**: F2 ya garantiza la invariancia respecto de identificadores, que
se registra como [D].
El **alcance de F2 respecto de una φ enumerativa** quedó resuelto como cuestión
interpretativa [D]: ninguna norma cerrada excluye una φ enumerativa; F2 no la exige.
**Lugar de la declaración de T-c:** interpretación [N] (β): acto humano externo a Ev,
posterior al cálculo de A, que solo elige e\* ∈ A; los hechos [D] de G-1 sobre «F2» y
«dominio Ev» se refieren al núcleo argmax. Condicional a T-c. Sigue ND si el acto ocurre
una sola vez.
**H3-C-3 sigue OPEN** porque R sigue OPEN.
**H3-C-4 sigue OPEN**, pero es inalcanzable bajo el U vigente.

Ver `docs/protocol/NORMATIVE_SPEC.md` §G.

---

## 10. Matriz de trazabilidad de esta consolidación

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
| R-B3 · interpretación de la condición 1 (R-a) | Conversación (Decision Brief de B3, auditoría de la condición 1, Decision Memo y decisión humana) | `DECISION_LOG.md` §7; `NORMATIVE_SPEC.md` §D | Sí. Interpretación [N]; fundamento documental en R-B3, §A y §E |
| O = C | Conversación (auditorías del nodo O, Decision Brief, decisión humana y auditoría de cierre) | `DECISION_LOG.md` §8 y `NORMATIVE_SPEC.md` §B, §G | Sí. Decisión humana de diseño; **el expediente no demuestra O = C** |
| U = {PRO, CEA, CEL} y C₁ | Conversación (auditoría de U, auditoría comparativa U-A / U-B, decisión humana y auditoría de cierre) | `DECISION_LOG.md` §8 y `NORMATIVE_SPEC.md` §B, §D, §G | Sí. Los hechos de U se apoyan en **E-32**, **E-37** y la verificación directa de las condiciones de base, que **no tiene fila propia en §E** |
| T-0 (decisión B) | Conversación (auditoría de T, auditoría T-0, decisión humana y auditoría de cierre) | `DECISION_LOG.md` §8 y `NORMATIVE_SPEC.md` §B, §D, §G | Sí. Decisión humana de diseño; **el expediente no determina A ni B** |
| N-H3 (neutralidad en H3-C-3) | Conversación (texto literal de la matriz C6-8a §7; auditorías de alcance y del acto normativo; decisión humana; interpretación de uso (2026-09-24)) | `DECISION_LOG.md` §1 (nota) y §8; `NORMATIVE_SPEC.md` §B, §D, §G | Sí. Origen [E]; extensión a H3 [N]. **El texto de la regla no estaba consolidado**: se transcribe ahora literal |
| R-EV (evidencia admisible para R) | Conversación (auditoría de dependencias de H3, auditoría de admisibilidad, Decision Brief, decisión humana y precisión sobre E14) | `DECISION_LOG.md` §8; `NORMATIVE_SPEC.md` §B, §D, §G | Sí. Decisión humana de diseño; las clases E1 a E14 proceden de la auditoría de admisibilidad |
| G-1 (arquitectura de R_regla) | Conversación (auditoría de R, Decision Brief de G-1, decisión humana y auditoría de consistencia previa) | `DECISION_LOG.md` §8; `NORMATIVE_SPEC.md` §B, §D, §G | Sí. Decisión humana de arquitectura; φ sin definir |
| G-2 (sin objeto) | Conversación (Decision Brief de G-2, auditoría semántica y formal, auditoría de función normativa, auditoría documental y decisión humana) | `DECISION_LOG.md` §8; `NORMATIVE_SPEC.md` §D, §G | Sí. Invariancia [D] con la demostración transcrita completa |
| Alcance de F2 respecto de una φ enumerativa (resolución interpretativa) | Conversación (Decision Brief sobre esta cuestión, auditoría interpretativa, auditoría de impacto y aceptación humana) | `DECISION_LOG.md` §8; `NORMATIVE_SPEC.md` §D | Sí. Resolución [D] con la derivación transcrita |
| Lugar de la declaración de T-c respecto de Ev (interpretación β) | Conversación (auditoría de C1 a C4, auditoría α / β, auditoría procedimental, Decision Brief, decisión humana, auditoría post-β y Decision Brief de registro) | `DECISION_LOG.md` §8; `NORMATIVE_SPEC.md` §D | Sí. Interpretación [N], condicional a T-c; n1 sigue ND |
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
