"""Small educational ML classifier trained on illustrative messages bundled with this project.
Not suitable for real financial decisions; evaluate on a representative labeled dataset first.
"""
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Small starter examples are intentionally visible for a student project. They are not a
# representative production dataset and must not be used to claim real-world accuracy.
TRAINING_DATA = [
    ("Your bank account will be blocked today share your OTP immediately", 1),
    ("Congratulations you won a lottery claim your prize by paying a processing fee", 1),
    ("Urgent KYC update click this link or your account will be suspended", 1),
    ("Send money now to unlock your refund", 1),
    ("Your UPI payment failed refund available verify your PIN at this link", 1),
    ("Install AnyDesk so our customer care agent can help recover your money", 1),
    ("You have won a free gift pay delivery charges now", 1),
    ("Police case will be filed unless you transfer funds immediately", 1),
    ("Share your password and verification code to avoid account closure", 1),
    ("Investment guaranteed double your money today send deposit", 1),
    ("Your parcel is held pay a small fee through this shortened link", 1),
    ("Dear customer your wallet is locked confirm OTP to reactivate", 1),
    ("Claim unclaimed cashback before it expires today", 1),
    ("Refund processing fee required to release your payment", 1),
    ("Download this APK for a bank reward and enter your PIN", 1),
    ("Final warning account blocked permanently act now", 1),
    ("Please transfer money to this new account and keep it secret", 1),
    ("We need your card number CVV and OTP to reverse a transaction", 1),
    ("Your electricity will be disconnected tonight pay now using this link", 1),
    ("A prize has been selected for you pay tax to receive it", 1),
    ("Your appointment is confirmed for tomorrow at 3 PM", 0),
    ("Thank you for your order your package will arrive Friday", 0),
    ("The meeting has moved to room 204 at 10 AM", 0),
    ("Your monthly bank statement is ready in the official banking app", 0),
    ("Payment received successfully for your electricity bill", 0),
    ("Please call me when you reach the college", 0),
    ("Your booking confirmation number is 438291", 0),
    ("Reminder your subscription renews next month", 0),
    ("The transfer you initiated has been completed", 0),
    ("Your package delivery is scheduled for Monday", 0),
    ("Please review the attached meeting agenda before Friday", 0),
    ("Your salary slip is available in the employee portal", 0),
    ("Thanks for contacting support your ticket has been created", 0),
    ("The library will close at 5 PM today", 0),
    ("Your appointment reminder from the clinic is tomorrow morning", 0),
    ("Your online payment receipt is ready to download from the app", 0),
    ("The class schedule has been updated on the college website", 0),
    ("We received your request and will respond within two business days", 0),
    ("Your order has shipped and tracking is available in your account", 0),
    ("Please verify the delivery time with the official courier app", 0),
]

@lru_cache(maxsize=1)
def get_model():
    texts = [row[0] for row in TRAINING_DATA]
    labels = [row[1] for row in TRAINING_DATA]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    model.fit(texts, labels)
    return model

def predict_fraud_probability(message: str) -> float:
    """Return an illustrative model score between 0 and 1."""
    model = get_model()
    return float(model.predict_proba([message])[0][1])
