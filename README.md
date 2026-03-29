# Automatización Nóminas: Drive -> Supabase + KPIs

Este proyecto procesa PDFs de nómina desde una carpeta de Google Drive, normaliza conceptos y vuelca los datos a Supabase (PostgreSQL). Además, incluye dashboard Streamlit con KPIs mensuales y anuales.

## Componentes

- `extractor.py`: extracción PDF (multi página) + clasificación de conceptos + validación de neto.
- `drive_ingestor.py`: ingesta automática de Drive -> Supabase (recursiva en subcarpetas), con control de duplicados.
- `kpi_builder.py`: cálculo de métricas mensuales, anuales y comparativas YoY.
- `app.py`: orquestador Streamlit (filtros + flujo principal).
- `nominas_app/ui/*`: render de tarjetas, tablas, gráficas y secciones de calidad.
- `nominas_app/services/*`: preparación de dataframes para vistas y alertas.
- `subcategorias.json`: catálogo editable de matching de conceptos -> subcategorías.

### Estructura recomendada

```text
.
├── app.py
├── drive_ingestor.py
├── extractor.py
├── kpi_builder.py
├── subcategorias.json
├── nominas_app/
│   ├── services/
│   │   ├── config_loader.py
│   │   └── dashboard_data.py
│   └── ui/
│       ├── cards.py
│       ├── charts.py
│       ├── formatting.py
│       ├── quality.py
│       ├── style.py
│       └── tables.py
└── tests/
    ├── test_app_smoke.py
    ├── test_dashboard_services.py
    ├── test_drive_ingestor.py
    ├── test_extractor_core.py
    └── test_kpi_builder.py
```

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
3. Descarga el JSON de credenciales y guárdalo como `credentials.json`.
4. Comparte:
   - la carpeta de Drive origen
   con el email del Service Account (Editor).
5. Crea proyecto y tablas en Supabase (`nominas`, `control`) ejecutando `supabase/schema.sql` y copia URL/Service Role Key.
6. Crea `config.json`:

```json
{
  "credentials_path": "credentials.json",
  "drive_folder_id": "ID_CARPETA_DRIVE",
  "supabase_url": "https://<project>.supabase.co",
  "supabase_service_role_key": "<service_role_key>",
  "supabase_schema": "public"
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

## 4) Qué escribe en Supabase

- Tabla `nominas`:
  - Año, Mes, Concepto, Importe, Categoría, Subcategoría, file_id, file_name
- Tabla `control`:
  - file_id, file_name, md5_drive, source_folder_breadcrumb, renamed_to, target_folder_breadcrumb, rules_version, processed_at_utc, status, error

`control` evita reprocesar el mismo archivo por `file_id` y también por `md5_drive` (deduplicación lógica por contenido).
La ingesta también acota la búsqueda por `modifiedTime` (con margen de seguridad) usando la última ejecución registrada en `control`.

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
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_SCHEMA` (opcional, por defecto `public`)
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

- `DRIVE_FOLDER_ID`: ID de la carpeta de Drive con las nóminas
- `SUPABASE_URL`: URL del proyecto Supabase
- `SUPABASE_SERVICE_ROLE_KEY`: Service Role Key de Supabase

### Ejecución

- Manual: Actions -> `Ingesta Nominas Drive to Supabase` -> Run workflow
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
- preparación de vistas/alertas del dashboard (servicios de datos)
- smoke test de compilación de `app.py`

## 11) Checklist visual rápida (UI)

Tras cualquier cambio de `app.py`, revisar en 2-3 minutos:

- Filtros en una fila: `Año`, `Mes`, `Comparación` visibles y funcionales.
- KPIs mensuales: 2 filas x 5 tarjetas, alineadas y sin solapes.
- KPIs anuales: tarjetas centradas/alineadas; bloque `Jubilación` y bloque `ESPP y RSU` dentro de su tarjeta.
- Gráficas de comparativa/evolución en la misma fila (anual y mensual).
- Tabla `Información mensual explicada`: zebra rows y empieza en índice visual 1.
- Tabla `Desglose mensual`: orden cronológico de columnas, zebra rows y filtros (texto, cambios, ceros) operativos.
- `Modo privacidad`: oculta importes en KPIs, tablas y gráficas.
- Estados vacíos: mensajes claros en `ESPP/RSU` y `Desglose mensual`.
- Responsive básico: en ancho reducido, columnas hacen wrap sin romper métricas.
