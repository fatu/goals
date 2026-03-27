import Foundation

struct AttachedFile: Codable, Equatable {
    var name: String
    var path: String
}

struct DailyGoal: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    var added_date: String?
    var category: String?
    var attachment: String?
    var files: [AttachedFile]?

    enum CodingKeys: String, CodingKey {
        case text, added_date, category, attachment, files
    }
}

struct SubGoal: Codable, Identifiable, Equatable {
    var id: String  // persisted short hex id (e.g. "1aeb")
    var text: String
    var attachment: String?

    var stableID: String { id }

    enum CodingKeys: String, CodingKey {
        case id, text, attachment
    }
}

struct YearGoal: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    var sub_goals: [SubGoal]?

    enum CodingKeys: String, CodingKey {
        case text, sub_goals
    }
}

struct BacklogItem: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    var added_date: String?
    var scheduled_date: String?
    var category: String?
    var attachment: String?
    var files: [AttachedFile]?

    enum CodingKeys: String, CodingKey {
        case text, added_date, scheduled_date, category, attachment, files
    }
}

struct Bulb: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    var created: String?
    var category: String?
    var attachment: String?
    var files: [AttachedFile]?

    enum CodingKeys: String, CodingKey {
        case text, created, category, attachment, files
    }
}

struct Alarm: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    var time: String  // "HH:MM"
    var date: String  // "YYYY-MM-DD"

    enum CodingKeys: String, CodingKey {
        case text, time, date
    }
}

struct GoalsFile: Codable {
    var daily_goals: [DailyGoal]
    var year_goals: [YearGoal]
    var backlog: [BacklogItem]
    var bulbs: [Bulb]
    var focus_videos: [String]
    var alarms: [Alarm]

    init() {
        daily_goals = []
        year_goals = []
        backlog = []
        bulbs = []
        focus_videos = []
        alarms = []
    }

    enum CodingKeys: String, CodingKey {
        case daily_goals, year_goals, backlog, bulbs, focus_videos, alarms
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        daily_goals = (try? container.decode([DailyGoal].self, forKey: .daily_goals)) ?? []
        year_goals = (try? container.decode([YearGoal].self, forKey: .year_goals)) ?? []
        backlog = (try? container.decode([BacklogItem].self, forKey: .backlog)) ?? []
        bulbs = (try? container.decode([Bulb].self, forKey: .bulbs)) ?? []
        focus_videos = (try? container.decode([String].self, forKey: .focus_videos)) ?? []
        alarms = (try? container.decode([Alarm].self, forKey: .alarms)) ?? []
    }
}
