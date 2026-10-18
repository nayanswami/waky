from __future__ import annotations

import logging

LOGGER = logging.getLogger("waky")

SERVICE = "Waky"


def _keyring():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        if isinstance(keyring.get_keyring(), FailKeyring):
            # Packaged builds can miss entry-point metadata; pick the Windows backend explicitly.
            from keyring.backends.Windows import WinVaultKeyring

            keyring.set_keyring(WinVaultKeyring())
        return keyring
    except Exception:
        return None


def available() -> bool:
    return _keyring() is not None


def get(name: str) -> str:
    kr = _keyring()
    if kr is None:
        return ""
    try:
        return kr.get_password(SERVICE, name) or ""
    except Exception:
        LOGGER.warning("[SECRETS] could not read %s from credential store", name)
        return ""


def set(name: str, value: str) -> bool:
    """Store a secret in Windows Credential Manager. An empty value deletes it."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        if value:
            kr.set_password(SERVICE, name, value)
        else:
            try:
                kr.delete_password(SERVICE, name)
            except Exception:
                pass
        return True
    except Exception:
        LOGGER.warning("[SECRETS] could not write %s to credential store", name)
        return False
