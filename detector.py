import re
from urllib.parse import urlparse

# Transparent demo rules. This is a screening aid, not a trained fraud model.
RULES = [
    ("Urgency or pressure", 18, [
        r"\bimmediately\b", r"\burgent\b", r"\bwithin\s+\d+\s*(minutes?|hours?)\b",
        r"\bact now\b", r"\bexpires? today\b", r"\blast warning\b", r"\baccount will be blocked\b"
    ]),
    ("Requests for credentials or OTP", 28, [
        r"\botp\b", r"\bpin\b", r"\bpassword\b", r"\bverification code\b",
        r"\bshare (?:your )?(?:otp|pin|password|code)\b"
    ]),
    ("Payment or transfer pressure", 20, [
        r"\bpay now\b", r"\btransfer (?:money|funds)\b", r"\bsend money\b",
        r"\bprocessing fee\b", r"\bpay a fee\b", r"\brefund fee\b"
    ]),
    ("Prize, reward, or unexpected refund", 14, [
        r"\byou (?:have )?won\b", r"\bclaim your prize\b", r"\bfree gift\b",
        r"\bcashback\b", r"\bunclaimed refund\b", r"\blottery\b"
    ]),
    ("Threats or account suspension", 18, [
        r"\blegal action\b", r"\bpolice case\b", r"\barrest\b",
        r"\bsuspended\b", r"\bblocked permanently\b", r"\baccount has been locked\b"
    ]),
    ("Remote-access or app installation request", 22, [
        r"\binstall (?:this )?app\b", r"\bremote access\b", r"\bscreen sharing\b",
        r"\banydesk\b", r"\bteamviewer\b", r"\bdownload the apk\b"
    ]),
]

URL_RE = re.compile(r"(https?://[^\s<>\]\[\"']+|www\.[^\s<>\]\[\"']+)", re.I)

def analyze_message(message: str) -> dict:
    text = message.lower()
    signals = []
    score = 0

    for label, weight, patterns in RULES:
        if any(re.search(pattern, text, re.I) for pattern in patterns):
            signals.append({"label": label, "detail": _detail(label), "weight": weight})
            score += weight

    urls = URL_RE.findall(message)
    suspicious_urls = []
    for raw in urls:
        normalized = raw if raw.lower().startswith(("http://", "https://")) else "http://" + raw
        host = (urlparse(normalized).hostname or "").lower()
        if host and (host.startswith("xn--") or re.search(r"\d+\.\d+\.\d+\.\d+", host) or
                     any(x in host for x in ["bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd"])):
            suspicious_urls.append(raw)
    if suspicious_urls:
        signals.append({
            "label": "Link needs extra verification",
            "detail": "A shortened or unusual-looking link was found. Check the destination independently.",
            "weight": 15
        })
        score += 15

    if re.search(r"\b(bank|paypal|upi|wallet|support|customer care|kyc)\b", text) and urls:
        signals.append({
            "label": "Financial-service wording plus a link",
            "detail": "The message mentions a financial service and includes a link. Open the official app or website yourself instead.",
            "weight": 8
        })
        score += 8

    score = min(score, 100)
    if score >= 60:
        level, title = "high", "High risk indicators"
        summary = "This message contains several warning signs commonly associated with scams."
    elif score >= 30:
        level, title = "medium", "Some warning signs found"
        summary = "This message includes warning signs worth checking carefully."
    else:
        level, title = "low", "Fewer warning signs detected"
        summary = "The demo detector found fewer known warning signs. This does not prove the message is safe."

    tips = [
        "Never share an OTP, PIN, password, or full card details with anyone.",
        "Do not use links or phone numbers in an unexpected message; contact the organization through its official app or website.",
        "Do not send money to unlock a prize, refund, account, or job offer.",
        "If you already paid or shared sensitive details, contact your bank or payment provider immediately."
    ]
    return {
        "score": score,
        "level": level,
        "title": title,
        "summary": summary,
        "signals": signals,
        "tips": tips,
        "urls_found": len(urls),
        "disclaimer": "PayGuard AI is a student demo that uses transparent text-matching rules. It can miss scams or flag legitimate messages. It does not verify links, contact banks, or guarantee a transaction is safe."
    }

def _detail(label):
    details = {
        "Urgency or pressure": "Scammers often pressure people to act before they have time to verify a request.",
        "Requests for credentials or OTP": "Legitimate support staff should not ask you to reveal your OTP, PIN, or password.",
        "Payment or transfer pressure": "Unexpected demands to pay or transfer money should be independently verified.",
        "Prize, reward, or unexpected refund": "Unexpected prizes or refunds can be used to persuade people to share details or pay fees.",
        "Threats or account suspension": "Threatening language can be used to frighten people into acting quickly.",
        "Remote-access or app installation request": "Remote-access tools can allow another person to view or control your device.",
    }
    return details.get(label, "Review this indicator and verify the request independently.")
