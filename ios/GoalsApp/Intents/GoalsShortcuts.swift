import AppIntents

struct GoalsShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AddBacklogIntent(),
            phrases: [
                "Add to backlog in \(.applicationName)",
                "Add backlog item in \(.applicationName)"
            ],
            shortTitle: "Add to Backlog",
            systemImageName: "tray.and.arrow.down"
        )
        AppShortcut(
            intent: AddDailyGoalIntent(),
            phrases: [
                "Add goal to today in \(.applicationName)",
                "Add daily goal in \(.applicationName)"
            ],
            shortTitle: "Add Daily Goal",
            systemImageName: "calendar.badge.plus"
        )
        AppShortcut(
            intent: AddBulbIntent(),
            phrases: [
                "Capture idea in \(.applicationName)",
                "Add idea in \(.applicationName)"
            ],
            shortTitle: "Capture Idea",
            systemImageName: "lightbulb"
        )
    }
}
