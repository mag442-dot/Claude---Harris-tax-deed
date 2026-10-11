# Conectar el repo con tu Google Sheet (una sola vez, ~5 min)

Resultado: `python3 scripts/push_to_sheet.py runs/<sale_id>` actualiza **el mismo Sheet** (pestaña `Analisis`)
sin versiones nuevas, sin pegar texto a mano y sin conector de Drive. Sirve también en rutinas.

1. Abre (o crea) el Google Sheet destino. Ej.: el de la carpeta "Real estate - Claude".
2. **Extensiones > Apps Script**. Borra lo que haya, pega el contenido de `apps_script/Code.gs` y guarda.
3. En Apps Script: **Configuración del proyecto (engrane) > Propiedades del script > Añadir propiedad**:
   nombre `TOKEN`, valor = una clave larga al azar (ej. 32+ caracteres). Guárdala, la necesitas en el paso 5.
4. **Implementar > Nueva implementación > Tipo: Aplicación web**. Ejecutar como: **Yo**. Quién tiene acceso: **Cualquier persona**.
   (Hace falta "Cualquier persona" porque quien llama es un script, no tú; el TOKEN es lo que protege.)
   Autoriza los permisos y copia la **URL de la aplicación web** (termina en `/exec`).
5. En la configuración del entorno de Claude Code (nube): **Variables de entorno / secretos**
   - `SHEET_WEBHOOK_URL` = la URL del paso 4
   - `SHEET_WEBHOOK_TOKEN` = el TOKEN del paso 3
   y en **Network access** permite `script.google.com` y `script.googleusercontent.com`.
   (En local: `export SHEET_WEBHOOK_URL=... SHEET_WEBHOOK_TOKEN=...`.)
6. Prueba: `python3 scripts/push_to_sheet.py runs/harris-2026-11-03`

Notas de seguridad: no pongas la URL ni el token en el repo. Si se filtran, cambia el `TOKEN` en Apps Script
(las llamadas viejas dejan de funcionar al instante) o elimina la implementación.
Si cambias `Code.gs`, hay que crear una **nueva versión** en Implementar > Administrar implementaciones.
