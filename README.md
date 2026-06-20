# Alemeno AI: Intelligent Transaction Pipeline

Alemeno AI is a high-performance, asynchronous pipeline designed to ingest, clean, and analyze financial transaction data using Artificial Intelligence.

## 🚀 The Purpose
Financial data is often messy, inconsistent, and voluminous. This project solves that by automating the transition from **Raw CSV Data** to **Actionable Financial Insights**. It uses Large Language Models (LLM) to categorize spending, detect anomalies, and generate human-readable narratives about financial health.

---

## 🛠 Tech Stack
- **Backend**: FastAPI (Python) - High performance, asynchronous API.
- **Asynchronous Processing**: Celery + Redis - Handles heavy AI processing without blocking the UI.
- **AI Engine**: Google Gemini 1.5 Flash - Used for intelligent categorization and narrative generation.
- **Database**: MongoDB (Beanie ODM) - Stores transaction records and processing results.
- **Frontend**: Vanilla JS + CSS (Dashboard) - Premium, minimalist UI with real-time Chart.js visualizations.
- **Containerization**: Docker & Docker Compose - Ensures the app runs perfectly on any machine.

---

## 🔄 How It Works: The Pipeline

### 1. File Ingestion
When you upload a CSV via the dashboard, the **FastAPI** server receives it, creates a unique `Job ID` in MongoDB, and immediately sends the raw data to a **Redis** queue. 

### 2. The Worker (Celery)
A separate **Celery Worker** process picks up the job from the queue. This is crucial because AI processing can take time, and we don't want the user's browser to freeze.

### 3. Data Cleaning (Pandas)
The worker uses **Pandas** to:
- Standardize date formats.
- Convert currencies (using a fixed base or AI).
- Handle missing values (NaNs).

### 4. AI Analysis (Gemini)
The cleaned data is sent to the **Gemini 1.5 Flash API**, which performs:
- **Intelligent Categorization**: It looks at merchant names (e.g., "Starbucks") and assigns categories (e.g., "Food & Dining").
- **Anomaly Detection**: It flags unusual spikes or suspicious transactions.
- **Narrative Generation**: It writes a 2-3 sentence summary of the entire file (e.g., "You spent 40% more on Travel this month").

### 5. Persistence & UI
The final "Cleaned & Analyzed" data is saved back to **MongoDB**. The frontend dashboard polls the API, and once the task is marked as `completed`, it renders the results using **Chart.js**.

---

## 📁 Key Files & Folders

| File/Folder | Purpose |
| :--- | :--- |
| `app/main.py` | The "Brain" of the API. Manages endpoints and routing. |
| `app/tasks.py` | The "Worker's Logic". Contains the AI processing pipeline. |
| `app/models.py` | Defines how data (Jobs/Transactions) is structured in MongoDB. |
| `app/pipeline/` | Contains the actual cleaning and AI logic scripts. |
| `static/` | The "Face" of the project. Contains the Dashboard (HTML/CSS/JS). |
| `docker-compose.yml` | The "Orchestrator". Runs API, Worker, Redis, and DB in harmony. |

---

## 🚦 How to Run
1.  **Environment**: Add your `GEMINI_API_KEY` to the `.env` file.
2.  **Containerize**: Run `docker compose up --build`.
3.  **Access**: Open `http://localhost:8000` in your browser.

---

**Built with ❤️ for the Almeno Assignment.**
