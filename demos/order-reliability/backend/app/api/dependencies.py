from typing import Annotated

from fastapi import Depends, Request

from ..container import Lab


def get_lab(request: Request) -> Lab:
    return request.app.state.lab


LabDependency = Annotated[Lab, Depends(get_lab)]
