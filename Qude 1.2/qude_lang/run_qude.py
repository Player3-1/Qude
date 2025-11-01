from __future__ import annotations
import sys
import tkinter as tk
from .parser import Parser
from .interpreter import QudeAstInterpreter

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m qude.qude_lang.run_qude <script.q>")
        return 1
    script_path = sys.argv[1]
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"[Error] Cannot read script: {e}")
        return 2

    root = tk.Tk()
    try:
        root.withdraw()
    except Exception:
        pass

    def cw(msg: str) -> None:
        print(msg)

    try:
        program = Parser(code).parse()
    except Exception as e:
        print(f"[Error] Parse: {e}")
        return 3

    try:
        interp = QudeAstInterpreter(cw, root)
        interp.run(program)
        root.mainloop()
    except Exception as e:
        print(f"[Error] Run: {e}")
        return 4
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
