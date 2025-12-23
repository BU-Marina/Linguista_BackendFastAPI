"""..."""

import aioboto3


class S3Storage:
    """..."""

    def __init__(self, bucket: str, region: str | None = None, endpoint_url: str | None = None):
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url

    async def upload(self, file_bytes: bytes, dest_path: str) -> str:
        session = aioboto3.Session()
        async with session.client("s3", endpoint_url=self.endpoint_url) as client:
            await client.put_object(Bucket=self.bucket, Key=dest_path, Body=file_bytes, ACL="public-read")

        # формируем публичный URL (или используем CDN)
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{dest_path}"
        if self.region:
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{dest_path}"

        return f"https://{self.bucket}.s3.amazonaws.com/{dest_path}"

    async def delete(self, path_or_url: str) -> None:
        # ожидаем path (key) или полный URL — нужно извлечь key
        key = self._key_from_path(path_or_url)
        session = aioboto3.Session()

        async with session.client("s3", endpoint_url=self.endpoint_url) as client:
            await client.delete_object(Bucket=self.bucket, Key=key)

    def _key_from_path(self, path_or_url: str) -> str:
        # если получаете полный URL, извлеките ключ, иначе просто верните path_or_url
        # простая реализация предполагает, что вы храните относительный ключ в БД
        return path_or_url.split("/", 3)[-1]  # адаптируйте под format
