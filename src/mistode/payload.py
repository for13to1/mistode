"""Payload decoding and integrity errors for obfuscated artifacts.

The Python and C readers share one wire format (base64 or cipher output, then
zlib, then JSON) and one rule: a payload that cannot be decoded is an error.
Skipping it would drop records the token stream still expects, corrupting the
output instead of reporting the problem.
"""

import base64
import binascii
import json
import zlib
from typing import Any

ENCRYPTED_PAYLOAD = (
    "Encrypted payload: provide --password and the matching --cipher (default: stream)"
)
ENCRYPTED_METADATA = (
    "File is encrypted: provide --password and the matching --cipher (default: stream)"
)


class PayloadError(ValueError):
    """A payload could not be decoded; the message names the stage."""


def untokenisable(exc: BaseException) -> ValueError:
    """Build the error for a file that cannot be tokenised at all.

    Used at every entry point that tokenises an artifact, so a damaged file
    is reported for what it is rather than for the symptom the damage caused
    (a swallowed footer looks like missing metadata; a swallowed chunk looks
    like "not a Mistode artifact").
    """
    return ValueError(
        f"Obfuscated file does not tokenise ({exc}). Restore the "
        "original artifact, or re-obfuscate the source."
    )


def inconsistent(observed: str) -> ValueError:
    """Build the error for an artifact whose layout records do not add up.

    `observed` states what the reader found (counts of records and tokens);
    the rest of the message is shared so both readers report the same thing.
    """
    return ValueError(
        f"Obfuscated file is inconsistent: {observed}. A chunk marker was "
        "inserted or removed, so the file cannot be restored reliably. "
        "Restore the original artifact, or re-obfuscate the source."
    )


def not_an_artifact() -> ValueError:
    """Build the error for input that carries no layout records at all.

    Distinct from `inconsistent()`: nothing was inserted or removed here, so
    suggesting a damaged chunk would send the reader looking for one that
    never existed.
    """
    return ValueError("File does not appear to be obfuscated (no layout chunks found).")


def _decode(
    payload: str,
    secure: bool,
    cipher: Any | None,
    missing_password: str = ENCRYPTED_PAYLOAD,
) -> bytes:
    """Undo encryption or base64, then decompress."""
    if secure:
        if not cipher:
            # A missing password is a usage problem, not a corrupt payload,
            # so it surfaces unchanged.
            raise ValueError(missing_password)
        raw = cipher.decrypt(payload)
    else:
        raw = base64.b64decode(payload, validate=True)
    return zlib.decompress(raw)


def _decode_or_raise(
    payload: str,
    *,
    secure: bool,
    cipher: Any | None,
    template: str,
    missing_password: str = ENCRYPTED_PAYLOAD,
) -> Any:
    try:
        decoded = _decode(payload, secure, cipher, missing_password)
    except (binascii.Error, zlib.error) as exc:
        # Neither is a cipher failure: binascii.Error subclasses ValueError
        # and zlib.error does not, which is why both are caught explicitly
        # rather than relying on one `except ValueError`.
        raise PayloadError(template.format(exc=exc)) from exc
    try:
        return json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise PayloadError(template.format(exc=exc)) from exc


_CHUNK_TEMPLATE = (
    "Malformed chunk payload in obfuscated file: the @mistode marker is not "
    "valid layout data ({exc}). Restore the original artifact, or "
    "re-obfuscate the source."
)
_CHUNK_SHAPE = (
    "Malformed chunk payload in obfuscated file: decoded layout is not a "
    "list of layout records."
)
_METADATA_TEMPLATE = (
    "Malformed metadata payload in obfuscated file: the @mistode:metadata "
    "marker is not valid metadata ({exc})."
)


def decode_layouts(payload: str, *, secure: bool, cipher: Any | None) -> list[dict]:
    """Decode one chunk payload into its list of layout records."""
    layouts = _decode_or_raise(
        payload, secure=secure, cipher=cipher, template=_CHUNK_TEMPLATE
    )
    if not isinstance(layouts, list) or not all(
        isinstance(item, dict) for item in layouts
    ):
        raise PayloadError(_CHUNK_SHAPE)
    return layouts


def decode_metadata(payload: str, *, secure: bool, cipher: Any | None) -> dict:
    """Decode the embedded metadata payload."""
    metadata = _decode_or_raise(
        payload,
        secure=secure,
        cipher=cipher,
        template=_METADATA_TEMPLATE,
        missing_password=ENCRYPTED_METADATA,
    )
    if not isinstance(metadata, dict):
        raise PayloadError(_METADATA_TEMPLATE.format(exc="expected a JSON object"))
    return metadata
