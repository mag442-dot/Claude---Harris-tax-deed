---
description: Corre el flujo completo de tax deed para una venta (ej. /venta harris-2026-11-03)
argument-hint: <sale_id>
---

Corre el flujo completo de `CLAUDE.md` para la venta `$ARGUMENTS`, de principio a fin y sin pedirme confirmación en cada paso:

1. `scout`: si `runs/$ARGUMENTS/candidatos.csv` está vacío o no existe, búscalo en la fuente oficial.
2. `intake` y luego `tax`, `title`, `legal`, `physical-risk` en paralelo por propiedad.
3. `valuation`, después `reviewer` en contexto limpio.
4. `python3 scripts/validate_record.py runs/$ARGUMENTS/records` y corrige lo que falle.
5. `python3 scripts/merge_to_csv.py runs/$ARGUMENTS/records runs/$ARGUMENTS/consolidado.csv`.
6. Entrégame el resumen y la lista de pendientes humanos (captcha, login, visitas).

Si algo está bloqueado, regístralo y sigue con el resto. Nunca pujes ni uses credenciales.
