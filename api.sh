#!/bin/sh

uvicorn app:app --reload --host 0.0.0.0 --port 80 --port 443 --ssl-keyfile /opt/certs/${HOSTNAME}+5-key.pem --ssl-certfile /opt/certs/${HOSTNAME}+5.pem
