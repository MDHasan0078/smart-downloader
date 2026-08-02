"""PyInstaller entry point: launches the frozen engine binary.

engine.py uses relative imports, so it must be imported as the `core.engine`
package (not executed as a top-level script). PyInstaller bundles the `core`
package via hiddenimports=collect_submodules("core").
"""

from core.engine import main

main()
