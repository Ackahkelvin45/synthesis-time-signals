```python
from hypothesis import strategies as st
import json

# ---------- basic atoms ----------

# No raw NUL anywhere. Control chars allowed elsewhere (parser accepts them in strings/comments).
_ascii_safe = st.characters(min_codepoint=1, max_codepoint=127)
_unicode_safe = st.characters(min_codepoint=1, max_codepoint=0x10FFFF)

_bare_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

unquoted_key = st.text(alphabet=_bare_key_chars, min_size=1, max_size=12)
long_unquoted_key = st.text(alphabet=_bare_key_chars, min_size=1, max_size=10000)

# Escapes for basic strings
_hex4 = st.text(alphabet="0123456789abcdefABCDEF", min_size=4, max_size=4)
_hex8 = st.text(alphabet="0123456789abcdefABCDEF", min_size=8, max_size=8)
escapes = st.one_of(
    st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
    _hex4.map(lambda h: "\\u" + h),
    _hex8.map(lambda h: "\\U" + h),
    st.just("\\u0000"),  # fine inside string
)

_basic_inner_char = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c not in '"\\\n'),
    escapes,
)

basic_string_inner = st.lists(_basic_inner_char, max_size=20).map("".join)

basic_string = basic_string_inner.map(lambda s: '"' + s + '"')

_literal_inner_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(
    lambda c: c not in "'\n"
)
literal_string = st.lists(_literal_inner_char, max_size=20).map(
    lambda cs: "'" + "".join(cs) + "'"
)

# multiline basic: content may include newlines but not the closing triple quote
_ml_basic_char = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "\\"),
    escapes,
    st.just('"'),
    st.just("\n"),
    st.just("\r\n"),
)
ml_basic_string = st.lists(_ml_basic_char, max_size=15).map(
    lambda cs: '"""' + "".join(cs) + '"""'
)

_ml_literal_char = st.one_of(
    st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "'"),
    st.just("'"),
    st.just("\n"),
    st.just("\r\n"),
)
ml_literal_string = st.lists(_ml_literal_char, max_size=15).map(
    lambda cs: "'''" + "".join(cs) + "'''"
)

any_string = st.one_of(
    basic_string, literal_string, ml_basic_string, ml_literal_string
)

# ---------- numbers ----------

_digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
_hexd = st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=20)
_octd = st.text(alphabet="01234567", min_size=1, max_size=20)
_bind = st.text(alphabet="01", min_size=1, max_size=20)

def _sign(s):
    return s

dec_int = st.one_of(
    _digits,
    st.tuples(st.sampled_from(["+", "-"]), _digits).map(lambda t: t[0] + t[1]),
    st.just("0"),
    st.just("007"),
    st.just("1_000"),
    st.just("9223372036854775808"),
    st.just("9999999999999999999999999999999999999999"),
    st.just("-9223372036854775809"),
)

hex_int = _hexd.map(lambda h: "0x" + h)
oct_int = _octd.map(lambda o: "0o" + o)
bin_int = _bind.map(lambda b: "0b" + b)

integer = st.one_of(dec_int, hex_int, oct_int, bin_int)

_frac = _digits
_exp = st.tuples(st.sampled_from(["e", "E"]), st.sampled_from(["", "+", "-"]), _digits).map(
    lambda t: t[0] + t[1] + t[2]
)

float_ = st.one_of(
    st.tuples(_digits, st.just("."), _digits).map(lambda t: t[0] + t[1] + t[2]),
    st.tuples(_digits, st.just("."), _digits, _exp).map(
        lambda t: t[0] + t[1] + t[2] + t[3]
    ),
    st.tuples(st.sampled_from(["", "+", "-"]), _digits, _exp).map(
        lambda t: t[0] + t[1] + t[2]
    ),
    st.just("1."),
    st.just(".5"),
    st.just("1e309"),
    st.just("-1e309"),
    st.just("1e-999"),
    st.just("3.141592653589793"),
)

inf_nan = st.one_of(
    st.just("inf"),
    st.just("+inf"),
    st.just("-inf"),
    st.just("nan"),
    st.just("+nan"),
    st.just("-nan"),
)

floating_point = st.one_of(float_, inf_nan)

boolean = st.sampled_from(["true", "false"])

# ---------- date-times ----------

_year = st.text(alphabet="0123456789", min_size=4, max_size=4)
_month = st.text(alphabet="0123456789", min_size=2, max_size=2)
_day = st.text(alphabet="0123456789", min_size=2, max_size=2)
_hh = st.text(alphabet="0123456789", min_size=2, max_size=2)
_mm = st.text(alphabet="0123456789", min_size=2, max_size=2)
_ss = st.text(alphabet="0123456789", min_size=2, max_size=2)
_secfrac = st.tuples(st.just("."), _digits).map(lambda t: t[0] + t[1])

full_date = st.tuples(_year, _month, _day).map(lambda t: t[0] + "-" + t[1] + "-" + t[2])
partial_time = st.tuples(_hh, _mm, _ss).map(lambda t: t[0] + ":" + t[1] + ":" + t[2])
partial_time_frac = st.tuples(partial_time, _secfrac).map(lambda t: t[0] + t[1])
_delim = st.sampled_from(["T", "t", " "])
_offset = st.one_of(
    st.just("Z"),
    st.tuples(
        st.sampled_from(["+", "-"]), _hh, st.just(":"), _mm
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
)

offset_datetime = st.tuples(
    full_date, _delim, partial_time_frac, _offset
).map(lambda t: t[0] + t[1] + t[2] + t[3])

local_datetime = st.tuples(full_date, _delim, partial_time_frac).map(
    lambda t: t[0] + t[1] + t[2]
)

local_date = full_date
local_time = partial_time_frac

date_time = st.one_of(offset_datetime, local_datetime, local_date, local_time)

# invalid-calendar date accepted by parser
invalid_date = st.just("1979-02-30")

# ---------- recursive values ----------

# We build values recursively: arrays and inline tables recurse.
key_simple = st.one_of(unquoted_key, basic_string, literal_string)

dotted_key = st.lists(key_simple, min_size=2, max_size=4).map(lambda ks: ".".join(ks))

key = st.one_of(key_simple, dotted_key)

def _join_inline(pairs):
    return "{" + ", ".join(pairs) + "}"

def _join_array(items):
    return "[" + ", ".join(items) + "]"

# scalar values (non-recursive)
scalar_value = st.one_of(
    any_string, integer, floating_point, boolean, date_time, invalid_date
)

# Recursive value strategy
value = st.recursive(
    scalar_value,
    lambda children: st.one_of(
        # arrays: possibly empty, possibly deep
        st.lists(children, max_size=6).map(_join_array),
        st.just("[]"),
        # inline tables
        st.lists(
            st.tuples(key, st.just(" = "), children).map(lambda t: t[0] + t[1] + t[2]),
            max_size=4,
        ).map(_join_inline),
        st.just("{}"),
        # trailing comma inline table
        st.lists(
            st.tuples(key, st.just(" = "), children).map(lambda t: t[0] + t[1] + t[2]),
            min_size=1,
            max_size=3,
        ).map(lambda ps: "{" + ", ".join(ps) + ",}"),
    ),
    max_leaves=40,
)

# Deep nesting in the 1500-2048 band: nested arrays
def _deep_array(depth):
    return "[" * depth + "1" + "]" * depth

deep_arrays = st.integers(min_value=1500, max_value=2048).map(_deep_array)

def _deep_inline(depth):
    inner = "1"
    for _ in range(depth):
        inner = "{a = " + inner + "}"
    return inner

deep_inlines = st.integers(min_value=200, max_value=500).map(_deep_inline)

# ---------- documents ----------

def _kv_line(k, v):
    return k + " = " + v

key_value = st.tuples(key, st.just(" = "), value).map(lambda t: t[0] + t[1] + t[2])

comment = st.one_of(
    st.just("#"),
    st.text(
        alphabet=st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(
            lambda c: c != "\n"
        ),
        max_size=30,
    ).map(lambda s: "#" + s),
)

def _table_line(k):
    return "[" + k + "]"

def _array_table_line(k):
    return "[[" + k + "]]"

table = key.map(_table_line)
array_table = key.map(_array_table_line)

_ws = st.sampled_from(["", " ", "\t", "  "])
_nl = st.sampled_from(["\n", "\r\n"])

def _line_expr(expr):
    return expr

expression = st.one_of(
    key_value,
    table,
    array_table,
    comment,
)

# Build a document: sequence of expressions separated by newlines
document = st.lists(expression, max_size=8).map(lambda es: "\n".join(es))

# Document with trailing newline sometimes
document_nl = st.tuples(document, _nl).map(lambda t: t[0] + t[1])

# Empty/comment-only documents
empty_doc = st.just("")
comment_only = st.lists(comment, min_size=1, max_size=5).map(lambda cs: "\n".join(cs))

# Documents covering deep nesting
deep_doc = st.one_of(
    deep_arrays.map(lambda a: "a = " + a),
    deep_inlines.map(lambda a: "a = " + a),
)

# ---------- malformed / near-valid ----------

def _mutate(s):
    # one missing/doubled delimiter, unterminated string, stray token
    return s

malformed = st.one_of(
    # unterminated basic string
    basic_string_inner.map(lambda s: 'a = "' + s),
    # unterminated literal string
    literal_string.map(lambda s: "a = " + s[:-1]),
    # missing closing bracket
    st.just("a = [1, 2, 3"),
    # doubled bracket
    st.just("a = [[1, 2]]"),
    # stray token
    st.just("a = @"),
    # missing equals
    st.just("a 1"),
    # value on next line
    st.just("a =\n1"),
    # newline inside inline table
    st.just("a = {b = 1,\nc = 2}"),
    # invalid escape
    st.just('a = "\\q"'),
    # unicode bare key
    st.just("é = 1"),
    # duplicate key (parser rejects)
    st.just("a = 1\na = 2"),
    # duplicate table
    st.just("[t]\n[t]"),
    # table and array of tables same name
    st.just("[t]\n[[t]]"),
)

# ---------- assemble ----------

strategy = st.one_of(
    document,
    document_nl,
    empty_doc,
    comment_only,
    deep_doc,
    malformed,
    # a key/value with every value kind
    key_value,
    # CRLF and tab indentation
    st.tuples(st.just("\t"), key_value, _nl).map(lambda t: t[0] + t[1] + t[2]),
    # long key
    st.tuples(long_unquoted_key, st.just(" = 1")).map(lambda t: t[0] + t[1]),
    # empty quoted key
    st.just('"" = 1'),
    # empty table
    st.just("[t]"),
    # empty array of tables
    st.just("[[a]]"),
    # --- added: richer structural coverage for tables & nesting ---
    # table with header followed by key/values (exercises table state machine)
    st.tuples(
        table,
        _nl,
        st.lists(key_value, min_size=1, max_size=4).map(lambda ls: "\n".join(ls)),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # array-of-tables with entries
    st.tuples(
        array_table,
        _nl,
        st.lists(key_value, min_size=1, max_size=4).map(lambda ls: "\n".join(ls)),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # nested tables via dotted headers
    st.tuples(
        st.lists(key_simple, min_size=2, max_size=4).map(lambda ks: "[" + ".".join(ks) + "]"),
        _nl,
        key_value,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # mixed document: table + array-table + kvs + comments
    st.lists(expression, min_size=2, max_size=10).map(lambda es: "\n".join(es)),
    # whitespace variety around equals and separators
    st.tuples(
        key,
        _ws,
        st.just("="),
        _ws,
        value,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3] + t[4]),
    # arrays with mixed whitespace and trailing comma
    st.lists(value, min_size=1, max_size=5).map(
        lambda vs: "a = [ " + " , ".join(vs) + " , ]"
    ),
    # inline table with mixed whitespace
    st.lists(key_value, min_size=1, max_size=4).map(
        lambda ps: "a = { " + " , ".join(ps) + " }"
    ),
    # --- added: targeted coverage for parser edge paths ---
    # table header followed by nested dotted subtable headers
    st.tuples(
        table,
        _nl,
        st.lists(
            st.tuples(
                st.lists(key_simple, min_size=2, max_size=3).map(
                    lambda ks: "[" + ".".join(ks) + "]"
                ),
                _nl,
                key_value,
            ).map(lambda t: t[0] + t[1] + t[2]),
            min_size=1,
            max_size=3,
        ).map(lambda ls: "\n".join(ls)),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # array-of-tables with nested array-of-tables
    st.tuples(
        array_table,
        _nl,
        key_value,
        _nl,
        array_table,
        _nl,
        key_value,
    ).map(lambda t: "".join(t)),
    # comments interleaved with whitespace and key/values
    st.lists(
        st.one_of(
            comment,
            key_value,
            st.just(""),
            st.just("  "),
            st.just("\t"),
        ),
        min_size=1,
        max_size=8,
    ).map(lambda ls: "\n".join(ls)),
    # boolean / number edge values in tables
    st.tuples(
        st.just("[nums]"),
        _nl,
        st.lists(
            st.tuples(
                unquoted_key,
                st.just(" = "),
                st.one_of(integer, floating_point, boolean, date_time),
            ).map(lambda t: t[0] + t[1] + t[2]),
            min_size=1,
            max_size=5,
        ).map(lambda ls: "\n".join(ls)),
    ).map(lambda t: t[0] + t[1] + t[2]),
    # quoted keys with escapes in key position
    st.tuples(
        st.one_of(
            basic_string,
            st.tuples(st.just('"'), escapes, st.just('"')).map(lambda t: t[0] + t[1] + t[2]),
        ),
        st.just(" = "),
        value,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # empty array / empty inline table as top-level values
    st.sampled_from(["a = []", "a = {}", "a = [[]]", "a = [{}]", "a = {b = []}"]),
    # strings with all escape kinds
    st.tuples(
        st.just("a = "),
        st.lists(escapes, min_size=1, max_size=6).map(
            lambda es: '"' + "".join(es) + '"'
        ),
    ).map(lambda t: t[0] + t[1]),
    # multiline strings with leading newline (parser strips)
    st.tuples(
        st.just("a = "),
        st.one_of(
            st.just('"""\nhello"""'),
            st.just("'''\nhello'''"),
            st.just('"""\r\nhello"""'),
        ),
    ).map(lambda t: t[0] + t[1]),
    # --- added: broaden coverage of strings, numbers, and whitespace edge paths ---
    # every escape kind individually at top level and inside arrays
    st.tuples(
        st.just("a = "),
        st.lists(escapes, min_size=1, max_size=8).map(
            lambda es: '["' + "".join(es) + '"]'
        ),
    ).map(lambda t: t[0] + t[1]),
    # multiline strings with embedded escapes and real newlines
    st.tuples(
        st.just("a = "),
        st.lists(
            st.one_of(escapes, st.just("\n"), st.just("\r\n"), st.just('"'), st.just("'")),
            min_size=1,
            max_size=8,
        ).map(lambda cs: '"""' + "".join(cs) + '"""'),
    ).map(lambda t: t[0] + t[1]),
    # literal multiline with embedded single quotes
    st.tuples(
        st.just("a = "),
        st.lists(
            st.one_of(st.just("'"), st.just("\n"), st.just("x")),
            min_size=1,
            max_size=8,
        ).map(lambda cs: "'''" + "".join(cs) + "'''"),
    ).map(lambda t: t[0] + t[1]),
    # numeric edge cases: signed/underscored/leading-zero integers and floats
    st.tuples(
        st.just("a = "),
        st.one_of(
            st.just("+0"),
            st.just("-0"),
            st.just("0x0"),
            st.just("0o0"),
            st.just("0b0"),
            st.just("1__0"),
            st.just("_1"),
            st.just("1_"),
            st.just("0x"),
            st.just("0o"),
            st.just("0b"),
            st.just("1."),
            st.just(".1"),
            st.just("1.e5"),
            st.just("1e"),
            st.just("1e+"),
            st.just("1e-"),
            st.just("+."),
            st.just("-.5"),
        ),
    ).map(lambda t: t[0] + t[1]),
    # datetime edge cases: lowercase t/z, space delimiter, bad offsets
    st.tuples(
        st.just("a = "),
        st.one_of(
            st.just("1979-05-27T07:32:00Z"),
            st.just("1979-05-27t07:32:00z"),
            st.just("1979-05-27 07:32:00+00:00"),
            st.just("1979-05-27T07:32:00.999999-07:00"),
            st.just("1979-05-27T07:32:00+99:99"),
            st.just("07:32:00"),
            st.just("07:32:00.5"),
            st.just("1979-05-27"),
            st.just("1979-13-40"),
        ),
    ).map(lambda t: t[0] + t[1]),
    # whitespace variety: leading/trailing spaces, tabs, CRLF around constructs
    st.tuples(
        _ws,
        st.one_of(key_value, table, array_table, comment),
        _ws,
        _nl,
    ).map(lambda t: t[0] + t[1] + t[2] + t[3]),
    # array with newlines and comments between elements
    st.tuples(
        st.just("a = ["),
        _nl,
        comment,
        _nl,
        value,
        _nl,
        st.just("]"),
    ).map(lambda t: "".join(t)),
    # dotted keys in key/value position (deep)
    st.tuples(
        st.lists(key_simple, min_size=2, max_size=5).map(lambda ks: ".".join(ks)),
        st.just(" = "),
        value,
    ).map(lambda t: t[0] + t[1] + t[2]),
    # table header with quoted / escaped segments
    st.tuples(
        st.just("["),
        st.lists(
            st.one_of(unquoted_key, basic_string, literal_string),
            min_size=1,
            max_size=4,
        ).map(lambda ks: ".".join(ks)),
        st.just("]"),
        _nl,
        key_value,
    ).map(lambda t: "".join(t)),
    # array-of-tables with dotted names
    st.tuples(
        st.just("[["),
        st.lists(key_simple, min_size=2, max_size=4).map(lambda ks: ".".join(ks)),
        st.just("]]"),
        _nl,
        key_value,
    ).map(lambda t: "".join(t)),
)
```