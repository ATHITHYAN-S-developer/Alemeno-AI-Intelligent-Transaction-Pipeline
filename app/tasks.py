from celery import Celery
import asyncio
from app.config import settings
from app.database import init_db
from app.models import Job, Transaction, JobSummary
import pandas as pd
import io
from datetime import datetime
from app.pipeline.cleaning import clean_transaction_data
from app.pipeline.anomalies import detect_anomalies
from app.pipeline.llm import classify_with_llm, generate_narrative_summary

celery_app = Celery("tasks", broker=settings.REDIS_URI, backend=settings.REDIS_URI)

@celery_app.task(name="process_transactions_task")
def process_transactions_task(job_id: str, csv_content: str):
    return asyncio.run(process_pipeline(job_id, csv_content))

async def process_pipeline(job_id: str, csv_content: str):
    await init_db()
    job = await Job.get(job_id)
    if not job:
        return
    
    try:
        job.status = "processing"
        await job.save()
        
        # Load CSV
        df = pd.read_csv(io.StringIO(csv_content))
        job.row_count_raw = len(df)
        await job.save()
        
        # 1. Data Cleaning
        df_clean = clean_transaction_data(df)
        job.row_count_clean = len(df_clean)
        await job.save()
        
        # 2. Anomaly Detection
        df_anomalies = detect_anomalies(df_clean)
        
        # 3. LLM Classification (Batch)
        df_llm = await classify_with_llm(df_anomalies)
        
        # Save transactions to DB
        transactions = []
        for _, row in df_llm.iterrows():
            txn = Transaction(
                job_id=job_id,
                txn_id=str(row['txn_id']) if pd.notnull(row['txn_id']) else None,
                date=str(row['date']),
                date_iso=row['date_iso'] if 'date_iso' in row and pd.notnull(row['date_iso']) else None,
                merchant=str(row['merchant']),
                amount=float(row['amount']),
                currency=str(row['currency']),
                status=str(row['status']),
                category=str(row['category']),
                account_id=str(row['account_id']),
                notes=str(row['notes']) if pd.notnull(row['notes']) else None,
                is_anomaly=bool(row.get('is_anomaly', False)) if pd.notnull(row.get('is_anomaly')) else False,
                anomaly_reason=str(row['anomaly_reason']) if pd.notnull(row.get('anomaly_reason')) else None,
                llm_category=row.get('llm_category') if pd.notnull(row.get('llm_category')) else None,
                llm_failed=bool(row.get('llm_failed', False)) if pd.notnull(row.get('llm_failed')) else False
            )
            transactions.append(txn)
        
        if transactions:
            await Transaction.insert_many(transactions)
        
        # 4. LLM Narrative Summary
        summary_data = await generate_narrative_summary(df_llm)
        
        job_summary = JobSummary(
            job_id=job_id,
            total_spend_inr=summary_data.get('total_spend_inr', 0),
            total_spend_usd=summary_data.get('total_spend_usd', 0),
            top_merchants=summary_data.get('top_merchants', []),
            anomaly_count=summary_data.get('anomaly_count', 0),
            narrative=summary_data.get('narrative'),
            risk_level=summary_data.get('risk_level', 'low')
        )
        await job_summary.insert()
        
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        await job.save()
        
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        await job.save()
        raise e
