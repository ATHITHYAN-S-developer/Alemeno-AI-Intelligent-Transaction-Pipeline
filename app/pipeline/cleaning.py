import pandas as pd
import numpy as np
from datetime import datetime
import re

def clean_transaction_data(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Remove exact duplicate rows
    df = df.drop_duplicates().copy()
    
    # Ensure essential columns exist (even if empty)
    for col in ['date', 'merchant', 'amount']:
        if col not in df.columns:
            df[col] = None
            
    # Default values for secondary columns
    if 'status' not in df.columns:
        df['status'] = 'SUCCESS'
    else:
        df['status'] = df['status'].fillna('SUCCESS').str.upper()
        
    if 'currency' not in df.columns:
        df['currency'] = 'INR'
    else:
        df['currency'] = df['currency'].fillna('INR').str.upper()
        
    if 'account_id' not in df.columns:
        df['account_id'] = 'DEFAULT_ACC'
    else:
        df['account_id'] = df['account_id'].fillna('DEFAULT_ACC')

    # 2. Clean Amount: strip currency symbols and convert to float
    def clean_amount(val):
        if pd.isna(val) or val == '':
            return 0.0
        if isinstance(val, str):
            val = re.sub(r'[$₹,]|INR|Rs\.?|rupees?', '', val, flags=re.IGNORECASE).strip()
            try:
                # Handle cases with multiple decimal points or weird characters
                return float(val)
            except ValueError:
                return 0.0
        return float(val)
    
    df['amount'] = df['amount'].apply(clean_amount)
    
    # 3. Fill missing categories
    if 'category' not in df.columns:
        df['category'] = 'Uncategorised'
    else:
        df['category'] = df['category'].fillna('Uncategorised')
        df.loc[df['category'] == '', 'category'] = 'Uncategorised'
    
    # 4. Normalize dates to ISO 8601
    def parse_date(date_str):
        if pd.isna(date_str) or date_str == '':
            return None
        formats = ['%d-%m-%Y', '%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue
        try:
            # Fallback for pandas default parsing
            return pd.to_datetime(date_str).to_pydatetime()
        except:
            return None

    df['date_iso'] = df['date'].apply(parse_date)
    
    return df
