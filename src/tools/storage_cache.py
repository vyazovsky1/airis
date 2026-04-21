import csv
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

def init_cache():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
def save_to_cache(cache_file: str, headers: list, row_data: dict):
    """Saves metrics or findings to a local CSV file."""
    init_cache()
    file_path = os.path.join(DATA_DIR, cache_file)
    write_headers = not os.path.exists(file_path)
    
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if write_headers:
            writer.writeheader()
        
        # Add timestamp
        if "timestamp" not in row_data:
            row_data["timestamp"] = datetime.datetime.now().isoformat()
            
        # Ensure only expected headers are written
        clean_row = {k: v for k, v in row_data.items() if k in headers}
        writer.writerow(clean_row)
