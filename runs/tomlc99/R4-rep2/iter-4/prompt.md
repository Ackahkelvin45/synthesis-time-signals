Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(*parts):
    return "".join(parts)

_ws = st.sampled_from(["", " ", "  ", "\t", " \t "])

def _comment():
    body = st.text(
        alphabet=st.characters(
            blacklist_categories=(), blacklist_characters="\x00\n\r"
        ),
        max_size=12,
    )
    return body.map(lambda b: "#" + b)

# ---------- UTF-8 byte-level helpers ----------

def _raw_utf8_bytes():
    lead = st.sampled_from([
        "\x00", "\x7f",
        "\xc2", "\xdf",
        "\xe0", "\xe9", "\xef",
        "\xf0", "\xf4", "\xf7",
        "\xf8", "\xfb",
        "\xfc", "\xfd",
        "\x80", "\xbf",
        "\xc0", "\xc1",
        "\xfe", "\xff",
    ])
    cont = st.sampled_from(["\x80", "\xbf", "\x9f", "\xa0", "A", "\xff", ""])
    return st.builds(
        lambda a, b, c, d, e, f: a + b + c + d + e + f,
        lead, cont, cont, cont, cont, cont,
    )

def _utf8_in_string():
    inner = st.lists(
        st.one_of(
            st.characters(blacklist_categories=(), blacklist_characters='"\x00\n').map(str),
            _basic_key_esc,
            _raw_utf8_bytes(),
        ),
        max_size=6,
    ).map("".join)
    basic = inner.map(lambda s: 'a = "' + s + '"')
    lit = st.lists(
        st.one_of(
            st.characters(blacklist_categories=(), blacklist_characters="'\x00\n"),
            _raw_utf8_bytes(),
        ),
        max_size=6,
    ).map(lambda cs: "a = '" + "".join(cs) + "'")
    key = _raw_utf8_bytes().map(lambda b: '"' + b + '" = 1')
    return st.one_of(basic, lit, key)

def _utf8_escape():
    cp = st.one_of(
        st.integers(min_value=0, max_value=0x10FFFF),
        st.integers(min_value=0xD800, max_value=0xDFFF),
        st.integers(min_value=0x110000, max_value=0x1FFFFF),
        st.just(0x7F),
        st.just(0x80),
        st.just(0x7FF),
        st.just(0x800),
        st.just(0xFFFF),
        st.just(0x10000),
        st.just(0x10FFFF),
    )
    u4 = cp.map(lambda c: '\\u%04X' % (c & 0xFFFF))
    U8 = cp.map(lambda c: '\\U%08X' % (c & 0xFFFFFFFF))
    return st.one_of(u4, U8).map(lambda esc: 'a = "' + esc + '"')

# ---------- keys ----------

_unquoted_key_char = st.sampled_from(
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
)

def _unquoted_key():
    return st.lists(_unquoted_key_char, min_size=1, max_size=8).map("".join)

_basic_key_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u0000", "\\U0001F600", "\\u00e9",
     "\\uD800", "\\uDFFF", "\\U00110000", "\\UFFFFFFFF"]
)

def _basic_string_inner():
    return st.lists(
        st.one_of(
            st.characters(
                blacklist_categories=(),
                blacklist_characters='"\x00\n',
            ).map(str),
            _basic_key_esc,
        ),
        max_size=6,
    ).map("".join)

def _basic_string():
    return _basic_string_inner().map(lambda s: '"' + s + '"')

def _literal_string():
    return st.lists(
        st.characters(
            blacklist_categories=(),
            blacklist_characters="'\x00\n",
        ),
        max_size=6,
    ).map(lambda cs: "'" + "".join(cs) + "'")

def _quoted_key():
    return st.one_of(_basic_string(), _literal_string())

def _simple_key():
    return st.one_of(_unquoted_key(), _quoted_key())

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(".".join)

def _key():
    return st.one_of(_simple_key(), _dotted_key())

# ---------- strings / values ----------

_ml_basic_esc = st.sampled_from(
    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
     "\\u0041", "\\u0000", "\\U0001F600", "\\\n", "\\\r\n",
     "\\uD800", "\\uDFFF", "\\U00110000"]
)

def _ml_basic_string():
    inner = st.lists(
        st.one_of(
            st.characters(
                blacklist_categories=(),
                blacklist_characters='"\x00',
            ).map(str),
            _ml_basic_esc,
        ),
        max_size=8,
    ).map("".join)
    return inner.map(lambda s: '"""' + s + '"""')

def _ml_literal_string():
    inner = st.lists(
        st.characters(
            blacklist_categories=(),
            blacklist_characters="'\x00",
        ),
        max_size=8,
    ).map("".join)
    return inner.map(lambda s: "'''" + s + "'''")

def _string():
    return st.one_of(
        _basic_string(),
        _literal_string(),
        _ml_basic_string(),
        _ml_literal_string(),
    )

def _digits():
    return st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)

def _underscored_digits(min_d=1, max_d=6):
    return st.lists(st.sampled_from("0123456789"), min_size=min_d, max_size=max_d).map(
        lambda ds: ds[0] + "".join("_" + d for d in ds[1:]) if len(ds) > 1 else ds[0]
    )

def _dec_int():
    return st.one_of(
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=8).map("".join),
        _underscored_digits(),
        st.just("0"),
        st.just("007"),
        st.just("0" * 30),
        st.integers(min_value=-2**70, max_value=2**70).map(str),
        st.integers(min_value=-2**63, max_value=2**64).map(str),
    )

def _hex_int():
    body = st.lists(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=6).map("".join)
    return body.map(lambda b: "0x" + b)

def _oct_int():
    body = st.lists(st.sampled_from("01234567"), min_size=1, max_size=6).map("".join)
    return body.map(lambda b: "0o" + b)

def _bin_int():
    body = st.lists(st.sampled_from("01"), min_size=1, max_size=8).map("".join)
    return body.map(lambda b: "0b" + b)

def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())

def _float():
    frac = st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join)
    exp = st.builds(
        lambda sign, ds: "e" + sign + ds,
        st.sampled_from(["", "+", "-"]),
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=3).map("".join),
    )
    plain = st.builds(
        lambda a, b: a + "." + b,
        _digits(),
        frac,
    )
    with_exp = st.builds(
        lambda a, b, e: a + "." + b + e,
        _digits(),
        frac,
        exp,
    )
    bare_exp = st.builds(lambda a, e: a + e, _digits(), exp)
    return st.one_of(
        plain,
        with_exp,
        bare_exp,
        st.just("1."),
        st.just(".5"),
        st.just("1e309"),
        st.just("-1e309"),
        st.just("0.0"),
        st.just("1_000.5"),
        st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
    )

def _bool():
    return st.sampled_from(["true", "false"])

def _date_time():
    year = st.lists(st.sampled_from("0123456789"), min_size=4, max_size=4).map("".join)
    month = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    day = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    hh = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    mm = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    ss = st.lists(st.sampled_from("0123456789"), min_size=2, max_size=2).map("".join)
    secfrac = st.builds(
        lambda ds: "." + ds,
        st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map("".join),
    )
    partial_time = st.builds(
        lambda h, m, s, f: h + ":" + m + ":" + s + f,
        hh, mm, ss, st.one_of(st.just(""), secfrac),
    )
    full_date = st.builds(lambda y, mo, d: y + "-" + mo + "-" + d, year, month, day)
    offset = st.one_of(
        st.just("Z"),
        st.builds(lambda s, h, m: s + h + ":" + m, st.sampled_from(["+", "-"]), hh, mm),
    )
    full_time = st.builds(lambda pt, off: pt + off, partial_time, offset)
    delim = st.sampled_from(["T", "t", " "])
    return st.one_of(
        st.builds(lambda d, dl, t: d + dl + t, full_date, delim, full_time),
        st.builds(lambda d, dl, t: d + dl + t, full_date, delim, partial_time),
        full_date,
        partial_time,
        st.just("1979-02-30"),
        st.just("1979-05-27 07:32:00Z"),
        st.just("0000-00-00"),
        st.just("23:59:59.999999"),
    )

# ---------- recursive arrays / inline tables ----------

def _value(depth):
    if depth <= 0:
        return st.one_of(
            _string(), _integer(), _float(), _bool(), _date_time(),
        )
    child = st.deferred(lambda: _value(depth - 1))
    return st.one_of(
        _string(), _integer(), _float(), _bool(), _date_time(),
        _array(child, depth),
        _inline_table(child, depth),
    )

def _array(child, depth):
    nl = st.sampled_from(["", " ", "\n", "\r\n", " \n ", "\n# c\n", "\t"])
    sep = st.builds(lambda a, b: a + "," + b, nl, nl)
    elems = st.lists(
        st.builds(lambda c, s: c + s, child, nl),
        min_size=0,
        max_size=4,
    ).map(lambda xs: "".join(xs))
    trailing = st.sampled_from(["", ",", " ,", ",\n"])
    return st.builds(
        lambda lead, body, tr, tail: "[" + lead + body + tr + tail + "]",
        nl, elems, trailing, nl,
    )

def _inline_table(child, depth):
    def pair(c):
        return st.builds(
            lambda k, eq, v: k + eq + v,
            _key(),
            st.sampled_from(["=", " = ", "\t=\t"]),
            c,
        )
    pairs = st.lists(
        st.builds(lambda p, ws: p + ws, pair(child), st.sampled_from(["", " ", "  "])),
        min_size=0,
        max_size=3,
    ).map(lambda xs: "".join(xs))
    trailing = st.sampled_from(["", ",", " ,"])
    return st.builds(
        lambda body, tr: "{" + body + tr + "}",
        pairs, trailing,
    )

# ---------- document lines ----------

def _key_value(depth):
    return st.builds(
        lambda k, eq, v, c: k + eq + v + c,
        _key(),
        st.sampled_from(["=", " = ", "\t=\t", "= "]),
        _value(depth),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _table():
    return st.builds(
        lambda k, c: "[" + k + "]" + c,
        _key(),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _array_table():
    return st.builds(
        lambda k, c: "[[" + k + "]]" + c,
        _key(),
        st.one_of(st.just(""), _comment().map(lambda c: " " + c)),
    )

def _line(depth):
    return st.one_of(
        _key_value(depth),
        _table(),
        _array_table(),
        _comment(),
        st.just(""),
    )

def _malformed(depth):
    return st.one_of(
        _basic_string_inner().map(lambda s: 'a = "' + s),
        st.lists(
            st.characters(blacklist_categories=(), blacklist_characters="'\x00\n"),
            max_size=5,
        ).map(lambda cs: "a = '" + "".join(cs)),
        _value(depth).map(lambda v: "a = [" + v),
        _value(depth).map(lambda v: "a = {b = " + v),
        _value(depth).map(lambda v: "a = [[" + v + "]]"),
        _value(depth).map(lambda v: "a = {{b = " + v + "}}"),
        st.just("a = 1 2"),
        st.just("a = "),
        st.just("= 1"),
        st.just("a b = 1"),
        st.just("[t"),
        st.just("[[t]"),
        st.just("a = {b = 1\n}"),
        st.just('a = "\\q"'),
        st.just("a = 1\nb = 2\nb = 3"),
        st.just("[t]\n[t]"),
        st.just("a = 1\nb"),
        st.just("\u00e9 = 1"),
        st.just("k\u00e9y = 1"),
        _raw_utf8_bytes().map(lambda b: 'a = "' + b + '"'),
        _raw_utf8_bytes().map(lambda b: "a = '" + b + "'"),
        _raw_utf8_bytes().map(lambda b: b + " = 1"),
        _raw_utf8_bytes().map(lambda b: "# " + b),
        _raw_utf8_bytes(),
        st.just('a = "\\u12"'),
        st.just('a = "\\U0011"'),
        st.just('a = "\\'),
        st.just('a = "\\u'),
    )

# ---------- NEW: basic-string escape stressors ----------
# Drive norm_basic_str: control chars, escapes, multi-line continuations,
# truncated \u/\U, invalid escapes, embedded quotes/backslashes.

_control_chars = st.sampled_from(
    [chr(c) for c in list(range(0x00, 0x09)) + list(range(0x0A, 0x20)) + [0x7F]]
)

def _norm_basic_stress():
    # pieces that exercise every branch of norm_basic_str
    pieces = st.one_of(
        st.sampled_from([
            "\\u0041", "\\U0001F600", "\\u00e9", "\\uD800", "\\uDFFF",
            "\\U00110000", "\\UFFFFFFFF",
            "\\u12", "\\U0011", "\\u", "\\U", "\\uZZZZ", "\\UZZZZZZZZ",
            "\\u0000", "\\u0008", "\\u0009", "\\u000A", "\\u001F", "\\u007F",
            "\\\\", '\\"', "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
            "\\q", "\\x41", "\\0", "\\",
            "\\\n", "\\\r\n", "\\ \n", "\\\t\n", "\\ \t\r\n",
            "\\\n   continued", "\\\r\n\tmore",
            '"', "\\\\\\", "\\\\\\u0041",
        ]),
        _control_chars,
        st.characters(blacklist_categories=(), blacklist_characters='"\x00').map(str),
    )
    body = st.lists(pieces, min_size=0, max_size=10).map("".join)
    basic = body.map(lambda s: 'a = "' + s + '"')
    ml = body.map(lambda s: 'a = """' + s + '"""')
    # unterminated / truncated end-of-input variants to hit "last backslash" path
    truncated = body.map(lambda s: 'a = "' + s)
    truncated_ml = body.map(lambda s: 'a = """' + s)
    return st.one_of(basic, ml, truncated, truncated_ml)

# ---------- NEW: table path walkers ----------
# Drive walk_tabpath / parse_select: deeply dotted keys, quoted segments,
# arrays-of-tables, and duplicate table definitions.

def _tabpath_stress():
    seg = st.one_of(
        _unquoted_key(),
        _basic_string(),
        _literal_string(),
        st.just('""'),
        st.just("''"),
    )
    deep = st.lists(seg, min_size=1, max_size=8).map(".".join)
    table = deep.map(lambda k: "[" + k + "]")
    aot = deep.map(lambda k: "[[" + k + "]]")
    kv = st.builds(
        lambda k, v: k + " = " + v,
        deep,
        st.one_of(_integer(), _string(), _bool()),
    )
    # duplicates / conflicting definitions
    dup = deep.map(lambda k: "[" + k + "]\n[" + k + "]")
    dup_aot = deep.map(lambda k: "[[" + k + "]]\n[[" + k + "]]")
    conflict = deep.map(lambda k: "[" + k + "]\n[[" + k + "]]")
    # child of a scalar
    scalar_then_child = deep.map(lambda k: k + " = 1\n[" + k + ".child]")
    return st.one_of(table, aot, kv, dup, dup_aot, conflict, scalar_then_child)

# ---------- document ----------

def _document():
    def lines(depth):
        return st.lists(
            _line(depth),
            min_size=0,
            max_size=6,
        ).map(lambda ls: "\n".join(ls))

    def with_malformed(depth):
        return st.one_of(lines(depth), _malformed(depth))

    base = with_malformed(2)
    return st.one_of(
        base,
        st.integers(min_value=1500, max_value=2048).flatmap(
            lambda d: st.builds(
                lambda v: "a = " + v,
                _value(d),
            )
        ),
        st.just(""),
        st.just("\n"),
        st.just("# only a comment"),
        st.just("# c1\n# c2\n"),
        st.builds(lambda s: s, base),
        lines(2).map(lambda s: s.replace("\n", "\r\n")),
        _utf8_in_string(),
        _utf8_escape(),
        st.builds(
            lambda a, b, c: a + "\n" + b + "\n" + c,
            _utf8_in_string(),
            _utf8_escape(),
            _utf8_in_string(),
        ),
        # NEW: dedicated stressors for under-covered functions
        _norm_basic_stress(),
        _tabpath_stress(),
        st.builds(
            lambda a, b: a + "\n" + b,
            _norm_basic_stress(),
            _tabpath_stress(),
        ),
    )

strategy = _document()
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 66.17,
  "region_coverage_pct": 66.57,
  "least_covered_functions": [
    "toml_utf8_to_ucs (0% of branches)",
    "toml_parse_file (0% of branches)",
    "norm_lit_str (0% of branches)",
    "toml_rtos (0% of branches)",
    "toml_timestamp_at (0% of branches)"
  ],
  "least_covered_function_source": "int toml_utf8_to_ucs(const char *orig, int len, int64_t *ret) {\n  const unsigned char *buf = (const unsigned char *)orig;\n  unsigned i = *buf++;\n  int64_t v;\n\n  /* 0x00000000 - 0x0000007F:\n     0xxxxxxx\n  */\n  if (0 == (i >> 7)) {\n    if (len < 1)\n      return -1;\n    v = i;\n    return *ret = v, 1;\n  }\n  /* 0x00000080 - 0x000007FF:\n     110xxxxx 10xxxxxx\n  */\n  if (0x6 == (i >> 5)) {\n    if (len < 2)\n      return -1;\n    v = i & 0x1f;\n    for (int j = 0; j < 1; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00000800 - 0x0000FFFF:\n     1110xxxx 10xxxxxx 10xxxxxx\n  */\n  if (0xE == (i >> 4)) {\n    if (len < 3)\n      return -1;\n    v = i & 0x0F;\n    for (int j = 0; j < 2; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00010000 - 0x001FFFFF:\n     11110xxx 10xxxxxx 10xxxxxx 10xxxxxx\n  */\n  if (0x1E == (i >> 3)) {\n    if (len < 4)\n      return -1;\n    v = i & 0x07;\n    for (int j = 0; j < 3; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x00200000 - 0x03FFFFFF:\n     111110xx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx\n  */\n  if (0x3E == (i >> 2)) {\n    if (len < 5)\n      return -1;\n    v = i & 0x03;\n    for (int j = 0; j < 4; j++) {\n      i = *buf++;\n      if (0x2 != (i >> 6))\n        return -1;\n      v = (v << 6) | (i & 0x3f);\n    }\n    return *ret = v, (const char *)buf - orig;\n  }\n\n  /* 0x04000000 - 0x7FFFFFFF:\n     1111110x 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx\n/* ... truncated ... */"
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.