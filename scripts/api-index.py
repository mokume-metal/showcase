#!/usr/bin/env python3
"""API ごとの目次 API.md を作る。`--check` は書かずに、ずれを見つけたら非 0 で終わる。

API の並びは mokume.org の DocC JSON (トピックの順) に従う。作例ごとに 2 つを数える:

- 主役: 作例 README の見出し直後の段落に、インラインコードで書いた API (1〜3 個)
- 使用: 作例のソース (Sources/**/*.swift) に出てくる API

使用は字句で拾う近似で、型は解かない。作例は小さく自分たちで書くので足りるとする。
オーバーロードは名前 1 つに畳み (`background(_:)` も `background(_:_:)` も `background`)、
リンク先はトピック順で最初の版にする。
"""

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DOCS_URL = "https://mokume.org/data/documentation/mokume.json"
SITE = "https://mokume.org"
OUTPUT = "API.md"

# Swift のキーワードと重なり、字句では見分けられない名前
IGNORED = {"init", "get", "set"}

HEADER = f"""# API ごとの作例

<!-- scripts/api-index.py が生成する。手で直さない -->

並びは [mokume.org]({SITE}/documentation/mokume/) のトピック順。**太字**はその作例の主役、ほかはソースで使っているもの。
"""


@dataclass(frozen=True)
class Api:
    name: str
    url: str
    top_level: bool  # SketchPart などの型の中ではなく、モジュール直下にある


def base_name(text):
    """`SketchPart/background(_:)-9jeha` や `circle(_:_:_:)` を `background` / `circle` へ畳む。"""
    last = re.split(r"[/.]", text.split("(")[0])[-1]
    return re.sub(r"-[0-9a-z]+$", "", last).strip()


def load_topics(source):
    """[(トピック名, [Api])] を返す。同じ名前は最初に出たトピックにだけ置く。"""
    if re.match(r"https?://", source):
        request = urllib.request.Request(source, headers={"User-Agent": "showcase-api-index"})
        with urllib.request.urlopen(request, timeout=30) as response:
            docs = json.load(response)
    else:
        docs = json.loads(Path(source).read_text())

    seen = set()
    topics = []
    for section in docs["topicSections"]:
        apis = []
        for identifier in section["identifiers"]:
            path = identifier.split("/documentation/mokume/", 1)[1]
            name = base_name(path)
            if name in seen or name in IGNORED:
                continue
            seen.add(name)
            url = SITE + docs["references"][identifier]["url"].rstrip("/") + "/"
            apis.append(Api(name, url, "/" not in path))
        topics.append((section["title"], apis))
    return topics


def tokenize(source):
    """Swift のソースを (種類, 字) の列にする。コメントと文字列は落とし、文字列の補間 `\\(…)` は読む。"""
    tokens = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c.isspace():
            i += 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
        elif source.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if source.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif source.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif c == '"' or (c == "#" and source.startswith('#"', i)):
            i = skip_string(source, i, tokens)
            tokens.append(("str", ""))
        elif c.isalpha() or c == "_":
            m = re.compile(r"[A-Za-z_][A-Za-z0-9_]*").match(source, i)
            tokens.append(("ident", m.group()))
            i = m.end()
        elif c == "`":
            end = source.find("`", i + 1)
            end = n if end < 0 else end
            tokens.append(("ident", source[i + 1 : end]))
            i = end + 1
        else:
            tokens.append(("punct", c))
            i += 1
    return tokens


def skip_string(source, i, tokens):
    """i から始まる文字列の終わりの次を返す。補間の中身は tokens へ足す。"""
    raw = 0
    while source[i] == "#":
        raw, i = raw + 1, i + 1
    quote = '"""' if source.startswith('"""', i) else '"'
    close = quote + "#" * raw
    escape = "\\" + "#" * raw
    i += len(quote)
    n = len(source)
    while i < n:
        if source.startswith(close, i):
            return i + len(close)
        if source.startswith(escape, i):
            i += len(escape)
            if i < n and source[i] == "(":
                depth, start = 1, i + 1
                i += 1
                while i < n and depth:
                    depth += {"(": 1, ")": -1}.get(source[i], 0)
                    i += 1
                tokens.extend(tokenize(source[start : i - 1]))
            else:
                i += 1
        else:
            i += 1
    return n


def used_names(source, apis):
    tokens = tokenize(source)
    # 作例が自分で宣言した型 (`final class Orbit: Sketch` など) は、同名の API があっても別物
    declared = {
        text for (_, prev), (kind, text) in zip(tokens, tokens[1:])
        if kind == "ident" and prev in ("class", "struct", "enum", "actor", "protocol", "typealias")
    }
    used = set()
    for k, (kind, text) in enumerate(tokens):
        api = apis.get(text)
        if kind != "ident" or api is None or text in declared:
            continue
        prev = tokens[k - 1][1] if k > 0 else ""
        nxt = tokens[k + 1][1] if k + 1 < len(tokens) else ""
        if nxt == ":" and prev in ("(", ","):
            continue  # 引数ラベル
        if prev == "." and api.top_level and text[0].islower():
            continue  # `array.map` のように、別の値のメンバー
        used.add(text)
    return used


def lead_names(readme):
    """見出し直後の最初の段落にあるインラインコードを、順に (重複なしで) 返す。"""
    if not readme.exists():
        return []
    paragraph = []
    lines = readme.read_text().splitlines()
    start = next((k + 1 for k, line in enumerate(lines) if line.startswith("# ")), None)
    if start is None:
        return []
    for line in lines[start:]:
        if line.strip():
            paragraph.append(line)
        elif paragraph:
            break
    names = []
    for code in re.findall(r"`([^`]+)`", "\n".join(paragraph)):
        name = base_name(code)
        if name not in names:
            names.append(name)
    return names


def find_examples(root):
    return sorted(p.parent.name for p in root.glob("*/Package.swift"))


def collect(root, topics):
    """作例ごとの (主役, 使用) と、主役の約束違反を返す。"""
    apis = {api.name: api for _, items in topics for api in items}
    examples = {}
    problems = []
    for name in find_examples(root):
        sources = "\n".join(p.read_text() for p in sorted((root / name / "Sources").rglob("*.swift")))
        used = used_names(sources, apis)
        leads = lead_names(root / name / "README.md")
        if not 1 <= len(leads) <= 3:
            problems.append(f"{name}: README の見出し直後に書く主役の API が {len(leads)} 個 (1〜3 個にする)")
        for lead in leads:
            if lead not in apis:
                problems.append(f"{name}: 主役の `{lead}` が mokume.org の API に無い")
            elif lead not in used:
                problems.append(f"{name}: 主役の `{lead}` をソースで使っていない")
        examples[name] = ([l for l in leads if l in apis], used)
    return examples, problems


def render(topics, examples):
    if not examples:
        return HEADER + "\nまだ無い。\n"
    out = [HEADER]
    for title, items in topics:
        lines = []
        for api in items:
            leads = [e for e, (lead, _) in examples.items() if api.name in lead]
            users = [e for e, (lead, used) in examples.items() if api.name in used and api.name not in lead]
            if not leads and not users:
                continue
            links = [f"**[{e}]({e}/)**" for e in leads] + [f"[{e}]({e}/)" for e in users]
            lines.append(f"- [`{api.name}`]({api.url}) — " + " · ".join(links))
        if lines:
            out.append(f"\n## {title}\n\n" + "\n".join(lines) + "\n")
    return "".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="書かずに、ずれがあれば非 0 で終わる")
    parser.add_argument("--docs", default=DOCS_URL, help="DocC JSON の URL かファイル")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()

    topics = load_topics(args.docs)
    examples, problems = collect(args.root, topics)
    text = render(topics, examples)
    output = args.root / OUTPUT

    if args.check:
        if not output.exists() or output.read_text() != text:
            problems.append(f"{OUTPUT} が古い (scripts/api-index.py で作り直す)")
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        print(f"{OUTPUT} は最新 (作例 {len(examples)} 本)")
        return 0

    output.write_text(text)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{OUTPUT} を書いた (作例 {len(examples)} 本)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
