```python
from hypothesis import strategies as st
import json

# Helper character sets (avoid raw NUL \x00)
_ascii_printable = [chr(c) for c in range(32, 127)]
# Exclude quotes and backslash for BASIC_STRING raw chars (they must be escaped)
_basic_ok = [c for c in _ascii_printable if c not in ('"', '\\', '\n', '\r')]
# For LITERAL_STRING exclude single quote and newlines
_literal_ok = [c for c in _ascii_printable if c not in ("'", '\n', '\r')]

# Control bytes allowed inside basic strings (except NUL, LF, CR)
_control_bytes = [chr(i) for i in range(1, 32) if i not in (10, 13, 0)]

# Simple small helpers
def _rnd_underscore_int(min_digits=1, max_digits=6, allow_leading_zero=True):
    # returns st of decimal-like ints with optional underscores and optional leading zeros
    def build(n):
        # generate segments and join with underscores
        return st.lists(st.text(alphabet="0123456789", min_size=1, max_size=1),
                        min_size=n, max_size=n).map(lambda parts: "_".join(parts))
    return st.integers(min_value=min_digits, max_value=max_digits).flatmap(build)

# Basic escaped sequences for BASIC_STRING (as literal backslash sequences)
_basic_escapes = st.sampled_from(['\\n', '\\t', '\\r', '\\b', '\\f', '\\/', '\\\\', '\\"'])
_unicode_escape_u = st.integers(0, 0xFFFF).map(lambda i: '\\u%04x' % i)
_unicode_escape_U = st.integers(0, 0xFFFFFFFF).map(lambda i: '\\U%08x' % i)
_invalid_escape = st.sampled_from(['\\q', '\\z'])

# BASIC_STRING content pieces: raw safe characters, control bytes, escapes, unicode escapes, invalid escapes
basic_content_piece = st.one_of(
    st.sampled_from(_basic_ok),
    st.sampled_from(_control_bytes),
    _basic_escapes,
    _unicode_escape_u,
    _unicode_escape_U,
    _invalid_escape
)

# LITERAL_STRING content pieces: no escaping, no newlines, allow non-ascii
literal_content_piece = st.one_of(
    st.sampled_from(_literal_ok),
    st.text(min_size=1, max_size=1).filter(lambda ch: ch not in ("'", '\n', '\r', '\x00'))
)

# Multi-line content can include newlines and a larger variety
ml_basic_piece = st.one_of(
    st.sampled_from(_basic_ok + _control_bytes),
    _basic_escapes,
    _unicode_escape_u,
    _unicode_escape_U
)
ml_literal_piece = st.one_of(
    st.sampled_from(_literal_ok),
    st.text(min_size=1, max_size=1).filter(lambda ch: ch not in ("'", '\x00'))
)

# Strategies for four kinds of TOML strings, including malformed variants
basic_string = st.lists(basic_content_piece, min_size=0, max_size=24).map(''.join).flatmap(
    lambda s: st.one_of(
        st.just('"' + s + '"'),
        # Unterminated or doubled delimiter near-miss
        st.just('"' + s),
        st.just('"' + s + '""')  # doubled closing quote, stray token
    )
)

ml_basic_string = st.lists(ml_basic_piece, min_size=0, max_size=40).map(''.join).flatmap(
    lambda s: st.one_of(
        st.just('"""' + s + '"""'),
        st.just('"""' + s),          # unterminated
        st.just('"""' + s + '""')    # malformed trailing mismatch
    )
)

literal_string = st.lists(literal_content_piece, min_size=0, max_size=24).map(''.join).flatmap(
    lambda s: st.one_of(
        st.just("'" + s + "'"),
        st.just("'" + s),            # unterminated
        st.just("'" + s + "''")      # stray token
    )
)

ml_literal_string = st.lists(ml_literal_piece, min_size=0, max_size=40).map(''.join).flatmap(
    lambda s: st.one_of(
        st.just("'''" + s + "'''"),
        st.just("'''" + s),          # unterminated
    )
)

string_value = st.one_of(basic_string, ml_basic_string, literal_string, ml_literal_string)

# Integers: decimal (with optional leading zeros and underscores), hex, octal, binary, extremes
def decimal_ints():
    # normal decimal, leading zeros sometimes
    digits = st.text(alphabet="0123456789", min_size=1, max_size=20)
    with_unders = st.lists(st.text(alphabet="0123456789", min_size=1, max_size=4),
                           min_size=1, max_size=5).map(lambda parts: "_".join(parts))
    leading_zero = st.booleans().flatmap(lambda z: st.just("0" + "0" * st.integers(0, 5).example()) if z else digits)
    # compose various forms and signs
    return st.one_of(
        digits,
        with_unders,
        # leading zeros explicitly
        st.just("00") + st.text(alphabet="0123456789", min_size=0, max_size=18),  # not typical but allows leading zeros
        # extreme long integer
        st.just("1" * 1000)
    ).map(lambda s: s).flatmap(
        lambda s: st.one_of(st.just(s), st.just("+" + s), st.just("-" + s))
    )

hex_int = st.integers(min_value=0, max_value=0xFFFFFFFFFFFF).map(lambda i: hex(i).replace('0x', '0x') )
oct_int = st.integers(min_value=0, max_value=0o7777777777).map(lambda i: oct(i).replace('0o', '0o'))
bin_int = st.integers(min_value=0, max_value=0b111111111111).map(lambda i: bin(i).replace('0b', '0b'))

# Allow oct/hex/bin with underscores inserted occasionally
def spaced_base_int(prefix, digits_alphabet, max_len=12):
    def make():
        # randomly make segments and join with underscores
        return st.lists(st.sampled_from(list(digits_alphabet)), min_size=1, max_size=max_len).map(lambda chars: ''.join(chars))
    return make().map(lambda body: prefix + body).flatmap(
        lambda s: st.one_of(st.just(s), st.just(s + '_' + s[:min(len(s), 3)]))
    )

hex_int = spaced_base_int('0x', '0123456789abcdefABCDEF', max_len=8)
oct_int = spaced_base_int('0o', '01234567', max_len=10)
bin_int = spaced_base_int('0b', '01', max_len=16)

integer_value = st.one_of(
    decimal_ints(),
    hex_int,
    oct_int,
    bin_int
)

# Floats: many variants including inf/nan, 1., .5, exponent extremes
def float_variants():
    normal = st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map(''.join)
    frac = st.lists(st.sampled_from("0123456789"), min_size=1, max_size=6).map(''.join)
    exp = st.integers(min_value=-400, max_value=400).map(lambda e: 'e' + str(e))
    return st.one_of(
        # typical float
        st.tuples(normal, st.just('.'), frac, st.one_of(st.just(''), exp)).map(lambda t: ''.join(t)),
        # missing digit after dot
        st.tuples(normal, st.just('.')).map(lambda t: ''.join(t)),
        # missing leading digit
        st.tuples(st.just('.'), frac).map(lambda t: ''.join(t)),
        # exponent only
        st.tuples(normal, exp).map(lambda t: ''.join(t)),
        # extremes
        st.just('1e309'),
        st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
    )

float_value = float_variants()

bool_value = st.sampled_from(['true', 'false'])

# Dates: full date, local time, local date-time, offset date-time; calendar-invalid allowed
def date_piece():
    y = st.integers(0, 9999).map(lambda i: "%04d" % i)
    m = st.integers(1, 12).map(lambda i: "%02d" % i)
    d = st.integers(1, 31).map(lambda i: "%02d" % i)
    hh = st.integers(0, 23).map(lambda i: "%02d" % i)
    mm = st.integers(0, 59).map(lambda i: "%02d" % i)
    ss = st.integers(0, 60).map(lambda i: "%02d" % i)  # 60 allowed (leap)
    frac = st.one_of(st.just(''), st.integers(1, 999999999).map(lambda i: '.' + str(i)))
    offset = st.one_of(st.just('Z'), st.tuples(st.sampled_from(['+','-']), hh, st.just(':'), mm).map(lambda t: ''.join(t)))
    sep = st.sampled_from(['T', 't', ' '])
    return st.one_of(
        # offset datetime: YYYY-MM-DD T hh:mm:ss[.frac] (Z or ±HH:MM)
        st.tuples(y, st.just('-'), m, st.just('-'), d, st.just(' '), st.just('T')).map(lambda _: "1970-01-01"),  # placeholder
        st.tuples(y, st.just('-'), m, st.just('-'), d, sep, hh, st.just(':'), mm, st.just(':'), ss, frac, offset).map(lambda t: ''.join(t)),
        # local datetime (no offset)
        st.tuples(y, st.just('-'), m, st.just('-'), d, sep, hh, st.just(':'), mm, st.just(':'), ss, frac).map(lambda t: ''.join(t)),
        # local date
        st.tuples(y, st.just('-'), m, st.just('-'), d).map(lambda t: ''.join(t)),
        # local time
        st.tuples(hh, st.just(':'), mm, st.just(':'), ss, frac).map(lambda t: ''.join(t))
    )

date_value = date_piece()

# A base non-recursive value strategy (strings, numbers, bools, dates)
base_value = st.one_of(
    string_value,
    integer_value,
    float_value,
    bool_value,
    date_value
)

# Inline table generator (no newlines ideally; but sometimes emit malformed newline to test rejection)
def inline_table_builder(value_strategy):
    # Build one or more key = value pairs, possibly with trailing comma. Avoid newlines in values for valid inline tables.
    key_simple = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20)
    quoted_key_basic = string_value  # may include newlines; we'll filter below for valid ones
    # choose values but for valid inline table avoid newlines by filtering small set
    safe_value = st.one_of(
        # single-line basic/literal string
        st.lists(basic_content_piece, min_size=0, max_size=10).map(''.join).map(lambda s: '"' + s + '"'),
        st.lists(literal_content_piece, min_size=0, max_size=10).map(''.join').map(lambda s: "'" + s + "'"),
        integer_value,
        float_value,
        bool_value,
        date_value
    )
    # sometimes intentionally produce newline inside inline table (malformed)
    def make_pair():
        return st.tuples(st.one_of(key_simple, quoted_key_basic), st.one_of(safe_value, value_strategy)).map(lambda kv: kv[0] + " = " + kv[1])
    # Compose 0..4 pairs (allow empty inline table)
    pairs = st.lists(make_pair(), min_size=0, max_size=4)
    return pairs.map(lambda ps: "{ " + (", ".join(ps) + ("," if st.booleans().example() else "")) + " }").map(lambda s: s)

# Array builder that can recurse (arrays contain arbitrary values including nested arrays/inline tables).
def array_builder(child_strategy):
    # elements: allow comments/newlines between elements; represent comments as "# ...\n"
    comment_piece = st.one_of(st.just(""), st.just(" # " + "x"*5))
    # lists of elements up to small size
    elems = st.lists(child_strategy, min_size=0, max_size=6)
    def mk(elems_list):
        if not elems_list:
            inner = ""
        else:
            # randomly add trailing comma
            trailing = st.booleans().example()
            inner = ", ".join(elems_list) + ("," if trailing else "")
        return "[" + inner + "]"
    return elems.map(mk)

# Now a recursive value strategy where arrays may contain nested arrays/inline tables
recursive_values = st.deferred(lambda: st.recursive(
    base_value,
    lambda s: st.one_of(
        array_builder(s),
        inline_table_builder(base_value)  # keep inline tables non-recursive to reduce newlines inside them
    ),
    max_leaves=50
))

# Deep nesting helpers: explicit deep arrays and deep inline tables up to ~2048 levels
deep_array = st.integers(min_value=0, max_value=2048).map(lambda d: ("[" * d) + "1" + ("]" * d))
# Nested inline tables built as {a={a={... key=1 ...}}}
def deep_inline_table_str(depth):
    # produce nested inline tables like {a = {a = { ... key = 1 } } }
    if depth <= 0:
        return "{a = 1}"
    inner = "{a = 1}"
    for _ in range(depth):
        inner = "{a = " + inner + "}"
    return inner

deep_inline_table = st.integers(min_value=0, max_value=800).map(deep_inline_table_str)

# Keys: unquoted, quoted, dotted
unquoted_key = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20)
# non-ASCII bare keys (should be rejected by parser) to include as edge-case
nonascii_bare_key = st.text(min_size=1, max_size=10).filter(lambda s: any(ord(c) > 127 for c in s))
quoted_key = st.one_of(
    st.lists(basic_content_piece, min_size=0, max_size=10).map(''.join).map(lambda s: '"' + s + '"'),
    st.lists(literal_content_piece, min_size=0, max_size=10).map(''.join).map(lambda s: "'" + s + "'")
)
dotted_key = st.lists(st.one_of(unquoted_key, quoted_key), min_size=2, max_size=5).map(lambda parts: ".".join(parts))

simple_key = st.one_of(unquoted_key, quoted_key)

key_strategy = st.one_of(simple_key, dotted_key, nonascii_bare_key)

# Key/value line builder
def key_value_builder(value_strat):
    # occasionally produce duplicate keys by repeating the same key twice in the document builder
    def kv():
        return st.tuples(key_strategy, value_strat).map(lambda t: t[0] + " = " + t[1])
    return kv()

# Table headers: [key] or [[key]]; include malformed header (missing bracket/doubled)
table_header = st.tuples(key_strategy).map(lambda t: "[" + t[0] + "]")
array_table_header = st.tuples(key_strategy).map(lambda t: "[[" + t[0] + "]]")
malformed_table = st.one_of(
    key_strategy.map(lambda k: "[" + k),         # missing closing bracket
    key_strategy.map(lambda k: k + "]"),         # missing opening
    key_strategy.map(lambda k: "[[" + k + "]"),  # doubled mismatch
)

# Comment lines and blank lines
comment_line = st.one_of(st.just(""), st.text(alphabet="# " + "abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=30).map(lambda s: "#" + s))
blank_line = st.just("")

# Expression: key_value, table header, array table header, comment
def expression_builder(val_strat):
    return st.one_of(
        key_value_builder(val_strat),
        table_header,
        array_table_header,
        malformed_table,
        comment_line
    )

# Document builder: list of expressions separated by newlines; allow documents with no trailing newline.
def document_builder(val_strat):
    # expressions per document
    exprs = st.lists(expression_builder(val_strat), min_size=0, max_size=12)
    # join with CRLF or LF sometimes; include optional trailing newline
    def mk(es):
        sep = st.sampled_from(["\n", "\r\n"]).example()
        # Filter empty strings not to produce stray separators within inline tables by accident
        body = sep.join(es)
        if st.booleans().example():
            return body  # no trailing newline
        else:
            return body + sep
    return exprs.map(mk)

# Special near-valid-but-malformed cases: stray token, doubled delimiter, missing delimiter, unterminated string, stray token in middle
def malformed_variants(val_strat):
    base_doc = document_builder(val_strat)
    stray = st.sampled_from(["]", "[", "=", "==", ",,", "}}", "..."])
    return st.one_of(
        base_doc.map(lambda s: s + "\n" + stray.example()),
        base_doc.map(lambda s: s.replace("=", "==", 1) if "=" in s else s + "\nfoo = = 1"),
        # inject unterminated string: key = "abc (no closing)
        st.tuples(unquoted_key, st.just('"unterminated')).map(lambda t: t[0] + " = " + t[1]),
    )

# Top-level strategy: combine many modes, including deep nesting and malformed inputs
strategy = st.one_of(
    # Regular documents with recursive values (arrays, inline tables, strings, numbers etc.)
    document_builder(recursive_values),
    # Small focused documents to hit many value kinds: ensure presence of all value kinds in one doc
    st.just(
        '\n'.join([
            's_basic = "hello\\nworld\\t\\u263A"',                    # basic w/ escapes
            "s_literal = 'raw\\x01\\x02'",                            # literal (raw control bytes allowed)
            's_ml_basic = """multi\nline\nstring"""',
            "s_ml_literal = '''multi\nraw\nstring'''",
            "i_dec = 007",                                            # leading zeros accepted by parser
            "i_hex = 0xFF_FF",
            "i_oct = 0o12_34",
            "i_bin = 0b1010_0101",
            "f1 = 1.",                                                # float w/o fractional part
            "f2 = .5",                                                # float w/o leading digit
            "f3 = 1e309",
            "infv = inf",
            "n = nan",
            "b = true",
            "dt1 = 1979-05-27T07:32:00Z",
            "dt2 = 1979-05-27 07:32:00",                              # space separator, local datetime
            "dt3 = 1979-02-30",                                       # calendar-invalid accepted
            "arr_empty = []",
            "arr_mixed = [1, \"two\", 3.0, true, 1979-05-27]",
            "inline_empty = {}",
            "inline_trailing = {a = 1,}",                             # trailing comma allowed
            "[t]",                                                    # table header
            "[[a]]"                                                   # array table
        ])
    ),
    # Deep array nesting explicit (stress recursion up to ~2048)
    deep_array,
    # Deep nested inline tables
    deep_inline_table,
    # malformed variants to exercise near-valid-but-bad inputs
    malformed_variants(recursive_values),
    # Documents that intentionally include duplicate keys/tables to test rejection path
    st.tuples(unquoted_key, base_value).map(lambda kv: kv[0] + " = " + kv[1] + "\n" + kv[0] + " = " + kv[1]),
    # A mostly empty/ comment-only or tiny documents
    st.one_of(st.just(""), st.just("# only comment\n"), st.just("\n"))
).map(lambda s: s if isinstance(s, str) else str(s))
```