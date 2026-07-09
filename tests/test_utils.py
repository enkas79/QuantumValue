"""
Test per il modulo utils (parsing, formattazione, gestione API key).

Autore: Enrico Martini
Versione: 0.7.14
"""

import os
import sys

import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import utils


# ---------------------------------------------------------------------------
# parse_to_float
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("100", 100.0),
    ("1,5", 1.5),
    ("2K", 2_000.0),
    ("1,5M", 1_500_000.0),
    ("3B", 3_000_000_000.0),
    ("$ 180", 180.0),
    ("12%", 12.0),
    ("-4,25", -4.25),
])
def test_parse_to_float_valid(raw, expected):
    assert utils.parse_to_float(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "   ", "abc", "12x", None])
def test_parse_to_float_invalid(raw):
    with pytest.raises(ValueError):
        utils.parse_to_float(raw)


# ---------------------------------------------------------------------------
# format_to_string
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    (1_500_000_000, "1,50B"),
    (2_000_000, "2,00M"),
    (1_230, "1,23K"),
    (12.3, "12,30"),
    (-2_500_000, "-2,50M"),
])
def test_format_to_string(value, expected):
    assert utils.format_to_string(value) == expected


def test_parse_format_roundtrip():
    assert utils.parse_to_float(utils.format_to_string(1_500_000.0)) == pytest.approx(1_500_000.0)


# ---------------------------------------------------------------------------
# encrypt/decrypt API key (offuscamento Fernet)
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    pytest.importorskip("cryptography")
    secret = "chiave-fmp-di-prova-123"
    encrypted = utils.encrypt_api_key(secret)
    assert encrypted != secret
    assert utils.decrypt_api_key(encrypted) == secret


# ---------------------------------------------------------------------------
# save/load/delete API key (portachiavi con fallback)
# ---------------------------------------------------------------------------

class FakeSettings:
    """QSettings finto basato su dizionario."""

    def __init__(self):
        self.store = {}

    def setValue(self, key, value):
        self.store[key] = value

    def value(self, key, default=None):
        return self.store.get(key, default)

    def remove(self, key):
        self.store.pop(key, None)


class FakeKeyring:
    """Backend keyring in memoria."""

    def __init__(self):
        self.store = {}

    def set_password(self, service, user, value):
        self.store[(service, user)] = value

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


class BrokenKeyring:
    """Backend keyring che fallisce sempre (es. nessun portachiavi di sistema)."""

    def set_password(self, *args):
        raise RuntimeError("Nessun backend disponibile")

    def get_password(self, *args):
        raise RuntimeError("Nessun backend disponibile")

    def delete_password(self, *args):
        raise RuntimeError("Nessun backend disponibile")


def test_api_key_keyring_roundtrip(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    settings = FakeSettings()

    utils.save_api_key(settings, "segreto")
    assert utils.load_api_key(settings) == "segreto"
    # Con il portachiavi disponibile QSettings non contiene la chiave
    assert "fmp_api_key" not in settings.store

    utils.delete_api_key(settings)
    assert utils.load_api_key(settings) == ""


def test_api_key_keyring_roundtrip_second_provider(monkeypatch):
    """Le chiavi di provider diversi (es. Twelve Data) sono indipendenti da FMP."""
    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    settings = FakeSettings()

    utils.save_api_key(settings, "fmp-segreto")
    utils.save_api_key(settings, "twelvedata-segreto", "twelvedata_api_key")

    assert utils.load_api_key(settings) == "fmp-segreto"
    assert utils.load_api_key(settings, "twelvedata_api_key") == "twelvedata-segreto"

    utils.delete_api_key(settings, "twelvedata_api_key")
    assert utils.load_api_key(settings, "twelvedata_api_key") == ""
    # La chiave FMP resta intatta
    assert utils.load_api_key(settings) == "fmp-segreto"


def test_api_key_fallback_qsettings(monkeypatch):
    pytest.importorskip("cryptography")
    monkeypatch.setitem(sys.modules, "keyring", BrokenKeyring())
    settings = FakeSettings()

    utils.save_api_key(settings, "segreto")
    # Fallback: la chiave e' salvata offuscata in QSettings
    assert settings.store.get("fmp_api_key") not in (None, "", "segreto")
    assert utils.load_api_key(settings) == "segreto"

    utils.delete_api_key(settings)
    assert utils.load_api_key(settings) == ""


def test_api_key_migration_from_legacy(monkeypatch):
    pytest.importorskip("cryptography")
    settings = FakeSettings()
    # Chiave legacy salvata offuscata in QSettings (portachiavi assente)
    settings.setValue("fmp_api_key", utils.encrypt_api_key("legacy-key"))

    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    # Il load migra la chiave nel portachiavi e ripulisce QSettings
    assert utils.load_api_key(settings) == "legacy-key"
    assert fake.get_password("QuantumValue", "fmp_api_key") == "legacy-key"
    assert "fmp_api_key" not in settings.store
