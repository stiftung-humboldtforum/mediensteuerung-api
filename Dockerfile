FROM python:3.11-slim
RUN apt-get update && apt-get -qq install curl git
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade \
	fastapi==0.95.1 \
	fastapi-mqtt==1.0.7 \
	fastapi-users[beanie]==11.0.0 \
	websockets==11.0.3 \
	wsproto==1.2.0 \
	pydantic==1.10.7 \
	uvicorn==0.22.0 \
	python-dateutil==2.8.2 \
 	PyYAML==6.0.2 \
	bcrypt==4.0.1 \
    	pynetbox==7.4.1
WORKDIR /api
