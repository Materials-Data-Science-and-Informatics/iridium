"""
Pydantic models for relevant JSON objects.

Based on the source code of various Invenio(RDM) modules
and the official InvenioRDM documentation here:
https://inveniordm.docs.cern.ch/reference/metadata/

This recreation of the structures is not perfect.
If failures happen, please open a bug report and describe
what kind of API call failed in order to deduce a possible problem in the model.
"""

# re-export all classes for convenience

from .biblio import *  # noqa: F401, F403
from .query import *  # noqa: F401, F403
from .technical import *  # noqa: F401, F403
