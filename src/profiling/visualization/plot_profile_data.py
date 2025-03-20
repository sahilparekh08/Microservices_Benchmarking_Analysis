"""
Plot profile data from CSV files.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import numpy as np
from typing import Dict, List, Tuple

def calculate_percentiles(df: pd.DataFrame, column: str) -> Tuple[float, float, float]:
    """
    Calculate 25th, 75th, and 99th percentiles for a column.
    
    Args:
        df: DataFrame containing the data
        column: Column name to calculate percentiles for
        
    Returns:
        Tuple of (p25, p75, p99) percentiles
    """
    data = df[column].astype(float)
    data = data.replace(0, np.nan)
    data = data.dropna()
    
    p25 = float(np.percentile(data, 25))
    p75 = float(np.percentile(data, 75))
    p99 = float(np.percentile(data, 99))
    
    return p25, p75, p99

def aggregate_llc_data(dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Aggregate LLC data across all cores.
    
    Args:
        dfs: Dict of DataFrames containing performance data for each core
        
    Returns:
        DataFrame containing aggregated LLC data
    """
    # Create a copy of the first DataFrame for the aggregated data
    agg_df = pd.DataFrame()
    
    # Sum LLC loads and misses across all cores
    agg_df['LLC-loads'] = sum(df['LLC-loads'] for df in dfs.values())
    agg_df['LLC-misses'] = sum(df['LLC-misses'] for df in dfs.values())
    
    # Recalculate LLC miss rate
    agg_df['LLC-miss-rate'] = agg_df['LLC-misses'] / agg_df['LLC-loads']
    
    return agg_df

def plot_llc_data(agg_df: pd.DataFrame, output_file: str, test_name: str, container_name: str, config: str) -> bool:
    """
    Plot aggregated LLC data with percentile lines.
    
    Args:
        agg_df: DataFrame containing aggregated LLC data
        output_file: Path to save the plot
        test_name: Name of the test
        container_name: Name of the container
        config: Test configuration
        
    Returns:
        bool: True if plotting was successful, False otherwise
    """
    try:
        # Calculate percentiles
        loads_p25, loads_p75, loads_p99 = calculate_percentiles(agg_df, 'LLC-loads')
        misses_p25, misses_p75, misses_p99 = calculate_percentiles(agg_df, 'LLC-misses')
        miss_rate_p25, miss_rate_p75, miss_rate_p99 = calculate_percentiles(agg_df, 'LLC-miss-rate')
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        fig.suptitle(f'LLC Performance Analysis\n{test_name} - {container_name} - {config}')
        
        # Plot LLC loads and misses with percentiles
        ax1.plot(agg_df['Time'], agg_df['LLC-loads'], label='LLC Loads', color='blue')
        ax1.axhline(loads_p25, color='blue', linestyle=':', alpha=0.5, label='Loads 25th')
        ax1.axhline(loads_p75, color='blue', linestyle=':', alpha=0.5, label='Loads 75th')
        ax1.axhline(loads_p99, color='blue', linestyle=':', alpha=0.5, label='Loads 99th')
        
        ax1.plot(agg_df['Time'], agg_df['LLC-misses'], label='LLC Misses', color='red')
        ax1.axhline(misses_p25, color='red', linestyle=':', alpha=0.5, label='Misses 25th')
        ax1.axhline(misses_p75, color='red', linestyle=':', alpha=0.5, label='Misses 75th')
        ax1.axhline(misses_p99, color='red', linestyle=':', alpha=0.5, label='Misses 99th')
        
        ax1.set_xlabel('Time (μs)')
        ax1.set_ylabel('Count')
        ax1.set_title('Total LLC Loads and Misses')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True)
        
        # Plot LLC miss rate with percentiles
        ax2.plot(agg_df['Time'], agg_df['LLC-miss-rate'], label='LLC Miss Rate', color='green')
        ax2.axhline(miss_rate_p25, color='green', linestyle=':', alpha=0.5, label='Miss Rate 25th')
        ax2.axhline(miss_rate_p75, color='green', linestyle=':', alpha=0.5, label='Miss Rate 75th')
        ax2.axhline(miss_rate_p99, color='green', linestyle=':', alpha=0.5, label='Miss Rate 99th')
        
        ax2.set_xlabel('Time (μs)')
        ax2.set_ylabel('Rate')
        ax2.set_title('Overall LLC Miss Rate')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax2.grid(True)
        
        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(output_file, bbox_inches='tight')
        plt.close()
        return True
    except Exception as e:
        print(f"Error creating LLC plot: {str(e)}")
        return False

def plot_core_instructions(dfs: Dict[pd.DataFrame], output_file: str, test_name: str, container_name: str, config: str) -> bool:
    """
    Plot instructions per core with percentile lines.
    
    Args:
        dfs: Dict of DataFrames containing performance data for each core
        output_file: Path to save the plot
        test_name: Name of the test
        container_name: Name of the container
        config: Test configuration
        
    Returns:
        bool: True if plotting was successful, False otherwise
    """
    try:
        plt.figure(figsize=(12, 6))
        plt.title(f'Instructions per Core\n{test_name} - {container_name} - {config}')
        
        # Plot instructions for each core with percentiles
        i: int = 0
        for core_no, df in dfs.items():
            color = plt.cm.viridis(i / len(dfs))  # Use different colors for each core
            p25, p75, p99 = calculate_percentiles(df, 'Instructions')
            
            plt.plot(df['Time'], df['Instructions'], label=f'Core {core_no}', color=color, alpha=0.7)
            plt.axhline(p25, color=color, linestyle=':', alpha=0.5, label=f'Core {core_no} 25th')
            plt.axhline(p75, color=color, linestyle=':', alpha=0.5, label=f'Core {core_no} 75th')
            plt.axhline(p99, color=color, linestyle=':', alpha=0.5, label=f'Core {core_no} 99th')
        
            i += 1
        
        plt.xlabel('Time (μs)')
        plt.ylabel('Instructions')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True)
        
        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(output_file, bbox_inches='tight')
        plt.close()
        return True
    except Exception as e:
        print(f"Error creating instructions plot: {str(e)}")
        return False

def process_files(input_dir: str, plot_dir: str, test_name: str, container_name: str, config: str) -> bool:
    """
    Process all input files and create corresponding plots.
    
    Args:
        input_dir: Directory containing input CSV files
        plot_dir: Directory to store the plots
        test_name: Name of the test
        container_name: Name of the container
        config: Test configuration
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    try:
        # Read all CSV files
        dfs = {}
        for input_file in os.listdir(input_dir):
            if input_file.endswith('.csv'):
                input_splits = input_file.split('_')
                core_no = input_splits[len(input_splits) - 1]
                input_path = os.path.join(input_dir, input_file)
                df = pd.read_csv(input_path)
                dfs[core_no] = df
        
        if not dfs:
            print(f"No CSV files found in {input_dir}")
            return False
        
        # Create aggregated LLC plot
        agg_df = aggregate_llc_data(dfs)
        llc_plot_file = os.path.join(plot_dir, f"{test_name}_{container_name}_{config}_llc_performance.png")
        if not plot_llc_data(agg_df, llc_plot_file, test_name, container_name, config):
            return False
        
        # Create per-core instructions plot
        instructions_plot_file = os.path.join(plot_dir, f"{test_name}_{container_name}_{config}_core_instructions.png")
        if not plot_core_instructions(dfs, instructions_plot_file, test_name, container_name, config):
            return False
        
        return True
    except Exception as e:
        print(f"Error processing files: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Plot profiling data from CSV files')
    parser.add_argument('--test-name', type=str, required=True, help='Name of the test')
    parser.add_argument('--container-name', type=str, required=True, help='Name of the container')
    parser.add_argument('--config', type=str, required=True, help='Test configuration')
    parser.add_argument('--data-dir', type=str, required=True, help='Directory containing CSV files')
    parser.add_argument('--plot-dir', type=str, required=True, help='Directory to save plots')
    args = parser.parse_args()

    test_name: str = args.test_name.replace(" ", "_")
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    plot_dir: str = args.plot_dir

    if process_files(data_dir, plot_dir, test_name, container_name, config):
        print(f"\nSuccessfully created plots in {plot_dir}:")
        print(f"- {test_name}_{container_name}_{config}_llc_performance.png (Aggregated LLC data across all cores)")
        print(f"- {test_name}_{container_name}_{config}_core_instructions.png (Instructions per core)")
    else:
        print("\nFailed to create plots")

if __name__ == '__main__':
    main()