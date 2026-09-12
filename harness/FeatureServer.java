// FeatureServer.java — grammar-derived proxy features on the JVM ANTLR runtime.
//
// Why: fuzz/formats.py derives the proxy's structural features (productions,
// recursion depth) by parsing each input with the target's own ANTLR grammar.
// The Python runtime costs ~1.3 ms per nesting level on the TOML grammar (an
// adaptive-prediction decision at every level); the JVM runtime is ~50x faster.
// Same grammar, same ANTLR version (4.13.2), so rule indices and token types
// are identical, and the Python side keeps ALL naming/filtering logic: this
// server only reports raw facts about a strict parse.
//
// Protocol (stdin/stdout, one process per format, kept alive by formats.py):
//   in : 4-byte big-endian length + UTF-8 bytes of the input
//   out: one line:  "F <ok> <depth> <ruleIdx,...> <tokenType,...>\n"
//        ok = 1 if the strict parse succeeded (any lexer/parser error => 0),
//        depth = max over rules of (occurrences on a root-to-leaf path) - 1,
//        the two lists are the DISTINCT parser rule indices and token types
//        seen in the tree (empty lists print as "-").
//
// Usage: java -cp <antlr-jar>:<classes> FeatureServer gen.JSONLexer gen.JSONParser json
import org.antlr.v4.runtime.*;
import org.antlr.v4.runtime.misc.ParseCancellationException;
import org.antlr.v4.runtime.tree.*;

import java.io.*;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.*;

public final class FeatureServer {
    static final class Strict extends BaseErrorListener {
        @Override public void syntaxError(Recognizer<?, ?> r, Object sym, int line, int col,
                                          String msg, RecognitionException e) {
            throw new ParseCancellationException(line + ":" + col + " " + msg);
        }
    }

    static Constructor<?> lexerCtor, parserCtor;
    static Method startRule;

    public static void main(String[] args) throws Exception {
        Class<?> lexerCls = Class.forName(args[0]);
        Class<?> parserCls = Class.forName(args[1]);
        lexerCtor = lexerCls.getConstructor(CharStream.class);
        parserCtor = parserCls.getConstructor(TokenStream.class);
        startRule = parserCls.getMethod(args[2]);

        DataInputStream in = new DataInputStream(new BufferedInputStream(System.in, 1 << 20));
        PrintStream out = new PrintStream(new BufferedOutputStream(System.out, 1 << 16), false, "UTF-8");
        while (true) {
            int len;
            try { len = in.readInt(); } catch (EOFException eof) { break; }
            byte[] buf = new byte[len];
            in.readFully(buf);
            final String text = new String(buf, StandardCharsets.UTF_8);
            final String[] result = new String[1];
            // Deep inputs recurse once per rule level: run on a thread with a 1 GiB stack.
            Thread t = new Thread(null, () -> result[0] = features(text), "parse", 1L << 30);
            t.start();
            t.join();
            out.print(result[0]);
            out.print('\n');
            out.flush();
        }
    }

    static String features(String text) {
        ParserRuleContext tree;
        Parser parser;
        try {
            Lexer lexer = (Lexer) lexerCtor.newInstance(CharStreams.fromString(text));
            lexer.removeErrorListeners();
            lexer.addErrorListener(new Strict());
            parser = (Parser) parserCtor.newInstance(new CommonTokenStream(lexer));
            parser.removeErrorListeners();
            parser.addErrorListener(new Strict());
            parser.setErrorHandler(new BailErrorStrategy());
            tree = (ParserRuleContext) startRule.invoke(parser);
        } catch (Throwable e) {        // ParseCancellation, StackOverflowError, anything
            return "F 0 0 - -";
        }
        // Iterative walk: distinct rule indices, distinct token types, recursion depth.
        BitSet rules = new BitSet(), toks = new BitSet();
        int maxDepth = 0;
        int nRules = parser.getRuleNames().length;
        ArrayDeque<Object[]> stack = new ArrayDeque<>();
        stack.push(new Object[]{tree, new int[nRules]});
        while (!stack.isEmpty()) {
            Object[] top = stack.pop();
            ParseTree node = (ParseTree) top[0];
            int[] counts = (int[]) top[1];
            if (node instanceof TerminalNode) {
                int tt = ((TerminalNode) node).getSymbol().getType();
                if (tt >= 0) toks.set(tt);
                continue;
            }
            if (node instanceof ParserRuleContext) {
                int ri = ((ParserRuleContext) node).getRuleIndex();
                rules.set(ri);
                int[] c = counts.clone();
                c[ri]++;
                if (c[ri] - 1 > maxDepth) maxDepth = c[ri] - 1;
                for (int i = 0; i < node.getChildCount(); i++) stack.push(new Object[]{node.getChild(i), c});
            }
        }
        StringBuilder sb = new StringBuilder("F 1 ").append(maxDepth).append(' ');
        sb.append(join(rules)).append(' ').append(join(toks));
        return sb.toString();
    }

    static String join(BitSet bs) {
        if (bs.isEmpty()) return "-";
        StringBuilder sb = new StringBuilder();
        for (int i = bs.nextSetBit(0); i >= 0; i = bs.nextSetBit(i + 1)) {
            if (sb.length() > 0) sb.append(',');
            sb.append(i);
        }
        return sb.toString();
    }
}
