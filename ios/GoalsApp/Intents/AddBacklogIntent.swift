import AppIntents
import Foundation

struct AddBacklogIntent: AppIntent {
    static var title: LocalizedStringResource = "Add to Backlog"
    static var description = IntentDescription("Add an item to your GoalsApp backlog")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Item")
    var item: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        await iCloudFileManager.shared.initialize()
        let goals = await iCloudFileManager.shared.read(GoalsFile.self, from: "goals.json") ?? GoalsFile()

        let today = DailyState.todayString()
        let newItem = BacklogItem(text: item, added_date: today)

        var updated = goals
        updated.backlog.append(newItem)

        await iCloudFileManager.shared.write(updated, to: "goals.json")

        return .result(dialog: "Added \"\(item)\" to your backlog.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Add \(\.$item) to backlog")
    }
}

struct AddDailyGoalIntent: AppIntent {
    static var title: LocalizedStringResource = "Add Daily Goal"
    static var description = IntentDescription("Add a goal to your today list")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Goal")
    var goal: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        await iCloudFileManager.shared.initialize()
        let goals = await iCloudFileManager.shared.read(GoalsFile.self, from: "goals.json") ?? GoalsFile()

        let today = DailyState.todayString()
        let newGoal = DailyGoal(text: goal, added_date: today)

        var updated = goals
        updated.daily_goals.append(newGoal)

        await iCloudFileManager.shared.write(updated, to: "goals.json")

        return .result(dialog: "Added \"\(goal)\" to today's goals.")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Add \(\.$goal) to today")
    }
}

struct AddBulbIntent: AppIntent {
    static var title: LocalizedStringResource = "Add Idea"
    static var description = IntentDescription("Capture a quick idea in your bulbs list")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Idea")
    var idea: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        await iCloudFileManager.shared.initialize()
        let goals = await iCloudFileManager.shared.read(GoalsFile.self, from: "goals.json") ?? GoalsFile()

        let today = DailyState.todayString()
        let bulb = Bulb(text: idea, created: today)

        var updated = goals
        updated.bulbs.insert(bulb, at: 0)

        await iCloudFileManager.shared.write(updated, to: "goals.json")

        return .result(dialog: "Captured idea: \"\(idea)\"")
    }

    static var parameterSummary: some ParameterSummary {
        Summary("Capture idea \(\.$idea)")
    }
}
