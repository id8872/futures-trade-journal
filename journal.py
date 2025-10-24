from flask import Flask, render_template_string, request, redirect, send_from_directory, url_for
import pandas as pd
import matplotlib.pyplot as plt
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'data'
CHART_PATH = 'static'
CHART_FILE = 'profit_curve.png'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_PATH, exist_ok=True)

HTML = """
<!doctype html>
<title>Futures Trade Journal</title>
<h1>Upload NinjaTrader CSV</h1>
<form method=post enctype=multipart/form-data action="/upload">
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
{% if summary %}
  <h2>Trade Summary</h2>
  <ul>
    <li>Total trades: {{ summary['total_trades'] }}</li>
    <li>Winning trades: {{ summary['winning_trades'] }}</li>
    <li>Losing trades: {{ summary['losing_trades'] }}</li>
    <li>Total profit: ${{ summary['total_profit'] }}</li>
    <li>Average profit: ${{ summary['avg_profit'] }}</li>
    <li>Net profit: ${{ summary['net_profit'] }}</li>
  </ul>
  {% if chart_url %}
      <h2>Cumulative Net Profit</h2>
      <img src="{{ chart_url }}" alt="Cumulative Profit Curve" style="width:90%;max-width:700px">
  {% endif %}
{% endif %}
"""


def parse_all_csv(folder):
    df_list = []
    for f in os.listdir(folder):
        if f.endswith('.csv'):
            df = pd.read_csv(os.path.join(folder, f))
            # Clean numeric columns if present
            if 'Profit' in df.columns:
                df['Profit'] = df['Profit'].replace(
                    {'\\$': '', ',': ''}, regex=True).astype(float)
            if 'Cum. net profit' in df.columns:
                df['Cum. net profit'] = df['Cum. net profit'].replace(
                    {'\\$': '', ',': ''}, regex=True).astype(float)
            if 'Exit time' in df.columns:
                try:
                    df['Exit time'] = pd.to_datetime(df['Exit time'])
                except Exception:
                    pass
            df_list.append(df)
    if df_list:
        return pd.concat(df_list, ignore_index=True)
    else:
        return pd.DataFrame()


def make_summary(df):
    if df.empty:
        return None
    total_trades = len(df)
    winning_trades = (df['Profit'] > 0).sum()
    losing_trades = (df['Profit'] <= 0).sum()
    total_profit = df['Profit'].sum()
    avg_profit = df['Profit'].mean()
    net_profit = df['Cum. net profit'].iloc[-1] if 'Cum. net profit' in df else 0
    return dict(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        total_profit=f"{total_profit:.2f}",
        avg_profit=f"{avg_profit:.2f}",
        net_profit=f"{net_profit:.2f}"
    )


def save_profit_curve(df, chart_path):
    if df.empty or 'Exit time' not in df or 'Cum. net profit' not in df:
        return None
    plt.figure(figsize=(10, 4))
    plt.plot(df['Exit time'], df['Cum. net profit'], marker='o', linestyle='-')
    plt.title('Cumulative Net Profit Over Time')
    plt.xlabel('Exit Time')
    plt.ylabel('Cumulative Net Profit')
    plt.xticks(rotation=45)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()
    return chart_path


@app.route("/", methods=["GET"])
def index():
    df = parse_all_csv(UPLOAD_FOLDER)
    summary = make_summary(df)
    chart_url = None
    if summary and not df.empty and 'Exit time' in df and 'Cum. net profit' in df:
        chart_file = os.path.join(CHART_PATH, CHART_FILE)
        save_profit_curve(df, chart_file)
        chart_url = url_for('static', filename=CHART_FILE)
    return render_template_string(HTML, summary=summary, chart_url=chart_url)


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
