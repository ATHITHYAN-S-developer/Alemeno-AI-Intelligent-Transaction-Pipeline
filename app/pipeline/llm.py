import google.generativeai as genai
import pandas as pd
import json
import asyncio
from app.config import settings
import time

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

async def call_gemini_with_retry(prompt, retries=3, delay=2):
    if not model:
        return None
    
    for i in range(retries):
        try:
            # Using run_in_executor since genai is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            return response.text
        except Exception as e:
            if i == retries - 1:
                print(f"LLM call failed after {retries} attempts: {e}")
                return None
            await asyncio.sleep(delay * (2 ** i)) # Exponential backoff
    return None

async def classify_with_llm(df: pd.DataFrame) -> pd.DataFrame:
    # Find rows with 'Uncategorised'
    missing_mask = df['category'] == 'Uncategorised'
    rows_to_classify = df[missing_mask]
    
    if rows_to_classify.empty or not model:
        return df

    # Prepare batch prompt
    transactions_list = []
    for idx, row in rows_to_classify.iterrows():
        transactions_list.append({
            "temp_id": idx,
            "merchant": row['merchant'],
            "notes": row['notes'] if pd.notnull(row['notes']) else ""
        })
    
    prompt = f"""
    Classify the following financial transactions into one of these categories: 
    Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, or Other.
    Return ONLY a JSON list of objects with "temp_id" and "category".
    
    Transactions:
    {json.dumps(transactions_list)}
    """
    
    response_text = await call_gemini_with_retry(prompt)
    if response_text:
        try:
            # Clean response text (sometimes Gemini returns markdown)
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            classifications = json.loads(clean_text)
            for item in classifications:
                idx = item.get('temp_id')
                category = item.get('category')
                if idx in df.index:
                    df.at[idx, 'category'] = category
                    df.at[idx, 'llm_category'] = category
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            df.loc[missing_mask, 'llm_failed'] = True
    else:
        df.loc[missing_mask, 'llm_failed'] = True
            
    return df

async def generate_narrative_summary(df: pd.DataFrame) -> dict:
    # Calculate stats
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
    
    if not model:
        return {**summary_stats, "narrative": "LLM not configured", "risk_level": "low"}
    
    # Prepare data for LLM narrative
    txns_summary = df[['merchant', 'amount', 'currency', 'category', 'is_anomaly', 'anomaly_reason']].to_dict(orient='records')
    
    prompt = f"""
    Analyze these transactions and provide a 2-3 sentence spending narrative and a risk level (low, medium, or high).
    Return ONLY a JSON object with "narrative" and "risk_level".
    
    Stats: {json.dumps(summary_stats)}
    Transactions: {json.dumps(txns_summary[:50])} (truncated to 50)
    """
    
    response_text = await call_gemini_with_retry(prompt)
    if response_text:
        try:
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_text)
            return {**summary_stats, **result}
        except:
            pass
            
    return {**summary_stats, "narrative": "Failed to generate narrative", "risk_level": "medium" if anomaly_count > 0 else "low"}
