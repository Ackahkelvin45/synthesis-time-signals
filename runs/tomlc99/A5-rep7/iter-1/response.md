```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic building blocks
# ---------------------------------------------------------------------------

_WS = st.sampled_from(["", " ", "\t", "  ", " \t "])
_NL = st.sampled_from(["\n", "\r\n", "\n\n", "\r\n\r\n"])

# Bare keys: ASCII letters, digits, '-', '_' (non-ASCII bare keys are rejected).
_BARE_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
_bare_key = st.text(alphabet=_BARE_KEY_CHARS, min_size=1, max_size=12)

# Escape sequences
_esc_simple = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)
_esc_unicode = st.builds(lambda h: "\\u" + h, _hex4)
_esc_ex_unicode = st.builds(lambda h: "\\U" + h, _hex8)
_esc_invalid = st.sampled_from(["\\q", "\\x", "\\u12", "\\U123", "\\", "\\'"])

# Characters safe inside strings (no raw NUL, no quote/backslash/newline for
# basic strings; literal strings forbid newline and single quote).
_plain_char = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00",
)
_plain_char_no_nl = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters="\x00\n\r",
)
# Raw control bytes are accepted by the parser inside strings and comments.
_ctrl_char = st.sampled_from(["\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1b", "\x7f"])

# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

_esc = st.one_of(_esc_simple, _esc_unicode, _esc_ex_unicode, _esc_invalid)

_basic_inner_char = st.one_of(_plain_char_no_nl.filter(lambda c: c not in '"\\'), _ctrl_char)
_basic_inner = st.one_of(_basic_inner_char, _esc)
_basic_string = st.builds(
    lambda parts: '"' + "".join(parts) + '"',
    st.lists(_basic_inner, max_size=10),
)

_literal_inner_char = st.one_of(_plain_char_no_nl.filter(lambda c: c != "'"), _ctrl_char)
_literal_string = st.builds(
    lambda parts: "'" + "".join(parts) + "'",
    st.lists(_literal_inner_char, max_size=10),
)

# Multiline strings: content may include newlines; avoid a bare """ / ''' inside.
_ml_basic_unit = st.one_of(
    _basic_inner_char,
    _esc,
    st.just("\n"),
    st.just("\r\n"),
)
_ml_basic_string = st.builds(
    lambda parts: '"""' + "".join(parts) + '"""',
    st.lists(_ml_basic_unit, max_size=12),
)

_ml_literal_unit = st.one_of(
    _literal_inner_char,
    st.just("\n"),
    st.just("\r\n"),
)
_ml_literal_string = st.builds(
    lambda parts: "'''" + "".join(parts) + "'''",
    st.lists(_ml_literal_unit, max_size=12),
)

# Unterminated / malformed string fragments (near-valid-but-broken).
_unterminated_string = st.one_of(
    st.builds(lambda s: s[:-1], _basic_string),
    st.builds(lambda s: s[:-1], _literal_string),
    st.builds(lambda s: s[:-3], _ml_basic_string),
    st.builds(lambda s: s[:-3], _ml_literal_string),
    st.just('"'),
    st.just("'"),
    st.just('"""'),
    st.just("'''"),
)

_string = st.one_of(
    _basic_string,
    _literal_string,
    _ml_basic_string,
    _ml_literal_string,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_digit = st.integers(min_value=0, max_value=9)
_digit_str = st.builds(str, _digit)

_dec_int_simple = st.builds(
    lambda sign, body: sign + body,
    st.sampled_from(["", "+", "-"]),
    st.one_of(
        _digit_str,
        st.builds(
            lambda d, rest: d + rest,
            st.integers(min_value=1, max_value=9).map(str),
            st.text(alphabet="0123456789_", min_size=0, max_size=10),
        ),
    ),
)

# Leading zeros accepted by the parser (deviation).
_dec_int_leading_zero = st.builds(
    lambda sign, zeros, rest: sign + zeros + rest,
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0", min_size=1, max_size=5),
    st.text(alphabet="0123456789_", min_size=0, max_size=8),
)

_big_int = st.builds(
    lambda sign, body: sign + body,
    st.sampled_from(["", "-"]),
    st.integers(min_value=10**18, max_value=10**40).map(str),
)

_hex_int = st.builds(
    lambda body: "0x" + body,
    st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=16),
)
_oct_int = st.builds(
    lambda body: "0o" + body,
    st.text(alphabet="01234567_", min_size=1, max_size=16),
)
_bin_int = st.builds(
    lambda body: "0b" + body,
    st.text(alphabet="01_", min_size=1, max_size=16),
)

_integer = st.one_of(
    _dec_int_simple,
    _dec_int_leading_zero,
    _big_int,
    _hex_int,
    _oct_int,
    _bin_int,
    st.sampled_from(["0", "+0", "-0", "1_000", "1_0_0", "0x0", "0o0", "0b0"]),
)

_float_frac = st.builds(
    lambda d: "." + d,
    st.text(alphabet="0123456789_", min_size=0, max_size=12),
)
_float_exp = st.builds(
    lambda e, sign, d: e + sign + d,
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789_", min_size=1, max_size=6),
)
_float_body = st.one_of(
    st.builds(
        lambda i, f, e: i + f + e,
        st.text(alphabet="0123456789", min_size=1, max_size=8),
        _float_frac,
        st.one_of(st.just(""), _float_exp),
    ),
    st.builds(
        lambda i, e: i + e,
        st.text(alphabet="0123456789", min_size=1, max_size=8),
        _float_exp,
    ),
    # Parser accepts "1." and ".5".
    st.builds(lambda i: i + ".", st.text(alphabet="0123456789", min_size=1, max_size=8)),
    st.builds(lambda f: "." + f, st.text(alphabet="0123456789", min_size=1, max_size=8)),
)
_float = st.builds(
    lambda sign, body: sign + body,
    st.sampled_from(["", "+", "-"]),
    _float_body,
)

_inf = st.sampled_from(["inf", "+inf", "-inf"])
_nan = st.sampled_from(["nan", "+nan", "-nan"])
_extreme_float = st.sampled_from(
    ["1e309", "-1e309", "1e-309", "1e999", "1e-999", "0.0", "-0.0", "1e0"]
)

_floating_point = st.one_of(_float, _inf, _nan, _extreme_float)

# ---------------------------------------------------------------------------
# Booleans and date-times
# ---------------------------------------------------------------------------

_bool = st.sampled_from(["true", "false"])

_year = st.text(alphabet="0123456789", min_size=4, max_size=4)
_month = st.text(alphabet="0123456789", min_size=2, max_size=2)
_day = st.text(alphabet="0123456789", min_size=2, max_size=2)
_hour = st.text(alphabet="0123456789", min_size=2, max_size=2)
_minute = st.text(alphabet="0123456789", min_size=2, max_size=2)
_second = st.text(alphabet="0123456789", min_size=2, max_size=2)
_secfrac = st.builds(lambda d: "." + d, st.text(alphabet="0123456789", min_size=1, max_size=6))
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.builds(
        lambda s, h, m: s + h + ":" + m,
        st.sampled_from(["+", "-"]),
        _hour,
        _minute,
    ),
)

_full_date = st.builds(lambda y, m, d: y + "-" + m + "-" + d, _year, _month, _day)
_partial_time = st.builds(
    lambda h, m, s, frac: h + ":" + m + ":" + s + frac,
    _hour,
    _minute,
    _second,
    st.one_of(st.just(""), _secfrac),
)
_full_time = st.builds(lambda pt, off: pt + off, _partial_time, _offset)

_offset_date_time = st.builds(lambda d, dl, t: d + dl + t, _full_date, _delim, _full_time)
_local_date_time = st.builds(lambda d, dl, t: d + dl + t, _full_date, _delim, _partial_time)
_local_date = _full_date
_local_time = _partial_time

# Calendar-invalid dates accepted by the parser (deviation).
_invalid_date = st.sampled_from(
    ["1979-02-30", "2021-13-01", "2021-00-00", "0000-00-00", "9999-99-99"]
)

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    _invalid_date,
)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------
# Depth band: concentrate interesting depth in 1500-2048 for the recursive
# productions.  Hypothesis' recursive() with a max_leaves controls breadth;
# depth is driven by a separate "depth budget" integer we thread through.

_scalar = st.one_of(
    _string,
    _integer,
    _floating_point,
    _bool,
    _date_time,
    _unterminated_string,
)

# We build recursive values with st.recursive, mapping tuples to joined text.
# The recursion is over a "value" strategy that includes arrays and inline
# tables.  A depth parameter is approximated via recursive's max_leaves.

def _array_of(inner):
    # inner: strategy producing str values
    return st.builds(
        lambda elems: "[" + ", ".join(elems) + "]",
        st.lists(inner, max_size=6),
    )

def _inline_table_of(inner):
    def _kv(pair):
        k, v = pair
        return k + " = " + v
    return st.builds(
        lambda pairs: "{" + ", ".join(_kv(p) for p in pairs) + "}",
        st.lists(
            st.tuples(_key, inner).map(lambda p: (p[0], p[1])),
            max_size=5,
        ),
    )

# Placeholder; _key defined below.  We use a forward reference via a lambda.
def _key_strategy():
    return _key

_value = st.recursive(
    _scalar,
    lambda children: st.one_of(
        _array_of(children),
        _inline_table_of(children),
    ),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_quoted_key = st.one_of(_basic_string, _literal_string)
_simple_key = st.one_of(_bare_key, _quoted_key)
_dotted_key = st.builds(
    lambda parts: ".".join(parts),
    st.lists(_simple_key, min_size=2, max_size=4),
)
_key = st.one_of(_simple_key, _dotted_key)

# ---------------------------------------------------------------------------
# Arrays, inline tables, tables, documents
# ---------------------------------------------------------------------------

# Multiline array with comments and trailing comma.
_array_multiline = st.builds(
    lambda elems: "[\n" + ",\n".join(elems) + ",\n]",
    st.lists(_value, max_size=5),
)
_array_empty = st.just("[]")
_array_simple = st.builds(
    lambda elems: "[" + ", ".join(elems) + "]",
    st.lists(_value, max_size=6),
)
_array = st.one_of(_array_empty, _array_simple, _array_multiline)

_inline_table_empty = st.just("{}")
_inline_table_simple = st.builds(
    lambda pairs: "{" + ", ".join(k + " = " + v for k, v in pairs) + "}",
    st.lists(st.tuples(_key, _value), max_size=5),
)
# Trailing comma in inline table is accepted by the parser (deviation).
_inline_table_trailing_comma = st.builds(
    lambda pairs: "{" + ", ".join(k + " = " + v for k, v in pairs) + ",}",
    st.lists(st.tuples(_key, _value), min_size=1, max_size=5),
)
_inline_table = st.one_of(
    _inline_table_empty,
    _inline_table_simple,
    _inline_table_trailing_comma,
)

_value_full = st.one_of(_value, _array, _inline_table)

# ---------------------------------------------------------------------------
# Deep nesting: build arrays/inline tables up to ~2048 levels.
# ---------------------------------------------------------------------------

def _deep_value():
    depth = st.integers(min_value=1, max_value=2048)
    return st.builds(
        lambda d: "[" * d + "]" * d,
        depth,
    )

def _deep_inline():
    depth = st.integers(min_value=1, max_value=2048)
    return st.builds(
        lambda d: "{" * d + "}" * d,
        depth,
    )

_deep_nesting = st.one_of(_deep_value(), _deep_inline())

# ---------------------------------------------------------------------------
# Key/value lines, tables, documents
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

_ws = st.one_of(st.just(""), st.just(" "), st.just("\t"), st.just("  "))

_key_value = st.builds(
    lambda k, eq, v: k + " " + eq + " " + v,
    _key,
    st.just("="),
    _value_full,
)

_key_value_line = st.builds(
    lambda kv, c: kv + c,
    _key_value,
    st.one_of(st.just(""), st.builds(lambda c: "  " + c, _comment)),
)

_standard_table = st.builds(
    lambda k: "[" + k + "]",
    _key,
)
_array_table = st.builds(
    lambda k: "[[" + k + "]]",
    _key,
)

_table_line = st.one_of(_standard_table, _array_table)

# Near-valid-but-malformed lines.
_malformed_line = st.one_of(
    # Missing closing delimiter.
    st.builds(lambda k: "[" + k, _key),
    st.builds(lambda k: "[[" + k + "]", _key),
    # Doubled delimiter.
    st.builds(lambda k: "[[" + k + "]]]", _key),
    # Stray token.
    st.sampled_from(["@", "=", "]", "}", "]]", "==", "a =", "= 1"]),
    # Missing equals.
    st.builds(lambda k, v: k + " " + v, _key, _value_full),
    # Value on the next line.
    st.builds(lambda k, v: k + " =\n" + v, _key, _value_full),
    # Duplicate key (same line twice, joined by newline).
    st.builds(
        lambda k, v1, v2: k + " = " + v1 + "\n" + k + " = " + v2,
        _key,
        _value_full,
        _value_full,
    ),
    # Newline inside inline table.
    st.builds(
        lambda k, v: "{" + k + " =\n" + v + "}",
        _key,
        _value_full,
    ),
)

_line = st.one_of(
    _key_value_line,
    _table_line,
    _comment,
    st.just(""),
    _malformed_line,
)

_document = st.builds(
    lambda lines, trailing: "\n".join(lines) + trailing,
    st.lists(_line, min_size=0, max_size=12),
    st.sampled_from(["", "\n", "\r\n"]),
)

# Documents with deep nesting.
_deep_document = st.builds(
    lambda k, v: k + " = " + v,
    _key,
    _deep_nesting,
)

# Duplicate table / duplicate array-table.
_dup_table_doc = st.builds(
    lambda k: "[" + k + "]\n[" + k + "]",
    _key,
)
_dup_array_table_doc = st.builds(
    lambda k: "[[" + k + "]]\n[[" + k + "]]",
    _key,
)

# Empty / comment-only documents.
_empty_doc = st.sampled_from(["", "\n", "\r\n", "# just a comment", "# c\n\n# d\n"])

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

strategy = st.one_of(
    _document,
    _deep_document,
    _dup_table_doc,
    _dup_array_table_doc,
    _empty_doc,
    # Standalone value documents (a bare key = value).
    st.builds(lambda k, v: k + " = " + v, _key, _value_full),
    # Extreme numeric documents.
    st.builds(
        lambda v: "x = " + v,
        st.one_of(_integer, _floating_point, _extreme_float, _inf, _nan),
    ),
    # Escape / non-ASCII string documents.
    st.builds(lambda s: "s = " + s, _string),
    # Embedded control bytes inside strings (no raw NUL).
    st.builds(
        lambda s: "s = " + s,
        st.builds(
            lambda inner: '"' + inner + '"',
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="\x00",
                ),
                min_size=1,
                max_size=12,
            ),
        ),
    ),
)
```