from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models import Job, Transaction, JobSummary
from app.config import settings

async def init_db():
    client = AsyncIOMotorClient(settings.MONGO_URI)
    # The database name is taken from the URI or defaults to 'transaction_db'
    db_name = settings.MONGO_URI.split("/")[-1] or "transaction_db"
    await init_beanie(database=client[db_name], document_models=[Job, Transaction, JobSummary])
