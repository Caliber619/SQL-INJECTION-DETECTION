# http://127.0.0.1:5000/ where our project shows

from flask import Flask, request, render_template, session, redirect, url_for
from datetime import datetime
from datetime import timedelta
import joblib
import sqlite3
import re
import logging
import hashlib
import secrets

from datetime import timedelta

# Load the pre-trained machine learning model and vectorizer
def load_ml_model():
    model = joblib.load('model.pkl')  # Load the trained model
    vectorizer = joblib.load('vectorizer.pkl')  # Load the vectorizer
    return model, vectorizer

# Call this function to load the model globally
model, vectorizer = load_ml_model()

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secret key for session management

# Set session lifetime
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Function to create a sample database and users table
def setup_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Insert initial users if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, email, password) VALUES ('admin', 'admin@example.com', ?)", (hash_password('admin123'),))
        cursor.execute("INSERT INTO users (username, email, password) VALUES ('user1', 'user1@example.com', ?)", (hash_password('password1'),))
    conn.commit()
    conn.close()

# Password hashing function for security
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Validate email format
def is_valid_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

# Validate input for username and password
def is_valid_input(user_input):
    return bool(re.match("^[a-zA-Z0-9_]*$", user_input))

# Log suspicious attempts
def log_attempt(user_input):
    user_ip = request.remote_addr  # Get user IP address
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Current timestamp
    logging.info(f"[{timestamp}] Suspicious input detected from {user_ip}: {user_input}")

# Detect suspicious input patterns (SQL injection-like patterns)

# def detect_suspicious_input(user_input):
#     # Enhanced list of suspicious patterns for SQL injection detection
#     suspicious_patterns = [
#         "'", "--", ";", "/", "*", "\"", "#", "/*", "*/", " OR ", " AND "
#     ]
#     for pattern in suspicious_patterns:
#         if pattern.lower() in user_input.lower():
#             log_attempt(user_input)
#             return True
#     return False
def detect_suspicious_input(user_input):
    # First, check for known patterns like SQL injection patterns
    suspicious_patterns = [
        "'", "--", ";", "/", "*", "\"", "#", "/*", "*/", " OR ", " AND "
    ]
    for pattern in suspicious_patterns:
        if pattern.lower() in user_input.lower():
            log_attempt(user_input)
            return True
    
    # Now, use the ML model for additional detection
    input_vector = vectorizer.transform([user_input])  # Convert input to vector
    prediction = model.predict(input_vector)  # Use the model to predict
    
    if prediction == 1:  # If the model predicts 'Malicious' (1)
        log_attempt(user_input)
        return True
    
    return False


# Fetch user details safely
def fetch_user(user_input):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (user_input,))
    users = cursor.fetchall()
    conn.close()
    return users

# Register a new user
def register_user(username, email, password):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Setup the database initially
setup_database()

# Unified route to handle search, signup, login, and logout
@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    #check if the user is logged in
    logged_in = 'user_id' in session

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'search':
            if not logged_in:
                result = 'Please log in to search the users'
            else:
                search_username = request.form['search_username']
                if not is_valid_input(search_username):
                    result = "Potential SQL Injection attack Detected !!! Invalid input!"
                elif detect_suspicious_input(search_username):
                    result = "Potential SQL injection attack detected!"
                    logging.warning(f"Suspicious search attempt detected from {request.remote_addr}: Search query={search_username}")
                else:
                    users = fetch_user(search_username)
                    if users:
                        result = f"User found: {users}"
                        logging.info(f"User search successful for query '{search_username}' from {request.remote_addr}")
                    else:
                        result = "No user found."
                        logging.info(f"User search unsuccessful for query '{search_username}' from {request.remote_addr}")

                    
        elif action == 'signup' and not logged_in:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            if not is_valid_input(username):
                result = "Invalid username. Only letters, numbers, and underscores are allowed."
            elif not is_valid_email(email):
                result = "Invalid email format."
            elif len(password) < 6:
                result = "Password must be at least 6 characters long."
            elif detect_suspicious_input(username) or detect_suspicious_input(email):
                result = "Potential SQL injection attack detected!"
                logging.warning(f"Suspicious signup attempt detected from {request.remote_addr}: Username={username}, Email={email}")
            else:
                if register_user(username, email, password):
                    result = "User registered successfully!"
                    logging.info(f"New user registered: {email} from {request.remote_addr}")
                else:
                    result = "Error: Email already in use."
                    logging.warning(f"Failed signup attempt for {email} from {request.remote_addr}")

                    
        elif action == 'login' and not logged_in:
            email = request.form['email']
            password = request.form['password']
            hashed_password = hash_password(password)
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed_password))
            user = cursor.fetchone()
            conn.close()

            if detect_suspicious_input(email):
                result = "Potential SQL injection attack detected!"
                logging.warning(f"Suspicious login attempt detected from {request.remote_addr}: {email}")
            elif user:
                session.permanent = True
                session['user_id'] = user[0]
                session['username'] = user[1]
                result = "Login successful!"
                logging.info(f"Successful login for {email} from {request.remote_addr}")
            else:
                result = "Invalid credentials."
                logging.warning(f"Failed login attempt for {email} from {request.remote_addr}")

                        
        elif action == 'logout' and logged_in:
            session.clear()
            result = "You have been logged out."
            logging.info(f"User logged out from{request.remote_addr}")
    
    return render_template("index.html", result=result, logged_in=logged_in)

# Run the application
if __name__ == '__main__':
    app.run(debug=True)
