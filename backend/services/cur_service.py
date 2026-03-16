import boto3
import pandas as pd
import os
import tempfile
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# =====================================================================
# CONFIGURATION VARIABLES
# =====================================================================
# Replace this with the S3 bucket where you chose to deliver the raw Parquet CUR files
RAW_CUR_BUCKET = "cur-demo-cloudcost"
RAW_CUR_PREFIX = "raw-reports/"
# =====================================================================

def download_latest_cur_files(client, bucket: str, prefix: str, download_dir: str) -> List[str]:
    """
    Finds the latest .parquet files in the given S3 bucket prefix and downloads them.
    """
    logger.info(f"Scanning S3 bucket {bucket} with prefix {prefix} for Parquet files...")
    paginator = client.get_paginator('list_objects_v2')
    
    parquet_files = []
    
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                if key.endswith('.parquet'):
                    parquet_files.append(key)
    except Exception as e:
        logger.error(f"Failed to scan S3 for Parquet files: {e}")
        return []
                
    if not parquet_files:
        logger.warning(f"No Parquet files found in the specified S3 path (s3://{bucket}/{prefix}).")
        return []
        
    downloaded_paths = []
    # Download them to /tmp/
    for key in parquet_files:
        filename = os.path.basename(key)
        local_path = os.path.join(download_dir, filename)
        logger.info(f"Downloading {key} to {local_path}...")
        try:
            client.download_file(bucket, key, local_path)
            downloaded_paths.append(local_path)
        except Exception as e:
            logger.error(f"Failed to download {key}: {e}")
            
    return downloaded_paths

def fetch_cur_data_pandas(customer_session: boto3.Session, start_date_str: str, end_date_str: str) -> List[Dict]:
    """
    Downloads CUR parquet files, parses them with Pandas, groups by resource ID, and returns exact format as Athena.
    """
    logger.info(f"Starting Pandas CUR processing between {start_date_str} and {end_date_str}")
    s3_client = customer_session.client('s3')
    
    parsed_results = []
    
    # Create a temporary directory that automatically cleans up
    with tempfile.TemporaryDirectory() as temp_dir:
        local_files = download_latest_cur_files(s3_client, RAW_CUR_BUCKET, RAW_CUR_PREFIX, temp_dir)
        
        if not local_files:
            return []
            
        logger.info("Loading Parquet files into Pandas DataFrame...")
        
        # Load all downloaded parquet files into pandas DataFrame
        df_list = []
        for file in local_files:
            try:
                # We only need specific columns to save RAM. Using fastparquet.
                df = pd.read_parquet(file, columns=[
                    'line_item_usage_start_date',
                    'line_item_product_code',
                    'line_item_usage_type',
                    'line_item_resource_id',
                    'line_item_unblended_cost'
                ], engine='fastparquet')
                df_list.append(df)
            except Exception as e:
                logger.error(f"Failed to read parquet file {file}: {e}")
                
        if not df_list:
            logger.warning("No valid DataFrame could be parsed from downloaded files.")
            return []
            
        # Combine all files into a single master memory buffer
        master_df = pd.concat(df_list, ignore_index=True)
        
        # Filter by date and specific AWS services
        master_df['line_item_usage_start_date'] = pd.to_datetime(master_df['line_item_usage_start_date'], utc=True)
        
        start_date = pd.to_datetime(start_date_str, utc=True)
        end_date = pd.to_datetime(end_date_str, utc=True)
        
        # Filter dataframe for speed
        mask = (master_df['line_item_usage_start_date'] >= start_date) & \
               (master_df['line_item_usage_start_date'] < end_date) & \
               (master_df['line_item_resource_id'] != "") & \
               (master_df['line_item_product_code'].isin(['AmazonEC2', 'AmazonRDS', 'AWSLambda', 'AmazonS3', 'AWSELB']))
               
        filtered_df = master_df.loc[mask].copy()
        
        if filtered_df.empty:
            logger.info("No matching records found after filtering by date and services.")
            return []
            
        # Normalize the date to string YYYY-MM-DD
        filtered_df['usage_date'] = filtered_df['line_item_usage_start_date'].dt.strftime('%Y-%m-%d')
        filtered_df['line_item_unblended_cost'] = pd.to_numeric(filtered_df['line_item_unblended_cost'], errors='coerce').fillna(0)
        
        # Group by Date, Service, UsageType, ResourceId (Equivalent to SQL GROUP BY)
        grouped = filtered_df.groupby([
            'usage_date',
            'line_item_product_code',
            'line_item_usage_type',
            'line_item_resource_id'
        ])['line_item_unblended_cost'].sum().reset_index()
        
        # Convert to list of dicts for exact parity with previous Athena output
        for _, row in grouped.iterrows():
            cost = row['line_item_unblended_cost']
            if cost > 0:
                parsed_results.append({
                    "usage_date": row['usage_date'],
                    "service_name": row['line_item_product_code'],
                    "usage_type": row['line_item_usage_type'],
                    "resource_id": row['line_item_resource_id'],
                    "cost": float(cost)
                })
        
        logger.info(f"Successfully processed {len(parsed_results)} aggregated cost rows from Pandas.")
        
    # temp_dir and its contents are automatically deleted here
    return parsed_results
