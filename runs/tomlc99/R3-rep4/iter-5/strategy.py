from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _join(*parts):
    return "".join(parts)

# characters that are safe-ish raw inside strings (no NUL, but include controls)
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

# Non-ASCII characters to exercise UTF-8 -> UCS conversion paths.
_NON_ASCII = st.text(
    alphabet=st.characters(
        min_codepoint=0x80,
        blacklist_categories=("Cs",),
    ),
    min_size=1,
    max_size=6,
)

# Raw UTF-8 encoded multi-byte sequences (as literal characters) to stress
# the utf8 decoder, including boundary codepoints.
_UTF8_BOUNDARY = st.sampled_from([
    "\u0080", "\u07ff", "\u0800", "\uffff",
    "\U00010000", "\U0010ffff",
    "\u00e9", "\u20ac", "\u4e2d", "\U0001f600",
])

# Multi-byte UTF-8 sequences rendered as raw bytes-in-str (surrogate-free
# latin-1 style) to exercise the utf8 decoder's byte-level paths.
_RAW_UTF8_BYTES = st.sampled_from([
    "\x80", "\xbf", "\xc0\xaf", "\xed\xa0\x80", "\xf4\x90\x80\x80",
    "\xff", "\xfe", "\xc3", "\xe2\x82", "\xf0\x9f",
    "\xc2\x80", "\xe0\xa0\x80", "\xf0\x90\x80\x80",
    "\xe2\x82\xac", "\xf0\x9f\x98\x80",
])

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
    _NON_ASCII,
    _UTF8_BOUNDARY,
    _RAW_UTF8_BYTES,
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
    st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="'\x00\n",
                ),
                max_size=8,
            ),
            _NON_ASCII,
            _UTF8_BOUNDARY,
            _RAW_UTF8_BYTES,
        ),
        max_size=4,
    ).map("".join),
)

ml_basic_body = st.one_of(
    _SAFE_ASCII,
    _ESCAPE,
    st.just("\\\n"),
    st.just("\\\r\n"),
    _RAW_STR_CHARS,
    _NON_ASCII,
    _UTF8_BOUNDARY,
    _RAW_UTF8_BYTES,
)

ml_basic_string = st.builds(
    lambda body: '"""' + body + '"""',
    st.lists(ml_basic_body, max_size=6).map("".join),
)

ml_literal_string = st.builds(
    lambda body: "'''" + body + "'''",
    st.lists(
        st.one_of(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs",),
                    blacklist_characters="'\x00",
                ),
                max_size=10,
            ),
            _NON_ASCII,
            _UTF8_BOUNDARY,
            _RAW_UTF8_BYTES,
        ),
        max_size=4,
    ).map("".join),
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

# Keys with surrounding whitespace and Unicode to stress walk_tabpath.
_ws_key = st.builds(
    lambda lead, k, trail: lead + k + trail,
    st.text(alphabet=" \t", max_size=2),
    simple_key,
    st.text(alphabet=" \t", max_size=2),
)

_unicode_key = st.builds(
    lambda k: '"' + k + '"',
    st.one_of(_NON_ASCII, _RAW_UTF8_BYTES),
)

key = st.one_of(simple_key, dotted_key, _ws_key, _unicode_key)

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
    # values already strings; sep is a separator string
    return "[" + sep.join(values) + "]"

def _inline_table_body(pairs, trailing_comma):
    inner = ", ".join(pairs)
    if trailing_comma and pairs:
        inner += ","
    return "{" + inner + "}"

def _kv_pair(k, v):
    return k + " = " + v

# We build the recursive value strategy with st.recursive.
# Leaf values (non-recursive).
leaf_value = st.one_of(
    any_string,
    integer,
    floating_point,
    boolean,
    date_time,
)

# For arrays: allow empty, single, multi, with comments/newlines/trailing comma.
def _array_from(child):
    def build(args):
        style, items, trailing = args
        if not items:
            return "[]"
        if style == 0:
            # single line
            sep = ", "
            body = sep.join(items)
            if trailing:
                body += ","
            return "[" + body + "]"
        if style == 1:
            # multiline with newlines and comments
            lines = []
            for it in items:
                lines.append("  " + it + ",")
            if not trailing and lines:
                lines[-1] = lines[-1][:-1]
            return "[\n" + "\n".join(lines) + "\n]"
        # mixed with comments
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

# depth band: concentrate interesting depth in 1..~40 but allow up to a few hundred
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

# A "line" in a document is one of these; each rendered string may itself
# contain newlines (multiline arrays/strings).
_line = st.one_of(
    key_value_line,
    standard_table_line,
    array_table_line,
    _comment,
)

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
    # missing closing bracket on array
    st.builds(lambda v: "a = [" + v, leaf_value),
    # doubled closing bracket
    st.builds(lambda v: "a = [" + v + "]]", leaf_value),
    # unterminated basic string
    st.builds(lambda s: 'a = "' + s, _SAFE_ASCII),
    # unterminated literal string
    st.builds(lambda s: "a = '" + s, _SAFE_ASCII),
    # stray token
    st.builds(lambda t: "a = " + t, st.sampled_from(["@", "$", "%", "&", "!", "?", "~", "`"])),
    # missing value
    st.just("a ="),
    # missing equals
    st.builds(lambda k: k + " 1", simple_key),
    # missing closing brace on inline table
    st.builds(lambda k, v: "a = {" + k + " = " + v, simple_key, leaf_value),
    # doubled equals
    st.builds(lambda k, v: k + " == " + v, simple_key, leaf_value),
    # newline inside inline table
    st.builds(lambda k, v: "a = {" + k + " = " + v + "\n}", simple_key, leaf_value),
    # invalid escape
    st.just('a = "\\q"'),
    # unterminated multiline
    st.builds(lambda s: 'a = """' + s, _SAFE_ASCII),
    # bare unicode key
    st.builds(lambda v: "\u00e9 = " + v, leaf_value),
    # invalid UTF-8 byte sequences (as latin-1 style raw bytes rendered in str)
    st.builds(lambda b: 'a = "' + b + '"', _RAW_UTF8_BYTES),
    # truncated / malformed UTF-8 in keys
    st.builds(lambda b: b + " = 1", _RAW_UTF8_BYTES),
    # table path with weird content to exercise walk_tabpath
    st.builds(lambda k: "[" + k + "]", st.one_of(
        st.just(""),
        st.just("."),
        st.just("a..b"),
        st.just(".a"),
        st.just("a."),
        st.builds(lambda a, b: a + "." + b, simple_key, st.just("")),
    )),
    # array-of-table with weird path
    st.builds(lambda k: "[[" + k + "]]", st.one_of(
        st.just(""),
        st.just("."),
        st.just("a..b"),
        st.builds(lambda a, b: a + "." + b, simple_key, st.just("")),
    )),
    # timestamp-oriented malformed inputs to exercise toml_timestamp_at
    st.builds(lambda s: "a = " + s, st.sampled_from([
        "1979-05-27T07:32:00", "1979-05-27T07:32:00Z",
        "1979-05-27T07:32:00.", "1979-05-27T07:32:00.12",
        "1979-05-27T07:32:00+", "1979-05-27T07:32:00+07",
        "1979-05-27T07:32:00+07:", "1979-05-27T07:32:00+07:32",
        "1979-05-27T07:32:00-", "1979-05-27T07:32:00-07:",
        "1979-05-27T07:32", "1979-05-27T07", "1979-05-27T",
        "1979-05-27", "1979-05", "1979-", "1979",
        "07:32:00", "07:32:00.", "07:32:00.1234567890123",
        "07:32", "07:", "07", "T07:32:00", "t07:32:00",
        "1979-05-27 07:32:00", "1979-05-27t07:32:00z",
        "1979-13-27T07:32:00Z", "1979-05-32T07:32:00Z",
        "1979-05-27T25:32:00Z", "1979-05-27T07:62:00Z",
        "1979-05-27T07:32:62Z",
        "1979-05-27T07:32:00+24:00",
        "1979-05-27T07:32:00+07:60",
        "1979-05-27T07:32:00.Z",
        "1979-05-27T07:32:00.123+07:32",
        "0000-00-00T00:00:00Z",
        "9999-99-99T99:99:99.999999999Z",
    ])),
)

# ---------------------------------------------------------------------------
# final strategy
# ---------------------------------------------------------------------------

def _maybe_malformed(doc, bad):
    return doc if doc is not None else bad

strategy = st.one_of(
    document,
    _malformed_cases,
    # deep nesting band for arrays
    st.builds(
        lambda depth, leaf: "a = " + ("[" * depth) + leaf + ("]" * depth),
        st.integers(min_value=1, max_value=200),
        leaf_value,
    ),
    # deep nesting for inline tables
    st.builds(
        lambda depth, leaf: "a = " + ("{x = " * depth) + leaf + ("}" * depth),
        st.integers(min_value=1, max_value=200),
        leaf_value,
    ),
    # documents exercising table path walking with nested tables
    st.builds(
        lambda n, leaf: "\n".join(
            ["[a" + "".join([".b" for _ in range(i)]) + "]\n" for i in range(n)]
            + ["x = " + leaf],
        ),
        st.integers(min_value=1, max_value=8),
        leaf_value,
    ),
)