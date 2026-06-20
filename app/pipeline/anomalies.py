import pandas as pd

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df['is_anomaly'] = False
    df['anomaly_reason'] = None
    
    # 1. Flag if amount > 3x the account's median
    # We group by account_id and calculate median
    medians = df.groupby('account_id')['amount'].transform('median')
    median_outliers = df['amount'] > (3 * medians)
    
    df.loc[median_outliers, 'is_anomaly'] = True
    df.loc[median_outliers, 'anomaly_reason'] = "Amount exceeds 3x account median"
    
    # 2. Flag if currency is USD but merchant is domestic-only
    domestic_merchants = ['Swiggy', 'Ola', 'IRCTC', 'Zomato', 'Flipkart', 'Jio Recharge']
    domestic_anomalies = (df['currency'] == 'USD') & (df['merchant'].isin(domestic_merchants))
    
    df.loc[domestic_anomalies, 'is_anomaly'] = True
    # Append to existing reason if any
    mask = domestic_anomalies
    df.loc[mask, 'anomaly_reason'] = df.loc[mask, 'anomaly_reason'].apply(
        lambda x: (x + "; " if x else "") + "USD used for domestic merchant"
    )
    
    return df
