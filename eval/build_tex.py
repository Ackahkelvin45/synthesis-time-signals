"""build_tex.py — paper/paper.md -> paper/tex/paper.tex under Springer svjour3 (legacy layout) or a plain article class (JSS submission) via pandoc in Docker, then xelatex.

The abstract and keywords are lifted from the Markdown; the body (everything from
"## 1. Introduction") is converted with pandoc as a fragment and wrapped in the
class's front matter. Author block is a placeholder to be filled by the author.

    python eval/build_tex.py --springer <dir containing svjour3.cls>
"""
import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--springer", default=None, help="Springer svjour3 package dir; omit for a plain article-class build (Elsevier Your Paper Your Way)")
    ap.add_argument("--md", default="paper/paper.md")
    ap.add_argument("--out", default="paper/tex")
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    md = (ROOT / a.md).read_text()
    title = " ".join(re.search(r"^# (.+?)\n\n", md, re.M | re.S).group(1).split())   # the heading may wrap
    short = title.split(":")[0].strip()
    if len(short) > 70:
        short = " ".join(short.split()[:8])
    abstract = md[md.index("## Abstract"):md.index("**Keywords.**")].split("\n", 1)[1].strip()
    keywords = re.search(r"\*\*Keywords\.\*\* (.+)", md).group(1).strip().rstrip(".")
    body = md[md.index("## 1. Introduction"):]
    body = re.sub(r"^## (\d+)\. ", "## ", body, flags=re.M)          # svjour3 numbers sections itself
    body = re.sub(r"^### (\d+\.\d+) ", "### ", body, flags=re.M)
    body = re.sub(r"^## (Statements and Declarations|References)$", r"## \1 {-}", body, flags=re.M)  # unnumbered
    (out / "body.md").write_text(body)
    figs = out / "figures"
    figs.mkdir(exist_ok=True)
    for f in (ROOT / "paper" / "figures").glob("*.pdf"):
        shutil.copy(f, figs / f.name)
    subprocess.run(["docker", "run", "--rm", "-v", f"{out}:/data", "pandoc/core:latest", "body.md",
                    "-f", "markdown", "-t", "latex", "--shift-heading-level-by=-1", "-o", "body.tex"], check=True)
    body_tex = (out / "body.tex").read_text()
    # pandoc wraps caption-less tables in {\def\LTcaptype{none} ...}; svjour3 has no such counter
    body_tex = body_tex.replace("{\\def\\LTcaptype{none} % do not increment counter\n", "{\n")
    (out / "body.tex").write_text(body_tex)
    if a.springer:
        for f in Path(a.springer).iterdir():   # class, its .clo option files, bibliography styles
            if f.suffix in (".cls", ".clo", ".bst", ".sty"):
                shutil.copy(f, out / f.name)
    else:
        tex = r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{fontspec}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{calc}
\usepackage{amsmath}
\usepackage[hidelinks]{hyperref}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{#1}
\setkeys{Gin}{width=\linewidth,keepaspectratio}
\setlength{\parskip}{4pt}
\begin{document}
\title{%s}
\author{Kelvin Ackah\thanks{Corresponding author. kackah@st.knust.edu.gh} \and Dr Owusu-Agyemang Kwabena\thanks{kwabenaoa@knust.edu.gh} \and Dr Rose-Mary Owusuaa Mensah Gyening\thanks{rmo.mensah@knust.edu.gh} \and Dr Kate Takyi\thanks{takyikate@knust.edu.gh}\\[4pt]
  \normalsize Kwame Nkrumah University of Science and Technology, Kumasi, Ghana}
\date{}
\maketitle
\begin{abstract}
%s
\end{abstract}
\noindent\textbf{Keywords:} %s
\input{body.tex}
\end{document}
""" % (title, abstract.replace("\n", " "), keywords)
        (out / "paper.tex").write_text(tex)
        r = subprocess.run(["/Library/TeX/texbin/xelatex", "-interaction=nonstopmode", "-halt-on-error", "paper.tex"],
                           cwd=out, capture_output=True, text=True)
        log = (out / "paper.log").read_text() if (out / "paper.log").exists() else r.stdout
        err = [l for l in log.splitlines() if l.startswith("! ")]
        pages = re.search(r"Output written on paper.pdf \((\d+) pages", log)
        print("xelatex (article) exit", r.returncode, "| pages", pages.group(1) if pages else None, "| errors", err[:3])
        return
    tex = r"""\documentclass[smallextended]{svjour3}
\usepackage{fontspec}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{calc}
\usepackage{amsmath}
\usepackage{hyperref}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\pandocbounded}[1]{#1}
\setkeys{Gin}{width=\linewidth,keepaspectratio}
\smartqed
\journalname{Journal of Systems and Software}
\begin{document}
\title{%s}
\titlerunning{%s}
\authorrunning{K. Ackah et al.}
\author{Kelvin Ackah \and Dr Owusu-Agyemang Kwabena \and Dr Rose-Mary Owusuaa Mensah Gyening \and Dr Kate Takyi}
\institute{Kelvin Ackah (corresponding author) \at Kwame Nkrumah University of Science and Technology, Kumasi, Ghana \\ \email{kackah@st.knust.edu.gh}
  \and Dr Owusu-Agyemang Kwabena \at Kwame Nkrumah University of Science and Technology, Kumasi, Ghana \\ \email{kwabenaoa@knust.edu.gh}
  \and Dr Rose-Mary Owusuaa Mensah Gyening \at Kwame Nkrumah University of Science and Technology, Kumasi, Ghana \\ \email{rmo.mensah@knust.edu.gh}
  \and Dr Kate Takyi \at Kwame Nkrumah University of Science and Technology, Kumasi, Ghana \\ \email{takyikate@knust.edu.gh}}
\date{Received: date / Accepted: date}
\maketitle
\begin{abstract}
%s
\keywords{%s}
\end{abstract}
\input{body.tex}
\end{document}
""" % (title, short, abstract.replace("\n", " "), keywords.replace(";", " \\and"))
    (out / "paper.tex").write_text(tex)
    r = subprocess.run(["/Library/TeX/texbin/xelatex", "-interaction=nonstopmode", "-halt-on-error", "paper.tex"],
                       cwd=out, capture_output=True, text=True)
    log = (out / "paper.log").read_text() if (out / "paper.log").exists() else r.stdout
    err = [l for l in log.splitlines() if l.startswith("! ")]
    pages = re.search(r"Output written on paper.pdf \((\d+) pages", log)
    print("xelatex exit", r.returncode, "| pages", pages.group(1) if pages else None, "| errors", err[:3])


if __name__ == "__main__":
    main()
