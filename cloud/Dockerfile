FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/kisamore

COPY cloud/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && addgroup --system kisamore \
    && adduser --system --ingroup kisamore kisamore \
    && mkdir -p /srv/kisamore/data/photos \
    && chown -R kisamore:kisamore /srv/kisamore/data

COPY --chown=kisamore:kisamore cloud /srv/kisamore/cloud

USER kisamore

EXPOSE 8000

CMD ["uvicorn", "cloud.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
