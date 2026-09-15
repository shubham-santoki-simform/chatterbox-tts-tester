"""Map the bridge's clinical distress vocabulary onto Chatterbox's generation knobs.

The HS voice bridge already classifies each scenario's own chart text into a `kind`
("none" | "pain" | "breathless" | "fatigue") plus a graded `pain` intensity 0.0-1.0, and
forwards both to /api/tts. It was written FOR this engine -- see the "Graded distress, for
the expressive (Chatterbox) TTS engine" section in hs-voice-bridge/bridge.py. This module is
the other half of that contract.

Chatterbox has no categorical emotion parameter. What it has is:
  exaggeration  0.25..2.0  emotional INTENSITY (0.5 neutral)
  cfg_weight    0.0..1.0   pacing / deliberateness (lower = slower, more measured)
  temperature              delivery variability
so a named clinical state is a POINT in that space, not a parameter value.

Two non-obvious things drive the curves below, both taken from the bridge's own reasoning:

  * Fatigue is FLAT -- under-expressive, not over. Every other distress kind pushes
    exaggeration UP as it worsens; fatigue pushes it DOWN, below neutral. A tired patient is
    not a dramatic patient. Getting this backwards makes an exhausted patient sound theatrical.
  * Higher exaggeration speeds Chatterbox up. That is a documented coupling, not a quirk. So
    any preset that raises exaggeration must LOWER cfg_weight to keep the pacing believable,
    which is why cfg falls as intensity rises for pain and breathlessness.
"""

from __future__ import annotations

# Chatterbox's own documented bounds. Values outside these are clamped rather than rejected:
# the operator drawer is a live demo control and must never 500 mid-sentence.
EXAG_MIN, EXAG_MAX = 0.25, 2.0
# CFG_MIN is 0.05, NOT 0.0. Chatterbox generation FAILS at cfg_weight=0.0 -- /api/tts returns 502 and
# the patient goes silent mid-sentence. 0.0 was advertised as draggable, so pulling the panel's
# "pacing" slider fully left broke the voice with no visible cause. Measured 2026-07-29: cfg 0.0 ->
# 502 at every exaggeration tried, cfg 0.05 -> 200. The panel reads its slider range from bounds()
# below, so raising the floor here fixes the API clamp AND the UI together, with no frontend rebuild.
CFG_MIN, CFG_MAX = 0.05, 1.0
TEMP_MIN, TEMP_MAX = 0.05, 1.5

NEUTRAL = {"exaggeration": 0.45, "cfg_weight": 0.50, "temperature": 0.80}

# kind -> (exag_at_0, exag_at_1, cfg_at_0, cfg_at_1)
# Endpoints are linearly interpolated by `pain`. Note fatigue's exaggeration ramp runs
# DOWNWARD (0.42 -> 0.20) for the reason in the module docstring.
_CURVES = {
    "none":       (0.45, 0.45, 0.50, 0.50),
    # PAIN'S EXAGGERATION CEILING IS DELIBERATELY LOW (was 1.25, lowered to 0.80 on 2026-07-30).
    # Reported at 1.25: the patient read as ANGRY, not hurting. That is the predictable failure --
    # `exaggeration` is raw INTENSITY, and loud + pressed + fast is exactly what anger is. Measured
    # at 1.25 the output was +32.5% LOUDER than calm, and loudness is the single cue that separates
    # the two: anger and pain share raised pitch, but pain is quiet, depleted and halting while anger
    # projects. Pushing intensity therefore walks the voice toward anger no matter how good the
    # reference clip is, so pain must get its character from the CLIP (weak, breathy, wincing) and
    # only a modest intensity nudge from the dial. If pain ever needs to read stronger, add
    # brokenness and breathiness to refs\*_pain.wav -- do NOT raise this back up.
    # Ceiling walked DOWN twice by operator ear: 1.25 (read as ANGRY) -> 0.80 (read as WORRIED)
    # -> 0.62. Each report named a different neighbour and each needed a different axis:
    #   vs ANGER  -- separate on EFFORT. Anger projects; pain is quiet. Fixed by dropping intensity.
    #   vs WORRY  -- separate on PITCH MOVEMENT. Anxiety is fluttery, fast and rising, with lots of
    #                pitch excursion; pain is flatter, slower and ROUGH, with falling contours and
    #                breath catches. `exaggeration` drives pitch excursion, so at 0.80 the voice was
    #                still darting around (+137% pitch range over calm) and that reads as worried.
    # Pain is therefore the LEAST exaggerated of the distress kinds, not the most -- its signature is
    # roughness and interruption, which live in the reference clip, not in this dial.
    # Ceiling history, each step driven by an operator ear report naming a DIFFERENT neighbour:
    #   1.25 -> read as ANGRY    (loud + pressed)          -> dropped to 0.80
    #   0.80 -> read as WORRIED  (fluttery pitch movement) -> dropped to 0.62
    #   0.62 -> read as SARCASTIC                          -> RAISED to 1.15, see below
    #
    # SARCASM was self-inflicted and is the most instructive of the three. Its signature is
    # drawn-out vowels + slow deliberate pacing + flat affect, and that is precisely what
    # cfg_weight 0.30 (very measured) plus a low intensity plus a reference clip of "Mmmh... ohhh"
    # produces: "ohhh, riiight." Chasing away anger and worry walked straight into it.
    #
    # EXCRUCIATING pain is not a quieter version of moderate pain -- it is a different signal:
    #   * high EFFORT (vocal strain raises pitch), so exaggeration goes back up
    #   * but FRAGMENTED, not fluent -- which is what keeps it clear of anger. Anger is high-effort
    #     AND sustained AND articulate; severe pain cannot finish a sentence.
    #   * vowels SHORTEN into sharp involuntary bursts. Lengthening them is the sarcasm/comfortable-
    #     moaning direction. This is the inversion that matters most.
    #   * cfg comes UP off 0.30 because "measured" is the sarcastic quality; severe pain is not
    #     measured, it is interrupted.
    # The anger guard is therefore no longer an exaggeration ceiling -- it is cfg_weight, which is
    # what actually separates them (anger 0.74 fast/fluent vs pain 0.39 broken).
    # rev6 (2026-07-30): rev5's excruciating read as TOO MUCH. Target is now moderate -- clearly
    # audible in the voice and the speech pattern, but a patient who can still hold a conversation.
    #
    # ⚠️ HOW TO TONE PAIN DOWN WITHOUT RE-CREATING THE SARCASM. Turning intensity down is exactly
    # what produced the sarcastic reading at rev3-4, but intensity was NOT the cause -- the cause was
    # slow measured pacing (cfg 0.30) plus lengthened vowels. So intensity comes down while cfg moves
    # UP, further from the drawl floor, not toward it:
    #     rev4 (sarcastic)   exag 0.599  cfg 0.327   <- low intensity AND slow = sarcasm
    #     rev5 (too much)    exag 1.083  cfg 0.391
    #     rev6 (moderate)    exag 0.875  cfg 0.426   <- lower intensity, FASTER pacing
    # Everything that made rev5 read as real pain is kept: fragmented delivery, short sharp vowels,
    # and the vocal roughness (jitter) that finally survived cloning. Only the volume of the
    # performance is reduced, which is the difference between a 9/10 and a 6/10 patient.
    # rev7 (2026-07-30): rev6 read as too HAPPY. Cause is visible in the numbers -- pitch RANGE was
    # +37.9% over calm while pitch HEIGHT was only +4.8%. Wide melodic excursion with no elevation is
    # an ANIMATED, engaged profile, which is most of what makes a voice sound cheerful (the happy clip
    # measures +56% range). `exaggeration` is what drives that excursion, so the ceiling comes down
    # again -- but cfg stays at 0.42, because dropping BOTH is what produced sarcasm at rev4.
    #
    # Operator also asked for a tinge of IRRITATION or SADNESS from the pain, i.e. pain should carry a
    # negative affect rather than neutral discomfort. That is mostly the reference clip's job (weary,
    # fed-up wording, closed nasal groans), but a narrower pitch range helps here too: sadness and
    # irritation are both LESS melodically varied than cheerfulness, not more.
    "pain":       (0.58, 0.78, 0.46, 0.42),
    # BREATHLESS, revised 2026-08-06 after a blind listening test failed it on BOTH patients tried
    # (Harold heard "anxious", Ray heard "angry"; both wrote "speaking way too quickly").
    # The old ceiling of 0.95 made breathlessness the SECOND most exaggerated kind in the whole set,
    # above `anxious` (0.824) -- so the dial was asserting more emotional intensity for a patient who
    # cannot breathe than for one having an anxiety response. Since exaggeration also SPEEDS
    # Chatterbox up (documented at the top of this file), that single number produced both complaints
    # at once: too intense AND too fast.
    #
    # Breathlessness is not a strong EMOTION, it is a physical impairment. Its cues are pause
    # structure and audible inhalation, neither of which lives on these dials -- so the right move is
    # to stop over-driving intensity and let the reference clip carry it. cfg also comes down a
    # little so the speech that survives between breaths is not hurried.
    #
    # ⚠️ THE DIAL WAS ONLY HALF THE FAULT. Measured on the reference clips themselves, breathless is
    # SHORTER than calm with LESS pause time (Harold 4.24s vs 5.12s, pause -27.9%; Ray 4.32s vs
    # 4.56s). A breathless clip with fewer pauses than a calm one cannot sound breathless at any dial
    # setting. Regenerating those clips with real breath groups is the other half of this fix.
    "breathless": (0.45, 0.60, 0.42, 0.24),
    # FATIGUE'S PACING WAS INVERTED, fixed 2026-08-06. The exaggeration ramp running DOWNWARD is
    # correct and long-documented (a tired patient is under-expressive, not dramatic) -- that is not
    # what was wrong. The bug was cfg_weight rising 0.52 -> 0.55, which made a MORE tired patient
    # speak FASTER, and left `drowsy` at 0.546 -- more hurried than `calm` at 0.500 and the third
    # fastest preset overall. Nobody had questioned the cfg direction because the exaggeration
    # inversion was the famous part of this curve.
    #
    # Consequence in a blind test: drowsy was heard as "calm" (Ray) and "need to slow down and allow
    # for pauses" (both), while `sad` -- which IS slow at 0.362 -- was heard as "drowsy" by both
    # patients. The two had effectively swapped places on the one axis that separates them.
    # Drowsy is now the slowest preset in the set, which is what tiredness actually sounds like.
    "fatigue":    (0.42, 0.20, 0.50, 0.20),
    # Operator-only. The bridge never emits this kind -- it classifies chart text, and confusion
    # is not a charted symptom the way pain or dyspnea are. It exists because a "Confused" preset
    # built on the flat "none" curve came out byte-identical to "Calm", i.e. a dead button.
    # Hesitancy is not INTENSITY, it is PACING: neutral exaggeration with cfg_weight pulled well
    # down reads as halting and searching rather than distressed.
    "hesitant":   (0.44, 0.52, 0.40, 0.24),

    # ---- GENERAL AFFECT, added 2026-07-30 for the voice-testing lab ----------------------------
    # Everything above is CLINICAL (what a chart can imply). These are general affect, which the
    # bridge never emits -- no chart says "happy" -- so they are lab/operator-only.
    #
    # Each one is defined against the neighbour it is most likely to be MISTAKEN FOR, because that
    # is the only thing that turned out to matter: `pain` needed four revisions purely because it
    # kept landing on anger (shared raised pitch) and then on worry (shared pitch movement).
    #
    # happy  vs EXCITED/manic -- both raise pitch. Excitement is fast AND loud; warmth is neither.
    #        So intensity stays moderate and pacing stays near normal. A happy patient who talks
    #        fast reads as manic, which is not the same clinical picture at all.
    "happy":      (0.55, 0.85, 0.55, 0.62),
    # sad    vs FATIGUE -- both are low, slow and quiet. The separator is CONTOUR, not level: sadness
    #        still has emotional movement (it falls away at the end of phrases) whereas fatigue is
    #        simply flat. So exaggeration drops but stays ABOVE fatigue's 0.20 floor, and pacing goes
    #        slower than fatigue rather than equal to it.
    "sad":        (0.42, 0.32, 0.45, 0.34),
    # angry  vs IN PAIN -- the pair that actually bit us. They share raised pitch and raised
    #        loudness, and separate on PACING: anger is fast and clipped, pain is slow and halting.
    #        So anger is the ONLY kind whose cfg_weight rises with intensity; every distress kind
    #        lowers it. This is also the one place a high exaggeration ceiling is correct -- anger IS
    #        loud and pressed, which is exactly what that dial produces.
    "angry":      (0.90, 1.60, 0.60, 0.78),
    # anxious -- NOW ITS OWN CURVE (2026-07-30). It used to be `("pain", 0.45)`, i.e. the pain curve
    # at low intensity, which made it a DEAD BUTTON: measured distance to `irritable` was 0.031 and to
    # `in_pain` 0.082 in normalised dial space, so all three were the same voice at three volumes.
    # (Same trap `confused` hit when it was built on the flat `none` curve and came out identical to
    # `calm`.) Adding it to the lab without this curve would have shipped three buttons that sound
    # alike.
    #
    # vs SAD    -- direction. Anxiety RISES and rushes; sadness falls away and slows.
    # vs IN PAIN-- pacing. Pain is slow and halting (cfg 0.33); anxiety is quick and pressured, so
    #              this is the one distress kind whose cfg sits ABOVE neutral.
    # vs HAPPY  -- both are expressive with raised pitch, and in dial space they sit closer than any
    #              other pair here (~0.14). They separate on PACING plus temperature, and above all in
    #              the REFERENCE CLIP, which is where character actually lives -- cheerful and
    #              frightened are unmistakable to a listener even at similar dials.
    # Temperature deliberately stays on the RISING default branch rather than joining the steady
    # group: erratic delivery is precisely what anxiety sounds like. That is the same finding that
    # made high temperature wrong for pain, applied in the direction where it is right.
    "anxious":    (0.60, 0.88, 0.62, 0.76),
}

# Named presets for the operator drawer. These are (kind, intensity) pairs rather than raw
# knob values so the drawer and the automatic scenario-derived path resolve through exactly
# the same curves -- one source of truth, so a preset always sounds like the real thing.
PRESETS = {
    "calm":       ("none", 0.0),
    # Repointed off the pain curve onto its own -- see the `anxious` note in _CURVES for why the old
    # ("pain", 0.45) made this indistinguishable from in_pain and irritable.
    "anxious":    ("anxious", 0.80),
    "in_pain":    ("pain", 0.85),
    # Lab presets for the general-affect kinds above. `confused` already mapped to `hesitant`
    # before these existed, and is deliberately left pointing there rather than duplicated.
    "happy":      ("happy", 0.75),
    "sad":        ("sad", 0.80),
    "angry":      ("angry", 0.80),
    "breathless": ("breathless", 0.75),
    "confused":   ("hesitant", 0.70),
    "drowsy":     ("fatigue", 0.85),
    "irritable":  ("pain", 0.60),
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def params_for(kind: str | None, pain: float | None) -> dict:
    """Resolve the bridge's (kind, pain) into Chatterbox generation params."""
    k = (kind or "none").strip().lower()
    if k not in _CURVES:
        k = "none"
    try:
        t = _clamp(float(pain if pain is not None else 0.0), 0.0, 1.0)
    except (TypeError, ValueError):
        t = 0.0

    e0, e1, c0, c1 = _CURVES[k]
    out = {
        "exaggeration": round(_clamp(_lerp(e0, e1, t), EXAG_MIN, EXAG_MAX), 3),
        "cfg_weight": round(_clamp(_lerp(c0, c1, t), CFG_MIN, CFG_MAX), 3),
        # Was "more variability when distressed: a patient in pain is less measured", ramping
        # 0.80 -> 0.92 for everything except fatigue. That reasoning does not survive contact:
        # temperature buys ERRATIC delivery, and erratic is what ANXIETY sounds like, not pain.
        # A patient in real pain is grimly consistent -- the same hurt on every syllable, steady and
        # rough, not darting about. So pain now sits BELOW the neutral 0.80 alongside fatigue, and
        # only the genuinely agitated kinds ramp up. Kept >= 0.70 because low temperature on a small
        # model flattens prosody into monotone, and >0.92 starts to slur words.
        # `sad` joins the steady group for the same reason as pain: sadness is heavy and consistent,
        # while erratic delivery reads as agitation. Only the genuinely agitated kinds ramp up.
        # pain moved OFF the steady 0.74 (2026-07-30, third revision). Steady was right when the goal
        # was "not anxious", but a perfectly even delivery is also what makes drawn-out pain read as
        # SARCASTIC -- sarcasm is controlled. Excruciating pain is involuntary and irregular, so it
        # needs some variability back. 0.86 sits between the steady group and the agitated 0.90+.
        # 0.82 (was 0.86 at rev5): a little less involuntary irregularity to match a moderate rather
        # than excruciating patient, while staying clear of the flat 0.74 that reads as controlled --
        # and controlled is the sarcastic quality.
        "temperature": round(_clamp(0.82 if k == "pain"
                                    else 0.74 if k in ("fatigue", "sad") else 0.80 + 0.12 * t,
                                    TEMP_MIN, TEMP_MAX), 3),
    }
    out["kind"] = k
    out["intensity"] = round(t, 3)
    return out


def params_for_preset(name: str) -> dict:
    """Resolve a named operator preset through the same curves as the automatic path."""
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; known: {sorted(PRESETS)}")
    kind, intensity = PRESETS[key]
    out = params_for(kind, intensity)
    out["preset"] = key
    return out


def sanitize_overrides(raw: dict | None) -> dict:
    """Clamp explicit operator slider values, dropping anything unrecognized."""
    out: dict = {}
    if not raw:
        return out
    bounds = {
        "exaggeration": (EXAG_MIN, EXAG_MAX),
        "cfg_weight": (CFG_MIN, CFG_MAX),
        "temperature": (TEMP_MIN, TEMP_MAX),
    }
    for field, (lo, hi) in bounds.items():
        if raw.get(field) is None:
            continue
        try:
            out[field] = round(_clamp(float(raw[field]), lo, hi), 3)
        except (TypeError, ValueError):
            continue
    return out


# ---------------------------------------------------------------------------------------------
# AFFECT WORDING -- the other half of an emotion.
#
# ⚠️ WHY THIS LIVES HERE, NEXT TO THE CURVES. Chatterbox has no categorical emotion parameter, so
# everything above only moves HOW the patient sounds: intensity, pacing, variability, plus which
# reference clip is cloned. None of it touches WHAT the patient says. Pin "angry" with dials alone
# and you get a patient who sounds furious while calmly answering "Yes, since Tuesday" -- which reads
# as broken rather than angry. The wording below is the missing half, and it is kept in this file so
# that tuning an emotion means editing ONE place; split across two files they drift, and a preset
# whose voice and words disagree is worse than one with neither.
#
# ⚠️ CONTENT, NOT INSTRUCTION. Measured repeatedly on this 3B: a bare rule ("you are angry") barely
# moves the output, while concrete behavioural wording does. Same finding as the TTS work, where an
# emotion TAG over a calm sentence produced a calm reading and only rewriting the SCRIPT fixed it.
# So each entry describes observable speech behaviour -- length, what the patient volunteers, how
# they open -- rather than naming the feeling and hoping.
#
# ⚠️ WHAT THESE MAY NEVER DO. They are appended AFTER the anti-fabrication and "you are not a
# clinician" rules and must not license invention. An angry patient is short and uncooperative; it
# does NOT get to invent a blood pressure, and a confused one does not get to invent a wrong number
# instead of saying it does not know. Emotion changes MANNER, never FACTS -- the same line the
# uncertainty levels hold, and for the same reason: a student charts what the patient says.
#
# Keyed on the CLINICAL kind (what _effective_params returns), not the preset name, so the automatic
# scenario path and an operator pin resolve through one table.
AFFECT = {
    "none": "",
    "pain": (
        "You are in real pain right now. Keep answers very short and break off mid-thought. "
        "Mention the pain unprompted -- shifting position, needing a moment. You are worn down and "
        "fed up with it, not brave about it, and you do not chat."
    ),
    "breathless": (
        "You are short of breath. Speak in short bursts of a few words and stop for air. Sentences "
        "trail off unfinished. You cannot manage a long answer, and you say when you need a moment."
    ),
    "fatigue": (
        "You are exhausted and struggling to stay awake. Answers are slow, flat and minimal. You "
        "lose the thread and need questions repeated. You volunteer nothing."
    ),
    "hesitant": (
        "You are confused and unsure. You start answers and lose them, ask what the question was, "
        "and hedge constantly -- 'I think', 'maybe', 'sorry, what?'. When you cannot follow, say so "
        "rather than guessing at an answer."
    ),
    "anxious": (
        "You are frightened about what this means. You seek reassurance, ask whether it is serious, "
        "and answer questions with questions. You apologise for taking up time and mention what you "
        "have been worrying about."
    ),
    "angry": (
        "You are angry about how you have been treated -- the wait, being passed around, nobody "
        "explaining. Answers are clipped and reluctant. You push back before cooperating and say "
        "plainly that you want someone to tell you what is happening. You are not abusive."
    ),
    "sad": (
        "You are low and subdued. Answers are quiet, brief and resigned. You do not volunteer much, "
        "and there is a weariness about the whole thing that goes beyond today."
    ),
    "happy": (
        "You are in good spirits and relieved to be seen. You are warm, chatty and cooperative, and "
        "you say when something is a relief to hear."
    ),
}


def affect_prompt(kind: str | None) -> str:
    """Behavioural wording for a clinical kind, or "" when there is nothing to add.

    Returns "" for unknown kinds rather than raising: an unrecognised kind should cost the affect
    and leave the patient neutral, never break the conversation turn.
    """
    return AFFECT.get((kind or "none").strip().lower(), "")
