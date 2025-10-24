from flask import Flask, render_template_string, request, redirect
import pandas as pd
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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


@app.route("/", methods=["GET"])
def index():
    df = parse_all_csv(UPLOAD_FOLDER)
    summary = make_summary(df)
    return render_template_string(HTML, summary=summary)


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
