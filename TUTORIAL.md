# Iridium

## Introduction

The goal of Iridium is to provide an easy-to-use Python interface for interacting
with [Invenio RDM](https://inveniordm.docs.cern.ch/).

Invenio RDM has a [REST API](https://inveniordm.docs.cern.ch/reference/rest_api_index/),
but this API is *"[...] intended for advanced users, and developers of InvenioRDM
that have some experience with using REST APIs [...]"*.

Iridium is intended for *everyone else* who needs a programmatic interface to Invenio RDM,
e.g.:

* **domain researchers and data scientists** with basic user-level Python competence
  who would like to use an environment such as Jupyter notebooks
  e.g. in order to reuse or analyse available data.
* **developers** who need to build lightweight external tooling around Invenio RDM
  e.g. as a part of bigger domain-specific solutions and workflows
  that use Invenio RDM as the underlying repository.

In this tutorial you will learn how to use most of the Iridium interface.
For a deeper look, consider looking into the more technical documentation of
classes in the `iridium` package.

## Import Iridium

**IMPORTANT:** in order to use all the APIs, you need to get an **API token** from the
Invenio RDM you are going to use. For this, sign in to your Invenio RDM, and go to
*Settings -> Applications -> Personal access tokens* to create one.
Without a token you will only be able to have read-only access to published records.

Start with the following imports:

```python
from iridium import Repository
from iridium.inveniordm.models import *
```

A `Repository` object represents the top-level entry point from which all exposed
functionality can be accessed. Get access to the Invenio RDM instance:

```python
rdm = Repository.connect("https://www.your-invenio-rdm.org", "YOUR_API_TOKEN")
```

**Remark:** If you are using a test instance of Invenio RDM that uses a self-signed
certificate, you need to pass an extra argument `verify=False` to the `connect` method.
Otherwise the connection will fail due to security reasons.

## Create a new record

In Invenio, the workflow to update records always goes through record *drafts*.
Create a draft for a new record like this:

```python
draft = rdm.drafts.create()
```

When you print or evaluate `draft` in your notebook, you will see something like:

```python
{ 'access': { 'embargo': {'active': False},
              'files': 'public',
              'record': 'public',
              'status': 'metadata-only'},
  'created': '2022-02-14T10:21:36.081522+00:00',
  'expires_at': '2022-02-14T10:21:36.081560',
  'files': [],
  'id': 'k86r9-7b355',
  'is_published': False,
  'metadata': {},
  'updated': '2022-02-14T10:21:36.100746+00:00',
  'versions': {'index': 1, 'is_latest': False, 'is_latest_draft': True}}
```

**Remark:** This is a slightly censored view at what Invenio RDM stores about drafts and
records. Iridium will hide some fields that are confusing or too technical (you can still
access them, if you know what you are doing).

Both `save()` and `publish()` work exactly the same as you know it from the web interface.
**This means, you must `save()` changes you do to the metadata, otherwise they are lost
once you get rid of your draft object.**
Also, changes you do to drafts are visible *only to you* until you `publish()` the draft.
Note that `publish()` will also automatically `save()` your changes.

We can try publishing the draft without adding any metadata:

```python
draft.publish()
```

We will get back a number of validation errors from Invenio RDM:

```python
{ 'files.enabled': 'Missing uploaded files. To disable files for this record '
                   'please mark it as metadata-only.',
  'metadata.creators': 'Missing data for required field.',
  'metadata.publication_date': 'Missing data for required field.',
  'metadata.resource_type': 'Missing data for required field.',
  'metadata.title': 'Missing data for required field.'}
```

### Uploading a file

In order to fix the first problem, you either have to set `draft.files.enabled = False`,
thus confirming that you want to create a *metadata-only* record, or you can add at least
one file. We will take the second option here.
To upload and attach `my_file.zip` to the draft, run:

```python
draft.files.upload("my_file.zip")
```

**Remark:** If you don't have a file stored on disk or want to store it under a different
name in the record, you can use `draft.files.upload("target_filename.zip", data)`,
where `data` can be an arbitrary binary stream. To create a suitable stream from a file,
use `open(PATH_TO_FILE, "rb")`.

**Example:** `draft.files.upload("renamed.zip", open("my_file.zip", "rb"))` would upload the
same file as above, but save it as `renamed.zip` in the draft.

Now let us inspect `draft.files`:

```python
{'my_file.zip': FileMetadata(...)}
```

We see that the new file is registered in the draft. We can also access the information
that is stored alongside the uploaded file by inspecting `draft.files["my_file.zip"]`:

```python
{ 'bucket_id': '263bcf0e-f74e-4d98-ab3a-3560b30c4c8b',
  'checksum': 'md5:1a6954f71cb8e867c6ea67b1d01c725b',
  'created': '2022-02-14T11:01:24.484029+00:00',
  'file_id': 'b529e0c8-ce4b-4213-8d4b-ef3744aa4a5b',
  'key': 'my_file.zip',
  'links': { 'commit': 'https://127.0.0.1:5000/api/records/k86r9-7b355/draft/files/README.md/commit',
             'content': 'https://127.0.0.1:5000/api/records/k86r9-7b355/draft/files/README.md/content',
             'self': 'https://127.0.0.1:5000/api/records/k86r9-7b355/draft/files/README.md'},
  'metadata': {},
  'mimetype': 'text/markdown',
  'size': 2686,
  'status': 'completed',
  'storage_class': 'S',
  'updated': '2022-02-14T11:01:24.590777+00:00',
  'version_id': 'e5b11c0a-60c3-42f7-be26-d332cd776310'}
```

The most interesting information is probably the `checksum`, that you can use to verify
that no file corruption happened during upload (you could e.g. run `md5sum` on your file
in the terminal and compare the checksum strings - they must be equal).

### Adding some metadata

In order to modify access restrictions or bibliographic metadata of a draft,
you can edit the `draft.access` and `draft.metadata` fields directly
(don't forget to `save()` afterwards).

Now let us add the missing information Invenio RDM was complaining about.
Iridium does not hide away or simplify the internal metadata model, but it provides
classes that help you constructing the required entities (that is why we imported
`iridium.inveniordm.models` at the start).

```python
from datetime import date

# add an arbitrary title
draft.metadata.title = "My amazing new dataset"
# publication date must be of the shape YYYY[-MM][-DD]
draft.metadata.publication_date = date.today().isoformat()  # e.g.: 2022-10-20
# you can check the existing types with list(rdm.vocabulary[VocType.resource_types])
draft.metadata.resource_type = VocabularyRef(id="dataset")

draft.metadata.creators = [
  Creator(
  role=CreatorRole(id="contactperson"),
  affiliations=[Affiliation(name="CERN")],
  person_or_org=PersonOrOrg(family_name="Doe", given_name="John", type="personal"))
]

draft.save() # should return no validation errors now
draft.publish()
```

Notice that after `publish()` succeeds, we now hold a non-draft record object.
You can check its record id in `draft.id`.

Now lets verify that our new published record can be accessed:

```python
rec = rdm.records[draft.id]
print(rec.metadata.title)
```

We should see `My amazing new dataset` printed out to us.

## Update a record

But what if we notice that we did a mistake?
If the mistake was only in the metadata and not in the files, then we can easily fix it.
For example, let us change the title of the record that we created:

```python
rec = rdm.records[draft.id]
rec.edit()
rec.metadata.title = "My corrected new dataset"
rec.publish()
```

So we access the record, set it into editable mode (technically, we switch to a draft),
update the metadata and `publish()` the changes - that's it.

If our mistake is in the files that we uploaded, though, there is some more work involved.
**Invenio RDM only allows to update the files attached to a record if we create a new
version of that record. The old files will forever remain accessible in the previous
versions.**

Currently, our fresh record has just one version:

```python
print(len(rec.versions))  # should print: 1
print(rec.versions)       # should print a list containing just the value of rec.id
```

Now let us create a new version (which is another draft, but one linked to the
previous version):

```python
rec_new = rec.versions.create()
```

We can use `rec_new.save()` to get the validation errors:
```python
{ 'files.enabled': 'Missing uploaded files. To disable files for this record '
                   'please mark it as metadata-only.',
  'metadata.publication_date': 'Missing data for required field.'}
```

From this you learn two things:

1. In a new version, the publication date is removed from the draft,
  forcing you to consciously update it.
2. By default, the files from the previous version are not included in the new version.

If you want to keep (a subset of) the files from the previous version in the record,
use `rec_new.files.import_old()` to import them into the draft, so you will not have to
upload them again. You can use `rec_new.files.delete(filename)` to remove such imported
files as well as any files that you uploaded into an unpublished draft.

To add a new file, proceed as described above, e.g. `rec_new.files.upload("other.data")`.

Now you can set the new publication date and publish the new version.
After this there should be two versions of your record and
`rec.versions.latest()` should point to the new assigned `id` of the new version, i.e.
be equal to `rec_new.id`.

## Query records

TODO

**Remark:** The drafts can be queried similarly,
just use `rdm.drafts` instead of `rdm.records`.

## Query vocabularies

Invenio RDM provides a number of vocabularies that can be queried.
See the `VocType` class for a list of the supported vocabularies.

For example, we can print all software licenses as follows:
```python
for l in rdm.vocabulary[VocType.licenses](tags="software"):`
  print(l.id)
```

Or we can see how many listed languages are extinct:
```python
print(len(rdm.vocabulary[VocType.languages](tags="extinct")))
```

Or we can look at specific entries in more detail:
```python
print(rdm.vocabularies[VocType.resource_types]["dataset"])
```

resulting in an object like this:
```
{ 'created': '2022-01-11T09:15:42.699516+00:00',
  'icon': 'table',
  'id': 'dataset',
  'links': { 'self': 'https://127.0.0.1:5000/api/vocabularies/resourcetypes/dataset'},
  'props': { 'csl': 'dataset',
             'datacite_general': 'Dataset',
             'datacite_type': '',
             'eurepo': 'info:eu-repo/semantics/other',
             'openaire_resourceType': '21',
             'openaire_type': 'dataset',
             'schema.org': 'https://schema.org/Dataset',
             'subtype': '',
             'type': 'dataset'},
  'revision_id': 1,
  'tags': ['depositable', 'linkable'],
  'title': {'en': 'Dataset'},
  'type': 'resourcetypes',
  'updated': '2022-01-11T09:15:42.753576+00:00'}
```
