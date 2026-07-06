# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Built-in course: **Python 高级程序设计**.

A fixed, version-controlled sample course used to develop and test the STUDY
learning surface. The content here is intentionally small but *real* (correct,
runnable Python) placeholder material; it can later be swapped for a full
textbook without touching the seeder.

Shape (consumed by :mod:`learning.builtin_course_seed`)::

    COURSE = {
        "space": {"space_id": ..., "title": ...},
        "artifacts": [ <envelope-payload dicts, contract-valid> ],
        "materials": [ {"path": "<relpath>", "content": "<text>"} ],
    }

Every artifact dict is a ``LearningOutputEnvelope`` *payload half*: the seeder
supplies ``kind`` / ``title`` and passes ``payload`` through
``OutputWriter.write_artifact`` so the frozen contract validates it.
"""

from __future__ import annotations

from typing import Any, Dict

# Stable id so the built-in course is recognizable and re-seed is idempotent.
SPACE_ID = "builtin-python-advanced"
SPACE_TITLE = "Python 高级程序设计"

# Directory (relative to the workspace root) the materials are written into.
MATERIALS_SUBDIR = "courses/python-advanced"

_SOURCE_REFS = [{"origin": "builtin:python-advanced"}]


# --------------------------------------------------------------------------- #
# Embedded source materials (placeholder — real content, small size).
# --------------------------------------------------------------------------- #

_README_MD = """\
# Python 高级程序设计

面向已掌握 Python 基础语法的学习者，聚焦语言的高级特性与工程实践。

## 模块
1. 迭代器与生成器（惰性求值、协程雏形）
2. 装饰器与闭包（函数即对象、`functools.wraps`）
3. 上下文管理器（`with`、`__enter__/__exit__`、`contextlib`）
4. 并发与 asyncio（GIL、线程/进程、事件循环）
5. 元编程（描述符、元类、`__getattr__`）

## 说明
本目录为内置示例课程的占位素材，内容真实可运行，供学习功能开发与测试使用。
"""

_ITERATORS_MD = """\
# 迭代器与生成器

## 迭代器协议
一个对象是**可迭代对象**（iterable）当它实现 `__iter__`，返回一个**迭代器**
（iterator）——实现 `__next__`，并在耗尽时抛出 `StopIteration`。

```python
class Countdown:
    def __init__(self, n): self.n = n
    def __iter__(self): return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1
```

## 生成器
`yield` 让函数成为生成器，自动实现迭代器协议并**惰性求值**：

```python
def countdown(n):
    while n > 0:
        yield n
        n -= 1
```

生成器一次只在内存中保留一个值，适合处理大/无限序列。`yield from` 委托给
子生成器；生成器还能通过 `.send()` 接收值，是原生协程的雏形。
"""

_DECORATORS_MD = """\
# 装饰器与闭包

**闭包**：内层函数捕获外层作用域变量。**装饰器**是接收函数、返回函数的高阶函数。

```python
import functools

def logged(func):
    @functools.wraps(func)          # 保留 __name__/__doc__/签名
    def wrapper(*args, **kwargs):
        print(f"call {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@logged
def add(a, b):
    return a + b
```

`@logged` 等价于 `add = logged(add)`。带参数的装饰器再包一层工厂函数。
务必使用 `functools.wraps`，否则被装饰函数的元信息会丢失。
"""

_CONTEXT_MD = """\
# 上下文管理器

`with` 语句保证资源被确定性地获取与释放，即使发生异常。

```python
class Timer:
    def __enter__(self):
        import time
        self.t0 = time.perf_counter()
        return self
    def __exit__(self, exc_type, exc, tb):
        import time
        self.elapsed = time.perf_counter() - self.t0
        return False            # 不吞异常
```

`contextlib.contextmanager` 用生成器简化写法：`yield` 之前是 `__enter__`，
之后（放在 `finally`）是 `__exit__`。
"""

_ASYNCIO_MD = """\
# 并发与 asyncio

- **GIL**：CPython 同一时刻只有一个线程执行字节码；线程适合 I/O 密集，
  CPU 密集应使用多进程（`multiprocessing`）。
- **asyncio**：单线程事件循环上的协作式并发，`async def` 定义协程，`await`
  在等待点让出控制权。

```python
import asyncio

async def fetch(name, delay):
    await asyncio.sleep(delay)
    return name

async def main():
    return await asyncio.gather(fetch("a", 0.1), fetch("b", 0.05))

asyncio.run(main())
```

`await` 只挂起当前协程而非阻塞线程，因此成千上万的 I/O 任务可并发进行。
"""

_METAPROG_MD = """\
# 元编程

## 描述符
实现 `__get__/__set__/__delete__` 的对象，放在类属性上可拦截属性访问，
`property`、方法、`classmethod` 都是描述符。

```python
class Positive:
    def __set_name__(self, owner, name): self.name = "_" + name
    def __get__(self, obj, owner): return getattr(obj, self.name)
    def __set__(self, obj, value):
        if value <= 0:
            raise ValueError("must be positive")
        setattr(obj, self.name, value)
```

## 元类
类的类。`type(name, bases, ns)` 动态造类；自定义元类可在类创建时校验/注册。
多数场景 `__init_subclass__` 或类装饰器已足够，元类是最后手段。
"""

_ITERATORS_PY = '''\
"""迭代器与生成器示例。"""


def countdown(n):
    """惰性倒计时生成器。"""
    while n > 0:
        yield n
        n -= 1


def take(iterable, k):
    """取前 k 个元素，适用于无限生成器。"""
    out = []
    for i, x in enumerate(iterable):
        if i >= k:
            break
        out.append(x)
    return out


if __name__ == "__main__":
    print(list(countdown(3)))          # [3, 2, 1]
    print(take((i * i for i in range(10**9)), 5))  # [0, 1, 4, 9, 16]
'''

_DECORATORS_PY = '''\
"""带参数的装饰器示例：重试。"""

import functools
import time


def retry(times=3, delay=0.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - demo
                    last = exc
                    time.sleep(delay)
            raise last
        return wrapper
    return decorator


@retry(times=2)
def flaky(counter=[0]):
    counter[0] += 1
    if counter[0] < 2:
        raise ValueError("not yet")
    return "ok"


if __name__ == "__main__":
    print(flaky())   # ok
'''

_ASYNCIO_PY = '''\
"""asyncio 并发抓取示例。"""

import asyncio


async def fetch(name, delay):
    await asyncio.sleep(delay)
    return name


async def main():
    results = await asyncio.gather(
        fetch("a", 0.10),
        fetch("b", 0.05),
        fetch("c", 0.01),
    )
    return results


if __name__ == "__main__":
    print(asyncio.run(main()))   # ['a', 'b', 'c']
'''

_MATERIALS = [
    {"path": "README.md", "content": _README_MD},
    {"path": "01-iterators-generators.md", "content": _ITERATORS_MD},
    {"path": "02-decorators.md", "content": _DECORATORS_MD},
    {"path": "03-context-managers.md", "content": _CONTEXT_MD},
    {"path": "04-concurrency-asyncio.md", "content": _ASYNCIO_MD},
    {"path": "05-metaprogramming.md", "content": _METAPROG_MD},
    {"path": "code/iterators_generators.py", "content": _ITERATORS_PY},
    {"path": "code/decorators.py", "content": _DECORATORS_PY},
    {"path": "code/asyncio_demo.py", "content": _ASYNCIO_PY},
]


# --------------------------------------------------------------------------- #
# Structured artifacts (contract-valid payloads).
# --------------------------------------------------------------------------- #

def _learning_plan() -> Dict[str, Any]:
    return {
        "kind": "learning_plan",
        "title": "Python 高级程序设计 · 学习计划",
        "payload": {
            "goals": [
                "掌握迭代器/生成器、装饰器、上下文管理器等语言机制",
                "理解 GIL 与 asyncio 并发模型并能选择合适方案",
                "了解描述符与元类等元编程手段及其适用边界",
            ],
            "phases": [
                {
                    "title": "阶段一：迭代与惰性求值",
                    "tasks": [
                        {"title": "阅读《迭代器与生成器》讲义", "order": 1,
                         "done_when": "能手写迭代器协议与生成器"},
                        {"title": "运行并修改 iterators_generators.py", "order": 2,
                         "done_when": "能用生成器处理无限序列"},
                    ],
                },
                {
                    "title": "阶段二：装饰器与上下文管理器",
                    "tasks": [
                        {"title": "实现一个带参数的装饰器", "order": 1,
                         "done_when": "正确使用 functools.wraps"},
                        {"title": "用 contextlib 写一个上下文管理器", "order": 2,
                         "done_when": "异常路径下资源仍被释放"},
                    ],
                },
                {
                    "title": "阶段三：并发与元编程",
                    "tasks": [
                        {"title": "对比线程/进程/asyncio 的适用场景", "order": 1,
                         "done_when": "能解释 GIL 对 CPU 密集任务的影响"},
                        {"title": "用描述符实现属性校验", "order": 2,
                         "done_when": "非法赋值抛出 ValueError"},
                    ],
                },
            ],
        },
    }


def _knowledge_base() -> Dict[str, Any]:
    return {
        "kind": "knowledge_base",
        "title": "Python 高级程序设计 · 核心概念",
        "payload": {
            "concepts": [
                {"term": "迭代器协议",
                 "explanation": "对象实现 __iter__ 返回迭代器，迭代器实现 __next__ 并在耗尽时抛 StopIteration。"},
                {"term": "生成器",
                 "explanation": "用 yield 定义的函数，惰性产出值，自动实现迭代器协议，内存占用低。"},
                {"term": "闭包",
                 "explanation": "内层函数捕获并记住外层作用域的变量，即使外层已返回。"},
                {"term": "装饰器",
                 "explanation": "接收函数、返回新函数的高阶函数；@f 等价于 target = f(target)。"},
                {"term": "上下文管理器",
                 "explanation": "实现 __enter__/__exit__（或用 contextlib.contextmanager），保证资源确定性释放。"},
                {"term": "GIL",
                 "explanation": "CPython 全局解释器锁，同一时刻仅一个线程执行字节码；CPU 密集宜用多进程。"},
                {"term": "协程与 await",
                 "explanation": "async def 定义协程，await 在等待点让出事件循环，实现单线程协作式并发。"},
                {"term": "描述符",
                 "explanation": "实现 __get__/__set__/__delete__ 的类属性，可拦截属性访问；property 即描述符。"},
                {"term": "元类",
                 "explanation": "类的类，控制类的创建过程；多数场景 __init_subclass__ 或类装饰器已足够。"},
            ],
        },
    }


def _resource_pack() -> Dict[str, Any]:
    return {
        "kind": "resource_pack",
        "title": "Python 高级程序设计 · 资料清单",
        "payload": {
            "resources": [
                {"title": "课程总览 README.md", "purpose": "了解课程结构与模块划分",
                 "credibility": "内置课程素材"},
                {"title": "讲义：迭代器与生成器", "purpose": "掌握惰性求值与迭代器协议"},
                {"title": "讲义：装饰器与闭包", "purpose": "理解高阶函数与 functools.wraps"},
                {"title": "讲义：上下文管理器", "purpose": "掌握 with 与资源管理"},
                {"title": "讲义：并发与 asyncio", "purpose": "理解 GIL 与事件循环并发模型"},
                {"title": "讲义：元编程", "purpose": "了解描述符与元类的适用边界"},
                {"title": "代码：iterators_generators.py / decorators.py / asyncio_demo.py",
                 "purpose": "可运行示例，配合讲义练习"},
            ],
        },
    }


def _flashcard_deck() -> Dict[str, Any]:
    return {
        "kind": "flashcard_deck",
        "title": "Python 高级 · 记忆卡片",
        "payload": {
            "cards": [
                {"front": "可迭代对象与迭代器的区别？",
                 "back": "可迭代对象实现 __iter__ 返回迭代器；迭代器实现 __next__ 并在耗尽时抛 StopIteration。",
                 "tags": ["迭代器"]},
                {"front": "生成器相比列表的主要优势？",
                 "back": "惰性求值，一次只保留一个值，适合大/无限序列，节省内存。",
                 "tags": ["生成器"]},
                {"front": "yield from 的作用？",
                 "back": "把迭代/发送委托给子生成器，简化嵌套生成器代码。",
                 "tags": ["生成器"]},
                {"front": "为什么装饰器要用 functools.wraps？",
                 "back": "否则被包装函数的 __name__/__doc__/签名等元信息会被 wrapper 覆盖。",
                 "tags": ["装饰器"]},
                {"front": "@deco 等价于什么？",
                 "back": "target = deco(target)。带参装饰器则是 target = deco(args)(target)。",
                 "tags": ["装饰器"]},
                {"front": "上下文管理器的两个协议方法？",
                 "back": "__enter__（进入，返回绑定给 as 的对象）与 __exit__（退出，返回 True 可吞异常）。",
                 "tags": ["上下文管理器"]},
                {"front": "GIL 对多线程意味着什么？",
                 "back": "同一时刻仅一个线程执行字节码；I/O 密集受益于线程，CPU 密集应用多进程。",
                 "tags": ["并发"]},
                {"front": "await 会阻塞线程吗？",
                 "back": "不会。它挂起当前协程并把控制权交回事件循环，其它任务可继续运行。",
                 "tags": ["asyncio"]},
                {"front": "property 属于什么机制？",
                 "back": "描述符：实现了 __get__/__set__/__delete__，用于拦截属性访问。",
                 "tags": ["描述符"]},
                {"front": "何时该用元类？",
                 "back": "极少数需要在类创建时统一改写/注册的场景；通常 __init_subclass__ 或类装饰器足够。",
                 "tags": ["元类"]},
            ],
        },
    }


def _quiz() -> Dict[str, Any]:
    return {
        "kind": "quiz",
        "title": "Python 高级 · 自测",
        "payload": {
            "questions": [
                {
                    "type": "choice",
                    "prompt": "下列哪项最能体现生成器的核心优势？",
                    "options": ["运行更快", "惰性求值、内存占用低", "自动多线程", "类型更安全"],
                    "answer": 1,
                    "explanation": "生成器一次只产出一个值，惰性求值，适合大/无限序列。",
                    "tags": ["生成器"],
                    "points": 2,
                },
                {
                    "type": "true_false",
                    "prompt": "由于 GIL，CPython 的多线程无法让 CPU 密集型任务获得并行加速。",
                    "answer": True,
                    "explanation": "GIL 限制同一时刻仅一个线程执行字节码，CPU 密集应改用多进程。",
                    "tags": ["并发", "GIL"],
                    "points": 1,
                },
                {
                    "type": "true_false",
                    "prompt": "await 会阻塞整个线程直到结果返回。",
                    "answer": False,
                    "explanation": "await 仅挂起当前协程并让出事件循环，不阻塞线程。",
                    "tags": ["asyncio"],
                    "points": 1,
                },
                {
                    "type": "choice",
                    "prompt": "装饰器中应使用哪个工具保留原函数元信息？",
                    "options": ["functools.reduce", "functools.wraps", "functools.partial", "functools.cache"],
                    "answer": 1,
                    "explanation": "functools.wraps 复制 __name__/__doc__/__wrapped__ 等元信息。",
                    "tags": ["装饰器"],
                    "points": 1,
                },
                {
                    "type": "short_answer",
                    "prompt": "迭代器耗尽时应抛出哪个异常？",
                    "answer": "StopIteration",
                    "accepted": ["stopiteration"],
                    "explanation": "__next__ 在没有更多元素时抛 StopIteration，for 循环据此终止。",
                    "tags": ["迭代器"],
                    "points": 1,
                },
                {
                    "type": "short_answer",
                    "prompt": "实现了 __get__/__set__ 的类属性统称为什么？（中文或英文均可）",
                    "answer": "描述符",
                    "accepted": ["descriptor", "描述符"],
                    "explanation": "描述符（descriptor）用于拦截属性访问，property 即其应用。",
                    "tags": ["描述符"],
                    "points": 1,
                },
                {
                    "type": "choice",
                    "prompt": "上下文管理器的 __exit__ 返回 True 会发生什么？",
                    "options": ["重新进入 with", "吞掉 with 体内的异常", "关闭解释器", "无任何影响"],
                    "answer": 1,
                    "explanation": "__exit__ 返回真值表示异常已被处理，不再向外传播。",
                    "tags": ["上下文管理器"],
                    "points": 2,
                },
            ],
        },
    }


COURSE: Dict[str, Any] = {
    "space": {"space_id": SPACE_ID, "title": SPACE_TITLE},
    "source_refs": _SOURCE_REFS,
    "materials_subdir": MATERIALS_SUBDIR,
    "materials": _MATERIALS,
    "artifacts": [
        _learning_plan(),
        _knowledge_base(),
        _resource_pack(),
        _flashcard_deck(),
        _quiz(),
    ],
}
