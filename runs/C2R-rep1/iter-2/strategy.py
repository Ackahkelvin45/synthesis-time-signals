from hypothesis import strategies as st
import json

# ---------- primitive building blocks ----------

# Keys: bias toward simple ASCII keys, but include unicode escapes and control bytes.
_ascii_key = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters='"\\'),
    min_size=0,
    max_size=8,
)

_escaped_key = st.sampled_from(
    [
        "\\n",
        "\\t",
        "\\r",
        "\\b",
        "\\f",
        "\\/",
        "\\\\",
        "\\\"",
        "\\u0000",
        "\\u001f",
        "\\u0041",
        "\\uD800",
        "\\uDC00",
        "\\uD83D\\uDE00",
        "\\uFFFF",
        "\\u00e9",
    ]
)

_key_body = st.one_of(_ascii_key, _escaped_key)
_key = _key_body.map(lambda s: '"' + s + '"')

# Numbers: valid forms plus the parser's lenient/extreme cases.
_valid_int = st.one_of(
    st.just("0"),
    st.integers(min_value=1, max_value=10**6).map(str),
    st.integers(min_value=-(10**6), max_value=-1).map(str),
)

_frac = st.integers(min_value=0, max_value=10**6).map(lambda n: "." + str(n))

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=400).map(str),
).map(lambda t: "".join(t))

_number = st.one_of(
    _valid_int,
    st.tuples(_valid_int, _frac).map(lambda t: "".join(t)),
    st.tuples(_valid_int, _exp).map(lambda t: "".join(t)),
    st.tuples(_valid_int, _frac, _exp).map(lambda t: "".join(t)),
    # extreme magnitudes / overflow
    st.sampled_from(
        [
            "1e309",
            "-1e309",
            "1e400",
            "1E+999",
            "1e-999",
            "1e308",
            "1.7976931348623157e308",
            "2.2250738585072014e-308",
            "0.0",
            "-0",
            "-0.0",
            "1e01",
            "1e00",
            "123456789012345678901234567890",
        ]
    ),
    # parser leniency: lone '-'
    st.just("-"),
    # near-valid malformed numbers
    st.sampled_from(
        [
            "+1",
            ".5",
            "1.",
            "01",
            "007",
            "0x1F",
            "1e",
            "1e+",
            "--1",
            "1..2",
            "00",
            "-",
            "1_000",
        ]
    ),
)

# Strings: valid content plus escapes, control bytes, NUL, surrogates.
_safe_char = st.characters(
    min_codepoint=0x20,
    max_codepoint=0x7E,
    blacklist_characters='"\\',
)

_control_char = st.sampled_from(
    ["\x00", "\x01", "\x07", "\x08", "\x0b", "\x0c", "\x1f", "\x7f"]
)

_escape = st.sampled_from(
    [
        "\\n",
        "\\t",
        "\\r",
        "\\b",
        "\\f",
        "\\/",
        "\\\\",
        "\\\"",
        "\\u0000",
        "\\u0001",
        "\\u001f",
        "\\u0041",
        "\\u00e9",
        "\\uD800",
        "\\uDC00",
        "\\uDFFF",
        "\\uD83D\\uDE00",
        "\\uFFFF",
        "\\uABCD",
        "\\uabcd",
    ]
)

_string_inner = st.one_of(
    st.text(alphabet=_safe_char, min_size=0, max_size=8),
    _control_char,
    _escape,
)

_string = st.one_of(
    st.lists(_string_inner, min_size=0, max_size=4).map("".join).map(lambda s: '"' + s + '"'),
    # unterminated string
    st.lists(_string_inner, min_size=0, max_size=4).map("".join).map(lambda s: '"' + s),
)

# ---------- recursive JSON values ----------

_json_value = st.deferred(lambda: _value)

_ws = st.sampled_from(["", " ", "  ", "\n", "\t", "\r\n", " \t "])

_obj_member = st.tuples(_key, st.just(":"), _json_value).map(lambda t: t[0] + t[1] + t[2])

_obj = st.one_of(
    st.just("{}"),
    st.tuples(
        st.just("{"),
        st.lists(_obj_member, min_size=1, max_size=4).map(lambda ms: ",".join(ms)),
        st.just("}"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # trailing comma variant
    st.tuples(
        st.just("{"),
        st.lists(_obj_member, min_size=1, max_size=3).map(lambda ms: ",".join(ms)),
        st.just(",}"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # duplicate keys
    st.tuples(
        st.just("{"),
        _key,
        st.just(":1,"),
        _key,
        st.just(":2}"),
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
)

_arr = st.one_of(
    st.just("[]"),
    st.tuples(
        st.just("["),
        st.lists(_json_value, min_size=1, max_size=4).map(lambda vs: ",".join(vs)),
        st.just("]"),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # trailing comma
    st.tuples(
        st.just("["),
        st.lists(_json_value, min_size=1, max_size=3).map(lambda vs: ",".join(vs)),
        st.just(",]"),
    ).map(lambda t: t[0] + t[1] + t[2]),
)

_value = st.one_of(
    _string,
    _number,
    _obj,
    _arr,
    st.sampled_from(["true", "false", "null"]),
)

# ---------- malformed / near-valid whole documents ----------

_malformed = st.sampled_from(
    [
        "[1,,2]",
        "[,]",
        "[,1]",
        "{,}",
        '{"a" 1}',
        '{"a":}',
        '{"a":1,,"b":2}',
        "{:1}",
        "{1:2}",
        "[1 2]",
        '{"a":1 "b":2}',
        "tru",
        "nul",
        "fals",
        "tru e",
        "1abc",
        "[]xyz",
        "1 garbage",
        "true false",
        "// comment",
        "/* c */ 1",
        "'x'",
        "{a:1}",
        "",
        " ",
        "\x00",
        "{}extra",
        "[1,2,3",
        '{"a":1',
        '"unterminated',
        "{'single':1}",
        "\xef\xbb\xbf{}",
    ]
)

# ---------- deep nesting ----------

_deep_obj = st.integers(min_value=1, max_value=60).map(
    lambda n: "{" + '{"k":' * n + "1" + "}" * n + "}"
)

_deep_arr = st.integers(min_value=1, max_value=200).map(
    lambda n: "[" * n + "]" * n
)

# ---------- top-level strategy ----------

_document = st.one_of(
    _value,
    _malformed,
    _deep_obj,
    _deep_arr,
)

strategy = _document