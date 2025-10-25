# 📊 Futures Trade Journal

An AI-powered trading journal web application that tracks, analyzes, and provides AI feedback on your futures trading performance. Built with Flask, Supabase, and Perplexity AI.

## Features

### Dashboard
- **Trade Overview**: Real-time statistics including win rate, net profit, average profit, risk/reward ratio, and expectancy
- **Multi-Account Support**: Track and compare performance across multiple trading accounts
- **Strategy Performance**: Analyze profitability by trading strategy
- **Visual Charts**: Interactive charts showing cumulative profit, win/loss distribution, profit distribution, and profit by strategy/account
- **Date Range Filtering**: Filter trades by custom date ranges or quick presets (Today, This Week, This Month, All Time)
- **CSV Upload**: Import trade data directly from NinjaTrader CSV exports

### Trade Analysis
- **Trade Listing**: View all trades in a detailed table with entry/exit prices, P&L, MAE, and MFE
- **Trade Selection**: Multi-select trades for batch analysis
- **AI-Powered Feedback**: Get expert analysis on entry/exit quality, risk management, and execution using Perplexity AI
- **Actionable Insights**: Specific feedback on how to improve your trading execution

## Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Backend**: Python Flask
- **Database**: Supabase (PostgreSQL)
- **AI**: Perplexity AI API
- **Charting**: Matplotlib
- **Hosting**: Render
- **Data Processing**: Pandas

## Project Structure

```
futures-trade-journal/
├── journal.py                          # Main Flask application
├── requirements.txt                    # Python dependencies
├── .env                               # Environment variables (local only)
├── .gitignore                         # Git ignore configuration
├── static/                            # Generated charts and assets
│   ├── profit_curve.png
│   ├── win_loss.png
│   ├── profit_dist.png
│   ├── strategy_profit.png
│   └── account_profit.png
├── data/                              # Local CSV data (ignored)
│   └── *.csv
└── README.md                          # This file
```

## Installation

### Prerequisites
- Python 3.8+
- Git
- Supabase account (free tier available)
- Perplexity AI API key

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/futures-trade-journal.git
   cd futures-trade-journal
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   PERPLEXITY_API_KEY=pplx-your-api-key
   ```

5. **Run the application**
   ```bash
   python journal.py
   ```

   Access the app at `http://localhost:5000`

## Deployment (Render)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Create Render Service**
   - Go to [Render.com](https://render.com)
   - Create new Web Service
   - Connect your GitHub repository
   - Select the `main` branch

3. **Set Environment Variables on Render**
   - Go to Service → Environment
   - Add the following:
     - `SUPABASE_URL`: Your Supabase URL
     - `SUPABASE_KEY`: Your Supabase anon key
     - `PERPLEXITY_API_KEY`: Your Perplexity API key

4. **Configure Build & Start**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn journal:app`

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy your app

## Usage

### Dashboard (Home Page)

1. **Upload CSV**
   - Export trades from NinjaTrader as CSV
   - Click "Upload CSV" and select your file
   - Trades are automatically added to the database

2. **Filter Trades**
   - Use account dropdown to filter by account
   - Use date range inputs for custom date filtering
   - Click quick filter buttons (Today, This Week, This Month, All Time)

3. **View Analytics**
   - Stats cards show key metrics
   - Strategy Performance table breaks down by strategy
   - Account Comparison compares performance across accounts
   - Charts visualize profit curves, outcomes, distributions, and strategy/account performance

### Analysis Page

1. **Navigate to Trade Analysis**
   - Click "🔍 Trade Analysis" link on dashboard

2. **Select Trades**
   - Check boxes next to trades you want to analyze
   - Use "Select All" checkbox to select all visible trades

3. **Get AI Feedback**
   - Click "Analyze Selected Trades"
   - Wait for Perplexity AI to analyze your trades
   - Review feedback on entry/exit quality, risk management, and execution ratings

## CSV Format (NinjaTrader)

Expected CSV columns from NinjaTrader export:
```
Trade number, Instrument, Account, Strategy, Market pos., Qty, Entry price, Exit price, 
Entry time, Exit time, Entry name, Exit name, Profit, Cum. net profit, Commission, MAE, MFE
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard home page |
| GET | `/analysis` | Trade analysis page |
| POST | `/analyze` | AI trade analysis endpoint |
| POST | `/upload` | CSV file upload endpoint |

## Statistics Calculated

- **Win Rate**: Percentage of winning trades
- **Total Profit/Loss**: Sum of all P&L
- **Average Profit**: Mean P&L per trade
- **Largest Win/Loss**: Best and worst individual trades
- **Risk/Reward Ratio**: Average win divided by average loss
- **Expectancy**: Expected value per trade (probability × outcome)
- **Net Profit**: Cumulative profit as of last trade

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Your Supabase project URL | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon key | `eyJhbGc...` |
| `PERPLEXITY_API_KEY` | Your Perplexity API key | `pplx-xxxx` |

## Troubleshooting

### "Connection error" when analyzing trades
- Verify `PERPLEXITY_API_KEY` is set correctly on Render
- Check Render logs for detailed error messages
- Ensure your Perplexity account is active and has API credits

### No trades showing on dashboard
- Make sure CSV file is formatted correctly
- Check that file contains required columns
- Verify trades have exit times within your date filter range

### Charts not displaying
- Ensure trade data has required columns (entry_time, exit_time, profit, cum_net_profit)
- Check Render logs for matplotlib errors
- Try uploading additional trades if dataset is too small

## Future Enhancements

- [ ] Price chart overlays at entry/exit points
- [ ] Advanced filtering and sorting options
- [ ] Trade performance heatmaps
- [ ] Monthly/yearly performance reports
- [ ] Trade setup pattern recognition
- [ ] Performance benchmarking
- [ ] Mobile app
- [ ] Real-time trade syncing
- [ ] Multiple file upload support
- [ ] Export analysis results as PDF

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Contact the developer

## Acknowledgments

- Perplexity AI for trade analysis
- Supabase for database hosting
- Render for application hosting
- NinjaTrader for trade data export format

---

**Last Updated**: October 25, 2025  
**Version**: 1.0.0  
**Status**: Active Development


ToDo

1. **Verify Data Upload and Display**
   - Confirm that uploaded CSV rows are properly inserted into Supabase
   - Confirm the dashboard metrics update accordingly on upload
   - Fix any remaining parsing or display issues from test uploads

2. **Polish User Interface**
   - Enhance form UI/UX to show upload success or errors clearly
   - Add pagination or search/filter for large numbers of trades
   - Add export/download buttons for reports or charts

3. **Add User Authentication**
   - Use Supabase auth to allow multiple users
   - Secure trade data to each user account
   - Add login/register pages

4. **Expand Analytics**
   - Add new chart types like monthly P&L, instrument-wise stats, HOD/LOL analysis
   - Implement strategy comparison over time
   - Add trade journal notes and tagging features

5. **Improve Performance & Scalability**
   - Cache frequent queries
   - Optimize database indexes and fetches

6. **Automate CSV Uploads**
   - Consider automating CSV extract from NinjaTrader via APIs or scheduled upload scripts

7. **Backup & Data Export**
   - Add options to backup Supabase data or export all trades to CSV/Excel for offline use

