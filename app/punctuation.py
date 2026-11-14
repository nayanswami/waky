"""Rule-based punctuation for when the AI cleanup is skipped or unavailable (short phrases, offline).

Conservative on purpose: it fixes what is clearly wrong (capitals, "i", spacing, final mark, obvious questions and commas)
and never rewords anything.
"""
from __future__ import annotations

import re

QUESTION_STARTS = (
    "what", "why", "how", "when", "where", "who", "whom", "whose", "which",
    "is", "are", "am", "was", "were", "do", "does", "did", "can", "could", "will", "would", "should", "shall", "may", "might",
    "have", "has", "had", "isn't", "aren't", "don't", "doesn't", "didn't", "can't", "won't", "wouldn't", "shouldn't", "couldn't",
    "kya", "kab", "kaise", "kaisa", "kaisi", "kyun", "kyon", "kahan", "kaun", "kitna", "kitne", "kitni", "kisne", "kisko",
)
QUESTION_ENDS = ("right", "no", "yeah", "okay", "ok", "na", "kya", "hai na", "theek hai", "samjhe", "samjha")
OPENERS = ("however", "actually", "basically", "honestly", "obviously", "also", "anyway", "meanwhile", "otherwise", "therefore",
           "unfortunately", "luckily", "finally", "firstly", "secondly", "thirdly", "okay", "alright", "well", "yes", "no", "so",
           "hi", "hello", "hey", "thanks", "sorry", "please", "btw", "for example", "in fact", "by the way", "of course",
           "accha", "acha", "theek hai", "haan", "nahi", "waise")
COMMA_BEFORE = ("but", "however", "although", "though", "whereas", "lekin", "magar", "par", "isliye", "because")
SHORT_ENDING_OK = {"ok", "okay", "yes", "no", "thanks", "thank you", "hello", "hi", "hey", "sure", "done", "great", "nice", "cool", "sounds good"}


def _first_words(sentence: str, n: int = 2) -> list[str]:
    return re.findall(r"[\w']+", sentence.lower())[:n]


def _is_question(sentence: str) -> bool:
    words = re.findall(r"[\w']+", sentence.lower())
    if len(words) < 3:
        return False
    if words[0] in QUESTION_STARTS:
        return True
    tail = " ".join(words[-2:])
    return words[-1] in QUESTION_ENDS and ("," in sentence or len(words) <= 6) and (tail in QUESTION_ENDS or words[-1] in QUESTION_ENDS)


def _capitalise_sentences(text: str) -> str:
    return re.sub(r"(^|[.!?]\s+|\n\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def _fix_i(text: str) -> str:
    text = re.sub(r"\bi\b(?=[\s,.!?;:']|$)", "I", text)
    return re.sub(r"\bi(?='(?:m|ll|ve|d)\b)", "I", text)


def _comma_openers(sentence: str) -> str:
    low = sentence.lower()
    for opener in sorted(OPENERS, key=len, reverse=True):
        if low.startswith(opener + " ") and len(sentence.split()) > len(opener.split()) + 2:
            rest = sentence[len(opener):]
            if not rest.lstrip().startswith((",", ".", "!", "?")):
                return sentence[:len(opener)] + "," + rest
            break
    return sentence


def _comma_before(sentence: str) -> str:
    words = sentence.split(" ")
    if len(words) < 6:
        return sentence
    out: list[str] = []
    for i, word in enumerate(words):
        bare = word.lower().strip(",.")
        if i >= 3 and bare in COMMA_BEFORE and out and not out[-1].endswith((",", ".", "!", "?", ";", ":")) and i < len(words) - 2:
            out[-1] += ","
        out.append(word)
    return " ".join(out)


def polish(text: str) -> str:
    """Tidy one dictation: spacing, capitals, 'I', commas after openers and before 'but', and a closing mark."""
    text = (text or "").strip()
    if not text:
        return text
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=\S)(?![\d])", r"\1 ", text)
    text = re.sub(r"([.!?])(?=[A-Za-z])", r"\1 ", text)
    text = _fix_i(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    fixed = []
    for part in parts:
        part = _comma_openers(_comma_before(part.strip()))
        fixed.append(part)
    text = " ".join(fixed)
    text = _capitalise_sentences(text)
    last = text.splitlines()[-1].strip()
    if last and last[-1] not in ".!?:)\"'" and "\n" not in text.strip():
        words = re.findall(r"[\w']+", last)
        sentence = re.split(r"(?<=[.!?])\s+", last)[-1]
        if _is_question(sentence):
            if words[-1].lower() in ("right", "na") and len(words) > 3 and not re.search(r",\s*\w+$", last):
                text = text[: len(text) - len(words[-1])].rstrip() + ", " + words[-1]
            text += "?"
        elif len(words) >= 3 or " ".join(w.lower() for w in words) in SHORT_ENDING_OK:
            text += "."
    elif last and last[-1] == "." and _is_question(re.split(r"(?<=[.!?])\s+", last)[-1].rstrip(".")):
        text = text[:-1] + "?"
    return text


COMMON = frozenset(
    """a an and are as at be but by for from had has have he her his i if in is it its me my of on or our she so that the their them then there they this to us was we were will with you your
    about above after again all also am any because been before being below between both can come could did do does done down during each even every first get give go going good got how into just keep know like little look make many may more most much must never new no not now off old once one only other out over own people really right said same say see should show since some still such take tell than these think those through time too two under until up use very want way well what when where which while who why would yes yet
    please thanks thank hello okay ok send sent call called meeting email message file work today tomorrow yesterday morning evening night week month year day home office team project plan idea thing things something anything nothing everything someone anyone everyone maybe actually basically however also another already always around away back best better big bit both bring brought change check clear close code come create does doing end enough ever example far few find fine follow found full give goes gone great hard help here high hope hour important keep kind large last later least left less let life long look lot made main mean might move name need next number often open part past pick place point put read ready real reason remember result run set side small start stop sure sorry talk test text turn understand used using wait whole without write wrong
    kya hai hain nahi nahin kal aaj abhi bhi toh tum aap main mera meri mere kaise kyun kahan theek accha acha haan""".split()
)


def fix_random_caps(text: str, keep: set[str] | None = None) -> str:
    """Lower-case a Capitalised common word in the middle of a sentence ("Send The file" -> "Send the file").

    Names, acronyms, "I" and words from your own vocabulary are left alone.
    """
    keep = {k.lower() for k in (keep or set())}

    def fix_sentence(sentence: str) -> str:
        tokens = re.split(r"(\s+)", sentence)
        seen_word = False
        out = []
        for tok in tokens:
            m = re.fullmatch(r"([\"'(\[]*)([A-Za-z][a-z']*)([\"')\].,;:!?]*)", tok)
            if m and seen_word:
                pre, word, post = m.groups()
                low = word.lower()
                if word[0].isupper() and word != "I" and not re.match(r"I'", word) and low in COMMON and low not in keep:
                    tok = pre + low + post
            if tok.strip():
                seen_word = True
            out.append(tok)
        return "".join(out)

    parts = re.split(r"(?<=[.!?])(\s+)", text)
    return "".join(fix_sentence(p) if i % 2 == 0 else p for i, p in enumerate(parts))
