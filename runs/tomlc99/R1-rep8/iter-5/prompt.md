Here is the current Hypothesis strategy:

```python
from hypothesis import strategies as st
import json

# ---------- helpers ----------

_BARE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
_CTRL = [chr(i) for i in range(0x01, 0x20) if i not in (0x0a, 0x0d)] + ["\t", "\r"]
_NONASCII = [chr(c) for c in (0x00e9, 0x4e2d, 0x1f600, 0x03b1, 0x0416, 0x2603)]


def _join(*parts):
    return "".join(parts)


# ---------- keys ----------

def _bare_key():
    return st.text(alphabet=_BARE, min_size=1, max_size=12)


_esc_short = st.sampled_from(["\\\"", "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"])


def _unicode_escape():
    return st.sampled_from(["\\u0041", "\\u00e9", "\\u0000", "\\uFFFF", "\\U0001F600",
                            "\\U00000000", "\\u4e2d"])


def _basic_string_char():
    return st.one_of(
        st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`'", min_size=1, max_size=4),
        _esc_short,
        _unicode_escape(),
        st.sampled_from(_CTRL),
        st.sampled_from(_NONASCII),
    )


def _basic_string():
    return st.lists(_basic_string_char(), max_size=4).map(lambda xs: '"' + "".join(xs) + '"')


def _literal_string():
    return st.lists(
        st.one_of(
            st.text(alphabet="abcXYZ 019!@#$%^&*()[]{}.,;:<>?|~`\"\\", min_size=0, max_size=4),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map(lambda xs: "'" + "".join(xs) + "'")


def _ml_basic_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'", min_size=0, max_size=6),
            _esc_short,
            _unicode_escape(),
            st.sampled_from(["\\\n", "\\\r\n"]),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: '"""' + b + '"""')


def _ml_literal_string():
    body = st.lists(
        st.one_of(
            st.text(alphabet="abc 0123\n\t\"'\\", min_size=0, max_size=6),
            st.sampled_from(_NONASCII),
        ),
        max_size=4,
    ).map("".join)
    return body.map(lambda b: "'''" + b + "'''")


def _simple_key():
    return st.one_of(
        _bare_key(),
        _basic_string(),
        _literal_string(),
        st.just('""'),
    )


def _dotted_key():
    return st.lists(_simple_key(), min_size=2, max_size=3).map(lambda ps: ".".join(ps))


def _key():
    return st.one_of(_simple_key(), _dotted_key())


# ---------- scalars ----------

def _dec_int():
    return st.one_of(
        st.integers(min_value=-(10 ** 30), max_value=10 ** 30).map(str),
        st.sampled_from(["0", "-0", "+0", "007", "00", "1_000", "1_2_3",
                         "99999999999999999999999999999999999999",
                         "-99999999999999999999999999999999999999"]),
    )


def _hex_int():
    return st.one_of(
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=10).map(lambda s: "0x" + s),
        st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFFFFFFFFFFFFFFFFFFFF"]),
    )


def _oct_int():
    return st.one_of(
        st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
        st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
    )


def _bin_int():
    return st.one_of(
        st.text(alphabet="01", min_size=1, max_size=12).map(lambda s: "0b" + s),
        st.sampled_from(["0b0", "0b1", "0b1_0_1", "0b" + "1" * 64]),
    )


def _integer():
    return st.one_of(_dec_int(), _hex_int(), _oct_int(), _bin_int())


def _float():
    return st.one_of(
        st.sampled_from(["1.0", "-1.5", "+3.25", "1.", ".5", "0.0", "-0.0",
                         "1e10", "1E-10", "1.5e+300", "1e309", "-1e309",
                         "6.626e-34", "1_000.0", "1.0_0", "3.14e1_0"]),
        st.tuples(
            st.integers(min_value=-10 ** 6, max_value=10 ** 6).map(str),
            st.sampled_from([".0", ".5", "."]),
            st.one_of(st.just(""), st.sampled_from(["e1", "E-2", "e+10", "e309"])),
        ).map(lambda t: t[0] + t[1] + t[2]),
    )


def _inf_nan():
    return st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])


def _bool():
    return st.sampled_from(["true", "false"])


def _date_time():
    return st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27 07:32:00Z",
        "1979-05-27t07:32:00z",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27T07:32:00",
        "1979-05-27T07:32:00.5",
        "1979-05-27",
        "1979-02-30",
        "0000-00-00",
        "9999-99-99",
        "07:32:00",
        "07:32:00.999",
        "23:59:59.999999999",
    ])


def _string():
    return st.one_of(_basic_string(), _literal_string(), _ml_basic_string(), _ml_literal_string())


# ---------- recursive values ----------

def _scalar():
    return st.one_of(
        _string(),
        _integer(),
        _float(),
        _inf_nan(),
        _bool(),
        _date_time(),
    )


def _array_body(depth):
    inner = _value(depth)
    elems = st.lists(
        st.tuples(
            inner,
            st.one_of(st.just(""), st.just(" "), st.just("\n"), st.just(" # c\n")),
        ).map(lambda t: t[0] + t[1]),
        max_size=4,
    )
    return elems


def _array(depth):
    def build(elems):
        sep = st.sampled_from([",", ", ", ",\n", " , "])
        return sep, elems

    return st.builds(
        lambda elems: _render_array(elems),
        _array_body(depth),
    )


def _render_array(elems):
    if not elems:
        return st.just("[]").example() if False else "[]"
    return "[" + ", ".join(elems) + "]"


def _inline_table(depth):
    inner = _value(depth)

    def kv():
        return st.tuples(_key(), inner).map(lambda t: t[0] + " = " + t[1])

    def render(pairs):
        if not pairs:
            return "{}"
        return "{" + ", ".join(pairs) + "}"

    return st.lists(kv(), max_size=3).map(render)


def _value(depth):
    if depth <= 0:
        return _scalar()
    return st.one_of(
        _scalar(),
        _array(depth - 1),
        _inline_table(depth - 1),
    )


def _deep_array(n):
    return st.just("[" * n + "]" * n)


def _deep_inline(n):
    # {a={a={a=...}}} nested inline tables
    return st.just("{a=" * n + "1" + "}" * n)


# ---------- documents ----------

def _comment():
    return st.lists(
        st.one_of(
            st.text(alphabet="abc 0123!@#$%^&*()[]{}.,;:<>?|~`'\"\\", min_size=0, max_size=8),
            st.sampled_from(_CTRL),
            st.sampled_from(_NONASCII),
        ),
        max_size=3,
    ).map(lambda xs: "#" + "".join(xs))


def _keyval_line(depth):
    return st.tuples(_key(), _value(depth), st.one_of(st.just(""), _comment())).map(
        lambda t: t[0] + " = " + t[1] + (" " + t[2] if t[2] else "")
    )


def _table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[" + t[0] + "]" + (" " + t[1] if t[1] else "")
    )


def _array_table_line():
    return st.tuples(_key(), st.one_of(st.just(""), _comment())).map(
        lambda t: "[[" + t[0] + "]]" + (" " + t[1] if t[1] else "")
    )


def _line(depth):
    return st.one_of(
        _keyval_line(depth),
        _table_line(),
        _array_table_line(),
        _comment(),
        st.just(""),
    )


def _document():
    return st.lists(_line(2), max_size=6).map(lambda ls: "\n".join(ls))


# ---------- malformed near-valid ----------

def _malformed():
    base = st.one_of(
        _keyval_line(1),
        _table_line(),
        _array_table_line(),
    )

    def drop_last(s):
        return s[:-1] if s else s

    def dup_last(s):
        return s + (s[-1] if s else "x")

    return st.one_of(
        base.map(drop_last),
        base.map(dup_last),
        st.tuples(_key(), _basic_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), _literal_string()).map(lambda t: t[0] + " = " + t[1][:-1]),
        st.tuples(_key(), st.just("[1, 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("1 2")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("true false")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " = " + t[1] + " stray"),
        st.tuples(_key(), st.just('"\\q"')).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), st.just("{a = 1\nb = 2}")).map(lambda t: t[0] + " = " + t[1]),
        st.tuples(_key(), _value(1)).map(lambda t: t[0] + " =\n" + t[1]),
        st.tuples(_key(), st.just("1")).map(lambda t: t[0] + " = " + t[1]).map(
            lambda s: s + "\n" + s
        ),
        st.just("[]"),
        st.just("=1"),
        st.just("[["),
        st.just("]]"),
        st.just("{"),
        st.just("}"),
        st.just("."),
        st.just(","),
        st.just("[a"),
        st.just("[[a]"),
        st.just("a ="),
        st.just("a = ]"),
    )


# ---------- top-level strategy ----------

def _deep_document():
    n = st.integers(min_value=1500, max_value=2048)
    return st.one_of(
        n.map(lambda k: "a = " + "[" * k + "]" * k),
        n.map(lambda k: "a = " + "[" * k + "1" + "]" * k),
        st.integers(min_value=1, max_value=40).map(lambda k: "a = " + "{b=" * k + "1" + "}" * k),
        st.integers(min_value=1, max_value=40).map(
            lambda k: "a = " + "[" * k + "{b=1}" + "]" * k
        ),
    )


def _duplicate_doc():
    return st.tuples(_key(), _value(1)).map(
        lambda t: t[0] + " = " + t[1] + "\n" + t[0] + " = " + t[1]
    )


def _scalar_doc():
    # Documents that exercise the scalar productions the parser currently
    # never reaches (floats, bools, datetimes, hex/oct/bin ints, ML strings).
    return st.tuples(_key(), _scalar()).map(lambda t: t[0] + " = " + t[1])


def _gap_doc():
    # Target the specific productions the parser has not yet accepted:
    # BOOLEAN, NAN, HEX_INT (and keep coverage for the others).
    inf = st.sampled_from(["inf", "+inf", "-inf"])
    nan = st.sampled_from(["nan", "+nan", "-nan"])
    oct_int = st.one_of(
        st.text(alphabet="01234567", min_size=1, max_size=8).map(lambda s: "0o" + s),
        st.sampled_from(["0o0", "0o777", "0o1_2_3"]),
    )
    hex_int = st.one_of(
        st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=10).map(
            lambda s: "0x" + s
        ),
        st.sampled_from(["0x0", "0xDEADBEEF", "0xdead_beef", "0xFF"]),
    )
    boolean = st.sampled_from(["true", "false"])
    offset_dt = st.sampled_from([
        "1979-05-27T07:32:00Z",
        "1979-05-27T07:32:00+07:00",
        "1979-05-27T07:32:00-07:00",
        "1979-05-27T00:32:00.999999-07:00",
        "1979-05-27 07:32:00Z",
    ])
    local_dt = st.sampled_from([
        "1979-05-27T07:32:00",
        "1979-05-27T07:32:00.5",
        "1979-05-27T00:32:00.999999",
        "1979-05-27 07:32:00",
    ])
    local_date = st.sampled_from([
        "1979-05-27", "0000-00-00", "9999-99-99", "2024-02-29", "2023-02-29",
    ])
    val = st.one_of(inf, nan, oct_int, hex_int, boolean,
                    offset_dt, local_dt, local_date)
    return st.tuples(_key(), val).map(lambda t: t[0] + " = " + t[1])


def _bool_nan_doc():
    # Focused documents for the three scalar keyword productions that the
    # parser has not yet accepted: BOOLEAN, NAN, HEX_INT.
    kw = st.sampled_from(["true", "false", "nan", "+nan", "-nan",
                          "0x0", "0xFF", "0xDEADBEEF"])
    return st.tuples(_key(), kw).map(lambda t: t[0] + " = " + t[1])


def _full_doc():
    return st.one_of(
        _document(),
        _malformed(),
        _deep_document(),
        _duplicate_doc(),
        _scalar_doc(),
        _gap_doc(),
        _bool_nan_doc(),
        st.just(""),
        st.just("\n"),
        st.just("\r\n"),
        st.just("# only comment"),
        st.just("# only comment\n"),
        st.just("[t]"),
        st.just("[[a]]"),
        st.just("[[a]]\n[[a]]"),
        st.just('"" = 1'),
        st.just("a = {b = 1,}"),
        st.just("a = [1, 2,]"),
        st.just("a = [\n  1,\n  2, # c\n]"),
        st.just("a = 1\r\nb = 2\r\n"),
        st.just("a = 1"),
        st.just("\t[a]\n\tb = 1"),
    )


def _no_nul(s):
    return s.replace("\x00", "")


strategy = _full_doc().map(_no_nul)
```

Here is the summary of its last run against the parser (no coverage data is available):
{
  "outcomes": {
    "valid": 141,
    "reject": 209
  },
  "acceptance_rate": 0.403,
  "max_nesting_depth": 1999,
  "productions_accepted": [
    "BASIC_STRING",
    "BIN_INT",
    "BOOLEAN",
    "COMMENT",
    "DEC_INT",
    "HEX_INT",
    "INF",
    "LITERAL_STRING",
    "LOCAL_DATE",
    "ML_BASIC_STRING",
    "NAN",
    "NL",
    "OCT_INT",
    "UNQUOTED_KEY",
    "array_",
    "array_table",
    "array_values",
    "bool_",
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
    "ML_LITERAL_STRING",
    "FLOAT",
    "OFFSET_DATE_TIME",
    "LOCAL_DATE_TIME",
    "LOCAL_TIME"
  ],
  "cap_distance_mass": 0.05,
  "novelty": 63,
  "divergences": 43,
  "divergence_examples": [
    "b'a = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['",
    "b'a = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['",
    "b'a = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[['"
  ],
  "unique_crash_signatures": [],
  "reject_reasons_sample": []
}

Make EXACTLY ONE change to the strategy: **improve_strategy** — make it a better fuzzer for this grammar, using the run feedback above where it is given.
Change nothing else. Keep it a valid Hypothesis strategy producing `str`. Return the full revised module as one ```python code block.