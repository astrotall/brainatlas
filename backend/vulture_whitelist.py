from neuroctivity.domain.review import Language
from neuroctivity.transport.errors import FieldError
from neuroctivity.transport.reviews import CreateReviewRequest, Review, ReviewListQuery
from neuroctivity.transport.visits import VisitStats

Language.RU
Language.EN

FieldError.field

CreateReviewRequest.rating
CreateReviewRequest.lang
CreateReviewRequest.turnstile_token

Review.id
Review.rating
Review.lang
Review.translated
Review.created_at

ReviewListQuery.lang
ReviewListQuery.limit

VisitStats.today
VisitStats.total
