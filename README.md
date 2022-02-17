# Iridium

![Project status](https://img.shields.io/badge/project%20status-alpha-%23ff8000)
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
Similarly, this package provides an enhanced Python coating around the [InvenioRDM APIs](https://inveniordm.docs.cern.ch/reference/rest_api_index/).

It provides:
* a low-level Python API faithfully wrapping the public InvenioRDM backend APIs
* a high-level object-oriented easy-to-use convenience API

Currently only the Vocabulary and Draft/Record APIs are supported.

Other APIs (such as Communities and Requests APIs)
might follow when there is interest and the REST APIs are stabilized.

## Compatibility

This package supports the officially supported Python versions, i.e. `>=3.7`.

Concerning the version of InvenioRDM, we currently do not give any commitment beyond
supporting the latest official release (i.e. currently `v7`).

If the InvenioRDM REST APIs at some point get a structured versioning and change policy,
i.e. it becomes possible to

* programmatically detect the InvenioRDM version of an instance
* clearly understand the API differences between releases

we might reconsider and start committing to support active InvenioRDM LTS releases.

## Getting Started

As a user, you can install this package just as any other package into your current
Python environment using
```
$ pip install git+https://github.com/Materials-Data-Science-and-Informatics/iridium.git
```
As usual, it is highly recommended that you use a
[virtual environment](https://stackoverflow.com/questions/41573587/what-is-the-difference-between-venv-pyvenv-pyenv-virtualenv-virtualenvwrappe)
to ensure isolation of dependencies between unrelated projects
(or use `poetry` as described further below, which automatically takes care of this).

If you installed `iridium` successfully,
you are probably interested in the high-level API.
Read the [tutorial](TUTORIAL.md) to learn how to use it.

It is not advised to use the low-level API directly,
unless you are an InvenioRDM expert.
The low-level API documentation is minimal and located
[here](https://materials-data-science-and-informatics.github.io/iridium/iridium/inveniordm.html).

## Development

This project uses [Poetry](https://python-poetry.org/) for dependency
management, so you will need to have poetry
[installed](https://python-poetry.org/docs/master/#installing-with-the-official-installer)
in order to contribute.

Then you can run the following lines to setup the project and install the package:
```
$ git clone https://github.com/Materials-Data-Science-and-Informatics/iridium.git
$ cd iridium
$ poetry install
```

Run `pre-commit install` (see [https://pre-commit.com](https://pre-commit.com))
after cloning. This enables pre-commit to enforce the required linting hooks.

Run `pytest` (see [https://docs.pytest.org](https://docs.pytest.org)) before
merging your changes to make sure you did not break anything. To check
coverage, use `pytest --cov`.

**Note:** Running the tests requires a recent and functioning
InvenioRDM instance that you have access to.

To generate local documentation (as the one linked above), run
`pdoc --html -o docs iridium` (see [https://pdoc.dev](https://pdoc.dev)).

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
