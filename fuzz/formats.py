"""formats.py — grammar-derived, format-generic proxy features (paper plan, step 5).

The proxy signal used to be JSON-specific in code: productions came from a
hand-written walk of `json.loads`, depth from counting brackets. That cannot
be "the same method held out" on TOML or XML. This module derives the same
three features from the SAME ANTLR grammar the model is given:

  productions(text)  the parser rule names, named lexer tokens and word-like
                     literal tokens visited by a successful parse of `text`
                     (a strict parse: any syntax or token error = no parse)
  depth(text)        the recursion depth of the most-recursive rule on any
                     root-to-leaf path, minus one (so `1` -> 0, `[1]` -> 1,
                     `{"a":[1]}` -> 2; equals bracket depth for JSON)
  fingerprint(text)  (sorted productions, depth band) for novelty counting

`PRODS` (the universe of productions a generator could cover) is read from
the generated parser: every parser rule, every named non-skipped token and
every alphabetic literal token. Nothing here knows what JSON is.

Parsers are generated once from grammar/<FMT>.g4 into grammar/gen/<fmt>/ with
ANTLR 4.13.2 (`grammar/gen.sh`) and committed, so reviewers need no Java.
Deep inputs (thousands of nesting levels) parse in a worker thread with a
large stack and a raised recursion limit; a parse that still fails counts as
"no productions", exactly like the previous json.loads path did.
"""
from __future__ import annotations

import importlib
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream, ParserRuleContext
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.ErrorStrategy import BailErrorStrategy
from antlr4.error.Errors import ParseCancellationException
from antlr4.tree.Tree import TerminalNode

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "grammar" / "gen"

_THREAD_STACK = 512 * 1024 * 1024   # deep nesting: ANTLR recurses per rule level
_RECURSION_LIMIT = 200_000


class _Strict(ErrorListener):
    """Any lexer or parser error aborts the parse (default ANTLR RECOVERS,
    which would count garbage as parsed)."""
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise ParseCancellationException(f"{line}:{column} {msg}")


@dataclass
class GrammarFormat:
    name: str                      # e.g. "JSON"
    gen_dir: Path                  # grammar/gen/json
    lexer_cls: str                 # "JSONLexer"
    parser_cls: str                # "JSONParser"
    start_rule: str                # "json"
    PRODS: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        sys.path.insert(0, str(self.gen_dir))
        self._lexer = getattr(importlib.import_module(self.lexer_cls), self.lexer_cls)
        self._parser = getattr(importlib.import_module(self.parser_cls), self.parser_cls)
        P = self._parser
        # word-like literals ('true') and named tokens (STRING); skip punctuation
        lits = [n.strip("'") for n in P.literalNames if n and n.strip("'").isalpha()]
        syms = [n for n in P.symbolicNames if n and n not in ("<INVALID>",)]
        skipped = self._skipped_tokens()
        toks = [t for t in syms if t not in skipped]
        self.PRODS = tuple(dict.fromkeys([*P.ruleNames, *toks, *lits]))
        self._rule_names = set(P.ruleNames)
        self._sym = {i: n for i, n in enumerate(P.symbolicNames) if n and n != "<INVALID>"}
        self._lit = {i: n.strip("'") for i, n in enumerate(P.literalNames) if n}
        self._skipped = skipped

    def _skipped_tokens(self) -> set[str]:
        """Token names whose lexer rule is `-> skip` (whitespace/comments):
        they never reach the parser, so they are not coverable productions."""
        g4 = ROOT / "grammar" / f"{self.name}.g4"
        out: set[str] = set()
        if not g4.exists():
            return out
        import re
        text = g4.read_text()
        for m in re.finditer(r"^([A-Z][A-Za-z0-9_]*)\s*:[^;]*?->\s*(?:skip|channel\s*\(\s*HIDDEN\s*\))", text, re.M | re.S):
            out.add(m.group(1))
        return out

    # --- parsing --------------------------------------------------------------
    def _parse_inline(self, text: str):
        lexer = self._lexer(InputStream(text))
        lexer.removeErrorListeners(); lexer.addErrorListener(_Strict())
        parser = self._parser(CommonTokenStream(lexer))
        parser.removeErrorListeners(); parser.addErrorListener(_Strict())
        parser._errHandler = BailErrorStrategy()
        return getattr(parser, self.start_rule)()

    def parse(self, text: str):
        """Strict parse tree, or None if the grammar rejects `text`."""
        result: list = [None]

        def work() -> None:
            old = sys.getrecursionlimit()
            sys.setrecursionlimit(_RECURSION_LIMIT)
            try:
                result[0] = self._parse_inline(text)
            except (ParseCancellationException, RecursionError, MemoryError):
                result[0] = None
            except Exception:  # noqa: BLE001 - a broken input must never kill the loop
                result[0] = None
            finally:
                sys.setrecursionlimit(old)

        old_size = threading.stack_size(_THREAD_STACK)
        try:
            t = threading.Thread(target=work, daemon=True)
            t.start(); t.join()
        finally:
            threading.stack_size(old_size)
        return result[0]

    # --- features ---------------------------------------------------------------
    def features(self, text: str) -> tuple[set[str], int]:
        """(productions, depth) in ONE parse. Empty set / 0 if unparseable."""
        tree = self.parse(text)
        if tree is None:
            return set(), 0
        prods: set[str] = set()
        max_depth = 0
        # iterative walk: (node, {rule: count on this path})
        stack: list[tuple[object, dict[str, int]]] = [(tree, {})]
        while stack:
            node, counts = stack.pop()
            if isinstance(node, TerminalNode):
                tt = node.symbol.type
                if tt in self._sym and self._sym[tt] not in self._skipped:
                    prods.add(self._sym[tt])
                if tt in self._lit and self._lit[tt].isalpha():
                    prods.add(self._lit[tt])
                continue
            if isinstance(node, ParserRuleContext):
                name = self._parser.ruleNames[node.getRuleIndex()]
                prods.add(name)
                c = dict(counts); c[name] = c.get(name, 0) + 1
                max_depth = max(max_depth, c[name] - 1)
                for child in (node.children or []):
                    stack.append((child, c))
        return prods, max_depth

    def productions(self, text: str) -> set[str]:
        return self.features(text)[0]

    def depth(self, text: str) -> int:
        return self.features(text)[1]

    def fingerprint(self, text: str) -> tuple:
        prods, d = self.features(text)
        band = min(d // 4, 8)   # coarse depth bands so trivial jitter isn't 'novel'
        return (tuple(sorted(prods)), band)


_REGISTRY: dict[str, dict] = {
    "JSON": dict(gen_dir=GEN / "json", lexer_cls="JSONLexer", parser_cls="JSONParser",
                 start_rule="json"),
    # TOML / XML entries are added with their targets (plan step 11).
}
_CACHE: dict[str, GrammarFormat] = {}


def get(name: str) -> GrammarFormat:
    if name not in _CACHE:
        if name not in _REGISTRY:
            raise KeyError(f"no grammar format registered for {name!r}")
        _CACHE[name] = GrammarFormat(name=name, **_REGISTRY[name])
    return _CACHE[name]
