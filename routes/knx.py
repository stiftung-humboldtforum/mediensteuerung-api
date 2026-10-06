from datetime import datetime
from fastapi import Depends, APIRouter
from fastapi.encoders import jsonable_encoder
import pymongo
from users import current_active_user
from db import client
from misc import logger

db = client['knx']

router = APIRouter(dependencies=[Depends(current_active_user)])


@router.get('/knx/get_events')
async def get_events():
    events = []
    # pymongo's async aggregate() is a coroutine (must be awaited) — unlike
    # find(), and unlike motor's sync-returning aggregate().
    aggregate_events = await db['events'].aggregate(
        [{'$sort': {'data.event.time': pymongo.DESCENDING}}])
    async for event in aggregate_events:
        event['_id'] = str(event['_id'])
        events.append(jsonable_encoder(event))
    return events


async def save_event(event):
    try:
        payload = jsonable_encoder(event)
        await db['events'].insert_one(payload)
    except Exception as e:
        logger.exception(e)
