from uuid import UUID

from neuroctivity.domain.review import Language


class NoopModerationNotifier:
    async def review_submitted(self, review_id: UUID, lang: Language) -> None:
        del review_id, lang
