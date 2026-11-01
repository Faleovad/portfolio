import os

import httpx
import pytest_asyncio
from platform_core.api import create_app
from platform_core.database import transaction

DSN = os.environ.get("ORCHESTRATOR_DSN")
ADMIN = os.environ.get("ORCHESTRATOR_ADMIN_DSN")
READ = os.environ.get("PROVIDER_READ_DSN")
PROVIDER_ADMIN = os.environ.get("PROVIDER_ADMIN_DSN")


@pytest_asyncio.fixture
async def client():
    async with transaction(ADMIN) as c:
        await c.execute("TRUNCATE tenants CASCADE")
    async with transaction(PROVIDER_ADMIN) as c:
        await c.execute("TRUNCATE effects,provider_attempts RESTART IDENTITY CASCADE")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(DSN, READ, True)), base_url="http://lab"
    ) as value:
        yield value
