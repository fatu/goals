import Foundation

struct CompletedLogEntry: Codable, Identifiable {
    var id = UUID()
    var text: String
    var added_date: String?
    var completed_date: String?
    var days: Int?

    enum CodingKeys: String, CodingKey {
        case text, added_date, completed_date, days
    }
}

struct FocusLogEntry: Codable, Identifiable {
    var id = UUID()
    var date: String
    var seconds: Int

    enum CodingKeys: String, CodingKey {
        case date, seconds
    }

    var formattedDuration: String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        if h > 0 {
            return String(format: "%dh %02dm", h, m)
        }
        return "\(m)m"
    }
}
