import Foundation
import mokume

@main
final class Hello: Sketch {
    var settings: SketchSettings {
        SketchSettings(width: 960, height: 540, title: "Hello")
    }

    func draw() {
        background(15, 18, 23)
        noSuchShowcaseAPI()
        fill(242, 115, 51)
        let angle = time * 0.8
        circle(width / 2 + cos(angle) * 160, height / 2 + sin(angle) * 120, 80)
    }
}
