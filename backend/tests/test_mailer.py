import logging
import smtplib

import pytest

from app.core.config import settings
from app.services import mailer


class FakeSMTP:
    instances = []
    fail_on = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.logged_in = None
        self.sent = []
        FakeSMTP.instances.append(self)
        if FakeSMTP.fail_on == "connect":
            raise OSError("tidak bisa tersambung")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        if FakeSMTP.fail_on == "login":
            raise smtplib.SMTPAuthenticationError(535, b"salah")
        self.logged_in = (user, password)

    def send_message(self, msg):
        if FakeSMTP.fail_on == "send":
            raise smtplib.SMTPException("ditolak")
        self.sent.append(msg)


class ImmediateThread:
    started = []

    def __init__(self, target, args=(), daemon=None, **kw):
        self.target, self.args, self.daemon = target, args, daemon

    def start(self):
        ImmediateThread.started.append(self)
        self.target(*self.args)


@pytest.fixture(autouse=True)
def smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail_on, ImmediateThread.started = [], None, []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(settings, "smtp_host", "smtp.contoh.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "akun")
    monkeypatch.setattr(settings, "smtp_password", "sandi-smtp-rahasia")
    monkeypatch.setattr(settings, "smtp_from", "NARAtive <no-reply@narative.test>")


def test_without_a_smtp_host_the_email_is_only_logged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "")
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    mailer.send("rana@example.com", "Kode", "Kode kamu 123456")
    assert FakeSMTP.instances == [] and ImmediateThread.started == []
    assert any("rana@example.com" in r.getMessage() and "123456" in r.getMessage() for r in caplog.records)


def test_a_message_is_delivered_with_the_configured_server_and_credentials():
    mailer.send("rana@example.com", "Judul", "Isi pesan")
    [server] = FakeSMTP.instances
    assert (server.host, server.port) == ("smtp.contoh.com", 587)
    assert server.started_tls is True and server.logged_in == ("akun", "sandi-smtp-rahasia")
    [msg] = server.sent
    assert msg["To"] == "rana@example.com" and msg["From"] == "NARAtive <no-reply@narative.test>" and msg["Subject"] == "Judul"
    assert msg.get_content().strip() == "Isi pesan"


def test_it_does_not_log_in_when_no_user_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "")
    mailer.send("rana@example.com", "Judul", "Isi")
    assert FakeSMTP.instances[0].logged_in is None and len(FakeSMTP.instances[0].sent) == 1


def test_delivery_happens_in_a_background_thread():
    mailer.send("rana@example.com", "Judul", "Isi")
    [thread] = ImmediateThread.started
    assert thread.daemon is True


@pytest.mark.parametrize("stage", ["connect", "login", "send"])
def test_a_delivery_failure_never_reaches_the_caller(stage, caplog):
    FakeSMTP.fail_on = stage
    mailer.send("rana@example.com", "Judul", "Isi")
    assert any("rana@example.com" in r.getMessage() for r in caplog.records)


def test_the_smtp_password_never_appears_in_the_logs(caplog):
    FakeSMTP.fail_on = "login"
    caplog.set_level(logging.DEBUG)
    mailer.send("rana@example.com", "Judul", "Isi")
    assert "sandi-smtp-rahasia" not in caplog.text
