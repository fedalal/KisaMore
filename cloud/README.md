# KisaMore Cloud API

The central service receives outbound snapshots from the Raspberry Pi and exposes a separate
read-only endpoint for the public website. It does not contain light, watering, configuration,
or shutdown commands.

## Data flow

1. The Pi reads its existing SQLite state and latest saved sensor samples.
2. Every 30 seconds it sends an HTTPS request authenticated by a device ID and a random token.
3. The API stores current rack state and telemetry history in PostgreSQL.
4. The public site reads only `/api/v1/public/farms/{slug}/live`.

Video uses a separate media path: each camera is opened once by the Raspberry Pi application,
encoded to H.264 by FFmpeg and published over encrypted RTSPS to MediaMTX on the VPS. MediaMTX creates HLS for public
viewers, so adding viewers does not add outgoing connections from the Raspberry Pi.

The Raspberry Pi does not accept incoming internet connections.

## VPS start with Docker Compose

```bash
cp cloud/.env.example cloud/.env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Generate two different values. Put them in KISAMORE_BOOTSTRAP_DEVICE_TOKEN and
# KISAMORE_MEDIA_PUBLISH_PASSWORD.
# Set KISAMORE_TLS_CERT_PATH and KISAMORE_TLS_KEY_PATH to the current
# Let's Encrypt certificate and private key on this VPS.

docker compose --env-file cloud/.env -f docker-compose.cloud.yml up -d --build
curl http://127.0.0.1:8080/api/v1/health
```

Publish `127.0.0.1:8080` through Nginx at an HTTPS hostname such as `api.kisamore.com`.
Do not expose PostgreSQL to the internet.

Proxy MediaMTX HLS through the same HTTPS virtual host. When the public API is already proxied
from `/` to `127.0.0.1:8080`, add this more specific location before it:

```nginx
location /hls/ {
    proxy_pass http://127.0.0.1:8888/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 60s;
}
```

Reload Nginx after checking its configuration:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Let's Encrypt certificates issued directly for an IP address are short-lived (160 hours).
Run the Certbot renewal scheduler at least daily and verify it with `certbot renew --dry-run`.
Install a Certbot deploy hook that reloads Nginx and runs
`docker compose --env-file /path/to/KisaMore/cloud/.env -f /path/to/KisaMore/docker-compose.cloud.yml restart media`.
Restarting MediaMTX after renewal is required so new RTSPS connections receive the renewed
certificate instead of the certificate loaded when the container started.

MediaMTX publishes HLS only on `127.0.0.1:8888`. TCP port `8322` accepts the encrypted RTSPS
publisher and must be allowed by the VPS firewall. If the Pi has a fixed public IP, restrict the
port to that address. MediaMTX reads the same valid TLS certificate used by the VPS. The publisher
account can publish but cannot administer the media server; anonymous users can only read the
public farm streams.

## Raspberry Pi configuration

Install the updated dependencies, then add these variables to the `kisamore.service` systemd
unit (preferably via an `EnvironmentFile` readable only by root):

```dotenv
KISAMORE_CLOUD_URL=https://api.kisamore.com
KISAMORE_DEVICE_ID=greenhouse-pi-01
KISAMORE_DEVICE_TOKEN=the-same-random-token-used-on-the-vps
KISAMORE_CLOUD_INTERVAL_SECONDS=30
KISAMORE_CLOUD_TIMEOUT_SECONDS=10
KISAMORE_SOFTWARE_VERSION=d7caafd-cloud-sync

# Live video. The hostname is the public VPS hostname; do not add a rack path.
KISAMORE_MEDIA_ENABLED=true
KISAMORE_MEDIA_PUBLISH_URL=rtsps://api.kisamore.com:8322
KISAMORE_MEDIA_PUBLISH_USER=kisamore-edge
KISAMORE_MEDIA_PUBLISH_PASSWORD=the-same-media-password-used-on-the-vps
KISAMORE_MEDIA_FARM_SLUG=demo-farm
KISAMORE_MEDIA_VIDEO_CODEC=auto
```

Install FFmpeg on the Raspberry Pi if it is not present:

```bash
sudo apt update
sudo apt install -y ffmpeg v4l-utils
```

Then run:

```bash
source kisamoreevn/bin/activate
pip install -r requirements.txt
sudo systemctl daemon-reload
sudo systemctl restart kisamore.service
journalctl -u kisamore.service -f
```

Expected log line:

```text
[cloud-sync] snapshot sent: racks=4
[camera-live] started: streams=4, resolution=1024x768, fps=8
```

Without the three required cloud variables, synchronization stays disabled and the existing
local controller continues to operate normally.

Without `KISAMORE_MEDIA_PUBLISH_URL`, video publishing is disabled independently; lighting,
watering, sensor sync and local camera pages continue to work.

## Camera modes

- Live video: `1024x768`, 8 FPS, 1200 kbit/s for each rack by default.
- Viewer delivery: HLS; the dashboard loads only the camera selected with **Смотреть**.
- Archive photo: the Pi asks `v4l2-ctl` for the largest MJPG mode and takes the photo
  sequentially. For the current webcams this is expected to be `3840x2160`.
- During a full-resolution photo, the selected stream can pause briefly and resumes
  automatically. The webcam is never opened concurrently by OpenCV and FFmpeg.
- Perspective points saved on an older `1280x720` preview are scaled automatically to both
  live and archive resolutions. New points are saved with their actual reference size.

## API

- `GET /` — public live dashboard for the configured farm.
- `GET /api/v1/health` — service/database health.
- `POST /api/v1/edge/snapshot` — authenticated device ingestion.
- `GET /api/v1/public/farms/demo-farm/live` — public read-only state.
- `GET /api/docs` — OpenAPI UI.

The bootstrap token is hashed before it is stored. Once a device exists, changing only the
bootstrap token environment variable does not rotate its credentials.
