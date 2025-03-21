import os
from typing import Dict
import pandas as pd
import numpy as np

def load_profile_data(data_dir: str) -> Dict[str, pd.DataFrame]:
    cores_to_perf_df: Dict[str, pd.DataFrame] = {}
    for file in os.listdir(data_dir):
        if file.endswith(".csv"):
            core: str = file.split("_")[-1].split(".")[0]
            perf_df: pd.DataFrame = pd.read_csv(f"{data_dir}/{file}", sep=",")
            cores_to_perf_df[core] = perf_df
    return cores_to_perf_df

def get_processed_df(df: pd.DataFrame, column: str, to_normalise: bool) -> pd.DataFrame:
    data: pd.DataFrame = df[["Time", column]].copy()
    data[column] = data[column].astype(int)
    data['Time'] = data['Time'].astype(int)
    data = data.sort_values(by="Time")
    if to_normalise:
        data['Yime'] = data['Time'] - data['Time'].min()
    return data