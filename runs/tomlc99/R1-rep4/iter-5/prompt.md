Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _join(*parts):
    return "".join(parts)

_RAW_STR_CHARS = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\x00",
    ),
    max_size=12,
)

_SAFE_ASCII = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    max_size=10,
)

_ESCAPE = st.one_of(
    st.sampled_from(["\\\"", "\\\\", "\\b", "\\f", "\\n", "\\r", "\\t", "\\/"]),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\u%04X" % (n & 0xFFFF)),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08X" % n),
    st.just("\\u0000"),
)

_BASIC_BODY = st.one_of(
    _SAFE_ASCII,
    _ESCAPE,
    _RAW_STR_CHARS,
)

# ---------------------------------------------------------------------------
# strings (four quoting forms)
# ---------------------------------------------------------------------------

basic_string = st.builds(
    lambda body: '"' + body + '"',
    st.lists(_BASIC_BODY, max_size=6).map("".join),
)

literal_string = st.builds(
    lambda body: "'" + body + "'",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\x00\n",
        ),
        max_size=8,
    ),
)

ml_basic_body = st.one_of(
    _SAFE_ASCII,
    _ESCAPE,
    st.just("\\\n"),
    st.just("\\\r\n"),
    _RAW_STR_CHARS,
)

ml_basic_string = st.builds(
    lambda body: '"""' + body + '"""',
    st.lists(ml_basic_body, max_size=6).map("".join),
)

ml_literal_string = st.builds(
    lambda body: "'''" + body + "'''",
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="'\x00",
        ),
        max_size=10,
    ),
)

any_string = st.one_of(
    basic_string,
    literal_string,
    ml_basic_string,
    ml_literal_string,
)

# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

_unquoted_key_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

unquoted_key = st.builds(
    lambda s: "".join(s),
    st.lists(_unquoted_key_char, min_size=1, max_size=8),
)

quoted_key = st.one_of(basic_string, literal_string)

simple_key = st.one_of(unquoted_key, quoted_key)

dotted_key = st.builds(
    lambda parts: ".".join(parts),
    st.lists(simple_key, min_size=2, max_size=4),
)

key = st.one_of(simple_key, dotted_key)

# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------

_dec_digit = st.sampled_from("0123456789")
_hex_digit = st.sampled_from("0123456789abcdefABCDEF")
_oct_digit = st.sampled_from("01234567")
_bin_digit = st.sampled_from("01")

def _digits_with_underscores(digit_strat, min_len, max_len, allow_lead_zero=True):
    def build(args):
        digits, use_us = args
        out = []
        for i, d in enumerate(digits):
            if i > 0 and use_us[i]:
                out.append("_")
            out.append(d)
        return "".join(out)
    return st.tuples(
        st.lists(digit_strat, min_size=min_len, max_size=max_len),
        st.lists(st.booleans(), min_size=max_len, max_size=max_len),
    ).map(build)

dec_int_body = st.builds(
    lambda sign, body: sign + body,
    st.sampled_from(["", "+", "-"]),
    _digits_with_underscores(_dec_digit, 1, 12),
)

hex_int = st.builds(
    lambda body: "0x" + body,
    _digits_with_underscores(_hex_digit, 1, 10),
)

oct_int = st.builds(
    lambda body: "0o" + body,
    _digits_with_underscores(_oct_digit, 1, 10),
)

bin_int = st.builds(
    lambda body: "0b" + body,
    _digits_with_underscores(_bin_digit, 1, 12),
)

integer = st.one_of(dec_int_body, hex_int, oct_int, bin_int)

_exp_part = st.builds(
    lambda sign, body: "e" + sign + body,
    st.sampled_from(["", "+", "-"]),
    _digits_with_underscores(_dec_digit, 1, 4),
)

def _frac_body():
    return _digits_with_underscores(_dec_digit, 0, 6)

float_frac = st.builds(
    lambda sign, ip, fp: sign + ip + "." + fp,
    st.sampled_from(["", "+", "-"]),
    _digits_with_underscores(_dec_digit, 0, 8),
    _digits_with_underscores(_dec_digit, 0, 8),
)

float_exp = st.builds(
    lambda sign, ip, fp, ex: sign + ip + fp + ex,
    st.sampled_from(["", "+", "-"]),
    _digits_with_underscores(_dec_digit, 0, 6),
    st.one_of(st.just(""), _digits_with_underscores(_dec_digit, 1, 6).map(lambda s: "." + s)),
    _exp_part,
)

float_special = st.builds(
    lambda sign, word: sign + word,
    st.sampled_from(["", "+", "-"]),
    st.sampled_from(["inf", "nan"]),
)

floating_point = st.one_of(float_frac, float_exp, float_special)

# ---------------------------------------------------------------------------
# booleans
# ---------------------------------------------------------------------------

boolean = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# date-times
# ---------------------------------------------------------------------------

def _two(min_v=0, max_v=99):
    return st.integers(min_value=min_v, max_value=max_v).map(lambda n: "%02d" % n)

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = _two(0, 99)
_day = _two(0, 99)
_hour = _two(0, 99)
_minute = _two(0, 99)
_second = _two(0, 99)

_secfrac = st.builds(
    lambda s: "." + s,
    st.lists(_dec_digit, min_size=1, max_size=9).map("".join),
)

_full_date = st.builds(
    lambda y, m, d: y + "-" + m + "-" + d,
    _year, _month, _day,
)

_partial_time = st.builds(
    lambda h, m, s, frac: h + ":" + m + ":" + s + frac,
    _hour, _minute, _second,
    st.one_of(st.just(""), _secfrac),
)

_delim = st.sampled_from(["T", "t", " "])

_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda sign, h, m: sign + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _hour, _minute,
    ),
)

_full_time = st.builds(
    lambda pt, off: pt + off,
    _partial_time, _offset,
)

offset_date_time = st.builds(
    lambda d, delim, t: d + delim + t,
    _full_date, _delim, _full_time,
)

local_date_time = st.builds(
    lambda d, delim, t: d + delim + t,
    _full_date, _delim, _partial_time,
)

local_date = _full_date
local_time = _partial_time

date_time = st.one_of(
    offset_date_time,
    local_date_time,
    local_date,
    local_time,
)

# ---------------------------------------------------------------------------
# recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

def _array_body(values, sep):
    return "[" + sep.join(values) + "]"

def _inline_table_body(pairs, trailing_comma):
    inner = ", ".join(pairs)
    if trailing_comma and pairs:
        inner += ","
    return "{" + inner + "}"

def _kv_pair(k, v):
    return k + " = " + v

leaf_value = st.one_of(
    any_string,
    integer,
    floating_point,
    boolean,
    date_time,
)

def _array_from(child):
    def build(args):
        style, items, trailing = args
        if not items:
            return "[]"
        if style == 0:
            sep = ", "
            body = sep.join(items)
            if trailing:
                body += ","
            return "[" + body + "]"
        if style == 1:
            lines = []
            for it in items:
                lines.append("  " + it + ",")
            if not trailing and lines:
                lines[-1] = lines[-1][:-1]
            return "[\n" + "\n".join(lines) + "\n]"
        lines = []
        for it in items:
            if it.startswith("#"):
                lines.append(it)
            else:
                lines.append("  " + it + ",")
        return "[\n" + "\n".join(lines) + "\n]"
    return st.builds(
        build,
        st.tuples(
            st.integers(min_value=0, max_value=2),
            st.lists(child, min_size=0, max_size=4),
            st.booleans(),
        ),
    )

def _inline_table_from(child):
    def build(args):
        pairs, trailing = args
        if not pairs:
            return "{}"
        body = ", ".join(pairs)
        if trailing:
            body += ","
        return "{" + body + "}"
    return st.builds(
        build,
        st.tuples(
            st.lists(
                st.builds(_kv_pair, simple_key, child),
                min_size=0,
                max_size=4,
            ),
            st.booleans(),
        ),
    )

def _value_from_children(child):
    return st.one_of(
        leaf_value,
        _array_from(child),
        _inline_table_from(child),
    )

depth_strategy = st.integers(min_value=1, max_value=40)

value = st.recursive(
    leaf_value,
    lambda children: st.one_of(
        _array_from(children),
        _inline_table_from(children),
    ),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# document structure: key/value lines, tables, arrays of tables, comments
# ---------------------------------------------------------------------------

_comment = st.builds(
    lambda body: "#" + body,
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters="\x00\n\r",
        ),
        max_size=20,
    ),
)

_nl = st.sampled_from(["\n", "\r\n"])

_ws = st.text(alphabet=" \t", max_size=3)

def _kv_line(k, v):
    return k + " = " + v

key_value_line = st.builds(
    _kv_line,
    key,
    value,
)

standard_table_line = st.builds(
    lambda k: "[" + k + "]",
    key,
)

array_table_line = st.builds(
    lambda k: "[[" + k + "]]",
    key,
)

_line = st.one_of(
    key_value_line,
    standard_table_line,
    array_table_line,
    _comment,
)

def _build_document(lines, nl, trailing_nl, leading_ws):
    out = []
    for i, line in enumerate(lines):
        if leading_ws:
            out.append(_ws.example() if False else "")
        out.append(line)
        out.append(nl)
    if not trailing_nl and out:
        out.pop()
    return "".join(out)

def _render_doc(args):
    lines, nl, trailing_nl = args
    parts = []
    for line in lines:
        parts.append(line)
        parts.append(nl)
    if not trailing_nl and parts:
        parts.pop()
    return "".join(parts)

document = st.builds(
    _render_doc,
    st.tuples(
        st.lists(_line, min_size=0, max_size=8),
        _nl,
        st.booleans(),
    ),
)

# ---------------------------------------------------------------------------
# near-valid-but-malformed inputs
# ---------------------------------------------------------------------------

def _malformed(kv, v):
    return kv + " = " + v

_malformed_cases = st.one_of(
    st.builds(lambda v: "a = [" + v, leaf_value),
    st.builds(lambda v: "a = [" + v + "]]", leaf_value),
    st.builds(lambda s: 'a = "' + s, _SAFE_ASCII),
    st.builds(lambda s: "a = '" + s, _SAFE_ASCII),
    st.builds(lambda t: "a = " + t, st.sampled_from(["@", "$", "%", "&", "!", "?", "~", "`"])),
    st.just("a ="),
    st.builds(lambda k: k + " 1", simple_key),
    st.builds(lambda k, v: "a = {" + k + " = " + v, simple_key, leaf_value),
    st.builds(lambda k, v: k + " == " + v, simple_key, leaf_value),
    st.builds(lambda k, v: "a = {" + k + " = " + v + "\n}", simple_key, leaf_value),
    st.just('a = "\\q"'),
    st.builds(lambda s: 'a = """' + s, _SAFE_ASCII),
    st.builds(lambda v: "\u00e9 = " + v, leaf_value),
)

# ---------------------------------------------------------------------------
# targeted coverage boosters for missing productions
# ---------------------------------------------------------------------------

_coverage_boosters = st.one_of(
    st.builds(lambda k: k + " = true", simple_key),
    st.builds(lambda k: k + " = false", simple_key),
    st.builds(lambda k: k + " = inf", simple_key),
    st.builds(lambda k: k + " = +inf", simple_key),
    st.builds(lambda k: k + " = -inf", simple_key),
    st.builds(lambda k: k + " = nan", simple_key),
    st.builds(lambda k, n: k + " = " + n, simple_key, dec_int_body),
    st.builds(lambda k, n: k + " = " + n, simple_key, hex_int),
    st.builds(lambda k, n: k + " = " + n, simple_key, bin_int),
    st.builds(lambda k, n: k + " = " + n, simple_key, oct_int),
    st.builds(lambda k, s: k + " = " + s, simple_key, ml_literal_string),
    st.builds(lambda k, s: k + " = " + s, simple_key, ml_basic_string),
    st.builds(lambda k, s: k + " = " + s, simple_key, basic_string),
    st.builds(lambda k, s: k + " = " + s, simple_key, literal_string),
)

_deep_bounded = st.one_of(
    st.builds(
        lambda depth, leaf: "a = " + ("[" * depth) + leaf + ("]" * depth),
        st.integers(min_value=1, max_value=24),
        leaf_value,
    ),
    st.builds(
        lambda depth, leaf: "a = " + ("{x = " * depth) + leaf + ("}" * depth),
        st.integers(min_value=1, max_value=24),
        leaf_value,
    ),
)

_comment_booster = st.one_of(
    st.builds(lambda c: c, _comment),
    st.builds(lambda c, nl: c + nl, _comment, _nl),
    st.builds(lambda k, v, c: k + " = " + v + " " + c, simple_key, leaf_value, _comment),
    st.builds(lambda c, k, v: c + "\n" + k + " = " + v, _comment, simple_key, leaf_value),
)

_ml_basic_booster = st.one_of(
    st.builds(
        lambda k, body: k + " = \"\"\"" + body + "\"\"\"",
        simple_key,
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),
                blacklist_characters="\x00",
            ),
            max_size=12,
        ),
    ),
    st.builds(
        lambda k, a, b: k + " = \"\"\"" + a + "\n" + b + "\"\"\"",
        simple_key,
        _SAFE_ASCII,
        _SAFE_ASCII,
    ),
    st.builds(
        lambda k, a: k + " = \"\"\"\n" + a + "\n\"\"\"",
        simple_key,
        _SAFE_ASCII,
    ),
    st.builds(
        lambda k: k + " = \"\"\"\\\n   x\"\"\"",
        simple_key,
    ),
    st.builds(
        lambda k, a: k + " = \"\"\"" + a + "\\\"\"\"\"\"",
        simple_key,
        _SAFE_ASCII,
    ),
)

_offset_booster = st.one_of(
    st.builds(
        lambda k, dt: k + " = " + dt,
        simple_key,
        offset_date_time,
    ),
    st.builds(
        lambda k, y, mo, d, h, mi, s: k + " = " + y + "-" + mo + "-" + d + "T" + h + ":" + mi + ":" + s + "Z",
        simple_key, _year, _month, _day, _hour, _minute, _second,
    ),
    st.builds(
        lambda k, y, mo, d, h, mi, s, sign, oh, om: k + " = " + y + "-" + mo + "-" + d + "T" + h + ":" + mi + ":" + s + sign + oh + ":" + om,
        simple_key, _year, _month, _day, _hour, _minute, _second,
        st.sampled_from(["+", "-"]), _hour, _minute,
    ),
    st.builds(
        lambda k, y, mo, d, h, mi, s, frac, off: k + " = " + y + "-" + mo + "-" + d + " " + h + ":" + mi + ":" + s + frac + off,
        simple_key, _year, _month, _day, _hour, _minute, _second,
        _secfrac, _offset,
    ),
)

# ---------------------------------------------------------------------------
# dotted_key booster: the only remaining production gap. Exercise dotted
# keys in every syntactic position: key/value, standard table, array table,
# inline table keys, and nested dotted keys.
# ---------------------------------------------------------------------------

_dotted_key_booster = st.one_of(
    # key = value with a dotted key
    st.builds(
        lambda k, v: k + " = " + v,
        dotted_key,
        leaf_value,
    ),
    # [dotted.key] standard table header
    st.builds(
        lambda k: "[" + k + "]",
        dotted_key,
    ),
    # [[dotted.key]] array-of-tables header
    st.builds(
        lambda k: "[[" + k + "]]",
        dotted_key,
    ),
    # dotted key inside an inline table
    st.builds(
        lambda dk, v: "a = {" + dk + " = " + v + "}",
        dotted_key,
        leaf_value,
    ),
    # dotted key followed by a nested table header
    st.builds(
        lambda dk, v, dk2: dk + " = " + v + "\n[" + dk2 + "]",
        dotted_key,
        leaf_value,
        dotted_key,
    ),
    # dotted key with quoted components
    st.builds(
        lambda parts, v: ".".join(parts) + " = " + v,
        st.lists(
            st.one_of(unquoted_key, quoted_key),
            min_size=2,
            max_size=4,
        ),
        leaf_value,
    ),
    # deeply dotted key path
    st.builds(
        lambda n, v: ".".join(["k%d" % i for i in range(n)]) + " = " + v,
        st.integers(min_value=2, max_value=8),
        leaf_value,
    ),
)

# ---------------------------------------------------------------------------
# final strategy
# ---------------------------------------------------------------------------

def _maybe_malformed(doc, bad):
    return doc if doc is not None else bad

strategy = st.one_of(
    document,
    _coverage_boosters,
    _comment_booster,
    _ml_basic_booster,
    _offset_booster,
    _dotted_key_booster,
    _malformed_cases,
    _deep_bounded,
    st.builds(
        lambda depth, leaf: "a = " + ("[" * depth) + leaf + ("]" * depth),
        st.integers(min_value=1, max_value=200),
        leaf_value,
    ),
    st.builds(
        lambda depth, leaf: "a = " + ("{x = " * depth) + leaf + ("}" * depth),
        st.integers(min_value=1, max_value=200),
        leaf_value,
    ),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 245,
    "reject": 105
  },
  "acceptance_rate": 0.7,
  "max_nesting_depth": 190,
  "productions_accepted": [
    "BASIC_STRING",
    "BIN_INT",
    "BOOLEAN",
    "COMMENT",
    "DEC_INT",
    "HEX_INT",
    "INF",
    "LITERAL_STRING",
    "LOCAL_DATE_TIME",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "NAN",
    "NL",
    "OCT_INT",
    "OFFSET_DATE_TIME",
    "UNQUOTED_KEY",
    "array_",
    "array_table",
    "array_values",
    "bool_",
    "comment",
    "comment_or_nl",
    "date_time",
    "document",
    "dotted_key",
    "expression",
    "floating_point",
    "inline_table",
    "inline_table_keyvals",
    "inline_table_keyvals_non_empty",
    "integer",
    "key",
    "key_value",
    "nl_or_comment",
    "quoted_key",
    "simple_key",
    "standard_table",
    "string",
    "table",
    "unquoted_key",
    "value"
  ],
  "productions_gap": [
    "FLOAT",
    "LOCAL_DATE",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.0,
  "novelty": 58,
  "divergences": 81,
  "divergence_examples": [
    "b\"[gNV.'n\\x0f\\xee\\xaf\\x9a']\"",
    "b'[\"\\\\U00000DA5\".\"\".\\'\\xc3\\x9d\\x0b\\xf1\\x99\\x98\\x82K\\xf0\\xae\\x8f\\xa6\\xf0\\xa1\\xba\\x94J\\xf0\\x93\\xa1\\xb8\\']'",
    "b'[\"\\\\U00000000\".b.\\'\\xc3\\x9d\\x0b\\xf1\\x99\\x98\\x82K\\xf0\\xae\\x8f\\xa6\\xf0\\xa1\\xba\\x94J\\xf0\\x93\\xa1\\xb8\\']'"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.