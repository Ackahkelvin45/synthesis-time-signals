from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- leaf tokens ----------

# Valid numbers, including extremes / overflow / non-finite.
_valid_numbers = st.one_of(
    st.integers(min_value=-(10 ** 18), max_value=10 ** 18).map(str),
    st.sampled_from([
        "0", "-0", "1", "-1", "10", "100", "12345678901234567890",
        "1e309", "-1e309", "1e-309", "1E+308", "1e308",
        "1.5", "-1.5", "0.0", "-0.0", "1.0e10", "1e01", "1E-01",
        "1e999999", "1e-999999", "9" * 30, "0." + "0" * 20 + "1",
        "123456789012345678901234567890.12345678901234567890e+123",
        "-",  # lone minus accepted by parser
    ]),
)

# Malformed number forms (rejected by strict reader, useful edge inputs).
_bad_numbers = st.sampled_from([
    "+1", ".5", "1.", "01", "007", "0x1F", "1e", "1e+", "1e-",
    "--1", "1..2", "1.2.3", "1e1e1", "0b1", "0o7", "1_000",
    "+", "+.5", "-.5", "-.", "1.e5", "e5", ".", "1 2",
])

# Basic safe string content (no quotes/backslash/control).
_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='\\"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
                        '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f',
)

_safe_body = st.text(alphabet=_safe_chars, min_size=0, max_size=12)

# Escape sequences.
_escapes = st.sampled_from([
    '\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t",
])

_unicode_escapes = st.one_of(
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04X" % n),
    st.sampled_from([
        "\\u0000", "\\u001f", "\\u007f", "\\u0080", "\\uffff",
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD800\\uDC00", "\\uD83D\\uDE00",
        "\\uD800\\uD800", "\\uDC00\\uDC00",
        "\\uZZZZ", "\\u12", "\\u", "\\u123", "\\u12345",
    ]),
)

# Raw control bytes / NUL embedded in a string body.
_raw_controls = st.sampled_from([
    "\x00", "\x01", "\x1f", "\x7f", "\x08", "\x0b", "\x0c",
    "\x00\x00", "a\x00b", "\x1f\x1f",
])

_string_piece = st.one_of(
    _safe_body,
    _escapes,
    _unicode_escapes,
    _raw_controls,
)

# Well-formed string literal.
_valid_string = st.lists(_string_piece, min_size=0, max_size=8).map(
    lambda parts: '"' + "".join(parts) + '"'
)

# Unterminated / malformed string variants.
_unterminated_string = st.lists(_string_piece, min_size=0, max_size=6).map(
    lambda parts: '"' + "".join(parts)
)
_bad_string = st.one_of(
    _unterminated_string,
    st.just("'single'"),
    st.just('"a"b"'),
    st.just('"\\"'),
    st.just('"\\x41"'),
    st.just('"\\u12"'),
    st.just('"unclosed\\'),
)

# ---------- recursive structure ----------

# Forward-declared strategy for values.
value = st.deferred(lambda: value_strategy)

# Object keys: mostly valid strings, occasionally duplicated.
_key = _valid_string

# A pair: key ':' value
_pair = st.tuples(_key, st.just(":"), value).map(lambda t: t[0] + t[1] + t[2])

# Malformed pair variants.
_bad_pair = st.one_of(
    st.tuples(_key, value).map(lambda t: t[0] + t[1]),           # missing colon
    st.tuples(_key, st.just("::"), value).map(lambda t: "".join(t)),
    st.tuples(value, st.just(":"), value).map(lambda t: t[0] + t[1] + t[2]),
    st.just(":"),
    st.just('"a":'),
)

_obj_members = st.lists(_pair, min_size=0, max_size=6)

def _build_obj(members):
    # Bias toward objects with members; sometimes duplicate keys, trailing comma.
    if not members:
        return "{}"
    body = ",".join(members)
    return "{" + body + "}"

_obj = _obj_members.map(_build_obj)

def _build_obj_dup(members):
    if not members:
        return '{"a":1,"a":2}'
    # Duplicate the first member.
    dup = members + [members[0]]
    return "{" + ",".join(dup) + "}"

_obj_dup = _obj_members.map(_build_obj_dup)

_obj_trailing_comma = _obj_members.map(
    lambda m: ("{" + ",".join(m) + ",}") if m else "{,}"
)

_obj_malformed = st.one_of(
    st.just("{,}"),
    st.just('{"a":1,,}'),
    st.just('{"a":1,,"b":2}'),
    st.just('{"a":}'),
    st.just('{"a" 1}'),
    st.just("{a:1}"),
    st.just('{"a":1'),
    st.just("{"),
    st.just("}"),
)

_arr_members = st.lists(value, min_size=0, max_size=6)

def _build_arr(members):
    if not members:
        return "[]"
    return "[" + ",".join(members) + "]"

_arr = _arr_members.map(_build_arr)

_arr_trailing_comma = _arr_members.map(
    lambda m: ("[" + ",".join(m) + ",]") if m else "[,]"
)

_arr_malformed = st.one_of(
    st.just("[1,,2]"),
    st.just("[,]"),
    st.just("[,1]"),
    st.just("[1,]"),
    st.just("["),
    st.just("]"),
    st.just("[1 2]"),
)

# Deep nesting: many nested brackets/braces.
_deep_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "]" * n
)
_deep_obj = st.integers(min_value=1, max_value=100).map(
    lambda n: '{"a":' * n + "null" + "}" * n
)

# ---------- top-level values ----------

_bool_null = st.sampled_from(["true", "false", "null"])

_malformed_scalar = st.one_of(
    _bad_numbers,
    _bad_string,
    st.just("True"), st.just("FALSE"), st.just("Null"),
    st.just("nul"), st.just("tru"),
    st.just("1abc"), st.just("[]xyz"), st.just("1 garbage"),
    st.just("true false"), st.just(""),
    st.just(" "), st.just("\x00"), st.just("\x00\x00"),
    st.just("//comment\n1"),
    st.just("/*x*/1"),
)

value_strategy = st.one_of(
    _valid_string,
    _valid_numbers,
    _bool_null,
    _obj,
    _obj_dup,
    _obj_trailing_comma,
    _obj_malformed,
    _arr,
    _arr_trailing_comma,
    _arr_malformed,
    _deep_arr,
    _deep_obj,
    _malformed_scalar,
)

# ---------- top-level strategy ----------

_ws = st.sampled_from(["", " ", "\n", "\t", "\r\n", "  "])

def _wrap(v):
    return v

def _with_ws(v):
    return st.tuples(_ws, st.just(v), _ws).map(lambda t: t[0] + t[1] + t[2])

# Mix: mostly valid-ish top-level values, plus some trailing-junk variants.
_top = value_strategy.flatmap(
    lambda v: st.one_of(
        st.just(v),
        _with_ws(v),
        st.just(v + " "),
        st.just(v + "\x00"),
        st.just(v + "abc"),
        st.just(v + "[]"),
    )
)

# ---------- intensify_near_crash ----------
# Mutate structurally around the crashing input by repeatedly wrapping and
# perturbing a generated value: nest it, truncate it, duplicate fragments,
# and inject boundary delimiters/whitespace to stress the parser's recursion
# and allocation paths near the crash site.

def _mutate_near_crash(v):
    return st.one_of(
        st.just("[" * 1 + v + "]"),
        st.just("[" * 2 + v + "]"),
        st.just("[" * 50 + v + "]"),
        st.just("[" * 200 + v + "]"),
        st.just('{"a":' + v + "}"),
        st.just('{"a":' + v + "}" * 2),
        st.just('{"a":' + v + "}" * 50),
        st.just('{"a":' + v + "}" * 100),
        st.just(v[: len(v) // 2]) if v else st.just(v),
        st.just(v + v),
        st.just(v + v + v),
        st.just(v + "," + v),
        st.just(v + ":" + v),
        st.just(v + "\x00" + v),
        st.just(v.rstrip() + "\x00"),
        st.just(v + " " * 4),
        st.just(" " * 4 + v),
        st.just(v + "]" * 10),
        st.just(v + "}" * 10),
        st.just(",".join([v] * 8)),
    )

strategy = _top.flatmap(_mutate_near_crash)