"""AI 跟唱 VAD 门控（stream_manager / pitchfix 共用）。"""

ULTRA_ATT = 0.105


def follow_vad_tick(
    mic_rms: float,
    open_gate: float,
    close_gate: float,
    att: float,
    was_open: bool,
    vad_above: int,
    vad_below: int,
    voice_off_at: float | None,
    voice_on_at: float | None,
    now: float,
) -> tuple[bool, int, int, float | None, float | None]:
    att = min(0.2, max(0.1, float(att or 0.1)))
    ultra = att <= ULTRA_ATT
    recent_on = voice_on_at is not None and (now - voice_on_at) < 1.0
    if mic_rms >= open_gate:
        vad_above = min(4, vad_above + 1)
    else:
        vad_above = max(0, vad_above - 1)
    if mic_rms >= close_gate:
        vad_below = 0
    elif was_open:
        vad_below = min(8, vad_below + 1)
    if was_open:
        if ultra:
            active = mic_rms >= close_gate
            if not active and voice_off_at is None:
                voice_off_at = now
            elif active:
                voice_off_at = None
        elif mic_rms >= close_gate:
            voice_off_at = None
            active = True
        else:
            if voice_off_at is None:
                voice_off_at = now
            hold = max(0.22, att * 2.2) if vad_below <= 2 else max(0.05, att * 1.0)
            active = (now - voice_off_at) < hold
    elif vad_above >= (1 if recent_on else 2) or (recent_on and mic_rms >= close_gate):
        voice_off_at = None
        active = True
    else:
        active = False
        voice_off_at = None
    if active:
        voice_on_at = now
    return active, vad_above, vad_below, voice_off_at, voice_on_at


def smooth_follow_gate(tgt: float, g: float, att: float) -> float:
    att = min(0.2, max(0.1, float(att or 0.1)))
    if tgt >= 0.5:
        g = g + (1.0 - g) * 0.5
    elif att <= ULTRA_ATT:
        g = 0.0
    else:
        g *= max(0.42, min(0.86, 0.48 + att * 1.35))
    return max(0.0, min(1.0, g))
