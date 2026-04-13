import Foundation

struct BiweeklyState: Codable {
    var period_start: String
    var checked: [String: CheckStatus]

    static let epoch: Date = {
        var comps = DateComponents()
        comps.year = 2026; comps.month = 4; comps.day = 6
        return Calendar.current.date(from: comps)!
    }()

    init() {
        period_start = Self.currentPeriodStart()
        checked = [:]
    }

    static func currentPeriodStart() -> String {
        let (start, _) = currentPeriod()
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: start)
    }

    static func currentPeriod() -> (start: Date, end: Date) {
        let cal = Calendar.current
        let today = cal.startOfDay(for: Date())
        let epoch = cal.startOfDay(for: Self.epoch)
        let days = cal.dateComponents([.day], from: epoch, to: today).day ?? 0
        let periodIndex = max(0, days / 14)
        let start = cal.date(byAdding: .day, value: periodIndex * 14, to: epoch)!
        let end = cal.date(byAdding: .day, value: 13, to: start)!
        return (start, end)
    }

    static func periodLabel() -> String {
        let (start, end) = currentPeriod()
        let f = DateFormatter()
        f.dateFormat = "MMM d"
        return "\(f.string(from: start)) – \(f.string(from: end))"
    }

    var isCurrent: Bool {
        period_start == Self.currentPeriodStart()
    }
}
