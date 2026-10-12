from fastapi import Request

from ..container import Container


def container_of(request: Request) -> Container:
    return request.app.state.container
