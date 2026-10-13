"""LLM-as-a-Judge grounding gate for the CTO chatbot.

Every agent reply is verified BEFORE reaching the user:

1. Deterministic gate (free, no LLM): every ``PR #N`` cited in the reply must
   appear in the turn's tool observations. Catches fabricated tables (e.g. #1/#2
   with invented titles) with zero cost.
2. LLM judge (separate cheap model, ``JUDGE_MODEL``): semantic
   grounding check -> JSON verdict (PASS / FAIL).
3. Orchestration lives in ``ChatService._generate_with_judge``: FAIL -> one
   grounded retry -> safe fallback (the CTO never sees unverified numbers).

Design notes:
- The judge compares the reply against the turn's TOOL OBSERVATIONS (what the
  agent actually saw), not a fresh DB query — a reply grounded in nothing is
  rejected even if the DB happens to contain similar data.
- Judge infra failure (timeout, bad JSON) fails OPEN with a warning: a sick
  judge must not take the whole chatbot down. An explicit FAIL fails CLOSED.
- Smalltalk without verifiable claims ("Ahla!") skips the judge call entirely.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger("cto-copilot.judge")

PR_REF_RE = re.compile(r"(?:#|رقم)\s*(\d+)")
NUMBER_FIELD_RE = re.compile(r'"number"\s*:\s*(\d+)')
# Email addresses are structured identifiers like PR refs: an address the
# reply states must have been seen in the turn's tool observations (or be a
# restatement of the user's own question). Catches invented senders
# ("noreply@github.com") with zero LLM cost — same family as the PR gate.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# ISO calendar dates are structured too ("2026-10-12"): a reply that pins an
# event to an ISO date must have that literal in the observations (every tool
# output carries ISO timestamps, so a grounded date always matches). Catches
# the "latest PR was today" class where the model stitches the injected today
# onto a row from another day. Human-form dates ("12 October") are skipped —
# only exact ISO literals are verifiable without an LLM.
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _emails_in_text(text: str) -> set:
    # Trailing sentence dots ("wrote to boss@example.com.") are punctuation,
    # not part of the address — strip them so grounding compares cleanly.
    return {m.group(0).lower().rstrip(".") for m in EMAIL_RE.finditer(text or "")}


def _iso_dates_in_text(text: str) -> set:
    return {m.group(0) for m in ISO_DATE_RE.finditer(text or "")}


def _system_dates() -> set:
    """Today + yesterday (Cairo ISO) — system-provided ground truth.

    The agent gets these injected in every turn's system message, so stating
    them needs no tool call (demanding one would only add latency to "what
    day is it" questions). Any OTHER ISO date still needs tool evidence.
    """
    try:
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo("Africa/Cairo")).date()
    except Exception:
        today = datetime.now(timezone.utc).date()
    return {today.isoformat(), (today - timedelta(days=1)).isoformat()}


# A `WHERE number = 5` tool call proves the agent fetched PR #5 even when the
# SELECT list omits the key (e.g. `SELECT state ...` returns no "5" literal).
SQL_NUMBER_RE = re.compile(r"\bnumber\s*=\s*(\d+)", re.IGNORECASE)


# Denial markers (plain substrings, both languages): a "#N" that only ever
# appears next to one of these is a denial ("no PR #999"), not a fabrication.
# Kept as data, not patterns — no hardcoded names anywhere in this module.
DENIAL_MARKERS = (
    "no ", "not ", "n't", "never", "none", "without", "n't exist",
    "لا يوجد", "لا توجد", "مافيش", "مفيش", "ما فيش", "ما فيه",
    "لم يتم", "غير موجود", "مالناش", "معندناش", "ماعندناش", "ما عندناش",
    "لم يُفتح", "لم يفتح", "لا وجود",
)

_STRIP_CHARS = " \t\n\r.,;:!?()[]{}\"'`~@#$%^&*+=|/\\<>—–-؟!،؛«»"


def _ref_in_denial_context(low: str, start: int, end: int, prev_end: int,
                         window: int = 40, after_window: int = 12) -> bool:
    """True if a denial marker attaches to THIS ref (not a neighboring one).

    The before-window starts after the previous ref match, so one ref's
    denial ("no PR #999, but PR #9…") never bleeds onto the next ref.
    """
    before = low[max(prev_end, start - window):start]
    after = low[end:end + after_window]
    return any(m in before or m in after for m in DENIAL_MARKERS)


def _candidate_usernames(text: str) -> list:
    """Username-shaped tokens via plain string ops (no patterns, no lists).

    Keeps tokens with a Latin letter, length >= 3, username charset only.
    Pure Arabic/numbers/punctuation fall away; normal English words survive
    but never match a roster name (distance check below filters them).
    """
    out = []
    for tok in (text or "").split():
        t = tok.strip(_STRIP_CHARS)
        if len(t) < 3:
            continue
        if not any(c.isalpha() and ord(c) < 128 for c in t):
            continue
        if not all(c.isalnum() or c in "-_" for c in t):
            continue
        out.append(t)
    return out


def _known_authors_from_observations(observations) -> set:
    """Author/login/owner string values buried in tool-output JSON."""
    known = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    walk(v)
                elif isinstance(v, str) and str(k).lower() in (
                        "author", "login", "owner", "username", "merged_by"):
                    v = v.strip()
                    if v:
                        known.add(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for obs in observations or []:
        try:
            walk(json.loads(obs))
        except Exception:
            continue
    return known


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def verify_authors(reply: str, known: set) -> Dict[str, Any]:
    """Typo-grade author check against a roster (observations and/or DB).

    No hardcoded names: `known` is built live every call. A candidate within
    distance <= 2 of a known author (length >= 5) but not equal is almost
    certainly a mistyped username (SeifMahdoud63 vs SeifMahmoud63) -> FAIL.
    Anything else (exact hits, unknown words) passes through to the LLM judge.
    """
    cands = _candidate_usernames(reply)
    if not cands or not known:
        return {"verdict": "PASS", "reason": "nothing to verify"}
    roster = {k.lower(): k for k in known if k}
    for c in dict.fromkeys(cands):
        cl = c.lower()
        if cl in roster:
            continue
        if len(cl) < 5:
            continue
        for k, orig in roster.items():
            if abs(len(cl) - len(k)) > 2:
                continue
            if _levenshtein(cl, k) in (1, 2):
                return {
                    "verdict": "FAIL",
                    "reason": f"username '{c}' looks like a mistyped '{orig}'",
                    "bad_claims": [c],
                }
    return {"verdict": "PASS", "reason": "no mistyped authors"}

# Spelled-out numbers (cardinals 0-10, Arabic + English, Egyptian spellings
# included): a hallucinated "wahed"/"one" must trigger the judge exactly like
# a hallucinated "1" — digit-only checks are blind to it.
NUMBER_WORDS = {
    "صفر",
    "واحد", "واحدة", "واحده",
    "اثنان", "اثنين", "اتنين",
    "ثلاثة", "ثلاثه", "تلاتة", "تلاته", "ثلاث",
    "أربعة", "اربعة", "أربعه", "اربعه",
    "خمسة", "خمسه",
    "ستة", "سته",
    "سبعة", "سبعه",
    "ثمانية", "ثمانيه", "تمانية", "تمانيه", "ثمان",
    "تسعة", "تسعه", "تسع",
    "عشرة", "عشره", "عشر",
    "zero", "one", "two", "three", "four",
    "five", "six", "seven", "eight", "nine", "ten",
}


def _has_number_claim(text: str) -> bool:
    """True if the text makes any countable claim: digits, # refs, or words."""
    if not text:
        return False
    if re.search(r"[#\d]", text):
        return True
    # Token-based (not substring): "one" must not match "someone".
    tokens = set(re.findall(r"\w+", text.strip().lower()))
    return bool(tokens & NUMBER_WORDS)
RTL_RE = re.compile(r"[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]")

JUDGE_SYSTEM_PROMPT = """You are a fact-checking judge for an engineering assistant.
You receive: the user's question, the tool observations (the ONLY ground truth —
raw database/tool output the assistant saw this turn), and the assistant's reply.

Verdict rules:
- Scope: ONLY repository-data claims need grounding — PR numbers/titles/authors,
  engineer names tied to repo activity, PR counts, repo dates/durations and
  report metrics. General knowledge, definitions, explanations, advice and
  opinions need NO grounding even if they contain numbers or years
  ("DORA started in 2013" must NOT fail for its date).
- Semantic grounding (FLEXIBLE): Evaluate the underlying SEMANTIC meaning and
  factual truthfulness, NOT surface wording or literal phrasing. Answers may be
  expressed in colloquial language, regional dialects (such as Egyptian Arabic:
  'مالناش', 'معندناش', 'مفيش', 'زي الفل مافيش حاجة عاجلة'), idioms, or varied
  sentence structures. If the semantic claim aligns with the tool observations
  (e.g., stating 'we have no urgent emails right now' or 'مالناش إيميلات'
  semantically conveys count 0), treat it as factually grounded and PASS. Do NOT
  reject correct information because of dialect, natural phrasing, or indirect style.
- Conversational extras need NO grounding: follow-up questions ("want details
  on any of them?"), offers of help, restatements of the user's own words, and
  politeness fillers. Judge ONLY factual claims about repo data — a correct
  answer with a friendly tail is still PASS.
- Zero/empty results ("0", "none", "no X found/opened/merged", "مالناش X") are PASS
  when consistent with observations — never fail a correct zero or absence statement.
- Denials ("no PR #N", "X does not exist") are PASS only when the observations
  come from a query that WOULD contain the denied item if it existed (a full
  listing or COUNT over the same scope). A denial with no supporting
  observations behind it is FAIL.
- If there are NO tool observations: repository-data claims are FAIL, everything
  else is PASS. Pure smalltalk with zero factual claims is PASS.
- A reply that says it could not verify ("couldn't confirm", "not sure") is PASS.
- Reply language, tone and formatting are irrelevant to the verdict.
- Output ONLY JSON, no other text: {"verdict": "PASS"|"FAIL", "reason": "...", "bad_claims": [...]}.
  "bad_claims" lists the exact unsupported fragments (max 5)."""


class JudgeService:
    def __init__(self):
        self._client = None
        self._groq_client = None

    @property
    def enabled(self) -> bool:
        return bool(settings.judge_enabled)

    @property
    def client(self):
        """Lazy Bedrock OpenAI-compatible client (same endpoint, judge model).

        max_retries=0 by design: the OpenAI SDK otherwise retries each call
        internally (the "Retrying request in Xs (retry 1 of 2)" lines), which
        multiplies with our own retry x fallback loop and looks like an
        infinite loop in the logs. All retries are controlled explicitly in
        llm_judge() instead.
        """
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.bedrock_api_key,
                base_url=settings.bedrock_base_url_qwen,
                default_headers={"Authorization": f"Bearer {settings.bedrock_api_key}"},
                max_retries=0,
            )
        return self._client

    @property
    def groq_client(self):
        """Lazy Groq OpenAI-compatible client (judge fallback endpoint)."""
        if self._groq_client is None:
            from openai import OpenAI

            self._groq_client = OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
                max_retries=0,
            )
        return self._groq_client

    @staticmethod
    def _is_groq_model(model: str) -> bool:
        """Groq IDs are slash-style ("openai/gpt-oss-20b"), Bedrock dot-style."""
        return "/" in (model or "")

    def _client_for(self, model: str):
        """Route each model to its provider's client (Bedrock vs Groq)."""
        return self.groq_client if self._is_groq_model(model) else self.client

    # ---------------- Step 1: deterministic gate ---------------- #

    def deterministic_gate(
        self, reply: str, observations: List[str], roster: Optional[set] = None,
        user_content: Optional[str] = None,
        tool_calls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """PR refs + email-address + ISO-date + author-typo checks (zero LLM).

        Refs are structural (#N or Arabic "raqm N" — never a name list).
        Refs that appear ONLY inside denial context ("no PR #999") are not
        fabrication claims: they skip the instant FAIL and defer to the LLM
        judge, which understands denials.
        - A ref is grounded by the tool OUTPUTS or by the tool CALLS: a
          `WHERE number = 5` query proves PR #5 was fetched even when the
          SELECT list omits the key (e.g. `SELECT state ...`).
        - Email addresses follow the same rule: an address stated as a
          positive claim must appear in the observations, unless it
          restates the user's own question. A claimed address with no tool
          calls behind it is FAIL (forces a grounded retry); denial-only
          mentions defer exactly like PR refs.
        - ISO dates follow the same rule, except a PURE date answer ("today
          is X") with zero tool calls may state the system today/yesterday.
          Once tools ran, every ISO date must be in the outputs — this is
          what catches "latest PR was today" stitched onto another day's row.
          Human-form dates are unverifiable here and skipped.
        - Author check runs on every reply: exact roster hits pass, near-miss
          usernames fail, everything else passes through.
        """
        matches = list(PR_REF_RE.finditer(reply or ""))
        low = (reply or "").lower()
        substantive = []
        prev_end = 0
        for m in matches:
            if not _ref_in_denial_context(low, m.start(), m.end(), prev_end):
                substantive.append(m)
            prev_end = m.end()
        if substantive:
            if not observations:
                nums = sorted({m.group(1) for m in substantive}, key=int)
                return {
                    "verdict": "FAIL",
                    "reason": "reply cites PRs but the agent ran no tools this turn",
                    "bad_claims": [f"PR #{n}" for n in nums],
                }
            # Observations are raw SQL JSON: PRs appear as "number": N and/or
            # inside titles ("Merge pull request #4") — accept both shapes.
            # Plus the tool CALLS: `WHERE number = 5` proves PR #5 was fetched
            # even when the SELECT list omits the key.
            obs_text = "\n".join(observations)
            call_text = "\n".join(tool_calls or [])
            obs_refs = (set(PR_REF_RE.findall(obs_text)) | set(
                NUMBER_FIELD_RE.findall(obs_text)) | set(
                SQL_NUMBER_RE.findall(call_text)))
            missing = sorted({m.group(1) for m in substantive} - obs_refs, key=int)
            if missing:
                return {
                    "verdict": "FAIL",
                    "reason": f"cited PRs absent from tool output: {', '.join('#' + n for n in missing)}",
                    "bad_claims": [f"PR #{n}" for n in missing],
                }
        email_matches = list(EMAIL_RE.finditer(reply or ""))
        email_substantive = []
        prev_end = 0
        for m in email_matches:
            if not _ref_in_denial_context(low, m.start(), m.end(), prev_end):
                email_substantive.append(m.group(0).lower().rstrip("."))
            prev_end = m.end()
        if email_substantive:
            user_addrs = _emails_in_text(user_content)
            if not observations:
                claimed = sorted(set(email_substantive) - user_addrs)
                if claimed:
                    return {
                        "verdict": "FAIL",
                        "reason": "reply states email addresses but the agent ran no tools this turn",
                        "bad_claims": claimed,
                    }
                # Pure restatement of the user's own question — not a claim.
            else:
                obs_text = "\n".join(observations)
                grounded = _emails_in_text(obs_text) | user_addrs
                missing = sorted(set(email_substantive) - grounded)
                if missing:
                    return {
                        "verdict": "FAIL",
                        "reason": f"cited email addresses absent from tool output: {', '.join(missing)}",
                        "bad_claims": missing,
                    }
                # Grounded — fall through to the date check below.
        iso_matches = list(ISO_DATE_RE.finditer(reply or ""))
        iso_substantive = []
        prev_end = 0
        for m in iso_matches:
            if not _ref_in_denial_context(low, m.start(), m.end(), prev_end):
                iso_substantive.append(m.group(0))
            prev_end = m.end()
        if iso_substantive:
            user_dates = _iso_dates_in_text(user_content)
            if not observations:
                # Pure date answer: system today/yesterday need no tools.
                claimed = sorted(set(iso_substantive) - user_dates - _system_dates())
                if claimed:
                    return {
                        "verdict": "FAIL",
                        "reason": "reply pins events to ISO dates but the agent ran no tools this turn",
                        "bad_claims": claimed,
                    }
                # Pure restatement of the user's own question — not a claim.
            else:
                obs_text = "\n".join(observations)
                missing = sorted(d for d in set(iso_substantive)
                                 if d not in obs_text and d not in user_dates)
                if missing:
                    return {
                        "verdict": "FAIL",
                        "reason": f"cited ISO dates absent from tool output: {', '.join(missing)}",
                        "bad_claims": missing,
                    }
                # Grounded — fall through to the author check below.
        known = _known_authors_from_observations(observations) | set(roster or ())
        auth = verify_authors(reply or "", known)
        if auth["verdict"] == "FAIL":
            return auth
        if substantive:
            return {"verdict": "PASS", "reason": "all cited PRs grounded in tool output"}
        if matches:
            return {"verdict": "PASS", "reason": "refs only in denials — deferred to LLM judge"}
        return {"verdict": "PASS", "reason": "no PR references to verify"}

    async def _author_roster(self) -> set:
        """Live author roster via a strictly read-only query (no hardcoded names)."""
        try:
            from sqlalchemy import text as _t

            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                res = await session.execute(_t(
                    "SELECT author FROM engineers "
                    "UNION SELECT DISTINCT author FROM pull_requests"))
                return {str(r[0]).strip() for r in res.all()
                        if r and str(r[0]).strip()}
        except Exception as e:
            logger.debug(f"Author roster skipped: {e}")
            return set()

    # ---------------- Step 2: LLM judge ---------------- #

    def llm_judge(
        self, user_content: str, reply: str, observations: List[str]
    ) -> Dict[str, Any]:
        """Semantic grounding verdict from the judge model (PASS / FAIL / ERROR).

        Empty responses (reasoning models sometimes burn the whole token budget
        thinking and emit nothing) are retried, then escalated to the fallback
        model. Only a total miss returns ERROR (fail-open upstream).
        """
        obs_text = "\n".join(observations or [])[:4000] or "(no tool observations this turn)"
        prompt = (
            f"<question>\n{user_content}\n</question>\n\n"
            f"<tool_observations>\n{obs_text}\n</tool_observations>\n\n"
            f"<assistant_reply>\n{reply}\n</assistant_reply>\n\n"
            "Return the JSON verdict."
        )

        def _once(model: str) -> Dict[str, Any]:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": settings.judge_max_tokens,
                "timeout": 30.0,
            }
            if "gpt-oss" in model.lower() or "openai" in model.lower():
                kwargs["extra_body"] = {"reasoning_effort": "low"}

            resp = self._client_for(model).chat.completions.create(**kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("empty judge response")
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            verdict = str(data.get("verdict", "")).upper()
            if verdict not in ("PASS", "FAIL"):
                raise ValueError(f"unknown verdict: {verdict!r}")
            return {
                "verdict": verdict,
                "reason": str(data.get("reason", "")),
                "bad_claims": list(data.get("bad_claims") or [])[:5],
            }

        models = [settings.judge_model]
        fallback = (settings.judge_fallback_model or "").strip()
        if fallback and fallback != settings.judge_model:
            models.append(fallback)
        rounds = max(1, settings.judge_retries + 1)
        last_error: Exception = ValueError("empty judge response")
        tried = 0
        for mi, model in enumerate(models):
            if mi > 0:
                via = "Groq" if self._is_groq_model(model) else "Bedrock"
                logger.info(
                    f"Judge primary model exhausted, switching to {via} fallback {model}."
                )
            for _ in range(rounds):
                tried += 1
                try:
                    return _once(model)
                except Exception as e:
                    last_error = e
                    # Log plainly: which attempt, of how many total, and what happens next.
                    total = len(models) * rounds
                    if tried < total:
                        logger.warning(
                            f"Judge attempt {tried}/{total} with {model} failed ({e}); retrying."
                        )
                    else:
                        logger.warning(
                            f"Judge attempt {tried}/{total} with {model} failed ({e}); giving up."
                        )
        logger.warning(f"Judge call failed, failing open: {last_error}")
        return {"verdict": "ERROR", "reason": f"judge error: {last_error}", "bad_claims": []}

    # ---------------- Combined review ---------------- #

    async def review(
        self, user_content: str, reply: str, observations: List[str],
        tool_calls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Deterministic gate first, LLM judge second. Never raises.

        The gate ALWAYS runs — even with the LLM judge disabled it still
        drives the grounded retry in `_generate_with_judge`, at zero LLM
        cost and zero added latency on the happy path.
        `tool_calls` carries the turn's tool ARGUMENTS (e.g. SQL text): a
        `WHERE number = 5` query grounds a "#5" claim even when the SELECT
        list omits the key.
        """
        try:
            roster = await self._author_roster()
            gate = self.deterministic_gate(
                reply, observations, roster, user_content=user_content,
                tool_calls=tool_calls)
            if gate["verdict"] == "FAIL":
                logger.warning(f"Judge gate rejected reply: {gate['reason']}")
                return gate
            if not self.enabled:
                return {"verdict": "PASS",
                        "reason": "deterministic gate passed (judge disabled)"}
            # Nothing verifiable (smalltalk, no tools, no countable claims at
            # all — digits, # refs AND spelled-out numbers) -> skip the call.
            if not observations and not _has_number_claim(reply or ""):
                return {"verdict": "PASS", "reason": "no verifiable claims"}
            res = self.llm_judge(user_content, reply, observations)
            if res["verdict"] == "ERROR":
                return {"verdict": "PASS", "reason": "judge unavailable, passed open"}
            if res["verdict"] == "FAIL":
                logger.warning(f"Judge rejected reply: {res['reason']}")
            else:
                logger.info("Judge passed reply.")
            return res
        except Exception as e:
            logger.warning(f"Judge review crashed, failing open: {e}")
            return {"verdict": "PASS", "reason": f"judge crash: {e}"}

    # ---------------- Retry + fallback ---------------- #

    def retry_nudge(
        self,
        user_content: str,
        reply: str,
        observations: List[str],
        verdict: Dict[str, Any],
    ) -> str:
        """Instruction appended for the single grounded retry.

        Conditional by design: data questions MUST query first, while
        smalltalk/general questions must answer directly WITHOUT inventing
        repo facts. An unconditional "always call a tool" order would force
        pointless queries on greetings and likely fail them twice.

        Surgical: when bad_claims are known, the nudge names them explicitly
        so the model fixes EXACTLY the fabricated fragments instead of
        rewriting the whole answer from scratch.
        """
        obs_text = "\n".join(observations or [])[:3000] or "(no tool observations)"
        bad = verdict.get("bad_claims") or []
        reason = verdict.get("reason", "")
        if bad:
            bad_str = "\n".join(f"  - ❌ {claim}" for claim in bad)
            nudge_detail = (
                f"Your previous answer was REJECTED because it contains "
                f"fabricated/ungrounded claims:\n{bad_str}\n"
                f"Judge reason: {reason}\n\n"
            )
        else:
            nudge_detail = (
                f"Your previous answer was REJECTED ({reason}).\n\n"
            )
        return (
            nudge_detail +
            "MANDATORY RETRY RULES:\n"
            "1. If the question is about PRs, emails, reports, engineers, "
            "counts, or any repo data: you MUST call execute_readonly_query "
            "FIRST and answer ONLY from its output. Never answer repo "
            "questions from memory or conversation history.\n"
            "2. If it is smalltalk or general knowledge needing no data: "
            "answer directly, but do NOT include any repo-specific facts "
            "(no PR numbers, usernames, counts or dates).\n"
            "3. If the observations below already contain the answer, use "
            "them directly without a new tool call.\n"
            "4. When the tool returns 0 rows or count=0, say so clearly "
            "(e.g. 'مفيش' / 'none found') — never invent data.\n"
            "5. Copy identifiers character-for-character from tool output.\n"
            "6. VERBATIM RULE: every PR number, username, email address, "
            "count and date you write MUST appear exactly in the tool output "
            "above. If it is not there, delete it — never complete it from "
            "memory, not even as 'helpful context'.\n\n"
            f"<original_question>\n{user_content}\n</original_question>\n\n"
            f"<previous_rejected_reply>\n{reply[:800]}\n</previous_rejected_reply>\n\n"
            f"<tool_observations>\n{obs_text}\n</tool_observations>"
        )

    def safe_fallback(self, user_content: str) -> str:
        """Shown instead of an unverified reply — same language as the user."""
        if user_content and RTL_RE.search(user_content):
            return (
                "مقدرتش أتحقق من الإجابة من الداتا الحية، "
                "فمش هعرض أرقام غير مؤكدة. جرّب تسأل تاني أو بص على صفحة الـ PRs."
            )
        return (
            "I couldn't verify that answer against the live data, "
            "so I'm not showing unconfirmed numbers. Please try again "
            "or check the PRs page."
        )

    def classify_query_intent(self, user_content: str) -> str:
        """LLM-based intent classifier (sync fallback): 'data' or 'general'.

        Replaces regex-based filtering with a model call for higher accuracy.
        'data' = query needs DB tools (PRs, emails, engineers, reports, metrics).
        'general' = general knowledge, smalltalk, greetings, definitions.

        Falls back to 'data' on any error (safer — triggers a tool call
        rather than risking a hallucinated answer from memory).
        """
        try:
            resp = self.client.chat.completions.create(
                model=settings.judge_model,
                messages=[
                    {"role": "system", "content": (
                        "You classify user queries for an engineering CTO assistant.\n"
                        "The assistant has access to a database with: pull_requests, "
                        "engineers, daily_reports, emails, eval_fixtures.\n\n"
                        "Respond with ONLY one word:\n"
                        "- 'data' if the query asks about PRs, pull requests, engineers, "
                        "authors, contributors, email urgency, reports, scores, tiers, "
                        "overdue items, counts, repository metrics, or any team/project data.\n"
                        "- 'general' if the query is smalltalk, greetings, general knowledge, "
                        "definitions, advice, opinions, time/date, or anything NOT about "
                        "the specific repository/team data.\n\n"
                        "Output ONLY: data OR general"
                    )},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=8,
                timeout=10.0,
            )
            raw = (resp.choices[0].message.content or "").strip().lower()
            if "general" in raw:
                return "general"
            return "data"
        except Exception as e:
            logger.debug(f"Intent classifier failed, defaulting to 'data': {e}")
            return "data"

    async def classify_query_intent_jev(self, user_content: str) -> str:
        """JEV-based async intent classifier: 'data' or 'general'.

        Uses the TypeSafe SystemOne decision API for more accurate intent
        routing. 'data' means the query requires fresh tool calls to the
        database; 'general' means it can be answered from knowledge alone.

        The JEV model scores on a 0-9 scale how 'data-oriented' the query
        is; >= 5 (mapped to 6.0) triggers tool calls.

        Falls back to the sync LLM classifier on any error.
        """
        import httpx

        try:
            headers = {
                "Authorization": f"Bearer {settings.jev_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.jev_model,
                "state": user_content,
                "questions": {
                    "needs_tools": {
                        "type": "score",
                        "instructions": (
                            "Rate how much this user query requires a live database "
                            "lookup (PRs, emails, reports, engineers, metrics) vs. "
                            "being answerable from general knowledge, greetings, or "
                            "conversation memory alone. High score = needs database tools."
                        ),
                        "criteria": [
                            "1 - Pure greeting, hello, thanks, bye",
                            "2 - General knowledge question unrelated to the team",
                            "3 - Opinion or advice question (no data needed)",
                            "4 - Vague reference that might need context but not DB",
                            "5 - Borderline: might reference team data indirectly",
                            "6 - Asks about emails, reports, or team activity",
                            "7 - Asks for specific counts, lists, or metrics",
                            "8 - Asks about specific PRs, engineers, or scores",
                            "9 - Asks for filtered/date-specific data queries",
                            "10 - Complex data question needing multiple lookups",
                        ],
                    }
                },
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    settings.jev_api_url,
                    headers=headers,
                    json=payload,
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw_score = (
                        data.get("answers", {})
                        .get("needs_tools", {})
                        .get("score")
                    )
                    if raw_score is not None:
                        # JEV returns 0-9; >= 4 (i.e. mapped 5+) = data query
                        intent = "data" if int(raw_score) >= 4 else "general"
                        logger.info(
                            f"JEV intent: score={raw_score} -> {intent} "
                            f"for: {user_content[:60]}"
                        )
                        return intent
                logger.debug(
                    f"JEV intent returned {resp.status_code}, "
                    f"falling back to LLM classifier."
                )
        except Exception as e:
            logger.debug(f"JEV intent classifier failed: {e}")
        # Fallback to sync LLM classifier
        return self.classify_query_intent(user_content)


judge_service = JudgeService()
