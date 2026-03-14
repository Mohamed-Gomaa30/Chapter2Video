"""Quick debug script to inspect the first few pages of the PDF."""
import fitz
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "./data/raw/chapter1.pdf"
doc = fitz.open(pdf_path)

print(f"Total pages: {len(doc)}")
# Print first 5 pages text to understand the structure
for page_num in range(min(5, len(doc))):
    page = doc[page_num]
    text = page.get_text("text")
    print(f"\n{'='*60}")
    print(f"PAGE {page_num} (PDF page {page_num + 1})")
    print(f"{'='*60}")
    # Print first 1000 chars of each page
    print(text[:1000])
    print("...")

doc.close()
