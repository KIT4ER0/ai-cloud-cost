import logging
import time
from datetime import datetime, date

logger = logging.getLogger(__name__)

# =====================================================================
# CONFIGURATION VARIABLES - TO BE REPLACED AFTER CLOUDFORMATION SETUP
# =====================================================================
# The database and table names are defined when you run the AWS-provided CloudFormation template for the CUR report.
ATHENA_DATABASE_NAME = "athenacurcfn_ai_cloud_cost_report"
ATHENA_TABLE_NAME = "ai_cloud_cost_report"
# The S3 bucket where Athena should store query result files. Must exist in your account.
ATHENA_OUTPUT_LOCATION = "s3://YOUR-ATHENA-RESULTS-BUCKET-NAME/results/"
# =====================================================================

def query_athena_cur_data(client, start_date_str: str, end_date_str: str):
    """
    Submits an Athena query to retrieve AWS CUR data grouped by resource ID and usage type.
    
    Args:
        client: A boto3 Athena client (passed from the assumed session).
        start_date_str: e.g. "2023-10-01"
        end_date_str: e.g. "2023-10-31"
        
    Returns:
        List of dictionaries containing parsed cost rows.
    """
    logger.info(f"Submitting Athena Query for CUR data between {start_date_str} and {end_date_str}")
    
    # We query specific services to map them directly to our PostgesSQL models
    query = f"""
        SELECT 
            line_item_usage_start_date AS usage_date,
            line_item_product_code AS service_name,
            line_item_usage_type AS usage_type,
            line_item_resource_id AS resource_id,
            SUM(line_item_unblended_cost) AS total_cost
        FROM {ATHENA_DATABASE_NAME}.{ATHENA_TABLE_NAME}
        WHERE line_item_usage_start_date >= TIMESTAMP '{start_date_str}'
          AND line_item_usage_start_date < TIMESTAMP '{end_date_str}'
          AND line_item_resource_id != ''
          AND line_item_product_code IN ('AmazonEC2', 'AmazonRDS', 'AWSLambda', 'AmazonS3', 'AWSELB')
        GROUP BY 1, 2, 3, 4
    """

    try:
        response = client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': ATHENA_DATABASE_NAME},
            ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
        )
    except Exception as e:
        logger.error(f"Failed to submit Athena query: {e}")
        raise e
        
    execution_id = response['QueryExecutionId']
    logger.info(f"Athena query started with Execution ID: {execution_id}")
    
    # -----------------------------------------------------
    # Polling for Query Completion
    # -----------------------------------------------------
    state = 'RUNNING'
    max_retries = 100 # Adjust timeout as needed (100 * 3s = 5 mins)
    retries = 0
    
    while state in ['QUEUED', 'RUNNING'] and retries < max_retries:
        status_response = client.get_query_execution(QueryExecutionId=execution_id)
        state = status_response['QueryExecution']['Status']['State']
        
        if state in ['FAILED', 'CANCELLED']:
            reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown Error')
            logger.error(f"Athena query {execution_id} failed: {reason}")
            raise RuntimeError(f"Athena query {state}: {reason}")
            
        if state == 'SUCCEEDED':
            logger.info(f"Athena query {execution_id} SUCCEEDED.")
            break
            
        time.sleep(3)
        retries += 1
        
    if state != 'SUCCEEDED':
         raise TimeoutError(f"Athena query polling timed out. Last state: {state}")
         
    # -----------------------------------------------------
    # Fetching Paginated Results
    # -----------------------------------------------------
    return _fetch_paginated_results(client, execution_id)
    
def _fetch_paginated_results(client, execution_id: str):
    """
    Retrieves and parses the results from an Athena query.
    Handles pagination for large datasets.
    """
    logger.info("Fetching Athena query results...")
    parsed_results = []
    
    has_next = True
    next_token = None
    
    # The first row of the first page is always the header
    header_skipped = False 
    
    while has_next:
        kwargs = {'QueryExecutionId': execution_id, 'MaxResults': 1000}
        if next_token:
            kwargs['NextToken'] = next_token
            
        page = client.get_query_results(**kwargs)
        
        rows = page['ResultSet']['Rows']
        
        for idx, row in enumerate(rows):
            if not header_skipped and idx == 0:
                header_skipped = True
                continue # Skip header row
                
            data = row['Data']
            
            # Helper to extract varchar safely
            def get_val(item):
                return item.get('VarCharValue', '')
            
            try:    
                row_data = {
                    "usage_date": get_val(data[0]),
                    "service_name": get_val(data[1]),
                    "usage_type": get_val(data[2]),
                    "resource_id": get_val(data[3]),
                    "cost": float(get_val(data[4]) or 0.0)
                }
                parsed_results.append(row_data)
            except Exception as e:
                logger.warning(f"Error parsing row: {data} -> {e}")
                
        next_token = page.get('NextToken')
        has_next = next_token is not None
        
    logger.info(f"Fetched {len(parsed_results)} cost rows from Athena.")
    return parsed_results
