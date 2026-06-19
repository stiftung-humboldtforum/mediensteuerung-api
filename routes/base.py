import asyncio
import json
from typing import Annotated
from enum import StrEnum

from fastapi import Depends, APIRouter, Body, WebSocket, Query, HTTPException
from mqtt import mqtt

from users import current_active_user, UserManager, get_user_manager, JWTStrategy, get_jwt_strategy
from connection_manager import ConnectionManager
from misc import logger
from misc.data import DataLoader

manager = ConnectionManager()

router = APIRouter(dependencies=[Depends(current_active_user)])

# The WebSocket route must NOT inherit the HTTP OAuth2 security dependency
# (current_active_user -> OAuth2PasswordBearer). On a WebSocket, fastapi 0.137
# invokes the bearer scheme without a Request -> "OAuth2PasswordBearer.__call__()
# missing 'request'" and the handshake dies (and, via the shared router, breaks
# authenticated /api/ HTTP calls too -> manager 503 / KeyError 'devices').
# fastapi 0.95 tolerated this; 0.137 does not. /ws self-authenticates via the
# token query param, so it lives on its own dependency-free router.
ws_router = APIRouter()


async def on_reload():
    mqtt.publish('api/data-refresh', qos=1)
    await manager.broadcast(json.dumps({
        'target': 'app',
        'data': {
            'event': {'type': 'refresh'}
        }
    }))


data_loader = None
_loop: asyncio.AbstractEventLoop | None = None


def create_dataloader():
    global data_loader
    # Stop the previous loader before replacing it so a failed/slow loader's
    # threads don't accumulate (on_error re-invokes this from its worker thread).
    if data_loader is not None:
        data_loader.stop()
    logger.debug('Creating DataLoader instance')
    data_loader = DataLoader(_loop, on_reload=on_reload,
                             on_error=create_dataloader)
    data_loader.start()


def start_dataloader(loop: asyncio.AbstractEventLoop):
    # Capture the RUNNING server loop here (from the lifespan), not at import.
    # uvicorn 0.47+ imports the ASGI app eagerly in the parent process before the
    # server loop exists, and on Python 3.12 a module-scope asyncio.get_event_loop()
    # binds a throwaway loop that never runs — so run_coroutine_threadsafe(on_reload,
    # that_loop) from the NetBox worker thread would silently never fire (no MQTT
    # data-refresh publish, no WS 'refresh' broadcast).
    global _loop
    _loop = loop
    create_dataloader()


def stop_dataloader():
    global data_loader
    if data_loader is not None:
        data_loader.stop()
        data_loader = None


async def data_refresh():
    if data_loader is None:
        raise HTTPException(status_code=503, detail='DataLoader not ready')
    data_loader.reload()


@router.get('/')
async def get():
    return {
        'devices': await get_devices(),
        'tags': await get_tags(),
        'locations': await get_locations(),
    }


@router.get('/devices')
async def get_devices() -> list:
    async with data_loader:
        return data_loader.devices


@router.get('/tags')
async def get_tags() -> list:
    async with data_loader:
        return data_loader.tags


@router.get('/locations')
async def get_locations() -> list:
    async with data_loader:
        return data_loader.locations


class MethodTarget(StrEnum):
    device = 'device'
    tag = 'tag'
    location = 'location'


@router.post('/{target}/{method_name}')
async def method(target: MethodTarget, method_name, params: Annotated[dict, Body()]):
    logger.debug('Method %s %s', target, method_name)
    mqtt.publish(f'api/{str(target)}/{method_name}',
                 json.dumps(params),
                 qos=1)


@ws_router.websocket('/ws')
async def ws(websocket: WebSocket, token: str = Query(...),
             jwt_strategy: JWTStrategy = Depends(get_jwt_strategy),
             user_manager: UserManager = Depends(get_user_manager)):
    # Validate the token BEFORE registering the socket so an unauthenticated
    # client is never added to the broadcast pool (and a failed auth never
    # leaves a closed socket behind).
    await websocket.accept()
    try:
        user = await jwt_strategy.read_token(token, user_manager)
        if user is None:
            raise HTTPException(401)
    except:
        await websocket.send_json({'error': {'message': 'Authentication failed'}})
        await websocket.close(code=1000)
        return
    manager.register(websocket)
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except:
                break
            # Ignore frames without a 'fetch' command instead of tearing down the
            # connection, and constrain target to the known whitelist (no topic
            # injection from the client into api/{target}/fetch).
            if message.get('command') == 'fetch' and message.get('target') in MethodTarget.__members__:
                mqtt.publish(
                    f'api/{message["target"]}/fetch', json.dumps(message))
    finally:
        manager.disconnect(websocket)
