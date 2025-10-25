import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
import requests  # For calling Perplexity AI
import matplotlib
# Use 'Agg' backend for non-GUI environments like servers
matplotlib.use('Agg')

app = Flask(__name__)

# --- Supabase Setup ---
# Load from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Chart Generation Functions ---


def generate_profit_curve(df, static_folder):
    """Generates the cumulative profit curve chart."""
    if 'cum_net_profit' not in df.columns or 'exit_time' not in df.columns:
        return None

    # Ensure 'exit_time' is datetime and sorted
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values(by='exit_time')

    plt.figure(figsize=(10, 6))
    plt.plot(df['exit_time'], df['cum_net_profit'],
             label='Cumulative Profit', color='blue')
    plt.title('Cumulative Profit Over Time')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Profit ($)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    chart_path = os.path.join(static_folder, 'profit_curve.png')
    plt.savefig(chart_path)
    plt.close()
    # Add timestamp for cache-busting
    return f'profit_curve.png?v={datetime.now().timestamp()}'


def generate_win_loss_chart(df, static_folder):
    """Generates the win/loss distribution pie chart."""
    if 'profit' not in df.columns:
        return None

    wins = df[df['profit'] > 0].shape[0]
    losses = df[df['profit'] <= 0].shape[0]

    if wins == 0 and losses == 0:
        return None

    labels = 'Wins', 'Losses'
    sizes = [wins, losses]
    colors = ['#4CAF50', '#F44336']

    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, colors=colors,
            autopct='%1.1f%%', startangle=90)
    plt.title('Win/Loss Distribution')
    plt.axis('equal')

    chart_path = os.path.join(static_folder, 'win_loss.png')
    plt.savefig(chart_path)
    plt.close()
    return f'win_loss.png?v={datetime.now().timestamp()}'

# ... You can add your other chart functions here (profit_dist, strategy_profit, etc.) ...

# --- NEW: AI Tone Helper Function ---


def get_tone_prompt(tone_name):
    """Returns the specific AI instruction based on the selected tone."""

    tones = {
        "Soros": (
            "Analyze these trades from the reflective, macro-economic, and philosophical "
            "perspective of George Soros. Focus on the underlying thesis, "
            "reflexivity, and whether it was a boom-bust cycle. Be critical of the risk."
        ),
        "Tudor Jones": (
            "Analyze these trades as Paul Tudor Jones would. Be aggressive, "
            "focus on risk/reward, and cutting losers quickly. "
            "Comment on the technicals and market sentiment at the time. "
            "Where was the 'fat pitch'?"
        ),
        "Dennis": (
            "Analyze these trades like Richard Dennis. Focus on systematic, "
            "trend-following logic. Was this a valid breakout? "
            "Was the position sized correctly? "
            "Was the exit based on a clear rule? Be logical and unemotional."
        ),
        "Groucho": (
            "Analyze these trades as Groucho Marx. Be witty, sarcastic, and fill it "
            "with puns. 'A futures contract is an agreement to buy something you don't want, "
            "at a price you don't agree with, at a time you don't know.' "
            "Mock the bad trades and begrudgingly praise the good ones. "
            "Don't be afraid to be absurd."
        ),
        "default": (
            "You are a professional trading coach. Analyze the following trades. "
            "Be objective, clear, and provide constructive feedback."
        )
    }
    return tones.get(tone_name, tones['default'])


# --- Flask Routes ---

@app.route('/')
def index():
    """Dashboard home page."""
    try:
        # Get trades from Supabase
        response = supabase.table('trades').select(
            '*').order('exit_time', desc=True).execute()
        trades = response.data

        if not trades:
            # Pass empty data to template
            return render_template('index.html', stats={}, charts={})

        # Convert to DataFrame for analysis
        df = pd.DataFrame(trades)

        # --- Calculate Statistics (as per your README) ---
        total_trades = df.shape[0]
        wins = df[df['profit'] > 0].shape[0]
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        total_profit = df['profit'].sum()
        avg_profit = df['profit'].mean()
        avg_win = df[df['profit'] > 0]['profit'].mean()
        avg_loss = df[df['profit'] <= 0]['profit'].mean()
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        expectancy = (win_rate / 100 * avg_win) - \
            ((1 - win_rate / 100) * abs(avg_loss))

        stats = {
            'total_trades': total_trades,
            'win_rate': f"{win_rate:.2f}%",
            'total_profit': f"${total_profit:,.2f}",
            'avg_profit': f"${avg_profit:,.2f}",
            'rr_ratio': f"{rr_ratio:.2f}",
            'expectancy': f"${expectancy:,.2f}"
        }

        # --- Generate Charts ---
        static_folder = os.path.join(app.root_path, 'static')
        charts = {
            'profit_curve': generate_profit_curve(df.copy(), static_folder),
            'win_loss': generate_win_loss_chart(df.copy(), static_folder)
            # Add other chart function calls here
        }

        return render_template('index.html', stats=stats, charts=charts)

    except Exception as e:
        print(f"Error loading dashboard: {e}")
        return render_template('index.html', error=str(e), stats={}, charts={})


@app.route('/analysis')
def analysis_page():
    """Trade analysis page."""
    try:
        # Fetch all trades for the analysis table
        response = supabase.table('trades').select(
            '*').order('exit_time', desc=True).execute()
        trades = response.data
        return render_template('analysis.html', trades=trades)
    except Exception as e:
        print(f"Error loading analysis page: {e}")
        return render_template('analysis.html', trades=[], error=str(e))


@app.route('/upload', methods=['POST'])
def upload_csv():
    """CSV file upload endpoint."""
    if 'trade_file' not in request.files:
        return redirect(url_for('index', error='No file selected'))

    file = request.files['trade_file']
    if file.filename == '':
        return redirect(url_for('index', error='No file selected'))

    try:
        # Read CSV data
        df = pd.read_csv(file)

        # --- Data Cleaning (based on NinjaTrader format) ---
        # Rename columns to match Supabase (e.g., 'Trade number' -> 'trade_number')
        df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace('.', '')

        # Ensure correct data types
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['exit_time'] = pd.to_datetime(df['exit_time'])

        # Handle 'Profit', 'Commission', 'MAE', 'MFE' (remove $, commas)
        for col in ['profit', 'cum_net_profit', 'commission', 'mae', 'mfe']:
            if col in df.columns:
                df[col] = df[col].replace(
                    r'[$,]', '', regex=True).astype(float)

        # Convert DataFrame to list of dicts for Supabase
        # Handle numpy types which are not JSON serializable
        df = df.astype(object)  # Convert types for JSON
        df = df.where(pd.notnull(df), None)  # Replace NaT/NaN with None
        data_to_insert = df.to_dict('records')

        # Insert data into Supabase
        response = supabase.table('trades').insert(data_to_insert).execute()

        if response.data:
            return redirect(url_for('index'))
        else:
            return redirect(url_for('index', error='Failed to upload data.'))

    except Exception as e:
        print(f"Error during upload: {e}")
        return redirect(url_for('index', error=f"Error processing file: {e}"))


@app.route('/analyze', methods=['POST'])
def analyze_trades():
    """AI trade analysis endpoint."""
    if not PERPLEXITY_API_KEY:
        return jsonify({'error': 'PERPLEXITY_API_KEY not set on server'}), 500

    try:
        data = request.get_json()
        trades = data.get('trades', [])

        # --- NEW: Get the tone from the request ---
        tone = data.get('tone', 'default')
        tone_instruction = get_tone_prompt(tone)
        # --- END NEW ---

        if not trades:
            return jsonify({'error': 'No trades provided'}), 400

        # Prepare trade data for the AI
        trades_summary = []
        for i, trade in enumerate(trades):
            trades_summary.append(
                f"Trade {i+1}:\n"
                f"- Instrument: {trade.get('instrument')}\n"
                f"- Strategy: {trade.get('strategy')}\n"
                f"- Entry: {trade.get('entry_time')}\n"
                f"- Exit: {trade.get('exit_time')}\n"
                f"- P&L: {trade.get('profit')}\n"
                f"- MAE: {trade.get('mae')}\n"
                f"- MFE: {trade.get('mfe')}\n"
            )

        trades_text = "\n".join(trades_summary)

        # --- MODIFIED AI PROMPT ---
        prompt = f"""
        {tone_instruction}

        Please analyze the following futures trades. For each trade, I want a detailed 
        analysis of the entry, exit, and risk management.

        **Crucially, also provide an analysis of the *probable price action* at the time of 
        the trade (e.g., was it a breakout, a range-bound fade, a support test?).**

        Provide your analysis in clean HTML format. Use <h3> for trade titles, 
        <ul>/<li> for lists, and <strong> for key observations. 
        Do not include ```html at the beginning or end.

        Here are the trades:
        {trades_text}
        """

        # Call Perplexity AI
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            # or your preferred model from README (sonar-pro)
            "model": "pplx-7b-online",
            "messages": [
                {"role": "system", "content": "You are an expert trading analyst and coach."},
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post(
            "[https://api.perplexity.ai/chat/completions](https://api.perplexity.ai/chat/completions)", headers=headers, json=payload)

        if response.status_code == 200:
            ai_response = response.json()
            analysis_content = ai_response['choices'][0]['message']['content']
            return jsonify({'analysis': analysis_content})
        else:
            return jsonify({'error': f"AI API error: {response.text}"}), response.status_code

    except Exception as e:
        print(f"Error in /analyze: {e}")
        return jsonify({'error': str(e)}), 500

# --- Serve Static Chart Files ---


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serves static files (like generated charts)."""
    return send_from_directory('static', filename)


# --- Main ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
