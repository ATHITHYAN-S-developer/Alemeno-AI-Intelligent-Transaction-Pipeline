from celery import Celery
import asyncio
import os
from app.config import settings
from app.database import init_db
from app.models import Job, Transaction, JobSummary
import pandas as pd
import io
from datetime import datetime
from collections import defaultdict
from app.pipeline.cleaning import clean_transaction_data
from app.pipeline.anomalies import detect_anomalies
from app.pipeline.llm import classify_with_llm, generate_narrative_summary, map_headers_with_llm

celery_app = Celery("tasks", broker=settings.REDIS_URI, backend=settings.REDIS_URI)

celery_app.conf.update(
    task_track_started=True,
    task_send_sent_event=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True
)

@celery_app.task(name="process_transactions_task")
def process_transactions_task(job_id: str, file_path_or_content: str):
    return asyncio.run(process_pipeline(job_id, file_path_or_content))

async def process_pipeline(job_id: str, payload: str):
    await init_db()
    job = await Job.get(job_id)
    if not job:
        return
    
    try:
        job.status = "processing"
        await job.save()
        
        # Determine if payload is a file path or direct content
        is_file = os.path.exists(payload)
        
        # Initialize stats
        total_raw = 0
        total_clean = 0
        overall_df_sample = [] # To keep a small sample for the narrative summary
        sample_rows_collected = 0
        total_spend_inr = 0.0
        total_spend_usd = 0.0
        anomaly_count = 0
        merchant_totals = defaultdict(float)
        
        # Intelligent Header Mapping (using first few rows)
        if is_file:
            sample_df = pd.read_csv(payload, nrows=100)
        else:
            sample_df = pd.read_csv(io.StringIO(payload), nrows=100)
            
        current_headers = sample_df.columns.tolist()
        mapping = {}
        essential_missing = not all(f in current_headers for f in ["date", "merchant", "amount"])
        if essential_missing:
            mapping = await map_headers_with_llm(current_headers)
        
        # Chunked processing (approx 100MB per batch for typical transaction rows)
        chunksize = 250000
        reader = pd.read_csv(payload if is_file else io.StringIO(payload), chunksize=chunksize)
        
        for chunk in reader:
            total_raw += len(chunk)
            
            # Apply header mapping
            if mapping:
                rename_map = {v: k for k, v in mapping.items() if v in chunk.columns}
                chunk = chunk.rename(columns=rename_map)
            
            # 1. Data Cleaning
            df_clean = clean_transaction_data(chunk)
            total_clean += len(df_clean)
            
            # 2. Anomaly Detection
            df_anomalies = detect_anomalies(df_clean)
            
            # 3. LLM Classification (Batch for Uncategorised in this chunk)
            # Skip LLM classification for extreme datasets (> 500k rows) to prevent timeouts
            if total_raw < 500000:
                df_llm = await classify_with_llm(df_anomalies)
            else:
                df_llm = df_anomalies

            if not df_llm.empty:
                inr_mask = df_llm['currency'] == 'INR'
                usd_mask = df_llm['currency'] == 'USD'
                total_spend_inr += float(df_llm.loc[inr_mask, 'amount'].sum())
                total_spend_usd += float(df_llm.loc[usd_mask, 'amount'].sum())
                anomaly_count += int(df_llm['is_anomaly'].sum())

                for merchant, amount in df_llm.groupby('merchant')['amount'].sum().items():
                    merchant_totals[str(merchant)] += float(amount)
            
            # Save chunk transactions to DB
            transactions = []
            for _, row in df_llm.iterrows():
                # Ensure we don't pass NaN to fields that expect strings
                merchant_val = str(row['merchant']) if pd.notnull(row.get('merchant')) else "Unknown Merchant"
                date_val = str(row['date']) if pd.notnull(row.get('date')) else datetime.utcnow().strftime('%Y-%m-%d')
                
                txn = Transaction(
                    job_id=job_id,
                    txn_id=str(row['txn_id']) if pd.notnull(row.get('txn_id')) else None,
                    date=date_val,
                    date_iso=row['date_iso'] if 'date_iso' in row and pd.notnull(row['date_iso']) else None,
                    merchant=merchant_val,
                    amount=float(row['amount']) if pd.notnull(row.get('amount')) else 0.0,
                    currency=str(row['currency']) if pd.notnull(row.get('currency')) else "INR",
                    status=str(row['status']) if pd.notnull(row.get('status')) else "SUCCESS",
                    category=str(row['category']) if pd.notnull(row.get('category')) else "Uncategorised",
                    account_id=str(row['account_id']) if pd.notnull(row.get('account_id')) else "DEFAULT_ACC",
                    notes=str(row['notes']) if pd.notnull(row.get('notes')) else None,
                    is_anomaly=bool(row.get('is_anomaly', False)),
                    anomaly_reason=str(row['anomaly_reason']) if pd.notnull(row.get('anomaly_reason')) else None,
                    llm_category=row.get('llm_category') if pd.notnull(row.get('llm_category')) else None
                )
                transactions.append(txn)
            
            if transactions:
                await Transaction.insert_many(transactions)
                
            # Collect sample for narrative (first 100 cleaned rows)
            if sample_rows_collected < 100:
                sample = df_llm.head(100 - sample_rows_collected)
                overall_df_sample.append(sample)
                sample_rows_collected += len(sample)
            
            # Update job progress every 2 chunks (~500k rows) for real-time UI visibility
            if total_raw % (chunksize * 2) == 0:
                job.row_count_raw = total_raw
                job.row_count_clean = total_clean
                await job.save()

        # 4. LLM Narrative Summary (using the collected sample)
        final_sample_df = pd.concat(overall_df_sample) if overall_df_sample else pd.DataFrame()
        top_merchants = [
            {"merchant": merchant, "amount": amount}
            for merchant, amount in sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:3]
        ]
        summary_stats = {
            "total_spend_inr": total_spend_inr,
            "total_spend_usd": total_spend_usd,
            "anomaly_count": anomaly_count,
            "top_merchants": top_merchants
        }
        summary_data = await generate_narrative_summary(final_sample_df, summary_stats=summary_stats)
        
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
        job.row_count_raw = total_raw
        job.row_count_clean = total_clean
        job.completed_at = datetime.utcnow()
        await job.save()
        
        # Cleanup uploaded file if it was a file
        if is_file and os.path.exists(payload):
            os.remove(payload)
            
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        await job.save()
        raise e
