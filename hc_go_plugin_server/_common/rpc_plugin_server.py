import datetime
from base64 import b64encode
from collections.abc import Callable
from concurrent import futures
from typing import Any

import grpc
import grpc.aio
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import ExtendedKeyUsage
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .. import grpc_controller_pb2_grpc
from ..health_servicer import _configure_health_server


class RPCPluginServerBase:
    _server_factory: Callable[..., Any]
    "*Must* be set by subclasses."
    _controller_servicer_factory: Callable[..., Any]
    "*Must* be set by subclasses."

    def __init__(self, port: str = "0"):
        self.cert, self.key = generate_server_cert()
        self.cert_base64 = encode_cert_base64(self.cert)
        server = self.__class__._server_factory(
            futures.ThreadPoolExecutor(max_workers=10)
        )
        grpc_controller_pb2_grpc.add_GRPCControllerServicer_to_server(  # type: ignore
            self.__class__._controller_servicer_factory(server), server
        )
        key_cert_pair_for_grpc = (
            self.key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            self.cert.public_bytes(serialization.Encoding.PEM),
        )
        creds = grpc.ssl_server_credentials([key_cert_pair_for_grpc])
        self.port = server.add_secure_port(f"127.0.0.1:{port}", creds)
        _configure_health_server(server)
        self.server = server


def generate_server_cert() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    # key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    # cert
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MyCompany"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=30)
        )
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=3)  # valid for 3 days
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                True, False, True, True, False, True, False, False, False
            ),
            critical=False,
        )
        .add_extension(
            ExtendedKeyUsage(
                [
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                    ExtendedKeyUsageOID.SERVER_AUTH,
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(True, None), critical=False)
        .sign(key, hashes.SHA256())  # sign w/ private key
    )
    return cert, key


def encode_cert_base64(cert: x509.Certificate) -> str:
    return b64encode(cert.public_bytes(serialization.Encoding.DER)).decode(
        "ascii"
    )


def print_handshake_response(port: str, cert_base64: str) -> None:
    print(f"1|6|tcp|127.0.0.1:{port}|grpc|{cert_base64}", flush=True)
