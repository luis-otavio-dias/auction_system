from typing import TYPE_CHECKING

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from rest_framework.request import Request


class HealthCheckView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
