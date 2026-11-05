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


def _full_doc():
    return st.one_of(
        _document(),
        _malformed(),
        _deep_document(),
        _duplicate_doc(),
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


# ---------- improved: structured multi-section documents & targeted edge cases ----------

def _section_doc():
    """Build a document with a mix of tables, array-tables, keyvals and comments
    that exercise header re-entry, sub-table nesting, and ordering rules."""
    def render(parts):
        return "\n".join(parts)

    header = st.one_of(
        st.just("[t]"),
        st.just("[[t]]"),
        st.tuples(_key()).map(lambda t: "[" + t[0] + "]"),
        st.tuples(_key()).map(lambda t: "[[" + t[0] + "]]"),
        st.tuples(_key(), _key()).map(lambda t: "[" + t[0] + "." + t[1] + "]"),
    )
    body = st.lists(
        st.one_of(
            _keyval_line(1),
            _comment(),
            st.just(""),
        ),
        max_size=4,
    )
    return st.tuples(header, body).map(lambda t: _section_render(t[0], t[1]))


def _section_render(h, body):
    return h + "\n" + "\n".join(body)


def _multi_section():
    return st.lists(_section_doc(), min_size=1, max_size=3).map(lambda xs: "\n".join(xs))


def _targeted_edges():
    return st.sampled_from([
        # dotted keys with whitespace / quoting
        'a . b = 1',
        'a."b".c = 1',
        'a . "b" . c = 1',
        '"a.b" = 1',
        "'a.b' = 1",
        'a.b.c.d = 1',
        # array-of-tables with sub-tables
        '[[a]]\n[a.b]\nc = 1',
        '[[a]]\n[[a]]\n[a.b]\nc = 1',
        '[a]\n[[a.b]]\nx = 1',
        '[a.b]\n[a]\nc = 1',
        # inline table edge cases
        'a = {}',
        'a = { }',
        'a = {b = {c = {d = 1}}}',
        'a = { b = 1 , c = 2 }',
        'a = {b = [1, {c = 2}]}',
        # arrays
        'a = []',
        'a = [ ]',
        'a = [[1],[2]]',
        'a = [1, [2, [3, [4]]]]',
        'a = [\n1,\n2,\n]',
        'a = [ # c\n1 ]',
        # multiline strings with tricky content
        'a = """\n"""',
        'a = """\\\n   x"""',
        "a = '''\n'''",
        'a = """a""b"""',
        'a = """a\\"""b"""',
        # numbers edge cases
        'a = 0x',
        'a = 0o',
        'a = 0b',
        'a = 0x_1',
        'a = 1__2',
        'a = _1',
        'a = 1_',
        'a = +',
        'a = -',
        'a = .',
        'a = e10',
        'a = 1e',
        'a = 1.e',
        'a = infinity',
        'a = nan_',
        # booleans / dates near-miss
        'a = True',
        'a = FALSE',
        'a = 1979-05-27T',
        'a = 1979-05-27T07:32',
        'a = 1979-05-27T07:32:00.Z',
        'a = 1979-05-27T07:32:00+',
        'a = 1979-13-01',
        'a = 24:00:00',
        # whitespace / newline handling
        'a=1',
        'a =1',
        'a= 1',
        '\ta = 1',
        'a = 1\t',
        'a = 1 # c',
        'a = 1#c',
        'a = 1\rb = 2',
        'a = 1\r\nb = 2',
        # header edge cases
        '[ a ]',
        '[a . b]',
        '[a.]',
        '[.a]',
        '[]',
        '[[]]',
        '[[a]',
        '[a]]',
        '[[a]]]',
        # empty / weird
        '=',
        ' = ',
        'a',
        'a =',
        'a = ',
        '"a"',
        'a.b',
        # duplicate / redefinition
        '[a]\nb = 1\n[a]\nb = 2',
        'a = 1\na = 2',
        '[a]\nb = 1\n[a.b]\nc = 2',
        'a = {b = 1, b = 2}',
        # comment-only and blank-heavy
        '\n\n\n',
        '   \n\t\n',
        '#\n#\n#',
        'a = 1\n\n\nb = 2',
    ])


def _deep_document2():
    n = st.integers(min_value=50, max_value=400)
    return st.one_of(
        # nested arrays with alternating element types
        n.map(lambda k: "a = " + "[" * k + "1" + "]" * k),
        # nested inline tables inside arrays
        st.integers(min_value=1, max_value=60).map(
            lambda k: "a = " + "[{b=" * k + "1" + "}]" * k
        ),
        # deeply dotted keys
        st.integers(min_value=2, max_value=200).map(
            lambda k: ".".join(["a"] * k) + " = 1"
        ),
        # long array of small elements
        st.integers(min_value=100, max_value=2000).map(
            lambda k: "a = [" + ",".join(["1"] * k) + "]"
        ),
    )


def _full_doc_v2():
    return st.one_of(
        _full_doc(),
        _multi_section(),
        _targeted_edges(),
        _deep_document2(),
    )


# ---------- improved fuzzer: grammar-aware generation ----------

def _gen_key():
    return st.one_of(
        st.text(alphabet="abcXYZ_019-", min_size=1, max_size=8),
        st.text(alphabet="abcXYZ_019-", min_size=1, max_size=8).map(lambda s: '"' + s + '"'),
        st.text(alphabet="abcXYZ_019-", min_size=1, max_size=8).map(lambda s: "'" + s + "'"),
    )


def _gen_scalar():
    return st.one_of(
        st.integers(min_value=-10**12, max_value=10**12).map(str),
        st.sampled_from(["true", "false", "inf", "nan", "1.5", "-0.0", "1e10"]),
        st.text(alphabet="abcXYZ 019", min_size=0, max_size=6).map(lambda s: '"' + s + '"'),
        st.text(alphabet="abcXYZ 019", min_size=0, max_size=6).map(lambda s: "'" + s + "'"),
    )


def _gen_value(depth):
    if depth <= 0:
        return _gen_scalar()
    return st.one_of(
        _gen_scalar(),
        st.lists(_gen_value(depth - 1), max_size=4).map(lambda xs: "[" + ", ".join(xs) + "]"),
        st.lists(
            st.tuples(_gen_key(), _gen_value(depth - 1)).map(lambda t: t[0] + " = " + t[1]),
            max_size=3,
        ).map(lambda ps: "{" + ", ".join(ps) + "}"),
    )


def _gen_keyval():
    return st.tuples(_gen_key(), _gen_value(2)).map(lambda t: t[0] + " = " + t[1])


def _gen_table_body():
    return st.lists(
        st.one_of(_gen_keyval(), st.just(""), _comment()),
        max_size=5,
    ).map(lambda ls: "\n".join(ls))


def _gen_table():
    header = st.one_of(
        _gen_key().map(lambda k: "[" + k + "]"),
        _gen_key().map(lambda k: "[[" + k + "]]"),
        st.tuples(_gen_key(), _gen_key()).map(lambda t: "[" + t[0] + "." + t[1] + "]"),
    )
    return st.tuples(header, _gen_table_body()).map(lambda t: t[0] + "\n" + t[1])


def _gen_document():
    return st.lists(
        st.one_of(_gen_keyval(), _gen_table(), _comment(), st.just("")),
        min_size=1,
        max_size=8,
    ).map(lambda ls: "\n".join(ls))


def _improved_document():
    return st.one_of(
        _gen_document(),
        _full_doc_v2(),
    )


# ---------- targeted coverage boosters ----------

def _string_escape_edges():
    """Focus on string parsing branches: escapes, unicode, multiline delimiters."""
    return st.one_of(
        st.sampled_from([
            'a = "\\u"',
            'a = "\\u12"',
            'a = "\\u123"',
            'a = "\\u12345"',
            'a = "\\U0011FFFF"',
            'a = "\\U00110000"',
            'a = "\\uD800"',
            'a = "\\uDFFF"',
            'a = "\\x41"',
            'a = "\\0"',
            'a = "\\a"',
            'a = "\\ "',
            'a = "\\\n"',
            'a = "\\\r\n"',
            'a = "\\',
            'a = "abc',
            "a = 'abc",
            'a = """',
            'a = """abc',
            'a = """abc""',
            'a = """abc\\"""',
            'a = """\\',
            'a = """\\\n',
            "a = '''",
            "a = '''abc",
            "a = '''abc''",
            "a = '''abc\\'''",
            'a = """a""""',
            'a = """a"""""',
            "a = '''a''''",
            'a = """\\u0041"""',
            'a = """\\uD800"""',
            'a = """\\U00110000"""',
            'a = "\\u00e9"',
            'a = "\\u4e2d"',
            'a = "\\u0000"',
            'a = "\\b\\f\\n\\r\\t\\\\\\"\\/"',
        ]),
        st.tuples(
            st.sampled_from(['"', "'", '"""', "'''"]),
            st.text(alphabet="ab\\\"'uU0123456789x\n", min_size=0, max_size=8),
        ).map(lambda t: "a = " + t[0] + t[1] + t[0]),
    )


def _number_edges():
    """Focus on numeric parsing branches: signs, digits, exponents, underscores."""
    return st.one_of(
        st.sampled_from([
            'a = 0',
            'a = -0',
            'a = +0',
            'a = 00',
            'a = 01',
            'a = -01',
            'a = 0x',
            'a = 0xg',
            'a = 0xG',
            'a = 0b2',
            'a = 0o8',
            'a = 0o9',
            'a = 1_',
            'a = _1',
            'a = 1__2',
            'a = 1_2_',
            'a = 1._5',
            'a = 1_.5',
            'a = 1.5_',
            'a = 1e',
            'a = 1e+',
            'a = 1e-',
            'a = 1e_5',
            'a = 1e5_',
            'a = .e5',
            'a = .5e',
            'a = 1.5e+',
            'a = 1.5e-',
            'a = 1.5e+1_0',
            'a = 0x1_',
            'a = 0x_1',
            'a = 0b_1',
            'a = 0o_1',
            'a = 1e999999999999',
            'a = -1e999999999999',
            'a = 1e-999999999999',
            'a = 0x' + 'F' * 100,
            'a = ' + '9' * 100,
        ]),
        st.tuples(
            st.sampled_from(["", "+", "-"]),
            st.sampled_from(["0x", "0o", "0b", ""]),
            st.text(alphabet="0123456789abcdefABCDEF_", min_size=0, max_size=6),
            st.one_of(st.just(""), st.sampled_from([".5", ".", "e1", "E-2"])),
        ).map(lambda t: "a = " + t[0] + t[1] + t[2] + t[3]),
    )


def _datetime_edges():
    """Focus on date/time parsing branches: separators, ranges, fractional seconds."""
    return st.one_of(
        st.sampled_from([
            'a = 1979-05-27T07:32:00Z',
            'a = 1979-05-27t07:32:00z',
            'a = 1979-05-27 07:32:00Z',
            'a = 1979-05-27T07:32:00.123456789Z',
            'a = 1979-05-27T07:32:00.1234567890Z',
            'a = 1979-05-27T07:32:00+00:00',
            'a = 1979-05-27T07:32:00-00:00',
            'a = 1979-05-27T07:32:00+24:00',
            'a = 1979-05-27T07:32:00+23:59',
            'a = 1979-05-27T07:32:00+23:60',
            'a = 1979-05-27T07:32:00+23:59:60',
            'a = 1979-05-27T24:00:00',
            'a = 1979-05-27T23:60:00',
            'a = 1979-05-27T23:59:60',
            'a = 1979-05-27T23:59:61',
            'a = 1979-02-29',
            'a = 2000-02-29',
            'a = 1900-02-29',
            'a = 1979-04-31',
            'a = 1979-13-01',
            'a = 1979-00-01',
            'a = 1979-01-00',
            'a = 1979-1-1',
            'a = 1979-01-1',
            'a = 1979-1-01',
            'a = 1979-05-27T',
            'a = 1979-05-27T07',
            'a = 1979-05-27T07:',
            'a = 1979-05-27T07:32:',
            'a = 1979-05-27T07:32:00.',
            'a = 1979-05-27T07:32:00+',
            'a = 1979-05-27T07:32:00-',
            'a = 1979-05-27T07:32:00+0',
            'a = 1979-05-27T07:32:00+00:',
            'a = 07:32:00',
            'a = 07:32',
            'a = 07:32:00.5',
            'a = 07:32:00Z',
            'a = 1979-05-27Z',
            'a = 1979-05-27 07:32',
            'a = 1979-05-27  07:32:00',
        ]),
        st.tuples(
            st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}"),
            st.sampled_from(["-", "-"]),
            st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
            st.sampled_from(["-", "-"]),
            st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
            st.one_of(
                st.just(""),
                st.tuples(
                    st.sampled_from(["T", "t", " "]),
                    st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
                    st.just(":"),
                    st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
                    st.just(":"),
                    st.integers(min_value=0, max_value=99).map(lambda n: f"{n:02d}"),
                    st.one_of(
                        st.just(""),
                        st.just(".5"),
                        st.just(".123456789"),
                        st.just(".1234567890"),
                    ),
                    st.one_of(
                        st.just(""),
                        st.sampled_from(["Z", "z", "+00:00", "-07:00", "+23:59", "+24:00"]),
                    ),
                ).map(lambda t: "".join(t)),
            ),
        ).map(lambda t: "a = " + "".join(t)),
    )


def _structural_edges():
    """Focus on structural parsing branches: table headers, nesting, ordering."""
    return st.one_of(
        st.sampled_from([
            # table header parsing
            '[a]',
            '[a.b]',
            '[a.b.c]',
            '[ a ]',
            '[a ]',
            '[ a]',
            '[a.b ]',
            '[ a . b ]',
            '[a..b]',
            '[.a]',
            '[a.]',
            '[.]',
            '[]',
            '[[]]',
            '[[a]]',
            '[[a.b]]',
            '[[ a ]]',
            '[[a]',
            '[a]]',
            '[[a]]]',
            '[[[a]]]',
            '[a]]\n',
            # table re-entry / ordering
            '[a]\nb = 1\n[a]\nc = 2',
            '[a]\nb = 1\n[a.b]\nc = 2',
            '[a.b]\nc = 1\n[a]\nd = 2',
            '[a]\nb = 1\n[[a]]\nc = 2',
            '[[a]]\n[a.b]\nc = 1',
            '[[a]]\n[[a]]\n[a.b]\nc = 1',
            '[[a]]\n[a]\nb = 1',
            '[a]\n[[a.b]]\nc = 1',
            '[a.b]\n[a]\nc = 1\n[a.b]\nd = 2',
            # inline table parsing
            'a = {}',
            'a = { }',
            'a = {b = 1}',
            'a = {b = 1,}',
            'a = {,}',
            'a = {b}',
            'a = {