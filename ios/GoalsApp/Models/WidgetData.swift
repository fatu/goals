import Foundation

struct WidgetGoalItem: Codable {
    let text: String
    let status: String // "todo", "working", "done"
    let daysActive: Int?
}

struct WidgetData: Codable {
    let dailyGoals: [WidgetGoalItem]
    let dailyDone: Int
    let dailyTotal: Int
    let yearGoals: [WidgetGoalItem]
    let yearDone: Int
    let yearTotal: Int
    let lastUpdated: Date

    static let userDefaultsKey = "widgetData"

    static func load() -> WidgetData? {
        guard let defaults = UserDefaults(suiteName: Constants.appGroupID),
              let data = defaults.data(forKey: userDefaultsKey) else { return nil }
        return try? JSONDecoder().decode(WidgetData.self, from: data)
    }

    func save() {
        guard let defaults = UserDefaults(suiteName: Constants.appGroupID),
              let data = try? JSONEncoder().encode(self) else { return }
        defaults.set(data, forKey: Self.userDefaultsKey)
    }

    static var placeholder: WidgetData {
        WidgetData(
            dailyGoals: [
                WidgetGoalItem(text: "Morning exercise", status: "done", daysActive: 3),
                WidgetGoalItem(text: "Read chapter", status: "working", daysActive: 1),
                WidgetGoalItem(text: "Write report", status: "todo", daysActive: 5),
            ],
            dailyDone: 1,
            dailyTotal: 3,
            yearGoals: [
                WidgetGoalItem(text: "Learn Swift", status: "working", daysActive: nil),
                WidgetGoalItem(text: "Read 10 books", status: "todo", daysActive: nil),
            ],
            yearDone: 0,
            yearTotal: 2,
            lastUpdated: Date()
        )
    }
}
