from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lnbot")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .client import AsyncLnBot, LnBot
from .errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LnBotError,
    NotFoundError,
    UnauthorizedError,
)
from .types import (
    AddressInvoiceResponse,
    AddressResponse,
    ApiKeyResponse,
    BackupPasskeyBeginResponse,
    CreateWalletResponse,
    CreateWebhookResponse,
    InvoiceEvent,
    InvoiceResponse,
    InvoiceStatus,
    PaymentEvent,
    PaymentResponse,
    PaymentStatus,
    RecoveryBackupResponse,
    RecoveryRestoreResponse,
    RestorePasskeyBeginResponse,
    RestorePasskeyCompleteResponse,
    RotateApiKeyResponse,
    TransactionResponse,
    TransactionType,
    TransferAddressResponse,
    WalletResponse,
    WebhookResponse,
)

__all__ = [
    "__version__",
    "LnBot",
    "AsyncLnBot",
    "LnBotError",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "WalletResponse",
    "CreateWalletResponse",
    "ApiKeyResponse",
    "RotateApiKeyResponse",
    "InvoiceResponse",
    "InvoiceStatus",
    "InvoiceEvent",
    "AddressInvoiceResponse",
    "PaymentResponse",
    "PaymentStatus",
    "PaymentEvent",
    "AddressResponse",
    "TransferAddressResponse",
    "TransactionResponse",
    "TransactionType",
    "CreateWebhookResponse",
    "WebhookResponse",
    "RecoveryBackupResponse",
    "RecoveryRestoreResponse",
    "BackupPasskeyBeginResponse",
    "RestorePasskeyBeginResponse",
    "RestorePasskeyCompleteResponse",
]
