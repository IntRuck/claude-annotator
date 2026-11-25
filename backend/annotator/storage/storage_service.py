"""Supabase Storage REST client (like backend_web's SupabaseStorageService).

Server-side only: it uses the service key, so the browser never talks to Storage directly; it gets
short-lived signed URLs from the API instead.
"""
from urllib.parse import quote

import httpx

IMAGES_BUCKET = "images"


class StorageError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Storage error {status}: {message}")
        self.status = status


class StorageService:
    def __init__(self, base_url: str, service_key: str, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        headers = {"apikey": service_key}
        # New-style keys (sb_secret_...) are not JWTs, so they only go in `apikey`.
        if service_key and not service_key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {service_key}"
        self._http = httpx.Client(base_url=f"{self.base_url}/storage/v1", headers=headers, timeout=timeout,
                                  transport=transport)

    # ---------- buckets ----------
    def bucket_exists(self, bucket: str) -> bool:
        return self._request("GET", f"/bucket/{quote(bucket)}", allow=(400, 404)).status_code == 200

    def ensure_bucket(self, bucket: str) -> None:
        if not self.bucket_exists(bucket):
            self._request("POST", "/bucket", json={"id": bucket, "name": bucket, "public": False})

    # ---------- objects ----------
    def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        self._request("POST", f"/object/{quote(bucket)}/{quote(path)}", content=data,
                      headers={"Content-Type": content_type, "x-upsert": "true"})

    def download(self, bucket: str, path: str) -> bytes:
        return self._request("GET", f"/object/{quote(bucket)}/{quote(path)}").content

    def signed_url(self, bucket: str, path: str, expires_in: int) -> str:
        r = self._request("POST", f"/object/sign/{quote(bucket)}/{quote(path)}", json={"expiresIn": expires_in})
        return f"{self.base_url}/storage/v1{r.json()['signedURL']}"

    def remove(self, bucket: str, paths: list[str]) -> None:
        self._request("DELETE", f"/object/{quote(bucket)}", json={"prefixes": paths})

    # ---------- plumbing ----------
    def _request(self, method: str, url: str, allow: tuple[int, ...] = (), **kwargs) -> httpx.Response:
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise StorageError(0, str(e)) from e
        if response.is_success or response.status_code in allow:
            return response
        raise StorageError(response.status_code, _message(response))


def _message(response: httpx.Response) -> str:
    try:
        body = response.json()
        return body.get("message") or body.get("error") or response.text
    except ValueError:
        return response.text
