# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Single-user auto login for private, self-hosted instances.

When AUTO_LOGIN_EMAIL is set, any browser request without an authenticated session is
signed in as that (active) user, so the sign-in screen never appears. Admin (god-mode)
paths are signed in only when the user is an instance admin. API-key requests
(/api/v1/) are left alone.

Everyone who can reach the instance acts as this user: only enable it behind a network
boundary you trust (e.g. a tailnet-only front proxy).
"""

import logging

from django.conf import settings

from plane.authentication.utils.login import user_login

logger = logging.getLogger("plane.authentication")

SKIP_PREFIXES = ("/api/v1/", "/static/")


def is_admin_path(path: str) -> bool:
    # Same rule SessionMiddleware uses to pick the admin session cookie
    return "instances" in path


class AutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.email = (getattr(settings, "AUTO_LOGIN_EMAIL", "") or "").strip().lower()
        if self.email:
            logger.warning("AUTO_LOGIN_EMAIL is set: unauthenticated requests are signed in as %s", self.email)

    def __call__(self, request):
        if self.email and not request.user.is_authenticated and not request.path.startswith(SKIP_PREFIXES):
            self._login(request)
        return self.get_response(request)

    def _login(self, request):
        from plane.db.models import User
        from plane.license.models import InstanceAdmin

        user = User.objects.filter(email=self.email, is_active=True).first()
        if user is None:
            return
        admin = is_admin_path(request.path)
        if admin and not InstanceAdmin.objects.filter(user=user).exists():
            return
        user_login(request=request, user=user, is_app=not admin, is_admin=admin)
