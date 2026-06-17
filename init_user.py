import os
import asyncio
import getpass

import contextlib

from beanie import init_beanie

from db import db, User, get_user_db
from schemas import UserCreate
from users import get_user_manager
from fastapi_users.exceptions import UserAlreadyExists

get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


async def create_user(email: str, password: str, is_superuser: bool = False):
    try:
        await init_beanie(
            database=db,
            document_models=[
                User,
            ],
        )
        async with get_user_db_context() as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                user = await user_manager.create(
                    UserCreate(
                        email=email, password=password, is_superuser=is_superuser
                    )
                )
                print(f'User created {user}')
    except UserAlreadyExists:
        print(f'User {email} already exists')


def get_userpass():
    password = getpass.getpass('Password (can be changed later): ')
    if password == getpass.getpass('Verify password: '):
        return password
    else:
        print('Passwords do not match!')
        return get_userpass()


async def main():
    print('Creating system user...')
    username = os.environ.get('API_SYSTEM_USERNAME')
    password = str(os.environ.get('API_SYSTEM_PASSWORD'))
    # create_user already swallows UserAlreadyExists; let any other failure
    # surface instead of masking it with a broad except.
    await create_user(username, password, is_superuser=True)
    print('Please create your admin account')
    username = input('Email: ')
    password = get_userpass()
    await create_user(username, password, is_superuser=True)
    print('Done!')


if __name__ == '__main__':
    asyncio.run(main())
