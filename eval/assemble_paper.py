"""assemble_paper.py — concatenate the section drafts into paper/paper.md in the outline's order.

    python eval/assemble_paper.py --drafts <dir with draft_*.md> --out paper/paper.md
"""
import argparse
import re
from pathlib import Path


def part(text, start, end=None):
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    return text[i:j].rstrip() + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", required=True)
    ap.add_argument("--out", default="paper/paper.md")
    a = ap.parse_args()
    D = Path(a.drafts)
    intro = (D / "draft_intro_related.md").read_text()
    methods = (D / "draft_methods.md").read_text()
    results = (D / "draft_results.md").read_text()
    disc = (D / "draft_discussion.md").read_text()
    body = disc[disc.index("**What the heterogeneity says.**"):].rstrip() + "\n\n"
    out = [
        part(intro, "## Title", "## Abstract").replace("## Title (registered, neutral)\n\n", "# "),
        part(intro, "## Abstract", "## 1. Introduction").replace("## Abstract (about 240 words)", "## Abstract"),
        part(intro, "## 1. Introduction", "## 2. Background"),
        part(intro, "## 2. Background", "## 8. Related work"),
        part(methods, "## 3. Approach", "## 4. Experimental design"),
        part(methods, "## 4. Experimental design", "## 7. Threats to validity"),
        part(results, "## 5. Results", "## 6. Mechanism"),
        part(results, "## 6. Mechanism"),
        "## 7. Discussion\n\n" + body,
        part(methods, "## 7. Threats to validity").replace("## 7. Threats to validity", "## 8. Threats to validity", 1),
        part(intro, "## 8. Related work", "## 9. Conclusion").replace("## 8. Related work", "## 9. Related work", 1),
        part(intro, "## 9. Conclusion").replace("## 9. Conclusion", "## 10. Conclusion", 1),
    ]
    text = "".join(out)
    Path(a.out).write_text(text)
    words = len(re.findall(r"\b\w+\b", text))
    ph = re.findall(r"\[(?![−+0-9])[^\]]*\]", text)
    print(f"{a.out}: {words} words, {text.count(chr(10) + '## ')} sections, em-dashes {text.count('—')}, placeholders {len(ph)}: {ph}")
    for m in re.finditer(r"^## .*", text, re.M):
        print("  ", m.group(0)[:72])


if __name__ == "__main__":
    main()
