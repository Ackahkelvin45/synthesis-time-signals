```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

def _join(parts):
    return "".join(parts)

# ---------- scalar pieces ----------

SAFE_CHARS = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
                         '\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

def _plain_string_body():
    return st.text(SAFE_CHARS, min_size=0, max_size=12)

escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])

def _unicode_escape():
    hex4 = st.text("0123456789abcdefABCDEF", min_size=4, max_size=4)
    return hex4.map(lambda h: "\\u" + h)

def _surrogate_escape():
    return st.sampled_from([
        "\\uD800", "\\uDBFF", "\\uDC00", "\\uDFFF",
        "\\uD83D\\uDE00", "\\uD800\\uD800", "\\uDC00\\uDC00",
        "\\u0000", "\\u001f", "\\u007f", "\\uFFFF", "\\u00e9",
    ])

def _string_piece():
    return st.one_of(_plain_string_body(), escapes, _unicode_escape(), _surrogate_escape())

def _string_body():
    return st.lists(_string_piece(), min_size=0, max_size=8).map(_join)

def _quoted_string():
    return _string_body().map(lambda b: '"' + b + '"')

# ---------- numbers ----------

def _int_part():
    return st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=9).map(str),
        st.integers(min_value=10, max_value=10**18).map(str),
    )

def _frac_part():
    return st.text("0123456789", min_size=1, max_size=18).map(lambda d: "." + d)

def _exp_part():
    sign = st.sampled_from(["", "+", "-"])
    digits = st.text("0123456789", min_size=1, max_size=4)
    return st.tuples(sign, digits).map(lambda t: "e" + t[0] + t[1])

def _number():
    body = st.one_of(
        _int_part(),
        st.tuples(_int_part(), _frac_part()).map(lambda t: t[0] + t[1]),
        st.tuples(_int_part(), _exp_part()).map(lambda t: t[0] + t[1]),
        st.tuples(_int_part(), _frac_part(), _exp_part()).map(lambda t: t[0] + t[1] + t[2]),
    )
    neg = st.booleans()
    return st.tuples(neg, body).map(lambda t: ("-" if t[0] else "") + t[1])

def _extreme_number():
    return st.sampled_from([
        "1e309", "-1e309", "1e308", "1e-309", "1e-400", "0e0", "-0",
        "1E999", "9" * 30, "0." + "0" * 20 + "1",
        "1" + "0" * 300, "1e" + "9" * 10, "-1e-9999",
        "0.00000000000000000001", "123456789012345678901234567890",
    ])

def _number_or_extreme():
    return st.one_of(_number(), _extreme_number())

# ---------- malformed fragments ----------

MALFORMED_BITS = st.sampled_from([
    ",", ",,", ":", "::", "{", "}", "[", "]", '"', '""', "tru", "truee",
    "nul", "fals", "01", "+1", ".5", "1.", "-", "-.", "--1", "1..2",
    "1e", "1e+", "e5", '"unterminated', "'single'", "\\", "\\x", "\\u12",
    "\\uZZZZ", "NaN", "Infinity", "-Infinity", "undefined", "  ", "\t", "\n",
])

# ---------- recursive structure ----------

def _string_value():
    return _quoted_string()

def _pair(key_st, value_st):
    return st.tuples(key_st, value_st).map(lambda t: t[0] + ":" + t[1])

def _obj_contents(value_st):
    # empty, single, multiple pairs
    def make(pairs):
        return "{" + ",".join(pairs) + "}"
    return st.one_of(
        st.just("{}"),
        st.lists(_pair(_quoted_string(), value_st), min_size=1, max_size=4).map(make),
    )

def _arr_contents(value_st):
    def make(items):
        return "[" + ",".join(items) + "]"
    return st.one_of(
        st.just("[]"),
        st.lists(value_st, min_size=1, max_size=4).map(make),
    )

def _value_leaf():
    return st.one_of(
        _string_value(),
        _number_or_extreme(),
        st.sampled_from(["true", "false", "null"]),
    )

def _value_strategy():
    return st.recursive(
        _value_leaf(),
        lambda children: st.one_of(_obj_contents(children), _arr_contents(children)),
        max_leaves=40,
    )

# ---------- deep nesting near limit ----------

def _deep_nesting():
    # concentrate near 2048: mostly just under, some just over, some well under
    depth = st.one_of(
        st.integers(min_value=0, max_value=64),
        st.integers(min_value=2000, max_value=2052),
        st.integers(min_value=2048, max_value=2060),
        st.integers(min_value=1900, max_value=2048),
    )
    opener = st.sampled_from(["[", "{"])
    closer = st.sampled_from(["]", "}"])
    filler = st.one_of(
        st.just("0"),
        st.just('"k":0'),
        st.just("null"),
        st.just("[]"),
    )
    return st.tuples(depth, opener, closer, filler).map(
        lambda t: t[1] * t[0] + t[3] + t[2] * t[0]
    )

# ---------- duplicate keys ----------

def _duplicate_keys():
    key = st.sampled_from(['"k"', '"a"', '"dup"', '""'])
    val = st.one_of(_number_or_extreme(), _string_value(),
                    st.sampled_from(["true", "false", "null"]))
    n = st.integers(min_value=2, max_value=5)
    return st.tuples(key, val, n).map(
        lambda t: "{" + ",".join([t[0] + ":" + t[1]] * t[2]) + "}"
    )

# ---------- malformed / near-valid ----------

def _malformed():
    return st.one_of(
        # double commas / missing colons
        st.sampled_from([
            '{"a":1,,"b":2}',
            '{"a" 1}',
            '{"a":}',
            '{:1}',
            '[1,,2]',
            '[,1]',
            '[1,]',
            '{"a":1,}',
            '{"a":1 "b":2}',
            '[,]',
            '{,}',
            '[:]',
            '{"a":1:2}',
            '[1 2]',
            '{"a"}',
        ]),
        # unterminated strings
        st.sampled_from([
            '"abc',
            '{"a":"unterminated}',
            '["x',
            '"\\',
            '"\\u12',
        ]),
        # leading + / .5 / 01
        st.sampled_from([
            "+1", ".5", "01", "-.5", "1.", "+.5", "00", "007",
            "1e", "1e+", "1e-", "0x1", "1_000",
        ]),
        # trailing content (accepted by parser)
        st.tuples(_value_strategy(), st.text(SAFE_CHARS, min_size=1, max_size=6)).map(
            lambda t: t[0] + t[1]
        ),
        # lone sign (parses as 0)
        st.sampled_from(["-", "-.", "-e", "-.e1"]),
        # random malformed fragments
        st.lists(MALFORMED_BITS, min_size=1, max_size=6).map(_join),
    )

# ---------- top-level strategy ----------

def _top():
    return st.one_of(
        _value_strategy(),
        _deep_nesting(),
        _duplicate_keys(),
        _malformed(),
        # empty containers explicitly
        st.sampled_from(["{}", "[]", "{} ", "[ ]", "\n{}\n", "\t[]\t"]),
        # extreme scalars at top level
        _extreme_number(),
        _quoted_string(),
        # whitespace-padded valid values (parser should be whitespace-tolerant)
        st.tuples(
            st.text(" \t\n\r", min_size=0, max_size=4),
            _value_strategy(),
            st.text(" \t\n\r", min_size=0, max_size=4),
        ).map(lambda t: t[0] + t[1] + t[2]),
        # valid JSON produced by the stdlib encoder (round-trip oracle)
        st.recursive(
            st.one_of(
                st.none(),
                st.booleans(),
                st.integers(min_value=-(10**18), max_value=10**18),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(SAFE_CHARS, max_size=8),
            ),
            lambda children: st.one_of(
                st.lists(children, max_size=4),
                st.dictionaries(st.text(SAFE_CHARS, max_size=6), children, max_size=4),
            ),
            max_leaves=20,
        ).map(json.dumps),
    )

strategy = _top()
```