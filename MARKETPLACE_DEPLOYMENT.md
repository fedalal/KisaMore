# KisaMore marketplace update

Branch: `feature/marketplace-core`

The update only adds tables. Existing relay state, schedules, sensor history, and camera settings
are not deleted. Nevertheless, back up both databases before the first start.

## Raspberry Pi

```bash
cd /home/admin/KisaMore
git status --short --branch
```

Stop if tracked files are modified and review them before switching branches. If the worktree is
clean:

```bash
mkdir -p /home/admin/kisamore-backups
cp -a kisamore.db "/home/admin/kisamore-backups/kisamore-$(date +%Y%m%d-%H%M%S).db"

git fetch origin
git switch --track origin/feature/marketplace-core

source kisamoreevn/bin/activate
pip install -r requirements.txt

sudo systemctl restart kisamore.service
sudo systemctl is-active kisamore.service
sudo journalctl -u kisamore.service -n 100 --no-pager
```

The application startup creates `plants`, `rack_slots`, and `plantings`, then creates six slots
for every configured rack. Verify:

```bash
curl -fsS http://127.0.0.1:8000/api/growing/slots | python -m json.tool
```

Open `http://<raspberry-pi-ip>:8000/growing`, add plants, and assign the current plantings.

## VPS

The commands below assume the repository is `/home/alex/projects/KisaMore`. Use the actual path
if it differs.

```bash
cd /home/alex/projects/KisaMore
git status --short --branch
```

Stop if tracked files are modified. Back up PostgreSQL before rebuilding:

```bash
mkdir -p "$HOME/kisamore-backups"
sudo docker compose --env-file cloud/.env -f docker-compose.cloud.yml \
  exec -T postgres pg_dump -U kisamore -d kisamore \
  > "$HOME/kisamore-backups/kisamore-$(date +%Y%m%d-%H%M%S).sql"
```

If `POSTGRES_USER` or `POSTGRES_DB` in `cloud/.env` differ from `kisamore`, substitute their real
values in the backup command.

Update and rebuild:

```bash
git fetch origin
git switch --track origin/feature/marketplace-core

grep -q '^KISAMORE_SESSION_DAYS=' cloud/.env || echo 'KISAMORE_SESSION_DAYS=30' >> cloud/.env
grep -q '^KISAMORE_COOKIE_SECURE=' cloud/.env || echo 'KISAMORE_COOKIE_SECURE=true' >> cloud/.env
grep -q '^KISAMORE_OFFER_HOURS=' cloud/.env || echo 'KISAMORE_OFFER_HOURS=24' >> cloud/.env
grep -q '^KISAMORE_PHOTO_DIR=' cloud/.env || echo 'KISAMORE_PHOTO_DIR=/srv/kisamore/data/photos' >> cloud/.env
grep -q '^KISAMORE_PHOTO_MAX_BYTES=' cloud/.env || echo 'KISAMORE_PHOTO_MAX_BYTES=2097152' >> cloud/.env

sudo docker compose --env-file cloud/.env -f docker-compose.cloud.yml up -d --build
sudo docker compose --env-file cloud/.env -f docker-compose.cloud.yml ps
sudo docker compose --env-file cloud/.env -f docker-compose.cloud.yml logs --tail=100 api
curl -fsS http://127.0.0.1:8080/api/v1/health
```

The API startup creates the new PostgreSQL tables. Nginx configuration does not change because
the website and API continue to use the existing root and `/api` routes.

## End-to-end verification

After both systems have run for at least one synchronization interval (normally 30 seconds):

```bash
curl -fsS https://YOUR-VPS-HOST/api/v1/public/farms/demo-farm/market | python -m json.tool
```

The response should contain `plants`, racks, six `slots` per rack, and `photo_url` after the first
successful camera capture. The public website should
open in English by default and offer English, Russian, German, French, Spanish, Italian,
Portuguese, Polish, and Chinese.

## Current checkout boundary

The marketplace workflow is operational, but no money is charged. A purchase creates an order
with `test_paid` status. Real payments and outbound email/Telegram messages require the payment
provider and messaging credentials to be selected and configured separately. Offers and other
messages are already saved as in-app notifications.
