import os
from typing import Any, Optional
import contextlib

from beanie import PydanticObjectId
from fastapi import Response, Query, APIRouter, Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_beanie import BeanieUserDatabase, ObjectIDIDMixin

from db import db, User, get_user_db
from schemas import UserRead

SECRET = os.environ['API_SECRET']


class UserManager(ObjectIDIDMixin, BaseUserManager[User, PydanticObjectId]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f'User {user.id} has registered.')

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f'User {user.id} has forgot their password. Reset token: {token}')

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(
            f'Verification requested for user {user.id}. Verification token: {token}')


async def get_user_manager(user_db: BeanieUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)

bearer_transport = BearerTransport(tokenUrl='auth/jwt/login')


def get_jwt_strategy() -> JWTStrategy:
    # JWT lifetime in seconds; defaults to 1 year for backward compatibility.
    # Set JWT_LIFETIME_SECONDS (e.g. 3600) to shorten and rely on the existing
    # /auth/jwt/refresh endpoint.
    lifetime = int(os.getenv('JWT_LIFETIME_SECONDS') or 365 * 24 * 60 * 60)
    return JWTStrategy(secret=SECRET, lifetime_seconds=lifetime)


auth_backend = AuthenticationBackend(
    name='jwt',
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, PydanticObjectId](
    get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_active_admin = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(
    prefix='/users', dependencies=[Depends(current_active_admin)])


@router.get('/', response_model=list[UserRead])
async def list_users(
    is_active: bool = Query(None),  # Optional query parameter "is_active"
):
    # `db` is an instance of `AsyncIOMotorDatabase` (just like in the FastAPI Users exampleà
    users_collection = db['User']
    # Start to build a query (empty query means everything in MongoDB)
    query: dict[str, Any] = {}

    # Apply an is_active filter if the query is specified
    if is_active is not None:
        query['is_active'] = is_active

    # Perform the query
    cursor = users_collection.find(query)  # This an async iterator
    # For each result, MongoDB gives us a raw dictionary that we hydrate back in our Pydantic model
    results = [User(**obj) async for obj in cursor]

    return results
