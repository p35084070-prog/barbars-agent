import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "knowledge" / "discovered"

for name, icon in (("bazaar-mifril", "mifrilbar"), ("bazaar-bottles", "bottle")):
    h = (D / f"{name}.html").read_text(encoding="utf-8")
    blocks = re.findall(rf'<img[^>]*src="/images/icons/{icon}\.png".*?</div>', h, re.S)
    print(f"=== {name}: {len(blocks)} лотов ===")
    for b in blocks[:10]:
        print(re.sub(r"\s+", " ", b))
        print("---")
