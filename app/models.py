from typing import List, Optional
from datetime import datetime
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class JobStatus(str):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Document):
    filename: str
    status: str = "pending"
    row_count_raw: int = 0
    row_count_clean: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Settings:
        name = "jobs"

class Transaction(Document):
    job_id: Indexed(str)
    txn_id: Optional[str] = None
    date: str
    date_iso: Optional[datetime] = None
    merchant: str
    amount: float
    currency: str
    status: str
    category: Optional[str] = "Uncategorised"
    account_id: str
    notes: Optional[str] = None
    
    # Analysis fields
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_raw_response: Optional[str] = None
    llm_failed: bool = False

    class Settings:
        name = "transactions"

class MerchantSpend(BaseModel):
    merchant: str
    amount: float

class JobSummary(Document):
    job_id: Indexed(str)
    total_spend_inr: float = 0.0
    total_spend_usd: float = 0.0
    top_merchants: List[MerchantSpend] = []
    anomaly_count: int = 0
    narrative: Optional[str] = None
    risk_level: str = "low" # low, medium, high

    class Settings:
        name = "job_summaries"
