# Automatización Nóminas: Drive -> Sheets + KPIs

Este proyecto procesa PDFs de nómina desde una carpeta de Google Drive, normaliza conceptos y vuelca los datos a Google Sheets. Además, incluye dashboard Streamlit con KPIs mensuales y anuales.

## Componentes

- `extractor.py`: extracción PDF (multi página) + clasificación de conceptos + validación de neto.
- `drive_ingestor.py`: ingesta automática de Drive -> Sheets (recursiva en subcarpetas), con control de duplicados.
- `kpi_builder.py`: cálculo de métricas mensuales, anuales y comparativas YoY.
- `app.py`: dashboard Streamlit de análisis de KPIs.
- `subcategorias.json`: catálogo editable de matching de conceptos -> subcategorías.

## 1) Instalación

Requisitos recomendados:

- Python 3.11 (también válido 3.10+)

```bash
python3 -m pip install -r requirements.txt
```

## 2) Configuración

1. Crea un Service Account en Google Cloud.
2. Habilita APIs:
   - Google Drive API
   - Google Sheets API
3. Descarga el JSON de credenciales y guárdalo como `credentials.json`.
4. Comparte:
   - la carpeta de Drive origen
   - la hoja de cálculo destino
   con el email del Service Account (Editor).
5. Crea `config.json` desde `config.example.json`:

```json
{
  "credentials_path": "credentials.json",
  "drive_folder_id": "ID_CARPETA_DRIVE",
  "spreadsheet_id": "ID_SPREADSHEET"
}
```

Usa ruta relativa en `credentials_path` para que el mismo `config.json` funcione en local y en GitHub Actions.

## 3) Ejecutar ingesta automática

```bash
python3 drive_ingestor.py --config config.json
```

Opcional:

```bash
python3 drive_ingestor.py --config config.json --limit 5
```

## 4) Qué escribe en Sheets

- Hoja `Nominas`:
  - Año, Mes, Concepto, Importe, Categoría, Subcategoría, file_id, file_name
- Hoja `Control`:
  - file_id, file_name, md5_drive, source_folder_breadcrumb, renamed_to, target_folder_breadcrumb, rules_version, processed_at_utc, status, error

`Control` evita reprocesar el mismo archivo por `file_id` y también por `md5_drive` (deduplicación lógica por contenido).
La ingesta también acota la búsqueda por `modifiedTime` (con margen de seguridad) usando la última ejecución registrada en `Control`.

## 5) Renombrado y organización automática en Drive

Cada PDF procesado se renombra con formato:

- `Nómina <Mes> <Año>.pdf`

y se mueve a subcarpeta anual dentro de la carpeta raíz:

- `/2025`, `/2026`, etc.

Si la subcarpeta anual no existe, se crea automáticamente.

## 6) Dashboard de KPIs (Streamlit)

```bash
streamlit run app.py
```

El dashboard muestra:

- KPIs mensuales: bruto, neto, % IRPF, ahorro fiscal, consumo en especie, ingresos totales
- KPIs anuales: bruto, neto, % IRPF efectivo, IRPF medio, ahorro fiscal, ingresos totales, deltas YoY
- Bloque anual de Jubilación y bloque anual de ESPP/RSU (con detalle mensual en expander)
- Evolución y comparativa YoY
- Desglose mensual pivotado (Concepto/Subcategoría vs meses)
- Definiciones de fórmulas clave

Filtros disponibles en la app:

- Año (`Todos`, `2025`, `2026`, ...)
- Mes/Periodo (`Todos`, `YYYY-MM`)

### Despliegue en Streamlit Community Cloud

1. Sube este proyecto a GitHub.
2. En Streamlit Community Cloud -> New app:
   - Repository: tu repo
   - Branch: `main`
   - Main file path: `app.py`
3. En App settings -> Secrets, añade:
   - `SPREADSHEET_ID`
   - `GOOGLE_CREDENTIALS_JSON` (JSON completo del service account)
4. Guarda y redeploy.

Ejemplo de formato en `.streamlit/secrets.toml.example`.

## 7) Programarlo (ejemplo con cron)

Ejecuta cada 15 min:

```bash
*/15 * * * * cd "/Users/dferrer/Documents/Nóminas" && /usr/bin/python3 drive_ingestor.py --config config.json >> ingestor.log 2>&1
```

## 8) Automatización con GitHub Actions (recomendado)

Ya existe el workflow `.github/workflows/ingesta_nominas.yml`.

### Secrets necesarios en GitHub

En el repositorio: Settings -> Secrets and variables -> Actions -> New repository secret

- `GOOGLE_CREDENTIALS_JSON`: contenido completo del service account JSON
- `DRIVE_FOLDER_ID`: ID de la carpeta de Drive con las nóminas
- `SPREADSHEET_ID`: ID del Google Sheet destino

### Ejecución

- Manual: Actions -> `Ingesta Nominas Drive to Sheets` -> Run workflow
- Programada: día 1 de cada mes a las 08:00 UTC
- El workflow primero ejecuta checks (`py_compile`) y tests (`pytest`); solo si pasan, corre la ingesta.

Puedes pasar `limit` en ejecución manual para pruebas.

## 9) Notas operativas

- `credentials.json` y `config.json` no deben subirse al repositorio.
- La lectura de Drive es recursiva en subcarpetas.
- Si necesitas reprocesar un PDF concreto, elimina su `file_id` en la pestaña `Control` y vuelve a ejecutar ingesta.
- `rules_version` en `Control` permite auditar con qué versión de `subcategorias.json` se clasificó cada fichero.
- Deduplicación: si un PDF se vuelve a subir con otro nombre/ID pero mismo contenido (`md5_drive`), se omite automáticamente.

## 10) Tests

Ejecutar tests unitarios:

```bash
python3 -m pytest -q
```

Cobertura actual de tests:

- parser de período y normalización monetaria
- clasificación de conceptos y signo de deducciones
- cálculo de KPIs mensuales/anuales y comparativa YoY (a partir de `Nominas`)
- deduplicación y corte incremental por `modifiedTime` en ingesta Drive
