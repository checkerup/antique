"""SSRF guard tests for outbound URL validation.

Validates the reusable ``validate_outbound_url`` guard that protects
provider and webhook fetches from SSRF attacks targeting internal
addresses, cloud metadata endpoints, and link-local ranges.
"""
import pytest

from src.core.outbound_guard import (
    SSRFError,
    validate_outbound_url,
    is_safe_outbound_url,
)


class TestSchemeValidation:
    def test_https_allowed(self):
        assert validate_outbound_url("https://api.example.com/webhook") is not None

    def test_http_allowed(self):
        # http is allowed for self-hosted/local provider endpoints
        assert validate_outbound_url("http://self-hosted.example.com:8080/pool") is not None

    def test_file_scheme_rejected(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_outbound_url("file:///etc/passwd")

    def test_ftp_rejected(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_outbound_url("ftp://example.com/x")

    def test_gopher_rejected(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_outbound_url("gopher://example.com/x")

    def test_javascript_rejected(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_outbound_url("javascript:alert(1)")

    def test_data_uri_rejected(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_outbound_url("data:text/plain,hello")


class TestMissingHost:
    def test_empty_url_rejected(self):
        with pytest.raises(SSRFError, match="empty"):
            validate_outbound_url("")

    def test_none_url_rejected(self):
        with pytest.raises(SSRFError, match="empty"):
            validate_outbound_url(None)  # type: ignore

    def test_no_host_rejected(self):
        with pytest.raises(SSRFError, match="host"):
            validate_outbound_url("https:///path/only")

    def test_scheme_relative_rejected(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("//evil.com/path")


class TestCloudMetadataBlocked:
    """The 169.254.169.254 cloud-metadata endpoint must always be blocked."""

    def test_aws_metadata_ipv4(self):
        with pytest.raises(SSRFError, match="metadata|internal|link.local|169"):
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")

    def test_aws_metadata_with_port(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://169.254.169.254:80/latest/meta-data/")

    def test_gcp_metadata(self):
        # GCP metadata uses 169.254.169.254 as well, and also metadata.google.internal
        with pytest.raises(SSRFError):
            validate_outbound_url("http://metadata.google.internal/computeMetadata/")

    def test_azure_metadata(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://169.254.169.254/metadata/instance?api-version=2021-02-01")


class TestLoopbackBlocked:
    """Loopback addresses must be blocked to prevent internal port scanning."""

    def test_localhost_blocked(self):
        with pytest.raises(SSRFError, match="loopback|internal"):
            validate_outbound_url("http://localhost:8080/admin")

    def test_127_ip_blocked(self):
        with pytest.raises(SSRFError, match="loopback|internal"):
            validate_outbound_url("http://127.0.0.1:8080/admin")

    def test_127_subrange_blocked(self):
        with pytest.raises(SSRFError, match="loopback|internal"):
            validate_outbound_url("http://127.0.0.2:8080/admin")

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(SSRFError, match="loopback|internal"):
            validate_outbound_url("http://[::1]:8080/admin")


class TestPrivateRangesBlocked:
    """RFC 1918 private ranges must be blocked."""

    def test_10_range_blocked(self):
        with pytest.raises(SSRFError, match="private|internal"):
            validate_outbound_url("http://10.0.0.1/internal")

    def test_172_16_range_blocked(self):
        with pytest.raises(SSRFError, match="private|internal"):
            validate_outbound_url("http://172.16.0.1/internal")

    def test_172_31_range_blocked(self):
        with pytest.raises(SSRFError, match="private|internal"):
            validate_outbound_url("http://172.31.0.1/internal")

    def test_192_168_range_blocked(self):
        with pytest.raises(SSRFError, match="private|internal"):
            validate_outbound_url("http://192.168.1.1/admin")

    def test_172_outside_private_allowed(self):
        # 172.15.x.x is NOT in the 172.16/12 range
        assert validate_outbound_url("http://172.15.0.1/pool") is not None

    def test_172_32_allowed(self):
        # 172.32.x.x is NOT in the 172.16/12 range
        assert validate_outbound_url("http://172.32.0.1/pool") is not None


class TestLinkLocalBlocked:
    """169.254.x.x link-local must be blocked."""

    def test_link_local_blocked(self):
        with pytest.raises(SSRFError, match="link.local|169"):
            validate_outbound_url("http://169.254.1.1/test")

    def test_link_local_upper_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://169.254.254.254/test")


class TestCarrierGradeNATBlocked:
    """100.64.0.0/10 (CGNAT) must be blocked."""

    def test_cgnat_blocked(self):
        with pytest.raises(SSRFError, match="private|internal|reserved"):
            validate_outbound_url("http://100.64.0.1/test")


class TestSpecialUseBlocked:
    """0.0.0.0, test-net, multicast, etc."""

    def test_all_zeros_blocked(self):
        with pytest.raises(SSRFError, match="reserved|unspecified|0\\.0\\.0\\.0"):
            validate_outbound_url("http://0.0.0.0/")

    def test_test_net_1_blocked(self):
        # 192.0.2.0/24 is TEST-NET-1
        with pytest.raises(SSRFError, match="reserved|test"):
            validate_outbound_url("http://192.0.2.1/")

    def test_ipv6_link_local_blocked(self):
        with pytest.raises(SSRFError, match="link.local|reserved"):
            validate_outbound_url("http://[fe80::1]/")


class TestPublicUrlsAllowed:
    def test_normal_https(self):
        assert validate_outbound_url("https://discord.com/api/webhooks/123") is not None

    def test_normal_http_with_port(self):
        assert validate_outbound_url("http://api.example.com:9000/v1/proxies") is not None

    def test_normal_domain(self):
        assert validate_outbound_url("https://vendor.proxy-provider.com/pool?limit=10") is not None


class TestBypassAttempts:
    """Ensure common SSRF bypass tricks are blocked."""

    def test_localhost_substring_blocked(self):
        """localhost.evil.com is a public domain, not localhost — it passes.
        The guard blocks the literal host 'localhost', not substring matches.
        (This is the correct behavior: localhost.evil.com resolves to a
        public IP, which is not a SSRF target.)
        """
        # localhost.evil.com is NOT localhost — it's a domain name
        assert validate_outbound_url("http://localhost.evil.com/admin") is not None

    def test_decimal_ip_localhost(self):
        # 127.0.0.1 = 2130706433 in decimal
        with pytest.raises(SSRFError):
            validate_outbound_url("http://2130706433/")

    def test_hex_ip_localhost(self):
        # 127.0.0.1 = 0x7f000001
        with pytest.raises(SSRFError):
            validate_outbound_url("http://0x7f000001/")

    def test_octal_ip_localhost(self):
        # 127.0.0.1 = 0177.0.0.1 in octal
        with pytest.raises(SSRFError):
            validate_outbound_url("http://0177.0.0.1/")

    def test_ipv6_mapped_ipv4_localhost(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://[::ffff:127.0.0.1]/")

    def test_ipv6_mapped_ipv4_private(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://[::ffff:10.0.0.1]/")

    def test_zero_short_form_localhost(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://0/")

    def test_url_with_credentials(self):
        # URL with userinfo portion — should still resolve host
        with pytest.raises(SSRFError):
            validate_outbound_url("http://user:pass@127.0.0.1/admin")


class TestIsSafeOutboundUrl:
    """Boolean convenience wrapper — never raises."""

    def test_safe_url_true(self):
        assert is_safe_outbound_url("https://api.example.com/webhook") is True

    def test_metadata_false(self):
        assert is_safe_outbound_url("http://169.254.169.254/latest/") is False

    def test_empty_false(self):
        assert is_safe_outbound_url("") is False

    def test_invalid_scheme_false(self):
        assert is_safe_outbound_url("file:///etc/passwd") is False


class TestDNSAndRedirectValidation:
    def test_domain_resolving_private_is_rejected(self, monkeypatch):
        import socket
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ])
        with pytest.raises(SSRFError, match="resolves to blocked"):
            validate_outbound_url("http://attacker.invalid/path", resolve_dns=True)

    def test_mixed_public_private_answers_are_rejected(self, monkeypatch):
        import socket
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
        ])
        with pytest.raises(SSRFError, match="blocked"):
            validate_outbound_url("https://attacker.invalid/", resolve_dns=True)

    def test_redirect_handler_rejects_private_location(self):
        from src.core.outbound_guard import SafeRedirectHandler
        with pytest.raises(SSRFError):
            SafeRedirectHandler().redirect_request(
                None, None, 302, "Found", {}, "http://127.0.0.1/admin"
            )
