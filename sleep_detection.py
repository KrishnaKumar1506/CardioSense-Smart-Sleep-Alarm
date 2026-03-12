# %%
import pandas as pd 
import numpy as np 
df=pd.read_csv("ecg_sleep_features_new.csv")
df.isnull().sum()

# %%
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
x= df.drop(columns=["label", "timestamp"])  # Features
y = df["label"]   


# %%
x

# %%
xtr, xt, ytr, yt = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)


# %%
xtr

# %%
rf = RandomForestClassifier(n_estimators=200,max_depth=10,random_state=42)
rf.fit(xtr, ytr)

# %%
y_pred = rf.predict(xt)

# %%
acc = accuracy_score(yt, y_pred)
print(f"\n Accuracy: {acc*100:.2f}%\n")
print("🔍 Classification Report:")
print(classification_report(yt, y_pred))

# %%
cm = confusion_matrix(yt, y_pred, labels=rf.classes_)
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=rf.classes_, yticklabels=rf.classes_)
plt.title("Confusion Matrix - Sleep Stage Classification")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.show()

# %%
importances = pd.Series(rf.feature_importances_, index=x.columns).sort_values(ascending=False)
plt.figure(figsize=(8, 5))
sns.barplot(x=importances.values, y=importances.index, palette="viridis")
plt.title("Feature Importance (Random Forest)")
plt.xlabel("Importance")
plt.ylabel("Feature")
plt.show()

# %%

import joblib
joblib.dump(rf, "sleep_stage_rf_model.pkl")
print("✅ Model saved as 'sleep_stage_rf_model.pkl'")

loaded_model = joblib.load("sleep_stage_rf_model.pkl")
print("✅ Model loaded successfully!")


sample = xt.iloc[0].values.reshape(1, -1)
predicted_label = loaded_model.predict(sample)[0]
print("🧠 Predicted Sleep Stage:", predicted_label)



# %%



