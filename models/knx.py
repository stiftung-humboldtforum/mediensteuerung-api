from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from . import PyObjectId


class KNXEventModel(BaseModel):
    id: PyObjectId = Field(alias='_id')
    target: int = Field()
    value: bool = Field()
    time: int = Field()

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
