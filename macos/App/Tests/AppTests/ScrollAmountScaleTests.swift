import XCTest
@testable import App

final class ScrollAmountScaleTests: XCTestCase {
    func testRatioAnchorsAndSymmetry() {
        for (percent, position): (UInt32, Double) in [(25, -2), (50, -1), (100, 0), (200, 1), (400, 2)] {
            XCTAssertEqual(ScrollAmountScale.position(for: percent), position, accuracy: 1e-12)
            XCTAssertEqual(ScrollAmountScale.percent(at: position), percent)
        }
        for position in stride(from: 0.0, through: 2.0, by: 0.125) {
            let lower = Double(ScrollAmountScale.percent(at: -position))
            let upper = Double(ScrollAmountScale.percent(at: position))
            XCTAssertEqual(log2(lower / 100), -log2(upper / 100), accuracy: 0.03)
        }
    }

    func testEveryCommittedIntegerRoundTripsWithoutQuantization() {
        for percent: UInt32 in 25...400 {
            XCTAssertEqual(ScrollAmountScale.percent(at: ScrollAmountScale.position(for: percent)), percent)
        }
    }

    func testTrackBoundsAndMonotonicity() {
        XCTAssertEqual(ScrollAmountScale.percent(at: -10), 25)
        XCTAssertEqual(ScrollAmountScale.percent(at: 10), 400)
        var previous: UInt32 = 25
        for position in stride(from: -2.0, through: 2.0, by: 0.001) {
            let percent = ScrollAmountScale.percent(at: position)
            XCTAssertTrue((25...400).contains(percent))
            XCTAssertGreaterThanOrEqual(percent, previous)
            previous = percent
        }
    }
}
