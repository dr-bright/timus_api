import io
import math
import os.path
import re
import sys
import time
import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import requests as rqs


# TODO: docstrings
# TODO: automatic testing

default_judge_id = "320816ZW"

language_detector = {
    "py": "Python",
    "c": "GCC",
    "cpp": "G++",
    "pas": "Pascal",
    "java": "Java",
    "pypy": "PyPy"
}

submit_form = {  # action = "https://acm.timus.ru/submit.aspx?space=1"
    "Action": "submit",
    "SpaceID": "1",
    "JudgeID": None,
    "Language": None,
    "ProblemNum": None,
    "Source": None
}

supported_langs_cache = None


def supported_langs():
    global supported_langs_cache
    if supported_langs_cache is not None:
        return supported_langs_cache
    data = rqs.get('https://acm.timus.ru/submit.aspx').text
    p_select = re.compile(r'<select name="Language".*?>.*?</select>', re.I)
    data = p_select.findall(data)[0]
    p_option = re.compile(r'<option value="(.*?)">(.*?)</option>', re.I)
    rsp = {name: code for code, name in p_option.findall(data)}
    supported_langs_cache = rsp
    return rsp


@dataclass
class SubmitStatus:
    submit_id: int | None = None
    timestamp: float | None = None
    accepted: bool | None = None
    reason: str | None = None
    test: int | None = None
    runtime: float | None  = None
    memory: int | None = None  # in KB
    author_id: int | None = None
    author_name: str | None = None
    task_id: int | None = None
    task_name: str | None = None
    lang_name: str | None = None
    lang_code: int | None = None

    def __getitem__(self, k):
        return self.__dict__[k]

    def __setitem__(self, k, v):
        self.__dict__[k] = v
        return True

    def __getattr__(self, k):
        return getattr(self.__dict__, k)

    def __iter__(self):
        return self.keys()


# TODO: implement proper author.aspx parser for this dataclass
@dataclass
class Author:
    id: int | None = None
    name: str | None = None
    motd: str | None = None
    locale: str | None = None
    rank_by_solved: str | None = None
    rank_by_rating: str | None = None
    rating: str | None = None
    solved_tasks: list[int] | None = None

    def __getitem__(self, k):
        return self.__dict__[k]

    def __setitem__(self, k, v):
        self.__dict__[k] = v
        return True

    def __getattr__(self, k):
        return getattr(self.__dict__, k)

    def __iter__(self):
        return self.keys()


def status_naked(count=math.inf, upto=None, lang=None, **kwargs) -> list[SubmitStatus]:
    # ?author={author_id}&count={n}&from={n}&num={n}&status=accepted
    # supports author, num, status, count, from, upto, lang
    if count == 0:
        return []
    kwargs["space"] = 1
    if "from_" in kwargs:
        kwargs["from"] = kwargs["from_"]
        del kwargs["from_"]
    kwargs['count'] = 1000
    url = f"https://acm.timus.ru/status.aspx"
    data = rqs.get(url, params=kwargs).content.decode('utf-8')
    rsp = []
    p_entry = re.compile(r'(<TD class="id">(.*?)</TD>.*?<TD class="memory">[^>]*?>)', re.I)
    p_author_id = re.compile(r'<TD class="coder">.*?id=(.*?)".*?</TD>', re.I)
    p_author_name = re.compile(r'<TD class="coder">.*?>(.*?)</A></TD>', re.I)
    p_task_id = re.compile(r'<TD class="problem">.*?num=(.*?)".*?</TD>', re.I)
    p_task_name = re.compile(r'<TD class="problem">.*?>\. (.*?)<.*?</TD>', re.I)
    p_lang = re.compile(r'<TD class="language">(.*?)</TD>', re.I)
    p_verdict = re.compile(r'<TD class="verdict_(ac|rj|wt)">(.*?)</TD>', re.I)
    p_runtime = re.compile(r'<TD class="runtime">(.*?)</TD>', re.I)
    p_memory = re.compile(r'<TD class="memory">(.*?)</TD>', re.I)
    p_test = re.compile(r'<TD class="test">(.*?)</TD>', re.I)
    p_date = re.compile(r'<TD class="date"><NOBR>(.*?)</NOBR><BR><NOBR>(.*?)</NOBR></TD>', re.I)

    for entry, submit_id in p_entry.findall(data):
        stat = SubmitStatus()
        try:
            stat.submit_id = int(submit_id)
        except ValueError:
            submit_id = submit_id[:submit_id.rfind("<")]
            submit_id = submit_id[submit_id.rfind(">") + 1:]
            stat.submit_id = int(submit_id)
        verdict = p_verdict.findall(entry)[0]
        stat.stat = verdict[0]
        stat.accepted = None if verdict[0] == "wt" else False if verdict[0] == "rj" else True
        stat.reason = verdict[1]
        try:
            stat.runtime = float(p_runtime.findall(entry)[0])
        except (IndexError, ValueError):
            stat.runtime = 0
        try:
            stat.memory = int(p_memory.findall(entry)[0].replace(" ", "")[:-2])
        except (IndexError, ValueError):
            stat.memory = 0
        try:
            stat.test = int(p_test.findall(entry)[0])
        except (IndexError, ValueError):
            stat.test = 0
        stat.author_id = p_author_id.findall(entry)[0]
        stat.author_name = p_author_name.findall(entry)[0]
        stat.task_id = p_task_id.findall(entry)[0]
        stat.task_name = p_task_name.findall(entry)[0]
        stat.lang_name = p_lang.findall(entry)[0]
        stat.lang_code = detect_lang(stat.lang_name.split()[0])
        date = p_date.findall(entry)[0]
        date = date[0] + " " + date[1] + " GMT+0500"
        date = datetime.strptime(date, "%H:%M:%S %d %b %Y %Z%z")
        stat.timestamp = date.timestamp()
        rsp.append(stat)
    if upto is not None:
        rsp = filter(lambda st: st.submit_id > upto, rsp)
    lang_code = detect_lang(lang)
    if lang_code is not None:
        rsp = filter(lambda st: st.lang_code == lang_code, rsp)
    return [*rsp][:int(min(count, 1000))]


def status_cached_iter(cache: Iterable[SubmitStatus], **kwargs):
    # supports author, num, status, lang, count, from, from_, upto
    cache = iter(cache)
    if 'author' in kwargs:
        cache = filter(lambda st: st.author_id == kwargs['author'], cache)
    if 'num' in kwargs:
        cache = filter(lambda st: st.task_id == kwargs['num'], cache)
    if 'status' in kwargs:
        cache = filter(lambda st: st.accepted == (kwargs['status'] == 'accepted'), cache)
    if 'lang' in kwargs:
        lang_code = detect_lang(kwargs['lang'])
        cache = filter(lambda st: st.lang_code == lang_code, cache)
    if 'from_' in kwargs:
        kwargs['from'] = kwargs.pop('from_')
    if 'from' in kwargs:
        if isinstance(kwargs['from'], int):
            cache = filter(lambda st: st.submit_id <= kwargs['from'], cache)
        else:
            if isinstance(kwargs['from'], datetime):
                kwargs['from'] = kwargs['from'].timestamp()
            cache = filter(lambda st: st.timestamp > kwargs['from'], cache)
    if 'upto' in kwargs:
        if isinstance(kwargs['upto'], int):
            cache = filter(lambda st: st.submit_id > kwargs['upto'], cache)
        else:
            if isinstance(kwargs['upto'], datetime):
                kwargs['upto'] = kwargs['upto'].timestamp()
            cache = filter(lambda st: st.timestamp > kwargs['upto'], cache)
    if math.isfinite(kwargs.get('count', math.inf)):
        yield from itertools.islice(cache, kwargs['count'])
    yield from cache


def status_cached(cache: Iterable[SubmitStatus], **kwargs):
    return [*status_cached_iter(cache, **kwargs)]


def status_find(value, /, key=None, *, progress=None, **kwargs):
    # accepts author, num, status, from, upto
    # lang filtering is explicitly can't be supported with binary search
    # when in desperate need, utilize this to pinpoint an approximation; then use external linear search
    # example_key = lambda st: st.timestamp

    if not progress:
        def progress(*_, **__):
            pass
    elif progress is True:
        progress = print
    if not key:
        def key(st):
            return st.timestamp
        if isinstance(value, datetime):
            value = value.timestamp()
    kwargs.pop('lang', None)    # lang filtering is not supported
    if 'from_' in kwargs:
        kwargs['from'] = kwargs.pop('from_')
    if not isinstance(kwargs.get('upto', 1), int):
        _ = None
        if "from" in kwargs:
            _ = kwargs.pop("from")
        kwargs['upto'] = status_find(kwargs.pop('upto'), key=key, progress=progress, **kwargs)[0]
        if _ is not None:
            kwargs["from"] = _
    if not isinstance(kwargs.get('from', 1), int):
        _ = None
        if "upto" in kwargs:
            _ = kwargs.pop("upto")
        kwargs['from'] = status_find(kwargs.pop('from'), key=key, progress=progress, **kwargs)[1] - 1
        if _ is not None:
            kwargs["upto"] = _
    interval = [-math.inf, math.inf]

    # noinspection PyShadowingNames
    def bound(sel: list[SubmitStatus]):
        bounding = [-math.inf, math.inf]
        for st in sel:
            cp = key(st) - value
            if cp <= 0:
                bounding[0] = max(bounding[0], st.submit_id)
                interval[0] = max(interval[0], st.submit_id)
            if cp >= 0:
                bounding[1] = min(bounding[1], st.submit_id)
                interval[1] = min(interval[1], st.submit_id)
        return bounding
    kwargs['count'] = 1000
    progress(0.0)
    shot = status_naked(**kwargs)
    search_width = shot[0].submit_id - kwargs.get('upto', 1)
    bounding = bound(shot)
    if math.isfinite(sum(bounding)) or not math.isfinite(bounding[1]) or len(shot) in range(1, 1000):
        progress(1.0)
        return bounding
    kwargs['from'] = kwargs.get('upto', 0) + 999
    # loop stops when shot contains less than 1000 elements or when shot contains elements greater than upto
    # 1) shot bounding is finite, meaning that the point is found
    # 2) shot contains < 1000 but > 0 entries and shot bounding[0] is -inf
    while True:
        shot = status_naked(**kwargs)
        boundary_flag = len(shot) in range(1, 1000)
        bounding = bound(shot)
        if math.isfinite(sum(bounding)) or not math.isfinite(bounding[0]) and boundary_flag:
            progress(1.0)
            break
        end = interval[0]
        if not shot:
            end = interval[0]
        progress(search_width ** (-(interval[1] - end) / search_width))
        kwargs['from'] = (interval[1] + end) // 2 + 500
        kwargs['upto'] = end
    return interval


def status_find_timestamp(timestamp, /, **kwargs):
    return status_find(timestamp, **kwargs)


def status_iter(*, lang=None, progress=None, **kwargs):
    # supports author, num, status, count, from, upto, lang
    # from and upto can be timestamps or datetime objects

    # valid slice specs:
    # from (implied: count = <single-request>, upto = 0)
    # count (implied: from = <newest>, upto = 0)
    # upto (implied: from = <newest>, count = inf)
    # from, upto (implied: count = inf)
    # from, count (implied: upto = 0)
    # from, count, upto

    if progress is None:
        def progress(*_, **__):
            pass
    elif progress is True:
        progress = print
    if 'from_' in kwargs:
        kwargs['from'] = kwargs.pop('from_')
    if not isinstance(kwargs.get('from', 0), int):
        _ = kwargs.pop('upto', 'marker')
        kwargs['from'] = status_find_timestamp(kwargs.pop('from'), **kwargs)[0]
        if _ != 'marker':
            kwargs['upto'] = _
    if not isinstance(kwargs.get('upto', 0), int):
        _ = kwargs.pop('from', 'marker')
        kwargs['upto'] = status_find_timestamp(kwargs.pop('upto'), **kwargs)[1]
        if _ != 'marker':
            kwargs['from'] = _
    if lang is not None:
        lang = detect_lang(lang)
    count = kwargs.pop('count', math.inf if 'upto' in kwargs else None)
    kwargs['count'] = 1000
    start_sid = None
    end_sid = kwargs.get('upto', 0)
    start_count = count or math.inf
    current_sid = None
    progress(0.0)
    while True:
        chunk = status_naked(**kwargs)
        if not chunk:
            break
        kwargs['from'] = chunk[-1].submit_id - 1
        if start_sid is None:
            start_sid = current_sid = chunk[0].submit_id
        tail_flag = len(chunk) != 1000
        if lang is not None:
            chunk = [*filter(lambda st: st.lang_code == lang, chunk)]
        if count is None:
            count = len(chunk)
        else:
            del chunk[count:]
        count -= len(chunk)
        yield from chunk
        if tail_flag or count <= 0:
            break
        if chunk:
            current_sid = chunk[-1].submit_id
        progress(max(1 - count / start_count, (start_sid - current_sid) / (start_sid - end_sid)))
    progress(1.0)
    return


def status(**kwargs):
    return [*status_iter(**kwargs)]


def search(author_name):
    url = f"https://acm.timus.ru/search.aspx"
    data = rqs.get(url, params={"Str": author_name}).content.decode('utf-8')
    """
    <tr class="content"><td>12667</td><td><div class="flags-img flag-earth" title="I&#39;m a citizen of the Earth!">
    </div></td><td class="name"><a href="https://acm.timus.ru/author.aspx?id=320816">drbright</a></td><td>5710</td>
    <td>31</td><td>2 ноя 2022 22:16</td></tr>
    """
    p_entry = re.compile(r'(<tr class="content"><td>.*?id=([0-9]+)">(.*?)</a>.*?</tr>)', re.I)
    rsp = {}
    for entry, author_id, author_name in p_entry.findall(data):
        rsp[author_name] = author_id
    return rsp


def author(author_id):
    url = f"https://acm.timus.ru/author.aspx"
    r = rqs.get(url, params={"id": author_id})  # .content.decode('utf-8')
    data = r.text
    p_author = re.compile(r'<h2 class="author_name">(.*?)</h2>', re.I)
    author_name = p_author.findall(data)
    if not author_name:
        return None
    author_name = author_name[0].strip()
    if author_name[0] == '<':
        p_name = re.compile(r'>(.*?)<')
        author_name = p_name.findall(author_name)[0]
    return Author(id=int(author_id), name=author_name.strip())


def get_status(submit_id):
    return status_naked(count=1, from_=submit_id)[0]


def detect_lang(lang):
    if not isinstance(lang, str):
        return None
    langs = supported_langs()
    if lang.lower() in language_detector:
        lang = language_detector[lang.lower()]
    if lang in langs:
        return langs[lang]
    lang = lang.lower()
    ss = re.escape(lang)
    if ss == lang:
        p = re.compile(r'\b' + ss + r'\b')
    else:
        p = re.compile(ss)
    for lang in langs:
        r = p.findall(lang.lower())
        if r:
            return langs[lang]
    return None


def detect_task_id(code_or_filename):
    headpat = re.compile(r"[0-9]{4}")
    if "\n" not in code_or_filename:  # then its a filename
        try:
            return headpat.findall(code_or_filename)[0]
        except IndexError:
            return
    comments = re.compile(r"#.*?$", flags=re.M).findall(code_or_filename)
    comments += re.compile(r'""".*?"""', flags=re.M).findall(code_or_filename)
    comments += re.compile(r"'''.*?'''", flags=re.M).findall(code_or_filename)
    numbers = []
    for comment in comments:
        numbers += headpat.findall(comment)
    if numbers:
        return numbers[0]


def submit(code_or_file, encoding=None, judge_id=None, task_id=None, lang=None, retry=True):
    encoding = encoding or "cp1251"
    if type(code_or_file) is str:
        if os.path.isfile(code_or_file):
            try:
                with open(code_or_file, "rt", encoding=encoding) as f:
                    code = f.read()
            except UnicodeDecodeError:
                with open(code_or_file, "rt", encoding="utf-8") as f:
                    code = f.read()
        else:
            code = code_or_file
    else:
        code = code_or_file.read()
    judge_id = judge_id or default_judge_id
    lang = lang or detect_lang(code_or_file)
    if lang is None:
        raise RuntimeError("Can't deduce language")
    elif lang not in supported_langs().values():
        lang = detect_lang(lang)
        if lang is None:
            raise RuntimeError("Language is not supported")
    if task_id is None:
        task_id = detect_task_id(code_or_file)
        if task_id is None:
            task_id = detect_task_id(code)
            if task_id is None:
                raise RuntimeError("Can't deduce task_id")

    data = {}
    data.update(submit_form)
    data["Language"] = str(lang)
    data["ProblemNum"] = str(task_id)
    data["JudgeID"] = judge_id
    data["Source"] = code.encode("cp1251", errors="replace")
    r = None
    for i in range(5):
        r = rqs.post(
            "https://acm.timus.ru/submit.aspx?space=1",
            data=data,
            files=(),
            allow_redirects=False
        )
        if 'X-SubmitID' in r.headers:  # if response contains X-SubmitID, its ok
            return r.headers['X-SubmitID']
        # otherwise if response text contains red text, that text is an error description
        err_p = re.compile(r"<td .*?color:red.*?>(.*?)</td>", re.IGNORECASE)
        err = err_p.findall(r.text)
        if not err:
            raise RuntimeError(r, r.text)
        err = err[0]
        # if error is 10 seconds timeout, wait 6 seconds
        if '10' not in err:
            raise RuntimeError(err)
        elif not retry:
            return
        time.sleep(6)
    raise RuntimeError(r, r.text)


def submit_sync(code_or_file, encoding=None, judge_id=None, task_id=None, lang=None):
    submit_id = submit(code_or_file, encoding=encoding, judge_id=judge_id, task_id=task_id, lang=lang)
    time.sleep(2)
    st = get_status(submit_id)
    while st.accepted is None:
        time.sleep(1)
        st = get_status(submit_id)
    return st


def print_status(
        st: SubmitStatus,
        file: str | io.TextIOBase | None = sys.stdout,
        encoding: str = None,
        end: str = "\n"
):
    encoding = encoding or "utf-8"
    return_string = False
    close_file = False
    try:
        if file is None:
            return_string = True
            file = io.StringIO()
        elif type(file) == str:
            close_file = True
            file = open(file, "wt", encoding=encoding)
        print(f'Author: {st.author_name} #{st.author_id}')
        print(f'Task: {st.task_id}. {st.task_name}')
        print(f'Language: {st.lang_name}')
        print(f'Date: {datetime.fromtimestamp(st.timestamp)}')
        print(f'Status: {"OK" if st.accepted else "FAIL"}', file=file)
        print(f'Reason: {st.reason}', file=file)
        print(f'Test: {st.test}', file=file)
        print(f'Run time: {st.runtime}', file=file)
        print(f'Used memory: {st.memory} KB', end=end, file=file, flush=True)
        if return_string:
            file.seek(0)
            return file.read()
    finally:
        if close_file:
            file.close()
