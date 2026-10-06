from typing import Annotated, Any

from bson import ObjectId
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema


class _ObjectIdAnnotation:
    """pydantic v2 annotation: validate str/ObjectId -> ObjectId, serialize to
    str in JSON, and present as a string in the JSON schema."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(v: Any) -> ObjectId:
            if isinstance(v, ObjectId):
                return v
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid objectid")
            return ObjectId(v)

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, return_schema=core_schema.str_schema(), when_used="json"
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        return {"type": "string"}


# Use as a field type: `id: PyObjectId = Field(alias='_id')`
PyObjectId = Annotated[ObjectId, _ObjectIdAnnotation]
