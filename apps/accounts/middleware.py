from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import translation


class UserLanguageMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            language = request.user.preferred_language
            translation.activate(language)
            request.LANGUAGE_CODE = language
        return self.get_response(request)
