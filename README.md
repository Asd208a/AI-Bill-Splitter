# AI Bill Splitter

A Python + Streamlit application that reads receipt images with EasyOCR, lets users review extracted items, assigns items to participants, and calculates each person's share including tax and discounts.

## Features

- Upload PNG, JPG, or JPEG bill images.
- Extract text using EasyOCR (deep-learning-based OCR).
- Heuristically detect likely item descriptions, quantities, and prices.
- Review and manually correct OCR results in an editable table.
- Add participants by entering one name per line.
- Assign each item to one or more participants.
- Split shared items equally among selected participants.
- Distribute tax and discounts proportionally to each participant's item subtotal.
- Download the final split as CSV.

## Tech stack

- Python
- Streamlit
- EasyOCR
- Pillow
- NumPy
- Pandas

## Run locally

Python 3.10 or newer is recommended.

```bash
git clone https://github.com/YOUR-USERNAME/ai-bill-splitter.git
cd ai-bill-splitter

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The first OCR run downloads EasyOCR's model weights and may take a few minutes. CPU mode is enabled by default.

## Important limitations

Receipt formats vary widely. The included parser is a lightweight heuristic, not a universal receipt parser. It may misread quantities, prices, or item descriptions, especially on blurry, tilted, or complex receipts. Always review and correct the editable item table before calculating.

Tax and discounts are distributed proportionally based on each person's assigned item subtotal. Shared items are divided equally among the people selected for that item. This version does not automatically infer tax or discounts from the receipt; enter those amounts in the sidebar.

## Suggested GitHub description

AI-powered receipt scanner and bill splitter using EasyOCR and Streamlit. Extracts bill items from images, supports shared and individual item allocation, and calculates tax-adjusted amounts owed by each participant.
