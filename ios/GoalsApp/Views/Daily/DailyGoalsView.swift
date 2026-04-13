import SwiftUI

struct DailyGoalsView: View {
    @Environment(GoalsStore.self) private var store
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var showAdd = false
    @State private var editingIndex: Int?

    @State private var editTitle = ""
    @State private var editNotes: String?
    @State private var editCategory: String?

    @State private var undo = UndoState<DailyGoal>()
    @State private var undoCheckedStatus: CheckStatus?

    @State private var showAddAlarm = false
    @State private var alarmText = ""
    @State private var alarmDate = Date()
    @State private var alarmTime = AlarmsHelper.defaultTime()
    @State private var editingAlarmIndex: Int?
    @State private var editAlarmText = ""
    @State private var editAlarmDate = Date()
    @State private var editAlarmTime = Date()

    private var total: Int { store.goals.daily_goals.count }
    private var done: Int { (0..<total).filter { store.dailyStatus(at: $0) == .done }.count }
    private var working: Int { (0..<total).filter { store.dailyStatus(at: $0) == .working }.count }
    private var progress: Double { total > 0 ? Double(done) / Double(total) : 0 }

    var body: some View {
        @Bindable var store = store
        NavigationStack {
            ZStack(alignment: .bottom) {
                List {
                    todayHeader
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)

                    if store.goals.daily_goals.isEmpty && !undo.isVisible {
                        EmptyStateView(
                            icon: "target",
                            title: "No goals today",
                            subtitle: "Tap + to add your first goal for today"
                        )
                    } else {
                        Section {
                            ForEach(Array(store.goals.daily_goals.enumerated()), id: \.element.id) { index, goal in
                                Button {
                                    editingIndex = index
                                    editTitle = goal.text
                                    editNotes = goal.attachment
                                    editCategory = goal.category
                                } label: {
                                    DailyGoalRow(goal: goal, index: index)
                                }
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) {
                                        deleteWithUndo(at: index)
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                                .swipeActions(edge: .leading) {
                                    Button {
                                        store.moveDailyToBacklog(at: index)
                                    } label: {
                                        Label("Backlog", systemImage: "tray.and.arrow.down")
                                    }
                                    .tint(.orange)
                                }
                            }
                            .onMove { source, destination in
                                store.moveDailyGoal(from: source, to: destination)
                            }
                        }
                    }

                    // === Alarms ===
                    alarmsSection
                }
                .navigationTitle("Today")
                .iPadReadableWidth()
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            editingIndex = nil
                            editTitle = ""
                            editNotes = nil
                            editCategory = nil
                            showAdd = true
                        } label: {
                            Image(systemName: "plus")
                        }
                    }
                }
                .sheet(isPresented: $showAdd) {
                    GoalDetailSheet(
                        title: $editTitle,
                        notes: $editNotes,
                        category: $editCategory,
                        scheduledDate: .constant(nil),
                        showDatePicker: false,
                        showCategoryPicker: true
                    ) {
                        guard !editTitle.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.addDailyGoal(editTitle, category: editCategory)
                    }
                    .environment(store)
                }
                .sheet(item: $editingIndex) { index in
                    GoalDetailSheet(
                        title: $editTitle,
                        notes: $editNotes,
                        category: $editCategory,
                        scheduledDate: .constant(nil),
                        showDatePicker: false,
                        showCategoryPicker: true,
                        files: index < store.goals.daily_goals.count ? store.goals.daily_goals[index].files ?? [] : []
                    ) {
                        guard index < store.goals.daily_goals.count else { return }
                        store.goals.daily_goals[index].text = editTitle
                        store.goals.daily_goals[index].attachment = editNotes
                        store.goals.daily_goals[index].category = editCategory
                        store.saveGoals()
                    }
                    .environment(store)
                }
                .refreshable {
                    store.load()
                }
                .sheet(isPresented: $showAddAlarm) {
                    alarmSheet(title: "New Alarm", text: $alarmText, alarmDate: $alarmDate, time: $alarmTime) {
                        guard !alarmText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.addAlarm(alarmText, date: AlarmsHelper.dateString(from: alarmDate), time: AlarmsHelper.timeString(from: alarmTime))
                    }
                }
                .sheet(item: $editingAlarmIndex) { index in
                    alarmSheet(title: "Edit Alarm", text: $editAlarmText, alarmDate: $editAlarmDate, time: $editAlarmTime) {
                        guard index < store.goals.alarms.count else { return }
                        guard !editAlarmText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.goals.alarms[index].text = editAlarmText
                        store.goals.alarms[index].date = AlarmsHelper.dateString(from: editAlarmDate)
                        store.goals.alarms[index].time = AlarmsHelper.timeString(from: editAlarmTime)
                        store.goals.alarms.sort { ($0.date, $0.time) < ($1.date, $1.time) }
                        store.saveGoals()
                        store.scheduleAlarmNotifications()
                    }
                }

                if undo.isVisible {
                    UndoToast(message: undo.message) {
                        performUndo()
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .padding(.bottom, 8)
                }
            }
        }
    }

    // MARK: - Delete with Undo

    private func deleteWithUndo(at index: Int) {
        guard index < store.goals.daily_goals.count else { return }
        let item = store.goals.daily_goals[index]
        undoCheckedStatus = store.dailyStatus(at: index)
        store.deleteDailyGoal(at: IndexSet(integer: index))
        withAnimation { undo.show(item: item, index: index, message: "Deleted") }
    }

    private func performUndo() {
        guard let item = undo.item, let idx = undo.index else { return }
        let insertIdx = min(idx, store.goals.daily_goals.count)
        store.goals.daily_goals.insert(item, at: insertIdx)
        // Rebuild checked indices to make room for re-inserted item
        var newChecked: [String: CheckStatus] = [:]
        for (key, val) in store.dailyState.checked {
            guard let k = Int(key) else { continue }
            newChecked[String(k >= insertIdx ? k + 1 : k)] = val
        }
        if let status = undoCheckedStatus {
            newChecked[String(insertIdx)] = status
        }
        store.dailyState.checked = newChecked
        store.saveGoals()
        store.saveDailyState()
        withAnimation { undo.dismiss() }
    }

    // MARK: - Today Header

    private var todayHeader: some View {
        VStack(spacing: 16) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(greeting)
                        .font(.title2)
                        .fontWeight(.bold)
                    Text(formattedDate)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                ZStack {
                    Circle()
                        .stroke(Color(.systemGray5), lineWidth: 6)
                    Circle()
                        .trim(from: 0, to: progress)
                        .stroke(
                            done == total && total > 0 ? Color.green : Color.blue,
                            style: StrokeStyle(lineWidth: 6, lineCap: .round)
                        )
                        .rotationEffect(.degrees(-90))
                        .animation(.spring(response: 0.4), value: progress)
                    Text("\(done)/\(total)")
                        .font(.caption)
                        .fontWeight(.semibold)
                }
                .frame(width: sizeClass == .regular ? 72 : 52, height: sizeClass == .regular ? 72 : 52)
            }

            if total > 0 {
                HStack(spacing: 12) {
                    statusChip(icon: "checkmark.circle.fill", count: done, label: "Done", color: .green)
                    statusChip(icon: "hammer.fill", count: working, label: "Working", color: .orange)
                    statusChip(icon: "circle", count: total - done - working, label: "To Do", color: .gray)
                    Spacer()
                }
            }
        }
        .padding()
    }

    private func statusChip(icon: String, count: Int, label: String, color: Color) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundStyle(color)
            Text("\(count)")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .clipShape(Capsule())
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good Morning"
        case 12..<17: return "Good Afternoon"
        case 17..<22: return "Good Evening"
        default: return "Good Night"
        }
    }

    private var formattedDate: String {
        let f = DateFormatter()
        f.dateFormat = "EEEE, MMM d"
        return f.string(from: Date())
    }

    // MARK: - Alarms Section

    private var alarmsSection: some View {
        Section {
            ForEach(Array(store.goals.alarms.enumerated()), id: \.element.id) { index, alarm in
                Button {
                    editingAlarmIndex = index
                    editAlarmText = alarm.text
                    editAlarmDate = AlarmsHelper.parseDate(alarm.date)
                    editAlarmTime = AlarmsHelper.parseTime(alarm.time)
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "alarm.fill")
                            .font(.subheadline)
                            .foregroundStyle(.orange)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(alarm.text)
                                .foregroundStyle(.primary)
                            HStack(spacing: 4) {
                                Text(AlarmsHelper.relativeDate(alarm.date))
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                Text(alarm.time)
                                    .font(.caption2)
                                    .fontWeight(.semibold)
                                    .foregroundStyle(.orange)
                            }
                        }

                        Spacer()

                        Text(alarm.time)
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                    }
                    .padding(.vertical, 2)
                }
                .swipeActions(edge: .trailing) {
                    Button(role: .destructive) {
                        store.deleteAlarm(at: IndexSet(integer: index))
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
            }

            Button {
                alarmText = ""
                alarmDate = Date()
                alarmTime = AlarmsHelper.defaultTime()
                showAddAlarm = true
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                        .foregroundStyle(.orange)
                    Text("Add Alarm")
                        .foregroundStyle(.orange)
                }
            }
        } header: {
            HStack {
                Image(systemName: "alarm")
                    .font(.caption)
                Text("Alarms")
            }
        }
    }

    private func alarmSheet(title: String, text: Binding<String>, alarmDate: Binding<Date>, time: Binding<Date>, onSave: @escaping () -> Void) -> some View {
        NavigationStack {
            Form {
                Section("Alarm Name") {
                    TextField("What's this alarm for?", text: text)
                }
                Section("Date") {
                    DatePicker("Date", selection: alarmDate, displayedComponents: .date)
                        .datePickerStyle(.graphical)
                }
                Section("Time") {
                    DatePicker("Time", selection: time, displayedComponents: .hourAndMinute)
                        .datePickerStyle(.wheel)
                        .labelsHidden()
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showAddAlarm = false
                        editingAlarmIndex = nil
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave()
                        showAddAlarm = false
                        editingAlarmIndex = nil
                    }
                    .disabled(text.wrappedValue.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }
}

enum AlarmsHelper {
    static func defaultTime() -> Date {
        return Date()
    }

    static func parseTime(_ timeStr: String) -> Date {
        let parts = timeStr.split(separator: ":")
        guard parts.count == 2, let h = Int(parts[0]), let m = Int(parts[1]) else {
            return defaultTime()
        }
        let cal = Calendar.current
        var comps = cal.dateComponents([.year, .month, .day], from: Date())
        comps.hour = h
        comps.minute = m
        return cal.date(from: comps) ?? defaultTime()
    }

    static func parseDate(_ dateStr: String) -> Date {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: dateStr) ?? Date()
    }

    static func timeString(from date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.string(from: date)
    }

    static func dateString(from date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    static func relativeDate(_ dateStr: String) -> String {
        let todayStr = dateString(from: Date())
        if dateStr == todayStr { return "Today" }
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: dateStr) else { return dateStr }
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: Date()), to: Calendar.current.startOfDay(for: d)).day ?? 0
        if days == 1 { return "Tomorrow" }
        if days == -1 { return "Yesterday" }
        if days < 0 { return "\(-days)d ago" }
        if days <= 7 { return "In \(days)d" }
        return dateStr
    }
}

extension Int: @retroactive Identifiable {
    public var id: Int { self }
}
