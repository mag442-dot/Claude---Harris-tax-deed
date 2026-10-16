# Revisión independiente en MODO BARATO (instrucciones para el agente `reviewer`)

Usa este texto como prompt de cada agente `reviewer` cuando una rutina o `/venta` lo lance. Cada agente recibe **hasta 7 cuentas** (números HCAD) y solo edita sus archivos `runs/<sale_id>/records/<property_id>.json`, sección `review` (+ añade a `human_blockers`).

Antes: lee `CLAUDE.md`, `playbook/playbook.md`, `runs/<sale_id>/params.json` y `HANDOFF.md` (sección 8, límites conocidos).

## Reglas
- NO lances agente `title` y NO hagas búsquedas web nuevas ni sesiones de navegador: trabaja solo con lo que ya está en el registro.
- `review` trae una pre-revisión mecánica (su `rationale` contiene "nunca COMPRA FUERTE sin esa revision"): reemplázala con tu criterio, mismo esquema: `decision` (COMPRA FUERTE, CONDICIONAL, VIGILAR, BAJA, DESCARTADA, SOLO CERCA DE LA APERTURA, NO PARA DUPLEX), `rationale` (3-5 frases en español, con los 2 hechos decisivos), `bid_ceiling` y `all_in_cost_estimate` (copiados de `valuation`; si te parecen inconsistentes dilo en `contradictions`, no los cambies), `contradictions[]`, `conditions_to_buy[]` (concretas y verificables).
- `valuation.bid_ceiling` es TEÓRICO: asume reventa al valor de mercado HCAD, sin comparables, 25% de retorno, quiet title $4,000 y cierre 3%. En casas el valor HCAD ignora estado y ocupación: da una idea con descuentos de 20-30%. Estrategia de Miguel: lotes baldíos para dúplex; juzga las casas como reventa/rehab y di que están fuera de la estrategia.
- `legal` está BLOQUEADO (login del District Clerk / PACER) => COMPRA FUERTE no está permitido. Aplica los descartes automáticos del playbook (floodway, lien federal activo sin vía de extinción, casa móvil no transferida, zonificación que impide el uso).
- `title` solo tiene filas CRUDAS del índice del Clerk por nombre (inferred). Solo las filas cuya `Desc` coincide con `intake.hcad_legal` pertenecen al predio. LIEN / A/J / JUDGE / L/P / CONT / LEVY / T/L son banderas para abogado, nunca conclusiones. Solo índice, sin imágenes.
- `tax.taxes_in_judgment` viene del campo del condado "Tax Years in Judgement" (un rango 'a - b' se expande). Si es desconocido, la cola de impuestos falta o es cota superior.

## Caza de contradicciones (todas)
(a) Dueño HCAD / `hcad_owner_since` / escrituras posteriores a la sentencia vs. dueño demandado (`tax.assessed_owner_county`, `legal.judgment_date`): una transferencia después de la sentencia es posible defecto de citación. (b) Cola de impuestos vs. `valuation.all_in_costs`. (c) Liens de `title` que podrían sobrevivir vs. un modelo de costos que los supone cero. (d) Zona FEMA / % SFHA / ciudad en `physical`. (e) Área de lote HCAD vs. GIS; valor HCAD vs. valor del condado. (f) Algo marcado `verified` sin `source`. (g) Dueños sucesión/fallecidos/entidades, inquilinos, ocupación. (h) Apertura muy pequeña frente al valor (<5%) o mayor que el total adeudado: ¿qué incluye?

Si la evidencia es escasa, prefiere CONDICIONAL o VIGILAR e indica exactamente qué la mejoraría. No eres abogado: "attorney review recommended". Valida con `python3 scripts/validate_record.py runs/<sale_id>/records`.
Devuelve una línea por propiedad: decisión + razón + número de contradicciones, y una línea de totales.
