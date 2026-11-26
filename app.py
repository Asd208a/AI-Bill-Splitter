import re
from io import BytesIO

import easyocr
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="AI Bill Splitter", page_icon="🧾", layout="wide")

st.title("🧾 AI Bill Splitter")
st.caption("Upload a receipt, review the OCR results, assign items, and calculate what everyone owes.")

@st.cache_resource
def get_reader():
    # First run downloads EasyOCR model weights.
    return easyocr.Reader(["en"], gpu=False)

def parse_price(token):
    token = token.replace(",", "")
    match = re.search(r"\d+(?:\.\d{1,2})?", token)
    return float(match.group()) if match else None

def extract_items(ocr_lines):
    """Heuristic parser: extracts a likely description and last numeric value per OCR line."""
    rows = []
    for line in ocr_lines:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        # Ignore common receipt totals/metadata; users can add these as adjustments below.
        if re.search(r"\b(sub ?total|grand total|total|tax|gst|vat|discount|change|cash|card|thank you)\b",
                     cleaned, re.I):
            continue
        nums = re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d{1,2})?", cleaned)
        if not nums:
            continue
        price = parse_price(nums[-1])
        if price is None or price <= 0:
            continue
        description = cleaned[:cleaned.rfind(nums[-1])].strip(" -:|.")
        # Remove a leading quantity such as "2 x" or "2".
        qty = 1.0
        qmatch = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:x|×)\s*", description, re.I)
        if qmatch:
            qty = float(qmatch.group(1))
            description = description[qmatch.end():].strip()
        if not description or re.fullmatch(r"[\d\s.,/-]+", description):
            continue
        rows.append({"Item": description, "Quantity": qty, "Unit price": round(price / qty, 2)})
    return rows

def money(value):
    return f"₹{value:,.2f}"

if "items" not in st.session_state:
    st.session_state.items = pd.DataFrame(columns=["Item", "Quantity", "Unit price"])
if "participants" not in st.session_state:
    st.session_state.participants = ["Person 1", "Person 2"]

with st.sidebar:
    st.header("1. People")
    names_text = st.text_area("Participant names (one per line)", value="\n".join(st.session_state.participants),
                              help="Enter everyone sharing this bill.")
    participants = list(dict.fromkeys([x.strip() for x in names_text.splitlines() if x.strip()]))
    if not participants:
        participants = ["Person 1"]
    st.session_state.participants = participants
    st.divider()
    st.header("2. Bill adjustments")
    tax = st.number_input("Tax / GST amount (₹)", min_value=0.0, value=0.0, step=1.0)
    discount = st.number_input("Discount amount (₹)", min_value=0.0, value=0.0, step=1.0)

st.subheader("Step 1 — Upload and scan a bill")
uploaded = st.file_uploader("Choose a bill image", type=["png", "jpg", "jpeg", "webp"])
if uploaded:
    image = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
    left, right = st.columns([1, 1])
    with left:
        st.image(image, caption="Uploaded bill", use_container_width=True)
    with right:
        if st.button("🔍 Extract text and items", type="primary"):
            with st.spinner("Reading the bill with EasyOCR... The first run may take a little longer."):
                reader = get_reader()
                result = reader.readtext(np.array(image), detail=0, paragraph=False)
                st.session_state.ocr_text = "\n".join(result)
                detected = extract_items(result)
                if detected:
                    st.session_state.items = pd.DataFrame(detected, columns=["Item", "Quantity", "Unit price"])
                else:
                    st.warning("No item rows were confidently detected. Add items manually using the editor below.")
        if st.button("Clear extracted items"):
            st.session_state.items = pd.DataFrame(columns=["Item", "Quantity", "Unit price"])
            st.session_state.pop("ocr_text", None)

if "ocr_text" in st.session_state:
    with st.expander("View raw OCR text"):
        st.text(st.session_state.ocr_text)

st.subheader("Step 2 — Review and edit items")
st.info("OCR can misread receipt layouts, quantities, or prices. Check and correct every row before splitting.")
edited = st.data_editor(
    st.session_state.items,
    num_rows="dynamic",
    use_container_width=True,
    key="items_editor",
    column_config={
        "Item": st.column_config.TextColumn("Item name", required=True),
        "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.01, step=1.0, required=True),
        "Unit price": st.column_config.NumberColumn("Unit price (₹)", min_value=0.0, step=1.0, format="%.2f", required=True),
    },
)
st.session_state.items = edited

valid = edited.dropna(subset=["Item", "Quantity", "Unit price"]).copy()
valid = valid[(valid["Item"].astype(str).str.strip() != "") & (valid["Quantity"] > 0) & (valid["Unit price"] >= 0)]
if not valid.empty:
    valid["Line total"] = valid["Quantity"].astype(float) * valid["Unit price"].astype(float)

st.subheader("Step 3 — Assign items to people")
allocations = {}
if valid.empty:
    st.warning("Scan a bill or add at least one item in the table above.")
else:
    st.caption("Select everyone who shares each item. The item's cost is divided equally among the selected people.")
    for idx, row in valid.reset_index(drop=True).iterrows():
        default_people = participants
        selected = st.multiselect(
            f"{row['Item']} — {money(float(row['Line total']))}",
            options=participants,
            default=default_people,
            key=f"allocation_{idx}_{str(row['Item'])}",
        )
        allocations[idx] = selected

st.subheader("Step 4 — Calculate the split")
if not valid.empty:
    subtotal = float(valid["Line total"].sum())
    if discount > subtotal:
        st.error("Discount cannot be greater than the item subtotal.")
    elif not participants:
        st.error("Add at least one participant.")
    else:
        # Allocate item costs equally among the selected people.
        shares = {person: 0.0 for person in participants}
        unassigned = []
        for idx, row in valid.reset_index(drop=True).iterrows():
            selected = allocations.get(idx, [])
            if not selected:
                unassigned.append(str(row["Item"]))
                continue
            per_person = float(row["Line total"]) / len(selected)
            for person in selected:
                shares[person] += per_person

        # Tax and discount are distributed in proportion to each person's item subtotal.
        if unassigned:
            st.warning("Assign these items before calculating: " + ", ".join(unassigned))
        elif subtotal <= 0:
            st.error("The subtotal must be greater than zero to allocate tax or discounts proportionally.")
        else:
            for person in participants:
                proportion = shares[person] / subtotal
                shares[person] += (tax - discount) * proportion

            total_due = sum(shares.values())
            st.metric("Bill total", money(subtotal + tax - discount))
            result_df = pd.DataFrame([
                {"Participant": person, "Amount owed": round(amount, 2)}
                for person, amount in shares.items()
            ])
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            cols = st.columns(min(4, len(participants)))
            for i, person in enumerate(participants):
                cols[i % len(cols)].metric(person, money(shares[person]))
            st.caption(f"Reconciliation: sum of individual shares = {money(total_due)}")
            csv = result_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download split as CSV", csv, "bill_split.csv", "text/csv")

st.divider()
st.caption("Built with Python, Streamlit, EasyOCR, Pillow, NumPy and Pandas. Review OCR output before relying on the calculation.")
