# PLAN.md — epaper-dashboard

Plan de construcción por micro-runs. Cada fase es una sesión acotada de Claude
Code de 20–30 minutos, con 1–2 artefactos y una verificación concreta. Si algo
falla dos veces, se corta la fase y se replantea.

## Alcance de la v1

La primera versión usable muestra tres cosas:

1. **Hora y fecha.**
2. **Clima**: el día corriente con detalle (mañana / tarde / noche, con
   temperatura, sensación, probabilidad de lluvia y condición), y los tres días
   siguientes en versión resumida (máxima, mínima, condición).
3. **Lista de tareas**: pendientes del día, editables desde el panel web.

### Layout propuesto (800 × 480)

```
┌──────────────────────────┬───────────────────────────────────┐
│  14:35                   │  HOY                              │
│  viernes 18 de septiembre│  mañana   12°  ☁  10% lluvia      │
│                          │  tarde    19°  ☀   0%             │
│  ────────────────────────│  noche    14°  ☁  20%             │
│                          ├───────────────────────────────────┤
│  TAREAS                  │  sáb 21/13  ☀   dom 19/12  ☂      │
│  ▢ ...                   │  lun 23/14  ☁                     │
│  ▢ ...                   │                                   │
├──────────────────────────┴───────────────────────────────────┤
│  actualizado 14:35                                           │
└──────────────────────────────────────────────────────────────┘
```

Proporciones tentativas: columna izquierda ~45%, derecha ~55%; franja inferior
de 24 px. Se ajusta en la fase 1 mirando el PNG, no antes.

**Dos cosas a confirmar al empezar la fase 1**: si "tres días" significa hoy +
3 siguientes (lo asumido acá) o 3 en total; y si la franja de tareas necesita
más alto que el bloque de clima extendido.

### Origen de las tareas

Para la v1, **tareas locales**: se guardan en `tasks.json` y se administran
desde el panel web (agregar, marcar hecha, borrar). Sin dependencias externas
ni OAuth, así la v1 se termina rápido.

La interfaz `TaskSource` queda definida desde el principio con un solo método
(`get_tasks() -> list[Task]`), para que después se puedan enchufar otras
fuentes sin tocar el tile: un endpoint de n8n, Google Tasks, Todoist o lo que
use el homelab. Esa decisión se pospone a la fase 4 a propósito.

## Decisiones de arquitectura

**Render en la Pi, con Pillow.** Componer una imagen 1-bit de 800×480 le sobra
a la Zero 2. Descartado renderizar HTML con navegador headless: no entra en
512 MB y agrega una dependencia enorme.

**Capa de salida abstraída.** `display.py` expone `show(image)` y tiene dos
backends: `waveshare` (hardware real) y `mock` (escribe `out/preview.png`).
Esto permite desarrollar en la notebook sin hardware y deja la puerta abierta
a mover el render al homelab más adelante sin tocar el resto.

**Config en archivo, panel web encima.** La fuente de verdad es `config.yaml`.
El panel web lo lee y lo escribe; no tiene base de datos. Si el panel se cae,
el dashboard sigue andando.

**Actualización por `git pull` + systemd.** Sin CI ni runners. Un script
`deploy.sh` que hace pull en la Pi y reinicia el servicio. Suficiente para un
proyecto de una sola máquina.

**Cadencia.** Timer de systemd cada 5 minutos (Waveshare recomienda ≥180 s
entre refrescos). Refresco completo siempre en la fase 1; refresco parcial
recién en la fase 5, si hace falta.

## Estructura del repo

```
epaper-dashboard/
├── CLAUDE.md                 # contexto de hardware y entorno
├── PLAN.md                   # este archivo
├── README.md
├── .gitignore                # config.yaml, out/, .venv/, __pycache__
├── requirements.txt
├── config.example.yaml
├── src/epaper/
│   ├── __init__.py
│   ├── config.py             # carga y valida config.yaml
│   ├── display.py            # backends waveshare | mock
│   ├── render.py             # compone la imagen a partir de los tiles
│   ├── main.py               # entrypoint: leer config → render → mostrar
│   ├── tiles/
│   │   ├── base.py           # interfaz Tile: render(draw, box, ctx)
│   │   ├── clock.py
│   │   └── weather.py
│   ├── sources/
│   │   └── openmeteo.py      # cliente HTTP con timeout y caché en disco
│   └── web/
│       ├── app.py            # FastAPI: GET/POST config, preview, refrescar
│       └── templates/
├── systemd/
│   ├── epaper.service
│   ├── epaper.timer
│   └── epaper-web.service
├── scripts/
│   ├── setup-pi.sh           # venv + deps + enable units (idempotente)
│   └── deploy.sh             # pull + restart desde la notebook
└── out/                      # preview.png (gitignored)
```

---

## Fase 0 — Repo y esqueleto con modo mock

**Objetivo**: repo en GitHub, corriendo en la notebook, generando un PNG.
Todavía sin tocar la Pi.

**Artefactos**: estructura del repo + `display.py` con los dos backends.

1. Crear el repo `epaper-dashboard` en GitHub (privado o público, da igual) y
   clonarlo en la notebook.
2. Copiar `CLAUDE.md` y `PLAN.md` a la raíz. Commit inicial.
3. Crear la estructura de directorios y el `.gitignore`.
4. Implementar `display.py`:
   - `get_display()` lee `EPAPER_BACKEND` (`waveshare` | `mock`, default `mock`).
   - Backend `mock`: guarda la imagen en `out/preview.png`, imprime la ruta.
   - Backend `waveshare`: importa `epd7in5_V2`, hace `init()`, `display()`,
     y **siempre** `sleep()` en un `finally`.
   - Ambos exponen `WIDTH = 800`, `HEIGHT = 480`.
5. `main.py` mínimo: genera una imagen blanca con la fecha y hora en grande y
   la manda al display.

**Verificación**:
```bash
EPAPER_BACKEND=mock python3 -m epaper.main
```
Esperado: se crea `out/preview.png` de 800×480 con la hora legible.

**Criterio de corte**: si el import de Pillow o la estructura de paquetes da
problemas dos veces, simplificar a un solo archivo y seguir.

---

## Fase 1a — Datos del clima

**Objetivo**: tener los datos que el layout necesita, sin dibujar todavía.

**Artefactos**: `sources/openmeteo.py` + su caché.

1. Cliente de Open-Meteo: API gratuita, sin key. Una sola llamada pidiendo
   `hourly` (temperatura, sensación térmica, probabilidad de precipitación,
   weather code) y `daily` (máxima, mínima, weather code), con `timezone`
   correcto y `forecast_days=4`.
2. **Agregación por franjas** del día corriente: mañana 06–12, tarde 12–18,
   noche 18–24. Para cada franja: temperatura representativa (promedio o
   máxima, decidir mirando el resultado), probabilidad de lluvia máxima y el
   weather code dominante.
3. Los tres días siguientes se toman directo de `daily`: máxima, mínima y
   código.
4. `timeout=10` y manejo de excepciones que devuelva el último dato cacheado
   en vez de explotar.
5. Caché en disco (`out/cache.json`) con marca de tiempo, para que un fallo de
   red muestre datos viejos etiquetados en vez de una pantalla rota.
6. Mapeo de weather code WMO a una etiqueta corta en castellano y a un
   identificador de ícono.

**Verificación**: un script que imprime la estructura ya agregada. Contrastar
las franjas contra el pronóstico de cualquier app para el mismo día.

**Criterio de corte**: si la agregación por franjas se complica, entregar la
fase con temperatura actual + máxima/mínima y volver después.

---

## Fase 1b — Layout y tiles

**Objetivo**: el diseño de la v1 completo, verificado en mock.

**Artefactos**: `render.py` con el sistema de layout + los tiles.

1. Interfaz `Tile`: cada tile recibe un `ImageDraw` y un rectángulo, y dibuja
   dentro de ese rectángulo. Nada de coordenadas absolutas desparramadas.
2. El layout se define en un solo lugar, como un diccionario de rectángulos.
   Cambiar proporciones tiene que ser una línea.
3. Tiles: `clock` (hora grande + fecha), `weather_today` (tres franjas),
   `weather_forecast` (tres días resumidos), `tasks` (lista con checkbox
   vacío), `footer` (hora de actualización).
4. **Íconos de clima**: dibujados con primitivas de Pillow (círculo, arcos,
   líneas) o como PNG 1-bit pequeños en `assets/`. Nada de fuentes de íconos
   con antialiasing, que en 1 bit quedan sucios.
5. **Manejo de desborde en tareas**: definir cuántas entran (probablemente 5 o
   6) y qué pasa con el resto: truncar el texto largo con `…` y mostrar un
   "+N más" al pie del bloque.
6. Tipografía DejaVu del sistema. Sin antialiasing útil en 1 bit: no bajar de
   ~16 px, y probar bold para los títulos de sección.

**Verificación**: `out/preview.png` con datos reales de Buenos Aires, tareas de
prueba de largos variados (una corta, una muy larga, lista vacía, lista con
diez ítems), legible a un metro.

**Criterio de corte**: si un tile no cierra visualmente en dos intentos, dejarlo
con una versión simple y anotar el ajuste en el backlog.

---

## Fase 2 — Puesta en la Pi y servicio

**Objetivo**: el dashboard se actualiza solo cada 5 minutos.

**Artefactos**: `scripts/setup-pi.sh` + units de systemd.

1. `setup-pi.sh` idempotente: crea el venv con `--system-site-packages`,
   instala `requirements.txt`, instala la librería de Waveshare (copiar
   `waveshare_epd` al venv o agregarla al path; **no** depender de rutas
   relativas al repo clonado en `~/e-Paper`).
2. `epaper.service`: tipo `oneshot`, usuario `palessandri`, `WorkingDirectory`
   del repo, `Environment=EPAPER_BACKEND=waveshare`.
3. `epaper.timer`: `OnCalendar=*:0/5`, `Persistent=true`.
4. `deploy.sh`: desde la notebook, `ssh epaper.local` → `git pull` →
   `systemctl restart epaper.service` → mostrar las últimas líneas del journal.
5. Primer despliegue manual y verificación en pantalla real.

**Verificación**:
```bash
systemctl list-timers epaper.timer
journalctl -u epaper.service -n 20 --no-pager
```
Esperado: el timer con próxima ejecución agendada, el servicio en `success`,
y la pantalla mostrando la hora correcta.

**Criterio de corte**: si el servicio falla por permisos de SPI o GPIO, agregar
el usuario a los grupos `spi` y `gpio` y reintentar una sola vez.

---

## Fase 3 — Configuración y panel web

**Objetivo**: cambiar ciudad, cadencia y qué módulos se muestran sin SSH.

**Artefactos**: `config.py` + `web/app.py`.

1. `config.example.yaml` con: ubicación (lat/lon), zona horaria, formato de
   hora, cadencia, lista de tiles activos y su posición.
2. `config.py`: carga, valida y aplica defaults. Si el archivo está roto, usar
   defaults y loguear el error, nunca abortar.
3. Panel FastAPI + Uvicorn en `0.0.0.0:8080`, sin autenticación (red local),
   con cuatro capacidades: ver la configuración actual, editarla y guardarla,
   **administrar las tareas** (agregar, marcar hecha, borrar, reordenar), y un
   botón "refrescar ahora" que dispara el render.
3b. La vista de tareas es la que más vas a usar desde el celular: que sea lo
   primero de la página, con un campo de texto y un botón, sin menús. Guardar
   una tarea debería disparar el refresco automáticamente.
4. Endpoint `/preview` que devuelve el último PNG renderizado, para ver el
   resultado desde el celular sin ir hasta la pantalla.
5. `epaper-web.service` como servicio permanente.

**Verificación**: entrar desde el celular a `http://epaper.local:8080`, cambiar
la ciudad, tocar refrescar, y ver el cambio reflejado en la pantalla física.

**Criterio de corte**: si FastAPI resulta pesado para la Zero 2, bajar a un
`http.server` con un formulario HTML plano. La funcionalidad importa más que
el framework.

**Estado (2026-09-24)**: hecho el panel de administración con la sección
Tareas (puntos 3 salvo config, 3b, 4 y 5). Tareas en `tasks.json`, sin
autenticación a propósito (son tareas de la casa). Cada cambio refresca la
pantalla respetando 180 s entre refrescos (`refresh.py`). Pendiente: editar la
configuración desde la web.

---

## Fase 3c — Modo mensaje

**Objetivo**: dejar un mensaje para la familia en la pantalla, en vez del
dashboard, y volver al dashboard cuando se quiera.

1. Nueva sección "Mensaje" en el panel web: textarea de texto plano, guardar,
   y un switch **dashboard / mensaje**.
2. Estado en un archivo local (texto + modo activo), escrito con fsync como
   `tasks.json`.
3. Render del modo mensaje: texto grande centrado dentro de un marco, con
   ajuste automático del tamaño de letra al largo del texto y corte de línea
   por palabras.
4. `main.py` elige qué renderizar según el modo; el timer sigue igual.

**Verificación**: escribir un mensaje desde el celular, activarlo, verlo en
la pantalla; volver al dashboard.

**Estado (2026-09-24)**: hecho. Estado en `message.json`. Marco doble, letra
bold que se ajusta de 112 a 24 px, sin palabras huérfanas. Un mensaje fijo no
se vuelve a refrescar (se compara la firma de la imagen), salvo una vez por
día para cuidar el panel.

---

## Fase 4 — Módulos adicionales

**Objetivo**: que el dashboard muestre algo que realmente mires todos los días.

Candidatos, en orden de valor esperado:

- **Tareas desde una fuente externa**: implementar un segundo `TaskSource`
  contra n8n, Google Tasks o lo que uses. El tile no se toca.
- **Agenda del día** (Google Calendar). Requiere OAuth; la vía más simple es
  generar el token en la notebook y copiar el refresh token a la Pi.
- **Estado del homelab**: servicios arriba/abajo, alertas pendientes.
- **Contenido arbitrario desde n8n**: un endpoint que devuelva JSON con texto
  libre, para empujar cualquier cosa a la pantalla sin tocar la Pi.

Una fase por módulo. Cada uno es un `Tile` nuevo más su `source`, sin tocar el
resto.

---

## Fase 5 — Robustez y cuidado del panel

**Objetivo**: que ande solo durante meses.

1. **Refresco completo diario** forzado, aunque se use parcial, para limpiar
   ghosting.
2. **Refresco parcial** para el reloj, si se quiere cadencia de minutos. Medir
   antes si vale la pena: el completo cada 5 minutos puede ser suficiente.
3. **Modo nocturno**: sin refrescos entre determinadas horas. Ahorra desgaste y
   evita el parpadeo en un dormitorio.
4. **Manejo de errores end-to-end**: que un fallo de red o de API deje la
   pantalla anterior intacta en vez de dibujar una vacía.
5. **Salida limpia**: `epd.sleep()` garantizado ante excepciones y señales.
6. **Watchdog opcional**: si el servicio falla N veces seguidas, reiniciar la
   Pi. Evaluar si hace falta o es sobreingeniería.

---

## Backlog para más adelante

- Marco o gabinete impreso en 3D para la pantalla.
- Alimentación con batería y despertar programado (la Zero 2 no tiene RTC;
  requiere hardware adicional o dejarla siempre encendida).
- Mover el render al homelab y que la Pi solo baje un PNG, si el proyecto
  crece y la Zero 2 queda corta.
- Varias pantallas con la misma base de código.
