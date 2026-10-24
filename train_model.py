import os
import re
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

from category_classifier import classify_category

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "spam_or_not_spam.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "spam_model.joblib")
ENRICHED_PATH = os.path.join(BASE_DIR, "data", "spam_dataset_with_category.csv")

df = pd.read_csv(CSV_PATH)
df = df.dropna(subset=["email", "label"]).copy()
df["email"] = df["email"].astype(str);
df["label"] = df["label"].astype(int);


df["category"] = df["email"].apply(
    lambda x: classify_category("", "", x)
)
df.to_csv(ENRICHED_PATH, index=False)

X_train, X_test, y_train, y_test = train_test_split(
    df["email"],
    df["label"],
    test_size=0.20,
    random_state=42,
    stratify=df["label"],
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.98,
        sublinear_tf=True,
    )),
    ("classifier", LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )),
])

model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", round(accuracy_score(y_test, pred), 4))
print(classification_report(y_test, pred))

os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(model, MODEL_PATH)

print("\nSaved:", MODEL_PATH)
print("Saved:", ENRICHED_PATH)
