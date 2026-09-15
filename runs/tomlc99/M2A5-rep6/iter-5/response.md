```python
from hypothesis import strategies as st
import json

# Helper small pieces
_ascii_unquoted = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-_"
    ),
    min_size=1,
    max_size=50
)

# Very long key to exercise limits (including 10k char case sometimes)
_long_key = st.one_of(
    _ascii_unquoted,
    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=0x10FFFF).filter(lambda s: "\x00" not in s),
            min_size=1000, max_size=10000)
)

# Quoted keys (allow empty quoted key "")
_basic_quoted_key = st.one_of(
    st.just('""'),
    st.builds(lambda s: '"' + s + '"', st.text(min_size=0, max_size=50).filter(lambda s: "\x00" not in s and '\n' not in s and '"' not in s)),
    st.builds(lambda s: "'" + s + "'", st.text(min_size=0, max_size=50).filter(lambda s: "\x00" not in s and '\n' not in s and "'" not in s)),
)

# dotted key: combine simple keys and quoted pieces
_dotted_key = st.lists(st.one_of(_ascii_unquoted, _basic_quoted_key), min_size=1, max_size=4).map(lambda parts: ".".join(parts))

# Booleans
_bool = st.sampled_from(["true", "false"])

# Integers: decimal (allow leading zeros), hex, oct, bin, with underscores and extreme sizes
def _dec_int_str(n):
    s = str(n)
    # optionally insert underscores
    if len(s) > 2 and False:
        # naive underscore insertion (disabled deterministic)
        parts = [s[max(0, i-3):i] for i in range(len(s), 0, -3)]
        s = "_".join(reversed(parts))
    return s

_dec_int_small = st.integers(min_value=-2**63, max_value=2**63-1).map(str)
_dec_int_leading_zero = st.integers(min_value=0, max_value=999).map(lambda x: f"{x:03d}")
_dec_int_large = st.integers(min_value=10**18, max_value=10**300).map(str)
_hex_int = st.builds(lambda s: "0x" + s,
                     st.text(alphabet="0123456789abcdefABCDEF", min_size=1, max_size=30))
_oct_int = st.builds(lambda s: "0o" + s,
                     st.text(alphabet="01234567", min_size=1, max_size=30))
_bin_int = st.builds(lambda s: "0b" + s,
                     st.text(alphabet="01", min_size=1, max_size=64))

_integer_value = st.one_of(
    _dec_int_small,
    _dec_int_leading_zero,
    _dec_int_large,
    _hex_int,
    _oct_int,
    _bin_int,
)

# Floats: include forms like 1., .5, exponent, inf/nan and extremes
_float_normal = st.one_of(
    st.builds(lambda a, b: f"{a}.{b}", st.integers(min_value=0, max_value=10**6).map(str), st.integers(min_value=0, max_value=10**6).map(str)),
    st.builds(lambda a: f"{a}.", st.integers(min_value=0, max_value=10**6).map(str)),  # 1.
    st.builds(lambda b: f".{b}", st.integers(min_value=0, max_value=10**6).map(str)),   # .5
    st.builds(lambda a, e: f"{a}e{e}", st.integers(min_value=1, max_value=10**6).map(str), st.integers(min_value=-400, max_value=400).map(str)),
    st.builds(lambda a, f, e: f"{a}.{f}e{e}", st.integers(min_value=1, max_value=10**6).map(str), st.integers(min_value=0, max_value=10**6).map(str), st.integers(min_value=-400, max_value=400).map(str))
)
_float_special = st.sampled_from(["inf", "-inf", "+inf", "nan", "-nan", "+nan"])
_float_extreme = st.builds(lambda s: s, st.sampled_from(["1e309", "-1e309", "9.99e9999"]))
_float_value = st.one_of(_float_normal, _float_special, _float_extreme)

# Date/time: four forms, allow calendar-invalid dates
_year = st.integers(min_value=0, max_value=9999).map(lambda y: f"{y:04d}")
_month = st.integers(min_value=1, max_value=12).map(lambda m: f"{m:02d}")
_day = st.integers(min_value=1, max_value=31).map(lambda d: f"{d:02d}")
_hour = st.integers(min_value=0, max_value=23).map(lambda h: f"{h:02d}")
_minute = st.integers(min_value=0, max_value=59).map(lambda m: f"{m:02d}")
_second = st.integers(min_value=0, max_value=59).map(lambda s: f"{s:02d}")
_secfrac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.integers(min_value=0, max_value=10**6).map(str)))

_offset = st.one_of(
    st.just("Z"),
    st.builds(lambda sign, hh, mm: f"{sign}{hh}:{mm}",
              st.sampled_from(["+", "-"]),
              st.integers(min_value=0, max_value=23).map(lambda n: f"{n:02d}"),
              st.integers(min_value=0, max_value=59).map(lambda n: f"{n:02d"))
)

_date_local = st.builds(lambda Y, M, D: f"{Y}-{M}-{D}", _year, _month, _day)
_time_partial = st.builds(lambda h, m, s, frac: f"{h}:{m}:{s}{frac}", _hour, _minute, _second, _secfrac)
_offset_date_time = st.builds(lambda date, sep, time, off: f"{date}{sep}{time}{off}",
                              _date_local,
                              st.sampled_from(["T", "t", " "]),
                              _time_partial,
                              _offset)
_local_date_time = st.builds(lambda date, sep, time: f"{date}{sep}{time}", _date_local, st.sampled_from(["T", "t", " "]), _time_partial)
_local_date = _date_local
_local_time = _time_partial

_date_value = st.one_of(_offset_date_time, _local_date_time, _local_date, _local_time)

# Strings: four forms plus malformed variants (unterminated, invalid escape, embedded control bytes, unicode escapes)
# Avoid raw NUL '\x00' in produced strings; but allow escape sequence "\u0000" as text.
_non_nul_char = st.characters(min_codepoint=1, max_codepoint=0x10FFFF).filter(lambda c: c != "\x00")
_basic_string_content = st.text(alphabet=_non_nul_char, min_size=0, max_size=100).filter(lambda s: "\n" not in s and '"' not in s and "\\" not in s)
_basic_string_with_escapes = st.text(
    alphabet=st.characters(blacklist_characters=['\x00', '"']), min_size=0, max_size=100
).map(lambda s: s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t"))
_literal_string_content = st.text(alphabet=_non_nul_char, min_size=0, max_size=100).filter(lambda s: "'" not in s and "\n" not in s)
_ml_basic_content = st.text(alphabet=_non_nul_char, min_size=0, max_size=200)  # can contain newlines
_ml_literal_content = st.text(alphabet=_non_nul_char, min_size=0, max_size=200)

# Create different string forms, with occasional malformed variants
_basic_string = st.one_of(
    st.builds(lambda s: '"' + s + '"', _basic_string_with_escapes),
    st.builds(lambda s: '"' + s, _basic_string_with_escapes),  # unterminated
    st.builds(lambda s: '"' + s + '\\""', _basic_string_content)  # doubled delimiter inside
)

_literal_string = st.one_of(
    st.builds(lambda s: "'" + s + "'", _literal_string_content),
    st.builds(lambda s: "'" + s, _literal_string_content)  # unterminated
)

_ml_basic_string = st.one_of(
    st.builds(lambda s: '"""' + s + '"""', _ml_basic_content),
    st.builds(lambda s: '"""' + s, _ml_basic_content),  # unterminated
)

_ml_literal_string = st.one_of(
    st.builds(lambda s: "'''" + s + "'''", _ml_literal_content),
    st.builds(lambda s: "'''" + s, _ml_literal_content),
)

# Introduce strings with explicit escape sequences including unicode and invalid escapes
_escape_seq_string = st.one_of(
    st.builds(lambda body: '"' + body + '"',
              st.lists(st.one_of(st.just("\\n"), st.just("\\t"), st.just("\\u0000"), st.just("\\U00000041"), st.just("\\q"), st.just("\\\\"), st.just("A"), st.characters(min_codepoint=1, max_codepoint=127)),
                       min_size=0, max_size=50).map(lambda parts: "".join(parts))),
)

_string_value = st.one_of(_basic_string, _literal_string, _ml_basic_string, _ml_literal_string, _escape_seq_string)

# Primitive values strategy
_primitive_value = st.one_of(
    _string_value,
    _integer_value,
    _float_value,
    _bool,
    _date_value
)

# Recursive containers: arrays and inline tables. Use st.recursive to allow nesting.
def _make_array(items, allow_trailing_comma):
    # items: list of strings representing values/comments
    # Randomly insert comments/newlines between items; items are strings already
    inner = []
    for it in items:
        inner.append(it)
    body = ", ".join(inner)
    # Avoid using .example() inside strategy construction; only add trailing comma if there are items
    if allow_trailing_comma and len(items) > 0:
        # append trailing comma
        body = body + ","
    return "[" + body + "]"

def _make_inline_table(pairs, allow_trailing_comma, multiline_newline):
    # pairs: list of (k, v) tuples where k is key string, v is value string
    # multiline_newline indicates whether to include a newline inside (which is invalid per parser grammar)
    parts = []
    for k, v in pairs:
        parts.append(f"{k} = {v}")
    body = ", ".join(parts)
    # Avoid using .example() inside strategy construction; only add trailing comma if there are parts
    if allow_trailing_comma and len(parts) > 0:
        body = body + ","
    if multiline_newline and parts:
        # inject newline into inline table to create a near-valid-but-malformed input
        body = body.replace(", ", ",\n", 1)
    return "{" + body + "}"

# Strategies to build arrays and inline tables given element/value strategy
def _array_factory(elem_strat):
    # generate list of elements up to moderate size; allow nested arrays via elem_strat
    return st.lists(elem_strat, min_size=0, max_size=6).flatmap(
        lambda items: st.tuples(st.just(items), st.booleans()).map(lambda tpl: _make_array(tpl[0], tpl[1]))
    )

def _inline_table_factory(elem_strat):
    # generate 0..6 key/value pairs; keys can be simple, dotted, or quoted.
    # Instead of using .example() in strategy (bad), we construct using builds with lists.
    return st.lists(st.tuples(st.one_of(_ascii_unquoted, _basic_quoted_key, _long_key), elem_strat),
                    min_size=0, max_size=6).flatmap(
        lambda pairs: st.tuples(st.just(pairs), st.booleans(), st.booleans()).map(lambda tpl: _make_inline_table(tpl[0], tpl[1], tpl[2]))
    )

# Use st.recursive to produce nested arrays and inline tables; high max_leaves to allow deep nesting
_recursive_values = st.recursive(
    _primitive_value,
    lambda children: st.one_of(
        _array_factory(children),
        _inline_table_factory(children)
    ),
    max_leaves=2048
)

# Expression generators: key_value lines, tables, array tables, comment-only.
# key_value: key = value; key can be simple, dotted, or quoted.
_key_simple = st.one_of(_ascii_unquoted, _basic_quoted_key, _long_key)
_key_dotted = st.lists(st.one_of(_ascii_unquoted, _basic_quoted_key), min_size=2, max_size=5).map(lambda parts: ".".join(parts))
_key = st.one_of(_key_simple, _key_dotted, _dotted_key)

_key_value = st.builds(lambda k, v: f"{k} = {v}", _key, _recursive_values)

_table_header = st.builds(lambda k: f"[{k}]", st.one_of(_dotted_key, _key_simple, _basic_quoted_key))
_array_table_header = st.builds(lambda k: f"[[{k}]]", st.one_of(_dotted_key, _key_simple, _basic_quoted_key))

_comment = st.builds(lambda c: "#" + c, st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=60))

# Sometimes produce malformed headers: missing bracket or doubled bracket
_table_header_malformed = st.one_of(
    st.builds(lambda k: "[" + k, st.one_of(_dotted_key, _key_simple, _basic_quoted_key)),  # missing ]
    st.builds(lambda k: f"{k}]]", st.one_of(_dotted_key, _key_simple, _basic_quoted_key)),  # stray ]]
)

_expression = st.one_of(
    _key_value,
    st.builds(lambda h: h, _table_header),
    st.builds(lambda h: h, _array_table_header),
    _comment,
    _table_header_malformed,
    st.just("]"),  # stray token
    st.just("="),  # stray token
)

# Now build a full document: sequence of expressions separated by newlines (CRLF sometimes)
_newline = st.sampled_from(["\n", "\r\n"])
_expressions_list = st.lists(_expression, min_size=0, max_size=200)

_document = st.builds(
    lambda exprs, newline, trailing: (newline.join(exprs) + (newline if trailing else "")),
    _expressions_list, _newline, st.booleans()
)

# Top-level strategy must be named `strategy` and produce str
strategy = _document.map(lambda s: s)
```