from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class JobResponse(BaseModel):
    id: str
    filename: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime
    completed_at: Optional[datetime] = None

class JobStatusResponse(BaseModel):
    id: str
    status: str
    summary: Optional[dict] = None

class TransactionResponse(BaseModel):
    txn_id: Optional[str]
    date: str
    merchant: str
    amount: float
    currency: str
    status: str
    category: str
    is_anomaly: bool
    anomaly_reason: Optional[str]

class JobResultsResponse(BaseModel):
    job_id: str
    status: str
    cleaned_transactions: List[TransactionResponse]
    summaries: Optional[dict] = None
    category_distribution: Optional[dict] = None
