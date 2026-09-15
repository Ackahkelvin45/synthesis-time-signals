```python
from hypothesis import strategies as st
import json

# Helper primitives
_ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_digits = "0123456789"
_unquoted_chars = _ascii_letters + _digits + "-_"
# Characters allowed inside generated string content; exclude NUL (\x00)
_all_chars = st.characters(
    blacklist_characters="\x00",  # NEVER emit raw NUL
    min_codepoint=1,
    max_codepoint=0x10FFFF,
)

# Small probabilities for rare/edge behaviours
RARE = st.floats(min_value=0, max_value=1).map(lambda x: x < 0.1)

# Keys

unquoted_key = st.one_of(
    # typical short ascii key
    st.text(alphabet=st.sampled_from(list(_unquoted_chars)), min_size=1, max_size=20),
    # allow very long key edge-case
    st.just("k" * 10000),
    # keys that look like numbers or have leading zeros
    st.text(alphabet=st.sampled_from(list(_unquoted_chars)), min_size=1, max_size=50),
)

# Quoted keys - using the same string formers as values but ensure quoting is applied
def basic_quote(s: str) -> str:
    # Escape backslash and double-quote, keep raw control characters (except NUL)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'

def literal_quote(s: str) -> str:
    # Single-quoted literal; do not allow single-quote inside (but sometimes emit malformed)
    s = s.replace("'", "")  # strip single quotes for validity; malformed versions may keep them
    return "'" + s + "'"

quoted_key = st.one_of(
    st.text(alphabet=_all_chars, min_size=0, max_size=30).map(basic_quote),
    st.text(alphabet=_all_chars, min_size=0, max_size=30).map(literal_quote),
)

# Any key (simple or dotted)
simple_key = st.one_of(unquoted_key, quoted_key)
dotted_key = st.lists(simple_key, min_size=2, max_size=4).map(lambda parts: ".".join(parts))
key_strategy = st.one_of(simple_key, dotted_key)

# Strings (value forms)
# Basic (") string generator: include raw control characters (except NUL), escapes, unicode escapes, and sometimes malformed (unterminated)
def make_basic_string():
    # content may include backslash sequences or raw control chars
    content = st.text(alphabet=_all_chars, min_size=0, max_size=60)
    esc_forms = st.one_of(
        content.map(lambda s: s.replace("\\", "\\\\").replace('"', '\\"')),  # escaped quotes/backslashes
        content.map(lambda s: s + "\\n\\t\\u2603"),  # explicit escapes appended
        content.map(lambda s: s + "\\q"),  # invalid escape occasionally
    )
    # allow unterminated/malformed by dropping the trailing quote
    return st.one_of(
        esc_forms.map(lambda s: '"' + s + '"'),
        esc_forms.map(lambda s: '"' + s),  # unterminated
        # doubled delimiter
        esc_forms.map(lambda s: '""' + s + '"'),
    )

basic_string = make_basic_string()

# Multiline basic string: triple quotes; can include raw newlines; sometimes unterminated
ml_basic_string = st.one_of(
    st.text(alphabet=_all_chars, min_size=0, max_size=200).map(lambda s: '"""' + s + '"""'),
    st.text(alphabet=_all_chars, min_size=0, max_size=200).map(lambda s: '"""' + s),  # unterminated
)

# Literal (') string
def make_literal_string():
    content = st.text(alphabet=_all_chars, min_size=0, max_size=60).map(lambda s: s.replace("'", ""))
    return st.one_of(
        content.map(lambda s: "'" + s + "'"),
        # malformed: include single quote inside to provoke rejection
        st.text(alphabet=_all_chars, min_size=0, max_size=60).map(lambda s: "'" + s + "'").map(lambda s: s.replace("'", "'", 1)),
        # unterminated
        content.map(lambda s: "'" + s),
    )

literal_string = make_literal_string()

# Multiline literal
ml_literal_string = st.one_of(
    st.text(alphabet=_all_chars, min_size=0, max_size=200).map(lambda s: "'''" + s + "'''"),
    st.text(alphabet=_all_chars, min_size=0, max_size=200).map(lambda s: "'''" + s),  # unterminated
)

# Integers (decimal, hex, oct, bin), with underscores, leading zeros allowed
def dec_int_strat():
    # include extreme magnitudes, leading zeros, and underscores
    small = st.integers(min_value=-2**63, max_value=2**63 - 1)
    huge = st.one_of(st.integers(min_value=10**20, max_value=10**100), st.integers(min_value=0, max_value=10**50))
    decorated = st.one_of(small, huge).map(lambda i: str(i))
    # insert underscores occasionally
    def add_underscores(s: str) -> str:
        import random
        if len(s) > 3 and random.choice([True, False]):
            # insert underscores every 3 digits from the right
            sign = ""
            if s.startswith("-") or s.startswith("+"):
                sign = s[0]
                s = s[1:]
            parts = []
            while len(s) > 3:
                parts.insert(0, s[-3:])
                s = s[:-3]
            if s:
                parts.insert(0, s)
            return sign + "_".join(parts)
        return s
    return decorated.map(add_underscores)

hex_int = st.integers(min_value=0, max_value=2**128).map(lambda i: hex(i).replace("0x", "0x"))
oct_int = st.integers(min_value=0, max_value=2**120).map(lambda i: "0o" + oct(i)[2:])
bin_int = st.integers(min_value=0, max_value=2**120).map(lambda i: "0b" + bin(i)[2:])

integer_value = st.one_of(dec_int_strat(), hex_int, oct_int, bin_int)

# Floats: including '1.', '.5', inf, nan, extremes with exponent
def float_repr():
    special = st.sampled_from(["inf", "+inf", "-inf", "nan", "+nan", "-nan"])
    normal = st.one_of(
        st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, "g")),
        # force forms like '1.' and '.5'
        st.tuples(st.integers(min_value=0, max_value=1000), st.integers(min_value=0, max_value=1000)).map(lambda p: f"{p[0]}."),
        st.tuples(st.integers(min_value=0, max_value=1000), st.integers(min_value=1, max_value=999)).map(lambda p: f".{p[1]}"),
        # large exponent
        st.one_of(st.integers(min_value=1, max_value=9999), st.integers(min_value=100, max_value=1000)).map(lambda e: f"1e{e}"),
    )
    return st.one_of(special, normal)

float_value = float_repr()

# Boolean
bool_value = st.sampled_from(["true", "false"])

# Date/time forms; include calendar-invalid dates
def date_forms():
    year = st.integers(min_value=0, max_value=9999).map(lambda x: f"{x:04d}")
    month = st.integers(min_value=1, max_value=99).map(lambda x: f"{x:02d}")
    day = st.integers(min_value=1, max_value=99).map(lambda x: f"{x:02d}")
    hh = st.integers(min_value=0, max_value=23).map(lambda x: f"{x:02d}")
    mm = st.integers(min_value=0, max_value=59).map(lambda x: f"{x:02d}")
    ss = st.integers(min_value=0, max_value=59).map(lambda x: f"{x:02d}")
    frac = st.one_of(st.just(""), st.text(alphabet=st.sampled_from(list(_digits)), min_size=1, max_size=6).map(lambda s: "." + s))
    offset = st.one_of(st.just("Z"), st.tuples(st.sampled_from(["+", "-"]), hh, mm).map(lambda t: t[0] + t[1] + ":" + t[2]))
    # combine into different forms
    full_date = st.tuples(year, month, day).map(lambda t: "-".join(t))
    partial_time = st.tuples(hh, mm, ss, frac).map(lambda t: ":" .join([t[0], t[1], t[2]]) + (t[3] if t[3] else ""))
    offset_dt = st.tuples(full_date, st.sampled_from(["T", " "]), partial_time, offset).map(lambda t: f"{t[0]}{t[1]}{t[2]}{t[3]}")
    local_dt = st.tuples(full_date, st.sampled_from(["T", " "]), partial_time).map(lambda t: f"{t[0]}{t[1]}{t[2]}")
    local_date = full_date
    local_time = partial_time
    return st.one_of(offset_dt, local_dt, local_date, local_time)

date_value = date_forms()

# Base value strategy (non-recursive)
basic_value = st.one_of(
    basic_string,
    ml_basic_string,
    literal_string,
    ml_literal_string,
    integer_value,
    float_value,
    bool_value,
    date_value,
)

# Build recursive arrays and inline tables using st.recursive
# The recursive 'value' strategy will produce textual TOML value forms (strings)
def _array_builder(inner):
    # arrays may be multiline and contain comments/newlines and trailing commas
    def make_array(lst):
        # lst is a list of value-text strings
        import random
        pieces = []
        for v in lst:
            # optionally attach an inline comment
            if random.choice([True, False]):
                pieces.append(v + " # " + "c")
            else:
                pieces.append(v)
        # sometimes multiline
        if lst and random.choice([True, False]):
            body = ",\n  ".join(pieces)
            arr = "[\n  " + body + ",\n]"
        else:
            # optionally trailing comma
            trailing = "," if random.choice([True, False]) else ""
            body = ", ".join(pieces)
            arr = "[" + body + trailing + "]"
        return arr
    return st.lists(inner, min_size=0, max_size=6).map(make_array)

def _inline_table_builder(inner):
    # Inline tables must be single-line to be valid; but we also produce malformed ones with newlines
    def make_inline(kv_pairs):
        import random
        if not kv_pairs:
            return "{}"
        parts = []
        for k, v in kv_pairs:
            parts.append(f"{k} = {v}")
        trailing = "," if random.choice([True, False]) else ""
        # sometimes inject a newline inside (malformed)
        if random.choice([True, False, False]):
            # valid single-line
            return "{" + ", ".join(parts) + trailing + "}"
        else:
            # malformed with newline(s)
            return "{\n  " + ",\n  ".join(parts) + trailing + "\n}"
    # keys for inline tables must be simple (unquoted/unquoted) forms; reuse simple_key but ensure no newlines in keys
    inline_key = st.one_of(unquoted_key, quoted_key)
    return st.lists(st.tuples(inline_key, inner), min_size=0, max_size=6).map(make_inline)

# Use st.recursive to tie them together, allowing deep nesting (max_leaves large to permit high depth)
value = st.recursive(
    basic_value,
    lambda inner: st.one_of(_array_builder(inner), _inline_table_builder(inner)),
    max_leaves=4096,
)

# Key-value lines and tables, with occasional malformed variants
def kv_line():
    # key EQUALS value, optionally with comment. Introduce malformed variants sometimes.
    def make_kv(kv):
        k, v = kv
        import random
        comment = ""
        if random.choice([True, False, False]):
            comment = " # " + ("c" * random.randint(0, 20))
        # malformed variations
        mal = random.choice(["ok", "missing_value", "double_equals", "stray_token", "no_equals"])
        if mal == "ok":
            return f"{k} = {v}{comment}"
        elif mal == "missing_value":
            return f"{k} = {comment}"  # value missing
        elif mal == "double_equals":
            return f"{k} == {v}{comment}"
        elif mal == "stray_token":
            return f"{k} = {v} BAD{comment}"
        else:
            return f"{k} {v}{comment}"  # no equals
    return st.tuples(key_strategy, value).map(make_kv)

# Table headers
def table_header():
    std = st.tuples(key_strategy).map(lambda t: f"[{t[0]}]")
    arr = st.tuples(key_strategy).map(lambda t: f"[[{t[0]}]]")
    # malformed: missing closing bracket or doubled bracket
    malformed = st.one_of(
        st.tuples(key_strategy).map(lambda t: f"[{t[0]}"),
        st.tuples(key_strategy).map(lambda t: f"[[{t[0]}]"),
        st.tuples(key_strategy).map(lambda t: f"[{t[0]}]]"),
    )
    return st.one_of(std, arr, malformed)

comment_line = st.one_of(st.just(""), st.text(alphabet=st.sampled_from(list("#abcdefghijklmnopqrstuvwxyz ")), min_size=0, max_size=40).map(lambda s: "#" + s))

# Expression: key_value, table, or comment
expression = st.one_of(
    kv_line(),
    table_header(),
    st.just("")  # blank or comment-only handled separately
)

# Document: sequences of expressions separated by newlines. Include empty docs, comment-only docs, and docs with duplicate keys/tables.
def make_document(exprs):
    # exprs is a list of strings (some may be empty). We join with newlines, sometimes CRLF, sometimes no trailing newline.
    import random
    lines = []
    for e in exprs:
        if e == "":
            # produce either empty line or comment-only line
            if random.choice([True, False]):
                lines.append("")
            else:
                lines.append("# comment")
        else:
            lines.append(e)
    sep = "\r\n" if random.choice([True, False, False]) else "\n"
    doc = sep.join(lines)
    # occasional no trailing newline (document without trailing newline)
    if random.choice([True, False]):
        return doc
    else:
        return doc + sep

document = st.lists(expression, min_size=0, max_size=30).map(make_document)

# Final top-level strategy: include documents but also ensure that every value kind is reachable by biasing generation:
strategy = st.one_of(
    # typical document
    document,
    # tiny documents that exercise all value kinds
    st.just(
        # a compact hand-crafted document covering many kinds; include escapes and unicode escapes
        'a = "simple"\n'
        "b = 'lit'\n"
        'c = """multi\nline""" \n'
        "d = 007\n"
        "e = 1.\n"
        "f = .5\n"
        "g = +inf\n"
        "h = -nan\n"
        "i = 0xDEADBEEF\n"
        "j = 0o755\n"
        "k = 0b1010\n"
        "l = 1979-05-27T07:32:00Z\n"
        "m = [1, 2, [3, [4]]]\n"
        "n = {x = 1,}\n"
        "[table]\n"
        "[[arrtable]]\n"
        '# end'
    ),
    # produce a very deeply nested array (allowed up to 2048 levels)
    st.integers(min_value=1, max_value=2048).map(lambda depth: "[" * depth + "0" + "]" * depth),
    # produce a deeply nested inline-table chain: {a = {b = {c = 1}}}
    st.integers(min_value=1, max_value=300).map(
        lambda depth: "{a = " * depth + "1" + "}" * depth
    ),
    # generate documents from composed expression list
    document,
)
```