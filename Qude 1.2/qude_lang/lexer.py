from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import re

# Very small lexer sufficient for the current Qude MVP grammar.
# It recognizes identifiers, keywords, numbers, strings, operators, and symbols.

KEYWORDS = {
    "event", "then", "if", "elif", "else",
}

SYMBOLS = {
    "(", ")", ",", ".", "=", ":", ";", "<", ">",
}

OPERATORS = {
    "+", "-", "*", "/",
}

STRING_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
WS_RE = re.compile(r"\s+")

@dataclass
class Token:
    kind: str
    text: str
    line: int
    col: int

class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        lines = self.source.splitlines()
        for li, raw in enumerate(lines, start=1):
            s = raw
            i = 0
            L = len(s)
            while i < L:
                # comments
                if s[i:].startswith("//") or s[i:].startswith("#"):
                    break
                m = WS_RE.match(s, i)
                if m:
                    i = m.end()
                    continue
                # string
                m = STRING_RE.match(s, i)
                if m:
                    tokens.append(Token("STRING", m.group(0), li, i+1))
                    i = m.end()
                    continue
                # number
                m = NUMBER_RE.match(s, i)
                if m:
                    tokens.append(Token("NUMBER", m.group(0), li, i+1))
                    i = m.end()
                    continue
                # identifier / keyword
                m = IDENT_RE.match(s, i)
                if m:
                    text = m.group(0)
                    kind = "KW" if text in KEYWORDS else "IDENT"
                    tokens.append(Token(kind, text, li, i+1))
                    i = m.end()
                    continue
                # two-char symbols for option markers like '<ok>' are handled in parser; emit single symbols here
                ch = s[i]
                if ch in SYMBOLS or ch in OPERATORS:
                    tokens.append(Token(ch, ch, li, i+1))
                    i += 1
                    continue
                # unknown
                tokens.append(Token("UNKNOWN", ch, li, i+1))
                i += 1
            tokens.append(Token("EOL", "", li, len(s)+1))
        tokens.append(Token("EOF", "", len(lines)+1, 1))
        return tokens
