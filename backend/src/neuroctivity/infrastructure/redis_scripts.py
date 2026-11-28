from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Script:
    name: str
    source: str


CREATE_REVIEW = Script(
    "create_review",
    """
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
redis.call('HSET', KEYS[1], 'rating', ARGV[1], 'text', ARGV[2], 'lang', ARGV[3],
  'status', ARGV[4], 'created_at', ARGV[5])
redis.call('ZADD', KEYS[2], ARGV[5], ARGV[6])
return 1
""",
)

LIST_APPROVED = Script(
    "list_approved",
    """
local ids = redis.call('ZREVRANGE', KEYS[1], 0, tonumber(ARGV[1]) - 1)
local out = {}
for _, id in ipairs(ids) do
  table.insert(out, id)
  table.insert(out, redis.call('HGETALL', ARGV[2] .. id))
end
return out
""",
)

ACQUIRE_WINDOWS = Script(
    "acquire_windows",
    """
local n = #KEYS
for i = 1, n do
  local count = tonumber(redis.call('GET', KEYS[i]) or '0')
  if count >= tonumber(ARGV[i]) then return i end
end
for i = 1, n do
  redis.call('INCR', KEYS[i])
  if redis.call('TTL', KEYS[i]) < 0 then redis.call('EXPIRE', KEYS[i], ARGV[n + i]) end
end
return 0
""",
)

CLAIM_TOKEN = Script(
    "claim_token",
    """
if redis.call('SET', KEYS[1], '1', 'NX', 'EX', ARGV[1]) then return 1 end
return 0
""",
)
