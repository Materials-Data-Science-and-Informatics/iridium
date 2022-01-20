"""
CLI interface for Iridium API.

NOTE:
  Currently, designing an ergonomic CLI for all functionality is not high-priority.
  It just shows how the low-level API can be easily exposed through a command line tool.
"""
from pathlib import Path
from typing import Optional

import typer

from .inveniordm.api import InvenioRDMClient, Results, VocType

# Get access to API based on configured INVENIORDM_URL and INVENIORDM_TOKEN env vars.
# passing verify=False allows to use the self-signed certificate
rdm = InvenioRDMClient.from_env(httpx_kwargs={"verify": False})


def pprint_results(res: Results, size: int, page: int):
    """Pretty-print results from a query, given information about pagination."""
    firstidx = (page - 1) * size + 1
    lastidx = firstidx + len(res.hits.hits) - 1
    print(f"Results {firstidx} - {lastidx} out of {res.hits.total}:")
    for r in res.hits.hits:
        print(r)


# Default values for queries
_DEF_PAGE = 1
_DEF_SIZE = 10

# ---- build up the CLI interface ----

app = typer.Typer()

rec_app = typer.Typer()
app.add_typer(rec_app, name="record")

voc_app = typer.Typer()
app.add_typer(voc_app, name="vocabulary")


@rec_app.command(name="list")
def records(
    q: Optional[str] = None,
    user: Optional[bool] = False,
    size: int = _DEF_SIZE,
    page: int = _DEF_PAGE,
):
    """Query records using an elasticsearch query string."""
    res = rdm.query.records(user=user, q=q, size=size, page=page)
    pprint_results(res, size, page)


@rec_app.command(name="files")
def rec_files(rec_id: str):
    """List files attached to a record."""
    print("Attached files:")
    for fm in rdm.record.files(rec_id).entries:
        print(f"\t{fm.key}")


@rec_app.command(name="get")
def rec_get(
    rec_id: str, filename: str = None, out: Path = typer.Option(None, "--out", "-o")
):
    """Get record metadata or download a file."""
    if filename is None:
        print(rdm.record.get(rec_id))
        return

    # if filename is provided, we download the file from the record
    assert filename  # to silence typechecker
    if out is None:
        out = Path(filename)

    bs = rdm.record.file_download(rec_id, filename)
    with open(out, "wb") as of:
        of.write(bs.read())


@voc_app.command(name="list")
def voc(
    type: VocType,
    size: int = _DEF_SIZE,
    page: int = _DEF_PAGE,
):
    """List all terms in a controlled vocabulary."""
    res = rdm.query.vocabulary(type)
    pprint_results(res, size, page)


@voc_app.command(name="term")
def voc_term(type: VocType, term: str):
    """Print the entry for a term in a controlled vocabulary."""
    print(rdm.query.term(type, term))


if __name__ == "__main__":
    typer.run(app)
