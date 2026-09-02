from collections import defaultdict


class InMemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiries: dict[str, int] = {}
        self.sorted_sets: dict[str, dict[str, float]] = defaultdict(dict)
        self.streams: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        if ex is not None:
            self.expiries[key] = ex

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.values.get(key) for key in keys]

    def pipeline(self, transaction: bool = True):
        return InMemoryPipeline(self)


class InMemoryPipeline:
    def __init__(self, redis: InMemoryRedis) -> None:
        self.redis = redis
        self.commands: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    def zadd(self, key: str, mapping: dict[str, float]):
        self.commands.append(("zadd", key, mapping))
        return self

    def xadd(self, key: str, fields: dict[str, str], **kwargs):
        self.commands.append(("xadd", key, fields))
        return self

    def zremrangebyscore(self, key: str, minimum, maximum):
        self.commands.append(("zremrangebyscore", key, float(maximum)))
        return self

    def zcard(self, key: str):
        self.commands.append(("zcard", key))
        return self

    async def execute(self) -> list:
        results = []
        for command in self.commands:
            if command[0] == "zadd":
                _, key, mapping = command
                self.redis.sorted_sets[key].update(mapping)
                results.append(len(mapping))
            elif command[0] == "xadd":
                _, key, fields = command
                self.redis.streams[key].append(fields)
                results.append(str(len(self.redis.streams[key])))
            elif command[0] == "zremrangebyscore":
                _, key, maximum = command
                members = self.redis.sorted_sets[key]
                removed = [name for name, score in members.items() if score <= maximum]
                for name in removed:
                    del members[name]
                results.append(len(removed))
            elif command[0] == "zcard":
                _, key = command
                results.append(len(self.redis.sorted_sets[key]))
        return results


class RecordingStatusRepository:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def save_latest(self, **status) -> None:
        self.saved.append(status)
