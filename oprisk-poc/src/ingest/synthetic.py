"""Generate a realistic synthetic CFPB-style dataset for offline POC testing.

Produces ~1,200 incident narratives distributed across 8 product categories,
with realistic language, ground-truth labels, and date distribution (2021-2024).
"""
import random
from datetime import date, timedelta

import pandas as pd
from loguru import logger

SEED = 42
random.seed(SEED)

PRODUCTS = {
    "Credit card or prepaid card": 0.22,
    "Checking or savings account": 0.18,
    "Mortgage": 0.16,
    "Debt collection": 0.14,
    "Credit reporting, credit repair services, or other personal consumer reports": 0.12,
    "Student loan": 0.08,
    "Auto or consumer loan": 0.06,
    "Money transfer, virtual currency, or money service": 0.04,
}

# Narrative templates per product — realistic complaint language
TEMPLATES = {
    "Credit card or prepaid card": [
        "I noticed an unauthorized charge of ${amount} on my {issuer} credit card on {date_str}. "
        "I did not make this purchase at {merchant}. I contacted customer service and was told "
        "the dispute would take up to {days} business days. Meanwhile the charge is affecting my "
        "credit utilization. I am requesting an immediate provisional credit.",
        "My credit card ending in {last4} was declined at {merchant} despite having a ${amount} "
        "available balance. When I called {issuer}, the representative told me my account was "
        "flagged for fraud review without any prior notification. This happened {days} times in "
        "the past month causing significant embarrassment.",
        "I was charged a late fee of ${fee} even though my payment was submitted on {date_str}, "
        "three days before the due date. The bank claims the payment was received late due to "
        "a processing delay on their side. This is the {ordinal} time this has happened.",
        "{issuer} raised my APR from {old_apr}% to {new_apr}% without proper notice. "
        "I never missed a payment and my credit score is {score}. The increase was backdated "
        "to {date_str} and resulted in ${amount} in additional interest charges.",
    ],
    "Checking or savings account": [
        "My direct deposit of ${amount} from my employer was not posted to my {bank} checking "
        "account on {date_str}. I was charged {overdraft_count} overdraft fees of ${fee} each "
        "because the bank processed debits before crediting my deposit. Total fees: ${total}.",
        "Someone transferred ${amount} out of my savings account without my authorization. "
        "I received no alert despite having notifications enabled. When I reported this to "
        "{bank}, I was told the investigation would take {days} business days and I would not "
        "receive provisional credit.",
        "My account was frozen on {date_str} without any explanation. I have been a customer "
        "for {years} years with no issues. I am unable to pay my rent or utilities. Customer "
        "service cannot tell me why my account is restricted or when it will be resolved.",
        "{bank} charged me {overdraft_count} overdraft fees in a single day totaling ${total}. "
        "They reordered my transactions to process the largest first, causing multiple smaller "
        "transactions to overdraft. This practice was deemed illegal in other states.",
    ],
    "Mortgage": [
        "My mortgage servicer {servicer} misapplied ${amount} of my payment to fees instead "
        "of principal and interest on {date_str}. This resulted in a reported late payment "
        "to the credit bureaus which dropped my score by {points} points.",
        "I submitted a complete loan modification application on {date_str} and have not "
        "received a decision after {days} days. Meanwhile {servicer} initiated foreclosure "
        "proceedings even though I am in the review period. This is a dual-tracking violation.",
        "My escrow account was miscalculated, resulting in a shortage of ${amount}. "
        "{servicer} is requiring me to pay this in a lump sum or increase my monthly payment "
        "by ${monthly_increase}. I was not notified until {days} days before the deadline.",
        "The insurance company paid ${amount} for storm damage but {servicer} is holding the "
        "check in a loss draft account. It has been {days} days and repairs cannot start. "
        "I am making mortgage payments on a property I cannot live in.",
    ],
    "Debt collection": [
        "I am receiving {count} calls per day from {collector} for a debt I do not recognize. "
        "I sent a debt validation letter via certified mail on {date_str} and they have not "
        "responded within the 30-day window but continue to call.",
        "{collector} reported a collection account to the credit bureaus for ${amount} that "
        "is beyond the statute of limitations in my state ({years} years). This is a FDCPA "
        "violation. The original debt was from {original_creditor} and is clearly time-barred.",
        "I have sent {count} cease communication letters to {collector} and they continue to "
        "contact me by phone and mail. Most recently on {date_str}. I am requesting immediate "
        "cessation of all contact and documentation of violations.",
        "{collector} attempted to collect a debt from me that was discharged in bankruptcy "
        "case number {case_num} on {date_str}. This violates the automatic stay and is a "
        "contempt of court. I need this to stop immediately.",
    ],
    "Credit reporting, credit repair services, or other personal consumer reports": [
        "I disputed an account from {creditor} on my {bureau} credit report on {date_str}. "
        "The bureau completed a {days}-day investigation and said the information was verified "
        "but provided no documentation. The account shows a balance of ${amount} that I have "
        "already paid in full.",
        "There is an account from {creditor} on my credit report that does not belong to me. "
        "This appears to be a case of mixed files or identity theft. The account was opened on "
        "{date_str} in {state} and shows {late_payments} late payments.",
        "My credit score dropped {points} points after {creditor} reported a late payment "
        "that was actually paid on time. I have bank records showing the payment was received "
        "{days} days before the due date. {bureau} refuses to correct this.",
        "{bureau} is reporting a public record that was vacated by the court. I provided "
        "documentation of the court order on {date_str} and {days} days later the information "
        "is still showing. This is preventing me from qualifying for a mortgage.",
    ],
    "Student loan": [
        "My student loan servicer {servicer} miscalculated my income-driven repayment amount. "
        "Despite re-certifying on {date_str} with an income of ${income}, my payment increased "
        "by ${amount}. Three calls to customer service yielded three different explanations.",
        "I submitted a Public Service Loan Forgiveness application on {date_str}. After "
        "{months} months I was notified that {count} payments did not qualify due to loan type, "
        "despite {servicer} confirming my eligibility previously in writing.",
        "My loans were transferred from {old_servicer} to {new_servicer} on {date_str}. "
        "The transfer was mishandled — {count} payments totaling ${amount} were lost and "
        "my account now shows as delinquent. This is causing credit damage.",
        "{servicer} applied my payment of ${amount} to the wrong loans. Instead of paying "
        "the highest-interest loans first as I instructed, they distributed it equally, "
        "costing me an additional ${extra} in interest. I cannot opt out of their payment "
        "allocation system.",
    ],
    "Auto or consumer loan": [
        "The dealer {dealer} included a {product} worth ${amount} in my financing without "
        "disclosing it at the time of sale. I only discovered this when I reviewed the final "
        "contract. The lender {lender} refuses to remove it and says I must contact the dealer.",
        "My auto loan with {lender} was reported as 30 days late even though I enrolled in "
        "autopay on {date_str}. The autopay failed due to a {lender} system error and they "
        "reported the delinquency without notifying me.",
        "I paid off my auto loan on {date_str} but {lender} has not released the lien after "
        "{days} days. I cannot sell my vehicle or transfer the title. Customer service says "
        "they have no timeline for resolution.",
        "{lender} repossessed my vehicle on {date_str} despite my account being current. "
        "I have proof of payment for the last {months} consecutive months. I lost ${lost} in "
        "wages because I could not get to work.",
    ],
    "Money transfer, virtual currency, or money service": [
        "I sent ${amount} via {service} to {recipient_country} on {date_str}. The transfer "
        "was not received after {days} business days. {service} says it was delivered but the "
        "recipient has no record of the funds.",
        "My {service} account was closed without notice on {date_str}. I had a balance of "
        "${amount} that I cannot access. I have sent {count} inquiries and have not received "
        "a substantive response about how to retrieve my funds.",
        "I was charged a transfer fee of ${fee} when I was told the fee would be ${promised_fee}. "
        "The exchange rate I received was also worse than quoted at the time of transfer. "
        "Total discrepancy: ${discrepancy}.",
        "{service} froze my account for {days} days citing compliance review. During this time "
        "I was unable to send money for medical expenses to my family in {country}. "
        "No documentation was requested; the freeze was lifted without explanation.",
    ],
}

FILL_VALUES = {
    "amount": lambda: random.choice([47, 89, 120, 250, 500, 1200, 2500, 5000, 10000, 15000]),
    "fee": lambda: random.choice([25, 35, 38, 40]),
    "total": lambda: random.choice([75, 114, 152, 190]),
    "days": lambda: random.choice([7, 10, 14, 21, 30, 45, 60, 90]),
    "months": lambda: random.choice([6, 12, 18, 24, 36]),
    "years": lambda: random.choice([2, 3, 5, 7, 10]),
    "count": lambda: random.choice([2, 3, 4, 5, 6, 8, 10]),
    "points": lambda: random.choice([30, 45, 60, 80, 100, 120]),
    "score": lambda: random.choice([680, 710, 730, 750, 780]),
    "old_apr": lambda: random.choice([14, 16, 18, 20]),
    "new_apr": lambda: random.choice([24, 26, 28, 29]),
    "ordinal": lambda: random.choice(["second", "third", "fourth", "fifth"]),
    "last4": lambda: random.randint(1000, 9999),
    "overdraft_count": lambda: random.choice([2, 3, 4, 5]),
    "monthly_increase": lambda: random.choice([75, 100, 125, 150, 200]),
    "late_payments": lambda: random.choice([2, 3, 4, 6]),
    "points": lambda: random.choice([30, 45, 60, 80]),
    "income": lambda: random.choice([35000, 48000, 55000, 72000, 85000]),
    "extra": lambda: random.choice([50, 75, 100, 150, 200]),
    "lost": lambda: random.choice([200, 400, 600, 800, 1200]),
    "promised_fee": lambda: random.choice([5, 8, 10, 12]),
    "discrepancy": lambda: random.choice([15, 25, 40, 60]),
    "fee": lambda: random.choice([15, 20, 25, 30]),
    "case_num": lambda: f"{random.randint(20, 24)}-{random.randint(10000, 99999)}",
    "issuer": lambda: random.choice(["Chase", "Bank of America", "Citibank", "Capital One", "Wells Fargo", "Discover"]),
    "bank": lambda: random.choice(["Chase", "Bank of America", "Wells Fargo", "Citibank", "US Bank", "TD Bank"]),
    "servicer": lambda: random.choice(["Navient", "FedLoan", "Nelnet", "Great Lakes", "MOHELA", "Ocwen", "PHH"]),
    "old_servicer": lambda: random.choice(["Navient", "FedLoan", "Great Lakes"]),
    "new_servicer": lambda: random.choice(["MOHELA", "Nelnet", "Aidvantage"]),
    "collector": lambda: random.choice(["Midland Credit", "Portfolio Recovery", "LVNV Funding", "Encore Capital", "Cavalry Portfolio"]),
    "creditor": lambda: random.choice(["Chase", "Citibank", "Bank of America", "Synchrony", "Capital One", "Discover"]),
    "original_creditor": lambda: random.choice(["Chase", "Citibank", "Discover", "GE Capital", "Synchrony"]),
    "bureau": lambda: random.choice(["Equifax", "Experian", "TransUnion"]),
    "merchant": lambda: random.choice(["Amazon", "Walmart", "Target", "a gas station", "an online retailer", "Apple"]),
    "lender": lambda: random.choice(["Ally Financial", "Capital One Auto", "Wells Fargo Auto", "Chase Auto", "Santander Consumer"]),
    "dealer": lambda: random.choice(["the dealership", "AutoNation", "CarMax", "the selling dealer"]),
    "product": lambda: random.choice(["GAP insurance", "an extended warranty", "a credit protection plan", "paint protection"]),
    "service": lambda: random.choice(["Zelle", "Western Union", "MoneyGram", "PayPal", "Venmo", "Remitly", "Wise"]),
    "recipient_country": lambda: random.choice(["Mexico", "the Philippines", "India", "Nigeria", "Guatemala", "El Salvador"]),
    "country": lambda: random.choice(["Mexico", "India", "the Philippines", "Nigeria", "Guatemala"]),
    "state": lambda: random.choice(["California", "Texas", "Florida", "New York", "Georgia"]),
    "date_str": lambda: f"{random.choice(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'])} {random.randint(1, 28)}, {random.randint(2021, 2024)}",
}


def _fill_template(template: str) -> str:
    result = template
    for key, fn in FILL_VALUES.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, str(fn()), 1)
    return result


def _random_date() -> date:
    start = date(2021, 1, 1)
    end = date(2024, 6, 30)
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate_synthetic_dataset(n: int = 1200, seed: int = SEED) -> pd.DataFrame:
    random.seed(seed)
    total_weight = sum(PRODUCTS.values())
    counts = {
        p: max(1, round(n * w / total_weight))
        for p, w in PRODUCTS.items()
    }
    # Fix rounding
    diff = n - sum(counts.values())
    first_product = list(counts.keys())[0]
    counts[first_product] += diff

    rows = []
    idx = 0
    for product, count in counts.items():
        templates = TEMPLATES[product]
        issue_suffixes = [
            "I am requesting immediate resolution.",
            "Please investigate this matter urgently.",
            "I have documented all communications.",
            "This has caused significant financial hardship.",
            "I am considering legal action if this is not resolved.",
            "I would like a written response within 30 days.",
        ]
        for _ in range(count):
            template = random.choice(templates)
            narrative = _fill_template(template)
            narrative += " " + random.choice(issue_suffixes)
            rows.append({
                "cfpb_id": f"SYNTH-{idx:05d}",
                "narrative": narrative,
                "date_received": _random_date().isoformat(),
                "cfpb_product": product,
                "cfpb_issue": f"{product} issue",
            })
            idx += 1

    df = pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    logger.info(f"Generated {len(df)} synthetic incidents")
    for p, c in df["cfpb_product"].value_counts().items():
        logger.info(f"  {p[:50]}: {c}")
    return df


if __name__ == "__main__":
    df = generate_synthetic_dataset(1200)
    print(df.head(3).to_string())
    print(f"\nTotal: {len(df)} records")
