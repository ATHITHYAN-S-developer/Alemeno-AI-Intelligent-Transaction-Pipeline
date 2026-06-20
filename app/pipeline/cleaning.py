import pandas as pd
import numpy as np
from datetime import datetime

def clean_transaction_data(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Remove exact duplicate rows
    df = df.drop_duplicates().copy()
    
    # 2. Normalize status to Uppercase
    if 'status' in df.columns:
        df['status'] = df['status'].str.upper()
    
    # 3. Clean Amount: strip currency symbols and convert to float
    def clean_amount(val):
        if pd.isna(val):
            return 0.0
        if isinstance(val, str):
            val = val.replace('$', '').replace(',', '').strip()
            try:
                return float(val)
            except ValueError:
                return 0.0
        return float(val)
    
    df['amount'] = df['amount'].apply(clean_amount)
    
    # 4. Fill missing categories
    if 'category' in df.columns:
        df['category'] = df['category'].fillna('Uncategorised')
        df.loc[df['category'] == '', 'category'] = 'Uncategorised'
    
    # 5. Normalize dates to ISO 8601
    def parse_date(date_str):
        if pd.isna(date_str):
            return None
        formats = ['%d-%m-%Y', '%Y/%m/%d', '%Y-%m-%d']
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
        return None

    df['date_iso'] = df['date'].apply(parse_date)
    # Ensure all dates are strings for the response, but we keep date_iso for logic
    
    # 6. Normalize currency
    if 'currency' in df.columns:
        df['currency'] = df['currency'].str.upper()
        
    return df
