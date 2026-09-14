Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_bare_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

unquoted_key = st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)

# basic string content characters (no raw NUL, no unescaped quote/backslash/newline)
_basic_inner = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_characters='\\"\n\r\x00',
            blacklist_categories=(),
        ),
        min_size=0,
        max_size=20,
    ),
)

_escapes = st.sampled_from(
    [
        "\\\\",
        '\\"',
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
        "\\u0041",
        "\\u00e9",
        "\\u0000",
        "\\U0001F600",
        "\\U0010FFFF",
        "\\/",
    ]
)

_basic_piece = st.one_of(_basic_inner, _escapes)


def _join(parts):
    return "".join(parts)


basic_string = st.lists(_basic_piece, max_size=6).map(_join).map(
    lambda s: '"' + s + '"'
)

# literal string: no single quote, no newline; raw control chars allowed
literal_string = st.text(
    alphabet=st.characters(
        blacklist_characters="'\n\r\x00",
        blacklist_categories=(),
    ),
    max_size=20,
).map(lambda s: "'" + s + "'")

# multiline basic string
_ml_basic_piece = st.one_of(
    st.text(
        alphabet=st.characters(
            blacklist_characters='\\"\x00',
            blacklist_categories=(),
        ),
        max_size=20,
    ),
    _escapes,
    st.just("\n"),
    st.just("\r\n"),
    st.just('\\\n'),  # line-ending backslash
)
ml_basic_string = (
    st.lists(_ml_basic_piece, max_size=5)
    .map(_join)
    .map(lambda s: '"""' + s + '"""')
)

# multiline literal string: anything but NUL and the triple quote terminator
ml_literal_string = (
    st.text(
        alphabet=st.characters(
            blacklist_characters="'\x00",
            blacklist_categories=(),
        ),
        max_size=25,
    )
    .filter(lambda s: "'''" not in s)
    .map(lambda s: "'''" + s + "'''")
)

string_value = st.one_of(
    basic_string, literal_string, ml_basic_string, ml_literal_string
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
_dec_underscored = st.one_of(
    _dec_digits,
    st.lists(
        st.text(alphabet="0123456789", min_size=1, max_size=3),
        min_size=2,
        max_size=6,
    ).map(lambda parts: "_".join(parts)),
)
_sign = st.sampled_from(["", "+", "-"])

dec_int = st.tuples(_sign, _dec_underscored).map(lambda t: t[0] + t[1])
leading_zero_int = st.tuples(
    st.just("0"), st.text(alphabet="0123456789", min_size=1, max_size=6)
).map(lambda t: t[0] + t[1])

hex_int = st.tuples(
    st.just("0x"),
    st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=16),
).map(lambda t: t[0] + t[1])

oct_int = st.tuples(
    st.just("0o"),
    st.text(alphabet="01234567", min_size=1, max_size=16),
).map(lambda t: t[0] + t[1])

bin_int = st.tuples(
    st.just("0b"),
    st.text(alphabet="01", min_size=1, max_size=16),
).map(lambda t: t[0] + t[1])

integer_value = st.one_of(
    dec_int, leading_zero_int, hex_int, oct_int, bin_int
)

# floats
_frac = st.tuples(
    st.just("."),
    st.text(alphabet="0123456789", min_size=1, max_size=10),
).map(lambda t: t[0] + t[1])

_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_float_body = st.one_of(
    st.tuples(st.just("1"), _frac).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("1"), _exp).map(lambda t: t[0] + t[1]),
    st.tuples(st.just("1"), _frac, _exp).map(lambda t: "".join(t)),
    st.just("1."),          # no digit after dot
    st.just(".5"),          # no leading digit
    st.just("1e309"),       # overflow
    st.just("1e-9999"),
)

float_value = st.one_of(
    st.tuples(_sign, _float_body).map(lambda t: t[0] + t[1]),
    st.sampled_from(
        ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
    ),
)

# ---------------------------------------------------------------------------
# Dates / times
# ---------------------------------------------------------------------------

_date = st.tuples(
    st.text(alphabet="0123456789", min_size=4, max_size=4),
    st.just("-"),
    st.text(alphabet="0123456789", min_size=2, max_size=2),
    st.just("-"),
    st.text(alphabet="0123456789", min_size=2, max_size=2),
).map(lambda t: "".join(t))

_time = st.tuples(
    st.text(alphabet="0123456789", min_size=2, max_size=2),
    st.just(":"),
    st.text(alphabet="0123456789", min_size=2, max_size=2),
    st.just(":"),
    st.text(alphabet="0123456789", min_size=2, max_size=2),
).map(lambda t: "".join(t))

_secfrac = st.tuples(
    st.just("."),
    st.text(alphabet="0123456789", min_size=1, max_size=6),
).map(lambda t: t[0] + t[1])

_partial_time = st.one_of(
    _time,
    st.tuples(_time, _secfrac).map(lambda t: t[0] + t[1]),
)

_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
        st.just(":"),
        st.text(alphabet="0123456789", min_size=2, max_size=2),
    ).map(lambda t: "".join(t)),
)

_delim = st.sampled_from(["T", "t", " "])

offset_datetime = st.tuples(
    _date, _delim, _partial_time, _offset
).map(lambda t: "".join(t))

local_datetime = st.tuples(_date, _delim, _partial_time).map(
    lambda t: "".join(t)
)

local_date = _date
local_time = _partial_time

datetime_value = st.one_of(
    offset_datetime, local_datetime, local_date, local_time
)

bool_value = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

quoted_key = st.one_of(basic_string, literal_string)
simple_key = st.one_of(quoted_key, unquoted_key)


def _dotted(parts):
    return ".".join(parts)


dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(_dotted)

key = st.one_of(simple_key, dotted_key)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

scalar_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    datetime_value,
)

value = st.recursive(
    scalar_value,
    lambda children: st.one_of(
        st.lists(
            st.one_of(children, st.just("")),
            max_size=5,
        ).map(lambda items: "[" + ", ".join(items) + "]"),
        st.lists(
            st.tuples(simple_key, children).map(lambda t: t[0] + " = " + t[1]),
            max_size=4,
        ).map(lambda items: "{" + ", ".join(items) + "}"),
    ),
    max_leaves=30,
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

_key_value = st.tuples(key, value).map(lambda t: t[0] + " = " + t[1])

_standard_table = st.tuples(
    st.just("["), key, st.just("]")
).map(lambda t: "".join(t))

_array_table = st.tuples(
    st.just("[["), key, st.just("]]")
).map(lambda t: "".join(t))

_comment = st.one_of(
    st.just("#"),
    st.text(
        alphabet=st.characters(
            blacklist_characters="\n\r\x00",
            blacklist_categories=(),
        ),
        max_size=30,
    ).map(lambda s: "#" + s),
)

_line = st.one_of(_key_value, _standard_table, _array_table, _comment)

document = st.lists(_line, max_size=8).map(lambda lines: "\n".join(lines))

# ---------------------------------------------------------------------------
# Malformed / edge-case variants
# ---------------------------------------------------------------------------

_edge_scalars = st.sampled_from(
    [
        'a = "unterminated',
        "a = 'unterminated",
        'a = """unterminated',
        "a = '''unterminated",
        "a = [1, 2",
        "a = [1, 2,",
        "a = {b = 1",
        "a = {b = 1,}",
        "a = {b = 1\n}",
        "a = ",
        "a",
        "= 1",
        "a = = 1",
        "a = 1 2",
        "[t",
        "[t]]",
        "[[t]",
        "[[t]]]",
        "a..b = 1",
        "a. = 1",
        ".a = 1",
        'a = "\\q"',
        "a = 1\nb = 2\nb = 3",
        "[t]\n[t]",
        "a = 1979-02-30",
        "a = 007",
        "a = 1.",
        "a = .5",
        'a = "x\x01y"',
        "# comment with \x07 bell",
        "\x00",
        "",
        "\n\n\n",
        "# only a comment",
        "a = 1",
        "a = 1\n",
        "\ufeffa = 1",
        "café = 1",
        "a = true\nb = false",
        "a = 1_000",
        "a = 0xDEAD_BEEF",
        "a = 0o755",
        "a = 0b1010_1010",
        'a = "\\u0000"',
        "a = 1979-05-27T07:32:00Z",
        "a = 1979-05-27 07:32:00.999-07:00",
        "a = 07:32:00",
        "a = 1979-05-27",
        "a = {}",
        "a = []",
        "a = [[[]]]",
        "a = {b = {c = {}}}",
    ]
)

_edge_docs = st.lists(
    st.one_of(_line, _edge_scalars), max_size=6
).map(lambda lines: "\n".join(lines))

# deep nesting band 1500-2048
_depth = st.integers(min_value=1500, max_value=2048)


def _deep_array(n):
    return "[" * n + "]" * n


def _deep_inline(n):
    return "{a = " * n + "1" + "}" * n


_deep_doc = st.one_of(
    _depth.map(lambda n: "a = " + _deep_array(n)),
    st.integers(min_value=1, max_value=64).map(
        lambda n: "a = " + _deep_inline(n)
    ),
)

# ---------------------------------------------------------------------------
# Upweighted floating-point production (add_or_upweight_production)
# ---------------------------------------------------------------------------

_float_frac = st.tuples(
    st.just("."),
    st.text(alphabet="0123456789", min_size=1, max_size=10),
).map(lambda t: t[0] + t[1])

_float_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.text(alphabet="0123456789", min_size=1, max_size=4),
).map(lambda t: t[0] + t[1] + t[2])

_float_int_part = st.one_of(
    st.text(alphabet="0123456789", min_size=1, max_size=10),
    st.lists(
        st.text(alphabet="0123456789", min_size=1, max_size=3),
        min_size=2,
        max_size=5,
    ).map(lambda parts: "_".join(parts)),
)

_float_core = st.one_of(
    st.tuples(_float_int_part, _float_frac).map(lambda t: t[0] + t[1]),
    st.tuples(_float_int_part, _float_exp).map(lambda t: t[0] + t[1]),
    st.tuples(_float_int_part, _float_frac, _float_exp).map(
        lambda t: "".join(t)
    ),
    st.tuples(st.just("."), st.text(alphabet="0123456789", min_size=1, max_size=10)).map(
        lambda t: t[0] + t[1]
    ),
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("1e-9999"),
    st.just("6.626e-34"),
    st.just("224_617.445_991_228"),
    st.just("0.0"),
    st.just("-0.0"),
    st.just("1e0"),
    st.just("3.14159"),
)

_float_special = st.sampled_from(
    ["inf", "+inf", "-inf", "nan", "+nan", "-nan"]
)

_floating_point = st.one_of(
    st.tuples(_sign, _float_core).map(lambda t: t[0] + t[1]),
    _float_special,
)

_floating_point_kv = st.tuples(key, _floating_point).map(
    lambda t: t[0] + " = " + t[1]
)

_floating_point_doc = st.lists(
    st.one_of(_floating_point_kv, _line), max_size=8
).map(lambda lines: "\n".join(lines))

strategy = st.one_of(
    document,
    _edge_docs,
    _deep_doc,
    _floating_point_doc,
    _floating_point_kv,
    _floating_point,
    st.just(""),
)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 134,
    "reject": 216
  },
  "acceptance_rate": 0.383,
  "max_nesting_depth": 1999,
  "productions_accepted": [
    "BASIC_STRING",
    "BIN_INT",
    "COMMENT",
    "DEC_INT",
    "FLOAT",
    "INF",
    "LITERAL_STRING",
    "LOCAL_DATE",
    "LOCAL_DATE_TIME",
    "LOCAL_TIME",
    "ML_BASIC_STRING",
    "ML_LITERAL_STRING",
    "NAN",
    "NL",
    "OFFSET_DATE_TIME",
    "UNQUOTED_KEY",
    "array_",
    "array_table",
    "array_values",
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
    "bool_",
    "BOOLEAN",
    "HEX_INT",
    "OCT_INT"
  ],
  "cap_distance_mass": 0.119,
  "novelty": 53,
  "divergences": 54,
  "divergence_examples": [
    "b'\"\\\\\\\\\\\\u0000\\\\\"\\\\U0001F600\" = +1.'",
    "b'a = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['",
    "b'a = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **add_or_upweight_production** — bool_.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.