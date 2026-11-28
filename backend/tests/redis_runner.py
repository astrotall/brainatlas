from collections.abc import Sequence

import fakeredis

from neuroctivity.infrastructure.redis_scripts import Script


class FakeRedisRunner:
    def __init__(self, redis: fakeredis.FakeRedis | None = None) -> None:
        self.redis = redis or fakeredis.FakeRedis()

    async def run(self, script: Script, keys: Sequence[str], args: Sequence[str]) -> object:
        answer: object = self.redis.eval(script.source, len(keys), *keys, *args)
        return answer
