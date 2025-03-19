"""
Functions for loading trace and performance data.
"""

import os
import pandas as pd
from typing import Dict, Any
from .constants import DEFAULT_SERVICE_NAME

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    """Load traces data from CSV file."""
    jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data", 
                                                    f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    if not os.path.exists(jaeger_traces_csv_file_path):
        jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data", 
                                                    f"{DEFAULT_SERVICE_NAME}_{test_name}_{config}_traces_data.csv")

    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def load_perf_data(data_dir: str) -> pd.DataFrame:
    """Load performance data from CSV file."""
    llc_data_file: str = f"{data_dir}/data/profile_data.csv"
    df: pd.DataFrame = pd.read_csv(llc_data_file, sep=",")
    return df 