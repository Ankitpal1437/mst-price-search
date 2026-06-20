from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# Load CSV once when app starts
df = pd.read_csv("price.csv")

# Clean data
df["CODE"] = df["CODE"].astype(str).str.strip()
df["DESCRIPTION"] = df["DESCRIPTION"].astype(str).str.strip()

@app.route("/", methods=["GET", "POST"])
def home():

    results = []

    if request.method == "POST":

        search = request.form.get("search", "").strip()

        if search:

            search_lower = search.lower()

            # Exact code match
            exact = df[
                df["CODE"].str.lower() == search_lower
            ]

            # Starts with
            starts = df[
                df["CODE"].str.lower().str.startswith(search_lower)
            ]

            # Contains code or description
            contains = df[
                df["CODE"].str.lower().str.contains(search_lower, na=False)
                |
                df["DESCRIPTION"].str.lower().str.contains(search_lower, na=False)
            ]

            final = pd.concat([
                exact,
                starts,
                contains
            ]).drop_duplicates()

            results = final.head(20).to_dict("records")

    return render_template(
        "index.html",
        results=results
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
