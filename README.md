# Iridium

![Project status](https://img.shields.io/badge/status-pre--alpha-%23ff0000)
[
![Test](https://img.shields.io/github/workflow/status/Materials-Data-Science-and-Informatics/iridium/test?label=test)
](https://github.com/Materials-Data-Science-and-Informatics/iridium/actions?query=workflow:test)
[
![Coverage](https://img.shields.io/codecov/c/gh/Materials-Data-Science-and-Informatics/iridium?token=4JU2SZFZDZ)
](https://app.codecov.io/gh/Materials-Data-Science-and-Informatics/iridium)
[
![Docs](https://img.shields.io/badge/read-docs-success)
](https://materials-data-science-and-informatics.github.io/iridium/)
<!--
[
![PyPIPkgVersion](https://img.shields.io/pypi/v/iridium)
](https://pypi.org/project/iridium/)
-->

The metal Iridium is used to refine and enhance metal alloys.
Similarly, this package provides an enhanced coating
around the Invenio RDM APIs and is a central piece of the Ardiem platform.

It provides:
* a lower-level Python API wrapping the public Invenio RDM backend APIs

* a higher-level object-oriented convenience API (TODO)
* a JSON Schema based concept of "dataset profiles" for Invenio records (TODO)
* transparent support for storage and retrieval of additional validated metadata (TODO)

## Development

This project uses [Poetry](https://python-poetry.org/) for dependency management.

Clone this repository and run `poetry install`.

Run `pre-commit install` after cloning to enable pre-commit to enforce the required linting hooks.

Run `pytest` before merging your changes to make sure you did not break anything.

To generate documentation, run `pdoc --html -o docs python_app_template`.

To check coverage, use `pytest --cov`.

## Acknowledgements

<div>
<img style="vertical-align: middle;" alt="HMC Logo" src="https://helmholtz-metadaten.de/storage/88/hmc_Logo.svg" width=50% height=50% />
&nbsp;&nbsp;
<img style="vertical-align: middle;" alt="FZJ Logo" src="https://upload.wikimedia.org/wikipedia/de/8/8b/J%C3%BClich_fz_logo.svg" width=30% height=30% />
</div>
<br />

This project was developed at the Institute for Materials Data Science and Informatics
(IAS-9) of the Jülich Research Center and funded by the Helmholtz Metadata Collaboration
(HMC), an incubator-platform of the Helmholtz Association within the framework of the
Information and Data Science strategic initiative.
