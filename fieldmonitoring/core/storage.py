"""Private Vercel Blob storage for uploaded files (arrival photos).

Blobs are written to a *private* store: reading needs the store token, so a photo is
only ever delivered through the authorised photo endpoint, never by a public URL.
"""

import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, prefix: str = "media/"):
        self.prefix = prefix

    @staticmethod
    def _blob():
        from vercel import blob  # imported lazily: only needed where the store is configured

        return blob

    def _save(self, name, content):
        content.seek(0)
        result = self._blob().put(
            f"{self.prefix}{name}",
            content.read(),
            access="private",
            content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
            add_random_suffix=True,  # immutable blobs; never overwrite evidence
        )
        return result.pathname

    def _open(self, name, mode="rb"):
        from vercel.blob.errors import BlobNotFoundError

        try:
            result = self._blob().get(name, access="private")
        except BlobNotFoundError as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(result.content, name=name)

    def exists(self, name):
        # Every save gets a random suffix, so a new name never collides.
        return False

    def delete(self, name):
        self._blob().delete(name)

    def size(self, name):
        return self._blob().head(name).size

    def url(self, name):
        raise NotImplementedError("Private blobs are served through the authorised photo endpoint.")
