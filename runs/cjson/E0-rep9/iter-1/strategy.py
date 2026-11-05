from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- scalars ----------

_ws_chars = " \t\n\r"
_ws = st.text(alphabet=_ws_chars, max_size=3)

_hex = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=8)

def _num_strategy():
    sign = st.sampled_from(["", "-"])
    int_part = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**18).map(str),
        st.integers(min_value=1, max_value=10**6).map(str),
        st.just("01"),  # leading zero (accepted by parser)
        st.just("007"),
        st.just("0x10"),  # hex (accepted)
        st.just("0xDEADBEEF"),
    )
    frac = st.one_of(
        st.just(""),
        st.tuples(st.just("."), st.integers(min_value=0, max_value=10**6).map(str)).map(_join),
        st.just("."),  # trailing dot (accepted)
    )
    exp = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["", "+", "-"]),
            st.integers(min_value=0, max_value=10**6).map(str),
        ).map(_join),
        st.sampled_from(["e309", "E309", "e-309", "e999999", "e+308", "e0"]),
    )
    return st.tuples(sign, int_part, frac, exp).map(_join)

_number = _num_strategy()

# ---------- strings ----------

_safe = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters='"\\',
    ),
    max_size=8,
)

def _escape():
    return st.one_of(
        st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
        st.tuples(st.just("\\u"), _hex).map(_join),
        st.sampled_from([
            "\\u0000", "\\uD800", "\\uDC00", "\\uFFFF", "\\u00e9",
            "\\uDBFF", "\\uDFFF", "\\u12", "\\uZZZZ", "\\u",
        ]),
    )

def _raw_control():
    return st.sampled_from(["\x00", "\x01", "\x1f", "\x7f", "\t", "\n", "\r"])

_str_body = st.one_of(_safe, _escape(), _raw_control())

def _string():
    return st.tuples(
        st.just('"'),
        st.lists(_str_body, max_size=6),
        st.just('"'),
    ).map(lambda t: t[0] + "".join(t[1]) + t[2])

_string_strategy = _string()

# malformed / unterminated strings
_unterminated_string = st.tuples(
    st.just('"'),
    st.lists(_str_body, max_size=6),
).map(lambda t: t[0] + "".join(t[1]))

# ---------- literals ----------

_literal = st.sampled_from(["true", "false", "null", "NaN", "Infinity", "-Infinity"])

# ---------- recursive JSON ----------

_json = st.recursive(
    st.one_of(_string_strategy, _number, _literal),
    lambda children: st.one_of(_array(children), _object(children)),
    max_leaves=20,
)

def _array(children):
    inner = st.one_of(
        st.just(""),
        st.lists(children, min_size=1, max_size=4).map(lambda xs: ",".join(xs)),
        st.lists(children, min_size=1, max_size=3).map(lambda xs: ",".join(xs) + ","),  # trailing comma
        st.lists(children, min_size=2, max_size=3).map(lambda xs: ",".join(xs) + ",,"),  # double comma
    )
    return st.tuples(st.just("["), inner, st.just("]")).map(_join)

def _pair(children):
    key = st.one_of(_string_strategy, _unterminated_string)
    sep = st.sampled_from([":", "", "::", " : ", "  "])
    val = children
    return st.tuples(key, sep, val).map(_join)

def _object(children):
    inner = st.one_of(
        st.just(""),
        st.lists(_pair(children), min_size=1, max_size=4).map(lambda xs: ",".join(xs)),
        st.lists(_pair(children), min_size=1, max_size=3).map(lambda xs: ",".join(xs) + ","),
        st.lists(_pair(children), min_size=2, max_size=3).map(lambda xs: ",".join(xs) + ",,"),
    )
    return st.tuples(st.just("{"), inner, st.just("}")).map(_join)

# ---------- deep nesting near the 1000 limit ----------

def _deep_nesting():
    # produce depth near 1000 using a compact filler
    filler = st.sampled_from(["0", '""', "[]", "{}", "null"])
    depth = st.one_of(
        st.integers(min_value=995, max_value=1003),
        st.sampled_from([1000, 1001, 999, 1002]),
    )
    kind = st.sampled_from(["arr", "obj"])

    def build(t):
        d, k, f = t
        if k == "arr":
            return "[" * d + f + "]" * d
        else:
            return '{"a":' * d + f + "}" * d

    return st.tuples(depth, kind, filler).map(build)

# ---------- top-level assembly ----------

def _top():
    lead = st.one_of(st.just(""), st.just("\ufeff"), _ws)
    trail = st.one_of(st.just(""), _ws, st.just("\x00"), st.sampled_from(["abc", " 1 2", "}"]))
    core = st.one_of(
        _json,
        _deep_nesting(),
        _unterminated_string,
        st.just(""),
        st.just("-"),
        st.just("+1"),
        st.just(".5"),
        st.just("1."),
        st.just("01"),
        st.just("1e309"),
        st.just("0x10"),
        st.just('"\\ud800"'),
        st.just("NaN"),
        st.just("Infinity"),
        st.just("[,]"),
        st.just("{,}"),
        st.just('{"a"}'),
        st.just('{"a":}'),
        st.just("[1,]"),
        st.just('{"a":1,}'),
        st.just("'x'"),
        st.just("{a:1}"),
    )
    return st.tuples(lead, core, trail).map(_join)

strategy = _top()