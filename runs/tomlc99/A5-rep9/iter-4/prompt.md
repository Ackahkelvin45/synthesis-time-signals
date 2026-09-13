Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic building blocks ----------

# Characters that are safe-ish for content (no raw NUL ever).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),  # no surrogates
    blacklist_characters="\x00",   # never raw NUL
)

# ASCII letters/digits for bare keys.
_bare_key_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

def _bare_key():
    return st.lists(_bare_key_char, min_size=1, max_size=12).map("".join)

# Escape sequences for basic strings.
_escape = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
)

def _unicode_escape():
    return st.integers(min_value=0, max_value=0xFFFF).map(
        lambda n: "\\u%04X" % n
    )

def _ex_unicode_escape():
    return st.integers(min_value=0, max_value=0x10FFFF).map(
        lambda n: "\\U%08X" % n
    )

def _basic_char():
    # printable-ish content plus escapes and non-ASCII.
    return st.one_of(
        _escape,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\x00\\\n',
                min_codepoint=0x20,
            ),
            min_size=0,
            max_size=8,
        ),
        _unicode_escape(),
        _ex_unicode_escape(),
        # raw control bytes inside strings are accepted by the parser.
        st.integers(min_value=1, max_value=0x1F).map(chr),
    )

def _basic_string():
    return st.lists(_basic_char(), max_size=6).map(lambda cs: '"' + "".join(cs) + '"')

def _literal_char():
    return st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="'\x00\n",
            ),
            min_size=0,
            max_size=8,
        ),
        st.integers(min_value=1, max_value=0x1F).map(chr),
    )

def _literal_string():
    return st.lists(_literal_char(), max_size=6).map(lambda cs: "'" + "".join(cs) + "'")

def _ml_basic_string():
    inner = st.lists(
        st.one_of(
            _escape,
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters='"\x00\\',
                ),
                min_size=0,
                max_size=10,
            ),
            _unicode_escape(),
            st.just("\n"),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map("".join)
    return inner.map(lambda s: '"""' + s + '"""')

def _ml_literal_string():
    inner = st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="'\x00",
                ),
                min_size=0,
                max_size=10,
            ),
            st.just("\n"),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map("".join)
    return inner.map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

# ---------- numbers ----------

def _dec_int():
    digits = st.integers(min_value=0, max_value=9)
    return st.one_of(
        # small
        st.integers(min_value=0, max_value=10**6).map(str),
        # leading zeros (accepted by parser)
        st.integers(min_value=0, max_value=999).map(lambda n: "0" + str(n)),
        # underscores
        st.integers(min_value=1000, max_value=10**12).map(
            lambda n: "{:,}".format(n).replace(",", "_")
        ),
        # extreme magnitudes
        st.integers(min_value=0, max_value=10**40).map(str),
        # signed
        st.integers(min_value=-(10**20), max_value=10**20).map(str),
        # zero with sign
        st.sampled_from(["+0", "-0", "0"]),
    )

def _hex_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0x%X" % n),
        st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "0x%x" % n),
        st.integers(min_value=0, max_value=0xFFFF).map(
            lambda n: "0x" + "{:x}".format(n).replace("", "_").strip("_")
        ),
        st.just("0x0"),
        st.just("0xFFFFFFFFFFFFFFFFFFFFFFFF"),
    )

def _oct_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0o7777).map(lambda n: "0o%o" % n),
        st.just("0o0"),
        st.just("0o7777777777777777777777"),
    )

def _bin_int():
    return st.one_of(
        st.integers(min_value=0, max_value=0xFF).map(lambda n: "0b" + bin(n)[2:]),
        st.just("0b0"),
        st.just("0b" + "1" * 64),
    )

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    return st.one_of(
        # ordinary
        st.floats(allow_nan=False, allow_infinity=False, width=64).map(repr),
        # missing fraction digit
        st.integers(min_value=0, max_value=1000).map(lambda n: "%d." % n),
        # missing leading digit
        st.integers(min_value=0, max_value=1000).map(lambda n: ".%d" % n),
        # exponents
        st.integers(min_value=-400, max_value=400).map(lambda e: "1e%d" % e),
        st.integers(min_value=-400, max_value=400).map(lambda e: "1E+%d" % e),
        # extreme
        st.just("1e309"),
        st.just("1e-400"),
        st.just("1.7976931348623157e+308"),
        # underscores
        st.just("1_000.000_1"),
        # inf / nan
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )

# ---------- date-time ----------

def _year():
    return st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)

def _month():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _day():
    return st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)

def _full_date():
    return st.tuples(_year(), _month(), _day()).map(lambda t: "%s-%s-%s" % t)

def _partial_time():
    return st.tuples(
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        st.one_of(st.none(), st.integers(min_value=0, max_value=999999).map(lambda n: ".%d" % n)),
    ).map(lambda t: "%s:%s:%s%s" % (t[0], t[1], t[2], t[3] or ""))

def _offset():
    return st.one_of(
        st.just("Z"),
        st.just("z"),
        st.tuples(
            st.sampled_from(["+", "-"]),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
            st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n),
        ).map(lambda t: "%s%s:%s" % t),
    )

def _delim():
    return st.sampled_from(["T", "t", " "])

def _offset_date_time():
    return st.tuples(_full_date(), _delim(), _partial_time(), _offset()).map(
        lambda t: "%s%s%s%s" % t
    )

def _local_date_time():
    return st.tuples(_full_date(), _delim(), _partial_time()).map(
        lambda t: "%s%s%s" % t
    )

def _local_date():
    return _full_date()

def _local_time():
    return _partial_time()

def _date_time():
    return st.one_of(
        _offset_date_time(),
        _local_date_time(),
        _local_date(),
        _local_time(),
    )

def _bool():
    return st.sampled_from(["true", "false"])

# ---------- keys ----------

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_quoted_key(), _bare_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=3).map(lambda ks: ".".join(ks))

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- recursive values ----------

def _scalar_value():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _bool(),
        _date_time(),
    )

def _value(depth):
    if depth <= 0:
        return _scalar_value()
    return st.one_of(
        _scalar_value(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )

def _array(depth):
    inner = st.lists(
        st.one_of(
            _value(depth),
            st.just(""),
        ),
        max_size=4,
    )
    def render(items):
        # allow trailing comma and newlines
        body = ", ".join(items)
        if items and st.randoms is not None:
            pass
        return "[" + body + "]"
    return inner.map(render)

def _inline_table(depth):
    pair = st.tuples(_key(), _value(depth)).map(lambda t: "%s = %s" % t)
    pairs = st.lists(pair, max_size=3)
    def render(ps):
        return "{" + ", ".join(ps) + "}"
    return pairs.map(render)

def _any_value():
    return _value(3)

# ---------- documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="\x00\n",
                ),
                min_size=0,
                max_size=20,
            ),
            st.integers(min_value=1, max_value=0x1F).map(chr),
        ),
        max_size=6,
    ).map(lambda cs: "#" + "".join(cs))

def _key_value_line():
    return st.tuples(_key(), _any_value()).map(lambda t: "%s = %s" % t)

def _standard_table():
    return _key().map(lambda k: "[" + k + "]")

def _array_table():
    return _key().map(lambda k: "[[" + k + "]]")

def _expression():
    return st.one_of(
        _key_value_line(),
        _standard_table(),
        _array_table(),
        _comment(),
    )

def _document():
    lines = st.lists(_expression(), max_size=6)
    def render(ls):
        return "\n".join(ls)
    return lines.map(render)

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        # unterminated basic string
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters='"\x00\n',
            ),
            min_size=1,
            max_size=6,
        ).map(lambda s: 'a = "' + s),
        # unterminated literal string
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="'\x00\n",
            ),
            min_size=1,
            max_size=6,
        ).map(lambda s: "a = '" + s),
        # missing closing bracket on array
        st.just("a = [1, 2, 3"),
        # doubled delimiter
        st.just("a = [[1, 2]]]"),
        # stray token
        st.just("a = = 1"),
        # missing equals
        st.just("a 1"),
        # newline inside inline table (rejected by parser)
        st.just("a = {b = 1,\n c = 2}"),
        # invalid escape
        st.just('a = "\\q"'),
        # value on next line
        st.just("a =\n1"),
        # non-ASCII bare key
        st.just("é = 1"),
        # duplicate keys
        st.just("a = 1\na = 2"),
        # duplicate tables
        st.just("[t]\n[t]"),
        # table and array of tables same name
        st.just("[t]\n[[t]]"),
        # empty key pieces
        st.just(" = 1"),
        st.just("[ ]"),
        st.just("[]"),
        st.just("[[ ]]"),
        # trailing dot in dotted key
        st.just("a. = 1"),
        # leading dot
        st.just(".a = 1"),
    )

# ---------- strategy ----------

def _depth_band():
    # Concentrate interesting depth in the 1500-2048 band for nesting.
    return st.integers(min_value=1500, max_value=2048)

def _deep_array(depth):
    # Build nested arrays up to `depth` levels.
    def build(n):
        if n <= 0:
            return st.just("[]")
        return build(n - 1).map(lambda s: "[" + s + "]")
    return build(depth)

def _deep_inline_table(depth):
    def build(n):
        if n <= 0:
            return st.just("{}")
        return build(n - 1).map(lambda s: "{a = " + s + "}")
    return build(depth)

def _deep_nesting():
    return st.one_of(
        _depth_band().flatmap(_deep_array),
        _depth_band().flatmap(_deep_inline_table),
    )

def _edge_documents():
    return st.one_of(
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("# comment\n"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just("[[a]]\n[[a]]"),
        st.just('"" = 1'),
        st.just("'' = 1"),
        st.just("a = []"),
        st.just("a = {}"),
        st.just("a = [[]]"),
        st.just("a = [{b = 1}]"),
        st.just("a = {b = 1,}"),
        st.just("a = 007"),
        st.just("a = 1."),
        st.just("a = .5"),
        st.just('a = "x\x01y"'),
        st.just("# comment with \x01 control"),
        st.just("a = 1979-02-30"),
        st.just("a = 1e309"),
        st.just("a = 0xFFFFFFFFFFFFFFFFFFFFFFFF"),
        st.just("a = 1_000"),
        st.just("a = inf"),
        st.just("a = -inf"),
        st.just("a = nan"),
        st.just("a = true"),
        st.just("a = false"),
        st.just("a = 1979-05-27T07:32:00Z"),
        st.just("a = 1979-05-27 07:32:00Z"),
        st.just("a = 1979-05-27T07:32:00"),
        st.just("a = 1979-05-27"),
        st.just("a = 07:32:00"),
        st.just("a = 07:32:00.999999"),
        st.just("a = {b = 1, c = 2}"),
        st.just("a = [1, 2, 3,]"),
        st.just("a = [\n1,\n2,\n]"),
        st.just("a.b.c = 1"),
        st.just('"a b" = 1'),
        st.just("'a b' = 1"),
        st.just("a = \"\"\"multi\nline\"\"\""),
        st.just("a = '''multi\nline'''"),
        st.just("a = \"\\u0041\""),
        st.just("a = \"\\U0001F600\""),
        st.just("a = \"\\u0000\""),
        st.just("a = 1\r\nb = 2"),
        st.just("\ta = 1"),
        st.just("a = 1"),
        st.just("a = 1\n"),
        st.just("a" * 10000 + " = 1"),
        st.just("[a.b.c]"),
        st.just("[a]\n[a.b]"),
        st.just("[a.b]\n[a]"),
        st.just("[[a.b]]"),
        st.just("a = {b = {c = {d = 1}}}"),
    )

def _documents():
    return st.one_of(
        _document(),
        _malformed(),
        _edge_documents(),
        _deep_nesting(),
    )

# ---------- improved: structure-aware document generator ----------

def _header_path():
    # 1-4 dotted segments, each a simple key, for table headers.
    return st.lists(_simple_key(), min_size=1, max_size=4).map(lambda ks: ".".join(ks))

def _table_line():
    return _header_path().map(lambda p: "[" + p + "]")

def _array_table_line():
    return _header_path().map(lambda p: "[[" + p + "]]")

def _kv_line():
    return st.tuples(_key(), _any_value()).map(lambda t: "%s = %s" % t)

def _blank_or_comment():
    return st.one_of(
        st.just(""),
        _comment(),
    )

def _structured_document():
    # A sequence of sections: optional header, then key/value lines,
    # interleaved with comments/blank lines. This produces documents that
    # exercise table scoping, dotted keys, and mixed content far more
    # than the flat random line list.
    body_line = st.one_of(_kv_line(), _blank_or_comment())
    section = st.tuples(
        st.one_of(_table_line(), _array_table_line(), st.just("")),
        st.lists(body_line, max_size=4),
    ).map(lambda t: "\n".join([t[0]] + t[1]) if t[0] else "\n".join(t[1]))
    sections = st.lists(section, max_size=4)
    return sections.map(lambda ss: "\n".join(ss))

def _dotted_key_doc():
    # Deep dotted keys and nested inline tables/arrays with shared prefixes.
    def one(i):
        prefix = ".".join("k%d" % j for j in range(i + 1))
        return prefix + " = " + "{a = [1, 2, {b = 3}]}"
    return st.integers(min_value=0, max_value=5).map(
        lambda n: "\n".join(one(i) for i in range(n + 1))
    )

def _string_heavy_doc():
    # Documents dominated by tricky strings (escapes, multiline, unicode).
    line = st.tuples(_key(), _string()).map(lambda t: "%s = %s" % t)
    return st.lists(line, max_size=5).map(lambda ls: "\n".join(ls))

def _number_heavy_doc():
    line = st.tuples(_key(), st.one_of(_integer(), _float())).map(
        lambda t: "%s = %s" % t
    )
    return st.lists(line, max_size=6).map(lambda ls: "\n".join(ls))

def _datetime_heavy_doc():
    line = st.tuples(_key(), _date_time()).map(lambda t: "%s = %s" % t)
    return st.lists(line, max_size=6).map(lambda ls: "\n".join(ls))

def _deep_structured():
    # Deeply nested arrays/inline tables with moderate depth (safe for
    # generation), wrapped in a table header to exercise nesting contexts.
    depth = st.integers(min_value=1, max_value=40)
    def build_array(n):
        def b(k):
            if k <= 0:
                return st.just("[]")
            return b(k - 1).map(lambda s: "[" + s + "]")
        return b(n)
    def build_table(n):
        def b(k):
            if k <= 0:
                return st.just("{}")
            return b(k - 1).map(lambda s: "{a = " + s + "}")
        return b(n)
    return st.tuples(
        depth,
        st.sampled_from(["array", "table"]),
    ).flatmap(
        lambda t: (
            build_array(t[0]) if t[1] == "array" else build_table(t[0])
        ).map(lambda body: "[t]\na = " + body)
    )

def _documents():
    return st.one_of(
        _document(),
        _structured_document(),
        _dotted_key_doc(),
        _string_heavy_doc(),
        _number_heavy_doc(),
        _datetime_heavy_doc(),
        _deep_structured(),
        _malformed(),
        _edge_documents(),
        _deep_nesting(),
    )

# ---------- improved: token/whitespace fuzzing and grammar-aware mutation ----------

# Whitespace variants (spaces, tabs, CRLF, blank lines) to exercise lexer.
_ws = st.sampled_from([" ", "  ", "\t", "\r\n", "\n", " \t "])
_nl = st.sampled_from(["\n", "\r\n"])

def _ws_wrapped_document():
    # Emit a valid key/value line with randomized surrounding whitespace,
    # trailing comments, and CRLF/LF mixing. Targets whitespace handling
    # and comment termination edge cases.
    def line():
        return st.tuples(
            _ws, _key(), _ws, st.just("="), _ws, _any_value(), _ws,
            st.one_of(st.just(""), _comment()),
        ).map(lambda t: "".join(t))
    lines = st.lists(line(), max_size=5)
    return st.tuples(lines, _nl).map(lambda t: t[1].join(t[0]))

def _comment_edge_document():
    # Comments with tricky terminators: CR, EOF without newline, control
    # bytes, and very long comment bodies.
    body = st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="\x00\n\r",
            ),
            min_size=0,
            max_size=40,
        ),
        st.integers(min_value=1, max_value=0x1F).map(chr).map(lambda c: "x" + c + "y"),
        st.just("x" * 500),
    )
    return st.tuples(st.just("#"), body, st.sampled_from(["", "\n", "\r", "\r\n"])).map(
        lambda t: t[0] + t[1] + t[2]
    )

def _header_edge_document():
    # Table/array-table headers with whitespace, dotted keys, quoted keys,
    # and malformed closers.
    inner = st.one_of(
        _header_path(),
        st.tuples(_ws, _header_path(), _ws).map(lambda t: "".join(t)),
    )
    closer = st.sampled_from(["]", "]]", "]", "]]]", ""])
    opener = st.sampled_from(["[", "[[", "[ ", "[[ "])
    return st.tuples(opener, inner, _ws, closer).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    )

def _string_escape_fuzz():
    # Strings built from a small alphabet of escape-relevant bytes to
    # maximize coverage of escape/terminator handling.
    alphabet = st.sampled_from(list('\\"/btnfruU0123456789xXvabce \t'))
    inner = st.lists(alphabet, max_size=12).map("".join)
    quote = st.sampled_from(['"', "'", '"""', "'''"])
    return st.tuples(quote, inner, quote).map(lambda t: t[0] + t[1] + t[2])

def _escape_heavy_doc():
    line = st.tuples(_key(), _string_escape_fuzz()).map(lambda t: "%s = %s" % t)
    return st.lists(line, max_size=5).map(lambda ls: "\n".join(ls))

def _number_edge_doc():
    # Numbers near grammar boundaries: leading zeros, signs, underscores
    # in invalid positions, incomplete exponents, bare dots.
    tok = st.one_of(
        st.sampled_from([
            "0", "-0", "+0", "00", "01", "0_0", "_1", "1_", "1__2",
            "0x", "0x_", "0b", "0o", "0o8", "0b2",
            "1e", "1e+", "1e-", "1.e5", ".e5", "1.2.3", "1_2_3",
            "+", "-", ".", "..", "1..2",
            "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
            "1e999999", "1e-999999",
        ]),
        _integer(),
        _float(),
    )
    line = st.tuples(_key(), tok).map(lambda t: "%s = %s" % t)
    return st.lists(line, max_size=6).map(lambda ls: "\n".join(ls))

def _brackets_fuzz():
    # Random sequences of brackets/braces/commas/equals to stress the
    # parser's structural error recovery.
    toks = st.sampled_from(["[", "]", "[[", "]]", "{", "}", ",", "=", " ", "\n", "a", "1"])
    return st.lists(toks, max_size=20).map("".join)

def _truncated_valid():
    # Generate a valid document, then truncate it at a random point to
    # exercise EOF handling in every grammar production.
    base = _structured_document()
    return st.tuples(base, st.integers(min_value=0, max_value=200)).map(
        lambda t: t[0][: t[1]]
    )

def _documents():
    return st.one_of(
        _document(),
        _structured_document(),
        _dotted_key_doc(),
        _string_heavy_doc(),
        _number_heavy_doc(),
        _datetime_heavy_doc(),
        _deep_structured(),
        _malformed(),
        _edge_documents(),
        _deep_nesting(),
        _ws_wrapped_document(),
        _comment_edge_document(),
        _header_edge_document(),
        _escape_heavy_doc(),
        _number_edge_doc(),
        _brackets_fuzz(),
        _truncated_valid(),
    )

strategy = _documents()
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar (no run feedback is provided).
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.