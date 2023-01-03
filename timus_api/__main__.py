"""
timus_api <command> [parameters...]   (to omit optional parameters use -)

timus_api                       - prints this help message
timus_api help                  - prints this help message
timus_api submit <source> [task_id] [judge_id] [lang] [encoding] - submits solution, waits for verdict and prints it
            Examples: submit task1000.py - - - utf-8  - lang and task_id are inferred, default judge_id used
                      submit task1000.py              - everything is inferred, system's defaults assumed
                      submit "print(sum(map(int, input().split)))" 1000 320816ZW py cp1251
                                                      - everything is specified, string is used as a source
                      submit - 1000 - py cp866        - source is read from stdin
"""

# TODO: testing
# TODO: more cli interfaces
# TODO: add support for cli keys and cli keyword arguments

from . import *


def print_help(*_):
    print(__doc__)


def submit(source=None, task_id=None, judge_id=None, lang=None, encoding=None):
    if source is None:
        if encoding is None:
            source = sys.stdin.read()
        else:
            source = sys.stdin.buffer.read().decode(encoding).replace('\r\n', '\n').replace('\r', '\n')
    try:
        st = submit_sync(source, encoding=encoding, judge_id=judge_id, task_id=task_id, lang=lang)
        print_status(st)
    except Exception as e:
        print(repr(e))


args: list[str | None] = sys.argv[1:]
for i in range(len(args)):
    if args[i] == '-':
        args[i] = None
if not args or args[0] in ('help', '-h', '--help', '/?'):
    print_help(*args[1:])
elif args[0] == 'submit':
    submit(*args[1:])
else:
    print(f'ERROR: Unknown command "{args[0]}"')
    exit(1)


