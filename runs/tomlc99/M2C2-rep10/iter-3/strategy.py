from hypothesis import strategies as st
import json

# Helper character sets (exclude NUL '\x00' because harness skips NUL-terminated inputs)
ASCII_BARE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
PRINTABLE_NO_QUOTE_BACKSLASH = ''.join(
    c for c in (chr(i) for i in range(0x20, 0x7F))
    if c not in {'"', '\\', '\n', '\r', '\x00'}
)
PRINTABLE_NO_SINGLEQUOTE = ''.join(
    c for c in (chr(i) for i in range(0x20, 0x7F))
    if c not in {"'", '\n', '\r', '\x00'}
)

# Basic building blocks
unquoted_key = st.text(alphabet=ASCII_BARE, min_size=1, max_size=20)

# Quoted keys reuse string strategies below; allow empty quoted key
def make_basic_string_factory(allow_unterminated=False, multiline=False, literal=False, multiline_literal=False):
    """
    Returns a strategy that yields a textual TOML string token (including quotes).
    Variants may include unterminated forms when allow_unterminated=True.
    """
    pieces = []

    # basic string "..."
    basic_content = st.text(alphabet=st.characters(blacklist_characters=['\x00', '"', '\\', '\n', '\r']),
                            min_size=0, max_size=50)
    # occasionally include explicit escape sequences like \n \t \u1234 \U0001F600 and literal \u0000
    escapes = st.one_of(
        st.just("\\n"),
        st.just("\\t"),
        st.just("\\r"),
        st.just("\\b"),
        st.just("\\f"),
        st.text(alphabet=st.characters(whitelist_categories=('Lu','Ll','Nd')), min_size=0, max_size=5).map(lambda s: "\\u" + ("{0:04x}".format(abs(hash(s)) % 0x10000))),
        st.text(alphabet=st.characters(whitelist_categories=('Lu','Ll','Nd')), min_size=0, max_size=5).map(lambda s: "\\U" + ("{0:08x}".format(abs(hash(s)) % 0x100000000))),
        st.just("\\\""),
        st.just("\\\\"),
        st.just("\\/"),
    )

    # mix content with escapes
    mixed_basic = st.lists(st.one_of(basic_content, escapes), min_size=0, max_size=8).map(''.join)

    if not multiline and not literal and not multiline_literal:
        closed = mixed_basic.map(lambda s: '"' + s + '"')
        pieces.append(closed)
        if allow_unterminated:
            pieces.append(mixed_basic.map(lambda s: '"' + s))  # unterminated
    # multiline basic """..."""
    if multiline:
        # allow newlines, but avoid the terminating triple quotes sequence
        ml_content = st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=200).map(lambda s: s.replace('"""', '""'))  # simple avoidance
        pieces.append(ml_content.map(lambda s: '"""' + s + '"""'))
        if allow_unterminated:
            pieces.append(ml_content.map(lambda s: '"""' + s))  # unterminated

    # literal string '...'
    if literal:
        lit_content = st.text(alphabet=st.characters(blacklist_characters=['\x00', "'", '\n', '\r']), min_size=0, max_size=80)
        pieces.append(lit_content.map(lambda s: "'" + s + "'"))
        if allow_unterminated:
            pieces.append(lit_content.map(lambda s: "'" + s))  # unterminated

    # multiline literal '''...'''
    if multiline_literal:
        mll_content = st.text(alphabet=st.characters(blacklist_characters=['\x00']), min_size=0, max_size=300).map(lambda s: s.replace("'''", "''"))
        pieces.append(mll_content.map(lambda s: "'''" + s + "'''"))
        if allow_unterminated:
            pieces.append(mll_content.map(lambda s: "'''" + s))  # unterminated

    return st.one_of(*pieces)

basic_string = make_basic_string_factory(allow_unterminated=True, multiline=False)
ml_basic_string = make_basic_string_factory(allow_unterminated=True, multiline=True)
literal_string = make_basic_string_factory(allow_unterminated=True, literal=True)
ml_literal_string = make_basic_string_factory(allow_unterminated=True, multiline_literal=True)

quoted_key_basic = basic_string.map(lambda s: s)  # BASIC_STRING tokens are valid quoted keys
quoted_key_literal = literal_string.map(lambda s: s)
quoted_key = st.one_of(quoted_key_basic, quoted_key_literal)

simple_key = st.one_of(unquoted_key, quoted_key)
dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(lambda parts: '.'.join(part if part.startswith(("'", '"')) else part for part in parts))

key_strategy = st.one_of(simple_key, dotted_key)

# Integer strategies (decimal, hex, octal, bin) as textual forms with underscores and extremes
def decimal_text():
    # allow leading zeros like 007, negative sign, underscores
    small = st.integers(min_value=-10**6, max_value=10**6).map(str)
    leading_zeros = st.integers(min_value=0, max_value=9999).map(lambda n: str(n).zfill(st.integers(min_value=1, max_value=5).example() if False else max(1, min(4, len(str(n))) )))  # fallback; but .example() not allowed
    # simpler: build decimal strings with optional sign and underscores
    digs = st.text(alphabet='0123456789', min_size=1, max_size=40)
    with_underscores = st.lists(digs, min_size=1, max_size=5).map(lambda parts: '_'.join(parts))
    with_sign = st.one_of(with_underscores, digs).map(lambda s: s)
    signed = st.one_of(with_sign, with_sign.map(lambda s: '+' + s), with_sign.map(lambda s: '-' + s))
    # allow leading zero variants explicitly
    leading_zero_variant = st.one_of(st.just('0'), st.text(alphabet='0123456789', min_size=1, max_size=8)).map(lambda s: s)
    return st.one_of(signed, leading_zero_variant)

hex_int = st.builds(lambda s: '0x' + s, st.text(alphabet='0123456789abcdefABCDEF', min_size=1, max_size=40).map(lambda s: '_'.join([s[i:i+2] for i in range(0, len(s), 2)])))
oct_int = st.builds(lambda s: '0o' + s, st.text(alphabet='01234567', min_size=1, max_size=40).map(lambda s: '_'.join([s[i:i+2] for i in range(0, len(s), 2)])))
bin_int = st.builds(lambda s: '0b' + s, st.text(alphabet='01', min_size=1, max_size=60).map(lambda s: '_'.join([s[i:i+4] for i in range(0, len(s), 4)])))

dec_int = decimal_text()

integer_str = st.one_of(dec_int, hex_int, oct_int, bin_int)

# Float strategies including inf/nan, formats like 1., .5, exponent extremes
def float_text():
    basic_frac = st.one_of(
        # 1., 123.
        st.text(alphabet='0123456789', min_size=1, max_size=40).map(lambda s: s + '.'),
        # .5, .0001
        st.text(alphabet='0123456789', min_size=1, max_size=40).map(lambda s: '.' + s),
        # normal with optional exponent
        st.tuples(st.text(alphabet='0123456789', min_size=1, max_size=10),
                  st.text(alphabet='0123456789', min_size=1, max_size=5)).map(lambda t: t[0] + '.' + t[1]),
    )
    exponent = st.one_of(st.just('e+309'), st.just('e-100'), st.text(alphabet='eE+-0123456789', min_size=1, max_size=6))
    with_exp = st.one_of(
        basic_frac.map(lambda s: s + 'e10'),
        st.tuples(basic_frac, exponent).map(lambda t: t[0] + t[1])
    )
    inf_nan = st.sampled_from(['inf', '+inf', '-inf', 'nan', '+nan', '-nan'])
    return st.one_of(with_exp, basic_frac, inf_nan)

float_str = float_text()

# Boolean
bool_str = st.sampled_from(['true', 'false'])

# Date-time forms (allow calendar-invalid dates per notes)
def date_time_text():
    year = st.integers(min_value=0, max_value=9999).map(lambda y: "{:04d}".format(y))
    month = st.integers(min_value=1, max_value=12).map(lambda m: "{:02d}".format(m))
    day = st.integers(min_value=1, max_value=31).map(lambda d: "{:02d}".format(d))
    hour = st.integers(min_value=0, max_value=23).map(lambda h: "{:02d}".format(h))
    minute = st.integers(min_value=0, max_value=59).map(lambda m: "{:02d}".format(m))
    second = st.integers(min_value=0, max_value=59).map(lambda s: "{:02d}".format(s))
    secfrac = st.one_of(st.just(''), st.builds(lambda s: '.' + s, st.text(alphabet='0123456789', min_size=1, max_size=6)))
    offset = st.one_of(st.just('Z'), st.builds(lambda h, m, sign: sign + "{:02d}:{:02d}".format(h, m),
                                               st.integers(0, 23), st.integers(0, 59), st.sampled_from(['+','-'])))
    # Compose different forms
    offset_dt = st.tuples(year, month, day, st.sampled_from(['T',' ']), hour, minute, second, secfrac, offset).map(
        lambda t: "{}-{}-{}{}{:02d}:{:02d}:{:02d}{}{}".format(t[0], t[1], t[2], t[3], int(t[4]), int(t[5]), int(t[6]), t[7], t[8])
    )
    local_dt = st.tuples(year, month, day, st.sampled_from(['T',' ']), hour, minute, second, secfrac).map(
        lambda t: "{}-{}-{}{}{:02d}:{:02d}:{:02d}{}".format(t[0], t[1], t[2], t[3], int(t[4]), int(t[5]), int(t[6]), t[7])
    )
    local_date = st.tuples(year, month, day).map(lambda t: "{}-{}-{}".format(t[0], t[1], t[2]))
    local_time = st.tuples(hour, minute, second, secfrac).map(lambda t: "{:02d}:{:02d}:{:02d}{}".format(int(t[0]), int(t[1]), int(t[2]), t[3]))
    return st.one_of(offset_dt, local_dt, local_date, local_time)

date_time_str = date_time_text()

# Base value strategy
base_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    integer_str,
    integer_str,
    integer_str,
    integer_str,
    integer_str,
    float_str,
    bool_str,
    date_time_str,
)

# Comments and whitespace tokens
comment_text = st.text(alphabet=st.characters(blacklist_characters=['\x00', '\n', '\r']), min_size=0, max_size=80)
comment = comment_text.map(lambda s: "# " + s if s != "" else "#")
opt_comment = st.one_of(st.just(""), comment)
newline = st.sampled_from(["\n", "\r\n"])

# Recursive arrays and inline tables using st.recursive
def array_builder(children):
    # elements optionally separated by commas, with optional trailing comma; allow comments/newlines between
    elem = st.one_of(children, comment.map(lambda c: c), comment.map(lambda c: c))
    elems = st.lists(elem, min_size=0, max_size=6)
    def make_array(lst):
        # join with commas, allow random spaces, include trailing comma sometimes
        if not lst:
            inner = ""
        else:
            inner = ", ".join(lst)
            # maybe add trailing comma
            if st.booleans().example():
                inner = inner + ","
        return "[" + inner + "]"
    return elems.map(lambda lst: "[" + (", ".join(lst) if lst else "") + ("," if (len(lst)>0 and (hash("".join(lst)) & 1)==0) else "") + "]")

def inline_table_builder(children):
    # inline table: { key = value (, key = value)* ,? }
    keyvals = st.lists(st.tuples(key_strategy, children), min_size=0, max_size=6)
    def build_inline(kvs):
        parts = []
        for k, v in kvs:
            # k might be quoted with quotes; ensure spacing around =
            parts.append(f"{k} = {v}")
        inner = ", ".join(parts)
        # optionally trailing comma (allowed)
        if parts and (hash(inner) & 1):
            inner = inner + ","
        # occasionally insert newline inside inline table to create near-invalid case
        if (hash(inner) & 7) == 3:
            inner = inner.replace(", ", "," + "\n")
        return "{" + inner + "}"
    return keyvals.map(build_inline)

# Compose recursive value strategy (arrays and inline tables may contain children recursively)
value_strategy = st.recursive(
    base_value,
    lambda children: st.one_of(
        array_builder(children),
        inline_table_builder(children)
    ),
    max_leaves=2048
)

# Key-value line generator with some near-malformed variants
def key_value_line():
    # variants: normal, doubled equals, missing equals, stray token, extra spaces, duplicate keys allowed
    normal = st.tuples(key_strategy, value_strategy, opt_comment).map(lambda t: f"{t[0]} = {t[1]}" + ((" " + t[2]) if t[2] else ""))
    doubled_eq = st.tuples(key_strategy, value_strategy, opt_comment).map(lambda t: f"{t[0]} == {t[1]}" + ((" " + t[2]) if t[2] else ""))
    missing_eq = st.tuples(key_strategy, value_strategy, opt_comment).map(lambda t: f"{t[0]} {t[1]}" + ((" " + t[2]) if t[2] else ""))
    stray = st.tuples(key_strategy, value_strategy, st.text(alphabet="!@#$%^&*()", min_size=1, max_size=4)).map(lambda t: f"{t[0]} = {t[1]} {t[2]}")
    # allow duplicates by simply not checking uniqueness at generation time
    return st.one_of(normal, doubled_eq, missing_eq, stray)

# Table lines
standard_table = key_strategy.map(lambda k: "[" + k + "]")
array_table = key_strategy.map(lambda k: "[[" + k + "]]")
table_line = st.one_of(standard_table, array_table)

# Expression: key_value, table, or comment-only line
expression = st.one_of(key_value_line(), table_line, comment.map(lambda c: c), st.just(""))

# Document construction: sequence of expressions separated by newlines, allow CRLF and optional trailing newline
def document_builder():
    lines = st.lists(expression, min_size=0, max_size=30)
    def assemble(lines_list):
        # Filter some empty expressions optionally to produce blank or comment-only documents
        sep_choices = ["\n", "\r\n"]
        sep = sep_choices[hash("".join(lines_list)) % len(sep_choices)]
        doc = sep.join(lines_list)
        # occasionally append a comment-only trailing line without newline to get no trailing newline document
        if (len(lines_list) > 0) and ((hash(doc) & 3) == 0):
            return doc  # leave as-is (no trailing newline)
        # otherwise maybe end with newline
        if (hash(doc) & 1):
            return doc + sep
        return doc
    return lines.map(assemble)

# Final top-level strategy
strategy = document_builder()