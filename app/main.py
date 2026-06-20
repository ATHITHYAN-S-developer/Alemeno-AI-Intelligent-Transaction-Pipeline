from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from typing import List, Optional
from app.database import init_db
from app.models import Job, Transaction, JobSummary
from app.schemas import JobResponse, JobStatusResponse, JobResultsResponse
import uuid
import os
from app.tasks import process_transactions_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Transaction Processing API", lifespan=lifespan)

# Mount static files
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/ui", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/ui/index.html")

@app.post("/api/jobs/upload", response_model=dict)
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    # Save file temporarily or read content
    content = await file.read()
    # For simplicity, we'll store the filename and process it
    # In a real app, we'd save it to a storage bucket
    
    job = Job(filename=file.filename, status="pending")
    await job.insert()
    
    # Enqueue task
    process_transactions_task.delay(str(job.id), content.decode('utf-8'))
    
    return {"job_id": str(job.id)}

@app.get("/api/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = await Job.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    summary_data = None
    if job.status == "completed":
        summary = await JobSummary.find_one(JobSummary.job_id == job_id)
        if summary:
            summary_data = {
                "total_spend_inr": summary.total_spend_inr,
                "total_spend_usd": summary.total_spend_usd,
                "anomaly_count": summary.anomaly_count,
                "risk_level": summary.risk_level
            }
            
    return {
        "id": str(job.id),
        "status": job.status,
        "summary": summary_data
    }

@app.get("/api/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(job_id: str):
    job = await Job.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    transactions = await Transaction.find(Transaction.job_id == job_id).to_list()
    summary = await JobSummary.find_one(JobSummary.job_id == job_id)
    
    return {
        "job_id": str(job.id),
        "status": job.status,
        "cleaned_transactions": transactions,
        "summaries": summary.dict() if summary else None
    }

@app.get("/api/jobs", response_model=List[JobResponse])
async def list_jobs(status: Optional[str] = Query(None)):
    query = {}
    if status:
        jobs = await Job.find(Job.status == status).to_list()
    else:
        jobs = await Job.find_all().to_list()
    
    return [
        {
            "id": str(j.id),
            "filename": j.filename,
            "status": j.status,
            "row_count_raw": j.row_count_raw,
            "row_count_clean": j.row_count_clean,
            "created_at": j.created_at,
            "completed_at": j.completed_at
        } for j in jobs
    ]
