from collections.abc import Sequence

from seedance_client import SeedanceClient


ClientSignature = tuple[str, tuple[str, ...]]


class SeedanceClientRegistry:
    def __init__(self):
        self._clients: dict[str, tuple[ClientSignature, SeedanceClient]] = {}

    @staticmethod
    def _build_signature(api_keys: Sequence[str], base_url: str) -> ClientSignature:
        normalized_keys = tuple(key.strip() for key in api_keys if key.strip())
        return base_url.rstrip("/"), normalized_keys

    async def get_or_create(self, cache_key: str, api_keys: Sequence[str], base_url: str) -> SeedanceClient:
        signature = self._build_signature(api_keys, base_url)
        cached_entry = self._clients.get(cache_key)
        if cached_entry is not None:
            cached_signature, cached_client = cached_entry
            if cached_signature == signature:
                return cached_client
            await cached_client.aclose()

        client = SeedanceClient(list(signature[1]), signature[0])
        self._clients[cache_key] = (signature, client)
        return client

    async def invalidate(self, cache_key: str) -> None:
        cached_entry = self._clients.pop(cache_key, None)
        if cached_entry is None:
            return
        _, cached_client = cached_entry
        await cached_client.aclose()

    async def aclose(self) -> None:
        cached_clients = list(self._clients.values())
        self._clients.clear()
        for _, client in cached_clients:
            await client.aclose()
