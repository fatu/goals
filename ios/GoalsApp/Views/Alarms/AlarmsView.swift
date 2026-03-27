import SwiftUI

struct AlarmsView: View {
    @Environment(GoalsStore.self) private var store
    @State private var showAdd = false
    @State private var newText = ""
    @State private var newDate = Date()
    @State private var newTime = defaultAlarmDate()
    @State private var editingIndex: Int?
    @State private var editText = ""
    @State private var editDate = Date()
    @State private var editTime = Date()

    @State private var undo = UndoState<Alarm>()

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                List {
                    if store.goals.alarms.isEmpty && !undo.isVisible {
                        EmptyStateView(
                            icon: "alarm",
                            title: "No alarms",
                            subtitle: "Add alarms to get reminders at specific dates and times"
                        )
                    } else {
                        summaryHeader
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)

                        Section {
                            ForEach(Array(store.goals.alarms.enumerated()), id: \.element.id) { index, alarm in
                                Button {
                                    editingIndex = index
                                    editText = alarm.text
                                    editDate = Self.parseDate(alarm.date)
                                    editTime = Self.parseTime(alarm.time)
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "alarm.fill")
                                            .font(.title3)
                                            .foregroundStyle(.orange)

                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(alarm.text)
                                                .foregroundStyle(.primary)
                                            HStack(spacing: 6) {
                                                Text(alarm.date)
                                                    .font(.caption)
                                                    .foregroundStyle(.secondary)
                                                Text(alarm.time)
                                                    .font(.caption)
                                                    .fontWeight(.semibold)
                                                    .foregroundStyle(.orange)
                                            }
                                        }

                                        Spacer()

                                        VStack(alignment: .trailing, spacing: 2) {
                                            Text(alarm.time)
                                                .font(.title2)
                                                .fontWeight(.bold)
                                                .foregroundStyle(.secondary)
                                                .monospacedDigit()
                                            Text(Self.relativeDate(alarm.date))
                                                .font(.caption2)
                                                .foregroundStyle(.tertiary)
                                        }
                                    }
                                    .padding(.vertical, 6)
                                }
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) {
                                        deleteWithUndo(at: index)
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                            }
                            .onMove { source, destination in
                                store.goals.alarms.move(fromOffsets: source, toOffset: destination)
                                store.saveGoals()
                            }
                        } header: {
                            Text("\(store.goals.alarms.count) alarms")
                        }
                    }
                }
                .navigationTitle("Alarms")
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            newText = ""
                            newDate = Date()
                            newTime = Self.defaultAlarmDate()
                            showAdd = true
                        } label: {
                            Image(systemName: "plus")
                        }
                    }
                }
                .sheet(isPresented: $showAdd) {
                    alarmSheet(title: "New Alarm", text: $newText, alarmDate: $newDate, time: $newTime) {
                        guard !newText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.addAlarm(newText, date: Self.dateString(from: newDate), time: Self.timeString(from: newTime))
                    }
                }
                .sheet(item: $editingIndex) { index in
                    alarmSheet(title: "Edit Alarm", text: $editText, alarmDate: $editDate, time: $editTime) {
                        guard index < store.goals.alarms.count else { return }
                        guard !editText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.goals.alarms[index].text = editText
                        store.goals.alarms[index].date = Self.dateString(from: editDate)
                        store.goals.alarms[index].time = Self.timeString(from: editTime)
                        store.goals.alarms.sort { ($0.date, $0.time) < ($1.date, $1.time) }
                        store.saveGoals()
                    }
                }
                .refreshable {
                    store.load()
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

    // MARK: - Summary Header

    private var summaryHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("\(store.goals.alarms.count) alarms")
                    .font(.title2)
                    .fontWeight(.bold)
                if let next = nextAlarm() {
                    Text("Next: \(next.date) \(next.time) — \(next.text)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
        .padding()
    }

    // MARK: - Alarm Sheet

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
                        showAdd = false
                        editingIndex = nil
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave()
                        showAdd = false
                        editingIndex = nil
                    }
                    .disabled(text.wrappedValue.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    // MARK: - Actions

    private func deleteWithUndo(at index: Int) {
        guard index < store.goals.alarms.count else { return }
        let item = store.goals.alarms[index]
        store.deleteAlarm(at: IndexSet(integer: index))
        withAnimation { undo.show(item: item, index: index, message: "Deleted") }
    }

    private func performUndo() {
        guard let item = undo.item, let idx = undo.index else { return }
        let insertIdx = min(idx, store.goals.alarms.count)
        store.goals.alarms.insert(item, at: insertIdx)
        store.saveGoals()
        withAnimation { undo.dismiss() }
    }

    private func nextAlarm() -> Alarm? {
        let todayStr = Self.dateString(from: Date())
        let nowTime = Self.timeString(from: Date())
        // First try today's upcoming alarms
        if let next = store.goals.alarms.first(where: { $0.date == todayStr && $0.time >= nowTime }) {
            return next
        }
        // Then future alarms
        return store.goals.alarms.first { $0.date > todayStr }
            ?? store.goals.alarms.first
    }

    // MARK: - Helpers

    static func defaultAlarmDate() -> Date {
        return Date()
    }

    static func parseTime(_ timeStr: String) -> Date {
        let parts = timeStr.split(separator: ":")
        guard parts.count == 2, let h = Int(parts[0]), let m = Int(parts[1]) else {
            return defaultAlarmDate()
        }
        let cal = Calendar.current
        var comps = cal.dateComponents([.year, .month, .day], from: Date())
        comps.hour = h
        comps.minute = m
        return cal.date(from: comps) ?? defaultAlarmDate()
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
