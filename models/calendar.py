from enum import StrEnum
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from . import PyObjectId


class ItemType(StrEnum):
    Device = 'device'
    Tag = 'tag'
    Location = 'location'


class EventActionsModel(BaseModel):
    start: str = Field()
    end: str = Field()


class ExtendedPropsModel(BaseModel):
    id: int = Field()
    type: ItemType = Field()
    label: str = Field()
    description: Optional[str] = None
    actions: EventActionsModel = Field()


class EventModel(BaseModel):
    id: PyObjectId = Field(alias='_id')
    title: str = Field()
    start: datetime = Field()
    end: Optional[datetime] = None
    allDay: bool = Field()
    rrule: Optional[str] = None
    duration: Optional[float] = None
    extendedProps: ExtendedPropsModel = Field()

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str,
                       datetime: lambda date: date.isoformat()},
    )


class UpdateEventModel(BaseModel):
    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    allDay: Optional[bool] = None
    extendedProps: Optional[ExtendedPropsModel] = None
