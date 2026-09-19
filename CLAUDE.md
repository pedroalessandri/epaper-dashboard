# CLAUDE.md — contexto del proyecto epaper-dashboard

Este archivo es el contexto permanente del repo. Leelo antes de cualquier tarea.

## Qué es

Dashboard en una pantalla e-paper de 7,5" colgada de una Raspberry Pi Zero 2 W.
Muestra hora, clima y (más adelante) otros módulos. Se configura desde un panel
web local.

## Hardware (verificado y funcionando)

| Componente | Detalle |
|---|---|
| Placa | Raspberry Pi Zero 2 W (ARMv8 64-bit, 512 MB RAM, 4 núcleos) |
| Pantalla | Waveshare 7.5" e-Paper **V2**, blanco y negro, 800×480 |
| Driver | Waveshare e-Paper Driver HAT **rev 2.3** |
| Switches del HAT | Display Config = **B** (0,47R), Interface Config = **0** (SPI 4 hilos) |
| Conexión | HAT montado sobre header 2×20 soldado a mano (pines 1–28 poblados) |
| Módulo Python | `epd7in5_V2` de la librería oficial de Waveshare |

El header está soldado solo en las primeras 14 columnas. El HAT usa hasta el
pin 24, así que alcanza, pero **no asumir disponibilidad de GPIO más allá del
pin 28**.

### Pines en uso por el HAT (no reasignar)

| Señal | GPIO | Pin físico |
|---|---|---|
| VCC | — | 1 (3.3V) |
| GND | — | 6 |
| RST | 17 | 11 |
| PWR | 18 | 12 |
| BUSY | 24 | 18 |
| DIN (MOSI) | 10 | 19 |
| DC | 25 | 22 |
| CLK (SCLK) | 11 | 23 |
| CS (CE0) | 8 | 24 |

## Entorno (estado actual)

- **SO**: Raspberry Pi OS Lite 64-bit, imagen pi-gen `2026-09-15` (stage2),
  provisionada con **cloud-init** (`user-data` / `network-config` en `bootfs`).
  Ojo: el mecanismo viejo `custom.toml` ya no aplica en esta versión.
- **Hostname**: `epaper` · **Usuario**: `palessandri` · sudo sin contraseña
- **Acceso**: SSH por clave/contraseña. `epaper.local` resuelve vía avahi.
- **Red**: Wi-Fi 2,4 GHz únicamente (la Zero 2 no tiene radio de 5 GHz).
  Conexión NetworkManager: `netplan-wlan0-true24`, con `powersave 2` (apagado).
- **SPI**: habilitado (`dtparam=spi=on` en `config.txt` + módulo `rpi:` de
  cloud-init). Verificar con `ls /dev/spidev*` → `spidev0.0`, `spidev0.1`.
- **USB gadget**: `dtoverlay=dwc2` + `modules-load=dwc2,g_ether` habilitados
  como vía de acceso de emergencia si el Wi-Fi falla.
- **Librería Waveshare**: clonada en `~/e-Paper` (repo `waveshareteam/e-Paper`).
  Los ejemplos viven en `RaspberryPi_JetsonNano/python/examples`.
- **Paquetes apt ya instalados**: `python3-pil`, `python3-numpy`,
  `python3-spidev`, `python3-gpiozero`, `git`, `avahi-daemon`.

## Reglas del panel e-paper (no negociables)

1. **Siempre cerrar con `epd.sleep()`.** Dejar el panel energizado lo degrada.
   Todo camino de salida, incluidas las excepciones, tiene que pasar por ahí.
2. **Nunca refrescar en loop rápido.** El refresco completo tarda ~4 s y
   parpadea. Cadencia mínima razonable: varios minutos.
3. **Refresco completo periódico.** Si se usa refresco parcial, hay que hacer
   uno completo cada tanto (al menos 1 vez por día) para evitar ghosting.
4. **Imagen en modo `1`** (1 bit por píxel), 800×480, fondo 255 (blanco),
   tinta 0 (negro). No hay grises ni antialiasing útil: el texto chico con
   antialiasing queda sucio.

## Restricciones de la plataforma

- 512 MB de RAM y CPU modesta: evitar dependencias pesadas. **No** usar
  navegadores headless, Chromium, Playwright ni renderizado HTML→imagen en la
  Pi. Componer con Pillow directamente.
- El `apt install` y el `pip install` tardan minutos. No iterar sobre eso.
- Red inestable por Wi-Fi: todo acceso a internet tiene que tolerar fallos y
  timeouts sin dejar la pantalla en blanco ni colgar el proceso.

## Convenciones de desarrollo

- **Modo mock obligatorio.** El código corre en la notebook sin hardware:
  `EPAPER_BACKEND=mock` escribe `out/preview.png` en vez de mandar al panel.
  Toda la lógica de render se desarrolla y verifica así.
- **Python 3 del sistema con venv `--system-site-packages`**, para reutilizar
  `python3-pil`, `python3-numpy` y `python3-spidev` de apt en vez de compilarlos.
- **Nada de secretos en el repo.** Config real en `config.yaml` (gitignored),
  plantilla versionada en `config.example.yaml`.
- Logs a stdout; systemd se encarga del journal.

## Cómo correr esto

Layout `src/`: el paquete es `epaper` y vive en `src/epaper/`. Se instala en
modo editable (`pip install -e .`), o se corre con `PYTHONPATH=src`.

```bash
# desarrollo (notebook, sin hardware) -> out/preview.png
EPAPER_BACKEND=mock python3 -m epaper.main

# en la Pi, contra el panel real
EPAPER_BACKEND=waveshare python3 -m epaper.main

# limpiar la pantalla
python3 -m epaper.main --clear
```

**Toda iteración de diseño se hace en modo mock y se verifica mirando el PNG.**
No desplegar a la Pi para ver cómo quedó algo: el refresco tarda ~4 s y el ciclo
es mucho más lento.

## Verificaciones canónicas

```bash
# render (cualquier máquina)
EPAPER_BACKEND=mock python3 -m epaper.main && ls -l out/preview.png
# hardware
ls /dev/spidev*                    # spidev0.0 y spidev0.1
# red
iw dev wlan0 link                  # asociado; signal peor que -70 dBm = señal floja
iw dev wlan0 get power_save        # off
# servicio
systemctl status epaper.timer
journalctl -u epaper.service -n 30 --no-pager
```

## Prueba de humo del panel

```bash
python3 -c "
import sys; sys.path.append('$HOME/e-Paper/RaspberryPi_JetsonNano/python/lib')
from waveshare_epd import epd7in5_V2
e = epd7in5_V2.EPD(); e.init(); e.Clear(); e.sleep()
print('ok')
"
```

Esperado: la pantalla parpadea y queda blanco uniforme; imprime `ok`.

### Diagnóstico si falla

| Síntoma | Sospechoso |
|---|---|
| Se cuelga sin devolver el prompt | BUSY (pin 18) |
| Imprime `ok` pero la pantalla no reacciona | alimentación (1 y 6), RST (11), flex |
| Parpadea pero queda con rayas o manchas | DIN (19), CLK (23), flex mal insertado |
| Error de Python sobre spidev o GPIO | software: revisar SPI y grupos del usuario |
