// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "Hello",
    platforms: [.macOS("26.0")],
    // **実行ファイルを宣言する。** 宣言が無くても走らせる方法はあるが、道具が
    // 実行ファイルの場所を解決できなくなり、起動のたびに遠回りを払うことになる
    products: [.executable(name: "Hello", targets: ["Hello"])],
    dependencies: [.package(
    url: "https://github.com/mokume-metal/mokume.git",
    from: "0.1.0")],
    targets: [
        .executableTarget(
            name: "Hello",
            dependencies: [.product(name: "mokume", package: "mokume")],
            // **資材の置き場をここで宣言する。** 宣言が無いとビルドは静かに通り、
            // 実行時に読めないだけになる — 絵が出ないのに描画側を疑うことになるので、
            // ひな形の時点で宣言しておく
            resources: [.copy("assets")],
            swiftSettings: [.swiftLanguageMode(.v6), .defaultIsolation(MainActor.self)])
    ]
)
