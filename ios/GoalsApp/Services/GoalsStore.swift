import Foundation
import Combine
import UIKit
import UserNotifications
import WidgetKit

@Observable
final class GoalsStore {
    var goals = GoalsFile()
    var dailyState = DailyState()
    var yearState = YearState()
    var completedLog: [CompletedLogEntry] = []
    var focusLog: [FocusLogEntry] = []

    private var saveTask: Task<Void, Never>?
    private var metadataQuery: NSMetadataQuery?
    private var isLoading = false

    private var foregroundObserver: Any?

    init() {
        Task {
            await iCloudFileManager.shared.initialize()
            await MainActor.run { load() }
            startMonitoring()
        }
        // Request notification permission for alarms
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
        // Reload when app comes back to foreground
        foregroundObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.willEnterForegroundNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.load()
        }
    }

    deinit {
        metadataQuery?.stop()
        if let obs = foregroundObserver {
            NotificationCenter.default.removeObserver(obs)
        }
    }

    // MARK: - Load

    func load() {
        isLoading = true
        defer { isLoading = false }

        Task {
            let g = await iCloudFileManager.shared.read(GoalsFile.self, from: "goals.json") ?? GoalsFile()
            let ds = await iCloudFileManager.shared.read(DailyState.self, from: ".daily_state.json") ?? DailyState()
            let ys = await iCloudFileManager.shared.read(YearState.self, from: ".year_state.json") ?? YearState()
            let cl = await iCloudFileManager.shared.read([CompletedLogEntry].self, from: "completed_log.json") ?? []
            let fl = await iCloudFileManager.shared.read([FocusLogEntry].self, from: "focus_log.json") ?? []

            await MainActor.run {
                self.goals = g
                self.completedLog = cl
                self.focusLog = fl

                // Handle day/year rollover
                if !ds.isToday {
                    rollOverDaily(oldState: ds)
                } else {
                    self.dailyState = ds
                    promoteScheduledBacklog()
                }

                if !ys.isCurrent {
                    self.yearState = YearState()
                    saveYearState()
                } else {
                    self.yearState = ys
                }

                self.updateWidget()
                self.scheduleAlarmNotifications()
            }
        }
    }

    // MARK: - Save (debounced)

    private func scheduleSaveGoals() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            await iCloudFileManager.shared.write(goals, to: "goals.json")
            await MainActor.run { updateWidget() }
        }
    }

    func saveGoals() {
        scheduleSaveGoals()
    }

    func saveDailyState() {
        Task {
            await iCloudFileManager.shared.write(dailyState, to: ".daily_state.json")
            await MainActor.run { updateWidget() }
        }
    }

    func saveYearState() {
        Task {
            await iCloudFileManager.shared.write(yearState, to: ".year_state.json")
            await MainActor.run { updateWidget() }
        }
    }

    func saveLog() {
        Task { await iCloudFileManager.shared.write(completedLog, to: "completed_log.json") }
    }

    // MARK: - File monitoring (NSMetadataQuery)

    private func startMonitoring() {
        let query = NSMetadataQuery()
        query.searchScopes = [NSMetadataQueryUbiquitousDocumentsScope]
        query.predicate = NSPredicate(format: "%K LIKE '*.json'", NSMetadataItemFSNameKey)

        NotificationCenter.default.addObserver(
            forName: .NSMetadataQueryDidUpdate,
            object: query,
            queue: .main
        ) { [weak self] _ in
            guard let self, !self.isLoading else { return }
            self.load()
        }

        query.start()
        metadataQuery = query
    }

    // MARK: - Daily Goals

    func dailyStatus(at index: Int) -> CheckStatus {
        dailyState.checked[String(index)] ?? .todo
    }

    func toggleDailyStatus(at index: Int) {
        let key = String(index)
        let current = dailyState.checked[key] ?? .todo
        dailyState.checked[key] = current.next
        saveDailyState()
    }

    func addDailyGoal(_ text: String, category: String? = nil) {
        let today = DailyState.todayString()
        let goal = DailyGoal(text: text, added_date: today, category: category)
        goals.daily_goals.append(goal)
        saveGoals()
    }

    func deleteDailyGoal(at offsets: IndexSet) {
        goals.daily_goals.remove(atOffsets: offsets)
        // Rebuild checked state to keep indices consistent
        rebuildDailyChecked(removing: offsets)
        saveGoals()
        saveDailyState()
    }

    func moveDailyGoal(from source: IndexSet, to destination: Int) {
        var items = goals.daily_goals
        items.move(fromOffsets: source, toOffset: destination)
        goals.daily_goals = items
        // Rebuild checked to match new order
        let oldChecked = dailyState.checked
        dailyState.checked = [:]
        var mapping = Array(0..<items.count)
        mapping.move(fromOffsets: source, toOffset: destination)
        for (newIdx, oldIdx) in mapping.enumerated() {
            if let status = oldChecked[String(oldIdx)] {
                dailyState.checked[String(newIdx)] = status
            }
        }
        saveGoals()
        saveDailyState()
    }

    func moveDailyToBacklog(at index: Int) {
        guard index < goals.daily_goals.count else { return }
        let item = goals.daily_goals.remove(at: index)
        let today = DailyState.todayString()
        let backlogItem = BacklogItem(
            text: item.text,
            added_date: today,
            category: item.category,
            attachment: item.attachment,
            files: item.files
        )
        goals.backlog.append(backlogItem)
        rebuildDailyChecked(removing: IndexSet(integer: index))
        saveGoals()
        saveDailyState()
    }

    private func rebuildDailyChecked(removing offsets: IndexSet) {
        let oldChecked = dailyState.checked
        dailyState.checked = [:]
        var newIdx = 0
        for oldIdx in 0..<(goals.daily_goals.count + offsets.count) {
            if offsets.contains(oldIdx) { continue }
            if let status = oldChecked[String(oldIdx)] {
                dailyState.checked[String(newIdx)] = status
            }
            newIdx += 1
        }
    }

    // MARK: - Year Goals

    func yearStatus(at index: Int) -> CheckStatus {
        yearState.checked[String(index)] ?? .todo
    }

    func toggleYearStatus(at index: Int) {
        let key = String(index)
        let current = yearState.checked[key] ?? .todo
        yearState.checked[key] = current.next
        saveYearState()
    }

    func addYearGoal(_ text: String) {
        let goal = YearGoal(text: text, sub_goals: [])
        goals.year_goals.append(goal)
        saveGoals()
    }

    func deleteYearGoal(at offsets: IndexSet) {
        goals.year_goals.remove(atOffsets: offsets)
        saveGoals()
    }

    func moveYearGoal(from source: IndexSet, to destination: Int) {
        goals.year_goals.move(fromOffsets: source, toOffset: destination)
        saveGoals()
    }

    func addSubGoal(to yearIndex: Int, text: String) {
        let id = String(format: "%04x", Int.random(in: 0...0xFFFF))
        let sub = SubGoal(id: id, text: text)
        if goals.year_goals[yearIndex].sub_goals == nil {
            goals.year_goals[yearIndex].sub_goals = []
        }
        goals.year_goals[yearIndex].sub_goals?.append(sub)
        saveGoals()
    }

    func deleteSubGoal(yearIndex: Int, subIndex: Int) {
        goals.year_goals[yearIndex].sub_goals?.remove(at: subIndex)
        saveGoals()
    }

    // MARK: - Backlog

    func addBacklogItem(_ text: String, scheduledDate: String? = nil, category: String? = nil) {
        let today = DailyState.todayString()
        let item = BacklogItem(text: text, added_date: today, scheduled_date: scheduledDate, category: category)
        goals.backlog.append(item)
        saveGoals()
    }

    func deleteBacklogItem(at offsets: IndexSet) {
        goals.backlog.remove(atOffsets: offsets)
        saveGoals()
    }

    func moveBacklogItem(from source: IndexSet, to destination: Int) {
        goals.backlog.move(fromOffsets: source, toOffset: destination)
        saveGoals()
    }

    func addBacklogToToday(at index: Int) {
        guard index < goals.backlog.count else { return }
        let item = goals.backlog.remove(at: index)
        let today = DailyState.todayString()
        let daily = DailyGoal(
            text: item.text,
            added_date: today,
            category: item.category,
            attachment: item.attachment,
            files: item.files
        )
        goals.daily_goals.append(daily)
        saveGoals()
    }

    // MARK: - Bulbs

    func addBulb(_ text: String, category: String? = nil) {
        let today = DailyState.todayString()
        let bulb = Bulb(text: text, created: today, category: category)
        goals.bulbs.insert(bulb, at: 0)
        saveGoals()
    }

    func deleteBulb(at offsets: IndexSet) {
        goals.bulbs.remove(atOffsets: offsets)
        saveGoals()
    }

    func bulbToDaily(at index: Int) {
        guard index < goals.bulbs.count else { return }
        let bulb = goals.bulbs.remove(at: index)
        let today = DailyState.todayString()
        let daily = DailyGoal(text: bulb.text, added_date: today, category: bulb.category)
        goals.daily_goals.append(daily)
        saveGoals()
    }

    func bulbToBacklog(at index: Int) {
        guard index < goals.bulbs.count else { return }
        let bulb = goals.bulbs.remove(at: index)
        let today = DailyState.todayString()
        let item = BacklogItem(text: bulb.text, added_date: today, category: bulb.category)
        goals.backlog.append(item)
        saveGoals()
    }

    // MARK: - Alarms

    func addAlarm(_ text: String, date: String, time: String) {
        let alarm = Alarm(text: text, time: time, date: date)
        goals.alarms.append(alarm)
        goals.alarms.sort { ($0.date, $0.time) < ($1.date, $1.time) }
        saveGoals()
        scheduleAlarmNotifications()
    }

    func deleteAlarm(at offsets: IndexSet) {
        goals.alarms.remove(atOffsets: offsets)
        saveGoals()
        scheduleAlarmNotifications()
    }

    func scheduleAlarmNotifications() {
        let center = UNUserNotificationCenter.current()
        // Remove all existing alarm notifications, then reschedule
        center.removePendingNotificationRequests(withIdentifiers:
            goals.alarms.map { "alarm-\($0.date)-\($0.time)-\($0.text)" }
        )
        center.removeAllPendingNotificationRequests()

        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        let tf = DateFormatter()
        tf.dateFormat = "HH:mm"

        for alarm in goals.alarms {
            guard let alarmDate = df.date(from: alarm.date),
                  let alarmTime = tf.date(from: alarm.time) else { continue }

            let cal = Calendar.current
            var comps = cal.dateComponents([.year, .month, .day], from: alarmDate)
            let timeComps = cal.dateComponents([.hour, .minute], from: alarmTime)
            comps.hour = timeComps.hour
            comps.minute = timeComps.minute

            guard let fireDate = cal.date(from: comps), fireDate > Date() else { continue }

            let content = UNMutableNotificationContent()
            content.title = "⏰ Alarm"
            content.body = "\(alarm.time) — \(alarm.text)"
            content.sound = .default

            let triggerComps = cal.dateComponents([.year, .month, .day, .hour, .minute], from: fireDate)
            let trigger = UNCalendarNotificationTrigger(dateMatching: triggerComps, repeats: false)

            let id = "alarm-\(alarm.date)-\(alarm.time)-\(alarm.text)"
            let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
            center.add(request)
        }
    }

    // MARK: - Rollover

    func rollOverDaily(oldState: DailyState? = nil) {
        let state = oldState ?? dailyState
        let completedDate = state.date
        let oldTasks = goals.daily_goals

        var kept: [DailyGoal] = []
        for (i, task) in oldTasks.enumerated() {
            let status = state.checked[String(i)] ?? .todo
            if status == .done {
                let added = task.added_date ?? completedDate
                let daysCount = daysBetween(from: added, to: completedDate)
                let entry = CompletedLogEntry(
                    text: task.text,
                    added_date: added,
                    completed_date: completedDate,
                    days: daysCount
                )
                completedLog.append(entry)
            } else {
                kept.append(task)
            }
        }

        goals.daily_goals = kept
        dailyState = DailyState()
        saveGoals()
        saveDailyState()
        saveLog()
        promoteScheduledBacklog()
    }

    func promoteScheduledBacklog() {
        let today = DailyState.todayString()
        var remaining: [BacklogItem] = []
        var changed = false
        for item in goals.backlog {
            if let sd = item.scheduled_date, sd <= today {
                let daily = DailyGoal(text: item.text, added_date: today, category: item.category)
                goals.daily_goals.append(daily)
                changed = true
            } else {
                remaining.append(item)
            }
        }
        if changed {
            goals.backlog = remaining
            saveGoals()
        }
    }

    // MARK: - Category Helpers

    struct CategoryInfo {
        let text: String
        let color: Int  // index into CAT_COLORS
    }

    func categoryInfo(for catId: String?) -> CategoryInfo? {
        guard let catId else { return nil }
        for (gi, yg) in goals.year_goals.enumerated() {
            for sub in yg.sub_goals ?? [] {
                if sub.id == catId {
                    return CategoryInfo(text: sub.text, color: gi % Constants.catColors.count)
                }
            }
        }
        return nil
    }

    /// All sub-goals grouped by year goal, for category picker
    var categoryGroups: [(yearGoal: String, subGoals: [SubGoal])] {
        goals.year_goals.compactMap { yg in
            guard let subs = yg.sub_goals, !subs.isEmpty else { return nil }
            return (yearGoal: yg.text, subGoals: subs)
        }
    }

    // MARK: - Widget

    func updateWidget() {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        let now = Date()

        let dailyItems = goals.daily_goals.enumerated().map { (i, goal) -> WidgetGoalItem in
            let status = dailyState.checked[String(i)] ?? .todo
            let statusStr: String
            switch status {
            case .todo: statusStr = "todo"
            case .working: statusStr = "working"
            case .done: statusStr = "done"
            }
            var days: Int? = nil
            if let added = goal.added_date, let d = df.date(from: added) {
                days = max(1, Calendar.current.dateComponents([.day], from: d, to: now).day! + 1)
            }
            return WidgetGoalItem(text: goal.text, status: statusStr, daysActive: days)
        }

        let yearItems = goals.year_goals.enumerated().map { (i, goal) -> WidgetGoalItem in
            let status = yearState.checked[String(i)] ?? .todo
            let statusStr: String
            switch status {
            case .todo: statusStr = "todo"
            case .working: statusStr = "working"
            case .done: statusStr = "done"
            }
            return WidgetGoalItem(text: goal.text, status: statusStr, daysActive: nil)
        }

        let widgetData = WidgetData(
            dailyGoals: dailyItems,
            dailyDone: dailyItems.filter { $0.status == "done" }.count,
            dailyTotal: dailyItems.count,
            yearGoals: yearItems,
            yearDone: yearItems.filter { $0.status == "done" }.count,
            yearTotal: yearItems.count,
            lastUpdated: now
        )
        widgetData.save()
        WidgetCenter.shared.reloadAllTimelines()
    }

    // MARK: - Helpers

    private func daysBetween(from: String, to: String) -> Int {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        guard let d1 = f.date(from: from), let d2 = f.date(from: to) else { return 1 }
        return max(1, Calendar.current.dateComponents([.day], from: d1, to: d2).day! + 1)
    }
}
