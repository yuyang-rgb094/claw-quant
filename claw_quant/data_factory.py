"""Data provider factory — returns the appropriate DataProvider instance.

Usage:
    from claw_quant.data_factory import get_data_provider

    dp = get_data_provider('hybrid')     # Wind → AKShare → Synthetic (recommended)
    dp = get_data_provider('wind_first') # Same as 'hybrid'
    dp = get_data_provider('wind')       # Wind only (falls back to synthetic)
    dp = get_data_provider('akshare')    # AKShare only (falls back to synthetic)
    dp = get_data_provider('synthetic')  # Synthetic only (always available)
"""

from __future__ import annotations

from claw_quant.data_provider import DataProvider


def get_data_provider(name: str = "synthetic") -> DataProvider:
    """Return a DataProvider instance by name.

    Args:
        name: Provider name. Options:
            - 'hybrid' / 'wind_first': Wind → AKShare → Synthetic chain (recommended)
            - 'wind': Wind only (falls back to synthetic per-method)
            - 'akshare': AKShare only (free, requires network)
            - 'synthetic': Synthetic data (always available, for testing)

    Returns:
        A DataProvider instance.

    Raises:
        ValueError: If the provider name is not recognized.
        ImportError: If the provider's dependencies are not installed.
    """
    name = name.lower().strip()

    if name in ("hybrid", "wind_first"):
        from claw_quant.data_hybrid import HybridDataProvider
        return HybridDataProvider()

    elif name == "synthetic":
        from claw_quant.data_synthetic import SyntheticDataProvider
        return SyntheticDataProvider()

    elif name == "akshare":
        from claw_quant.data_akshare import AKShareDataProvider
        return AKShareDataProvider()

    elif name == "wind":
        from claw_quant.data_wind import WindDataProvider
        return WindDataProvider()

    else:
        raise ValueError(
            f"Unknown data provider: '{name}'. "
            f"Available providers: 'hybrid', 'wind_first', 'wind', 'akshare', 'synthetic'"
        )


def list_providers() -> list[str]:
    """List all available data provider names."""
    providers = ["synthetic", "hybrid", "wind_first"]

    try:
        import akshare  # noqa: F401
        providers.append("akshare")
    except ImportError:
        pass

    # Wind is always listed (requires external CLI installation)
    providers.append("wind")

    return providers