# HANDOFF — Sistema de análisis de Tax Deed Sales (Harris County, TX)

Documento para otra IA que deba **revisar, auditar y reestructurar** este proyecto. Estado al **2026-10-16**.
Usuario: Miguel (inversionista, bilingüe EN/ES, responde en español). Estrategia declarada: **lotes baldíos en Harris County para construir dúplex** (también Montgomery, aún sin implementar). Venta objetivo: **2026-11-03** (`sale_id = harris-2026-11-03`).

Repo: `mag442-dot/Claude---Harris-tax-deed`, rama `master` (sin PRs). Lee primero `CLAUDE.md` (orquestador), `playbook/playbook.md`, `README.md` y este archivo.

---

## 1. Qué hace el sistema (una frase)
Toma la lista oficial de propiedades de una venta de impuestos, la cruza con fuentes públicas (HCAD, tesorería, FEMA, County Clerk), pasa las candidatas por agentes especializados y un revisor independiente, y entrega una tabla en un Google Sheet. **Nunca puja, paga ni usa credenciales** (regla inquebrantable).

## 2. Arquitectura en capas
```
Fuentes públicas ──► Scripts determinísticos (scripts/) ──► JSON por propiedad (runs/<sale>/records/)
                                   │                                  ▲
                                   └─► Agentes LLM (.claude/agents/) ──┘  (title, reviewer; solo su sección)
                                                   │
        analisis.csv / resumen_sheet.csv ◄──────── build_analysis, summary_export
                                                   │
                       Google Sheet (webhook Apps Script) ◄── push_to_sheet.py
```
Principio de diseño: **todo dato es un "finding"** `{value, status, source, retrieved_at, note}` con `status ∈ {verified, inferred, unknown, blocked}`. Sin fuente primaria no hay `verified`. Cada etapa escribe **solo su sección** del JSON; solo el revisor escribe `review`. Contrato en `schema/property_record.schema.json`; `scripts/validate_record.py` lo exige (más reglas: `verified` requiere `source`; `blocked` requiere `human_blockers`; COMPRA FUERTE requiere techo numérico y nada bloqueado en tax/title/legal).

## 3. Secciones del registro y quién las escribe
| Sección | Escritor | Contenido |
|---|---|---|
| `intake` | `candidates_to_records.py` + `enrich_from_hcad.py` | Apertura, notas del condado; `hcad_*`: dueño, dirección, clase, lote, construcción, valores, exenciones, homestead, escrituras |
| `tax` | `tax_statement.py` | Estado de cuenta por año, años en sentencia, impuestos post-sentencia, "cola" estimada del comprador |
| `title` | `title_search.py` (crudo) + agente `title` (interpretación, solo 21 lotes) | Hits del índice del Clerk por nombre; vesting deed, hipotecas, liens, qué podría sobrevivir |
| `legal` | `legal_context.py` | Fechas/ventana TRCP 329, tipo de venta; demandados, citación y bancarrota **bloqueados** |
| `physical` | `parcel_check.py` (sustituye a `flood_check.py`) | Polígono de parcela, FEMA efectiva por área, floodway, ciudad, dimensiones estimadas |
| `valuation` | `valuation.py` | Valor proxy (HCAD), cierre esperado, costo total, **techo de puja teórico** |
| `review` | `review_rules.py` (previa mecánica) → agente `reviewer` (21 lotes) | Decisión, razón, contradicciones, condiciones para comprar |

Escrituras concurrentes: `scripts/_recio.py::save_sections` relee el archivo justo antes de escribir y reemplaza solo las secciones propias (los scripts corren en paralelo).

## 4. Flujo por venta (comandos)
Todos con `python3 -I scripts/<x>.py runs/harris-2026-11-03 [cuentas…]`. Dependencias: Playwright + Chromium (`/opt/pw-browsers/chromium`), `shapely`, `jsonschema`.
1. `fetch_harris_list.py` — Playwright acepta los términos de hctax.net, pagina la lista (10 filas/pág.) → `candidatos.csv` (incluye `anios_en_sentencia`) + `scout_report.md`.
2. `candidates_to_records.py` — crea registros base (no sobrescribe).
3. `enrich_from_hcad.py runs/… <dir>` — **bulk de HCAD** descargado de `https://download.hcad.org/data/CAMA/2026/` (`Real_acct_owner.zip`, `Real_building_land.zip`, `Real_jur_exempt.zip`; ~600 MB, descomprimir fuera del repo). Sin captcha.
4. `screen_list.py` → `screening.csv` (niveles A vacío / B casa sin homestead / C casa con homestead / D comercial). Homestead = exención RES/PAR/APR/FIR en el roll; **se excluyen** por decisión de Miguel.
5. En paralelo para las cuentas sin homestead (`/tmp/…/nh.txt` en la sesión; recalcular de `screening.csv`): `tax_statement.py`, `parcel_check.py`, `title_search.py` (el más lento, ~15 s/cuenta), luego `legal_context.py`, `valuation.py`, `review_rules.py`.
6. `build_analysis.py` → `analisis.csv`; `sheet_export.py` → `analisis_sheet.csv`; `shortlist.py` → `shortlist.txt` (lotes vacíos con CONDICIONAL/SOLO CERCA, sin floodway, con apertura y estado de cuenta).
7. **Agentes LLM**: 3 × `title` y 3 × `reviewer` (7 cuentas cada uno) sobre la lista corta. Luego `refresh_review_numbers.py` actualiza las cifras dentro de revisiones de agente si cambió la valoración (no toca la decisión).
8. Entrega: `push_to_sheet.py` (pestaña `Analisis`) y `summary_export.py` + `push_to_sheet.py --file resumen_sheet.csv --tab Resumen --no-build` (pestaña `Resumen`: solo las que pasaron).

Comando de usuario: `/venta <sale_id>` (`.claude/commands/venta.md`). Rutina diaria `trig_01GnKxpNdQ5xUXzfvNw6nVMB` (8:47 a.m. hora de Houston): solo refresca la lista y avisa de cambios; **no** corre el análisis completo; se desactiva tras 2026-11-03; sesión nueva sin conector de Drive.

## 5. Fuentes y alcance real (probado desde el entorno de nube con egress restringido)
| Fuente | Uso | Estado |
|---|---|---|
| `hctax.net/Property/listings/taxsalelisting` | Lista de la venta | OK con navegador (JS + términos). 182 propiedades el 2026-10-13 (66 el día 11) |
| `hctax.net/property/listings/saledetail?account=` | Estado de cuenta | OK para cuentas certificadas (104/136); 32 devuelven "uncertified" → `blocked` |
| `download.hcad.org/data/CAMA/2026/*` | Dueños, valores, exenciones, escrituras | OK |
| `www.gis.hctx.net/arcgis/rest/services/HCAD/{Parcels,HCAD_Cities}` | Polígonos, ciudad | OK (1 cuenta ausente) |
| FEMA NFHL `hazards.fema.gov/.../NFHL/MapServer/28` | Zona efectiva | OK. MAAPnext (borrador) **no** leído |
| `www.cclerk.hctx.net` RP index | Gravámenes/escrituras | OK sin login, **solo índice** (sin imágenes), búsqueda por nombre o descripción |
| `search.hcad.org`, `hcdistrictclerk.com`, PACER | Exenciones web, demandados, bancarrota | Captcha/login/cuenta → **bloqueado**; siempre queda como `human_blockers` |
| Zillow/Redfin/MLS | Comparables | No utilizables → **no hay comps** |

Dominios permitidos que el usuario tuvo que abrir en "Network access": `hctax.net`, `script.google.com`, `script.googleusercontent.com` (más los de HCAD/FEMA/Clerk que ya respondían).

## 6. Entrega a Google Sheet
Vía A (preferida): webhook **Google Apps Script** (`apps_script/Code.gs`, pasos en `apps_script/README.md`) autenticado por `TOKEN` en Propiedades del script; el script de Python lee `SHEET_WEBHOOK_URL` y `SHEET_WEBHOOK_TOKEN` del entorno. Reemplaza el contenido de una pestaña por llamada; las columnas `property_id`/`account_no` se guardan como texto (Google quita ceros iniciales). Vía B: conector Google Drive `create_file` con CSV (crea un Sheet nuevo cada vez; obliga a pegar el CSV en el prompt, ineficiente). Sheet actual: `Harris_TaxDeed_Analisis_2026-11-03_sin_homestead` en la carpeta "Real estate - Claude" (pestañas `Analisis`, `Resumen`, `Info`, y una `Untitled` vieja).

## 7. Resultados al 2026-10-16 (para calibrar expectativas)
- 182 propiedades; 181 con datos HCAD; 45 con homestead (excluidas); **136 analizadas**; entre ellas 54 lotes vacíos (nivel A), 72 casas, 10 otros.
- 21 lotes de la lista corta con agentes: **10 CONDICIONAL**, 9 VIGILAR, 1 NO PARA DUPLEX, 1 BAJA. **0 COMPRA FUERTE** (imposible mientras `legal` esté bloqueado).
- Las otras 115 solo tienen la decisión mecánica de `review_rules.py`.

## 8. Limitaciones y riesgos conocidos (revisar con escepticismo)
1. **Los techos de puja son teóricos.** `valuation.py` asume reventa al valor de mercado HCAD sin comparables, retorno 25% sobre costo, quiet title $4,000 y cierre 3% (supuestos **míos**, editables en `params.json`). Cierre esperado = max(apertura×1.088, valor×0.507); 0.507 es la mediana de 14 lotes vendidos el 04/08/2026 (hoja `Harris_TaxDeed_Terrenos_Vendidos_2026`, PropertyOnion). Con esos supuestos casi todo pasa el filtro: `review_rules.py` **no discrimina** (≈60 CONDICIONAL). La salida dúplex **no se evalúa** (sin costo de construcción ni zonificación/restricciones).
2. **Bug ya corregido y vigente como lección:** el condado muestra "Tax Years in Judgement" como rango (`2004 - 2018`); se leyó como dos años y se inflaron las colas de impuestos. Aun así `taxes_in_judgment` es poco fiable (hay años imposibles para el año de la causa; 23 cuentas no lo traen → se usa el total adeudado como cota superior).
3. **Aperturas ambiguas:** algunas son < 5% del valor HCAD (p. ej. $935.66 en casas de $250k) o muy superiores a la deuda (0 Burt St: $64k vs ~$25k adeudados). No se sabe qué incluye la apertura. No se debe tratar como costo total.
4. **Búsqueda del Clerk por nombre es ruidosa** (nombres comunes → cientos de filas). Se filtra por coincidencia de la subdivisión HCAD (heurística: hasta 3 tokens de `Desc`), lo que puede dar falsos negativos/positivos. Solo índice; tipo/monto/supervivencia de liens **desconocidos**. Un `LIEN` sin subtipo puede ser de ciudad, HOA, estado, etc. `L/P` (lis pendens) puede ser la propia demanda de impuestos.
5. **Legal vacío por diseño:** demandados, citación por publicación y bancarrota requieren login/PACER. La ventana TRCP 329 (2 años) se calcula solo por fechas. El texto de redención es inferencia para abogado, no asesoría legal.
6. **Discrepancias de datos detectadas por revisores:** área de lote HCAD vs polígono GIS (hasta −24%); valor HCAD vs valor del condado; propiedades "vacías" cuyo legal indica townhomes o franjas de calle privada; escritura posterior a la sentencia (dueño en registro ≠ dueño demandado); un posible strike-off a las entidades (0162670050026).
7. **Cobertura:** 32 cuentas sin estado de cuenta; 1 cuenta fuera del GIS (`0680420010029`); 1 fuera de HCAD (`1163550010076`); 1 dueño genérico omitido en la búsqueda del Clerk (`0122840200003`). Los agentes solo leyeron 21 de 136.
8. **Montgomery y la versión ChatGPT:** no implementados. En Drive existe `Tax_Deed_System_V1_Harris_Nov_3_2026.xlsx` (modelo de 10 agentes, puntajes A+..KILL, `Evidence Log`, `DD Queue`, reglas CORE/KILL); **no se integró** y tiene un error de formato (Target Profit `2500000.0%`). Puede servir de contraste conceptual.
9. **Seguridad:** el webhook es público ("Cualquier persona"); el token usado en las pruebas era **débil y quedó expuesto en el chat**: debe rotarse. Nunca documentar URL/token en el repo. El token no está en ningún archivo versionado.
10. **Acoplamientos frágiles:** `review_rules.py` distingue revisiones de agente por la frase "nunca COMPRA FUERTE sin esa revision" en la `rationale` (mejor: un campo `reviewed_by`). `build_analysis.py` y `summary_export.py` repiten esa heurística. Contar contradicciones excluye notas que empiezan con `"[20"`. `nh.txt` (lista de cuentas sin homestead) vive fuera del repo.
11. Datos personales: dueños y direcciones provienen de registros públicos, pero el repo puede ser privado; no volverlo público sin decisión de Miguel.

## 9. Sugerencias para quien reestructure (ordenadas por valor)
1. Reemplazar el modelo de valoración por uno con **comparables reales** o con resultados históricos de ventas (extender la hoja del 04/08 con más meses) y calibrar con `runs/harris-2026-08-04/` (14 lotes con precio de cierre real).
2. Agregar un campo explícito `review.reviewed_by` y eliminar las heurísticas por texto.
3. Un único orquestador (`scripts/run_sale.py`) que ejecute la secuencia completa con reintentos, logs y paralelismo controlado; hoy es una cadena manual de comandos.
4. Cálculo correcto de la "cola" de impuestos con las reglas del condado (qué años van en la sentencia, jurisdicciones, penalidades, fecha de pago), y lectura de la apertura (qué incluye).
5. Lectura de **imágenes** del Clerk (OCR) para tipo/monto de liens, y búsqueda por descripción legal automatizada para todas.
6. Evaluar dúplex: restricciones deed, reglas de lote de Houston (Cap. 42), zonificación de Baytown/Pasadena/Tomball/La Porte, frontage mínimo a partir del polígono.
7. Integrar Montgomery (RealAuction; HOA/constable en escalinatas del courthouse) y el seguimiento posterior a la compra.
8. Pruebas automatizadas (hoy solo hay pruebas manuales de scripts con datos de ejemplo `examples/sample_record.json`).

## 10. Mapa de archivos
```
CLAUDE.md                     orquestador y reglas
HANDOFF.md                    este documento
README.md                     guía de uso (es)
playbook/playbook.md          reglas aprendidas, benchmarks, fuentes
schema/property_record.schema.json
.claude/agents/               scout, intake, tax, title, legal, physical-risk, valuation, reviewer
.claude/commands/venta.md     /venta <sale_id>
apps_script/                  Code.gs + README (webhook a Google Sheets)
scripts/                      todo el pipeline (ver §4); _recio.py = escritura segura
examples/sample_record.json
runs/harris-2026-11-03/       venta objetivo: candidatos, records/, analisis*.csv, resumen_sheet.csv, shortlist.txt, params.json, screening.csv, hcad_enrichment.csv
runs/harris-2026-08-04/       calibración: 14 lotes ya vendidos (cierre real en `notes`); no se ha corrido el pipeline completo
```
Nota: de los agentes definidos solo `title` y `reviewer` se ejecutaron con LLM; `tax`, `legal`, `physical-risk`, `valuation` e `intake` fueron sustituidos por scripts determinísticos (sus definiciones siguen en `.claude/agents/`).
