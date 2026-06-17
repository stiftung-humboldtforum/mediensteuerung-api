#!/bin/sh

# No --reload in production (a bind-mount write would drop all WS/MQTT clients).
# Single --port 443 (uvicorn honours only one --port; 80 was silently dropped).
# Cert is referenced by a stable name symlinked by mkcert.sh (decoupled from the
# SAN-count-derived ${HOSTNAME}+N filename).
uvicorn app:app --host 0.0.0.0 --port 443 --ssl-keyfile /opt/certs/api-key.pem --ssl-certfile /opt/certs/api.pem
