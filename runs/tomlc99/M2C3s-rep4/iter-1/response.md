```python
from hypothesis import strategies as st
import json

# Control chars excluding NUL and excluding CR/LF to avoid accidental newlines where disallowed
_CONTROL_CHARS = ''.join(chr(i) for i in range(1, 32) if i not in (0, 10, 13))
_EXTRA_NON_ASCII = 'ñéöüø€あф'  # sample non-ASCII to ensure non-ASCII coverage
_PUNCT = "-_./:;@#%&*+?^=~"  # some punctuation useful inside strings/keys

# Basic building blocks
_unquoted_key = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=50
)

# Very-long key occasionally
_long_unquoted_key = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'),
        whitelist_characters='-_'
    ),
    min_size=1,
    max_size=10000
)

# Quoted key forms (no newlines inside quoted keys)
_basic_string_content = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'),
        whitelist_characters=_CONTROL_CHARS + _EXTRA_NON_ASCII + _PUNCT + r'\"\\'
    ),
    min_size=0,
    max_size=80
).map(lambda s: s.replace('\r', ''))  # avoid stray CR inside basic key strings

_literal_string_content = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'),
        whitelist_characters=_EXTRA_NON_ASCII + _PUNCT + r"'"  # single quote included to be sometimes present; composite will be quoted
    ),
    min_size=0,
    max_size=80
).map(lambda s: s.replace('\n', '').replace('\r', ''))

# Escape generators for double-quoted strings
_escape_seq = st.one_of(
    st.sampled_from(['\\n', '\\r', '\\t', '\\b', '\\f', '\\"', '\\\\', '\\/']),
    # Unicode escapes \uXXXX and \UXXXXXXXX
    st.builds(lambda h: '\\u' + h, st.text(alphabet='0123456789abcdefABCDEF', min_size=4, max_size=4)),
    st.builds(lambda h: '\\U' + h, st.text(alphabet='0123456789abcdefABCDEF', min_size=8, max_size=8)),
)

# Basic (double-quoted) string strategy: valid, with raw control characters included except NUL
_basic_string = st.one_of(
    # Valid basic string
    st.builds(lambda c: '"' + c + '"', _basic_string_content),
    # Multiline basic string
    st.builds(lambda c: '"""' + c + '"""', st.text(
        alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters=_CONTROL_CHARS + '\n' + _EXTRA_NON_ASCII + _PUNCT + r'\"\\'
        ),
        min_size=0,
        max_size=300
    )),
    # Unterminated string (near-malformed)
    st.builds(lambda c: '"' + c, _basic_string_content),
    # Include explicit escape sequences mixed into content
    st.builds(lambda a, b: '"' + a + b + '"',
              _basic_string_content,
              _escape_seq),
    # Invalid escape (near-malformed)
    st.builds(lambda c: '"' + c + '\\q' + c + '"', _basic_string_content),
).map(lambda s: s.replace('\x00', '\\u0000'))

# Literal strings (single-quoted)
_literal_string = st.one_of(
    st.builds(lambda c: "'" + c.replace("'", "''") + "'", _literal_string_content),
    st.builds(lambda c: "'''" + c + "'''", st.text(
        alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'),
            whitelist_characters=_EXTRA_NON_ASCII + _PUNCT + '\n' + _CONTROL_CHARS
        ),
        min_size=0,
        max_size=300
    )),
    # Unterminated literal
    st.builds(lambda c: "'" + c, _literal_string_content),
).map(lambda s: s.replace('\x00', '\\u0000'))

# Integer generators: decimal (with leading zeros sometimes), hex, octal, binary; include underscores and extremes
_dec_int = st.one_of(
    st.builds(lambda s: s, st.text(alphabet='0123456789', min_size=1, max_size=1)),  # small digit
    st.builds(lambda s: '+' + s, st.text(alphabet='0123456789', min_size=1, max_size=20)),
    st.builds(lambda s: '-' + s, st.text(alphabet='0123456789', min_size=1, max_size=20)),
    st.builds(lambda s: s, st.text(alphabet='0123456789_', min_size=1, max_size=40)),
    # leading zeros
    st.builds(lambda s: '00' + s, st.text(alphabet='0123456789', min_size=1, max_size=10)),
    # huge integer
    st.builds(lambda n: '9' * n, st.integers(min_value=20, max_value=1000)),
    # hex/octal/bin
    st.builds(lambda h: '0x' + h, st.text(alphabet='0123456789abcdefABCDEF_', min_size=1, max_size=40)),
    st.builds(lambda o: '0o' + o, st.text(alphabet='01234567_', min_size=1, max_size=40)),
    st.builds(lambda b: '0b' + b, st.text(alphabet='01_', min_size=1, max_size=40)),
)

# Floating point including special forms and edge cases
_float = st.one_of(
    st.builds(lambda s: s + '.', st.text(alphabet='0123456789', min_size=1, max_size=20)),  # 1.
    st.builds(lambda s: '.' + s, st.text(alphabet='0123456789', min_size=1, max_size=20)),  # .5
    st.builds(lambda m, e: m + 'e' + e, st.text(alphabet='0123456789._+-', min_size=1, max_size=10),
              st.text(alphabet='0123456789', min_size=1, max_size=4)),
    st.builds(lambda s: s + 'e' + str(309), st.text(alphabet='0123456789', min_size=1, max_size=10)),
    st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan']),
)

# Boolean
_bool = st.sampled_from(['true', 'false'])

# Date-time forms (no strict calendar validation)
_date = st.one_of(
    # FULL_DATE
    st.builds(lambda y, m, d: f"{y:04d}-{m:02d}-{d:02d}",
              st.integers(1900, 9999), st.integers(1, 12), st.integers(1, 31)),
    # LOCAL_DATE_TIME
    st.builds(lambda y, m, d, hh, mm, ss: f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}",
              st.integers(1900, 9999), st.integers(1, 12), st.integers(1, 31),
              st.integers(0, 23), st.integers(0, 59), st.integers(0, 59)),
    # OFFSET_DATE_TIME
    st.builds(lambda y, m, d, hh, mm, ss, off_sign, oh, om: f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}{off_sign}{oh:02d}:{om:02d}",
              st.integers(1900, 9999), st.integers(1, 12), st.integers(1, 31),
              st.integers(0, 23), st.integers(0, 59), st.integers(0, 59),
              st.sampled_from(['+', '-']), st.integers(0, 23), st.integers(0, 59)),
    # LOCAL_TIME
    st.builds(lambda hh, mm, ss: f"{hh:02d}:{mm:02d}:{ss:02d}",
              st.integers(0, 23), st.integers(0, 59), st.integers(0, 59)),
)

# Value base (atomic) -- doesn't recurse
value_base = st.one_of(
    _basic_string,
    _literal_string,
    _dec_int,
    _float,
    _bool,
    _date,
)

# Deferred strategy placeholder for recursion
value = st.deferred(lambda: _value_recursive)

# Helper to format inline table from list of (k, v) pairs; optionally malformed variants
def _format_inline_table(pairs, allow_trailing_comma=True, allow_newline_inside=False):
    # pairs is list of (k, v) strings
    items = []
    for k, v in pairs:
        items.append(f"{k} = {v}")
    inner = ", ".join(items)
    if allow_trailing_comma and (len(pairs) == 0 or st.randoms().example()):  # randomness only to vary; not deterministic here
        # This usage of st.randoms().example() is to occasionally add a trailing comma;
        # but we cannot call .example() in a strategy context reliably. Instead we'll add trailing comma in generator code.
        pass
    return "{" + inner + "}"

# Since we cannot rely on randoms.example inside strategies, make inline-table formatting within strategies.

# Make recursive extension: arrays and inline tables, and a deep-nesting special form
def _extend(inner):
    # Arrays: allow comments/newlines within (we'll model simply), allow trailing commas
    array_simple = st.builds(
        lambda elems, trailing: "[" + ("" if len(elems) == 0 else ", ".join(elems)) + ("," if trailing and len(elems) > 0 else "") + "]",
        st.lists(inner, min_size=0, max_size=6),
        st.booleans()
    )

    # Inline table: build list of key/value pairs; allow trailing comma; occasionally inject a newline inside to create a malformed inline table
    key_for_inline = st.one_of(
        _basic_string.map(lambda s: s),  # quoted form
        _literal_string.map(lambda s: s),
        _unquoted_key
    )

    inline_table = st.builds(
        lambda kvs, trailing, newline_inside: (
            "{" +
            ("\n".join(f"{k} = {v}" for k, v in kvs) if newline_inside else ", ".join(f"{k} = {v}" for k, v in kvs)) +
            ("," if trailing else "") +
            "}"
        ),
        st.lists(st.tuples(key_for_inline, inner), min_size=0, max_size=6),
        st.booleans(),  # trailing comma
        st.one_of(st.just(False), st.booleans())  # sometimes newline inside (malformed)
    )

    # Deep nesting: repeat brackets many times around an inner value (this concentrates deep nesting)
    deep_nesting = st.builds(
        lambda n, v: ("[" * n) + v + ("]" * n),
        st.integers(min_value=1, max_value=2048),
        inner
    )

    return st.one_of(array_simple, inline_table, deep_nesting)

# Build the recursive value strategy
_value_recursive = st.recursive(value_base, _extend, max_leaves=200)

# Key generators for dotted and simple keys, including quoted empty key
simple_key = st.one_of(
    _unquoted_key,
    _basic_string.map(lambda s: s),  # quoted basic string
    _literal_string.map(lambda s: s)
)

dotted_key = st.one_of(
    simple_key,
    st.builds(lambda parts: ".".join(parts),
              st.lists(simple_key, min_size=2, max_size=5))
)

# Key for table headers: usually a key (dotted allowed)
table_key = st.one_of(simple_key, dotted_key)

# Comments
_comment = st.builds(lambda t: "#" + t, st.text(alphabet=st.characters(max_codepoint=0x10FFFF), min_size=0, max_size=80))

# Key-value forms, including near-malformed variants (double '=', missing '=')
def _kv_line_strategy():
    # Key possibilities
    k = st.one_of(
        dotted_key,
        simple_key,
        _long_unquoted_key
    )
    # Malformed '=' variants
    eq = st.sampled_from([' = ', '=', '==', ' =', ' =  = '])
    # inline comment optionally
    trailing_comment = st.one_of(st.just(""), st.builds(lambda c: " " + c, _comment))
    return st.builds(lambda key, eqs, val, tc: f"{key}{eqs}{val}{tc}", k, eq, value, trailing_comment)

key_value_line = _kv_line_strategy()

# Table headers: standard and array of tables, with near-malformed cases (missing bracket, double bracket)
_standard_table = st.one_of(
    st.builds(lambda k: f"[{k}]", table_key),
    st.builds(lambda k: f"[[{k}]]", table_key),
    # malformed: missing closing bracket
    st.builds(lambda k: f"[{k}", table_key),
    # malformed: doubled bracket start
    st.builds(lambda k: f"[[[{k}]]", table_key),
)

# Stray garbage line
_garbage = st.text(alphabet=st.characters(max_codepoint=0x7F), min_size=1, max_size=40).map(lambda s: s + " ???")

# Expression: comment-only, key-value, table header, or garbage
expression = st.one_of(
    st.builds(lambda c: c, _comment),
    key_value_line,
    _standard_table,
    _garbage
)

# Document: zero or more expressions separated by newlines. Include CRLF occasionally.
_document_lines = st.lists(expression, min_size=0, max_size=20)

def _join_lines(lines, use_crlf=False, include_final_newline=False):
    sep = "\r\n" if use_crlf else "\n"
    text = sep.join(lines)
    if include_final_newline:
        text = text + sep
    return text

document = st.builds(
    lambda lines, use_crlf, final_nl: _join_lines(lines, use_crlf, final_nl),
    _document_lines,
    st.booleans(),  # use CRLF occasionally
    st.booleans()   # include final newline
).map(lambda s: s.replace('\x00', '\\u0000'))  # ensure no raw NUL bytes

# Top-level exported strategy
strategy = document
```