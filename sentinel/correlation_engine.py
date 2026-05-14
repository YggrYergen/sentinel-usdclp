"""
SENTINEL v3 — Motor de Correlaciones Cross-Asset
Calcula correlaciones rolling entre USDCLP y los 8 instrumentos monitoreados.
Detecta divergencias y quiebres de correlación.
"""

import pandas as pd
import numpy as np
import logging
from sentinel.config import (
    EXPECTED_CORRELATIONS, CORRELATION_WINDOW, 
    CORRELATION_BREAK_THRESHOLD, DIVERGENCE_THRESHOLD
)

logger = logging.getLogger("sentinel.correlation")


def calculate_correlation_matrix(all_data: dict, window: int = None) -> pd.DataFrame:
    """
    Calcula la matriz de correlación rolling entre todos los instrumentos.
    
    Args:
        all_data: Dict[str, DataFrame] con datos OHLCV por instrumento
        window: Ventana para rolling correlation (default: config)
    
    Returns:
        DataFrame con correlaciones actuales
    """
    if window is None:
        window = CORRELATION_WINDOW
    
    # Extraer retornos logarítmicos del close de cada instrumento
    # NOTA: Yahoo Finance devuelve timestamps diferentes por ticker,
    # por lo que necesitamos normalizar los índices antes de alinear.
    closes = {}
    for key, df in all_data.items():
        if not df.empty and 'close' in df.columns:
            s = df['close'].copy()
            # Normalizar: si tiene timezone, convertir a UTC y quitar tz
            if hasattr(s.index, 'tz') and s.index.tz is not None:
                s.index = s.index.tz_convert('UTC').tz_localize(None)
            # Redondear timestamps a la hora más cercana para alinear
            s.index = s.index.round('h')
            # Eliminar duplicados por redondeo (quedarse con el último)
            s = s[~s.index.duplicated(keep='last')]
            closes[key] = s
    
    if len(closes) < 2:
        return pd.DataFrame()
    
    # Crear DataFrame alineado por inner join en timestamps normalizados
    closes_df = pd.DataFrame(closes)
    closes_df = closes_df.dropna()
    
    if len(closes_df) < 5:
        return pd.DataFrame()
    
    # Calcular retornos logarítmicos sobre los datos ya alineados
    returns_df = np.log(closes_df / closes_df.shift(1)).dropna()
    
    if len(returns_df) < window:
        # Si no hay suficientes datos, usar toda la ventana disponible
        return returns_df.corr()
    
    # Correlación de los últimos N periodos
    recent = returns_df.tail(window)
    corr_matrix = recent.corr()
    
    return corr_matrix


def calculate_target_correlations(all_data: dict, 
                                    target_key: str = "target") -> dict:
    """
    Calcula correlación de cada instrumento vs USDCLP (target).
    
    Returns:
        Dict con:
        - correlations: dict de correlaciones actuales
        - divergences: dict de divergencias vs esperado
        - breaks: lista de instrumentos con correlación rota
        - score: score de correlación 0-100
    """
    corr_matrix = calculate_correlation_matrix(all_data)
    
    if corr_matrix.empty or target_key not in corr_matrix.columns:
        return {
            "correlations": {},
            "divergences": {},
            "breaks": [],
            "score": 50,  # Neutral si no hay datos
            "direction": "NEUTRAL",
            "alerts": [],
        }
    
    target_corr = corr_matrix[target_key]
    
    correlations = {}
    divergences = {}
    breaks = []
    alerts = []
    
    for key in EXPECTED_CORRELATIONS:
        if key in target_corr.index and key != target_key:
            actual = target_corr[key]
            expected = EXPECTED_CORRELATIONS[key]
            
            correlations[key] = round(actual, 3)
            
            # Calcular divergencia vs esperado
            div = actual - expected
            divergences[key] = round(div, 3)
            
            # Detectar quiebre de correlación
            if abs(actual) < CORRELATION_BREAK_THRESHOLD and abs(expected) > 0.4:
                breaks.append(key)
                alerts.append(f"⚠️ QUIEBRE: {key} correlación actual={actual:.2f} vs esperada={expected:.2f}")
    
    # Calcular score de correlación (0-100)
    score = _calculate_correlation_score(all_data, correlations)
    direction = _determine_correlation_direction(all_data, correlations)
    
    return {
        "correlations": correlations,
        "divergences": divergences,
        "breaks": breaks,
        "score": score,
        "direction": direction,
        "alerts": alerts,
    }


def _calculate_correlation_score(all_data: dict, correlations: dict) -> float:
    """
    Calcula un score 0-100 basado en si las correlaciones confirman
    una dirección clara para USDCLP.
    
    Score alto = alta confluencia de señales correlacionadas
    Score bajo = señales contradictorias o correlaciones rotas
    """
    if not correlations or not all_data:
        return 50
    
    votes = []
    weights = {
        "dxy": 3.0,      # DXY es el driver principal
        "copper": 2.5,    # Cobre es crucial para Chile
        "usdmxn": 1.5,    # Peer LATAM
        "usdbrl": 1.5,    # Peer LATAM
        "wti": 1.0,
        "audusd": 1.0,
        "usdcnh": 1.0,
        "sp500": 0.5,
    }
    
    for key in correlations:
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 10:
            continue
        
        # Retorno reciente del instrumento (últimas 5 velas)
        recent_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) if len(df) >= 5 else 0
        
        # Según la correlación esperada, ¿qué dirección sugiere para USDCLP?
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        if expected > 0:
            # Correlación directa: si sube → USDCLP debería subir
            vote = 1 if recent_return > 0 else -1
        elif expected < 0:
            # Correlación inversa: si sube → USDCLP debería bajar
            vote = -1 if recent_return > 0 else 1
        else:
            vote = 0
        
        weight = weights.get(key, 1.0)
        votes.append(vote * weight)
    
    if not votes:
        return 50
    
    # Normalizar: si todos votan lo mismo → score alto
    total_weight = sum(weights.get(k, 1.0) for k in correlations if k in all_data)
    if total_weight == 0:
        return 50
    
    consensus = sum(votes) / total_weight
    # consensus va de -1 a +1. Convertir a 0-100
    # Alta confluencia (consensus cercano a ±1) → score alto
    score = 50 + (abs(consensus) * 50)
    
    return round(min(100, max(0, score)), 1)


def _determine_correlation_direction(all_data: dict, correlations: dict) -> str:
    """
    Determina la dirección sugerida por las correlaciones.
    LONG = correlaciones sugieren que USDCLP suba
    SHORT = correlaciones sugieren que USDCLP baje
    NEUTRAL = sin consenso claro
    """
    if not correlations or not all_data:
        return "NEUTRAL"
    
    bull_score = 0
    bear_score = 0
    
    for key in correlations:
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 5:
            continue
        
        recent_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1) if len(df) >= 5 else 0
        expected = EXPECTED_CORRELATIONS.get(key, 0)
        
        if expected > 0:
            if recent_return > DIVERGENCE_THRESHOLD:
                bull_score += abs(expected)
            elif recent_return < -DIVERGENCE_THRESHOLD:
                bear_score += abs(expected)
        elif expected < 0:
            if recent_return > DIVERGENCE_THRESHOLD:
                bear_score += abs(expected)
            elif recent_return < -DIVERGENCE_THRESHOLD:
                bull_score += abs(expected)
    
    diff = bull_score - bear_score
    if diff > 0.5:
        return "LONG"
    elif diff < -0.5:
        return "SHORT"
    return "NEUTRAL"


def detect_divergence(all_data: dict, target_key: str = "target") -> list:
    """
    Detecta divergencias cross-asset: cuando USDCLP NO se mueve
    en la dirección esperada según los otros instrumentos.
    
    Esta es la ventaja competitiva principal del sistema.
    
    Returns:
        Lista de divergencias detectadas con descripción.
    """
    divergences = []
    
    if target_key not in all_data or all_data[target_key].empty:
        return divergences
    
    target_df = all_data[target_key]
    if len(target_df) < 10:
        return divergences
    
    target_return = (target_df['close'].iloc[-1] / target_df['close'].iloc[-5] - 1)
    
    for key, expected_corr in EXPECTED_CORRELATIONS.items():
        if key not in all_data or all_data[key].empty:
            continue
        
        df = all_data[key]
        if len(df) < 5:
            continue
        
        other_return = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1)
        
        # Retorno esperado de USDCLP basado en este instrumento
        expected_target_direction = other_return * np.sign(expected_corr)
        
        # ¿Hay divergencia?
        if abs(other_return) > DIVERGENCE_THRESHOLD:
            if np.sign(expected_target_direction) != np.sign(target_return):
                magnitude = abs(other_return)
                direction = "SUBIR" if expected_target_direction > 0 else "BAJAR"
                
                divergences.append({
                    "instrument": key,
                    "instrument_move": f"{other_return*100:.2f}%",
                    "expected_usdclp": direction,
                    "actual_usdclp": f"{target_return*100:.2f}%",
                    "magnitude": magnitude,
                    "description": (
                        f"🔍 DIVERGENCIA: {key.upper()} se movió {other_return*100:+.2f}% "
                        f"→ USDCLP debería {direction} pero fue {target_return*100:+.2f}%"
                    )
                })
    
    # Ordenar por magnitud (más significativas primero)
    divergences.sort(key=lambda x: x['magnitude'], reverse=True)
    
    return divergences


# ══════════════════════════════════════════════════════════
# Real-time Correlation Confidence Tracker (3-layer system)
# ══════════════════════════════════════════════════════════

class RealtimeCorrelationTracker:
    """
    Tracks real-time correlation confidence per cross-asset using 3 layers:
      1. EWMA Correlation — dual-lambda: fast variance, slow covariance
      2. Sign Concordance — direction agreement ratio over rolling window
      3. Z-Score Breakdown — detects when relationship has shifted regime

    Calibrated for 2.5s refresh scalping (USDCLP vs DXY, copper, WTI, etc).
    Uses dual-lambda EWMA to combat the Epps effect (correlations → 0 at
    high frequency due to asynchronous trading and microstructure noise).

    References:
      - Epps effect: https://en.wikipedia.org/wiki/Epps_effect
      - Dual lambda: robotwealth.com, NYU Stern financial risk forecasting
      - Sign concordance: Stanford HFT research
    """

    def __init__(self, lambda_var: float = 0.85, lambda_cov: float = 0.97,
                 concordance_window: int = 60,
                 zscore_window: int = 50, breakdown_z: float = 2.0):
        # Dual lambda: fast for variance (react to vol spikes), slow for
        # covariance (stable correlation estimate despite tick noise)
        self.lam_var = lambda_var    # Fast: ~7 tick effective memory
        self.lam_cov = lambda_cov    # Slow: ~33 tick effective memory
        self.conc_win = concordance_window  # 60 ticks × 2.5s = 2.5 min
        self.z_win = zscore_window
        self.z_thresh = breakdown_z

        # Per-asset state
        self._ewma_var_t = {}   # EWMA variance of target returns
        self._ewma_var_a = {}   # EWMA variance of asset returns
        self._ewma_cov = {}     # EWMA covariance (slow lambda)
        self._ewma_corr = {}    # latest EWMA correlation
        self._sign_history = {} # list of agreement flags
        self._spread_history = {} # list of spread values for z-score
        self._update_count = {}  # warmup counter
        self._expected_sign = {} # +1 or -1 per asset

    # ── Public API ───────────────────────────────────────

    def update(self, asset_key: str, ret_target: float, ret_asset: float,
               expected_sign: float = 1.0):
        """
        Feed one refresh cycle of returns (bps or pct_change).

        Args:
            asset_key: e.g. "dxy", "copper"
            ret_target: USDCLP return this tick
            ret_asset: cross-asset return this tick
            expected_sign: +1 if direct correlation, -1 if inverse
        """
        # Guard: skip NaN / infinite (market closed, no data)
        if not np.isfinite(ret_target) or not np.isfinite(ret_asset):
            return

        # Initialize on first call
        if asset_key not in self._ewma_var_t:
            self._ewma_var_t[asset_key] = ret_target ** 2 + 1e-10
            self._ewma_var_a[asset_key] = ret_asset ** 2 + 1e-10
            self._ewma_cov[asset_key] = ret_target * ret_asset
            self._ewma_corr[asset_key] = 0.0
            self._sign_history[asset_key] = []
            self._spread_history[asset_key] = []
            self._update_count[asset_key] = 1
            self._expected_sign[asset_key] = expected_sign
            return

        self._update_count[asset_key] += 1

        # ── Layer 1: Dual-Lambda EWMA Correlation ──
        # Fast lambda for variance (track volatility changes quickly)
        lv = self.lam_var
        self._ewma_var_t[asset_key] = lv * self._ewma_var_t[asset_key] + (1 - lv) * (ret_target ** 2)
        self._ewma_var_a[asset_key] = lv * self._ewma_var_a[asset_key] + (1 - lv) * (ret_asset ** 2)

        # Slow lambda for covariance (stable correlation estimate)
        lc = self.lam_cov
        self._ewma_cov[asset_key] = lc * self._ewma_cov[asset_key] + (1 - lc) * (ret_target * ret_asset)

        # Correlation from separate variance/covariance estimates
        denom = np.sqrt(self._ewma_var_t[asset_key] * self._ewma_var_a[asset_key])
        if denom > 1e-12:
            self._ewma_corr[asset_key] = np.clip(self._ewma_cov[asset_key] / denom, -1.0, 1.0)
        else:
            self._ewma_corr[asset_key] = 0.0

        # ── Layer 2: Sign Concordance ──
        st = np.sign(ret_target) if abs(ret_target) > 1e-10 else 0
        sa = np.sign(ret_asset) if abs(ret_asset) > 1e-10 else 0
        if st != 0 and sa != 0:
            if expected_sign > 0:
                agree = 1 if st == sa else 0
            else:
                agree = 1 if st != sa else 0  # inverse: disagree = good
            self._sign_history[asset_key].append(agree)
        if len(self._sign_history[asset_key]) > self.conc_win:
            self._sign_history[asset_key] = self._sign_history[asset_key][-self.conc_win:]

        # ── Layer 3: Z-Score Spread ──
        spread = ret_target - expected_sign * ret_asset
        self._spread_history[asset_key].append(spread)
        if len(self._spread_history[asset_key]) > self.z_win * 2:
            self._spread_history[asset_key] = self._spread_history[asset_key][-(self.z_win * 2):]

    def get_confidence(self, asset_key: str) -> dict:
        """
        Returns correlation confidence for an asset.

        Returns dict with:
          - confidence: float 0-1 (composite score)
          - ewma_corr: float current EWMA correlation
          - concordance: float 0-1 direction agreement ratio
          - breakdown: bool whether z-score signals regime shift
          - z_score: float current z-score of spread
          - warmup: bool whether still warming up
          - updates: int number of updates received
        """
        n = self._update_count.get(asset_key, 0)
        warmup = n < 30  # ~75 seconds at 2.5s refresh

        # EWMA correlation
        ewma_c = self._ewma_corr.get(asset_key, 0.0)

        # Sign concordance
        sh = self._sign_history.get(asset_key, [])
        concordance = sum(sh) / len(sh) if len(sh) >= 8 else 0.5

        # Z-Score breakdown
        sp = self._spread_history.get(asset_key, [])
        z_score = 0.0
        breakdown = False
        if len(sp) >= self.z_win:
            recent = sp[-self.z_win:]
            mu = np.mean(recent)
            std = np.std(recent)
            if std > 1e-10:
                z_score = (sp[-1] - mu) / std
                breakdown = abs(z_score) > self.z_thresh

        # ── Composite confidence ──

        # Layer 1: Directional EWMA agreement with amplification.
        # For DIRECT corr (DXY, expected_sign=+1): positive ewma_corr = good
        # For INVERSE corr (copper, expected_sign=-1): negative ewma_corr = good
        # We multiply ewma_corr by expected_sign so that "agreement" is
        # always positive when the asset is behaving as expected.
        # Amplify ×2.5 to map tick-level [-0.3, +0.3] into [0, 1].
        exp_s = self._expected_sign.get(asset_key, 1.0)
        directed_corr = ewma_c * exp_s  # positive = behaving as expected
        ewma_agreement = min(1.0, max(0.0, directed_corr * 2.5 + 0.5))

        breakdown_penalty = 0.0 if breakdown else 1.0

        if warmup:
            confidence = 0.0
        else:
            confidence = (
                0.35 * ewma_agreement +
                0.45 * concordance +
                0.20 * breakdown_penalty
            )
            confidence = min(1.0, max(0.0, confidence))

        return {
            "confidence": round(confidence, 3),
            "ewma_corr": round(ewma_c, 4),
            "concordance": round(concordance, 3),
            "breakdown": breakdown,
            "z_score": round(z_score, 2),
            "warmup": warmup,
            "updates": n,
        }

    def get_all_confidence(self) -> dict:
        """Returns confidence dict for all tracked assets."""
        return {k: self.get_confidence(k) for k in self._update_count}

