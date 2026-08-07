import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "raw", "ett", "ETTm1.csv")
MODELS_DIR = os.path.join(BASE_DIR, "maintenance")

def main():
    print("Loading ETTm1 transformer load dataset...")
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"ETTm1.csv not found at {DATA_PATH}. Please download it.")
        
    df = pd.read_csv(DATA_PATH)
    
    # ETTm1 columns: date, HUFL, HULL, MUFL, MULL, LUFL, LULL, OT
    # Features: load measurements
    feature_cols = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL"]
    X = df[feature_cols].values
    
    # Create target: Failure risk is High (1) if Oil Temperature (OT) > 30.0 or High Use Load (HUFL) > 8.0
    # Otherwise low (0)
    print("Creating failure risk labels based on oil temperature and loads...")
    y = ((df["OT"] > 30.0) | (df["HUFL"] > 8.0)).astype(int).values
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training RandomForestClassifier for predictive maintenance ({X_train.shape[0]} samples)...")
    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    clf.fit(X_train, y_train)
    
    # Evaluate
    preds = clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, preds, target_names=["Low Risk", "High Risk"]))
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "rf_maintenance.pkl")
    joblib.dump(clf, model_path)
    print(f"Random Forest maintenance model saved to {model_path}")

if __name__ == "__main__":
    main()
