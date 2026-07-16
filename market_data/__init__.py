"""market_data — Fase A: descarga y almacenamiento versionado de OHLCV crudo
(Binance Futures), destino data/raw/.

Deliberadamente tonto: sin dedup, sin validación de sanity — eso es
responsabilidad exclusiva de dc_v1 (ver CLAUDE.md / TARGET_ARCHITECTURE.md).

El punto de entrada público (exports explícitos de client/storage/downloader)
se completa a medida que esos módulos se agregan; por ahora solo existe
config.py.
"""
