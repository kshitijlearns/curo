"""Supabase Storage implementation — NOT IMPLEMENTED YET (needs SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY).

TODO when the keys arrive (see docs/INTEGRATION.md):
1. Create private buckets STORAGE_BUCKET_VIDEOS and STORAGE_BUCKET_THUMBS (no public access).
2. Use the Storage REST API with the service-role key from the server only:
   POST /storage/v1/object/{bucket}/{path} (upsert), GET for downloads, DELETE to remove.
3. signed_upload: POST /storage/v1/object/upload/sign/{bucket}/{path} returns a token; the
   app PUTs the file to {SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{path}?token=…
   (absolute URL, so the app sends it straight to Supabase, never through the API).
4. list: POST /storage/v1/object/list/{bucket} with {"prefix", "limit": 1000, "offset"}
   (paged; folders come back as entries without ids: recurse into them), created_at from
   each entry.
5. Contract test: put → exists → get → delete round trip against a test bucket.
"""

from __future__ import annotations

from .base import SignedUpload, StorageProvider

_TODO = "Supabase storage not implemented yet: set STORAGE_PROVIDER=local (see INTEGRATION.md)"


class SupabaseStorage(StorageProvider):
    name = "supabase"

    def __init__(self, url: str, service_role_key: str):
        self.url = url
        self.key = service_role_key

    def put(self, bucket, path, data, content_type):
        raise NotImplementedError(_TODO)

    def get(self, bucket, path):
        raise NotImplementedError(_TODO)

    def delete(self, bucket, path):
        raise NotImplementedError(_TODO)

    def exists(self, bucket, path):
        raise NotImplementedError(_TODO)

    def signed_upload(self, bucket, path, content_type, expires_in_s=900) -> SignedUpload:
        raise NotImplementedError(_TODO)

    def list(self, bucket, prefix):
        raise NotImplementedError(_TODO)
