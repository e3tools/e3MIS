"""Private Vercel Blob storage adapter. The SDK is stubbed: no network in tests."""

import types

import pytest
from django.core.files.base import ContentFile

from fieldmonitoring.core.storage import VercelBlobStorage


class FakeBlob:
    def __init__(self):
        self.store = {}
        self.calls = []

    def put(self, path, body, **kwargs):
        self.calls.append(("put", path, kwargs))
        name = path.replace(".jpg", "-abc123.jpg")
        self.store[name] = body
        return types.SimpleNamespace(pathname=name)

    def get(self, name, **kwargs):
        from vercel.blob.errors import BlobNotFoundError

        self.calls.append(("get", name, kwargs))
        if name not in self.store:
            raise BlobNotFoundError()
        return types.SimpleNamespace(content=self.store[name])

    def delete(self, name):
        self.store.pop(name, None)


@pytest.fixture
def storage(monkeypatch):
    fake = FakeBlob()
    monkeypatch.setattr(VercelBlobStorage, "_blob", staticmethod(lambda: fake))
    return VercelBlobStorage(), fake


def test_saves_privately_with_a_random_suffix_and_reads_back(storage):
    s, fake = storage
    name = s.save("photos/2026/09/a.jpg", ContentFile(b"jpeg-bytes"))
    assert name == "media/photos/2026/09/a-abc123.jpg"
    assert fake.calls[0][2]["access"] == "private" and fake.calls[0][2]["add_random_suffix"] is True
    assert s.open(name).read() == b"jpeg-bytes"
    assert fake.calls[-1][2]["access"] == "private"


def test_missing_blob_is_file_not_found(storage):
    s, _ = storage
    with pytest.raises(FileNotFoundError):
        s.open("media/nope.jpg")


def test_no_public_urls(storage):
    s, _ = storage
    with pytest.raises(NotImplementedError):
        s.url("media/x.jpg")
