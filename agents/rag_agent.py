import os
import requests
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from pathlib import Path
import streamlit as st



# ─────────────────────────────────────────────────────────────────
#  GOLD PRICING EQUATION
#
#  FROM CSV (per product):
#    C   = purchase_cost_per_gram  (what we paid per gram)
#    M   = making_charges_per_gram
#    W%  = wastage_percent
#    P   = packaging_cost (per unit)
#    H   = hallmarking_fee (per unit)
#    Wt  = weight_per_unit_grams
#    Q   = quantity
#
#  FROM LIVE (Yahoo Finance):
#    L   = live gold price per gram (INR)
#
#  STEP 1: Base Cost per gram
#    BaseCost/g = C + M + (C × W%)
#
#  STEP 2: Unit Raw Cost
#    UnitRawCost = (BaseCost/g × Wt) + P + H
#
#  STEP 3: Market Adjusted Cost
#    AdjustedCost = UnitRawCost × (L / C)
#    → If live > purchase: cost goes up
#    → If live < purchase: we still use purchase (never sell at loss)
#
#  STEP 4: Selling Price (30% margin pre-GST)
#    SellingPrice = AdjustedCost / 0.70
#
#  STEP 5: GST
#    CGST = SellingPrice × 1.5%
#    SGST = SellingPrice × 1.5%
#
#  STEP 6: Invoice Price per unit
#    InvoicePrice = SellingPrice + CGST + SGST
#
#  STEP 7: Line Total
#    LineTotal = InvoicePrice × Q
# ─────────────────────────────────────────────────────────────────

class RAGPricingAgent:

    CGST_RATE     = 0.015   # 1.5%
    SGST_RATE     = 0.015   # 1.5%
    TARGET_MARGIN = 0.30    # 30% margin on selling price

    def __init__(self, db_path="database/products.csv"):
        self.db_path      = db_path
        self.chroma_path  = "database/chroma_gold_v1"
        self.coll_name    = "gold_products_v1"
        self.yahoo_base   = "https://query1.finance.yahoo.com/v8/finance/chart/"
        self.headers      = {"User-Agent": "Mozilla/5.0"}

        # ChromaDB + embeddings
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = "./database/models_cache"
        self.chroma  = chromadb.PersistentClient(path=self.chroma_path)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.chroma.get_or_create_collection(
            name=self.coll_name,
            embedding_function=self.embed_fn
        )
        if self.collection.count() == 0:
            self._index_products()
        else:
            print(f"📚 RAG Agent: Vector DB loaded ({self.collection.count()} products).")

    # ── LIVE PRICE ─────────────────────────────────────────────

    def get_live_gold_price_inr(self):
        """
        Fetch live gold price from Yahoo Finance.
        GC=F  → COMEX Gold Futures (USD/oz)
        INR=X → USD to INR rate
        Convert → INR per gram  (1 troy oz = 31.1035g)
        """
        try:
            r1 = requests.get(f"{self.yahoo_base}GC=F",
                              headers=self.headers, timeout=5)
            gold_usd_oz = r1.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]

            r2 = requests.get(f"{self.yahoo_base}INR=X",
                              headers=self.headers, timeout=5)
            usd_inr = r2.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]

            inr_per_gram = round((gold_usd_oz * usd_inr) / 31.1035, 2)

            print(f"✅ LIVE GOLD: ${gold_usd_oz}/oz | USD/INR: {usd_inr} | ₹{inr_per_gram}/gram")
            return inr_per_gram, gold_usd_oz, usd_inr, "LIVE"

        except Exception as e:
            print(f"❌ Yahoo Finance failed: {e} — using fallback")
            # Fallback based on current approximate MCX rate
            return 14695.75, 5017.5, 91.099, "FALLBACK"

    def _purity_factor(self, purity: str) -> float:
        """24K=1.0, 22K=22/24, 18K=18/24"""
        return {"24K": 1.0, "22K": 22/24, "18K": 18/24, "14K": 14/24}.get(purity.upper(), 1.0)

    # ── CORE PRICING ───────────────────────────────────────────

    def calculate_gold_price(self, product: dict, qty: int, live_24k: float) -> dict:
        """
        Full pricing calculation for one product line.
        purchase_cost_per_gram is read from products.csv.
        """
        purity      = str(product.get("purity", "24K"))
        weight_g    = float(product.get("weight_per_unit_grams", 1))
        making_g    = float(product.get("making_charges_per_gram", 0))
        wastage_pct = float(product.get("wastage_percent", 0)) / 100
        packaging   = float(product.get("packaging_cost", 0))
        hallmarking = float(product.get("hallmarking_fee", 0))
        purchase_cost_24k = float(product.get("purchase_cost_per_gram", live_24k))

        # Adjust for purity
        factor       = self._purity_factor(purity)
        live_g       = round(live_24k * factor, 2)
        purchase_g   = round(purchase_cost_24k * factor, 2)

        # ── STEP 1: Base Cost per gram ──────────────────────────
        wastage_cost  = purchase_g * wastage_pct
        base_cost_g   = purchase_g + making_g + wastage_cost

        step1 = (f"BaseCost/g = ₹{purchase_g:,.2f} (purchase) "
                 f"+ ₹{making_g:,.2f} (making) "
                 f"+ ₹{wastage_cost:,.2f} (wastage {wastage_pct*100}%) "
                 f"= ₹{base_cost_g:,.2f}/g")

        # ── STEP 2: Unit Raw Cost ───────────────────────────────
        raw_gold     = base_cost_g * weight_g
        unit_raw     = raw_gold + packaging + hallmarking

        step2 = (f"UnitRawCost = ₹{base_cost_g:,.2f} × {weight_g}g "
                 f"= ₹{raw_gold:,.2f} + packaging ₹{packaging:,.2f} "
                 f"+ hallmarking ₹{hallmarking:,.2f} = ₹{unit_raw:,.2f}")

        # ── STEP 3: Market Adjusted Cost ───────────────────────
        market_factor  = round(max(live_g / purchase_g, 1.0), 4) if purchase_g > 0 else 1.0
        adjusted_cost  = round(unit_raw * market_factor, 2)

        step3 = (f"MarketFactor = Live ₹{live_g:,.2f} ÷ Purchase ₹{purchase_g:,.2f} "
                 f"= {market_factor}x | "
                 f"AdjustedCost = ₹{unit_raw:,.2f} × {market_factor} = ₹{adjusted_cost:,.2f}")

        # ── STEP 4: Selling Price (30% margin) ─────────────────
        selling_price = round(adjusted_cost / (1 - self.TARGET_MARGIN), 2)
        margin_actual = round(((selling_price - adjusted_cost) / selling_price) * 100, 2)

        step4 = (f"SellingPrice = ₹{adjusted_cost:,.2f} ÷ 0.70 "
                 f"= ₹{selling_price:,.2f} | Margin = {margin_actual}% ✅")

        # ── STEP 5: GST ─────────────────────────────────────────
        cgst      = round(selling_price * self.CGST_RATE, 2)
        sgst      = round(selling_price * self.SGST_RATE, 2)
        total_gst = round(cgst + sgst, 2)

        step5 = (f"CGST 1.5% = ₹{cgst:,.2f} | "
                 f"SGST 1.5% = ₹{sgst:,.2f} | "
                 f"Total GST = ₹{total_gst:,.2f}")

        # ── STEP 6: Invoice Price per unit ─────────────────────
        invoice_unit = round(selling_price + total_gst, 2)

        step6 = (f"InvoicePrice = ₹{selling_price:,.2f} + ₹{total_gst:,.2f} GST "
                 f"= ₹{invoice_unit:,.2f}/unit")

        # ── STEP 7: Line Total ──────────────────────────────────
        line_pretax  = round(selling_price * qty, 2)
        line_cgst    = round(cgst * qty, 2)
        line_sgst    = round(sgst * qty, 2)
        line_gst     = round(total_gst * qty, 2)
        line_invoice = round(invoice_unit * qty, 2)

        step7 = (f"LineTotal = ₹{invoice_unit:,.2f} × {qty} units "
                 f"= ₹{line_invoice:,.2f}")

        return {
            # Product info
            "product_name"           : product.get("product_name"),
            "sku"                    : product.get("sku"),
            "category"               : product.get("category"),
            "purity"                 : purity,
            "weight_per_unit_grams"  : weight_g,
            "qty"                    : qty,

            # Inputs
            "purchase_cost_per_gram" : purchase_g,
            "live_price_per_gram"    : live_g,
            "making_charges_per_gram": making_g,
            "wastage_percent"        : wastage_pct * 100,
            "packaging_cost"         : packaging,
            "hallmarking_fee"        : hallmarking,

            # Calculated
            "base_cost_per_gram"     : round(base_cost_g, 2),
            "unit_raw_cost"          : round(unit_raw, 2),
            "market_factor"          : market_factor,
            "adjusted_cost_per_unit" : adjusted_cost,
            "selling_price_per_unit" : selling_price,
            "actual_margin_percent"  : margin_actual,
            "cgst_per_unit"          : cgst,
            "sgst_per_unit"          : sgst,
            "total_gst_per_unit"     : total_gst,
            "invoice_price_per_unit" : invoice_unit,

            # Line totals
            "line_total_pretax"      : line_pretax,
            "line_total_cgst"        : line_cgst,
            "line_total_sgst"        : line_sgst,
            "line_total_gst"         : line_gst,
            "line_total_invoice"     : line_invoice,

            # Step logs for UI
            "calculation_steps": {
                "step1_base_cost"        : step1,
                "step2_unit_raw_cost"    : step2,
                "step3_market_adjustment": step3,
                "step4_selling_price"    : step4,
                "step5_gst"              : step5,
                "step6_invoice_price"    : step6,
                "step7_line_total"       : step7,
            }
        }

    # ── MAIN METHOD ────────────────────────────────────────────

    def lookup_and_price(self, ai_analysis: dict) -> dict:
        """
        Matches extracted RFQ items to products via ChromaDB,
        then prices each item using live MCX gold price.
        No purchase_cost parameter needed — read from CSV.
        """
        live_24k, gold_usd_oz, usd_inr, price_source = self.get_live_gold_price_inr()

        items_list          = ai_analysis.get("extracted_items", [])
        priced_items        = []
        grand_total_pretax  = 0
        grand_total_gst     = 0
        grand_total_invoice = 0

        for item in items_list:
            query_text = item.get("item") or item.get("description", "")
            qty        = self._clean_qty(item.get("qty", 1))
            if not query_text:
                continue

            results = self.collection.query(query_texts=[query_text], n_results=1)

            if results["metadatas"] and results["metadatas"][0]:
                sku     = results["metadatas"][0][0].get("sku")
                product = self._get_product_by_sku(sku)
                if not product:
                    continue

                pricing = self.calculate_gold_price(product, qty, live_24k)
                pricing["requested_item"] = query_text
                priced_items.append(pricing)

                grand_total_pretax  += pricing["line_total_pretax"]
                grand_total_gst     += pricing["line_total_gst"]
                grand_total_invoice += pricing["line_total_invoice"]
            else:
                priced_items.append({
                    "requested_item": query_text,
                    "product_name"  : "NOT MATCHED",
                    "qty"           : qty,
                    "status"        : "NO MATCH IN DB"
                })

        return {
            "line_items"             : priced_items,
            "grand_total_pretax"     : round(grand_total_pretax, 2),
            "grand_total_cgst"       : round(sum(i.get("line_total_cgst", 0) for i in priced_items), 2),
            "grand_total_sgst"       : round(sum(i.get("line_total_sgst", 0) for i in priced_items), 2),
            "grand_total_gst"        : round(grand_total_gst, 2),
            "grand_total_invoice"    : round(grand_total_invoice, 2),
            "live_gold_price_24k_inr": live_24k,
            "gold_usd_per_oz"        : gold_usd_oz,
            "usd_inr_rate"           : usd_inr,
            "price_source"           : price_source,
        }

    # ── DB HELPERS ─────────────────────────────────────────────

    def _index_products(self):
        print("⚙️ Indexing gold products into Vector DB...")
        df = pd.read_csv(self.db_path).fillna("")
        docs, metas, ids = [], [], []
        for _, row in df.iterrows():
            desc = (f"Product: {row['product_name']}. Category: {row['category']}. "
                    f"Purity: {row['purity']}. Weight: {row['weight_per_unit_grams']}g. "
                    f"Description: {row['description']}.")
            docs.append(desc)
            metas.append({
                "product_name": str(row["product_name"]),
                "sku"         : str(row["sku"]),
                "category"    : str(row["category"]),
                "purity"      : str(row["purity"])
            })
            ids.append(str(row["sku"]))
        self.collection.add(documents=docs, metadatas=metas, ids=ids)
        print(f"   ✅ Indexed {len(docs)} products.")

    def _get_product_by_sku(self, sku: str) -> dict:
        df  = pd.read_csv(self.db_path).fillna("")
        row = df[df["sku"] == sku]
        return row.iloc[0].to_dict() if not row.empty else None

    def _clean_qty(self, val) -> int:
        if isinstance(val, (int, float)):
            return max(int(val), 1)
        try:
            return max(int("".join(filter(str.isdigit, str(val)))), 1)
        except Exception:
            return 1
