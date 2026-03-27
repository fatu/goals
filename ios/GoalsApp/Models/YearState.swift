import Foundation

struct YearState: Codable {
    var year: String
    var checked: [String: CheckStatus]

    init() {
        year = Self.currentYear()
        checked = [:]
    }

    static func currentYear() -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy"
        return f.string(from: Date())
    }

    var isCurrent: Bool {
        year == Self.currentYear()
    }
}
