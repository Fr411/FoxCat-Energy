"""ACK LOGO et disponibilité de la commande onduleur (retour physique NQ9..NQ12)."""
import importlib.util
import sys
from pathlib import Path

path = Path(__file__).parents[1] / "custom_components" / "foxcat_energy" / "domain" / "engine" / "pri_feedback.py"
spec = importlib.util.spec_from_file_location("pri_feedback_under_test", path)
pf = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pf
spec.loader.exec_module(pf)


def test_feedback_code_reads_bits_l4_to_l1():
    assert pf.feedback_code(["on", "off", "off", "on"]) == "1001"
    assert pf.feedback_code(["off"] * 4) == "0000"


def test_feedback_code_not_configured_and_unreadable():
    assert pf.feedback_code(None) is None
    assert pf.feedback_code(["on", "unavailable", "off", "off"]) == "????"
    assert pf.feedback_code(["on", "unknown", "off", "off"]) == "????"
    assert pf.feedback_code(["on", None, "off", "off"]) == "????"


def test_ack_logo_ok_failed_absent_and_not_configured():
    assert pf.classify_ack_logo("0101", "0101") == pf.ACK_LOGO_OK
    assert pf.classify_ack_logo("0101", "0100") == pf.ACK_LOGO_FAILED
    assert pf.classify_ack_logo("0101", "????") == pf.ACK_LOGO_ABSENT
    assert pf.classify_ack_logo("0101", None) == pf.ACK_LOGO_NOT_CONFIGURED
    assert pf.classify_ack_logo(None, "0101") == pf.ACK_LOGO_ABSENT


def test_command_blocked_only_when_feedback_unreadable():
    assert pf.command_blocked(pf.AVAILABILITY_DOWN) is True
    assert pf.command_blocked(pf.AVAILABILITY_DEGRADED) is False
    assert pf.command_blocked(pf.AVAILABILITY_OK) is False
    assert pf.command_blocked(pf.AVAILABILITY_NOT_CONFIGURED) is False
    assert pf.command_blocked(None) is False


def test_logo_online_overrides_feedback():
    assert pf.command_availability("0000", None, "on") == pf.AVAILABILITY_OK
    assert pf.command_availability("0000", None, "off") == pf.AVAILABILITY_DOWN
    assert pf.command_availability("0000", None, "unavailable") == pf.AVAILABILITY_DOWN
    assert pf.command_availability("0000", "0000", "off") == pf.AVAILABILITY_DOWN
    assert pf.command_availability("0000", "0001", "on") == pf.AVAILABILITY_DEGRADED
    assert pf.command_availability("0000", "0000", "on") == pf.AVAILABILITY_OK
    assert pf.command_availability("0000", None, None) == pf.AVAILABILITY_NOT_CONFIGURED


def test_command_availability_states():
    assert pf.command_availability("0000", None) == pf.AVAILABILITY_NOT_CONFIGURED
    assert pf.command_availability("0000", "????") == pf.AVAILABILITY_DOWN
    assert pf.command_availability("0000", "0000") == pf.AVAILABILITY_OK
    assert pf.command_availability("0000", "0001") == pf.AVAILABILITY_DEGRADED
    assert pf.command_availability("????", "0001") == pf.AVAILABILITY_DEGRADED
