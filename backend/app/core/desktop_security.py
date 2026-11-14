"""Authentication for the private Electron loopback sidecar only."""

import secrets

from starlette.responses import JSONResponse


DESKTOP_ORIGINS = ["app://localhost", "http://127.0.0.1:5174", "http://localhost:5174"]


class DesktopTokenMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.expected = token.encode("utf-8")
        if len(self.expected) < 32:
            raise RuntimeError("Desktop authentication token is missing or too short.")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            values = [value for key, value in scope.get("headers", ()) if key.lower() == b"x-devharbor-token"]
            supplied = values[0] if len(values) == 1 else b""
            if not secrets.compare_digest(supplied, self.expected):
                await JSONResponse(status_code=401, content={"detail": "桌面连接验证失败，请重新打开应用。"})(scope, receive, send)
                return
        await self.app(scope, receive, send)
