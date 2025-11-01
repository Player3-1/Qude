import os
import sys
try:
    from .ide import QudeIDE
except ImportError:
    # Allow running directly: python qude/main.py
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from qude.ide import QudeIDE


def main():
    app = QudeIDE()
    app.run()


if __name__ == "__main__":
    main()
