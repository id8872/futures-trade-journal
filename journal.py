import pandas as pd
import matplotlib.pyplot as plt
import glob
import os


def load_and_process_trades(csv_folder):
    # Load all CSV files from folder
    all_files = glob.glob(os.path.join(csv_folder, '*.csv'))
    df_list = []

    for file in all_files:
        df = pd.read_csv(file)
        df_list.append(df)

    df_all = pd.concat(df_list, ignore_index=True)

    # Clean numeric columns
    df_all['Profit'] = df_all['Profit'].replace(
        {'\\$': '', ',': ''}, regex=True).astype(float)
    df_all['Cum. net profit'] = df_all['Cum. net profit'].replace(
        {'\\$': '', ',': ''}, regex=True).astype(float)
    df_all['Exit time'] = pd.to_datetime(df_all['Exit time'])

    return df_all


def calculate_summary(df):
    total_trades = len(df)
    winning_trades = len(df[df['Profit'] > 0])
    losing_trades = len(df[df['Profit'] <= 0])
    total_profit = df['Profit'].sum()
    avg_profit = df['Profit'].mean()
    net_profit = df['Cum. net profit'].iloc[-1] if not df.empty else 0

    summary = {
        'Total trades': total_trades,
        'Winning trades': winning_trades,
        'Losing trades': losing_trades,
        'Total profit': total_profit,
        'Average profit': avg_profit,
        'Net profit': net_profit
    }
    return summary


def plot_cumulative_profit(df):
    plt.figure(figsize=(10, 6))
    plt.plot(df['Exit time'], df['Cum. net profit'], marker='o', linestyle='-')
    plt.title('Cumulative Net Profit Over Time')
    plt.xlabel('Exit Time')
    plt.ylabel('Cumulative Net Profit')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('cumulative_net_profit.png')
    plt.show()


def save_summary(summary):
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv('trade_summary.csv', index=False)


def main():
    csv_folder = r'D:\futures_xml\journal'  # Use raw string for Windows path
    trades_df = load_and_process_trades(csv_folder)
    summary = calculate_summary(trades_df)
    print("Summary Statistics:")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: ${value:.2f}")
        else:
            print(f"{key}: {value}")
    plot_cumulative_profit(trades_df)
    save_summary(summary)


if __name__ == "__main__":
    main()
