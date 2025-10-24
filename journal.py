from datetime import datetime
import os
import matplotlib.pyplot as plt
from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for server

app = Flask(__name__)

UPLOAD_FOLDER = 'data'
CHART_FOLDER = 'static'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)


def parse_all_csv(folder):
    """Load and combine all CSV files from folder"""
    df_list = []
    for f in os.listdir(folder):
        if f.endswith('.csv'):
            try:
                df = pd.read_csv(os.path.join(folder, f))
                df_list.append(df)
            except Exception as e:
                print(f"Error loading {f}: {e}")

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
        # Clean numeric columns
        for col in ['Profit', 'Cum. net profit', 'Entry price', 'Exit price', 'Qty', 'MAE', 'MFE']:
            if col in df.columns:
                df[col] = df[col].replace({'\$': '', ',': ''}, regex=True)
                try:
                    df[col] = pd.to_numeric(df[col])
                except:
                    pass

        if 'Exit time' in df.columns:
            df['Exit time'] = pd.to_datetime(df['Exit time'])
        if 'Entry time' in df.columns:
            df['Entry time'] = pd.to_datetime(df['Entry time'])

        return df
    return pd.DataFrame()


def get_account_list(df):
    """Get list of unique accounts"""
    if df.empty or 'Account' not in df.columns:
        return []
    return sorted(df['Account'].unique().tolist())


def filter_by_account(df, account):
    """Filter dataframe by account"""
    if not account or account == 'all':
        return df
    if 'Account' in df.columns:
        return df[df['Account'] == account]
    return df


def calculate_stats(df):
    """Calculate comprehensive trading statistics"""
    if df.empty or 'Profit' not in df.columns:
        return None

    wins = df[df['Profit'] > 0]
    losses = df[df['Profit'] < 0]

    stats = {
        'total_trades': len(df),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'break_even': len(df[df['Profit'] == 0]),
        'win_rate': f"{(len(wins) / len(df) * 100):.1f}%" if len(df) > 0 else "0%",
        'total_profit': f"${df['Profit'].sum():.2f}",
        'avg_profit': f"${df['Profit'].mean():.2f}",
        'avg_win': f"${wins['Profit'].mean():.2f}" if len(wins) > 0 else "$0.00",
        'avg_loss': f"${losses['Profit'].mean():.2f}" if len(losses) > 0 else "$0.00",
        'largest_win': f"${df['Profit'].max():.2f}",
        'largest_loss': f"${df['Profit'].min():.2f}",
        'net_profit': f"${df['Cum. net profit'].iloc[-1]:.2f}" if 'Cum. net profit' in df.columns and len(df) > 0 else "$0.00",
    }

    # Risk/Reward Ratio
    if len(wins) > 0 and len(losses) > 0:
        avg_win = wins['Profit'].mean()
        avg_loss = abs(losses['Profit'].mean())
        stats['risk_reward'] = f"{avg_win / avg_loss:.2f}" if avg_loss != 0 else "N/A"
    else:
        stats['risk_reward'] = "N/A"

    # Expectancy
    prob_win = len(wins) / len(df) if len(df) > 0 else 0
    prob_loss = len(losses) / len(df) if len(df) > 0 else 0
    avg_win = wins['Profit'].mean() if len(wins) > 0 else 0
    avg_loss = losses['Profit'].mean() if len(losses) > 0 else 0
    expectancy = (prob_win * avg_win) + (prob_loss * avg_loss)
    stats['expectancy'] = f"${expectancy:.2f}"

    return stats


def get_strategy_stats(df):
    """Get stats grouped by strategy"""
    if df.empty or 'Strategy' not in df.columns:
        return {}

    strategies = {}
    for strategy in df['Strategy'].unique():
        strat_df = df[df['Strategy'] == strategy]
        wins = len(strat_df[strat_df['Profit'] > 0])
        total = len(strat_df)
        strategies[strategy] = {
            'trades': total,
            'wins': wins,
            'win_rate': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            'profit': f"${strat_df['Profit'].sum():.2f}"
        }
    return strategies


def get_account_comparison(df):
    """Compare performance across accounts"""
    if df.empty or 'Account' not in df.columns:
        return {}

    accounts = {}
    for account in df['Account'].unique():
        acc_df = df[df['Account'] == account]
        wins = len(acc_df[acc_df['Profit'] > 0])
        total = len(acc_df)
        accounts[account] = {
            'trades': total,
            'wins': wins,
            'win_rate': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            'profit': f"${acc_df['Profit'].sum():.2f}",
            'net_profit': f"${acc_df['Cum. net profit'].iloc[-1]:.2f}" if 'Cum. net profit' in acc_df.columns and len(acc_df) > 0 else "$0.00"
        }
    return accounts


def create_charts(df, account_filter='all'):
    """Generate all trading charts"""
    if df.empty:
        return {}

    charts = {}

    # 1. Cumulative Profit Curve
    if 'Exit time' in df.columns and 'Cum. net profit' in df.columns:
        plt.figure(figsize=(12, 5))
        plt.plot(df['Exit time'], df['Cum. net profit'], marker='o',
                 linestyle='-', linewidth=2, color='#007bff')
        title = 'Cumulative Net Profit Over Time'
        if account_filter != 'all':
            title += f' - {account_filter}'
        plt.title(title, fontsize=14, fontweight='bold')
        plt.xlabel('Exit Time')
        plt.ylabel('Cumulative Profit ($)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'profit_curve.png'), dpi=100)
        plt.close()
        charts['profit_curve'] = 'profit_curve.png'

    # 2. Win/Loss Distribution
    if 'Profit' in df.columns:
        plt.figure(figsize=(10, 5))
        wins = len(df[df['Profit'] > 0])
        losses = len(df[df['Profit'] < 0])
        break_even = len(df[df['Profit'] == 0])
        plt.bar(['Wins', 'Losses', 'Break Even'], [wins, losses, break_even],
                color=['#38ef7d', '#f45c43', '#999'])
        plt.title('Trade Outcomes', fontsize=14, fontweight='bold')
        plt.ylabel('Number of Trades')
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'win_loss.png'), dpi=100)
        plt.close()
        charts['win_loss'] = 'win_loss.png'

    # 3. Profit Distribution (Histogram)
    if 'Profit' in df.columns:
        plt.figure(figsize=(10, 5))
        plt.hist(df['Profit'], bins=15, color='steelblue', edgecolor='black')
        plt.title('Profit Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Profit ($)')
        plt.ylabel('Frequency')
        plt.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'profit_dist.png'), dpi=100)
        plt.close()
        charts['profit_dist'] = 'profit_dist.png'

    # 4. Strategy Performance
    if 'Strategy' in df.columns and 'Profit' in df.columns:
        strategy_prof = df.groupby('Strategy')['Profit'].sum().sort_values()
        plt.figure(figsize=(10, 5))
        colors = ['#38ef7d' if x >
                  0 else '#f45c43' for x in strategy_prof.values]
        strategy_prof.plot(kind='barh', color=colors)
        plt.title('Profit by Strategy', fontsize=14, fontweight='bold')
        plt.xlabel('Total Profit ($)')
        plt.axvline(0, color='black', linewidth=0.8)
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'strategy_profit.png'), dpi=100)
        plt.close()
        charts['strategy_profit'] = 'strategy_profit.png'

    # 5. Account Comparison (if multiple accounts and viewing all)
    if account_filter == 'all' and 'Account' in df.columns:
        account_prof = df.groupby('Account')['Profit'].sum().sort_values()
        if len(account_prof) > 1:
            plt.figure(figsize=(10, 5))
            colors = ['#38ef7d' if x >
                      0 else '#f45c43' for x in account_prof.values]
            account_prof.plot(kind='barh', color=colors)
            plt.title('Profit by Account', fontsize=14, fontweight='bold')
            plt.xlabel('Total Profit ($)')
            plt.axvline(0, color='black', linewidth=0.8)
            plt.tight_layout()
            plt.savefig(os.path.join(
                CHART_FOLDER, 'account_profit.png'), dpi=100)
            plt.close()
            charts['account_profit'] = 'account_profit.png'

    return charts


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Futures Trade Journal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 20px; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; margin-bottom: 15px; font-size: 1.3em; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .upload-section { background: #f9f9f9; padding: 20px; border-radius: 6px; flex: 1; min-width: 300px; }
        .upload-section form { display: flex; gap: 10px; }
        .upload-section input[type="file"] { padding: 8px; border: 1px solid #ddd; border-radius: 4px; flex: 1; }
        .upload-section button { background: #007bff; color: white; padding: 8px 20px; border: none; border-radius: 4px; cursor: pointer; white-space: nowrap; }
        .upload-section button:hover { background: #0056b3; }
        .account-filter { background: #f9f9f9; padding: 20px; border-radius: 6px; min-width: 250px; }
        .account-filter select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 6px; text-align: center; }
        .stat-card.positive { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .stat-card.negative { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }
        .stat-card h3 { font-size: 0.9em; opacity: 0.9; margin-bottom: 10px; }
        .stat-card .value { font-size: 1.8em; font-weight: bold; }
        .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; margin: 30px 0; }
        .chart-container { background: #f9f9f9; padding: 15px; border-radius: 6px; }
        .chart-container img { width: 100%; height: auto; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        table th { background: #007bff; color: white; padding: 12px; text-align: left; }
        table td { padding: 10px; border-bottom: 1px solid #ddd; }
        table tr:hover { background: #f5f5f5; }
        .account-label { display: inline-block; padding: 4px 8px; background: #007bff; color: white; border-radius: 4px; font-size: 0.85em; margin-left: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Futures Trade Journal{% if current_account and current_account != 'all' %}<span class="account-label">{{ current_account }}</span>{% endif %}</h1>
        
        <div class="top-bar">
            <div class="upload-section">
                <form method="post" enctype="multipart/form-data" action="/upload">
                    <input type="file" name="file" accept=".csv" required>
                    <button type="submit">Upload CSV</button>
                </form>
            </div>
            
            {% if accounts %}
                <div class="account-filter">
                    <form method="get" action="/">
                        <select name="account" onchange="this.form.submit()">
                            <option value="all" {% if current_account == 'all' %}selected{% endif %}>All Accounts</option>
                            {% for acc in accounts %}
                                <option value="{{ acc }}" {% if current_account == acc %}selected{% endif %}>{{ acc }}</option>
                            {% endfor %}
                        </select>
                    </form>
                </div>
            {% endif %}
        </div>
        
        {% if stats %}
            <h2>Overall Performance Metrics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Trades</h3>
                    <div class="value">{{ stats.total_trades }}</div>
                </div>
                <div class="stat-card positive">
                    <h3>Winning Trades</h3>
                    <div class="value">{{ stats.winning_trades }}</div>
                </div>
                <div class="stat-card negative">
                    <h3>Losing Trades</h3>
                    <div class="value">{{ stats.losing_trades }}</div>
                </div>
                <div class="stat-card">
                    <h3>Win Rate</h3>
                    <div class="value">{{ stats.win_rate }}</div>
                </div>
                <div class="stat-card positive">
                    <h3>Net Profit</h3>
                    <div class="value">{{ stats.net_profit }}</div>
                </div>
                <div class="stat-card">
                    <h3>Avg Trade</h3>
                    <div class="value">{{ stats.avg_profit }}</div>
                </div>
                <div class="stat-card positive">
                    <h3>Avg Win</h3>
                    <div class="value">{{ stats.avg_win }}</div>
                </div>
                <div class="stat-card negative">
                    <h3>Avg Loss</h3>
                    <div class="value">{{ stats.avg_loss }}</div>
                </div>
                <div class="stat-card">
                    <h3>Risk/Reward</h3>
                    <div class="value">{{ stats.risk_reward }}</div>
                </div>
                <div class="stat-card">
                    <h3>Expectancy</h3>
                    <div class="value">{{ stats.expectancy }}</div>
                </div>
            </div>
            
            {% if account_comparison and current_account == 'all' %}
                <h2>Account Comparison</h2>
                <table>
                    <tr>
                        <th>Account</th>
                        <th>Trades</th>
                        <th>Wins</th>
                        <th>Win Rate</th>
                        <th>Total Profit</th>
                        <th>Net Profit</th>
                    </tr>
                    {% for account, data in account_comparison.items() %}
                        <tr>
                            <td><strong><a href="/?account={{ account }}" style="text-decoration:none;color:#007bff;">{{ account }}</a></strong></td>
                            <td>{{ data.trades }}</td>
                            <td>{{ data.wins }}</td>
                            <td>{{ data.win_rate }}</td>
                            <td style="color: {% if data.profit[1] == '-' %}red{% else %}green{% endif %};">{{ data.profit }}</td>
                            <td style="color: {% if data.net_profit[1] == '-' %}red{% else %}green{% endif %};">{{ data.net_profit }}</td>
                        </tr>
                    {% endfor %}
                </table>
            {% endif %}
            
            {% if strategy_stats %}
                <h2>Strategy Breakdown</h2>
                <table>
                    <tr>
                        <th>Strategy</th>
                        <th>Trades</th>
                        <th>Wins</th>
                        <th>Win Rate</th>
                        <th>Profit</th>
                    </tr>
                    {% for strategy, data in strategy_stats.items() %}
                        <tr>
                            <td><strong>{{ strategy }}</strong></td>
                            <td>{{ data.trades }}</td>
                            <td>{{ data.wins }}</td>
                            <td>{{ data.win_rate }}</td>
                            <td style="color: {% if data.profit[1] == '-' %}red{% else %}green{% endif %};">{{ data.profit }}</td>
                        </tr>
                    {% endfor %}
                </table>
            {% endif %}
            
            <h2>Visualizations</h2>
            <div class="charts">
                {% if charts.profit_curve %}
                    <div class="chart-container">
                        <img src="{{ url_for('static', filename=charts.profit_curve) }}?v={{ timestamp }}" alt="Profit Curve">
                    </div>
                {% endif %}
                {% if charts.win_loss %}
                    <div class="chart-container">
                        <img src="{{ url_for('static', filename=charts.win_loss) }}?v={{ timestamp }}" alt="Win/Loss">
                    </div>
                {% endif %}
                {% if charts.profit_dist %}
                    <div class="chart-container">
                        <img src="{{ url_for('static', filename=charts.profit_dist) }}?v={{ timestamp }}" alt="Profit Distribution">
                    </div>
                {% endif %}
                {% if charts.strategy_profit %}
                    <div class="chart-container">
                        <img src="{{ url_for('static', filename=charts.strategy_profit) }}?v={{ timestamp }}" alt="Strategy Profit">
                    </div>
                {% endif %}
                {% if charts.account_profit %}
                    <div class="chart-container">
                        <img src="{{ url_for('static', filename=charts.account_profit) }}?v={{ timestamp }}" alt="Account Profit">
                    </div>
                {% endif %}
            </div>
        {% else %}
            <p style="text-align: center; color: #999; margin-top: 40px;">Upload CSV files to see your trading analytics.</p>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    df = parse_all_csv(UPLOAD_FOLDER)
    accounts = get_account_list(df)
    current_account = request.args.get('account', 'all')

    # Filter by account
    filtered_df = filter_by_account(df, current_account)

    stats = calculate_stats(filtered_df)
    strategy_stats = get_strategy_stats(filtered_df)
    account_comparison = get_account_comparison(
        df) if current_account == 'all' else None
    charts = create_charts(filtered_df, current_account)

    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        strategy_stats=strategy_stats,
        account_comparison=account_comparison,
        charts=charts,
        accounts=accounts,
        current_account=current_account,
        timestamp=datetime.now().timestamp()
    )


@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return redirect("/")
    file = request.files['file']
    if file and file.filename.endswith('.csv'):
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
