```python
from hypothesis import strategies as st
import json

# Helper small generators
_ascii_key_char = st.sampled_from(list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"))
_unquoted_key = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20)
# Quoted keys as BASIC_STRING or LITERAL_STRING
# For building pieces, avoid raw NUL (\x00) anywhere in generated literal text; use escapes instead.

# Escape sequences allowed in BASIC_STRING
_unicode_escape_4 = st.integers(min_value=0, max_value=0xFFFF).map(lambda v: "\\u%04x" % v)
_unicode_escape_8 = st.integers(min_value=0, max_value=0xFFFFFFFF).map(lambda v: "\\U%08x" % v)
_basic_esc_one = st.sampled_from(['\\\\', '\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
_bad_escape = st.sampled_from(['\\q', '\\z'])  # near-valid-but-malformed escape examples
_basic_escape = st.one_of(_basic_esc_one, _unicode_escape_4, _unicode_escape_8, _bad_escape)

# Characters allowed raw inside basic strings (raw control characters allowed except NUL),
# but exclude double-quote, backslash, and newline to avoid accidental termination or invalid grammar.
_basic_raw_char = st.characters(blacklist_characters='"\n\\\x00', min_codepoint=0x01, max_codepoint=0x10FFFF)
# For literal strings: single-quoted, exclude single quote and newline
_literal_raw_char = st.characters(blacklist_characters="'\n\x00", min_codepoint=0x01, max_codepoint=0x10FFFF)

# Small text segments to interleave with escapes
_text_segment = st.text(alphabet=_basic_raw_char, min_size=0, max_size=8)
_literal_segment = st.text(alphabet=_literal_raw_char, min_size=0, max_size=8)

# BASIC_STRING content: mix raw segments and escapes
_basic_string_content = st.lists(st.one_of(_text_segment.map(str), _basic_escape), min_size=0, max_size=6).map(lambda parts: "".join(parts))

_basic_string = st.one_of(
    _basic_string_content.map(lambda s: '"' + s + '"'),
    # unterminated variants
    _basic_string_content.map(lambda s: '"' + s),   # missing closing quote
    # double-delimiter (extra quote)
    _basic_string_content.map(lambda s: '""' + s + '"'),
)

# Multiline BASIC_STRING: triple quotes, allow raw newlines and escaped newline continuations
_ml_basic_inside = st.lists(st.one_of(
    st.text(alphabet=st.characters(blacklist_characters='\x00', min_codepoint=0x01), min_size=1, max_size=12),
    _basic_escape
), min_size=0, max_size=6).map(lambda parts: "".join(parts))
_ml_basic_string = st.one_of(
    _ml_basic_inside.map(lambda s: '"""' + s + '"""'),
    _ml_basic_inside.map(lambda s: '"""' + s),   # unterminated
)

# LITERAL_STRING
_literal_string = st.one_of(
    _literal_segment.map(lambda s: "'" + s + "'"),
    _literal_segment.map(lambda s: "'" + s),  # unterminated
)
# Multiline literal
_ml_literal_inside = st.text(alphabet=st.characters(blacklist_characters='\x00', min_codepoint=0x01), min_size=0, max_size=60)
_ml_literal_string = st.one_of(
    _ml_literal_inside.map(lambda s: "'''''" if False else "'''" + s + "'''"),  # normal triple
    _ml_literal_inside.map(lambda s: "'''" + s),  # unterminated
)

# QUOTED key generators
_basic_string_key = _basic_string.map(lambda s: s)
_literal_key = _literal_string.map(lambda s: s)

# Date/time generators: the parser accepts invalid calendar dates too.
_year = st.integers(min_value=0, max_value=9999).map(lambda x: "%04d" % x)
_two = lambda v: st.integers(min_value=0, max_value=v).map(lambda x: "%02d" % x)
_month = st.integers(min_value=0, max_value=99).map(lambda x: "%02d" % x)  # allow invalid months
_day = st.integers(min_value=0, max_value=99).map(lambda x: "%02d" % x)    # allow invalid days
_hour = st.integers(min_value=0, max_value=23).map(lambda x: "%02d" % x)
_minute = st.integers(min_value=0, max_value=59).map(lambda x: "%02d" % x)
_second = st.integers(min_value=0, max_value=59).map(lambda x: "%02d" % x)
_secfrac = st.integers(min_value=0, max_value=999999999).map(lambda x: "." + ("%d" % x))
_offset = st.one_of(
    st.just("Z"),
    st.tuples(st.sampled_from(['+', '-']), _hour, st.just(':'), _minute).map(lambda t: t[0] + t[1] + t[2] + t[3])
)
_offset_datetime = st.tuples(_year, st.just('-'), _month, st.just('-'), _day, st.sampled_from(['T', 't', ' ']), _hour, st.just(':'), _minute, st.just(':'), _second, st.one_of(_secfrac, st.just('')), _offset).map(lambda parts: "".join(parts))
_local_datetime = st.tuples(_year, st.just('-'), _month, st.just('-'), _day, st.sampled_from(['T', 't', ' ']), _hour, st.just(':'), _minute, st.just(':'), _second, st.one_of(_secfrac, st.just(''))).map(lambda parts: "".join(parts))
_local_date = st.tuples(_year, st.just('-'), _month, st.just('-'), _day).map(lambda parts: "".join(parts))
_local_time = st.tuples(_hour, st.just(':'), _minute, st.just(':'), _second, st.one_of(_secfrac, st.just(''))).map(lambda parts: "".join(parts))

# Integer generators for various bases (include leading zeros, underscores, signs)
_dec_digits = st.text(alphabet=st.sampled_from(list("0123456789")), min_size=1, max_size=20)
_dec_with_underscores = st.lists(st.text(alphabet=st.sampled_from(list("0123456789")), min_size=1, max_size=3), min_size=1, max_size=6).map(lambda parts: "_".join(parts))
_dec_int = st.one_of(
    st.tuples(st.sampled_from(['+', '-', '']), _dec_digits).map(lambda t: (t[0] + t[1]).lstrip('+')),
    st.tuples(st.sampled_from(['+', '-', '']), _dec_with_underscores).map(lambda t: (t[0] + t[1]).lstrip('+')),
    # Leading zeros allowed (contrary to TOML strict)
    st.sampled_from(['0', '007', '0001']).map(lambda s: s)
)

_hex_part = st.text(alphabet=st.sampled_from(list("0123456789abcdefABCDEF")), min_size=1, max_size=16)
_hex_int = st.one_of(
    st.tuples(st.sampled_from(['+', '-', '']), st.just('0x'), _hex_part).map(lambda t: t[0] + t[1] + t[2]),
    st.just('0xdeadbeef'),
)

_oct_part = st.text(alphabet=st.sampled_from(list("01234567")), min_size=1, max_size=16)
_oct_int = st.one_of(
    st.tuples(st.sampled_from(['+', '-', '']), st.just('0o'), _oct_part).map(lambda t: t[0] + t[1] + t[2]),
    st.just('0o755'),
)

_bin_part = st.text(alphabet=st.sampled_from(list("01")), min_size=1, max_size=32)
_bin_int = st.one_of(
    st.tuples(st.sampled_from(['+', '-','']), st.just('0b'), _bin_part).map(lambda t: t[0] + t[1] + t[2]),
    st.just('0b1010_1010'),
)

_integer = st.one_of(_dec_int, _hex_int, _oct_int, _bin_int)

# Floats including inf/nan and weird forms .5 and 1.
_float_regular = st.one_of(
    # normal floats with optional exponent
    st.builds(lambda s: s, st.text(alphabet=st.sampled_from(list("0123456789._")), min_size=1, max_size=12)).map(lambda s: s.replace('_', '')),  # crude
    # explicit forms:
    st.just("1."), st.just(".5"), st.just("1.0"), st.just("1e309"), st.just("-1e309")
)
_float_special = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
_float = st.one_of(_float_regular, _float_special)

# Boolean
_bool = st.sampled_from(['true', 'false'])

# Base (non-container) value strategy
_base_value = st.one_of(_integer, _bool)

# Use st.recursive to build arrays and inline tables that may nest deeply.
def _array_of_children(child):
    # Create arrays with comments, newlines, mixed types, trailing comma sometimes.
    items = st.lists(child, min_size=0, max_size=6)
    def mk_array(lst):
        # Insert comments and newlines randomly between items
        parts = []
        for i, it in enumerate(lst):
            # possibly add a comment before item
            if st.booleans().example():
                parts.append("# comment")
            parts.append(it)
            # comma between items
            if i != len(lst) - 1:
                parts.append(", ")
        # optionally trailing comma
        if st.booleans().example():
            if parts and not parts[-1].endswith(", "):
                parts.append(",")
            else:
                parts.append(",")
        inner = "".join(parts)
        return "[" + inner + "]"
    # Since we cannot call .example() in strategy building reliably, build via map
    return items.map(lambda lst: "[" + ", ".join(lst) + ("," if st.booleans().example() else "") + "]")

def _inline_table_of_children(child):
    # inline table: { key = value, ... } with optional trailing comma and newline injection sometimes
    kv = st.dictionaries(
        keys=st.one_of(_unquoted_key, _basic_string_key, _literal_key),
        values=child,
        min_size=0,
        max_size=6,
        allow_duplicates=True  # allow duplicates to test parser rejection
    )
    def mk_inline(d):
        parts = []
        for i, (k, v) in enumerate(d.items()):
            parts.append((k if isinstance(k, str) else k) + " = " + v)
        # maybe inject a newline inside (which the real parser rejects) for near-miss
        inner = ", ".join(parts)
        if st.booleans().example():
            # inject an illegal newline inside inline table occasionally
            inner = inner.replace(", ", ",\n", 1) if inner else inner
        trailing = "," if st.booleans().example() else ""
        return "{" + inner + trailing + "}"
    return kv.map(lambda d: mk_inline(d))

# The above functions used .example() which is not appropriate inside map constructions.
# Replace with strategies that build strings deterministically from drawn inputs instead.

# Rebuild array and inline-table constructors correctly using st.builds patterns.

@st.composite
def _array_strategy(draw, child):
    n = draw(st.integers(min_value=0, max_value=6))
    items = [draw(child) for _ in range(n)]
    # intersperse optional comments/newlines randomly
    pieces = []
    for i, it in enumerate(items):
        if draw(st.booleans()):
            pieces.append("# comment")
            if draw(st.booleans()):
                pieces.append("\n")
            else:
                pieces.append(" ")
        pieces.append(it)
        if i != len(items) - 1:
            pieces.append(", ")
    if draw(st.booleans()) and pieces:
        # trailing comma allowed
        pieces.append(",")
    inner = "".join(pieces)
    # occasionally add spaces/newlines to test multiline arrays
    if draw(st.booleans()):
        return "[" + inner + "]"
    else:
        # insert newlines randomly
        return "[\n" + inner + "\n]"

@st.composite
def _inline_table_strategy(draw, child):
    n = draw(st.integers(min_value=0, max_value=6))
    entries = []
    for _ in range(n):
        k = draw(st.one_of(_unquoted_key, _basic_string_key, _literal_key))
        v = draw(child)
        entries.append((k, v))
    parts = []
    for i, (k, v) in enumerate(entries):
        parts.append(k + " = " + v)
    inner = ", ".join(parts)
    # 50% chance to include trailing comma
    trailing = "," if draw(st.booleans()) else ""
    # 10% chance to include a newline inside (which should be rejected)
    if draw(st.integers(min_value=0, max_value=9)) == 0 and inner:
        # insert a newline after first comma if exists, else just put newline
        if ", " in inner:
            inner = inner.replace(", ", ",\n", 1)
        else:
            inner = inner + "\n"
    return "{" + inner + trailing + "}"

# Now construct recursive value strategy
def _value_recursive(max_leaves=256):
    # child param in st.recursive will be filled with the recursive strategy
    return st.recursive(
        _base_value,
        lambda child: st.one_of(
            _array_strategy(child),
            _inline_table_strategy(child)
        ),
        max_leaves=max_leaves
    )

# Key selectors: simple or dotted, including quoted simple keys
@st.composite
def _simple_key_strategy(draw):
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        return draw(_unquoted_key)
    elif choice == 1:
        return draw(_basic_string_key)
    else:
        return draw(_literal_key)

@st.composite
def _dotted_key_strategy(draw):
    # build dotted keys with 1..4 segments
    segments = draw(st.lists(_simple_key_strategy(), min_size=2, max_size=4))
    return ".".join(segments)

_key_strategy = st.one_of(_simple_key_strategy(), _dotted_key_strategy())

# Key-value line
@st.composite
def _key_value_expr(draw, value_strat):
    k = draw(_key_strategy)
    # Insert spaces around equals sometimes, or double equals as malformed
    eq = draw(st.sampled_from([' = ', '=', '  =  ', '==', ' =']))
    v = draw(value_strat)
    line = k + eq + v
    # Occasionally append trailing garbage stray token
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        line = line + " ???"
    return line

# Table header (standard) with possible malformed variants
@st.composite
def _table_expr(draw):
    k = draw(_dotted_key_strategy())
    choice = draw(st.integers(min_value=0, max_value=5))
    if choice == 0:
        # normal
        return "[" + k + "]"
    elif choice == 1:
        # missing closing bracket
        return "[" + k
    elif choice == 2:
        # double bracket wrongly
        return "[[" + k + "]"
    elif choice == 3:
        # extra closing bracket
        return "[" + k + "]]"
    else:
        # include comment on same line
        return "[" + k + "] # table comment"

# Array of tables (array table) header
@st.composite
def _array_table_expr(draw):
    k = draw(_dotted_key_strategy())
    if draw(st.booleans()):
        return "[[" + k + "]]"
    else:
        # malformed: missing one bracket or extra
        variants = ["[[" + k + "]", "[" + k + "]]", "[[" + k + "]]]"]
        return draw(st.sampled_from(variants))

# Comment-only expression
_comment_expr = st.one_of(
    st.just("# just a comment"),
    st.just("#"),
    st.builds(lambda s: "# " + s, st.text(min_size=0, max_size=40))
)

# Expression chooser
def _expression_strategy(value_strat):
    return st.one_of(
        _key_value_expr(value_strat),
        _key_value_expr(value_strat),
        _key_value_expr(value_strat),
        _table_expr(),
        _array_table_expr(),
        _comment_expr
    )

# Document builder: a sequence of expressions separated by newlines.
@st.composite
def _document(draw):
    # allow for deep nesting in arrays/inline tables by configuring leaves high
    max_leaves = draw(st.integers(min_value=4, max_value=256))
    value_strat = _value_recursive(max_leaves=max_leaves)
    expr_strat = _expression_strategy(value_strat)
    num_lines = draw(st.integers(min_value=0, max_value=12))
    lines = [draw(expr_strat) for _ in range(num_lines)]
    # Optionally inject duplicate keys to cover duplicate-key rejection
    if draw(st.booleans()) and len(lines) >= 1:
        # pick a previous key-value line if exists
        kv_lines = [ln for ln in lines if '=' in ln and not ln.strip().startswith('#')]
        if kv_lines:
            dup = draw(st.sampled_from(kv_lines))
            # insert duplicate at random position
            pos = draw(st.integers(min_value=0, max_value=len(lines)))
            lines.insert(pos, dup)
    # Optionally add table and then its subtables in reversed order (super-table after sub-table)
    if draw(st.booleans()):
        t = draw(_table_expr())
        stbl = t
        # add subtable later
        lines.append(t)
    # Occasionally omit final newline -> no trailing newline
    doc = "\n".join(lines)
    # Add a stray NUL? Must NEVER emit raw NUL; so avoid it.
    # But we can include the escaped Unicode NUL inside strings like \u0000.
    # Optionally append partial token to create near-valid-but-malformed inputs
    if draw(st.integers(min_value=0, max_value=9)) == 0:
        doc = doc + "\n" + "unterminated = \"oops"
    # Add final optional newline
    if draw(st.booleans()):
        doc = doc + "\n"
    return json.dumps(doc)

# Expose top-level strategy
strategy = _document()
```