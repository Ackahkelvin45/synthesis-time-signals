Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------------------------------------------------------------------------
# Basic character / fragment strategies
# ---------------------------------------------------------------------------

# characters allowed in bare keys
_bare_key_chars = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)

_bare_key = st.text(_bare_key_chars, min_size=1, max_size=12)

# escape sequences for basic strings
_escapes = st.one_of(
    st.just("\\n"),
    st.just("\\t"),
    st.just("\\r"),
    st.just("\\b"),
    st.just("\\f"),
    st.just("\\\""),
    st.just("\\\\"),
    st.just("\\/"),
    st.just("\\u0000"),
    st.just("\\u00e9"),
    st.just("\\u4e2d"),
    st.just("\\U0001F600"),
    # invalid escape (near-valid-but-malformed)
    st.just("\\q"),
)

# printable-ish content for strings (avoid NUL raw byte)
_string_body_chars = st.sampled_from(
    "abcXYZ 0123!@#$%^&*()_+-=[]{};:,.<>/?|`~"
    "\t\r\x01\x02\x1f"
    "éüñ中文日本語"
)

_basic_string_body = st.one_of(
    st.text(_string_body_chars, min_size=0, max_size=10),
    st.lists(
        st.one_of(
            st.text(_string_body_chars, min_size=0, max_size=4),
            _escapes,
        ),
        min_size=0,
        max_size=6,
    ).map("".join),
)

_literal_string_body = st.text(
    st.sampled_from("abcXYZ 0123!@#$%^&*()_+-=[]{};:,.<>/?|`~éü中\t\r\x01\x02\x1f"),
    min_size=0,
    max_size=12,
)

basic_string = _basic_string_body.map(lambda s: '"' + s + '"')
literal_string = _literal_string_body.map(lambda s: "'" + s + "'")

ml_basic_string = _basic_string_body.map(lambda s: '"""' + s + '"""')
ml_literal_string = _literal_string_body.map(lambda s: "'''" + s + "'''")

_any_string = st.one_of(
    basic_string,
    literal_string,
    ml_basic_string,
    ml_literal_string,
)

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_dec_digits = st.text(st.sampled_from("0123456789"), min_size=1, max_size=20)

_dec_int = st.one_of(
    _dec_digits,
    st.tuples(st.sampled_from(["+", "-", ""]), _dec_digits).map(lambda t: t[0] + t[1]),
    st.just("0"),
    st.just("007"),  # leading zeros accepted
    st.just("+0"),
    st.just("-0"),
    st.text(st.sampled_from("0123456789_"), min_size=1, max_size=25).filter(
        lambda s: s[0] != "_" and s[-1] != "_"
    ),
    st.just("9999999999999999999999999999999999999999"),
)

_hex_digits = st.text(st.sampled_from("0123456789abcdefABCDEF"), min_size=1, max_size=20)
_hex_int = _hex_digits.map(lambda s: "0x" + s)

_oct_digits = st.text(st.sampled_from("01234567"), min_size=1, max_size=20)
_oct_int = _oct_digits.map(lambda s: "0o" + s)

_bin_digits = st.text(st.sampled_from("01"), min_size=1, max_size=20)
_bin_int = _bin_digits.map(lambda s: "0b" + s)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

_frac = _dec_digits.map(lambda s: "." + s)
_exp = st.tuples(
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    _dec_digits,
).map(lambda t: t[0] + t[1] + t[2])

_float = st.one_of(
    st.tuples(_dec_digits, _frac).map(lambda t: t[0] + t[1]),
    st.tuples(_dec_digits, _exp).map(lambda t: t[0] + t[1]),
    st.tuples(_dec_digits, _frac, _exp).map(lambda t: t[0] + t[1] + t[2]),
    st.just("1."),   # accepted
    st.just(".5"),   # accepted
    st.just("1e309"),
    st.just("-1e-999"),
    st.just("0.0"),
    st.just("3.141592653589793"),
)

_inf_nan = st.one_of(
    st.just("inf"),
    st.just("+inf"),
    st.just("-inf"),
    st.just("nan"),
    st.just("+nan"),
    st.just("-nan"),
)

_floating_point = st.one_of(_float, _inf_nan)

_boolean = st.sampled_from(["true", "false"])

# ---------------------------------------------------------------------------
# Date-times
# ---------------------------------------------------------------------------

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_day = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_hour = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_minute = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_second = st.integers(min_value=0, max_value=99).map(lambda n: "%02d" % n)
_secfrac = st.one_of(
    st.just(""),
    st.text(st.sampled_from("0123456789"), min_size=1, max_size=6).map(lambda s: "." + s),
)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "-".join(t))
_partial_time = st.tuples(_hour, _minute, _second, _secfrac).map(
    lambda t: t[0] + ":" + t[1] + ":" + t[2] + t[3]
)
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.just("z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hour, _minute
    ).map(lambda t: t[0] + t[1] + ":" + t[2]),
)

_offset_date_time = st.tuples(_full_date, _delim, _partial_time, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
_local_date_time = st.tuples(_full_date, _delim, _partial_time).map(
    lambda t: t[0] + t[1] + t[2]
)
_local_date = _full_date
_local_time = _partial_time

_date_time = st.one_of(
    _offset_date_time,
    _local_date_time,
    _local_date,
    _local_time,
    st.just("1979-02-30"),  # calendar-invalid, accepted
    st.just("1979-05-27 07:32:00Z"),
)

# ---------------------------------------------------------------------------
# Recursive values: arrays and inline tables
# ---------------------------------------------------------------------------

_key_simple = st.one_of(
    _bare_key,
    basic_string,
    literal_string,
    st.just('""'),  # empty quoted key
)

_key = st.one_of(
    _key_simple,
    st.lists(_key_simple, min_size=2, max_size=4).map(lambda ks: ".".join(ks)),
)

# leaf values (non-recursive)
_leaf_value = st.one_of(
    _any_string,
    _integer,
    _floating_point,
    _boolean,
    _date_time,
)

_ws = st.sampled_from(["", " ", "  ", "\t"])
_comment = st.text(
    st.sampled_from("abcXYZ 0123!@#$%^&*()_+-=[]{};:,.<>/?"),
    min_size=0,
    max_size=10,
).map(lambda s: "#" + s)

# comment-or-newline blocks for arrays
_comment_or_nl = st.lists(
    st.one_of(
        st.just("\n"),
        st.just("\r\n"),
        _comment.map(lambda c: c + "\n"),
    ),
    min_size=0,
    max_size=3,
).map("".join)

def _value_strategy(draw):
    return draw(_value)

_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        # array_
        st.tuples(
            _comment_or_nl,
            st.lists(
                st.tuples(
                    _ws,
                    children,
                    _ws,
                    st.one_of(st.just(""), _comment_or_nl),
                    st.just(","),
                ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
                min_size=0,
                max_size=5,
            ),
            st.one_of(st.just(""), children),
            _comment_or_nl,
        ).map(
            lambda t: "["
            + t[0]
            + "".join(t[1])
            + ("" if t[2] == "" else t[2])
            + t[3]
            + "]"
        ),
        # empty array
        st.just("[]"),
        # inline table
        st.tuples(
            st.lists(
                st.tuples(
                    _key,
                    _ws,
                    st.just("="),
                    _ws,
                    children,
                ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
                min_size=0,
                max_size=4,
            ),
            st.booleans(),
        ).map(
            lambda t: "{"
            + ", ".join(t[0])
            + ("," if t[1] and t[0] else "")
            + "}"
        ),
        # empty inline table
        st.just("{}"),
    ),
    max_leaves=40,
)

# ---------------------------------------------------------------------------
# Key-value / table lines
# ---------------------------------------------------------------------------

_key_value = st.tuples(
    _key,
    _ws,
    st.just("="),
    _ws,
    _value,
    st.one_of(st.just(""), _ws.map(lambda w: w + "")),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4] + t[5])

_standard_table = st.tuples(
    st.just("["),
    _ws,
    _key,
    _ws,
    st.just("]"),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

_array_table = st.tuples(
    st.just("[["),
    _ws,
    _key,
    _ws,
    st.just("]]"),
).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4])

_expression = st.one_of(
    _key_value,
    _standard_table,
    _array_table,
    _comment,
)

_line_ending = st.sampled_from(["\n", "\r\n", "\n", "\n"])

_document = st.lists(
    st.tuples(_expression, st.one_of(_comment, st.just("")), _line_ending).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    min_size=0,
    max_size=8,
).map("".join)

# ---------------------------------------------------------------------------
# Malformed / near-valid variants
# ---------------------------------------------------------------------------

_malformed = st.one_of(
    # missing closing bracket in a table header
    st.tuples(st.just("["), _key).map(lambda t: t[0] + t[1]),
    # doubled closing bracket
    st.tuples(st.just("["), _key, st.just("]]")).map(lambda t: t[0] + t[1] + t[2]),
    # unterminated basic string
    _basic_string_body.map(lambda s: 'a = "' + s),
    # unterminated literal string
    _literal_string_body.map(lambda s: "a = '" + s),
    # missing equals
    st.tuples(_key, _ws, _value).map(lambda t: t[0] + t[1] + t[2]),
    # value on next line
    st.tuples(_key, st.just(" =\n"), _value).map(lambda t: t[0] + t[1] + t[2]),
    # stray token
    st.sampled_from(["a = = 1", "a = ,", "= 1", "a = 1 b = 2", "[[t]", "[t]]", "a = {b = 1, c}"]),
    # newline inside inline table
    st.tuples(_key, _value).map(lambda t: "a = {" + t[0] + " = " + t[1] + "\n}"),
    # duplicate key
    st.tuples(_key, _value).map(lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]),
    # invalid escape
    st.just('a = "\\q"'),
    # non-ASCII bare key
    st.just("é = 1"),
    # empty document with just whitespace
    st.just(""),
    st.just("   \n\t\n"),
)

# ---------------------------------------------------------------------------
# Deep nesting band (1500-2048 levels)
# ---------------------------------------------------------------------------

_deep_array = st.integers(min_value=1500, max_value=2048).map(
    lambda n: "a = " + "[" * n + "]" * n
)

_deep_inline_table = st.integers(min_value=200, max_value=600).map(
    lambda n: "a = " + "{b = " * n + "1" + "}" * n
)

# ---------------------------------------------------------------------------
# Final strategy
# ---------------------------------------------------------------------------

_document_variants = st.one_of(
    _document,
    _malformed,
    _deep_array,
    _deep_inline_table,
    # documents with no trailing newline
    _key_value,
    # comment-only document
    _comment,
)

# Improve the fuzzer: bias toward emitting multi-line documents that mix
# several well-formed expressions with occasional malformed fragments, since
# a C parser is most likely to fail on interactions between valid constructs
# and near-valid edge cases rather than on single isolated expressions.
# Use a recursive structure so nested mixed documents are also generated,
# and interleave line endings to exercise CRLF handling.
_mixed_document = st.recursive(
    st.one_of(_expression, _malformed),
    lambda children: st.one_of(
        st.tuples(children, _line_ending, children).map(lambda t: t[0] + t[1] + t[2]),
        st.tuples(children, _comment, _line_ending, children).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        ),
        st.lists(
            st.one_of(_expression, _malformed, children),
            min_size=1,
            max_size=6,
        ).map(lambda parts: "".join(p + "\n" for p in parts)),
    ),
    max_leaves=12,
)

strategy = st.one_of(
    _document_variants,
    _mixed_document,
)
```

No run feedback is provided.

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.