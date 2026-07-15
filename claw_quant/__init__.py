"""Claw Quant — Multi-layer investment agent framework for A-share equities.

Architecture:
    Fisher (Layer 0) → SFM (Layer 1) → Graham (Layer 2) → Markowitz (Layer 3)
             ↑                                                     ↓
             └────────── Damodaran Cross-Section Supervisor ───────┘
"""

__version__ = "0.1.0"