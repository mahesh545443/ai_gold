<<<<<<< HEAD
# ⚜ Straive Gold Industries — AI Negotiation Orchestrator

AI-powered gold quotation & multi-round negotiation engine for jewellery sellers.

---

## 🚀 Setup & Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
Edit `.env` and add your Groq API key:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at: https://console.groq.com

### 3. Run the App
```bash
cd lita_jewellery
streamlit run main.py
```

---

## 📁 Project Structure

```
lita_jewellery/
├── main.py                    ← Streamlit UI (Overview + Application tabs)
├── requirements.txt
├── .env                       ← API keys (edit this)
├── agents/
│   ├── intake.py              ← Reads uploaded RFQ file
│   ├── classifier.py          ← Groq LLaMA — classifies & extracts items
│   ├── rag_agent.py           ← ChromaDB match + live MCX gold pricing
│   ├── proposal_agent.py      ← PDF quote generator (ReportLab)
│   ├── negotiation_agent.py   ← Counter-offer math engine
│   └── tat_agent.py           ← TAT calculation
├── database/
│   └── products.csv           ← Gold product catalog
├── input_folder/
│   └── sample_rfq.txt         ← Sample buyer RFQ for testing
├── output_folder/             ← Initial quote PDFs saved here
└── revised_quotes/            ← Revised/negotiated quote PDFs saved here
```

---

## 🔄 How It Works

### Application Flow
```
Upload RFQ → Classify (Groq LLM) → Match Products (ChromaDB) 
→ Price with Live MCX Rate → Generate PDF Quote 
→ Buyer replies in UI → Negotiation Agent runs math 
→ Revised PDF → Repeat until ACCEPT/REJECT
```

### Pricing Equation (Backend — 7 Steps)
```
① BaseCost/g  = PurchaseCost + Making + (PurchaseCost × Wastage%)
② UnitRawCost = BaseCost/g × Weight(g) + Packaging + Hallmarking
③ MarketFactor = max(LiveMCX / PurchaseCost, 1.0)
④ AdjustedCost = UnitRawCost × MarketFactor
⑤ SellingPrice = AdjustedCost / (1 - 0.30)   ← 30% margin floor
⑥ CGST = SellingPrice × 1.5%  |  SGST = SellingPrice × 1.5%
⑦ InvoicePrice = SellingPrice + CGST + SGST
```

### Negotiation Decision Logic
```
If BuyerOffer ≥ OurQuote    → ✅ ACCEPT
If BuyerOffer ≥ Floor       → 🔄 COUNTER_OFFER at midpoint
If BuyerOffer < Floor       → ❌ REJECT (margin would drop below 30%)
```
**All math done in Python. LLM (Groq) only writes the professional email.**

---

## 🧪 Quick Demo

1. Run the app: `streamlit run main.py`
2. Go to **Application** tab
3. Upload `input_folder/sample_rfq.txt`
4. Click **Run AI Pipeline**
5. Confirm purchase cost → Click **Calculate Pricing**
6. Review 7-step pricing breakdown → Click **Generate Quote PDF**
7. Type a counter-offer like: *"Can you give us 5% discount?"*
8. Watch the negotiation agent run math and respond

---

## 📦 Products Database

Edit `database/products.csv` to add/modify gold products.

Columns:
- `product_name, sku, category, purity, weight_per_unit_grams`
- `making_charges_per_gram, wastage_percent, packaging_cost, hallmarking_fee`
- `stock_qty, min_delivery_days, description`

---

## 🔑 Key Features

- ✅ Live gold price from Yahoo Finance (COMEX GC=F → INR/gram)
- ✅ 30% pre-GST margin mathematically guaranteed
- ✅ CGST 1.5% + SGST 1.5% shown separately in every quote
- ✅ Full 7-step calculation visible in UI and embedded in PDF
- ✅ Multi-round negotiation — no limit on rounds
- ✅ Professional branded PDF with hallmark details, bank info, T&C
- ✅ Groq LLaMA 3.3-70B for classification + email writing
- ✅ ChromaDB vector search for product matching
=======
# ai_gold
>>>>>>> 69a2c89ad9bbd6e458aa04b25ef79aa64803560a
