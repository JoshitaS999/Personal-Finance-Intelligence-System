from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = "finance.db"

CATEGORIES = [
    "Salary", "Freelance", "Food", "Transport", "Shopping",
    "Bills", "Rent", "Education", "Health", "Entertainment",
    "Investment", "Other"
]

PAYMENT_METHODS = [
    "Cash", "UPI", "Debit Card", "Credit Card", "Bank Transfer", "Other"
]


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            transaction_date TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Other',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    columns = [row["name"] for row in conn.execute(
        "PRAGMA table_info(transactions)"
    ).fetchall()]

    if "payment_method" not in columns:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'Other'"
        )

    if "user_id" not in columns:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN user_id INTEGER"
        )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            UNIQUE(user_id, category),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    budget_columns = [row["name"] for row in conn.execute(
        "PRAGMA table_info(budgets)"
    ).fetchall()]

    if "user_id" not in budget_columns:
        conn.execute("ALTER TABLE budgets ADD COLUMN user_id INTEGER")

    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT id, username, email FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not username or not email or not password:
            flash("All fields are required.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.")
            return render_template("register.html")

        conn = get_db()

        existing = conn.execute(
            "SELECT id FROM users WHERE username=? OR email=?",
            (username, email)
        ).fetchone()

        if existing:
            conn.close()
            flash("Username or email already exists.")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        conn.commit()
        conn.close()

        flash("Registration successful. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Login successful.")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


def totals():
    user_id = session["user_id"]

    conn = get_db()
    income = conn.execute(
        """SELECT COALESCE(SUM(amount), 0)
           FROM transactions
           WHERE type='income' AND user_id=?""",
        (user_id,)
    ).fetchone()[0]

    expense = conn.execute(
        """SELECT COALESCE(SUM(amount), 0)
           FROM transactions
           WHERE type='expense' AND user_id=?""",
        (user_id,)
    ).fetchone()[0]

    conn.close()
    return income, expense, income - expense


@app.route("/")
@login_required
def dashboard():
    income, expense, balance = totals()
    user_id = session["user_id"]

    conn = get_db()

    recent = conn.execute(
        """SELECT * FROM transactions
           WHERE user_id=?
           ORDER BY transaction_date DESC, id DESC
           LIMIT 8""",
        (user_id,)
    ).fetchall()

    category_rows = conn.execute(
        """SELECT category, SUM(amount) AS total
           FROM transactions
           WHERE type='expense' AND user_id=?
           GROUP BY category
           ORDER BY total DESC""",
        (user_id,)
    ).fetchall()

    year_row = conn.execute(
        """SELECT MAX(strftime('%Y', transaction_date)) AS year
           FROM transactions
           WHERE user_id=?""",
        (user_id,)
    ).fetchone()

    chart_year = int(year_row["year"]) if year_row["year"] else date.today().year

    monthly_rows = conn.execute(
        """SELECT strftime('%m', transaction_date) AS month,
                  COALESCE(SUM(amount), 0) AS total
           FROM transactions
           WHERE type='expense'
             AND user_id=?
             AND strftime('%Y', transaction_date)=?
           GROUP BY strftime('%m', transaction_date)
           ORDER BY month""",
        (user_id, str(chart_year))
    ).fetchall()

    conn.close()

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    monthly_spending = [0] * 12
    for row in monthly_rows:
        index = int(row["month"]) - 1
        monthly_spending[index] = float(row["total"])

    savings = balance
    savings_percent = (savings / income * 100) if income else 0

    return render_template(
        "dashboard.html",
        income=income,
        expense=expense,
        balance=balance,
        savings=savings,
        savings_percent=savings_percent,
        recent=recent,
        category_rows=category_rows,
        month_names=month_names,
        monthly_spending=monthly_spending,
        chart_year=chart_year
    )


@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    if request.method == "POST":
        return save_transaction("income")

    return render_template(
        "form.html",
        title="Add Income",
        kind="income",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=date.today().isoformat()
    )


@app.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    if request.method == "POST":
        return save_transaction("expense")

    return render_template(
        "form.html",
        title="Add Expense",
        kind="expense",
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=date.today().isoformat()
    )


def save_transaction(kind):
    user_id = session["user_id"]
    category = request.form["category"].strip()
    amount_text = request.form["amount"].strip()
    description = request.form["description"].strip()
    transaction_date = request.form["transaction_date"]
    payment_method = request.form["payment_method"]

    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Please enter a valid amount greater than zero.")
        return redirect(url_for("income" if kind == "income" else "expense"))

    conn = get_db()

    conn.execute(
        """INSERT INTO transactions
           (user_id, type, category, amount, description,
            transaction_date, payment_method)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            kind,
            category,
            amount,
            description,
            transaction_date,
            payment_method
        )
    )

    conn.commit()
    conn.close()

    flash(f"{kind.title()} added successfully.")
    return redirect(url_for("transactions"))


@app.route("/transactions")
@login_required
def transactions():
    user_id = session["user_id"]

    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM transactions
           WHERE user_id=?
           ORDER BY transaction_date DESC, id DESC""",
        (user_id,)
    ).fetchall()
    conn.close()

    return render_template("transactions.html", transactions=rows)


@app.route("/edit/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    user_id = session["user_id"]

    conn = get_db()

    transaction = conn.execute(
        """SELECT * FROM transactions
           WHERE id=? AND user_id=?""",
        (transaction_id, user_id)
    ).fetchone()

    if transaction is None:
        conn.close()
        flash("Transaction not found.")
        return redirect(url_for("transactions"))

    if request.method == "POST":
        category = request.form["category"].strip()
        amount_text = request.form["amount"].strip()
        description = request.form["description"].strip()
        transaction_date = request.form["transaction_date"]
        payment_method = request.form["payment_method"]

        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            conn.close()
            flash("Please enter a valid amount greater than zero.")
            return redirect(
                url_for("edit_transaction", transaction_id=transaction_id)
            )

        conn.execute(
            """UPDATE transactions
               SET category=?, amount=?, description=?,
                   transaction_date=?, payment_method=?
               WHERE id=? AND user_id=?""",
            (
                category,
                amount,
                description,
                transaction_date,
                payment_method,
                transaction_id,
                user_id
            )
        )

        conn.commit()
        conn.close()

        flash("Transaction updated successfully.")
        return redirect(url_for("transactions"))

    conn.close()

    return render_template(
        "edit_transaction.html",
        transaction=transaction,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS
    )


@app.route("/delete/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    user_id = session["user_id"]

    conn = get_db()
    conn.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?",
        (transaction_id, user_id)
    )
    conn.commit()
    conn.close()

    flash("Transaction deleted.")
    return redirect(url_for("transactions"))

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    user_id = session["user_id"]

    if request.method == "POST":
        category = request.form["category"].strip()

        try:
            amount = float(request.form["amount"])

            if amount <= 0:
                raise ValueError

        except ValueError:
            flash("Please enter a valid budget amount greater than zero.")
            return redirect(url_for("budget"))

        conn = get_db()

        existing = conn.execute(
            """
            SELECT id
            FROM budgets
            WHERE user_id=? AND LOWER(category)=LOWER(?)
            """,
            (user_id, category)
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE budgets
                SET amount=?, category=?
                WHERE id=? AND user_id=?
                """,
                (amount, category, existing["id"], user_id)
            )
        else:
            conn.execute(
                """
                INSERT INTO budgets (user_id, category, amount)
                VALUES (?, ?, ?)
                """,
                (user_id, category, amount)
            )

        conn.commit()
        conn.close()

        flash("Budget saved successfully.")
        return redirect(url_for("budget"))

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            b.id,
            b.category,
            b.amount,
            COALESCE(SUM(t.amount), 0) AS spent
        FROM budgets b
        LEFT JOIN transactions t
            ON LOWER(t.category)=LOWER(b.category)
            AND t.type='expense'
            AND t.user_id=?
            AND strftime('%Y-%m', t.transaction_date)
                = strftime('%Y-%m', 'now')
        WHERE b.user_id=?
        GROUP BY b.id
        ORDER BY b.category
        """,
        (user_id, user_id)
    ).fetchall()

    conn.close()

    budgets = []

    for row in rows:
        spent = row["spent"]
        amount = row["amount"]

        raw_percent = (spent / amount * 100) if amount else 0

        budgets.append({
            "id": row["id"],
            "category": row["category"],
            "amount": amount,
            "spent": spent,
            "remaining": amount - spent,
            "percent": min(raw_percent, 100),
            "percent_text": round(raw_percent),
            "over_budget": raw_percent > 100
        })

    return render_template(
        "budget.html",
        budgets=budgets,
        categories=CATEGORIES
    )


@app.route("/budget/delete/<int:budget_id>", methods=["POST"])
@login_required
def delete_budget(budget_id):
    user_id = session["user_id"]

    conn = get_db()
    conn.execute(
        "DELETE FROM budgets WHERE id=? AND user_id=?",
        (budget_id, user_id)
    )
    conn.commit()
    conn.close()

    flash("Budget deleted.")
    return redirect(url_for("budget"))


@app.route("/insights")
@login_required
def insights():
    income, expense, balance = totals()
    user_id = session["user_id"]

    conn = get_db()

    categories = conn.execute(
        """SELECT category, SUM(amount) AS total
           FROM transactions
           WHERE type='expense' AND user_id=?
           GROUP BY category
           ORDER BY total DESC""",
        (user_id,)
    ).fetchall()

    conn.close()

    savings_rate = (balance / income * 100) if income else 0
    messages = []

    if income == 0 and expense == 0:
        messages.append(
            "Add your first income and expense to start receiving insights."
        )
    else:
        if balance < 0:
            messages.append(
                "Your recorded expenses are higher than your recorded income."
            )
        elif savings_rate >= 20:
            messages.append(
                "Your current recorded savings rate is 20% or more."
            )
        else:
            messages.append(
                "Your current recorded savings rate is below 20%."
            )

        if categories:
            top = categories[0]
            messages.append(
                f"Your largest expense category is {top['category']} "
                f"at ₹{top['total']:,.2f}."
            )

    return render_template(
        "insights.html",
        income=income,
        expense=expense,
        balance=balance,
        savings_rate=savings_rate,
        categories=categories,
        messages=messages
    )



@app.route("/financial-intelligence")
@login_required
def financial_intelligence():
    user_id = session["user_id"]
    today = date.today()
    month_start = today.replace(day=1)
    previous_month = (month_start.replace(day=1) - __import__("datetime").timedelta(days=1)).replace(day=1)
    current_key = month_start.strftime("%Y-%m")
    previous_key = previous_month.strftime("%Y-%m")

    conn = get_db()
    current_spending = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) FROM transactions
           WHERE user_id=? AND type='expense' AND strftime('%Y-%m', transaction_date)=?""",
        (user_id, current_key)
    ).fetchone()[0]
    previous_spending = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) FROM transactions
           WHERE user_id=? AND type='expense' AND strftime('%Y-%m', transaction_date)=?""",
        (user_id, previous_key)
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT id, category, amount, description, transaction_date
           FROM transactions WHERE user_id=? AND type='expense'
           ORDER BY transaction_date DESC, id DESC""", (user_id,)
    ).fetchall()
    conn.close()

    if previous_spending:
        change = (current_spending - previous_spending) / previous_spending * 100
    else:
        change = None

    recurring_groups = {}
    category_groups = {}
    for row in rows:
        amount = float(row["amount"])
        category = (row["category"] or "Other").strip()
        description = (row["description"] or "").strip()
        key = description.lower() if description else category.lower()
        recurring_groups.setdefault(key, []).append(row)
        category_groups.setdefault(category.lower(), []).append(row)

    recurring = []
    for key, items in recurring_groups.items():
        months = {item["transaction_date"][:7] for item in items if item["transaction_date"]}
        amounts = [float(item["amount"]) for item in items]
        if len(months) < 2 or len(amounts) < 2:
            continue
        average = sum(amounts) / len(amounts)
        if average and all(abs(value-average)/average <= 0.20 for value in amounts):
            recurring.append({"name": items[0]["description"] or items[0]["category"], "amount": average, "count": len(items)})

    anomalies = []
    for row in rows:
        category_rows = category_groups[(row["category"] or "Other").lower()]
        other_amounts = [float(item["amount"]) for item in category_rows if item["id"] != row["id"]]
        amount = float(row["amount"])
        if len(other_amounts) < 3:
            continue
        normal_min, normal_max = min(other_amounts), max(other_amounts)
        average = sum(other_amounts) / len(other_amounts)
        if amount > normal_max * 1.5 or (average > 0 and amount >= average * 2):
            anomalies.append({"category": row["category"], "amount": amount, "date": row["transaction_date"], "normal_min": normal_min, "normal_max": normal_max, "description": row["description"]})

    return render_template("financial_intelligence.html", current_spending=current_spending,
        previous_spending=previous_spending, change=change, recurring=recurring, anomalies=anomalies)


@app.route("/machine-learning", methods=["GET", "POST"])
@login_required
def machine_learning():
    from pathlib import Path
    import pandas as pd
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression, LinearRegression
    from sklearn.ensemble import IsolationForest

    user_id = session["user_id"]
    conn = get_db()
    training_rows = conn.execute(
        """SELECT description, category, amount, transaction_date FROM transactions
           WHERE user_id=? AND type='expense' AND description IS NOT NULL AND TRIM(description)!=''""",
        (user_id,)
    ).fetchall()
    all_expenses = conn.execute(
        """SELECT amount, transaction_date FROM transactions
           WHERE user_id=? AND type='expense' ORDER BY transaction_date""", (user_id,)
    ).fetchall()
    conn.close()

    # Synthetic examples help bootstrap the text model; personal records stay user-specific.
    dataset_path = Path(__file__).resolve().parent / "datasets" / "personal_expense_dataset.csv"
    training_data = []
    if dataset_path.exists():
        demo_df = pd.read_csv(dataset_path)
        demo_df = demo_df[demo_df["type"] == "expense"].dropna(subset=["description", "category"])
        category_map = {"Travel": "Other", "Personal Care": "Other"}
        for _, item in demo_df.iterrows():
            training_data.append((str(item["description"]), category_map.get(str(item["category"]), str(item["category"]))))

    for row in training_rows:
        training_data.append((str(row["description"]), str(row["category"])))

    prediction = None
    prediction_message = None
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        if not description:
            flash("Enter a transaction description first.")
        elif len(training_data) < 4 or len({label for _, label in training_data}) < 2:
            prediction_message = "Add more categorized expense examples to train the category model."
        else:
            texts = [text.lower() for text, _ in training_data]
            labels = [label for _, label in training_data]
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            features = vectorizer.fit_transform(texts)
            model = LogisticRegression(max_iter=1000, class_weight="balanced")
            model.fit(features, labels)
            prediction = model.predict(vectorizer.transform([description.lower()]))[0]

    # Forecast and anomaly detection use only the signed-in user's own transactions.
    monthly = {}
    for row in all_expenses:
        if row["transaction_date"]:
            key = row["transaction_date"][:7]
            monthly[key] = monthly.get(key, 0) + float(row["amount"])
    forecast = None
    if len(monthly) >= 3:
        keys = sorted(monthly)
        values = [monthly[k] for k in keys]
        trend = LinearRegression().fit(np.arange(len(values)).reshape(-1, 1), values)
        forecast = max(0, float(trend.predict([[len(values)]])[0]))

    anomaly_rows = []
    amounts = [float(r["amount"]) for r in all_expenses]
    if len(amounts) >= 5:
        detector = IsolationForest(contamination=0.10, random_state=42)
        labels = detector.fit_predict(np.array(amounts).reshape(-1, 1))
        for row, label in zip(all_expenses, labels):
            if label == -1:
                anomaly_rows.append({"amount": float(row["amount"]), "date": row["transaction_date"]})

    return render_template(
        "machine_learning.html", prediction=prediction,
        prediction_message=prediction_message, training_count=len(training_data),
        forecast=forecast, monthly_count=len(monthly), anomalies=anomaly_rows,
        demo_count=len(training_data) - len(training_rows), personal_count=len(training_rows)
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
