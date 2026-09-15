```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join(parts):
    return "".join(parts)

# Characters that can appear raw inside a JSON string (JSON grammar SAFECODEPOINT).
_SAFE = st.characters(
    blacklist_categories=["Cs"],
    blacklist_characters='"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\',
)

# Raw control / NUL bytes allowed by the target parser inside strings.
_CONTROL = st.sampled_from(
    [chr(i) for i in range(0, 0x20)] + ["\x7f"]
)

_ESCAPE_SIMPLE = st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])

_HEX = st.sampled_from("0123456789abcdefABCDEF")

def _unicode_escape():
    return st.tuples(st.just("\\u"), _HEX, _HEX, _HEX, _HEX).map(_join)

# Surrogate escapes: lone surrogates are REJECTED by the parser, so we include
# them in the malformed bucket but also as valid-looking pairs sometimes.
_SURROGATE = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d", "D"]),
    st.sampled_from("89abAB"),
    _HEX,
    _HEX,
).map(_join)

# A valid surrogate pair (high then low) — accepted by the parser.
_SURROGATE_PAIR = st.tuples(
    st.just("\\u"),
    st.sampled_from(["d", "D"]),
    st.sampled_from("89abAB"),
    _HEX,
    _HEX,
    st.just("\\u"),
    st.sampled_from(["d", "D"]),
    st.sampled_from("cdefCDEF"),
    _HEX,
    _HEX,
).map(_join)

_STRING_INNER = st.one_of(
    _SAFE,
    _CONTROL,
    _ESCAPE_SIMPLE,
    _unicode_escape(),
    _SURROGATE_PAIR,
)

def _quoted(inner):
    return st.tuples(st.just('"'), inner, st.just('"')).map(_join)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_INT = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**18).map(str),
    st.integers(min_value=-(10**18), max_value=-1).map(str),
    # leading-zero integers: ACCEPTED by the parser (deviation)
    st.tuples(st.just("0"), st.integers(min_value=0, max_value=10**6).map(str)).map(_join),
)

_FRAC = st.one_of(
    st.tuples(st.just("."), st.integers(min_value=0, max_value=10**12).map(str)).map(_join),
    st.just("."),  # trailing dot: ACCEPTED (deviation)
)

_EXP = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10**6).map(str),
).map(_join)

# Extreme magnitudes: overflow like 1e309, tiny, huge exponents.
_EXTREME_EXP = st.sampled_from(
    ["e309", "e308", "e400", "e1000", "E309", "e-309", "e-400", "e+999", "e01", "e000"]
)

_NUMBER = st.one_of(
    _INT,
    st.tuples(_INT, _FRAC).map(_join),
    st.tuples(_INT, _EXP).map(_join),
    st.tuples(_INT, _FRAC, _EXP).map(_join),
    st.tuples(_INT, _EXTREME_EXP).map(_join),
    st.tuples(_INT, _FRAC, _EXTREME_EXP).map(_join),
    # hex numbers: ACCEPTED by the parser (deviation)
    st.tuples(
        st.sampled_from(["0x", "0X", "-0x", "-0X"]),
        st.integers(min_value=0, max_value=2**32).map(lambda n: format(n, "x")),
    ).map(_join),
)

# ---------------------------------------------------------------------------
# Recursive value / obj / arr
# ---------------------------------------------------------------------------

# Depth budget. Parser rejects >1000 nesting levels. Concentrate near the limit.
def _depth_choice():
    return st.one_of(
        st.integers(min_value=0, max_value=4),          # shallow
        st.integers(min_value=5, max_value=50),         # moderate
        st.integers(min_value=50, max_value=200),       # deep
        st.integers(min_value=900, max_value=1005),     # near the limit
    )

def _string_literal():
    return _quoted(_STRING_INNER)

def _ws():
    return st.text(alphabet=" \t\n\r", min_size=0, max_size=3)

def _comma():
    return st.tuples(_ws(), st.just(","), _ws()).map(_join)

def _colon():
    return st.tuples(_ws(), st.just(":"), _ws()).map(_join)

def _value_strategy():
    return st.one_of(
        _string_literal(),
        _NUMBER,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

def _pair():
    return st.tuples(_string_literal(), _colon(), _value_strategy()).map(_join)

# Deep nesting generators, built manually so we can target depth precisely.
def _nested_arr(depth):
    return st.tuples(
        st.just("[" * depth),
        _value_strategy(),
        st.just("]" * depth),
    ).map(_join)

def _nested_obj(depth):
    return st.tuples(
        st.just('{"k":' * depth),
        _value_strategy(),
        st.just("}" * depth),
    ).map(_join)

def _deep_value():
    return st.tuples(_depth_choice()).flatmap(
        lambda d: st.one_of(_nested_arr(d), _nested_obj(d))
    )

# ---------------------------------------------------------------------------
# Objects and arrays with moderate recursion
# ---------------------------------------------------------------------------

def _obj():
    return st.one_of(
        st.just("{}"),
        st.tuples(
            st.just("{"),
            _ws(),
            st.lists(_pair(), min_size=1, max_size=6).map(lambda ps: (",".join(ps))),
            _ws(),
            st.just("}"),
        ).map(_join),
        # duplicate keys
        st.tuples(
            st.just("{"),
            st.just('"k":0,"k":1,"k":2'),
            st.just("}"),
        ).map(_join),
    )

def _arr():
    return st.one_of(
        st.just("[]"),
        st.tuples(
            st.just("["),
            _ws(),
            st.lists(_value_strategy(), min_size=1, max_size=8).map(lambda vs: ",".join(vs)),
            _ws(),
            st.just("]"),
        ).map(_join),
    )

# ---------------------------------------------------------------------------
# Malformed / near-valid inputs
# ---------------------------------------------------------------------------

_MALFORMED = st.one_of(
    # double commas
    st.sampled_from(["[1,,2]", "[,1]", "[1,]", '{"a":1,,"b":2}', '{"a":1,}']),
    # missing colon
    st.sampled_from(['{"a" 1}', '{"a"}', '{"a":}']),
    # unterminated strings
    st.tuples(st.just('"'), _SAFE, st.just("")).map(_join),
    st.just('"abc'),
    st.just('{"a":"unterminated'),
    st.just('["x'),
    # leading + / .5 / lone -
    st.sampled_from(["+1", ".5", "-", "+", ".", "-.", "1e", "1e+", "1.2.3"]),
    # NaN / Infinity words (rejected by parser)
    st.sampled_from(["NaN", "Infinity", "-Infinity", "nan", "inf"]),
    # lone surrogate escapes (rejected)
    _SURROGATE,
    st.tuples(st.just('"'), _SURROGATE, st.just('"')).map(_join),
    # invalid escapes
    st.sampled_from(['"\\x"', '"\\u12"', '"\\uZZZZ"', '"\\"', '"\\']),
    # single quotes / unquoted keys
    st.sampled_from(["'a'", "{a:1}", "'1'", "{'a':1}"]),
    # empty input (rejected)
    st.just(""),
    # bare control at top level
    st.sampled_from(["\x00", "\x01", "\xff"]),
    # trailing commas
    st.sampled_from(["[1,2,]", '{"a":1,}']),
)

# ---------------------------------------------------------------------------
# Assembled strategy
# ---------------------------------------------------------------------------

def _bom():
    return st.sampled_from(["", "\ufeff"])

def _trailing():
    # trailing content is ACCEPTED (parser stops after first value)
    return st.one_of(
        st.just(""),
        st.text(alphabet="abc012 \t\n\x00", min_size=1, max_size=8),
    )

def _valid_ish():
    return st.one_of(
        _value_strategy(),
        _obj(),
        _arr(),
        _deep_value(),
    )

def _with_leading_bom(v):
    return st.tuples(_bom(), v).map(_join)

def _with_trailing(v):
    return st.tuples(v, _trailing()).map(_join)

def _build():
    valid = _valid_ish()
    # valid, optionally BOM-prefixed and trailing-junk-suffixed
    well_formed = st.tuples(_with_leading_bom(valid), _trailing()).map(_join)
    # explicit deep nesting near the limit
    near_limit = st.one_of(
        st.integers(min_value=995, max_value=1005).flatmap(
            lambda d: st.one_of(_nested_arr(d), _nested_obj(d))
        ),
    )
    return st.one_of(
        well_formed,
        near_limit,
        _MALFORMED,
    )

strategy = _build()
```