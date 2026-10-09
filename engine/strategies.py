"""Compatibility shim for FoxCat Energy V1.2.0.

Les stratégies ont été séparées par mode dans ``engine/modes``. Ce module est
conservé pour éviter de casser un import interne ou un outil de diagnostic qui
utiliserait encore ``engine.strategies.evaluate_mode``.
"""

from .modes import evaluate_mode

__all__ = ["evaluate_mode"]
