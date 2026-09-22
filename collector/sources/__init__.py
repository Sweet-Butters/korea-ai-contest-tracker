"""Each source module exposes NAME, CONTEST_LIST and fetch() -> list[dict].

A raw item has at least "name" and "url"; optional: host, applyStart, applyEnd (ISO dates),
eventDates, prize, eligibility, notes, upcoming (bool). CONTEST_LIST=True means the source only
lists contests, so titles need not contain words like "대회".
"""
from . import aifactory, allcon, allforyoung, contestkorea, dacon, devevent, eventus, linkareer, naver_news, thinkgood, wevity

ALL = [thinkgood, allcon, linkareer, allforyoung, contestkorea, wevity, dacon, aifactory, eventus, devevent, naver_news]
