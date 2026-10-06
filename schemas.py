from typing import Generic, Optional
from beanie import PydanticObjectId
from pydantic import ConfigDict
from fastapi_users import models
from fastapi_users.schemas import CreateUpdateDictModel


class BaseUser(CreateUpdateDictModel, Generic[models.ID]):
    """Base User model."""

    # Keep email as a plain str (NOT EmailStr): the system/admin accounts use
    # non-FQDN addresses like system@localhost that EmailStr would reject.
    id: models.ID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class BaseUserCreate(CreateUpdateDictModel):
    email: str
    password: str
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


class BaseUserUpdate(CreateUpdateDictModel):
    password: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserRead(BaseUser[PydanticObjectId]):
    pass


class UserCreate(BaseUserCreate):
    pass


class UserUpdate(BaseUserUpdate):
    pass
