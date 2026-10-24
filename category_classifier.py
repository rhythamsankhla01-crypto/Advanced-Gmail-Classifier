import re

CATEGORY_RULES = {
    "Promotional": [
        "sale", "offer", "discount", "coupon", "deal", "limited time",
        "shop", "shopping", "buy now", "cashback", "promo", "promotion",
        "unsubscribe", "black friday", "festival offer", "clearance",
    ],
    "College": [
        "college", "university", "semester", "exam", "assignment", "attendance",
        "professor", "faculty", "student", "campus", "lecture", "result",
        "internship", "placement", "timetable", "class", "department",
    ],
    "Business": [
        "invoice", "quotation", "proposal", "client", "meeting", "project",
        "business", "company", "contract", "payment", "purchase order",
        "deadline", "sales", "revenue", "partnership", "hr", "corporate",
    ],
    "Finance": [
        "bank", "account", "transaction", "credit card", "debit card",
        "loan", "emi", "payment", "statement", "otp", "investment",
        "mutual fund", "insurance", "upi",
    ],
    "Social": [
        "instagram", "facebook", "linkedin", "twitter", "follow", "comment",
        "like", "friend request", "social", "notification",
    ],
    "Personal": [
        "family", "friend", "birthday", "wedding", "hello", "hi",
        "miss you", "dinner", "lunch", "trip", "vacation", "photos",
        "personal", "love",
    ],
    "Updates": [
        "notification", "alert", "verification", "security", "password",
        "confirm", "confirmation", "account update", "status", "reminder",
        "newsletter", "subscription",
    ],
}

def classify_category(subject, sender, body):
    text = f"{subject} {sender} {body}".lower()
    scores = {}

    for category, keywords in CATEGORY_RULES.items():
        score = 0
        for keyword in keywords:
            score += len(re.findall(re.escape(keyword), text))
        scores[category] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "Other"
    return best
