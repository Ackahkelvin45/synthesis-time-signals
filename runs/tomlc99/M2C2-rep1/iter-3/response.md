```python
from hypothesis import strategies as st
import json

# Helper small strategies
_hexdigit = st.sampled_from(list("0123456789abcdefABCDEF"))
_digit = st.sampled_from(list("0123456789"))
_sign = st.sampled_from(["+", "-"])
_nondigit_key_char = st.sampled_from(list("_-"))
_alpha = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu")), min_size=1, max_size=1)

# Characters excluding NUL and newlines where required
_no_nul_no_newline_char = st.characters(
    blacklist_characters=["\x00", "\n", "\r"], whitelist_categories=("L", "M", "N", "P", "S", "Zs")
)
_no_nul_no_newline_noquote_char = st.characters(
    blacklist_characters=['\x00', '\n', '\r', '"', "\\", "'"], whitelist_categories=("L", "M", "N", "P", "S", "Zs")
)
_no_nul_char = st.characters(blacklist_characters=["\x00"], whitelist_categories=("L", "M", "N", "P", "S", "Zs"))

# Build escape sequences used in basic strings
_unicode_escape = st.builds(lambda a, b, c, d: "\\u" + a + b + c + d, _hexdigit, _hexdigit, _hexdigit, _hexdigit)
_ex_unicode_escape = st.builds(
    lambda a,b,c,d,e,f,g,h: "\\U" + a+b+c+d+e+f+g+h,
    _hexdigit, _hexdigit, _hexdigit, _hexdigit,
    _hexdigit, _hexdigit, _hexdigit, _hexdigit,
)
_simple_escape = st.sampled_from([r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'])
_invalid_escape = st.sampled_from([r'\q', r'\y', r'\z'])  # intentionally invalid to provoke parser rejection

_escape_seq = st.one_of(_simple_escape, _unicode_escape, _ex_unicode_escape, _invalid_escape)

# Basic string content: sequences of raw (not quote/backslash/newline/NUL) or escape sequences
_basic_raw_piece = st.text(alphabet=st.characters(blacklist_characters=['\x00', '\n', '\r', '\\', '"'], whitelist_categories=("L","M","N","P","S","Zs")), min_size=0, max_size=30)
_basic_string_content = st.lists(st.one_of(_basic_raw_piece, _escape_seq), min_size=0, max_size=6).map("".join)

# Multiline basic string content: allow newlines and CR but no NUL; raw backslash permitted only as part of escapes
_ml_raw_piece = st.text(alphabet=st.characters(blacklist_characters=['\x00',], whitelist_categories=("L","M","N","P","S","Zs")), min_size=0, max_size=40)
_ml_basic_string_content = st.lists(st.one_of(_ml_raw_piece, _escape_seq, st.just("\n")), min_size=0, max_size=12).map("".join)

# Literal strings: no escapes; exclude single quote and newline for single-line literal
_literal_content = st.text(alphabet=st.characters(blacklist_characters=['\x00', '\n', '\r', "'"], whitelist_categories=("L","M","N","P","S","Zs")), min_size=0, max_size=40)
_ml_literal_content = st.text(alphabet=st.characters(blacklist_characters=['\x00'], whitelist_categories=("L","M","N","P","S","Zs")), min_size=0, max_size=200)

# Build string token generators (including occasional malformed variants)
def _maybe_unterminated(s):  # wrap with a chance to produce unterminated variant (omit closing delimiter)
    return st.one_of(s, s.map(lambda x: x[:-1] if x.endswith('\n') else x)  # harmless no-op mapping included
                      , s.map(lambda x: x[1:] if len(x) and x[0] in ('"', "'") else x).map(lambda x: x + "") )  # placeholder, keep diversity

_basic_string = st.deferred(lambda:
    st.one_of(
        # normal basic string
        _basic_string_content.map(lambda c: '"' + c + '"'),
        # invalid escape-heavy
        st.lists(st.one_of(_basic_raw_piece, _invalid_escape), min_size=0, max_size=6).map(lambda parts: '"' + "".join(parts) + '"'),
        # unterminated (missing closing quote)
        _basic_string_content.map(lambda c: '"' + c)  # unterminated
    )
)

_ml_basic_string = st.one_of(
    _ml_basic_string_content.map(lambda c: '"""' + c + '"""'),
    # unterminated
    _ml_basic_string_content.map(lambda c: '"""' + c)
)

_literal_string = st.one_of(
    _literal_content.map(lambda c: "'" + c + "'"),
    # empty quoted key case and unterminated
    st.just("''"),
    _literal_content.map(lambda c: "'" + c)  # unterminated
)

_ml_literal_string = st.one_of(
    _ml_literal_content.map(lambda c: "'''" + c + "'''"),
    _ml_literal_content.map(lambda c: "'''" + c)  # unterminated
)

# Key strategies: unquoted, quoted (allow empty quoted), dotted keys, very long keys
_unquoted_key = st.text(alphabet=st.characters(blacklist_characters=['\x00', '\n', '\r'], whitelist_categories=("L","M","N")), min_size=1, max_size=20).map(
    lambda s: "".join(ch if ch.isalnum() or ch in ('_', '-') else '_' for ch in s)
)
_very_long_key = st.just("k" * 10000)
_quoted_key = st.one_of(
    _basic_string,
    _literal_string,
    st.just('""')  # empty quoted key
)
_simple_key = st.one_of(_quoted_key, _unquoted_key, _very_long_key)

# Dotted key: join simple keys with dots; sometimes include quoted parts
_dotted_key = st.deferred(lambda: st.one_of(
    _simple_key,
    st.lists(_simple_key, min_size=2, max_size=5).map(lambda parts: ".".join(parts))
))

# Booleans
_bool = st.sampled_from(["true", "false"])

# Integers: decimals (allow leading zeros), hex/octal/bin, underscores, signs, extreme lengths
def _dec_int():
    # occasionally produce leading zeros
    return st.one_of(
        st.builds(lambda s: s, st.text(alphabet="0123456789", min_size=1, max_size=1)),  # single digit
        st.text(alphabet="0123456789_", min_size=1, max_size=30).map(lambda s: s.strip("_") or "0"),
        st.just("007"),  # explicit allowed leading zeros case
        st.just("0"),
        st.text(alphabet="0123456789", min_size=50, max_size=3000)  # extreme magnitude
    ).map(lambda s: s if (s[0] in "+-" or s[0].isdigit()) else s)

_dec_int_signed = st.one_of(
    _dec_int().map(lambda s: s),
    st.builds(lambda sign, s: sign + s, _sign, _dec_int())
)

_hex_int = st.builds(lambda s: "0x" + s, st.text(alphabet="0123456789abcdefABCDEF_", min_size=1, max_size=40).map(lambda s: s.strip("_") or "0"))
_oct_int = st.builds(lambda s: "0o" + s, st.text(alphabet="01234567_", min_size=1, max_size=40).map(lambda s: s.strip("_") or "0"))
_bin_int = st.builds(lambda s: "0b" + s, st.text(alphabet="01_", min_size=1, max_size=40).map(lambda s: s.strip("_") or "0"))

_integer = st.one_of(_dec_int_signed, _hex_int, _oct_int, _bin_int)

# Floats: include 1., .5, exponent extremes, inf/nan variants
_float_normal = st.one_of(
    # formats: 1., .5, 1.0, 1e10, 1.234e-10, large exponent
    st.builds(lambda a, b: a + b,
              st.one_of(st.text(alphabet="0123456789", min_size=1, max_size=20),
                        st.text(alphabet="0123456789", min_size=1, max_size=1).map(lambda s: s)),
              st.one_of(st.just("."), st.just(".5"), st.builds(lambda frac, exp: "." + frac + exp,
                                                              st.text(alphabet="0123456789", min_size=0, max_size=20).map(lambda x: x or "0"),
                                                              st.one_of(st.just(""), st.builds(lambda e: "e" + e, st.text(alphabet="0123456789+-", min_size=1, max_size=5)))))
             ),
    st.builds(lambda mant, exp: mant + "e" + exp, st.text(alphabet="0123456789", min_size=1, max_size=5), st.text(alphabet="0123456789+-", min_size=1, max_size=5)),
    # very large exponent
    st.builds(lambda a, b: a + "e" + b, st.text(alphabet="0123456789", min_size=1, max_size=10), st.text(alphabet="0123456789+-", min_size=3, max_size=6)),
)

_inf_nan = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])

_float = st.one_of(_float_normal, _inf_nan)

# Date and time forms
def _date_time_gen():
    year = st.text(alphabet="0123456789", min_size=4, max_size=4)
    month = st.text(alphabet="0123456789", min_size=2, max_size=2)
    day = st.text(alphabet="0123456789", min_size=2, max_size=2)
    hour = st.text(alphabet="0123456789", min_size=2, max_size=2)
    minute = st.text(alphabet="0123456789", min_size=2, max_size=2)
    second = st.text(alphabet="0123456789", min_size=2, max_size=2)
    frac = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text(alphabet="0123456789", min_size=1, max_size=9)))
    offset = st.one_of(st.just("Z"), st.builds(lambda s1, s2, s3: s1 + ":" + s2, st.text(alphabet="+-", min_size=1, max_size=1).map(lambda s: s if s in "+-" else "+"),
                                               st.text(alphabet="0123456789", min_size=2, max_size=2),
                                               st.text(alphabet="0123456789", min_size=2, max_size=2)))
    # create various combos: offset-date-time, local-date-time, local-date, local-time
    return st.one_of(
        st.builds(lambda Y, M, D, delim, H, Min, S, F, Off: Y + "-" + M + "-" + D + delim + H + ":" + Min + ":" + S + F + Off,
                  year, month, day, st.sampled_from(["T", " ", "t"]), hour, minute, second, frac, st.one_of(st.just("Z"), st.builds(lambda a,b: a+":"+b, st.text(alphabet="+-", min_size=1, max_size=1).map(lambda s: s if s in "+-" else "+"), st.text(alphabet="0123456789", min_size=2, max_size=2)))),
        st.builds(lambda Y, M, D, delim, H, Min, S, F: Y + "-" + M + "-" + D + delim + H + ":" + Min + ":" + S + F,
                  year, month, day, st.sampled_from(["T", " "]), hour, minute, second, frac),
        st.builds(lambda Y, M, D: Y + "-" + M + "-" + D, year, month, day),
        st.builds(lambda H, Min, S, F: H + ":" + Min + ":" + S + F, hour, minute, second, frac)
    )

_date_time = _date_time_gen()

# Comments: start with '#', may include raw control characters except NUL
_comment_text = st.text(alphabet=st.characters(blacklist_characters=['\x00'], whitelist_categories=("L","M","N","P","S","Zs")), min_size=0, max_size=60)
_comment_line = _comment_text.map(lambda t: "#" + t)

# Base value strategy (non-recursive)
_base_value = st.deferred(lambda: st.one_of(
    _basic_string,
    _ml_basic_string,
    _literal_string,
    _ml_literal_string,
    _integer,
    _float,
    _bool,
    _date_time
))

# Recursive construction for arrays and inline tables
def _array_builder(elem_strategy):
    # array_items: allow comments/newlines interleaved; include trailing comma; include nested arrays/tables via elem_strategy
    sep = st.just(",")
    # build list of 0..6 elements
    elems = st.lists(elem_strategy, min_size=0, max_size=6)
    # allow comments between items and trailing comma, and nested newlines/comments
    def make_array(items):
        # items is a list of textual value strings
        if not items:
            return "[]"
        # intersperse optional comments and newlines randomly: since this is static mapping, craft a simple variant that includes comments sometimes
        parts = []
        for i, v in enumerate(items):
            # occasionally add a comment before value
            parts.append(v)
            if i != len(items) - 1:
                parts.append(",")
        if st.random_module := None:  # dummy to quiet linters; won't execute
            pass
        return "[" + " ".join(parts) + "]"
    # Because we cannot access randomness here in builds, instead construct with builds using the list
    return elems.map(lambda items: (
        "[" + (", ".join(items) + ("," if (len(items) and (len(items) % 5 == 0)) else "")) + "]" if items else "[]"
    ))

def _inline_table_builder(kv_value_strategy):
    # kv_value_strategy produces "key = value" fragments (no newlines inside normally)
    # Build inline table: { k = v, k2 = v2, } sometimes include trailing comma; occasionally include a newline to create a malformed input
    kv_pairs = st.lists(kv_value_strategy, min_size=0, max_size=6)
    def build_braced(pairs):
        if not pairs:
            return "{}"
        body = ", ".join(pairs)
        # occasionally add trailing comma
        body = body + ("," if len(pairs) % 2 == 0 else "")
        return "{" + body + "}"
    return kv_pairs.map(build_braced)

# KV pair generator: key = value_text where value_text is produced by recursive value strategy later
@st.composite
def kv_pair(draw, value_strategy):
    key = draw(st.one_of(_simple_key, _quoted_key, _very_long_key))
    val = draw(value_strategy)
    # sometimes produce missing equals or doubled equals to create near-malformed input
    choice = draw(st.integers(min_value=0, max_value=9))
    if choice == 0:
        # missing equals: produce "key value" (no equals)
        return f"{key} {val}"
    elif choice == 1:
        # doubled equals
        return f"{key} == {val}"
    else:
        return f"{key} = {val}"

# Now recursive value strategy: base + arrays and inline tables built from nested values
def _build_recursive_value_strategy():
    # We'll use st.recursive with a factory that can build arrays and inline tables
    base = _base_value

    def extend(child):
        # child is a strategy yielding textual value representations
        array_strat = st.builds(lambda items: "[" + ", ".join(items) + ("," if (len(items) and len(items) % 2 == 0) else "") + "]",
                                st.lists(child, min_size=0, max_size=5))
        # inline table needs key/value pairs; keys must be simple keys or quoted keys
        inline_kv = st.lists(st.tuples(st.one_of(_simple_key, _quoted_key), child).map(lambda kv: f"{kv[0]} = {kv[1]}"), min_size=0, max_size=6)
        inline_table = inline_kv.map(lambda pairs: "{" + (", ".join(pairs) + ("," if (len(pairs) and len(pairs) % 2 == 0) else "")) + "}" if pairs else "{}")
        # occasionally construct malformed inline table with newline inside (which parser rejects)
        inline_table_malformed = inline_kv.map(lambda pairs: "{\n" + ("\n".join(pairs)) + "\n}" if pairs else "{\n}")
        return st.one_of(array_strat, inline_table, inline_table_malformed)
    # Allow deep recursion; max_leaves tuned to allow deep nested arrays/inline tables up to parser recursion band
    return st.recursive(base, extend, max_leaves=3000)

_value = _build_recursive_value_strategy()

# Expression strategies: key_value lines, tables, array_tables, comments
@st.composite
def key_value_expression(draw):
    # build a key (dotted or simple), equals, and value; value can be multi-line strings etc.
    key = draw(st.one_of(_dotted_key, _simple_key, _quoted_key))
    val = draw(_value)
    # occasionally append a comment
    if draw(st.booleans()):
        comment = draw(st.one_of(_comment_line, st.just("")))
        return f"{key} = {val}" + ((" " + comment) if comment else "")
    return f"{key} = {val}"

@st.composite
def table_expression(draw):
    # standard table [key] or array table [[key]]
    key = draw(st.one_of(_dotted_key, _simple_key, _quoted_key))
    if draw(st.booleans()):
        return "[" + key + "]"
    else:
        return "[[" + key + "]]"

@st.composite
def comment_expression(draw):
    # possibly empty comment or comment with raw control chars (excluding NUL)
    comment = draw(_comment_line)
    return comment

_expression = st.one_of(key_value_expression(), table_expression(), comment_expression())

# Document: sequence of expressions with newline separators. Allow empty documents and comment-only docs.
@st.composite
def document_strategy(draw):
    # number of lines
    n = draw(st.integers(min_value=0, max_value=30))
    exprs = []
    # Introduce deliberate duplicate keys/tables by probabilistically reusing same kv
    saved_kv = None
    for i in range(n):
        choice = draw(st.integers(min_value=0, max_value=9))
        if choice <= 5:
            e = draw(_expression)
        elif choice == 6 and saved_kv:
            e = saved_kv  # duplicate key intentionally
        else:
            # create a key-value expression and sometimes save it for duplication
            kv = draw(key_value_expression())
            e = kv
            if draw(st.booleans()):
                saved_kv = kv
        exprs.append(e)
    # optionally insert table at random positions, arrays of tables etc
    if draw(st.booleans()) and exprs:
        idx = draw(st.integers(min_value=0, max_value=len(exprs)-1))
        # insert an array-table
        tbl = draw(table_expression())
        exprs.insert(idx, tbl)
    # join lines with either LF or CRLF
    sep = draw(st.sampled_from(["\n", "\r\n"]))
    doc = sep.join(exprs)
    # optionally no trailing newline; sometimes add trailing newline
    if draw(st.booleans()):
        doc = doc + sep
    # occasionally append a stray token at the end to create near-valid-but-malformed input
    if draw(st.integers(min_value=0, max_value=15)) == 0:
        doc = doc + " " + draw(st.sampled_from(["#", "]", "}", "]]", "="]))
    return doc

# Export top-level strategy
strategy = document_strategy()
```