import dotenv
from datetime import datetime
import os
import matplotlib.pyplot as plt
from flask import Flask, render_template_string, request, jsonify
from supabase import create_client, Client
import pandas as pd
import matplotlib
matplotlib.use('Agg')

dotenv.load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
                df[col] = df[col].replace({'\$': '', ',': ''}, regex=True)
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


def get_trades_df(account='all'):
    try:
        if account and account != 'all':
            response = supabase.table('trades').select(
                '*').eq('account', account).execute()
        else:
            response = supabase.table('trades').select('*').execute()

        if response.data:
            df = pd.DataFrame(response.data)
            for col in ['entry_time', 'exit_time']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return pd.DataFrame()


def get_account_list():
    try:
        response = supabase.table('trades').select('account').execute()
        accounts = list(set([row['account']
                        for row in response.data if row.get('account')]))
        return sorted(accounts)
    except Exception as e:
        print(f"Error getting accounts: {e}")
        return []


def filter_by_account(df, account):
    if not account or account == 'all':
        return df
    if 'account' in df.columns:
        return df[df['account'] == account]
    return df

# ... (the other helper functions for stats and charts remain unchanged, same as before)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Futures Trade Journal</title>
    <style>
        /* Existing styles here */
        /* Add spinner and upload feedback styles */
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Futures Trade Journal{% if current_account and current_account != 'all' %}<span class="account-label">{{ current_account }}</span>{% endif %}</h1>
        
        <div class="top-bar">
            <div class="upload-section">
                <form id="upload-form" enctype="multipart/form-data">
                    <input type="file" name="file" id="file-input" accept=".csv" required>
                    <button id="upload-btn" type="submit">Upload CSV</button>
                </form>
                <div id="upload-status" style="margin-top:10px; font-weight:bold;"></div>
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
            <!-- Existing stats, comparisons, and charts HTML here -->
        {% else %}
            <p style="text-align: center; color: #999; margin-top: 40px;">Upload CSV files to see your trading analytics.</p>
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


@app.route("/", methods=["GET"])
def index():
    account = request.args.get('account', 'all')
    df = get_trades_df(account)
    accounts = get_account_list()

    filtered_df = filter_by_account(df, account)

    stats = calculate_stats(filtered_df)
    strategy_stats = get_strategy_stats(filtered_df)
    account_comparison = get_account_comparison(
        df) if account == 'all' else None
    charts = create_charts(filtered_df, account)

    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        strategy_stats=strategy_stats,
        account_comparison=account_comparison,
        charts=charts,
        accounts=accounts,
        current_account=account,
        timestamp=datetime.now().timestamp()
    )


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
