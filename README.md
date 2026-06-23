# Alemeno AI: Intelligent Transaction Pipeline

Alemeno AI is a high-performance, asynchronous pipeline designed to ingest, clean, and analyze financial transaction data using Artificial Intelligence.

---

## 🚀 Overall Concept

Financial transaction logs are frequently messy, unstructured, and large. This project builds a reliable, production-ready pipeline that automates the transition from **Raw CSV Data** to **Structured Financial Insights**. 

When a user uploads a transaction ledger:
1. The **FastAPI Backend** accepts the file upload, registers a tracking `Job` in the database, and offloads the processing workload.
2. The **Celery Background Worker** processes the ledger asynchronously. This prevents web server timeouts and UI freezing during heavy AI requests.
3. The **Data Pipeline** cleans the data using **Pandas**, maps custom headers via LLM, detects statistical anomalies, and runs batch LLM queries to categorize merchants and generate summaries.
4. The results are stored in **MongoDB** and displayed on a premium, real-time **HTML5/JS Dashboard** featuring dynamic visualizations.

---

## 🛠️ Technical Stack & How They Are Used

1. **FastAPI (Python)**:
   - Actively handles incoming REST API requests, streaming file uploads, and serving static files.
   - Utilizes `async/await` for high-throughput, non-blocking I/O.
2. **Celery & Redis**:
   - **Celery**: Runs background worker threads to clean data and invoke Gemini.
   - **Redis**: Acts as the message broker passing tasks from FastAPI to Celery, and storing task states.
3. **Google Gemini 1.5 Flash (API)**:
   - Performs intelligent header mapping (renaming arbitrary CSV headers to standard keys).
   - Classifies unknown merchants into financial categories (Food, Shopping, Travel, etc.) using batching.
   - Generates a concise 2-sentence financial health narrative and risk assessment.
4. **MongoDB & Beanie ODM**:
   - A NoSQL document database used to store jobs, transactions, and summaries.
   - **Beanie**: An asynchronous ODM (Object Document Mapper) for MongoDB that uses **Pydantic** models to enforce schemas.
5. **Pandas & NumPy**:
   - Used inside Celery tasks to parse CSVs, deduplicate records, clean/normalize amounts, and calculate statistical medians.
6. **HTML5, Vanilla CSS, JS & Chart.js**:
   - A modern, minimalist glassmorphism dashboard that displays live progress, spending distributions, and transaction anomalies.

---

## 📁 File and Function Purposes

### Backend Architecture (`app/`)

#### 1. `app/database.py`
- **Purpose**: Establishes the database connection.
- **Functions**:
  - `init_db()`: Initializes the MongoDB client using `motor` and links the Beanie ODM models (`Job`, `Transaction`, `JobSummary`).

#### 2. `app/models.py`
- **Purpose**: Declares Beanie MongoDB collections and Pydantic models.
- **Models**:
  - `Job`: Tracks ledger processing state (`pending`, `processing`, `completed`, `failed`), timestamps, and raw/clean row counts.
  - `Transaction`: Represents an individual transaction document. Stores dates, merchants, amounts, categories, and anomaly flags.
  - `JobSummary`: Stores overall aggregate analytics, top spending merchants, AI narrative, and calculated risk level.

#### 3. `app/schemas.py`
- **Purpose**: Defines Pydantic validation schemas for API endpoints, separating inputs and outputs.
- **Schemas**:
  - `JobResponse`, `JobStatusResponse`, `JobResultsResponse`.

#### 4. `app/tasks.py`
- **Purpose**: Defines asynchronous tasks handled by Celery.
- **Functions**:
  - `process_transactions_task(job_id, file_path)`: Runs the entire ingestion and cleaning sequence. Parses the CSV via Pandas, maps headers via LLM, cleans rows, categorizes transactions in batches, detects anomalies, saves data in bulk chunks to MongoDB, triggers the LLM summary, and marks the job as completed.

#### 5. `app/main.py`
- **Purpose**: The FastAPI application entrypoint.
- **Endpoints**:
  - `@app.post("/api/jobs/upload")`: Uploads a CSV file, saves it to a local buffer, creates a pending job, and dispatches the Celery task.
  - `@app.get("/api/jobs/{job_id}/status")`: Returns the job's current status and basic summary details.
  - `@app.get("/api/jobs/{job_id}/results")`: Returns aggregated results (capped at 1000 normal transactions + 1000 anomalies for browser performance).
  - `@app.get("/api/jobs/{job_id}/download")`: Streams the complete dataset as a CSV using `StreamingResponse` to prevent memory overload.

---

### Pipeline Components (`app/pipeline/`)

#### 1. `app/pipeline/cleaning.py`
- **Purpose**: Pandas-based cleaning of transaction rows.
- **Functions**:
  - `clean_transaction_data(df)`: Deduplicates rows, normalizes date columns to ISO 8601, and extracts numeric floats from dirty amount strings (removing currency signs like `₹`, `$`, etc.).

#### 2. `app/pipeline/anomalies.py`
- **Purpose**: Rule-based and statistical anomaly detection.
- **Functions**:
  - `detect_anomalies(df)`: Identifies outliers by flagging transactions that exceed 3 times the account's median spend or domestic merchants charged in USD.

#### 3. `app/pipeline/llm.py`
- **Purpose**: LLM interaction wrapper for Gemini and Ollama.
- **Functions**:
  - `map_headers_with_llm(user_headers)`: Asks LLM to match CSV headers to the schema fields.
  - `classify_with_llm(df)`: Resolves unknown categories. Uses a local cache first, and batches leftover unique merchants (up to 20 at a time) for LLM classification.
  - `generate_narrative_summary(df, summary_stats)`: Requests a 2-sentence financial health narrative and risk level based on aggregate statistics.

---

### Frontend Files (`static/`)
- `static/index.html`: Holds the dashboard markup, routing tabs, file upload trigger, summary cards, recent activity feed, and a detailed results viewer modal.
- `static/script.js`: Orchestrates view routing, file upload, stats updates, rendering Chart.js charts, polling task statuses, displaying results, and triggering streaming downloads.
- `static/style.css`: Sets CSS custom properties, defines a premium minimalist glassmorphism interface, and configures responsive layouts.

---

## 🐳 How Docker Works Here

The project uses Docker and Docker Compose to containerize and connect the entire environment. The orchestrator file `docker-compose.yml` sets up a virtual network running **4 services**:

1. **`mongo`**: Starts a MongoDB instance on port `27017` with persistent volume storage (`mongo_data`).
2. **`redis`**: Starts a Redis server on port `6379` to serve as Celery's broker.
3. **`api`**: Builds a container from the `Dockerfile` and runs Uvicorn on port `8000`. The local repository folder is mounted (`.:/app`) to enable code hot-reloading.
4. **`worker`**: Builds a container from the same `Dockerfile` and runs `celery -A app.tasks worker --loglevel=info`.

The containers share a common network allowing the API and worker to communicate with Mongo and Redis using hostname URIs (e.g. `mongodb://mongo:27017`).

---

## 🚦 How the API Works: Code Walkthrough

When you click **Upload** in the UI:
1. **API Upload Handler**:
   ```python
   @app.post("/api/jobs/upload")
   async def upload_csv(file: UploadFile = File(...)):
       job = Job(filename=file.filename, status="pending")
       await job.insert()
       file_path = f"data/uploads/{job.id}_{file.filename}"
       # ... streams file to disk ...
       process_transactions_task.delay(str(job.id), file_path) # Enqueues Celery task
       return {"job_id": str(job.id)}
   ```
2. **Celery Worker Execution**:
   Celery picks up the task and begins loading the CSV:
   ```python
   @shared_task
   def process_transactions_task(job_id, file_path):
       df = pd.read_csv(file_path)
       df = clean_transaction_data(df)
       df = detect_anomalies(df)
       # ... runs LLM categorization & stores results in MongoDB ...
   ```
3. **Memory-Safe Results Retrieval**:
   Since datasets can be massive (e.g. 7.4M rows), `/api/jobs/{job_id}/results` limits response items to avoid crashing the browser:
   ```python
   normal_txns = await Transaction.find(..., Transaction.is_anomaly == False).limit(1000).to_list()
   anomalies = await Transaction.find(..., Transaction.is_anomaly == True).limit(1000).to_list()
   ```
4. **Memory-Safe Streaming Download**:
   To download the full dataset, the `/api/jobs/{job_id}/download` endpoint streams the database cursor block-by-block directly as CSV lines, keeping RAM consumption constant and low:
   ```python
   @app.get("/api/jobs/{job_id}/download")
   async def download_job_results(job_id: str):
       async def csv_generator():
           yield "txn_id,date,merchant,amount,currency...\n"
           async for txn in Transaction.find(Transaction.job_id == job_id):
               yield f"{txn.txn_id},{txn.date},{txn.merchant}...\n"
       return StreamingResponse(csv_generator(), media_type="text/csv")
   ```

---

## 🐍 A Note on Django vs. FastAPI

This project **does not use Django**. Instead, it uses **FastAPI**. Here is why FastAPI was chosen for this specific architecture:

* **Asynchronous Native Design**: Django is historically built on WSGI (synchronous blocking thread per request model). While Django has added async capabilities, FastAPI was built from the ground up on ASGI (Asynchronous Server Gateway Interface) and `uvicorn`. This allows FastAPI to handle thousands of concurrent API requests (like polling for job statuses) using a single thread, consuming far less CPU and memory.
* **Non-Blocking I/O**: The pipeline relies on long-running AI requests (Gemini API calls) and high-volume database queries (MongoDB). FastAPI allows us to run these operations using `async/await` concurrently without locking up request threads.
* **Auto-Generated Documentation**: FastAPI automatically produces interactive Swagger UI docs (accessible at `http://localhost:8000/docs`) directly from Python type hints and Pydantic schemas, simplifying endpoint testing.
