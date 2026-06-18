import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from beanie import init_beanie
from bson import ObjectId
from fastapi import FastAPI, Response, Depends, Header, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mqtt import mqtt
from routes import base, config, calendar, knx
from routes.knx import save_event

from db import User, db
from schemas import UserCreate, UserRead, UserUpdate
import users
from users import auth_backend, current_active_admin, fastapi_users, bearer_transport

from misc import authenticate_token, logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # fastapi 0.137 + fastapi-mqtt 2.x: use lifespan instead of @on_event /
    # mqtt.init_app. Handlers (on_connect in mqtt.py, on_message below) are
    # registered at import time, before this runs.
    # DB first (independent of MQTT) so /healthcheck + auth come up even when the
    # broker is briefly unreachable. The initial MQTT connect has no timeout in
    # gmqtt, so it's best-effort + time-bounded here — a boot-time broker outage
    # must not wedge startup; gmqtt reconnects in the background.
    await init_beanie(
        database=db,
        document_models=[
            User,
        ],
    )
    try:
        await asyncio.wait_for(mqtt.mqtt_startup(), timeout=10)
    except Exception as e:
        logger.error(
            'MQTT broker unavailable at startup (%s); continuing, gmqtt will retry', e)
    # Start the NetBox DataLoader bound to the RUNNING server loop. Must be done
    # here (not at import): uvicorn 0.47+ eagerly imports the app before the loop
    # exists, so an import-time get_event_loop() would bind a dead loop and the
    # data-refresh broadcast/MQTT publish would silently never fire.
    base.start_dataloader(asyncio.get_running_loop())
    yield
    base.stop_dataloader()
    with suppress(Exception):
        await mqtt.mqtt_shutdown()


app = FastAPI(lifespan=lifespan)
app.add_middleware(HTTPSRedirectMiddleware)
# Restrict CORS via CORS_ALLOW_ORIGINS (comma-separated) when credentials are
# used; defaults to '*' for backward compatibility. Wildcard + credentials is
# spec-invalid, so set an explicit origin allowlist in production.
_cors = (os.getenv('CORS_ALLOW_ORIGINS') or '*').strip()
_allow_origins = ['*'] if _cors == '*' else [o.strip() for o in _cors.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)


@mqtt.on_message()
async def on_message(client, topic, payload, qos, properties):
    try:
        payload = payload.decode()
        payload = json.loads(payload)
    except:
        print(f'Error: Invalid MQTT Payload. "{payload}"')
        return
    if mqtt.match(topic, 'manager/device_event'):
        payload['target'] = 'device'
    elif mqtt.match(topic, 'manager/tag_event'):
        payload['target'] = 'tag'
    elif mqtt.match(topic, 'manager/location_event'):
        payload['target'] = 'location'
    elif mqtt.match(topic, 'knx/switch/#'):
        location_id = int(topic.split('/')[2])
        object_id = str(ObjectId())
        payload = {
            'id': object_id,
            'target': 'knx',
            'data': {
                'event': {
                    **payload,
                    'type': 'knx_state',
                    'target': location_id,
                    'id': object_id
                }
            }
        }
        await save_event({
            **payload,
            'target': location_id
        })
    await base.manager.broadcast(json.dumps(payload))


app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=['auth']
)


@app.post('/data-refresh')
async def data_refresh():
    await base.data_refresh()


@app.get('/healthcheck')
def healthcheck():
    return 'ok'


@app.post('/auth/jwt/refresh', tags=['auth'])
async def refresh_jwt(response: Response,
                      authorization: Annotated[str, Header()] = "",
                      jwt_strategy: users.JWTStrategy = Depends(
                          users.get_jwt_strategy),
                      user=Depends(fastapi_users.current_user(active=True))):
    token = authorization.split(" ")[1]
    valid_token = await authenticate_token(token)
    if not valid_token:
        raise HTTPException(status_code=401, detail='Invalid token')
    token = await jwt_strategy.write_token(user)
    return await bearer_transport.get_login_response(token)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix='/auth',
    tags=['auth'],
    dependencies=[Depends(current_active_admin)]
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix='/auth',
    tags=['auth'],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix='/auth',
    tags=['auth'],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix='/users',
    tags=['users'],
)


app.include_router(users.router, tags=['users'])

app.include_router(config.router, prefix='/config', tags=['config'])

app.include_router(calendar.router, prefix='/api', tags=['api'])

app.include_router(knx.router, prefix='/api', tags=['api'])

app.include_router(base.router, prefix='/api', tags=['api'])


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as ex:
            if ex.status_code == 404:
                return await super().get_response('index.html', scope)
            else:
                raise ex


app.mount('/', SPAStaticFiles(directory='static', html=True), name='app')
