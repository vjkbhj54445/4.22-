import pytest

import client_registry


class FakeSeedanceClient:
    def __init__(self, api_keys: list[str], base_url: str):
        self.api_keys = api_keys
        self.base_url = base_url
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_registry_reuses_client_for_same_signature(monkeypatch):
    registry = client_registry.SeedanceClientRegistry()
    monkeypatch.setattr(client_registry, "SeedanceClient", FakeSeedanceClient)

    first_client = await registry.get_or_create(
        "provider-a",
        [" key-a ", "key-b"],
        "https://api.ppio.com/",
    )
    second_client = await registry.get_or_create(
        "provider-a",
        ["key-a", "key-b"],
        "https://api.ppio.com",
    )

    assert first_client is second_client
    assert first_client.api_keys == ["key-a", "key-b"]
    assert first_client.base_url == "https://api.ppio.com"


@pytest.mark.asyncio
async def test_registry_replaces_client_when_signature_changes(monkeypatch):
    registry = client_registry.SeedanceClientRegistry()
    monkeypatch.setattr(client_registry, "SeedanceClient", FakeSeedanceClient)

    first_client = await registry.get_or_create(
        "provider-a",
        ["key-a"],
        "https://api.ppio.com",
    )
    second_client = await registry.get_or_create(
        "provider-a",
        ["key-c"],
        "https://api2.ppio.com",
    )

    assert first_client is not second_client
    assert first_client.closed is True
    assert second_client.api_keys == ["key-c"]
    assert second_client.base_url == "https://api2.ppio.com"