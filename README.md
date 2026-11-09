
# Personal Finance System — Stage 1

Flask + SQLite personal finance application with authentication.

## Stage 1 features

- User registration
- User login
- User logout
- Password hashing with Werkzeug
- Session-based authentication
- User-specific transactions
- User-specific budgets
- Edit/delete protected by logged-in user
- Categories
- Payment methods
- Dashboard
- Financial insights

## Run

Activate your existing virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install requirements:

```powershell
pip install -r requirements.txt
```

Start:

```powershell
python app.py
```

Open:

http://127.0.0.1:5000

## Important

For real deployment, change `app.secret_key` to a long random secret stored in an environment variable.

The application automatically adds the authentication fields to an existing Stage 2 database where possible.


## Stage 2 — Dashboard

Stage 2 adds:
- Total Income
- Total Expenses
- Balance
- Savings
- Savings %
- Monthly Spending bar chart for the latest transaction year
- Existing recent transactions and expense breakdown

The dashboard calculations are user-specific.


## Stage 3 — Budget Management
- Create or update monthly budgets by category
- Track current-month spending against each budget
- Show spending amount, budget amount, remaining amount, and percentage
- Highlight categories that exceed their budget
- Budgets remain user-specific


## Stage 4 — Financial Intelligence
Open **Financial Intelligence** from the navigation after logging in. It compares current and previous month expenses, detects similar expenses repeated across different months, and flags unusually high transactions compared with other transactions in the same category. Detection uses your own transaction history and requires enough data.


## Stage 5 — Machine Learning

Install the updated dependencies with `pip install -r requirements.txt`. Start the app with `python app.py` and open **Machine Learning** from the sidebar.

- Category prediction trains TF-IDF + Logistic Regression on the signed-in user's described expense transactions. It needs at least 4 examples and 2 categories.
- Monthly expense forecasting uses Linear Regression after at least 3 months of data.
- Amount anomaly detection uses Isolation Forest after at least 5 expense records.

Models are trained from the user's own SQLite transaction history when the page is opened; no transaction data is sent to an external service. Results are experimental and should be treated as suggestions, not financial advice.


## Stage 6 — Dataset integration

The `datasets/personal_expense_dataset.csv` file contains synthetic example transactions for five fictional users. It is included as **training/demo data**, not imported into `finance.db`. The category model trains on the sample descriptions plus the currently signed-in user's categorized expense descriptions. Sample categories not supported by the app are mapped to `Other`. Monthly forecasting and Isolation Forest anomaly detection use only the signed-in user's own SQLite transactions.

The CSV is synthetic and should not be treated as real financial data. To replace or extend it, keep the columns `type`, `description`, and `category` available for category training.
