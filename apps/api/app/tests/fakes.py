from urllib.parse import parse_qs, urlparse

from app.core.email import EmailProvider


class FakeEmailProvider(EmailProvider):
    """Records every "sent" email in memory instead of talking to SMTP, so
    tests can assert on delivery and extract tokens embedded in links
    without needing a real mail server."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "text_body": text_body, "html_body": html_body})

    def last_token_for(self, to: str) -> str:
        for message in reversed(self.sent):
            if message["to"] == to:
                for line in message["text_body"].splitlines():
                    if "token=" in line:
                        url = line.split(": ", 1)[-1].strip()
                        query = parse_qs(urlparse(url).query)
                        return query["token"][0]
        raise AssertionError(f"No email with a token link was sent to {to}")
