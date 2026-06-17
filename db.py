import os
import contextlib
from urllib.parse import quote_plus

from pymongo import AsyncMongoClient
from fastapi_users_db_beanie import BeanieBaseUserDocument, BeanieUserDatabase


mongodb_url = 'mongodb://%s:%s@%s:27017/%s' % tuple(map(quote_plus, (os.environ['MONGO_INITDB_USERNAME'], os.environ['MONGO_INITDB_PASSWORD'], os.environ['MONGO_INITDB_HOSTNAME'], os.environ['MONGO_INITDB_DATABASE'])))
# Enable TLS to Mongo via MONGO_TLS=true (+ optional MONGO_TLS_CA_FILE); defaults
# off so existing plaintext deployments keep working.
_client_kwargs = {'uuidRepresentation': 'standard'}
if os.getenv('MONGO_TLS', '').lower() in ('1', 'true', 'yes'):
    _client_kwargs['tls'] = True
    _ca = os.getenv('MONGO_TLS_CA_FILE')
    if _ca:
        _client_kwargs['tlsCAFile'] = _ca
client = AsyncMongoClient(mongodb_url, **_client_kwargs)
db = client['users']


class User(BeanieBaseUserDocument):
    pass


async def get_user_db():
    yield BeanieUserDatabase(User)

get_user_db_context = contextlib.asynccontextmanager(get_user_db)
