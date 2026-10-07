# Sistema de agentes — Tax deed sales (Texas)

Orquestador + 6 agentes especialistas + revisor independiente. Cada propiedad produce un JSON validado; al final se consolida en un CSV para tu Google Sheet.

## Requisitos
- Claude Code (terminal o desktop) abierto en esta carpeta
- Python 3.9+ y `pip install jsonschema`

## Uso rápido (venta del 3-nov-2026)
1. `runs/harris-2026-11-03/params.json` ya existe:
   ```json
   {"target_margin_pct": 25, "exit_strategy": "duplex"}
   ```
   (`exit_strategy`: `duplex` o `resale`. Ajusta el margen objetivo: es tu decisión.)
2. Abre Claude Code aquí (en tu computadora, con acceso a hctax.net) y escribe:
   > /venta harris-2026-11-03
   El agente `scout` busca la lista oficial, llena `candidatos.csv` y crea los registros; después corre todo el flujo. Si ya tienes tu propia lista, ponla en `runs/harris-2026-11-03/candidatos.csv` y el scout se salta.
   Nota: la lista de la venta del 3-nov solo existirá cuando el condado la publique.
4. Claude seguirá `CLAUDE.md`: intake → tax/title/legal/physical-risk en paralelo → valuation → reviewer → validar → CSV.
5. Importa `runs/harris-2026-11-03/consolidado.csv` en una pestaña nueva del Sheet.
6. Revisa la columna **Pendiente de Miguel** (captcha HCAD, login District Clerk, visitas, PACER).

## Re-verificación
Pide: "Modo refresh para `harris-2026-11-03`". Solo revisa estatus, gravámenes nuevos y bancarrotas. Prográmalo a T-30, T-7 y T-1 días.

## Qué NO hace
- No puja, no paga, no se registra como postor, no entra credenciales.
- No da asesoría legal: marca qué debe ver un abogado.
- No elimina el trabajo humano en captcha/login; lo lista y sigue.

## Estructura
```
CLAUDE.md                          Orquestador (flujo y reglas)
.claude/agents/                    scout, intake, tax, title, legal, physical-risk, valuation, reviewer
schema/property_record.schema.json Contrato de datos
playbook/playbook.md               Reglas aprendidas y fuentes (actualízalo)
scripts/validate_record.py         Valida esquema + reglas de evidencia
scripts/merge_to_csv.py            Consolida JSON -> CSV
examples/sample_record.json        Registro ficticio de prueba
runs/<sale_id>/                    Registros y salidas por venta
```

## Probar los scripts
```
python3 scripts/validate_record.py examples/
python3 scripts/merge_to_csv.py examples out.csv
```

## Siguientes pasos sugeridos
1. Correr 2–3 propiedades de la venta del 6-oct (ya analizadas a mano) y comparar contra tu hoja: ahí calibras los agentes.
2. Ajustar `playbook.md` con lo que el sistema se equivoque.
3. Después, agregar un agente de seguimiento post-compra (quiet title, permisos, construcción).
