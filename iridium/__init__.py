""".. include:: ../TUTORIAL.md"""  # noqa: D400
import sys
from pathlib import Path

import toml
from typing_extensions import Final

# re-export
from .api import Repository  # noqa: F401

# for pdoc to understand the include:: directive
__docformat__ = "restructuredtext"

__pkg_path__: Final[Path] = Path(sys.modules[__name__].__file__).parent.resolve()

# get root path of project (above the module dir)
__basepath__: Final[Path] = __pkg_path__.parent.resolve()


# single source of truth for version is the pyproject.toml!
pyproject = toml.load(__basepath__ / "pyproject.toml")

__version__: Final[str] = pyproject["tool"]["poetry"]["version"]
