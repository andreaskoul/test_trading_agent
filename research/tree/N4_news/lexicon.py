"""HAND word list for headline tone. NOT the Loughran-McDonald dictionary: the LM lists were not obtainable offline in
this environment (pysentiment2 not installed, no package index, network fetches forbidden for this branch). The words
below were chosen once, before any scoring, from the vocabulary of finance news headlines (analyst actions, earnings
outcomes, price moves, legal/regulatory events). Matching is on lower-case alphabetic tokens, exact (inflections
listed explicitly). Headline tone = (pos - neg) / max(pos + neg, 1).
"""
import re

POS = set("""
upgrade upgrades upgraded raise raises raised boost boosts boosted beat beats tops topped exceed exceeds exceeded
record strong stronger strength growth grow grows gain gains gained surge surges surged jump jumps jumped soar soars
soared rally rallies rallied rise rises rising higher outperform outperforms buy overweight approval approves approved
win wins won awarded accretive expand expands expansion profit profitable positive upbeat optimistic bullish
improve improves improved improvement rebound rebounds recovery breakthrough reaffirms reiterates
""".split())

NEG = set("""
downgrade downgrades downgraded lower lowers lowered cut cuts cutting miss misses missed fall falls fell drop drops
dropped slide slides slid plunge plunges plunged tumble tumbles tumbled decline declines declined weak weaker weakness
loss losses lawsuit lawsuits sue sues sued investigation probe recall recalls warn warns warning underperform
underperforms sell underweight bearish halt halted delay delays delayed fraud layoffs bankruptcy default downbeat
disappointing disappoints concern concerns fine fined resign resigns resigned subpoena slump slumps crash crashes
negative worst worse cautious suspend suspends suspended
""".split())

_TOK = re.compile(r"[a-z]+")


def tone(headline):
    w = _TOK.findall(headline.lower())
    p = sum(x in POS for x in w)
    n = sum(x in NEG for x in w)
    return (p - n) / max(p + n, 1)


def normalise(headline):
    """Text key for novelty: lower case, digits and punctuation removed, whitespace collapsed."""
    return " ".join(_TOK.findall(headline.lower()))
