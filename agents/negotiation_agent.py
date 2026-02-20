import os
import re
import json
import logging
import requests
import urllib3
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
import streamlit as st


env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ─────────────────────────────────────────────────────────────────
#  NEGOTIATION LOGIC
#
#  We QUOTE at 30% margin
#  We can NEGOTIATE down to 20% minimum
#
#  Floor = AdjustedCost / (1 - 0.20)   ← 20% minimum margin
#
#  DECISION:
#    BuyerOffer >= OurQuote             → ACCEPT
#    BuyerOffer >= Floor (20% margin)   → COUNTER_OFFER at midpoint
#    BuyerOffer <  Floor (20% margin)   → REJECT
#
#  All math in Python. LLM only writes the email.
# ─────────────────────────────────────────────────────────────────

QUOTE_MARGIN = 0.30   # We quote at 30%
MIN_MARGIN   = 0.20   # We never go below 20%
CGST         = 0.015
SGST         = 0.015


class NegotiationAgent:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
    
        self.token = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        self.model   = "llama-3.3-70b-versatile"

        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session = session

    def handle_counter_offer(self, lead: dict, buyer_message: str) -> dict:

        pricing                = lead.get("pricing_data", {})
        original_total_pretax  = pricing.get("grand_total_pretax", 0)
        original_total_invoice = pricing.get("grand_total_invoice", 0)
        customer_name          = lead.get("ai_analysis", {}).get("customer_name", "Valued Customer")

        logging.info(f"🤝 Negotiation: {customer_name} | Original quote: ₹{original_total_invoice:,.2f}")

        # ── STEP 1: Extract buyer's price from message ─────────
        buyer_offered_total = self._extract_price_from_message(buyer_message, original_total_invoice)

        # ── STEP 2: Back-calculate buyer's pre-GST price ───────
        buyer_pretax = buyer_offered_total / (1 + CGST + SGST)

        # ── STEP 3: Calculate 20% floor from adjusted costs ────
        # Quote was at 30%: SellingPrice = AdjustedCost / 0.70
        # Floor is at 20%:  FloorPrice   = AdjustedCost / 0.80
        total_floor_pretax = 0
        item_floors        = []

        for item in pricing.get("line_items", []):
            if item.get("product_name") == "NOT MATCHED":
                continue
            adj_cost        = item.get("adjusted_cost_per_unit", 0)
            qty             = item.get("qty", 1)
            floor_unit      = adj_cost / (1 - MIN_MARGIN)   # 20% floor
            floor_total     = floor_unit * qty
            total_floor_pretax += floor_total
            item_floors.append({
                "product"         : item.get("product_name"),
                "adjusted_cost"   : round(adj_cost, 2),
                "quoted_at_30pct" : round(adj_cost / (1 - QUOTE_MARGIN), 2),
                "floor_at_20pct"  : round(floor_unit, 2),
                "qty"             : qty,
                "floor_total"     : round(floor_total, 2)
            })

        total_floor_invoice   = total_floor_pretax * (1 + CGST + SGST)
        gap_from_original_pct = ((original_total_pretax - buyer_pretax) / original_total_pretax * 100) if original_total_pretax > 0 else 0

        logging.info(f"   Buyer offered (pre-GST): ₹{buyer_pretax:,.2f}")
        logging.info(f"   Our quote (pre-GST):     ₹{original_total_pretax:,.2f}")
        logging.info(f"   20% floor (pre-GST):     ₹{total_floor_pretax:,.2f}")
        logging.info(f"   Gap from original:       {gap_from_original_pct:.1f}%")

        # ── STEP 4: Decision (Python only) ─────────────────────
        if buyer_pretax >= original_total_pretax:
            # Buyer accepted our price or offered more
            decision           = "ACCEPT"
            new_offered_pretax = original_total_pretax
            discount_pct       = 0.0
            reasoning          = "Buyer's offer meets our quoted price. Deal confirmed."
            

        elif buyer_pretax >= total_floor_pretax:
            # Buyer is between 20% floor and 30% quote → counter at midpoint
            midpoint_pretax    = (buyer_pretax + original_total_pretax) / 2
            new_offered_pretax = max(midpoint_pretax, total_floor_pretax)
            discount_pct       = round((original_total_pretax - new_offered_pretax) / original_total_pretax * 100, 2)
            decision           = "COUNTER_OFFER"
            reasoning          = (
                f"Buyer offered ₹{buyer_offered_total:,.2f} (pre-GST ₹{buyer_pretax:,.2f}). "
                f"Above our 20% floor of ₹{total_floor_pretax:,.2f}. "
                f"Countering at midpoint ₹{new_offered_pretax:,.2f} pre-GST ({discount_pct:.1f}% discount)."
            )

        else:
            # Buyer is below our 20% floor → REJECT
            decision           = "REJECT"
            new_offered_pretax = total_floor_pretax
            discount_pct       = round((original_total_pretax - total_floor_pretax) / original_total_pretax * 100, 2)
            reasoning          = (
                f"Buyer offered ₹{buyer_offered_total:,.2f} (pre-GST ₹{buyer_pretax:,.2f}). "
                f"This is BELOW our 20% minimum margin floor of ₹{total_floor_pretax:,.2f}. "
                f"Maximum discount possible is {discount_pct:.1f}%. Cannot go further."
            )

        # ── STEP 5: GST on new price ────────────────────────────
        new_cgst          = round(new_offered_pretax * CGST, 2)
        new_sgst          = round(new_offered_pretax * SGST, 2)
        new_invoice_total = round(new_offered_pretax + new_cgst + new_sgst, 2)

        # ── STEP 6: LLM writes the email only ──────────────────
        email_draft = self._write_email(
            customer_name    = customer_name,
            buyer_message    = buyer_message,
            decision         = decision,
            original_invoice = original_total_invoice,
            new_invoice      = new_invoice_total,
            discount_pct     = discount_pct,
            reasoning        = reasoning,
            floor_invoice    = total_floor_invoice
        )

        negotiation_log = {
            "buyer_message"              : buyer_message,
            "buyer_offered_total_invoice": round(buyer_offered_total, 2),
            "buyer_offered_pretax"       : round(buyer_pretax, 2),
            "original_total_pretax"      : round(original_total_pretax, 2),
            "original_total_invoice"     : round(original_total_invoice, 2),
            "floor_pretax"               : round(total_floor_pretax, 2),
            "floor_invoice"              : round(total_floor_invoice, 2),
            "gap_from_original_pct"      : round(gap_from_original_pct, 2),
            "item_floors"                : item_floors,
            "decision"                   : decision,
            "reasoning"                  : reasoning,
            "new_offered_pretax"         : round(new_offered_pretax, 2),
            "new_offered_cgst"           : new_cgst,
            "new_offered_sgst"           : new_sgst,
            "new_invoice_total"          : new_invoice_total,
            "discount_percent"           : discount_pct,
            "reply_email_draft"          : email_draft
        }

        lead["negotiation_outcome"]  = negotiation_log
        lead["negotiation_history"]  = lead.get("negotiation_history", [])
        lead["negotiation_history"].append(negotiation_log)

        return lead

    # ── Helpers ────────────────────────────────────────────────

    def _extract_price_from_message(self, message: str, original_price: float) -> float:
        """Extract buyer's offered price from their message."""

        # Look for explicit price (₹ or Rs or INR)
        for pat in [
            r"₹\s*([\d,]+(?:\.\d+)?)",
            r"Rs\.?\s*([\d,]+(?:\.\d+)?)",
            r"INR\s*([\d,]+(?:\.\d+)?)",
            r"([\d,]+(?:\.\d+)?)\s*(?:rupees|INR|Rs)",
        ]:
            m = re.search(pat, message, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1).replace(",", ""))
                    if val > 100:
                        return val
                except Exception:
                    pass

        # Look for discount percentage
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:discount|off|reduction|less|lower)", message, re.IGNORECASE)
        if m:
            return original_price * (1 - float(m.group(1)) / 100)

        # Default: assume 5% discount if nothing found
        return original_price * 0.95

    def _write_email(self, customer_name, buyer_message, decision,
                     original_invoice, new_invoice, discount_pct, reasoning, floor_invoice):
        """LLM writes the professional reply email only."""
        prompt = f"""
You are a Senior Sales Manager at Analytics Avenue, a reputed gold company.
Write a professional email response to a buyer's negotiation.

SITUATION:
- Customer: {customer_name}
- Buyer said: "{buyer_message}"
- Our original quote (incl. GST): ₹{original_invoice:,.2f}
- Decision: {decision}
- {"Revised counter-offer (incl. GST): ₹" + f"{new_invoice:,.2f} ({discount_pct:.1f}% discount)" if decision == "COUNTER_OFFER" else ""}
- {"Buyer's price accepted." if decision == "ACCEPT" else ""}
- {"Cannot discount — below our 20% minimum margin. Floor: ₹" + f"{floor_invoice:,.2f}" if decision == "REJECT" else ""}
- Reason: {reasoning}

Instructions:
1. Be professional, warm but firm
2. Clearly state the {decision} with price
3. If REJECT — mention live MCX gold rates leave no room
4. End positively

Reply with email body text ONLY.
"""
        try:
            resp = self.session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json={"model": self.model, "max_tokens": 500, "temperature": 0.3,
                      "messages": [{"role": "user", "content": prompt}]},
                verify=False, timeout=30
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logging.error(f"❌ LLM email failed: {e}")
            if decision == "ACCEPT":
                return (f"Dear {customer_name},\n\nThank you. We are pleased to confirm "
                        f"your order at ₹{new_invoice:,.2f} (incl. GST).\n\nBest regards,\nAnalytics Avenue")
            elif decision == "COUNTER_OFFER":
                return (f"Dear {customer_name},\n\nThank you for your response. "
                        f"We can offer ₹{new_invoice:,.2f} (incl. GST) — a {discount_pct:.1f}% reduction. "
                        f"This is our best offer.\n\nBest regards,\nAnalytics Avenue")
            else:
                return (f"Dear {customer_name},\n\nThank you for your feedback. "
                        f"Due to current MCX gold rates, we cannot discount further. "
                        f"Our pricing reflects minimum viable margins.\n\nBest regards,\nAnalytics Avenue")

