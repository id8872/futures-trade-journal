import dotenv
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
from flask import Flask, render_template_string, request, jsonify
from supabase import create_client, Client
import pandas as pd
import matplotlib
import json
from openai import OpenAI

matplotlib.use('Agg')

dotenv.load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Perplexity client
perplexity_client = OpenAI(
    api_key=PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
)

CHART_FOLDER = 'static'
os.makedirs(CHART_FOLDER, exist_ok=True)


def clean_money_value(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace('$', '').replace(',', '').strip())


def insert_trades_from_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        for col in ['Profit', 'Cum. net profit', 'Entry price', 'Exit price', 'Qty', 'MAE', 'MFE']:
            if col in df.columns:
                df[col] = df[col].replace({r'\$': '', ',': ''}, regex=True)
                try:
                    df[col] = pd.to_numeric(df[col])
                except:
                    pass
        if 'Exit time' in df.columns:
            df['Exit time'] = pd.to_datetime(df['Exit time'])
        if 'Entry time' in df.columns:
            df['Entry time'] = pd.to_datetime(df['Entry time'])
        for idx, row in df.iterrows():
            trade_data = {
                'trade_number': int(row.get('Trade number', 0)) if pd.notna(row.get('Trade number')) else None,
                'instrument': str(row.get('Instrument', '')),
                'account': str(row.get('Account', '')),
                'strategy': str(row.get('Strategy', '')),
                'market_pos': str(row.get('Market pos.', '')),
                'qty': int(row.get('Qty', 0)) if pd.notna(row.get('Qty')) else 0,
                'entry_price': float(row.get('Entry price', 0)) if pd.notna(row.get('Entry price')) else 0,
                'exit_price': float(row.get('Exit price', 0)) if pd.notna(row.get('Exit price')) else 0,
                'entry_time': row['Entry time'].isoformat() if pd.notna(row.get('Entry time')) else None,
                'exit_time': row['Exit time'].isoformat() if pd.notna(row.get('Exit time')) else None,
                'entry_name': str(row.get('Entry name', '')),
                'exit_name': str(row.get('Exit name', '')),
                'profit': clean_money_value(row.get('Profit', 0)),
                'cum_net_profit': clean_money_value(row.get('Cum. net profit', 0)),
                'commission': clean_money_value(row.get('Commission', 0)),
                'mae': clean_money_value(row.get('MAE', 0)),
                'mfe': clean_money_value(row.get('MFE', 0)),
            }
            supabase.table('trades').insert(trade_data).execute()
        return True
    except Exception as e:
        print(f"Error inserting trades: {e}")
        return False


def get_trades_df(account='all', start_date=None, end_date=None):
    print("About to query Supabase...")
    query = supabase.table('trades').select('*')

    if not start_date and not end_date:
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        start_date = monday.strftime('%Y-%m-%d')
        print(
            f"No date filters provided, defaulting to current week from {start_date}")

    if account and account != 'all':
        print(f"Filtering by account: {account}")
        query = query.eq('account', account)

    if start_date:
        start_date_iso = f"{start_date}T00:00:00Z"
        print(f"Filtering by start_date: {start_date_iso}")
        query = query.gte('exit_time', start_date_iso)

    if end_date:
        end_date_iso = f"{end_date}T23:59:59Z"
        print(f"Filtering by end_date: {end_date_iso}")
        query = query.lte('exit_time', end_date_iso)

    query = query.order('exit_time', desc=True)

    try:
        response = query.execute()
        print("Supabase response received.")

        if hasattr(response, 'error') and response.error:
            print(f"Supabase API error: {response.error}")
            return pd.DataFrame()

        print(f"Number of rows: {len(response.data) if response.data else 0}")

    except Exception as e:
        print(
            f"Exception executing Supabase query: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

    if response.data:
        df = pd.DataFrame(response.data)
        for col in ['entry_time', 'exit_time']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        print("Rows returned:", len(df))
        return df

    print("No data received from Supabase.")
    return pd.DataFrame()


def get_account_list():
    response = supabase.table('trades').select('account').execute()
    accounts = list(set([row['account']
                    for row in response.data if row.get('account')]))
    return sorted(accounts)


def calculate_stats(df):
    if df.empty or 'profit' not in df.columns:
        return None
    wins = df[df['profit'] > 0]
    losses = df[df['profit'] < 0]
    stats = {
        'total_trades': len(df),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'break_even': len(df[df['profit'] == 0]),
        'win_rate': f"{(len(wins) / len(df) * 100):.1f}%" if len(df) > 0 else "0%",
        'total_profit': f"${df['profit'].sum():.2f}",
        'avg_profit': f"${df['profit'].mean():.2f}",
        'avg_win': f"${wins['profit'].mean():.2f}" if len(wins) > 0 else "$0.00",
        'avg_loss': f"${losses['profit'].mean():.2f}" if len(losses) > 0 else "$0.00",
        'largest_win': f"${df['profit'].max():.2f}",
        'largest_loss': f"${df['profit'].min():.2f}",
        'net_profit': f"${df['cum_net_profit'].iloc[-1]:.2f}" if 'cum_net_profit' in df.columns and len(df) > 0 else "$0.00",
    }
    if len(wins) > 0 and len(losses) > 0:
        avg_win = wins['profit'].mean()
        avg_loss = abs(losses['profit'].mean())
        stats['risk_reward'] = f"{avg_win / avg_loss:.2f}" if avg_loss != 0 else "N/A"
    else:
        stats['risk_reward'] = "N/A"
    prob_win = len(wins) / len(df) if len(df) > 0 else 0
    prob_loss = len(losses) / len(df) if len(df) > 0 else 0
    avg_win = wins['profit'].mean() if len(wins) > 0 else 0
    avg_loss = losses['profit'].mean() if len(losses) > 0 else 0
    expectancy = (prob_win * avg_win) + (prob_loss * avg_loss)
    stats['expectancy'] = f"${expectancy:.2f}"
    return stats


def get_strategy_stats(df):
    if df.empty or 'strategy' not in df.columns:
        return {}
    strategies = {}
    for strategy in df['strategy'].unique():
        strat_df = df[df['strategy'] == strategy]
        wins = len(strat_df[strat_df['profit'] > 0])
        total = len(strat_df)
        strategies[strategy] = {
            'trades': total,
            'wins': wins,
            'win_rate': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            'profit': f"${strat_df['profit'].sum():.2f}"
        }
    return strategies


def get_account_comparison(df):
    if df.empty or 'account' not in df.columns:
        return {}
    accounts = {}
    for account in df['account'].unique():
        acc_df = df[df['account'] == account]
        wins = len(acc_df[acc_df['profit'] > 0])
        total = len(acc_df)
        accounts[account] = {
            'trades': total,
            'wins': wins,
            'win_rate': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            'profit': f"${acc_df['profit'].sum():.2f}",
            'net_profit': f"${acc_df['cum_net_profit'].iloc[-1]:.2f}" if 'cum_net_profit' in acc_df.columns and len(acc_df) > 0 else "$0.00"
        }
    return accounts


def create_charts(df, account_filter='all'):
    if df.empty:
        return {}
    charts = {}
    if 'exit_time' in df.columns and 'cum_net_profit' in df.columns:
        df_sorted = df.sort_values('exit_time')
        plt.figure(figsize=(12, 5))
        plt.plot(df_sorted['exit_time'], df_sorted['cum_net_profit'],
                 marker='o', linestyle='-', linewidth=2, color='#007bff')
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
    if 'profit' in df.columns:
        plt.figure(figsize=(10, 5))
        wins = len(df[df['profit'] > 0])
        losses = len(df[df['profit'] < 0])
        break_even = len(df[df['profit'] == 0])
        plt.bar(['Wins', 'Losses', 'Break Even'], [wins, losses,
                break_even], color=['#38ef7d', '#f45c43', '#999'])
        plt.title('Trade Outcomes', fontsize=14, fontweight='bold')
        plt.ylabel('Number of Trades')
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'win_loss.png'), dpi=100)
        plt.close()
        charts['win_loss'] = 'win_loss.png'
    if 'profit' in df.columns:
        plt.figure(figsize=(10, 5))
        plt.hist(df['profit'], bins=15, color='steelblue', edgecolor='black')
        plt.title('Profit Distribution', fontsize=14, fontweight='bold')
        plt.xlabel('Profit ($)')
        plt.ylabel('Frequency')
        plt.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(CHART_FOLDER, 'profit_dist.png'), dpi=100)
        plt.close()
        charts['profit_dist'] = 'profit_dist.png'
    if 'strategy' in df.columns and 'profit' in df.columns:
        strategy_prof = df.groupby('strategy')['profit'].sum().sort_values()
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
    if account_filter == 'all' and 'account' in df.columns:
        account_prof = df.groupby('account')['profit'].sum().sort_values()
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
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 2rem; margin-bottom: 20px; color: #111; }
        .account-label { background: #007bff; color: white; padding: 4px 12px; border-radius: 4px; font-size: 0.9rem; margin-left: 10px; }
        .nav { margin-bottom: 20px; }
        .nav a { padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; display: inline-block; }
        .nav a:hover { background: #0056b3; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .upload-section form { display: flex; gap: 10px; align-items: center; }
        .upload-section input[type="file"] { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        .upload-section button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }
        .upload-section button:hover { background: #0056b3; }
        .upload-section button:disabled { background: #ccc; cursor: not-allowed; }
        #upload-status { font-size: 0.9rem; margin-top: 5px; }
        .account-filter form { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .account-filter select, .account-filter input[type="date"] { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.95rem; }
        .account-filter label { font-size: 0.9rem; font-weight: 500; }
        .quick-filters { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .btn-quick { padding: 8px 16px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; text-decoration: none; color: #333; font-size: 0.9rem; transition: all 0.2s; }
        .btn-quick:hover { background: #e0e0e0; border-color: #bbb; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-card h3 { font-size: 0.85rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
        .stat-card .value { font-size: 1.5rem; font-weight: 600; color: #111; }
        .section { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 25px; }
        .section h2 { font-size: 1.3rem; margin-bottom: 15px; color: #111; }
        .chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }
        .chart-item img { width: 100%; height: auto; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; }
        table th, table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        table th { background: #f9f9f9; font-weight: 600; font-size: 0.9rem; color: #666; }
        table td { font-size: 0.95rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Futures Trade Journal{% if current_account and current_account != 'all' %}<span class="account-label">{{ current_account }}</span>{% endif %}</h1>
        
        <div class="nav">
            <a href="/analysis">🔍 Trade Analysis</a>
        </div>
        
        <div class="quick-filters">
            <a href="/?start_date={{ today }}&end_date={{ today }}" class="btn-quick">Today</a>
            <a href="/" class="btn-quick">This Week</a>
            <a href="/?start_date={{ first_of_month }}" class="btn-quick">This Month</a>
            <a href="/?start_date=&end_date=" class="btn-quick">All Time</a>
        </div>
        
        <div class="top-bar">
            <div class="upload-section">
                <form id="upload-form" enctype="multipart/form-data">
                    <input type="file" name="file" id="file-input" accept=".csv" required>
                    <button id="upload-btn" type="submit">Upload CSV</button>
                </form>
                <div id="upload-status"></div>
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
                        <label for="start_date">From:</label>
                        <input type="date" name="start_date" value="{{ start_date|default('') }}" onchange="this.form.submit()">
                        <label for="end_date">To:</label>
                        <input type="date" name="end_date" value="{{ end_date|default('') }}" onchange="this.form.submit()">
                    </form>
                </div>
            {% endif %}
        </div>
        
        {% if stats %}
            <div class="stats-grid">
                <div class="stat-card"><h3>Total Trades</h3><div class="value">{{ stats.total_trades }}</div></div>
                <div class="stat-card"><h3>Win Rate</h3><div class="value">{{ stats.win_rate }}</div></div>
                <div class="stat-card"><h3>Net Profit</h3><div class="value">{{ stats.net_profit }}</div></div>
                <div class="stat-card"><h3>Avg Profit</h3><div class="value">{{ stats.avg_profit }}</div></div>
                <div class="stat-card"><h3>Risk/Reward</h3><div class="value">{{ stats.risk_reward }}</div></div>
                <div class="stat-card"><h3>Expectancy</h3><div class="value">{{ stats.expectancy }}</div></div>
            </div>
            
            {% if strategy_stats %}
            <div class="section">
                <h2>Strategy Performance</h2>
                <table>
                    <thead><tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>Profit</th></tr></thead>
                    <tbody>
                        {% for strategy, data in strategy_stats.items() %}
                        <tr><td>{{ strategy }}</td><td>{{ data.trades }}</td><td>{{ data.win_rate }}</td><td>{{ data.profit }}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            
            {% if account_comparison %}
            <div class="section">
                <h2>Account Comparison</h2>
                <table>
                    <thead><tr><th>Account</th><th>Trades</th><th>Win Rate</th><th>Profit</th><th>Net Profit</th></tr></thead>
                    <tbody>
                        {% for account, data in account_comparison.items() %}
                        <tr><td>{{ account }}</td><td>{{ data.trades }}</td><td>{{ data.win_rate }}</td><td>{{ data.profit }}</td><td>{{ data.net_profit }}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            
            {% if charts %}
            <div class="section">
                <h2>Charts</h2>
                <div class="chart-grid">
                    {% for name, path in charts.items() %}
                    <div class="chart-item"><img src="/static/{{ path }}?t={{ timestamp }}" alt="{{ name }}"></div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        {% else %}
            <p style="text-align: center; color: #999; margin-top: 40px;">No trades found for the selected filters.</p>
        {% endif %}
    </div>
    
    <script>
    const form = document.getElementById('upload-form');
    const btn = document.getElementById('upload-btn');
    const statusDiv = document.getElementById('upload-status');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('file-input');
      if (!fileInput.files.length) {
        statusDiv.textContent = 'Please choose a file.';
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Uploading...';
      statusDiv.textContent = '';

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      try {
        const res = await fetch('/upload', {
          method: 'POST',
          body: formData,
        });
        if (res.ok) {
          statusDiv.textContent = 'Upload successful! Refreshing...';
          setTimeout(() => {
            window.location.reload();
          }, 1500);
        } else {
          statusDiv.textContent = 'Upload failed. Please try again.';
        }
      } catch (error) {
        statusDiv.textContent = 'Error uploading file.';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Upload CSV';
      }
    });
    </script>
</body>
</html>
"""

ANALYSIS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Trade Analysis - Futures Journal</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 2rem; margin-bottom: 20px; color: #111; }
        .nav { margin-bottom: 20px; }
        .nav a { padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; }
        .nav a:hover { background: #0056b3; }
        .quick-filters { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .btn-quick { padding: 8px 16px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; text-decoration: none; color: #333; font-size: 0.9rem; }
        .controls { display: flex; gap: 15px; margin-bottom: 20px; align-items: center; }
        .controls select, .controls input { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; }
        table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        table th, table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        table th { background: #f9f9f9; font-weight: 600; font-size: 0.9rem; color: #666; }
        .profit-positive { color: #28a745; font-weight: 600; }
        .profit-negative { color: #dc3545; font-weight: 600; }
        #analyze-btn { padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; font-weight: 500; }
        #analyze-btn:hover { background: #0056b3; }
        #analyze-btn:disabled { background: #ccc; cursor: not-allowed; }
        #analysis-results { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-top: 20px; display: none; }
        .analysis-box { line-height: 1.6; white-space: pre-wrap; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #007bff; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; display: none; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Trade Analysis</h1>
        
        <div class="nav">
            <a href="/">← Back to Dashboard</a>
        </div>
        
        <div class="quick-filters">
            <a href="/analysis?start_date={{ today }}&end_date={{ today }}" class="btn-quick">Today</a>
            <a href="/analysis" class="btn-quick">This Week</a>
            <a href="/analysis?start_date={{ first_of_month }}" class="btn-quick">This Month</a>
            <a href="/analysis?start_date=&end_date=" class="btn-quick">All Time</a>
        </div>
        
        <div class="controls">
            <form method="get" action="/analysis" style="display: flex; gap: 10px; align-items: center;">
                {% if accounts %}
                <select name="account" onchange="this.form.submit()">
                    <option value="all" {% if current_account == 'all' %}selected{% endif %}>All Accounts</option>
                    {% for acc in accounts %}
                        <option value="{{ acc }}" {% if current_account == acc %}selected{% endif %}>{{ acc }}</option>
                    {% endfor %}
                </select>
                {% endif %}
                <label>From:</label>
                <input type="date" name="start_date" value="{{ start_date|default('') }}" onchange="this.form.submit()">
                <label>To:</label>
                <input type="date" name="end_date" value="{{ end_date|default('') }}" onchange="this.form.submit()">
            </form>
            <button id="analyze-btn">Analyze Selected Trades</button>
        </div>
        
        {% if trades %}
        <table>
            <thead>
                <tr>
                    <th><input type="checkbox" id="select-all"></th>
                    <th>Date/Time</th>
                    <th>Instrument</th>
                    <th>Strategy</th>
                    <th>Position</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>P&L</th>
                    <th>MAE</th>
                    <th>MFE</th>
                </tr>
            </thead>
            <tbody>
                {% for trade in trades %}
                <tr>
                    <td><input type="checkbox" class="trade-checkbox" value="{{ trade.id }}"></td>
                    <td>{{ trade.exit_time_display }}</td>
                    <td>{{ trade.instrument }}</td>
                    <td>{{ trade.strategy }}</td>
                    <td>{{ trade.market_pos }}</td>
                    <td>${{ "%.2f"|format(trade.entry_price) }}</td>
                    <td>${{ "%.2f"|format(trade.exit_price) }}</td>
                    <td class="{% if trade.profit > 0 %}profit-positive{% else %}profit-negative{% endif %}">${{ "%.2f"|format(trade.profit) }}</td>
                    <td>${{ "%.2f"|format(trade.mae) }}</td>
                    <td>${{ "%.2f"|format(trade.mfe) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="text-align: center; color: #999; margin-top: 40px;">No trades found for the selected filters.</p>
        {% endif %}
        
        <div class="loader" id="loader"></div>
        <div id="analysis-results"></div>
    </div>
    
    <script>
    // Select all checkbox
    document.getElementById('select-all').addEventListener('change', function() {
        document.querySelectorAll('.trade-checkbox').forEach(cb => cb.checked = this.checked);
    });

    // Analyze button
    document.getElementById('analyze-btn').addEventListener('click', async () => {
        const selected = Array.from(document.querySelectorAll('.trade-checkbox:checked'))
            .map(cb => cb.value);
        
        if (selected.length === 0) {
            alert('Please select at least one trade to analyze');
            return;
        }
        
        const btn = document.getElementById('analyze-btn');
        const loader = document.getElementById('loader');
        const results = document.getElementById('analysis-results');
        
        btn.disabled = true;
        btn.textContent = 'Analyzing...';
        loader.style.display = 'block';
        results.style.display = 'none';
        
        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({trade_ids: selected})
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Use textContent to safely insert text, then manually replace newlines
                const analysisDiv = document.createElement('div');
                analysisDiv.className = 'analysis-box';
                analysisDiv.textContent = result.analysis;
                
                results.innerHTML = '<h2>AI Analysis Results</h2>';
                results.appendChild(analysisDiv);
                results.style.display = 'block';
            } else {
                alert('Analysis failed: ' + result.error);
            }
        } catch (error) {
            alert('Error: ' + error.message);
            console.error('Analysis error:', error);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Analyze Selected Trades';
            loader.style.display = 'none';
        }
    });
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    account = request.args.get('account', 'all')
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)

    df = get_trades_df(account, start_date, end_date)
    accounts = get_account_list()

    stats = calculate_stats(df)
    strategy_stats = get_strategy_stats(df)
    account_comparison = get_account_comparison(
        df) if account == 'all' else None
    charts = create_charts(df, account)

    today = datetime.now().strftime('%Y-%m-%d')
    first_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        strategy_stats=strategy_stats,
        account_comparison=account_comparison,
        charts=charts,
        accounts=accounts,
        current_account=account,
        start_date=start_date,
        end_date=end_date,
        today=today,
        first_of_month=first_of_month,
        timestamp=datetime.now().timestamp()
    )


@app.route("/analysis", methods=["GET"])
def analysis():
    account = request.args.get('account', 'all')
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)

    df = get_trades_df(account, start_date, end_date)
    accounts = get_account_list()

    trades_list = df.to_dict('records') if not df.empty else []

    for trade in trades_list:
        if trade.get('exit_time'):
            trade['exit_time_display'] = pd.to_datetime(
                trade['exit_time']).strftime('%Y-%m-%d %H:%M')

    today = datetime.now().strftime('%Y-%m-%d')
    first_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    return render_template_string(
        ANALYSIS_TEMPLATE,
        trades=trades_list,
        accounts=accounts,
        current_account=account,
        start_date=start_date,
        end_date=end_date,
        today=today,
        first_of_month=first_of_month
    )


@app.route("/analyze", methods=["POST"])
def analyze_trades():
    trade_ids = request.json.get('trade_ids', [])

    if not trade_ids:
        return jsonify({"success": False, "error": "No trades selected"}), 400

    trades_data = []
    for trade_id in trade_ids:
        response = supabase.table('trades').select(
            '*').eq('id', trade_id).execute()
        if response.data:
            trades_data.append(response.data[0])

    analysis_prompt = f"""You are an expert futures trading analyst. Analyze the following trades and provide specific feedback:

For each trade, evaluate:
1. **Entry Quality**: Was the entry price optimal? Consider the MAE (Maximum Adverse Excursion) to assess if entry could have been better.
2. **Exit Quality**: Was the exit optimal? Consider the MFE (Maximum Favorable Excursion) to see if profit was left on the table.
3. **Risk Management**: Analyze the profit vs MAE/MFE ratio.
4. **Execution**: Rate the overall trade execution (1-10).

Trades to analyze:
{json.dumps(trades_data, indent=2)}

Provide actionable feedback for improvement. Be specific and practical."""

    try:
        response = perplexity_client.chat.completions.create(
            model="llama-3-sonar-large-32k-online",
            messages=[
                {"role": "system", "content": "You are an expert futures trading analyst with deep knowledge of price action, risk management, and execution optimization."},
                {"role": "user", "content": analysis_prompt}
            ]
        )
        analysis = response.choices[0].message.content
        return jsonify({"success": True, "analysis": analysis})
    except Exception as e:
        print(f"Perplexity API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return jsonify(success=False), 400
    file = request.files['file']
    if file and file.filename.endswith('.csv'):
        temp_path = f'/tmp/{file.filename}'
        file.save(temp_path)
        success = insert_trades_from_csv(temp_path)
        os.remove(temp_path)
        if success:
            return jsonify(success=True)
        else:
            return jsonify(success=False), 500
    return jsonify(success=False), 400


if __name__ == "__main__":
    app.run(debug=True)
