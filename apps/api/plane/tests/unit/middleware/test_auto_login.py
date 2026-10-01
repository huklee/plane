# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Unit tests for AutoLoginMiddleware (single-user private instances).

- disabled unless AUTO_LOGIN_EMAIL is set
- signs an unauthenticated browser request in as the configured active user
- never signs in inactive or unknown users, never replaces an existing session
- leaves API-key requests (/api/v1/) alone
- signs god-mode (instances) requests in only for instance admins
"""

import pytest
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from plane.authentication.middleware.auto_login import AutoLoginMiddleware
from plane.authentication.middleware.session import SessionMiddleware
from plane.db.models import User
from plane.license.models import Instance, InstanceAdmin


def run(path, user=None):
    """Request through session + auth + auto-login middleware; returns request.user."""
    request = RequestFactory().get(path, HTTP_HOST="plane.example")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    AuthenticationMiddleware(lambda r: HttpResponse()).process_request(request)
    if user is not None:
        request.user = user
    seen = {}

    def view(req):
        seen["user"] = req.user
        return HttpResponse()

    AutoLoginMiddleware(view)(request)
    return seen["user"], request


@pytest.fixture
def auto_login(settings):
    settings.AUTO_LOGIN_EMAIL = "solo@plane.so"
    settings.WEB_URL = "https://plane.example"
    settings.APP_BASE_URL = "https://plane.example/plane/"
    return settings


@pytest.fixture
def solo(db):
    return User.objects.create_user(email="solo@plane.so", username="solo", password="Solo#2026x")


@pytest.mark.unit
class TestAutoLoginMiddleware:
    @pytest.mark.django_db
    def test_disabled_without_setting(self, settings, solo):
        settings.AUTO_LOGIN_EMAIL = ""
        user, _ = run("/api/users/me/")
        assert not user.is_authenticated

    @pytest.mark.django_db
    def test_signs_in_configured_user(self, auto_login, solo):
        user, request = run("/api/users/me/")
        assert user.is_authenticated and user.id == solo.id
        assert request.session.session_key  # persisted session -> cookie on the response

    @pytest.mark.django_db
    def test_email_match_is_case_insensitive(self, auto_login, solo):
        auto_login.AUTO_LOGIN_EMAIL = " Solo@Plane.so "
        user, _ = run("/api/users/me/")
        assert user.is_authenticated and user.id == solo.id

    @pytest.mark.django_db
    def test_inactive_or_unknown_user_is_not_signed_in(self, auto_login, solo):
        solo.is_active = False
        solo.save()
        assert not run("/api/users/me/")[0].is_authenticated
        auto_login.AUTO_LOGIN_EMAIL = "nobody@plane.so"
        assert not run("/api/users/me/")[0].is_authenticated

    @pytest.mark.django_db
    def test_existing_session_is_kept(self, auto_login, solo):
        other = User.objects.create_user(email="other@plane.so", username="other", password="Other#2026x")
        user, _ = run("/api/users/me/", user=other)
        assert user.id == other.id

    @pytest.mark.django_db
    def test_api_key_paths_are_skipped(self, auto_login, solo):
        user, _ = run("/api/v1/workspaces/w/projects/")
        assert not user.is_authenticated

    @pytest.mark.django_db
    def test_admin_paths_require_instance_admin(self, auto_login, solo):
        assert not run("/api/instances/admins/me/")[0].is_authenticated
        instance = Instance.objects.create(
            instance_name="t",
            instance_id="t-1",
            current_version="1",
            latest_version="1",
            last_checked_at="2026-01-01T00:00:00Z",
        )
        InstanceAdmin.objects.create(user=solo, instance=instance, role=20)
        user, _ = run("/api/instances/admins/me/")
        assert user.is_authenticated and user.id == solo.id
