# Playbook — Texas tax deed / auction acquisitions

Reglas aprendidas. Todos los agentes la leen antes de trabajar. Actualízala cuando aprendas algo nuevo.

## Estrategia
- Foco: lotes baldíos (tax deed) en Harris County como materia prima para dúplex. Menos competencia, sin ocupantes, menor riesgo de redención que propiedades con mejoras.
- Quiet title post-compra es manejable pero hay que presupuestarlo.
- Montgomery: ventas de ejecución de impuestos online en RealAuction; ventas HOA/constable son en las escalones del courthouse (301 N. Main St., Conroe) y NO aparecen en RealAuction.

## Benchmarks de puja (Harris, datos observados ago-2026)
- ~34% de las propiedades se vendieron a terceros.
- Prima mediana ~8.8% sobre la apertura.
- Cierre mediano ~62% del valor estimado.
- El tope fijo de $45,000 fue eliminado (7-oct-2026): el agente de valuación debe calcular un techo por propiedad.

## Secuencia de due diligence
1. Intake: estatus actual de la venta, apertura, cause no., cuenta.
2. Impuestos: saldo por año (hctax saledetail), impuestos post-judgment, exenciones.
3. Título/gravámenes: índice del County Clerk (RP), liens IRS / ciudad / HOA, lis pendens, TDHCA si hay casa móvil.
4. Legal: demandados, citación por publicación (riesgo TRCP 329 hasta ~2 años tras el judgment), PACER.
5. Físico/riesgo: inundación (FEMA efectivo + borrador MAAPnext), floodway, zonificación, tamaño real del lote.
6. Valuación: comps, techo de puja, costo total estimado.
7. Revisor: contradicciones y decisión.

## Reglas de evidencia
- `verified` solo si se leyó de una fuente primaria. Citar URL o número de instrumento.
- Homestead es INFERIDO por tasa efectiva si no se puede leer HCAD (captcha). Marcar `inferred` y explicar.
- Búsquedas por apellido común (Gonzalez, Ramirez) se truncan en 200 resultados: marcar `inferred` y pedir confirmación por nombre completo.
- Una liberación de lien visible solo en el índice (sin imagen) es `inferred`, no `verified`.
- Un lien federal sin renovación: civil (28 USC 3201) puede haber expirado; restitución penal (18 USC 3613) puede seguir activa. Confirmar identidad del deudor antes de concluir.
- Sitios de terceros (BlockShopper, etc.) pueden tener errores: verificar contra el sitio del appraisal district antes de usar en documentos notariados.

## Fuentes y limitaciones conocidas
| Fuente | Uso | Limitación |
|---|---|---|
| hctax.net/property/listings/saledetail?account=... | Saldo por año | — |
| search.hcad.org | Exenciones, valor, clase | Captcha → bloqueo humano |
| County Clerk RP index (cclerk) | Gravámenes, escrituras | Solo índice, sin imágenes |
| hcdistrictclerk.com | Casos, demandados | Requiere login → bloqueo humano |
| Daily Court Review (avisos públicos PDF) | Citación por publicación | — |
| TDHCA mhweb | Título de casas móviles | — |
| FEMA FRD (grids Depth_/WSE_) + MAAPnext | Inundación | Borrador no es regulatorio; reportar ambos |
| PACER | Bancarrota | Requiere cuenta |
| montgomery.texas.realforeclose.com | Ventas online Montgomery | — |
| montgomery.tx.publicsearch.us / mcad-tx.org | Records Montgomery | — |
| foreclosehouston.com (F.I.L.S.) | Listas de pre-foreclosure y ventas | — |
| montgomerycountynews.net | Avisos legales | Bloquea crawlers: usar búsqueda web |

## Decisiones (etiquetas)
COMPRA FUERTE · CONDICIONAL · VIGILAR · BAJA · DESCARTADA · SOLO CERCA DE LA APERTURA · NO PARA DUPLEX

## Descarte automático (el revisor debe proponerlo)
- Lote dentro de floodway.
- Lien federal activo confirmado sin vía de extinción.
- Casa móvil con título personal no transferido por la venta y valor que depende de ella.
- Zonificación que impide el uso objetivo (p. ej. dúplex) sin posibilidad de variance razonable.
