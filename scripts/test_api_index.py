#!/usr/bin/env python3
"""scripts/api-index.py のテスト。DocC JSON は小さなフィクスチャで代える (網を使わない)。"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "api-index.py"
spec = importlib.util.spec_from_file_location("api_index", SCRIPT)
api_index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_index)

DOC = "doc://org.mokume.reference/documentation/mokume/"
IDENTIFIERS = {
    "スケッチを書く": ["Sketch", "Sketch/draw()", "Orbit"],
    "下地と色": ["SketchPart/background(_:)-9jeha", "SketchPart/background(_:_:)", "SketchPart/fill(_:)"],
    "2D の図形": ["SketchPart/circle(_:_:_:)", "SketchPart/width"],
    "角度と数を直す": ["map(_:_:_:_:_:)", "SketchPart/init()"],
}
DOCS = {
    "topicSections": [{"title": t, "identifiers": [DOC + i for i in ids]} for t, ids in IDENTIFIERS.items()],
    "references": {
        DOC + i: {"url": "/documentation/mokume/" + i.lower()} for ids in IDENTIFIERS.values() for i in ids
    },
}

SKETCH = """\
import mokume

@main
final class Orbit: Sketch {
    var settings: SketchSettings { SketchSettings(width: 960) }

    func draw() {
        background(0)
        // fill(255)
        let xs = [1, 2].map { $0 * 2 }
        text("\\(map(1, 0, 1, 0, 2))", 0, 0)
        circle(width / 2, 0, 80)
    }
}
"""


class ApiIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.docs = self.root / "docs.json"
        self.docs.write_text(json.dumps(DOCS))
        self.topics = api_index.load_topics(str(self.docs))

    def tearDown(self):
        self.tmp.cleanup()

    def add_example(self, name, readme, source=SKETCH):
        (self.root / name / "Sources" / name).mkdir(parents=True)
        (self.root / name / "Package.swift").write_text("")
        (self.root / name / "Sources" / name / "Main.swift").write_text(source)
        (self.root / name / "README.md").write_text(readme)

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--docs", str(self.docs), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
        )

    def test_no_examples_gives_empty_index(self):
        self.assertEqual(self.run_script().returncode, 0)
        self.assertTrue((self.root / "API.md").read_text().endswith("まだ無い。\n"))
        self.assertEqual(self.run_script("--check").returncode, 0)

    def test_overloads_fold_into_first_version(self):
        apis = {api.name: api for _, items in self.topics for api in items}
        self.assertEqual(apis["background"].url, "https://mokume.org/documentation/mokume/sketchpart/background(_:)-9jeha/")
        self.assertNotIn("init", apis)

    def test_counts_leads_and_uses_separately(self):
        self.add_example("orbit", "# orbit\n\n`circle(_:_:_:)` · `background`\n\n説明。\n")
        self.assertEqual(self.run_script().returncode, 0)
        text = (self.root / "API.md").read_text()
        self.assertIn("[`circle`](https://mokume.org/documentation/mokume/sketchpart/circle(_:_:_:)/) — **[orbit](orbit/)**", text)
        self.assertIn("[`draw`](https://mokume.org/documentation/mokume/sketch/draw()/) — [orbit](orbit/)\n", text)
        self.assertEqual(self.run_script("--check").returncode, 0)

    def test_ignores_labels_comments_members_and_own_types(self):
        apis = {api.name: api for _, items in self.topics for api in items}
        used = api_index.used_names(SKETCH, apis)
        self.assertIn("width", used)  # `width / 2` は使用
        self.assertIn("map", used)  # 文字列の補間の中は読む
        self.assertNotIn("fill", used)  # コメントの中
        self.assertNotIn("Orbit", used)  # 作例が自分で宣言した型
        self.assertEqual(api_index.used_names("SketchSettings(width: 1)", apis), set())  # 引数ラベル
        self.assertEqual(api_index.used_names("[1].map { $0 }", apis), set())  # 別の値のメンバー

    def test_check_fails_when_index_is_stale(self):
        self.run_script()
        self.add_example("orbit", "# orbit\n\n`circle`\n")
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("API.md が古い", result.stderr)

    def test_check_fails_on_lead_count(self):
        for name, readme in [("none", "# none\n\n説明だけ。\n"), ("many", "# many\n\n`circle` `background` `draw` `width`\n")]:
            self.add_example(name, readme)
        self.run_script()
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("none: README の見出し直後に書く主役の API が 0 個", result.stderr)
        self.assertIn("many: README の見出し直後に書く主役の API が 4 個", result.stderr)

    def test_check_fails_on_unknown_or_unused_lead(self):
        self.add_example("orbit", "# orbit\n\n`circel` · `fill`\n")
        self.run_script()
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("orbit: 主役の `circel` が mokume.org の API に無い", result.stderr)
        self.assertIn("orbit: 主役の `fill` をソースで使っていない", result.stderr)

    def test_lead_is_only_the_first_paragraph(self):
        readme = self.root / "README.md"
        readme.write_text("# orbit\n\n`circle`\n\n`fill` はここでは主役ではない。\n")
        self.assertEqual(api_index.lead_names(readme), ["circle"])


if __name__ == "__main__":
    unittest.main()
