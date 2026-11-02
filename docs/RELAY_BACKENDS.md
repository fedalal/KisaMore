# KisaMore relay backend (per Raspberry Pi)

Every KisaMore device runs the same Python application and service named kisamore.service.
The physical relay bus is selected locally in /etc/kisamore/config.yaml
or in the equipment settings modal (Настройки оборудования).

## GPIO — Waveshare Relay Board (B), eight channels

relay_backend: gpio, with gpio_relays.channels mapping each relay number to
a BCM GPIO number. Default: 1→5, 2→6, 3→13, 4→16, 5→19, 6→20, 7→21, 8→26.
Use gpio_relays.active_low: true for this board. Never connect an
unverified board or mains load during software testing. GPIO channels are 1–8.

## RS485 — Modbus RTU relay board, 16 channels

relay_backend: rs485. Specify rs485.port, baudrate, slave_id and other
serial settings. Channel range is 1–16. An actual serial adapter must be
connected to switch from GPIO. Legacy configs without relay_backend
default to RS485.

## Behavior

- GET/POST /api/config exposes and saves the active backend, GPIO channel
  map, and RS485 settings.
- Switching backend requires UI confirmation; switching to RS485 is rejected
  if the serial port does not exist.
- Saving without a physical wiring change reuses the live GPIO driver to
  avoid GPIOPinInUse and unnecessary relay toggling.
- Rack assignments and channel ranges are validated server-side.
- Secrets and device-specific data must never be committed to GitHub:
  config: /etc/kisamore/config.yaml;
  environment: /etc/kisamore/environment;
  database: /var/lib/kisamore/kisamore.db.
- On microSD 16 GB, disable local photo archives; keep full images on VPS.

The service template in deploy/kisamore.service uses user fedalal for
greenhouse #2; adapt User and Group for other installations.
