from hypothesis import strategies as st
import json

# ---------- scalar fragments ----------

_SAFE_CHARS = [chr(c) for c in range(0x20, 0x7f) if chr(c) not in ('"', '\\')]

_safe_text = st.text(alphabet=_SAFE_CHARS, max_size=8)

_escapes = st.sampled_from([
    '\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t',
    '\\u0000', '\\u001f', '\\u007f', '\\u00e9', '\\u20ac',
    '\\uD800', '\\uDC00', '\\uDFFF', '\\uFFFF', '\\uabcd', '\\uABCD',
    '\\u0000\\u0000', '\\uD83D\\uDE00',
])

# raw control bytes that are legal inside the *text* of a JSON string per the
# grammar are excluded (SAFECODEPOINT forbids 0x00-0x1f), but we do want the
# escape forms.  We never emit a raw NUL anywhere.

_string_piece = st.one_of(_safe_text, _escapes)


def _make_string():
    return st.lists(_string_piece, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')


_string = _make_string()


# ---------- numbers ----------

_int_digits = st.text(alphabet="0123456789", min_size=1, max_size=6)

_int_part = st.one_of(
    st.just("0"),
    st.tuples(st.sampled_from("123456789"), _int_digits).map(lambda t: t[0] + t[1]),
)

_frac = st.tuples(st.just("."), _int_digits).map(lambda t: t[0] + t[1])

_exp = st.tuples(
    st.sampled_from("eE"),
    st.sampled_from(["", "+", "-"]),
    _int_digits,
).map(lambda t: t[0] + t[1] + t[2])

_sign = st.sampled_from(["", "-"])

_number = st.tuples(
    _sign,
    _int_part,
    st.one_of(st.just(""), _frac),
    st.one_of(st.just(""), _exp),
).map(lambda t: t[0] + t[1] + t[2] + t[3])

# extreme magnitudes / overflow
_extreme_number = st.sampled_from([
    "1e309", "-1e309", "1e308", "-1e308", "1e999", "1e-999",
    "1e1000", "1.7976931348623157e308", "1.8e308",
    "0" * 400, "1" + "0" * 400, "1e" + "0" * 400,
    "123456789012345678901234567890", "-0", "0.0", "-0.0",
    "1e01", "1E+01", "1e-01",
])

# near-valid / malformed numbers
_bad_number = st.sampled_from([
    "-", "+", "+1", ".5", "-.5", "1.", "01", "-01", "00", "1e", "1e+", "1e-",
    "--1", "1..2", "1.2.3", "0x1f", "Infinity", "NaN", "-Infinity",
    "1e309extra",
])


# ---------- recursive value ----------

def _make_value():
    leaves = [
        _string,
        _number,
        _extreme_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ]
    return st.one_of(
        st.recursive(
            st.one_of(leaves),
            lambda children: st.one_of(
                _make_obj(children),
                _make_arr(children),
            ),
            max_leaves=20,
        ),
        st.one_of(leaves),
    )


def _make_obj(children):
    # a pair is a STRING ':' value
    pair = st.tuples(children, st.just(":"), children).map(
        lambda t: _string_or_str(t[0]) + t[1] + _value_str(t[2])
    )
    pairs = st.lists(pair, max_size=4).map(lambda ps: ",".join(ps))
    return st.tuples(st.just("{"), pairs, st.just("}")).map(lambda t: t[0] + t[1] + t[2])


def _make_arr(children):
    elems = st.lists(children, max_size=4).map(lambda xs: ",".join(_value_str(x) for x in xs))
    return st.tuples(st.just("["), elems, st.just("]")).map(lambda t: t[0] + t[1] + t[2])


def _value_str(x):
    return x if isinstance(x, str) else str(x)


def _string_or_str(x):
    return x if isinstance(x, str) else str(x)


# ---------- deep nesting near the cap ----------

_deep_open = st.integers(min_value=1, max_value=2100)
_deep_close = st.integers(min_value=1, max_value=2100)


def _make_deep():
    # deeply nested arrays / objects near the 2048 limit
    open_n = st.integers(min_value=1500, max_value=2100)
    close_n = st.integers(min_value=1500, max_value=2100)
    inner = st.one_of(st.just("0"), st.just("null"), _string)
    return st.tuples(open_n, close_n, inner).map(
        lambda t: "[" * t[0] + t[2] + "]" * t[1]
    )


def _make_deep_obj():
    open_n = st.integers(min_value=1000, max_value=2100)
    close_n = st.integers(min_value=1000, max_value=2100)
    return st.tuples(open_n, close_n).map(
        lambda t: '{"a":' * t[0] + "0" + "}" * t[1]
    )


# ---------- malformed / near-valid whole documents ----------

_malformed = st.sampled_from([
    '{"a":1,}',          # trailing comma in obj
    '[1,2,]',            # trailing comma in arr
    '{"a" 1}',           # missing colon
    '{"a":}',            # missing value
    '{"a":1',            # unterminated obj
    '[1,2',              # unterminated arr
    '"abc',              # unterminated string
    '"abc\\',            # trailing backslash
    '{"a":1 "b":2}',     # missing comma between pairs
    '[,]',               # double/leading comma
    '[1,,2]',            # double comma
    '{,}',               # lone comma
    '{:"v"}',            # missing key
    'tru',               # truncated literal
    'nul',               # truncated literal
    'fals',              # truncated literal
    'truefalse',         # trailing content
    '[]xyz',             # trailing garbage (accepted)
    '1abc',              # trailing garbage (accepted)
    '1 garbage',         # trailing garbage (accepted)
    '-',                 # lone sign (accepted as 0)
    '-.',                # lone sign+dot
    '+1',                # leading plus
    '.5',                # leading dot
    '1.',                # trailing dot
    '01',                # leading zero
    '{"k":0,"k":1}',     # duplicate keys (rejected)
    '{"a":{"a":{"a":1}}}',
    '[]',
    '{}',
    '',
    ' ',
    '\t\n\r ',
])


# ---------- top-level ----------

def _make_document():
    value = _make_value()
    return st.one_of(
        value,
        _make_value(),
        _make_deep(),
        _make_deep_obj(),
        _malformed,
        _bad_number,
        _extreme_number,
        _string,
        _number,
    )


# Favor structured documents (arrays/objects) more heavily so that the
# recursive object/array branches of the parser are exercised more often,
# while still keeping scalar and malformed cases for the leaf branches.
_structured = st.recursive(
    st.one_of([
        _string,
        _number,
        _extreme_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    ]),
    lambda children: st.one_of(_make_obj(children), _make_arr(children)),
    max_leaves=20,
)

# Improve fuzzing: mix structured documents, deeply nested cases, and
# malformed inputs to hit more parser branches. Add generation of
# well-formed but varied documents via json.dumps to reach valid-parse
# success paths that were under-covered.
def _json_value(depth):
    if depth <= 0:
        return st.one_of(
            _string,
            _number,
            _extreme_number,
            st.just("true"),
            st.just("false"),
            st.just("null"),
        )
    return st.one_of(
        _string,
        _number,
        _extreme_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
        st.lists(_json_value(depth - 1), max_size=4).map(json.dumps),
        st.dictionaries(
            _string.map(lambda s: json.loads(s)),
            _json_value(depth - 1),
            max_size=4,
        ).map(json.dumps),
    )


_valid_doc = st.integers(min_value=1, max_value=4).flatmap(_json_value)

strategy = st.one_of(
    _structured,
    _structured,
    _structured,
    _make_deep(),
    _make_deep_obj(),
    _malformed,
    _bad_number,
    _make_document(),
    _valid_doc,
)