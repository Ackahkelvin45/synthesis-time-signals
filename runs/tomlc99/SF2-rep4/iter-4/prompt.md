Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- basic character / token helpers ----------

_bare_key_chars = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
)

def _bare_key_text(min_size=1, max_size=12):
    return st.text(_bare_key_chars, min_size=min_size, max_size=max_size)

# string body characters (avoid raw NUL; allow control bytes, tabs, non-ASCII)
_body_chars = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF, blacklist_characters="\x00"),
    st.sampled_from(list(" \t\"'\\#[]{}=,.\n\r")),
)

_escapes = st.one_of(
    st.sampled_from(['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]),
    st.integers(min_value=0, max_value=0xFFFF).map(lambda n: "\\u%04x" % n),
    st.integers(min_value=0, max_value=0x10FFFF).map(lambda n: "\\U%08x" % n),
)

def _basic_body(min_size=0, max_size=8):
    return st.lists(
        st.one_of(
            st.characters(min_codepoint=1, max_codepoint=0x10FFFF,
                          blacklist_characters='\x00"\\\n'),
            _escapes,
        ),
        min_size=min_size, max_size=max_size,
    ).map("".join)

def _literal_body(min_size=0, max_size=8):
    return st.lists(
        st.characters(min_codepoint=1, max_codepoint=0x10FFFF,
                      blacklist_characters="\x00'\n"),
        min_size=min_size, max_size=max_size,
    ).map("".join)

# ---------- strings (all four quoting forms) ----------

basic_string = _basic_body().map(lambda b: '"' + b + '"')
literal_string = _literal_body().map(lambda b: "'" + b + "'")

def _ml_basic_body():
    return st.lists(
        st.one_of(
            st.characters(min_codepoint=1, max_codepoint=0x10FFFF,
                          blacklist_characters='\x00"\\'),
            _escapes,
            st.just("\n"),
        ),
        min_size=0, max_size=8,
    ).map("".join)

def _ml_literal_body():
    return st.lists(
        st.one_of(
            st.characters(min_codepoint=1, max_codepoint=0x10FFFF,
                          blacklist_characters="\x00'"),
            st.just("\n"),
        ),
        min_size=0, max_size=8,
    ).map("".join)

ml_basic_string = _ml_basic_body().map(lambda b: '"""' + b + '"""')
ml_literal_string = _ml_literal_body().map(lambda b: "'''" + b + "'''")

any_string = st.one_of(basic_string, literal_string, ml_basic_string, ml_literal_string)

# ---------- numbers ----------

def _digits_with_underscores(digit_strat, min_len=1, max_len=10):
    def build(parts):
        if not parts:
            return "0"
        out = parts[0]
        for p in parts[1:]:
            out += "_" + p if p else ""
        return out
    return st.lists(
        st.text(digit_strat, min_size=1, max_size=4),
        min_size=min_len, max_size=max_len,
    ).map(build)

_dec_digits = st.sampled_from(list("0123456789"))
_hex_digits = st.sampled_from(list("0123456789abcdefABCDEF"))
_oct_digits = st.sampled_from(list("01234567"))
_bin_digits = st.sampled_from(list("01"))

def _sign():
    return st.one_of(st.just(""), st.just("+"), st.just("-"))

dec_int = st.tuples(
    _sign(),
    st.one_of(
        st.text(_dec_digits, min_size=1, max_size=1),
        _digits_with_underscores(_dec_digits, 1, 8),
        st.text(_dec_digits, min_size=1, max_size=40),
    ),
).map(lambda t: t[0] + t[1])

hex_int = _digits_with_underscores(_hex_digits, 1, 8).map(lambda d: "0x" + d)
oct_int = _digits_with_underscores(_oct_digits, 1, 8).map(lambda d: "0o" + d)
bin_int = _digits_with_underscores(_bin_digits, 1, 8).map(lambda d: "0b" + d)

any_int = st.one_of(dec_int, hex_int, oct_int, bin_int)

def _exp():
    return st.tuples(
        st.sampled_from(["e", "E"]),
        st.one_of(st.just(""), st.just("+"), st.just("-")),
        st.text(_dec_digits, min_size=1, max_size=4),
    ).map(lambda t: t[0] + t[1] + t[2])

def _frac():
    return st.text(_dec_digits, min_size=1, max_size=6).map(lambda d: "." + d)

_float_base = st.one_of(
    st.tuples(dec_int, _exp()).map(lambda t: t[0] + t[1]),
    st.tuples(dec_int, _frac()).map(lambda t: t[0] + t[1]),
    st.tuples(dec_int, _frac(), _exp()).map(lambda t: t[0] + t[1] + t[2]),
    # lenient forms the parser accepts
    _frac(),
    dec_int.map(lambda d: d + "."),
)

float_lit = st.one_of(
    _float_base,
    st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"]),
)

# ---------- booleans ----------

bool_lit = st.sampled_from(["true", "false"])

# ---------- date-times ----------

def _two(min_v=0, max_v=99):
    return st.integers(min_value=min_v, max_value=max_v).map(lambda n: "%02d" % n)

_year = st.integers(min_value=0, max_value=9999).map(lambda n: "%04d" % n)
_month = st.one_of(_two(0, 99), st.sampled_from(["01", "02", "12"]))
_day = st.one_of(_two(0, 99), st.sampled_from(["01", "28", "30", "31"]))
_hour = _two(0, 99)
_minute = _two(0, 99)
_second = _two(0, 99)
_secfrac = st.text(_dec_digits, min_size=1, max_size=9).map(lambda d: "." + d)

_full_date = st.tuples(_year, _month, _day).map(lambda t: "%s-%s-%s" % t)
_partial_time = st.tuples(_hour, _minute, _second).map(lambda t: "%s:%s:%s" % t)
_partial_time_frac = st.tuples(_partial_time, _secfrac).map(lambda t: t[0] + t[1])
_time_any = st.one_of(_partial_time, _partial_time_frac)

_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(["+", "-"]), _hour, _minute).map(
        lambda t: t[0] + t[1] + ":" + t[2]
    ),
)

offset_date_time = st.tuples(_full_date, _delim, _time_any, _offset).map(
    lambda t: t[0] + t[1] + t[2] + t[3]
)
local_date_time = st.tuples(_full_date, _delim, _time_any).map(
    lambda t: t[0] + t[1] + t[2]
)
local_date = _full_date
local_time = _time_any

any_datetime = st.one_of(offset_date_time, local_date_time, local_date, local_time)

# ---------- keys ----------

def _simple_key():
    return st.one_of(
        _bare_key_text(1, 12),
        basic_string,
        literal_string,
        st.just('""'),  # empty quoted key
    )

def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=4).map(lambda ks: ".".join(ks))

any_key = st.one_of(_simple_key(), _dotted_key())

# ---------- recursive values ----------

_key = any_key

def _make_value():
    return st.one_of(
        any_string,
        any_int,
        float_lit,
        bool_lit,
        any_datetime,
    )

_leaf_value = _make_value()

def _array_body(inner):
    # inner is a strategy producing a value string
    return st.lists(inner, min_size=0, max_size=4).map(
        lambda xs: "[" + ", ".join(xs) + "]"
    )

def _inline_table_body(inner):
    def build(pairs):
        if not pairs:
            return "{}"
        parts = [k + " = " + v for (k, v) in pairs]
        return "{" + ", ".join(parts) + "}"
    return st.lists(
        st.tuples(_key, inner), min_size=0, max_size=3
    ).map(build)

_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        _array_body(children),
        _inline_table_body(children),
    ),
    max_leaves=20,
)

# ---------- key/value lines, tables ----------

def _kv_line():
    return st.tuples(any_key, _value).map(lambda t: t[0] + " = " + t[1])

def _comment():
    body = st.text(
        st.characters(min_codepoint=1, max_codepoint=0x10FFFF,
                      blacklist_characters="\x00\n"),
        min_size=0, max_size=20,
    )
    return body.map(lambda b: "#" + b)

_standard_table = any_key.map(lambda k: "[" + k + "]")
_array_table = any_key.map(lambda k: "[[" + k + "]]")

def _line():
    return st.one_of(
        _kv_line(),
        _standard_table,
        _array_table,
        _comment(),
        st.just(""),
    )

_document = st.lists(_line(), min_size=0, max_size=12).map(
    lambda lines: "\n".join(lines)
)

# ---------- near-valid-but-malformed inputs ----------

def _malformed():
    return st.one_of(
        # unterminated strings
        _basic_body().map(lambda b: 'a = "' + b),
        _literal_body().map(lambda b: "a = '" + b),
        # missing / doubled delimiters
        st.just("a = [1, 2"),
        st.just("a = {b = 1"),
        st.just("a = [[1, 2]]]"),
        st.just("[[t]"),
        st.just("[t]]"),
        st.just("a = 1\nb ="),
        st.just("a = "),
        st.just("= 1"),
        st.just("a = {b = 1,, c = 2}"),
        st.just("a = [1,,2]"),
        # stray token
        st.just("a = 1 @"),
        st.just("a 1"),
        st.just("[]"),
        st.just("[[]]"),
        # invalid escape
        st.just('a = "\\q"'),
        # non-ASCII bare key (rejected)
        st.just("é = 1"),
        st.just("key\u00e9 = 1"),
        # newline inside inline table (rejected)
        st.just("a = {b = 1,\nc = 2}"),
        # duplicate keys (rejected)
        st.just("a = 1\na = 2"),
        st.just("[t]\n[t]"),
        # value on next line
        st.just("a =\n1"),
    )

# ---------- deep nesting in the interesting band ----------

def _deep_array():
    return st.integers(min_value=1500, max_value=2048).map(
        lambda n: "a = " + "[" * n + "]" * n
    )

def _deep_inline_table():
    return st.integers(min_value=1500, max_value=2048).map(
        lambda n: "a = " + "{b = " * n + "1" + "}" * n
    )

# ---------- assemble ----------

strategy = st.one_of(
    _document,
    st.tuples(_document, _malformed()).map(lambda t: t[0] + "\n" + t[1]),
    _malformed(),
    _deep_array(),
    _deep_inline_table(),
    # edge-case explicit documents
    st.just(""),
    st.just("\n"),
    st.just("# only a comment"),
    st.just("a = 007"),
    st.just("a = 1."),
    st.just("a = .5"),
    st.just("a = {b = 1,}"),
    st.just("a = 1979-02-30"),
    st.just('a = "x\x01y"'),
    st.just("a = 1e309"),
    st.just("a = 1_000"),
    st.just("a = 0xDEAD_BEEF"),
    st.just("a = 0o755"),
    st.just("a = 0b1010_1010"),
    st.just("a = inf"),
    st.just("a = -nan"),
    st.just("a = 1979-05-27 07:32:00Z"),
    st.just("[t]\n[[a]]\n[[a]]"),
    st.just('"" = 1'),
    st.just("a = []"),
    st.just("a = {}"),
    st.just("a = [1, [2, [3, []]]]"),
    st.just("a = {b = {c = {}}}"),
    st.just("a = 1\r\nb = 2"),
    st.just("\ta = 1"),
)
```

Here is the code coverage its last run achieved on the parser (measured with instrumentation):
{
  "branch_coverage_pct": 63.71,
  "region_coverage_pct": 66.5
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.