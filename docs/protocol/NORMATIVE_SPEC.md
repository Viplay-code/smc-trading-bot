# Especificación normativa — Protocolo Científico V2

**Fecha de consolidación documental:** 2026-09-21
**Estado:** vigente y parcial — el Protocolo V2 sigue en curso; este documento registra
lo que está cerrado a la fecha de consolidación.
**Fuente:** sesiones de trabajo del Protocolo V2 (conversación). Ver
`docs/protocol/DECISION_LOG.md` para el registro decisión a decisión y para la matriz de
trazabilidad de esta consolidación.

---

## A. Propósito y alcance

Este documento es la **fuente canónica del estado normativo vigente del Protocolo V2**:
qué restricciones son obligatorias para el mecanismo, qué decisiones humanas las
establecieron, qué hechos matemáticos las acompañan y qué sigue abierto.

**Qué NO es este documento:**

| No es | Dónde vive eso |
|---|---|
| Implementación | `research/`, `backtest.py`, `bot.py`, `dc_v1/`, `market_data/` |
| Metodología de backtesting v1 | `FRAMEWORK.md` |
| Resultados experimentales | `FRAMEWORK.md`, CSV de la raíz |
| Arquitectura del software | `docs/architecture/TARGET_ARCHITECTURE.md` |
| Orden experimental v1 | `docs/research/EXPERIMENTAL_ROADMAP.md` |

**Relación con FRAMEWORK v1.** El Protocolo V2 es un marco distinto y posterior. No
sustituye ni corrige `FRAMEWORK.md` en esta consolidación. Donde ambos dicen cosas
distintas, se documenta la coexistencia (§I), no se armoniza.

**Etiquetas usadas en todo el documento:**

| Etiqueta | Significado |
|---|---|
| **[N]** | Decisión humana normativa. No es un resultado matemático |
| **[D]** | Hecho matemático demostrado en sesiones anteriores a la que cerró la decisión |
| **[D+]** | Hecho matemático demostrado durante el trabajo del Protocolo V2, con el alcance indicado |
| **ND** | Relación no demostrada ni refutada. **ND no significa falso** |

---

## B. Glosario y colisiones de nombres

**Ninguna de estas colisiones se resuelve renombrando.** Solo se documentan.

| Sigla | Significado A | Significado B | Significado C |
|---|---|---|---|
| **C1–C8** | **Motor de automatización experimental** (código): C1 trigger/entry genérico, C2 contrato, C3 `run_many`, C4 `expand_universe`, C5 decisión, C6 persistencia de escritura, C8 persistencia de lectura. Documentado en los docstrings de `research/*.py` | **Componentes críticos del Protocolo V2**: C1 alcance, C2 identidad y falsación, C3 nulo y comparadores, C4 control de gestión, C5 métrica y estimandos, C6 moneda/sizing/concurrencia/DD, C7 estados y re-test, C8 inferencia, C9 datos e independencia, C10 multiplicidad | **Fases de migración** C1–C3 y D en `docs/architecture/TARGET_ARCHITECTURE.md` §6.1 |
| **C6** | Persistencia de escritura del motor (`research/persistence.py`) | Componente del Protocolo V2 (moneda, sizing, concurrencia, drawdown) | — |
| **H1 / H2** | En `docs/research/EXPERIMENTAL_ROADMAP.md`: familias de experimentos v1 (p. ej. H2 = `distance`/`activation`/`be` aislados) | En el Protocolo V2: subdecisiones de C6-8 (H1 = frontera C-5 / C6-8e; H2 = saldo disponible y orden contable; H3 = reparto de margen entre exposiciones concurrentes; H4 = consecuencia de margen insuficiente) | — |
| **C2** | Contrato experimental del motor | Componente C2 del Protocolo V2 (identidad y falsación) | Fase C2 de `TARGET_ARCHITECTURE` (extracción del simulador) |

**Terminología propia de H3:**

| Término | Definición |
|---|---|
| **K** | Conjunto de competidores del evento. Un competidor es un cambio neto de posición por símbolo que requiere asignación de margen |
| **rᵢ** | Margen requerido por el competidor i. Llega a H3 ya calculado y referido a exposiciones ya escaladas por C6-3 |
| **P** | Saldo disponible del evento |
| **Pᵢ** | Margen que H3 asigna al competidor i |
| **f** | La regla de reparto: f(K, (rᵢ), P) → (Pᵢ) |
| **R_H3** | Remanente: P − Σ Pᵢ |
| **Abundancia / igualdad / escasez** | P > Σ r / P = Σ r / P < Σ r |
| **D\*** | Dominio no trivial: escasez con n ≥ 2 y necesidades no todas iguales |

**Clases de reglas** (se usan para acotar el alcance de cada hecho):

| Clase | Qué exige |
|---|---|
| **𝓔** | C-1a, B.1′, B-α, AM-3, A.1, O-EF |
| **𝓔𝓗** | 𝓔 + O-HO |
| **𝓔𝓗𝓞** | 𝓔𝓗 + OR-award + OR-loss |
| **𝓒** | 𝓔𝓗𝓞 + MR-pop — clase normativa vigente antes de DM-8 |
| **𝓒′** | 𝓒 + CT-joint — **clase normativa vigente** |

**Términos de H3-C-3: objeto de selección (O = C), universo (U) y regla de selección (R,
arquitectura B).** Decisiones humanas de diseño [N] del 2026-09-23 (`DECISION_LOG.md` §8).
**El expediente no demuestra O = C**: dejó O indeterminado, y la ambigüedad se resolvió
por decisión humana. **Tampoco determina la arquitectura A ni la B**: el humano adoptó B.

| Término | Definición |
|---|---|
| **ℱ** | Espacio de todas las reglas f. 𝓒′ ⊆ ℱ es una clase de **reglas** |
| **Cat** | Catálogo de entradas registradas: PRO, CEA, CEL, F-W, F-PRI, F-H, EQ, regla nula, PMIN, PMAX, SW½, SW₁ y F-OPT. Si Cat puede ampliarse es **ND** |
| **Entrada** (e) | Elemento de Cat. Una entrada es un **nombre**, no una regla |
| **type** | type : Cat → {RULE, FAMILY}. Toda entrada tiene tipo; el valor de type(F-OPT) es **ND** |
| **RULE** | Tipo de entrada que designa una única regla |
| **FAMILY** | Tipo de entrada que designa una familia parametrizada de reglas |
| **rule(e)** | Definida solo si type(e) = RULE: rule(e) ∈ ℱ |
| **Θ_e** | Espacio de parámetros. Definido solo si type(e) = FAMILY |
| **mem(e)** | Definida solo si type(e) = FAMILY: mem(e) = {f_θ : θ ∈ Θ_e} ⊆ ℱ |
| **out(e)** | Regla producida por la entrada: out(e) = rule(e) si type(e) = RULE; out(e, θ) = f_θ si type(e) = FAMILY y θ ∈ Θ_e está fijado |
| **U** | Universo de selección de H3-C-3: **U := {PRO, CEA, CEL}**, definido por lista (§D) |
| **e\*** | Entrada que seleccione H3-C-3, con e\* ∈ U |
| **R** | Regla de selección de H3-C-3: **R = (R_regla, R_motivo)**. **R_regla** es la parte operativa: si H3-C-3 termina por selección, aplicada a U da una única e\* ∈ U. **R_motivo** es la naturaleza o el motivo de la decisión, registrado en el mismo acto que R_regla. **OPEN**: no existe todavía ningún criterio, y el vocabulario de R_motivo no está fijado. Su espacio de diseño está restringido por **N-H3-1** y **N-H3-2**, y la evidencia admisible la fija **R-EV** (§D) |

rule y mem tienen **dominios disjuntos**. **No existe la convención de «familia unitaria»**:
una RULE no es una FAMILY de un solo miembro. **U y 𝓒′ son de tipos distintos**
(entradas frente a reglas): no se escribe U ⊆ 𝓒′, sino ∀e ∈ U: rule(e) ∈ 𝓒′ (§D).

**Arquitectura vigente de H3-C-3 (decisión B): O + U + R → H3-C-3.** El diferimiento **no**
es un componente de R: es una situación procedimental de H3-C-3, representada como OPEN.
Si se decide diferir, la instrucción y su condición se registrarán en ese momento.

**T (constructo de auditoría, retirado por la decisión B).** No es un nodo ni una variable
vigente del protocolo. Designaba la tipología 𝒯 = {normativa, modelado, empírica,
metodológica}, introducida en los encargos del 2026-09-22; se retiró sin convertirse en
taxonomía de R_motivo. No confundir con T-1, T-1a (§E.6) ni con T\* (D1.9, D1.10).

**Tipos registrados:** PRO, CEA, CEL, EQ, regla nula, PMIN, PMAX, SW½ y SW₁ son **RULE**;
F-W, F-PRI y F-H son **FAMILY**; type(F-OPT) es **ND**.

**Uso histórico de «familia».** En §E (E-6 y el título de E.5) y en §F, «familia» se
conserva en su sentido anterior, equivalente a «regla». El término técnico **FAMILY** es
solo el tipo de entrada definido aquí.

---

## C. Estado del Protocolo V2

### C.1 Decisiones cerradas de H3-C-1 y H3-C-2

**H3-C-1 — restricciones estructurales del reparto**

| Id | Contenido |
|---|---|
| **C-1a** [N] | f usa únicamente K, rᵢ, {rⱼ}, P y magnitudes derivadas de ellos. Quedan excluidos la identidad del símbolo, otros atributos de la exposición o de la señal, información de C6-3 distinta de la ya incorporada en rᵢ, los resultados de ejecución y cualquier orden de enumeración no declarado |
| **B.1′** [N] | Anonimato: si rᵢ = rⱼ (con los atributos admisibles iguales), entonces Pᵢ = Pⱼ. El reparto no puede depender de la identidad del símbolo |
| **B-α** | Independencia del orden de enumeración: f es función del conjunto de competidores. Requisito **derivado** de R-1, del determinismo y de G4′ |
| **AM-3** [N] | 0 ≤ Pᵢ ≤ rᵢ. No existe estado de exceso |
| **A.1** [N] | Σ Pᵢ ≤ P, y el remanente es R_H3 = P − Σ Pᵢ. La salida de H3 es una partición explícita (decisión H3-A = A.1) |

**H3-C-2 — propiedades del criterio de reparto**

| Decisión | Resultado | Tipo | Estado |
|---|---|---|---|
| DM-1 | **(d)**: se exige **O-EF** | [N] | CLOSED |
| DM-2 | **(a)**: **no** se exige O-CS | [N] | CLOSED |
| DM-3 | **(b)**: se exige **O-HO** | [N] | CLOSED |
| DM-4 | **(a)**: **no** se exige MR-P | [N] | CLOSED |
| DM-5 | **(a)**: **no** se exigen MR-own ni MR-others | [N] | CLOSED |
| DM-6 | **(d)**: se exigen **OR-award** y **OR-loss** | [N] | CLOSED |
| DM-7 | **(b)**: se exige **MR-pop** | [N] | CLOSED |
| DM-8 | **(e)**: se exige **CT-joint** | [N] | CLOSED |
| DM-9 | **(d)**: **no** se exige CT-K como norma independiente; queda registrada como **teorema [D]** (E-40 a E-42) | [N] | CLOSED |

**H3-C-2 — decisiones auxiliares**

| Decisión | Resultado | Tipo | Estado |
|---|---|---|---|
| B1, B2 | Sin objeto (por DM-1 = (d)) | — | CLOSED |
| **B3** | **P1 = (b)**: CT-P como teorema **[D]**, Γ = {CT-joint}, E-28 · **P2 = (a)**: CT-r, mismo estatus · **P3 = (b)**: no se añade trazabilidad adicional · **P4**: regla **R-B3** (§D) · **P5 = (a)**: OR-award y MR-pop, **sin objeto** | [N] | CLOSED |

**Por qué OR-award y MR-pop quedan sin objeto dentro de B3** [D]: su condición de
activación era que se exigieran las propiedades que las implican (E-16, E-17 para
OR-award; E-18 para MR-pop), y **DM-5 = (a)** no exige MR-own ni MR-others. Además ambas
se decidieron **directamente como normas [N]**: OR-award por **DM-6 = (d)** y MR-pop por
**DM-7 = (b)**. **B3 no las reabre.**

### C.2 Antecedentes normativos de los que depende H3

**Estas decisiones NO forman parte de H3-C-2.** Se cerraron **antes** de H3-C y se
registran aquí porque H3 carece de sentido sin ellas. El estado actual de H3-C-2 es el de
§C.1; confundir ambos bloques daría por nuevas decisiones que ya estaban tomadas. Su
desarrollo está en `DECISION_LOG.md` §1 a §6.

| Id | Decisión |
|---|---|
| **C6-8a, decisión A** [N] | Modo de posición: **One-way** |
| **C6-8b, decisión B** [N] | Tipo de margen: **aislado** |
| **C-1** [N] | C-1a: unidad contable = posición neta; sin atribución de margen a señales |
| **C-2** [N] | C-2b: el margen se actualiza en cada cambio de la posición neta |
| **C-3** [N] | C-3a: reducción proporcional; inversión modelada como cierre completo más apertura nueva. **Regla de modelado [I], no mecánica verificada de Binance** |
| **C-4** [N] | C-4a: el modelo tiene una variable explícita de saldo no asignado. La cantidad no se fija |
| **H1** [N] | Frontera: el núcleo de C-5 (viabilidad, comparación requerido/disponible y consecuencia) pertenece a C6-8e/H4. C conserva el residuo contable C-5′ |
| **H2 · R-1 a R-6** [N] | Ratificaciones de estructura del evento y de fronteras |
| **H2 · D-I** [N] | D-I.1: flujo de liberación atómico (margen, PnL realizado y coste en el mismo momento). Regla de modelado |
| **H2 · D-II** [N] | D-II.1: el saldo disponible excluye el PnL no realizado. Regla de modelado |
| **H3-A** [N] | A.1: la salida de H3 es una partición |
| **H3-Bβ** [N] | B.1′: anonimato exigido |
| **AM-3** [N] | Tope Pᵢ ≤ rᵢ |
| **R-H3-2** [N] | H3 actúa después de C6-3 |
| **H3-C-0** [N] | rᵢ forma parte del vector que decide si dos competidores son idénticos |
| **H3-C-1** [N] | C-1a: el criterio usa solo rᵢ, {rⱼ} y P |

### C.3 Decisiones de componentes del Protocolo V2 anteriores a C6-8

Cerradas en conversación. **Su Decision Record completo no está consolidado todavía**; en
`DECISION_LOG.md` figuran solo como resumen.

| Componente | Estado |
|---|---|
| C1 (alcance) | CLOSED — D1.1 a D1.13, P1.a a P1.d |
| C2 (identidad y falsación) | CLOSED — G1 = A, G2′ = A, G3 = B, G4′ = B, NC1 a NC5 |
| D1.6 (instrumento) | CLOSED — Binance USDⓈ-M Futures Perpetual |
| Y-12a (costes) | CLOSED — market ⇒ taker, usuario regular, sin BNB, 0,05 % por lado, 0,10 % ida y vuelta |
| C5a (métrica) | CLOSED — C5a-0 a C5a-6 |
| C6 parcial | C6-1 a C6-7 y C6-10 (estructura) aprobados; C6-6 = b. **C6 sigue OPEN** |

---

## D. Espacio normativo actual

### Obligatorio

| Propiedad | Enunciado |
|---|---|
| **O-EF** | Σ Pᵢ = mín(P, Σ rⱼ) |
| **O-HO** | f(K, λr, λP) = λ · f(K, r, P) para todo λ > 0 |
| **OR-award** | rᵢ ≥ rⱼ ⇒ Pᵢ ≥ Pⱼ |
| **OR-loss** | rᵢ ≥ rⱼ ⇒ rᵢ − Pᵢ ≥ rⱼ − Pⱼ |
| **MR-pop** | K ⊂ K′, con P y r_K fijos ⇒ Pᵢ(K′) ≤ Pᵢ(K) para todo i ∈ K |
| **CT-joint** | (r, P) ↦ Pᵢ(K, r, P) es continua en (0, ∞)ᴷ × [0, ∞), para cada K y todo i |

Más las restricciones estructurales de §C.1: C-1a, B.1′, B-α, AM-3 y A.1.

### Propiedades implicadas que NO son normas

Ninguna de las tres es una decisión [N]. Todas se cumplen necesariamente dentro de la clase
vigente 𝓒′, pero por **implicación demostrada**, no por elección normativa.

| Propiedad | Enunciado | Por qué se cumple en 𝓒′ | Estatus |
|---|---|---|---|
| **CT-P** | Con K y r fijos, P ↦ Pᵢ(K, r, P) es continua | Implicada por CT-joint (E-28) | **Teorema [D]**, no [N] — **B3 · P1 = (b)**. Γ = {CT-joint}; referencia **E-28** |
| **CT-r** | Con K y P fijos, r ↦ Pᵢ(K, r, P) es continua en (0, ∞)ᴷ | Implicada por CT-joint (E-28) | **Teorema [D]**, no [N] — **B3 · P2 = (a)**, mismo estatus que CT-P. Γ = {CT-joint}; referencia **E-28** |
| **CT-K** | **Continuidad ante la entrada de un competidor.** Para cada K, cada k ∉ K, cada r_K ∈ (0, ∞)ᴷ y cada P ≥ 0: **lím_{rₖ → 0⁺} Pᵢ(K ∪ {k}, (r_K, rₖ), P) = Pᵢ(K, r_K, P)** para todo i ∈ K | Implicada por **O-EF ∧ AM-3 ∧ MR-pop** (E-40, E-41). CT-joint **no** interviene | **No es [N]** — **DM-9 = (d)**. Es un **teorema [D]** |

**Precisiones de la definición de CT-K** (parte del enunciado registrado, no añadidos):

- El dominio es **rₖ > 0** y el límite es **por la derecha**: rₖ = 0 **no pertenece** al
  dominio de f, por lo que CT-K es una condición de **frontera**, no un caso particular de
  CT-r (que es continuidad en el abierto (0, ∞)^{K ∪ {k}}).
- Que el propio entrante reciba Pₖ → 0 **no hace falta exigirlo**: lo garantiza AM-3 [D].
- CT-K **no** es continuidad respecto de K en ninguna topología sobre conjuntos: compara
  Pᵢ(K) con Pᵢ(K ∪ {k}) a través de la proyección de coordenadas sobre K, y traslada toda
  la variación a la única variable real rₖ. Cualquier noción topológica sobre K exigiría
  **estructura adicional** que el protocolo no tiene, y sería una propiedad **distinta**
  (**ND**: no evaluable con el material actual).

> **DM-9 = (d) [N].** CT-K **no** se adopta como preferencia normativa independiente. Su
> validez dentro de la clase vigente está **demostrada** a partir de condiciones que ya
> fueron elegidas: **𝓒′ ⇒ CT-K** (E-42). No se afirma que CT-K sea deseable ni
> indeseable por sí misma.

**Las implicaciones que sostienen a CT-P y CT-r se mantienen expresamente** [D, E-28]:
**CT-joint ⇒ CT-P** y **CT-joint ⇒ CT-r**. Γ = {CT-joint} para ambas, por DM-8 = (e).

**Mismo estatus no significa equivalencia.** CT-P y CT-r reciben el mismo estatus por
**B3 · P2 = (a)**, pero son **propiedades distintas y mutuamente independientes**:
**CT-P ⇏ CT-r** y **CT-r ⇏ CT-P**, con testigos registrados en §F. B3 **no** afirma
que sean equivalentes ni intercambiables, y **no** altera esas no-implicaciones.

**Alcance de B3** (§C.1): se aplicó a **CT-P** y **CT-r**. **CT-K** ya tenía su estatus
fijado por **DM-9 = (d)**. Las ramas **OR-award** y **MR-pop** quedaron **sin objeto**
(**B3 · P5 = (a)**).

### Regla metodológica R-B3

> **R-B3 (B3 · P4) [N].** Cuando una propiedad quede **demostrada** como consecuencia
> lógica de condiciones o normas ya adoptadas, su estatus es **[D]**: se registran la
> propiedad, su **antecedente lógico Γ** y su **referencia demostrativa**, y **no** se
> convierte automáticamente en una norma **[N]** nueva.
>
> **Condiciones de aplicación. Las tres son necesarias:**
>
> 1. Debe existir una **demostración registrada**. R-B3 **no autoriza** etiquetar [D]
>    ninguna afirmación no demostrada: sin demostración registrada, el estado sigue siendo
>    **ND**.
> 2. El **antecedente Γ debe estar explícito**: qué condiciones ya adoptadas la implican.
> 3. Debe mantenerse la distinción entre **propiedad matemáticamente derivada [D]** y
>    **preferencia normativa [N]**. R-B3 no convierte una en la otra en ningún sentido.
>
> **Límites de R-B3:**
>
> - Es una regla **metodológica** sobre cómo se documenta el protocolo, **no** una
>   restricción sobre f: no añade, quita ni modifica ninguna regla de reparto, y **no
>   cambia 𝓒′**.
> - **No invalida ninguna decisión [N] posterior** que establezca un requisito
>   independiente. Si una decisión humana futura exige como norma una propiedad que
>   además sea derivable, **esa decisión prevalece**; R-B3 fija únicamente el estatus por
>   defecto en ausencia de tal decisión.
> - No prejuzga cómo documentar las **hipótesis auxiliares** de una demostración: eso se
>   resuelve caso por caso, como en §E.6 con S-a, S-b y S-c.
>
> **Aplicaciones registradas:** **DM-9 = (d)** para CT-K; **B3 · P1 = (b)** y
> **B3 · P2 = (a)** para CT-P y CT-r.

### No obligatorio

| Propiedad | Enunciado | Decisión |
|---|---|---|
| **O-CS** | Consistencia bajo reducción a subgrupos (formulación de referencia: CS-1) | DM-2 = (a) |
| **MR-P** | P′ ≥ P ⇒ Pᵢ(P′) ≥ Pᵢ(P) | DM-4 = (a) |
| **MR-own** | rᵢ′ ≥ rᵢ ⇒ Pᵢ′ ≥ Pᵢ | DM-5 = (a) |
| **MR-others** | rⱼ′ ≥ rⱼ (j ≠ i) ⇒ Pᵢ′ ≤ Pᵢ | DM-5 = (a) |

**"No obligatorio" no significa "indeseable".** Las cuatro decisiones registran
explícitamente que no se afirma nada sobre el valor de esas propiedades.

**CT-K no figura en esta tabla.** No es obligatoria como norma (DM-9 = (d)), pero tampoco
es opcional de hecho: **toda** regla de 𝓒′ la cumple necesariamente (E-42). Su lugar
es la tabla de propiedades implicadas de más arriba. Las cuatro propiedades de esta tabla,
en cambio, **pueden fallar** dentro de 𝓒′.

### Universo de selección de H3-C-3: U = {PRO, CEA, CEL}

**U := {PRO, CEA, CEL}** [N], decisión humana del 2026-09-23 (`DECISION_LOG.md` §8).
U está **definido por lista**: no existe regla de construcción de U, y U **no se deriva**
de DM-7 aunque coincida con su «Espacio resultante».

| Entrada | type | rule(e) = f_e |
|---|---|---|
| **PRO** | RULE | Pᵢ = rᵢ · mín(1, P / Σ r) |
| **CEA** | RULE | Pᵢ = mín(rᵢ, λ), con λ tal que Σ Pⱼ = mín(P, Σ r) |
| **CEL** | RULE | Pᵢ = máx(0, rᵢ − μ), con μ ≥ 0 tal que Σ Pⱼ = mín(P, Σ r) |

> **PRO, CEA y CEL NO están seleccionadas. H3-C-3 permanece OPEN.**

**Hechos sobre el U vigente:**

- **∀e ∈ U: type(e) = RULE ∧ out(e) = rule(e) = f_e ∈ ℱ** [D]. Seleccionar e\* ∈ U
  determina la regla en el mismo acto. Esto no cierra H3-D, H3-E, D-III ni H4.
- **∀e ∈ U: rule(e) ∈ 𝓒′** [D]. O-EF, O-HO, OR-award, OR-loss, MR-pop y CT-joint por
  **E-32**; C-1a, B.1′, B-α, AM-3 y A.1 por inspección directa de las tres fórmulas (sin
  fila propia en §E). Es un hecho sobre este U, **no una norma** sobre universos futuros.
- **rule[U] ⊊ 𝓒′** [D]: AVG ∈ 𝓒′ (E-37) y AVG ∉ rule[U].
- **U ∩ type⁻¹(FAMILY) = ∅** [D]. Por tanto e\* ∈ U ⇒ type(e\*) = RULE, y **H3-C-4 es
  inalcanzable bajo el U vigente** (§G).

El espacio de reglas admisibles es potencialmente infinito [I]. Estas tres son las
candidatas **estudiadas** que sobreviven, no una enumeración exhaustiva: U es un
**alcance declarado**, no una descripción de 𝓒′.

### Entradas FAMILY de Cat fuera de U

| Entrada | type | Θ_e | Estado |
|---|---|---|---|
| **F-W** | FAMILY | ND | En Cat · **fuera de U** · no evaluada |
| **F-PRI** (antes «F-PRI general») | FAMILY | ND | En Cat · **fuera de U** · no evaluada |
| **F-H** | FAMILY | ND | En Cat · **fuera de U** · no evaluada |

**«Fuera de U» no significa «excluida».** Estas entradas **no incumplen ninguna norma**:
no tienen definición formal y no se han evaluado. Sus parámetros originales, w(aᵢ) y
ρ(aᵢ), dependían de atributos que C-1a excluye, y no existe una re-especificación sobre
K, rᵢ, {rⱼ} y P; solo podrían ser admisibles como funciones de rᵢ. La admisibilidad de
una entrada FAMILY es **ND**. Están fuera de U por **alcance**, y solo C₁ puede cambiarlo.

### C₁ — Cláusula de revisión de U

> **C₁ [N]**, decisión humana de diseño del 2026-09-23. El expediente no la demuestra.
>
> 1. U queda **CLOSED** en su alcance actual: {PRO, CEA, CEL}.
> 2. U **no crece automáticamente**. No existe regla de construcción de U.
> 3. Cualquier modificación de U requiere una **decisión humana explícita**.
> 4. **Añadir o quitar cualquier entrada**, sea RULE o FAMILY, requiere reabrir U.
> 5. Especificar Θ_e de una FAMILY **no** implica que e entre en U.
> 6. Que una entrada sea compatible con 𝓒′ **no** implica que pertenezca a U.
> 7. C₁ **no reabre por sí misma** O ni ninguna decisión normativa anterior. Una
>    modificación de U solo afectaría a O si la entrada propuesta no pudiera tener tipo
>    RULE ni FAMILY, y a 𝓒′ o a una DM solo si dependiera expresamente de ellas.
>    Añadir entradas nuevas a Cat exige decidir antes si Cat puede ampliarse (hoy ND).
> 8. Si U cambia, debe evaluarse el efecto del cambio sobre T, R y H3-C-3, que dependen
>    de U. Cómo se propaga ese efecto **no está definido (ND)**.

> **Nota posterior — no forma parte del texto de C₁.** El punto 8 menciona T, que era un
> nodo de trabajo cuando se cerró U. Tras la decisión B (`DECISION_LOG.md` §8), T no es un
> nodo vigente y esa referencia queda **sin objeto**. La obligación de evaluar el efecto
> de un cambio de U sobre **R y H3-C-3** sigue vigente.

### Neutralidad de la selección de H3-C-3 (N-H3)

**Origen [E].** La regla de neutralidad pertenece históricamente a **C6-8a/b**: la fijó el
humano el **2026-09-17** en la matriz de decisión de C6-8a, §7, para las decisiones de esa
matriz. Texto literal:

> «Todas las decisiones deben quedar formuladas como una única configuración
> metodológica uniforme para todas las familias. No debe existir: una configuración para
> SMC; otra para Donchian; otra para una familia que eventualmente resulte prometedora. La
> configuración debe fijarse antes de observar resultados de la familia evaluada.»

**Extensión a H3-C-3 [N]** (2026-09-23, `DECISION_LOG.md` §8). El expediente **no
establecía ni deducía** que la regla alcanzara H3. El humano la extiende explícitamente a
H3-C-3. **Es [N], no [E] ni [D].** Sus únicas consecuencias son:

| Id | Restricción sobre H3-C-3 y R |
|---|---|
| **N-H3-1** | e\* debe quedar fijada sin utilizar, ajustar ni condicionar su selección a resultados experimentales de las familias de estrategias que posteriormente serán evaluadas con esa configuración |
| **N-H3-2** | Existe **una única e\* para todas las familias de estrategias**: no puede haber una e\* para SMC, otra para Donchian ni otra para cualquier otra familia. La selección de H3-C-3 es una configuración común a las familias de estrategias |

**Interpretación [N]** (2026-09-24): en H3-C-3, «antes de observar resultados» se interpreta
como independencia de uso; la formulación operativa es N-H3-1.

**«Familias» significa aquí familias de estrategias o señales** (SMC, Donchian y las que se
evalúen después). **No** significa entradas con type(e) = FAMILY del catálogo (F-W, F-PRI,
F-H), ni PRO, CEA o CEL. La neutralidad **no selecciona ni excluye** ninguna entrada de U.

**Lo que N-H3 no implica:** que R sea determinista; que R sea una función; que R sea
reconstruible por un tercero; que haga falta evidencia para seleccionar e\*; ninguna forma
concreta de R_regla; ninguna preferencia ni exclusión entre PRO, CEA y CEL. Tampoco cambia
O, U, C₁, T-0 / B, 𝓒′, DM-1 a DM-9, B3 ni R-B3. Solo restringe el uso de resultados
experimentales en la selección de H3-C-3 y entre qué familias debe mantenerse constante.

### Evidencia admisible para R (R-EV)

**Decisión humana [N]** (2026-09-24, `DECISION_LOG.md` §8): para fundamentar R (R_regla y
R_motivo) se adopta la **Alternativa C** del Decision Brief sobre evidencia admisible. El
expediente no determinaba esta elección.

> **Aviso de nombres.** E1 a E14 designan **clases de evidencia**; no confundir con los
> hechos matemáticos E-1 a E-43 de §E. «Alternativa C» se refiere al Decision Brief sobre
> evidencia; no confundir con las formas A, B y C de R_regla, que **siguen sin elegir**.

| Clase | Definición | Estado |
|---|---|---|
| **E1** | Normas internas cerradas de H3 | Admisible |
| **E2** | Hechos matemáticos registrados (§E) y fórmulas de §D | Admisible |
| **E3** | Propiedades matemáticas de f que no están entre las 14 propiedades de H3-C-2, deducidas de las fórmulas | Admisible |
| **E4** | Criterios declarados de modelado o representación | Admisible |
| **E5** | Análisis matemático o computacional abstracto de PRO, CEA y CEL | Admisible, con los límites de abajo |
| **E6** | Simulación sintética no calibrada: distribuciones hipotéticas de rᵢ y P | **Excluida** |
| **E7** | Datos reales de mercado sin señales de ninguna familia | **Excluida** |
| **E8** | Simulaciones calibradas con una familia y generadores de exposiciones | **Excluida** |
| **E9** | Productos de ejecutar una familia que no miden desempeño (recuento de señales, concurrencia, rᵢ empíricos) | **Excluida** |
| **E10** | Resultados de desempeño de familias que se evaluarán | **Excluida**; además, por N-H3-1 |
| **E11** | Resultados de una familia de calibración que nunca se evalúa | **Excluida** |
| **E12** | Backtests con H3 aplicando PRO, CEA o CEL | **Excluida**; además, por N-H3-1 respecto de las familias que se evaluarán |
| **E13** | Fuentes documentales externas | Admisible **solo como evidencia documental o descriptiva**, con los límites de abajo: no es un criterio automático de selección de e\* ni sustituye una decisión normativa del protocolo |
| **E14** | Declaración humana sin evidencia | Admisible: R_regla puede ser una declaración, con R_motivo registrado en el mismo acto |

**Límites de E5.** E5 es el cálculo, simbólico o numérico, de propiedades de PRO, CEA y CEL
sobre instancias (K, r, P) especificadas explícitamente. No asigna probabilidades, pesos ni
frecuencias de ocurrencia a las instancias (si lo hace, es E6). Las instancias no proceden
de datos de mercado (E7) ni de la ejecución de ninguna familia (E8, E9). Puede requerir
código fuera del motor, pero no usa el motor de backtest, señales, operaciones ni métricas
de trading: **no es un experimento de trading**.

**Límites de E13.** Una fuente externa puede aportar definiciones, caracterizaciones,
axiomas, propiedades matemáticas, resultados teóricos y antecedentes documentales sobre las
reglas. **No** puede usarse como fundamento de R para aportar resultados de desempeño,
backtests, resultados de trading, simulaciones, métricas operativas, resultados empíricos
de ejecución, evidencia calibrada con familias ni ningún otro resultado que funcionalmente
pertenezca a E6 a E12.

**Lo que R-EV deja como estaba:**

- Admitir E3 **no reabre H3-C-2**. Usar una propiedad de E3 como **exigencia** a f requeriría
  una DM nueva; si un motivo que cita E3 es exigencia o descripción **sigue abierto**.
- Si son admisibles dentro de E4 los motivos que no describen el comportamiento de f
  (simplicidad, reconstrucción, convención) **sigue abierto**.
- ND-2, ND-3, ND-4 y la aplicación de U a la regla original de C6-8a/b **no se activan**,
  porque E7, E8, E9 y E11 están excluidas. **Siguen ND.**
- No cambia U, no introduce dependencias con H4, D-III ni C6 y mantiene la selección de e\*
  separada de la evaluación posterior de las familias.

### Entradas de Cat excluidas por norma

| Entrada | Motivo | Etiqueta |
|---|---|---|
| **SW½** (PRO si P ≤ Σ r / 2; CEA si no) | Incumple **MR-pop** (DM-7) | [D+] |
| **SW₁** (PRO si P ≤ 1; CEA si no) | Incumple **O-HO** (DM-3) | [D] |
| **PMIN** (cobertura por orden creciente de rᵢ) | Incumple **OR-award** (DM-6) | [D] |
| **PMAX** (cobertura por orden decreciente de rᵢ) | Incumple **OR-loss** (DM-6) | [D] |
| **EQ** (Pᵢ = mín(rᵢ, P/n)) | Incumple **O-EF** (DM-1) | [D] |
| **Regla nula** (Pᵢ = 0) | Incumple **O-EF** (DM-1) | [D] |
| **F-OPT** (maximizar el número de competidores cubiertos) | Choca con B.1′ y con la frontera de ejecución | [D] |

Las reglas excluidas por norma **siguen siendo testigos matemáticos válidos** de
no-implicaciones (§F).

**Formas explícitas registradas de PMIN y PMAX** (auditoría de B-α): con Lᵢ = suma de las
necesidades estrictamente menores, Uᵢ = suma de las estrictamente mayores y mᵢ = número de
competidores con la misma necesidad que i:
PMIN: Pᵢ = mín(rᵢ, máx(0, P − Lᵢ)/mᵢ). PMAX: Pᵢ = mín(rᵢ, máx(0, P − Uᵢ)/mᵢ).

### Testigos auxiliares (no son candidatas ni entradas de Cat)

| Testigo | Definición | Clase |
|---|---|---|
| **AVG** | (PRO + CEA)/2 | Pertenece a 𝓒 y a 𝓒′ [D+] |
| **MIX** | Mezcla continua de PRO y CEA con peso dependiente de P/Σ r, no monótono | Pertenece a 𝓔𝓗𝓞 [D+]; su pertenencia a 𝓒 es **ND** |
| **SW-n** | PRO si \|K\| ≤ 2; CEA si \|K\| ≥ 3 | Pertenece a 𝓔𝓗𝓞 [D+]. Cumple CT-joint e incumple CT-K y MR-pop: testigo de E-43. **No pertenece a 𝓒** |

---

## E. Hechos matemáticos demostrados

Cada hecho indica la clase en la que está demostrado. Fuera de esa clase no se afirma nada.

> **Alcance de este registro.** Los hechos de esta sección **fueron demostrados durante el
> proceso de decisión**, en las auditorías previas a cada DM. Esta consolidación documental
> transcribe **sus enunciados y su alcance o clase**, no las demostraciones.
> **Las demostraciones completas, las pruebas, los contraejemplos y los cálculos originales
> no están todavía reproducidos íntegramente en el repositorio**: siguen en el material de
> las sesiones de trabajo. Un lector no debe entender que dispone localmente de la
> demostración de cada hecho. La clasificación [D] / [D+], el contenido y el alcance de
> cada hecho se conservan exactamente como se establecieron.

### E.1 Estructura y dominio

| # | Hecho | Etiqueta |
|---|---|---|
| E-1 | Con AM-3 y A.1: R_H3 ≥ máx(0, P − Σ r). El remanente se descompone en R_est = máx(0, P − Σ r), impuesto por el tope, y R_disc = mín(P, Σ r) − Σ Pᵢ, que produce el criterio | [D+] |
| E-2 | O-EF ⇔ EF-a ∧ EF-b ⇔ "no desperdicio" (si R_H3 > 0 entonces Pᵢ = rᵢ para todo i), bajo AM-3 | [D+] |
| E-3 | EF-a y EF-b son independientes entre sí | [D+] |
| E-4 | Con O-EF: si P ≥ Σ r, entonces Pᵢ = rᵢ. El reparto queda totalmente determinado en abundancia e igualdad | [D+] |
| E-5 | Con O-EF, los casos P = 0, n = 1 y necesidades todas iguales quedan determinados: 0, mín(r₁, P) y mín(ρ, P/n) | [D+] |
| E-6 | Por tanto, la elección de familia solo tiene contenido en D\* (escasez, n ≥ 2, necesidades distintas) | [D] |
| E-7 | Con O-EF y AM-3, "Pᵢ < rᵢ" implica R_H3 = 0: todo déficit que llega a C6-8e/H4 procede de escasez, no de margen que H3 dejó sin asignar | [D+] |

### E.2 Escala

| # | Hecho | Etiqueta |
|---|---|---|
| E-8 | Con AM-3, la única homogeneidad no trivial posible es la de **grado 1**. Con grado k ≠ 1 el tope falla al hacer λ → ∞ o λ → 0, salvo reparto idénticamente nulo | [D+] |
| E-9 | O-HO equivale a la invariancia de la cobertura Pᵢ/rᵢ ante escala común, siempre que el dominio sea cerrado ante escala, rᵢ > 0 y la igualdad valga para todo λ > 0 | [D+] |
| E-10 | La transformación de escala conserva el régimen y transforma D\* en sí mismo. O-HO solo restringe en D\* | [D+] |
| E-11 | O-HO implica la invariancia ordinal, pero no al revés | [D+] |
| E-12 | Umbrales absolutos sobre P o sobre r rompen O-HO. Los umbrales relativos (a P o a Σ r) la conservan | [D+] |

### E.3 Monotonías

| # | Hecho | Clase | Etiqueta |
|---|---|---|---|
| E-13 | MR-others ⇒ MR-own | 𝓔 | [D+] |
| E-14 | MR-own ⇒ la versión agregada de MR-others (la suma de lo que reciben los demás no aumenta) | 𝓔 | [D+] |
| E-15 | Con n = 2, MR-own ⇔ MR-others | 𝓔 | [D+] |
| E-16 | MR-own ∧ MR-others ∧ B.1′ ⇒ OR-award | 𝓔 | [D] |
| E-17 | MR-others ⇒ OR-award (por E-13 y E-16) | 𝓔 | [D+] |
| E-18 | MR-others ∧ CT-K ⇒ MR-pop | 𝓔 | [D] |
| E-19 | O-EF ∧ MR-P ⇒ CT-P | 𝓔 | [D+] |
| E-20 | La versión agregada de MR-P (Σ Pᵢ no decrece con P) ya la garantiza O-EF | [D+] |
| E-21 | La versión agregada de MR-pop (Σ_{i∈K} Pᵢ no aumenta al añadir competidores) ya la garantiza O-EF | [D+] |
| E-22 | Añadir un competidor o varios es equivalente en MR-pop, y equivale a leerla como "la salida de un competidor no perjudica a los que quedan" | [D+] |
| E-23 | MR-pop solo restringe cuando \|K\| ≥ 2 y K está en escasez | [D+] |

### E.4 Orden y continuidad

| # | Hecho | Etiqueta |
|---|---|---|
| E-24 | OR-award y OR-loss son independientes entre sí, ya con n = 2 | [D] |
| E-25 | Exigir ambas equivale, para rᵢ ≥ rⱼ, a **0 ≤ Pᵢ − Pⱼ ≤ rᵢ − rⱼ**. Lo recibido y el déficit crecen con la necesidad, y la diferencia de necesidad se reparte entre ambos | [D+] |
| E-26 | Con n = 2, exigir ambas equivale a que el reparto quede entre el de CEL y el de CEA. Con n ≥ 3 no hay caracterización análoga (ND) | [D+] |
| E-27 | OR-award y OR-loss se evalúan dentro de un mismo estado. Una regla que cambia de fórmula según el estado las cumple si cada fórmula las cumple | [D+] |
| E-28 | CT-joint ⇒ CT-P y CT-joint ⇒ CT-r | [D] |
| E-29 | Con O-EF, CT-P, CT-r y CT-joint son automáticas en abundancia, en la frontera P = Σ r, cuando P → 0⁺ y con n = 1. Solo restringen en el interior de la escasez con n ≥ 2 | [D+] |
| E-30 | CT-joint ⇒ O-CS es **falso** dentro de 𝓒 (testigo AVG, que es continua e inconsistente) | [D+] |
| E-31 | Las propiedades de continuidad no se siguen del determinismo, de la reconstruibilidad (G4′), de la independencia del orden ni de la estabilidad numérica. Son conceptos distintos | [D+] |

### E.5 Familias

| # | Hecho | Etiqueta |
|---|---|---|
| E-32 | PRO, CEA y CEL cumplen O-EF, O-HO, OR-award, OR-loss, MR-pop, CT-P, CT-r y CT-joint. También cumplen CT-K, MR-P, MR-own, MR-others y O-CS | [D] / [D+] |
| E-33 | SW½ cumple O-EF, O-HO, OR-award, OR-loss y CT-K; incumple MR-pop, MR-P, MR-own, MR-others, O-CS, CT-P y CT-r | [D] / [D+] |
| E-34 | PMIN cumple O-EF, O-HO, MR-P, MR-pop, O-CS, OR-loss, CT-P y CT-K; incumple OR-award, MR-own, MR-others y CT-r | [D] / [D+] |
| E-35 | PMAX cumple O-EF, O-HO, MR-P, MR-own, MR-others, MR-pop, O-CS, OR-award, CT-P y CT-K; incumple OR-loss y CT-r | [D] / [D+] |
| E-36 | EQ y la regla nula incumplen O-EF | [D] |
| E-37 | AVG pertenece a 𝓒 y a 𝓒′ e incumple O-CS. MIX pertenece a 𝓔𝓗𝓞, cumple CT-P e incumple MR-P | [D+] |
| E-38 | Las 14 propiedades candidatas de H3-C-2 son satisfacibles a la vez: PRO y CEA las cumplen todas. Ninguna combinación de exigencias deja vacío el espacio ni lo reduce a una única regla | [D] / [D+] |
| E-39 | Las formas explícitas de PMIN y PMAX cumplen C-1a, B.1′, B-α, AM-3, O-EF y O-HO: no dependen de ninguna enumeración, y los empates se tratan por grupo | [D+] |

### E.6 Entrada de competidores y CT-K (DM-9)

| # | Hecho | Etiqueta |
|---|---|---|
| E-40 | **T-1a — resultado primario.** Bajo S-a, S-b, S-c y **O-EF ∧ AM-3 ∧ MR-pop**: para todo K, todo k ∉ K y **todo rₖ > 0**, **0 ≤ Pᵢ(K, r_K, P) − Pᵢ(K ∪ {k}, (r_K, rₖ), P) ≤ rₖ** para todo i ∈ K, y en forma agregada **0 ≤ Σ_{i∈K} [Pᵢ(K) − Pᵢ(K ∪ {k})] ≤ rₖ**. Es una cota **uniforme**, no un enunciado de límite. **No usa** O-HO, OR-award, OR-loss, CT-joint, CT-P, CT-r ni B.1′ | [D] |
| E-41 | **T-1 — corolario de E-40.** **O-EF ∧ AM-3 ∧ MR-pop ⇒ CT-K**, tomando rₖ → 0⁺ en la cota de E-40 y aplicando el encaje. El límite queda **demostrado**, no supuesto: no se usa continuidad de ninguna clase. **Dependencia lógica: E-40 ⇒ E-41, y no al revés** — un enunciado de límite no puede producir una cota uniforme. Ambos se obtienen de los mismos pasos algebraicos | [D] |
| E-42 | **𝓒 ⇒ CT-K** y **𝓒′ ⇒ CT-K**, por E-41: 𝓒 contiene O-EF, AM-3 y MR-pop, y 𝓒′ ⊆ 𝓒. Por tanto **𝓒′ ∩ {CT-K} = 𝓒′**, igualdad de conjuntos cuantificada sobre **toda** regla de 𝓒′ — afirmación distinta y más fuerte que «PRO, CEA y CEL cumplen CT-K» (E-32), que solo cubre tres reglas concretas | [D] |
| E-43 | **CT-joint ⇒ CT-K es falsa en 𝓔, 𝓔𝓗 y 𝓔𝓗𝓞** (testigo SW-n). Dentro de 𝓒 y 𝓒′ la implicación se cumple, pero de forma **degenerada**: no porque CT-joint implique CT-K, sino porque la clase ya implica CT-K por E-41 | [D+] |

> **Hipótesis de E-40 y E-41 (T-1a y T-1).** Además de O-EF, AM-3 y MR-pop:
>
> - **S-a** — f está definida **para toda cardinalidad finita** (regla de población
>   variable). Ya presupuesta por MR-pop y por el propio enunciado de CT-K.
> - **S-b** — **K es finito.** Esencial: la deducción «cada sumando ≤ la suma» exige una
>   suma finita de términos no negativos.
> - **S-c** — **MR-pop está cuantificada sobre todo rₖ > 0**, incluidas necesidades
>   arbitrariamente pequeñas. Es la lectura registrada de MR-pop —solo se fijan P y r_K— y
>   es coherente con E-22.
>
> **S-c es la dependencia frágil.** Si más adelante se introdujera una restricción de
> materialidad que limitara MR-pop a entrantes con necesidad mínima positiva (rₖ ≥ δ > 0),
> **T-1 (E-41) dejaría de estar demostrado automáticamente**: el paso al límite exige
> MR-pop para rₖ arbitrariamente pequeño. T-1a (E-40) seguiría valiendo, pero solo en el
> rango rₖ ≥ δ. Esto queda registrado **como dependencia, no como decisión abierta**: no
> se prejuzga si el umbral de materialidad pendiente en el protocolo llegará a afectar a
> MR-pop.

---

## F. Relaciones ND

**ND no significa falso.** Cuando una no-implicación está demostrada en una clase más
amplia pero no hay testigo dentro de la clase normativa, el estado dentro de esa clase
sigue siendo ND.

| Relación | Estado |
|---|---|
| MR-own ⇒ MR-others individual, con n ≥ 3 | ND en 𝓔 |
| MR-own ⇒ OR-award | ND |
| MR-own ∧ MR-others ⇒ MR-P; ídem ⇒ CT-P | Falsas en 𝓔 (testigo SW₁). **ND en 𝓔𝓗 y en 𝓒** |
| MR-others ⇒ MR-pop | ND en 𝓔 |
| O-CS ⇒ MR-P, ⇒ MR-pop, ⇒ CT-P | ND |
| MR-P ⇒ MR-pop | ND |
| MR-own ⇒ MR-pop | ND |
| CT-P ⇒ MR-pop | ND |
| CT-P ⇒ MR-P | Falsa en 𝓔𝓗𝓞 (testigo MIX). **ND en 𝓒** |
| CT-P ⇒ CT-r | Falsa en 𝓔𝓗 (testigo PMIN). **ND en 𝓒** |
| CT-r ⇒ CT-P | Falsa en 𝓔 (testigo SW₁). **ND en 𝓔𝓗 y en 𝓒** |
| CT-P ∧ CT-r ⇒ CT-joint | ND en todas las clases |
| Las restricciones de 𝓒 ⇒ CT-P, CT-r o CT-joint | ND |
| CT-K ⇒ CT-P | Falsa en 𝓔 (SW₁). **ND en 𝓔𝓗 y en 𝓒** |
| CT-K ⇒ CT-r | Falsa en 𝓔𝓗 (PMIN). **ND en 𝓔𝓗𝓞 y en 𝓒** |
| MR-pop ⇒ CT-P | Falsa en 𝓔 (SW₁). **ND en 𝓒** |
| CT-joint ⇒ MR-own o MR-others | ND |
| OR-award ⇒ MR-own | ND |
| Que exigir CT-P sea distinto de exigir CT-r dentro de 𝓒 | ND |
| Que las opciones (a) a (e) de DM-8 impongan restricciones distintas dentro de 𝓒 | ND |
| Cuántas familias además de PRO, CEA y CEL quedan en el espacio actual | ND |
| Si MIX cumple MR-pop | ND |

**Resueltas por la auditoría de DM-9, ya no son ND:** «CT-joint ⇒ CT-K» pasa a **E-43**
(falsa en 𝓔, 𝓔𝓗 y 𝓔𝓗𝓞, testigo SW-n; degenerada en 𝓒 y 𝓒′).
«MR-pop ⇒ CT-K» queda **demostrada dentro de 𝓔** por **E-41**, porque 𝓔 contiene
O-EF y AM-3; sigue siendo falsa fuera de 𝓔 (testigo EQ, que incumple O-EF).

---

## G. Estado de componentes

| Componente | Estado |
|---|---|
| H3-C-1 (C-1a, B.1′, B-α, AM-3, A.1) | CLOSED |
| H3-C-2 · DM-1 a DM-8 | CLOSED |
| H3-C-2 · B1, B2 | Sin objeto (por DM-1 = (d)) |
| H3-C-2 · DM-9 (CT-K) | CLOSED — **(d)**: no es norma [N]; queda como teorema [D] (E-40 a E-42) |
| H3-C-2 · B3 (estatus de las propiedades implicadas) | CLOSED — CT-P y CT-r quedan como teoremas **[D]** (Γ = {CT-joint}, E-28); regla **R-B3** en §D; OR-award y MR-pop **sin objeto** |
| H3-C-3 · O (objeto de selección) | CLOSED — **C**: entrada de Cat, de tipo RULE o FAMILY (§B). Decisión humana; el expediente no la demuestra |
| H3-C-3 · U (universo de selección) | CLOSED — **U = {PRO, CEA, CEL}**, definido por lista; solo revisable por decisión humana explícita (**C₁**, §D) |
| H3-C-3 · T-0 (arquitectura: ¿naturaleza de la razón como nodo T?) | CLOSED — **B**: O + U + R → H3-C-3; la naturaleza de la razón es el atributo R_motivo de R. **T no es un nodo vigente.** Decisión humana; el expediente no determina A ni B |
| H3-C-3 · N-H3 (neutralidad; extensión de la regla de C6-8a/b) | CLOSED — **N-H3-1**: e\* debe quedar fijada sin utilizar, ajustar ni condicionar su selección a resultados experimentales de las familias de estrategias que posteriormente serán evaluadas con esa configuración. **N-H3-2**: una única e\* para todas las familias de estrategias. Decisión humana [N]; no implica determinismo ni reconstruibilidad de R (§D) |
| H3-C-3 · R-EV (evidencia admisible para R) | CLOSED — **Alternativa C**: E1 a E5 y E14; E13 solo como evidencia documental o descriptiva; E6 a E12 excluidas. Decisión humana [N] (§D) |
| **H3-C-3 · R** (regla de selección, R = (R_regla, R_motivo)) | **OPEN** — sin criterio de selección, forma de R_regla, vocabulario de R_motivo ni tratamiento de empates. Evidencia admisible fijada por **R-EV** (§D); excluye además resultados experimentales de las familias que posteriormente serán evaluadas con esa configuración (N-H3-1). Espacio de diseño restringido por N-H3-1, N-H3-2 y R-EV |
| **H3-C-3** (selección de entrada en U) | **OPEN** — R sigue **OPEN**; no hay selección entre PRO, CEA y CEL. e\* deberá ser **única, común a las familias de estrategias y fijada sin utilizar, ajustar ni condicionar su selección a resultados experimentales en los términos de N-H3-1** (N-H3). Un diferimiento se representaría como OPEN, con su instrucción y condición registradas al decidirlo |
| **H3-C-4** (parámetros de la entrada seleccionada) | **OPEN** — solo se activa si type(e\*) = FAMILY. **Inalcanzable bajo el U vigente**: U ∩ type⁻¹(FAMILY) = ∅, luego e\* ∈ U ⇒ type(e\*) = RULE |
| **H3-D** (destino del remanente y reasignación) | **OPEN** |
| **H3-E** (coherencia con C6-3) | **OPEN** |
| **D-III** (visibilidad de las liberaciones dentro del evento; opciones D-III.1 a D-III.4; D-III.5 descartada por B.1′) | **OPEN** |
| **H4 / C6-8e** (viabilidad, consecuencia de Pᵢ < rᵢ, atomicidad, ejecución parcial) | **OPEN** |
| **C9** (datos, independencia, blind) | **OPEN** |
| **C6** (moneda, sizing, concurrencia, drawdown) | **OPEN** |
| Otros componentes del Protocolo V2: C3, C4, C5b, C7, C8, C10 | **OPEN** |
| C-5 · decisión D (tratamiento histórico R1–R4) | **OPEN** |

---

## H. Implementación

> **No existe implementación de H3 en el código actual.**

| Hecho | Detalle |
|---|---|
| El motor C1–C8 de `research/` **no implementa H3** | Evalúa un activo y un periodo por ejecución. No tiene capa de cartera, margen, colateral ni concurrencia |
| El sizing actual es de riesgo fijo por operación | `risk_per_trade = 0.005` en `bot.py`; `risk=0.005` por defecto en el motor |
| No existe código que verifique O-EF, O-HO, OR-award, OR-loss, MR-pop ni CT-joint | — |
| La coincidencia de nombres entre el motor C1–C8 y los componentes del Protocolo V2 **no implica ninguna correspondencia funcional** | Ver §B |

Cuando exista implementación, este documento debe indicar qué propiedad verifica qué
prueba. Hoy, la columna de implementación está vacía para todas las propiedades.

---

## I. Coexistencia con FRAMEWORK v1

Diferencias registradas, **no corregidas** en esta consolidación:

| Tema | FRAMEWORK v1 y código | Protocolo V2 |
|---|---|---|
| **Coste por operación** | Comisión maker 0,02 % por lado; `COST_PER_TRADE = 0.0009` (0,04 % de comisión ida y vuelta más 0,05 % de slippage), documentado en `FRAMEWORK.md` y `CLAUDE.md` | Y-12a: las órdenes a mercado son taker; 0,05 % por lado; **0,10 % ida y vuelta** |
| **Gates** | PF ≥ 1,5, max DD ≤ −10 %, expectativa positiva y 6–12 operaciones al mes por activo, como criterio de aceptación (`research/metrics.py::gate_check`) | Los gates no equivalen a un estado de confirmación (C2/G7). Ningún gate se ha incorporado al Protocolo V2 |
| **Identidad del experimento** | `research/schema.py::compute_contract_hash` incluye el contexto de evaluación | G3: la identidad de la proposición **excluye** el contexto de evaluación |

Estas diferencias son **de versión**. Nada de v1 se recalcula ni se modifica por esta
consolidación.
