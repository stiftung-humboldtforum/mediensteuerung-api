FROM python:3.11-slim
RUN apt-get update && apt-get -qq install curl git
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade \
	fastapi==0.137.1 \
	fastapi-mqtt==2.2.0 \
	fastapi-users[beanie]==15.0.5 \
	beanie==2.1.0 \
	websockets==11.0.3 \
	wsproto==1.2.0 \
	pydantic==2.13.4 \
	uvicorn==0.22.0 \
	python-dateutil==2.9.0.post0 \
	PyYAML==6.0.2 \
	pynetbox==7.4.1
WORKDIR /api
