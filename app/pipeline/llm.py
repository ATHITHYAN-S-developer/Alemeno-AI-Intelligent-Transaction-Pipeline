import google.generativeai as genai
import pandas as pd
import json
import asyncio
import httpx
from app.config import settings
import time

# Classification Cache to reduce redundant LLM calls
MERCHANT_CATEGORY_CACHE = {
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "zomato": "Food",
    "swiggy": "Food",
    "uber": "Transport",
    "ola": "Transport",
    "netflix": "Entertainment",
    "spotify": "Entertainment"
}

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

async def call_gemini(prompt):
    if not gemini_model:
        return None
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: gemini_model.generate_content(prompt))
    return response.text

async def call_ollama(prompt):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            if response.status_code == 200:
                return response.json().get("response")
            return None
        except:
            return None

async def get_llm_response(prompt, retries=2, delay=1):
    for i in range(retries):
        try:
            if settings.LLM_PROVIDER == "gemini":
                result = await call_gemini(prompt)
            else:
                result = await call_ollama(prompt)
            if result: return result
        except:
            pass
        await asyncio.sleep(delay)
    return None

async def map_headers_with_llm(user_headers: list) -> dict:
    standard_fields = ["txn_id", "date", "merchant", "amount", "currency", "status", "category", "account_id", "notes"]
    prompt = f"Map these CSV headers to: {standard_fields}. User headers: {user_headers}. Return ONLY JSON mapping."
    response_text = await get_llm_response(prompt)
    if response_text:
        try:
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except: pass
    return {}

async def classify_with_llm(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Quick Cache Lookup (Fastest)
    def fast_categorize(row):
        merchant = str(row.get('merchant', '')).lower()
        for key, cat in MERCHANT_CATEGORY_CACHE.items():
            if key in merchant:
                return cat
        return 'Uncategorised'

    missing_mask = (df['category'] == 'Uncategorised') | (df['category'].isna())
    if not missing_mask.any():
        return df

    # Apply fast categorization first
    df.loc[missing_mask, 'category'] = df[missing_mask].apply(fast_categorize, axis=1)
    
    # 2. Re-check what's still missing
    missing_mask = df['category'] == 'Uncategorised'
    rows_to_classify = df[missing_mask]
    
    if rows_to_classify.empty:
        return df

    # Only classify UNIQUE merchants to save time
    unique_merchants = rows_to_classify['merchant'].unique()[:20] # Batch limited to 20 unique per chunk
    transactions_list = [{"merchant": m} for m in unique_merchants]
    
    prompt = f"""
    Classify these unique merchants into: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, or Other.
    Return ONLY a JSON object like {{"merchant_name": "Category"}}.
    Merchants: {json.dumps(transactions_list)}
    """
    
    response_text = await get_llm_response(prompt)
    if response_text:
        try:
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            new_mappings = json.loads(clean_text)
            
            # Update cache and dataframe
            for merchant_name, category in new_mappings.items():
                MERCHANT_CATEGORY_CACHE[merchant_name.lower()] = category
                # Update all matching rows in this chunk
                df.loc[df['merchant'] == merchant_name, 'category'] = category
                df.loc[df['merchant'] == merchant_name, 'llm_category'] = category
        except Exception as e:
            print(f"Error in batch classification: {e}")
            
    return df

async def generate_narrative_summary(df: pd.DataFrame, summary_stats: dict | None = None) -> dict:
    # Same logic but we use it sparingly (once per job)
    if summary_stats is None:
        if df.empty or not {"currency", "amount", "is_anomaly", "merchant"}.issubset(df.columns):
            summary_stats = {
                "total_spend_inr": 0.0,
                "total_spend_usd": 0.0,
                "anomaly_count": 0,
                "top_merchants": []
            }
        else:
            total_inr = df[df['currency'] == 'INR']['amount'].sum()
            total_usd = df[df['currency'] == 'USD']['amount'].sum()
            anomaly_count = df['is_anomaly'].sum()
            top_merchants_df = df.groupby('merchant')['amount'].sum().sort_values(ascending=False).head(3)
            top_merchants = [{"merchant": m, "amount": float(a)} for m, a in top_merchants_df.items()]

            summary_stats = {
                "total_spend_inr": float(total_inr),
                "total_spend_usd": float(total_usd),
                "anomaly_count": int(anomaly_count),
                "top_merchants": top_merchants
            }
    
    # Narrative prompt...
    prompt = f"Analyze transactions and provide a 2-sentence narrative and risk level (low/medium/high) in JSON. Stats: {json.dumps(summary_stats)}"
    response_text = await get_llm_response(prompt)
    if response_text:
        try:
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_text)
            return {**summary_stats, **result}
        except: pass
    return {**summary_stats, "narrative": "Summary generated.", "risk_level": "low"}
