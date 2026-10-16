# showcase

## 作例の約束

- **1 作例 = 1 フォルダ = 1 SwiftPM パッケージ。** products に executable を 1 つ (`mokume run` が名前をそこから取る)。
  形は `mokume new` の雛形のまま: swift-tools 6.2・`.macOS("26.0")`・
  `.swiftLanguageMode(.v6), .defaultIsolation(MainActor.self)`・mokume は `from:` で最新のリリース
- **リリース版の API だけを使う。** main にしか無いものは使わない
- **1 ファイルで、小さく。** 真似しやすさが目的
- **外部素材を使わない。** 使うなら帰属が明確なものだけ
- **`Package.resolved` を置かない。** CI が毎日最新のリリースで組み直して保証する
- **作例の README の冒頭に、主役の API を 1〜3 個書く。** 見出し直後の段落にインラインコードで (`` `circle` ``)。[API.md](API.md) の入口になる
- **作れなかった題材は [works](https://github.com/mokume-metal/works) へ回す。** ここは作れるものだけを置く
- **mokume 本体からは参照されない。** 依存は showcase → mokume の一方向

## 確かめるコマンド

```bash
scripts/build-all.sh          # 全作例が組めること (CI と同じ)
scripts/api-index.py          # API.md を作り直す
scripts/api-index.py --check  # API.md・主役の API のずれ (CI と同じ)
```
