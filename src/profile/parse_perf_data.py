import pandas as pd
import argparse

def convert_perf_csv(input_file: str, output_file: str) -> None:
    df: pd.DataFrame = pd.read_csv(input_file)
    
    pivot_df: pd.DataFrame = df.pivot_table(index='Time', columns='Type', values='Frequency', aggfunc='first')
    pivot_df = pivot_df.reset_index()
    
    result_df: pd.DataFrame = pd.DataFrame()
    result_df['Time'] = pivot_df['Time']
    result_df['LLC-loads'] = pivot_df.get('LOAD', pd.Series([0] * len(pivot_df)))
    result_df['LLC-misses'] = pivot_df.get('MISS', pd.Series([0] * len(pivot_df)))
    result_df['Instructions'] = pivot_df.get('INSTRUCTIONS', pd.Series([0] * len(pivot_df)))

    result_df = result_df.fillna(0)

    result_df['LLC-loads'] = result_df['LLC-loads'].astype(int)
    result_df['LLC-misses'] = result_df['LLC-misses'].astype(int)
    result_df['Instructions'] = result_df['Instructions'].astype(int)
    
    result_df.to_csv(output_file, index=False)
    print(f"Converted file saved to {output_file}")

if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='Convert perf CSV format to DataFrame with specific columns')
    parser.add_argument('--input-file', type=str, help='Path to the input CSV file')
    parser.add_argument('--output-file', type=str, help='Path to save the output CSV file')
    
    args: argparse.Namespace = parser.parse_args()
    
    convert_perf_csv(args.input_file, args.output_file)
