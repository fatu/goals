import Foundation

struct DailyState: Codable {
    var date: String
    var checked: [String: CheckStatus]
    var fired_alarms: [String]?

    init() {
        date = Self.todayString()
        checked = [:]
        fired_alarms = []
    }

    static func todayString() -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }

    var isToday: Bool {
        date == Self.todayString()
    }
}
