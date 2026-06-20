from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# CSV load
df = pd.read_csv("price.csv")

@app.route("/", methods=["GET", "POST"])
def home():

    results = []

    if request.method == "POST":

        search = request.form["search"].strip().lower()

        for _, row in df.iterrows():

            try:
                code = str(row.iloc[0]).lower()
                desc = str(row.iloc[1]).lower()

                if search in code or search in desc:
                    results.append(row)

                if len(results) >= 10:
                    break

            except:
                pass

    return render_template("index.html", results=results)

if __name__ == "__main__":
    app.run()
