from autoflow.domain.models.models import DiscoveryResult, ModelTestResult, RemoteModel


class FakeCredentialStore:
    def __init__(self):
        self.values: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    def write(self, key: str, value: bytes) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)
        self.deleted.append(key)


class FakeModelGateway:
    def __init__(self):
        self.items = (
            RemoteModel("Model-A", "Model A", "fixture", 8192),
            RemoteModel("model-b", "Model B"),
        )
        self.fail = None

    async def discover(self, connection, secret):
        if self.fail:
            raise self.fail
        return DiscoveryResult(
            self.items, 1.25, "http://127.0.0.1:9999/v1/models", "连接正常"
        )

    async def test_model(self, connection, secret, model_key):
        if self.fail:
            raise self.fail
        return ModelTestResult(
            2.5, "http://127.0.0.1:9999/v1/chat/completions", "OK", "", "模型调用成功"
        )
