# model.py

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

def train_model(dataset_path='dataset.csv'):
    # Load the dataset
    data = pd.read_csv(dataset_path)

    # Check for missing values in the 'query' column
    print(data.isnull().sum())  # This will show how many missing values are in each column

     # Remove rows with missing values in the 'query' or 'label' columns
    data = data.dropna(subset=['query', 'label'])


    # Preprocess the data
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(data['query'])
    y = data['label']

    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train the model
    model = LogisticRegression()
    model.fit(X_train, y_train)

    # Evaluate the model
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    # Save the trained model and vectorizer
    joblib.dump(model, 'model.pkl')
    joblib.dump(vectorizer, 'vectorizer.pkl')

    print("Model and vectorizer saved successfully.")

def load_model():
    # Load the trained model and vectorizer
    model = joblib.load('model.pkl')
    vectorizer = joblib.load('vectorizer.pkl')
    return model, vectorizer

if __name__ == "__main__":
    train_model()  
    # Uncomment this to train the model
