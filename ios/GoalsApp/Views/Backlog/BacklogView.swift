import SwiftUI

struct BacklogView: View {
    @Environment(GoalsStore.self) private var store
    @State private var showAdd = false
    @State private var editingIndex: Int?
    @State private var searchText = ""

    @State private var editTitle = ""
    @State private var editNotes: String?
    @State private var editCategory: String?
    @State private var editScheduledDate: String?

    @State private var undo = UndoState<BacklogItem>()

    private var today: String { DailyState.todayString() }

    private var filtered: [(index: Int, item: BacklogItem)] {
        let items = Array(store.goals.backlog.enumerated()).map { (index: $0.offset, item: $0.element) }
        if searchText.isEmpty { return items }
        return items.filter { $0.item.text.localizedCaseInsensitiveContains(searchText) }
    }

    private var overdue: [(index: Int, item: BacklogItem)] {
        filtered.filter {
            guard let sd = $0.item.scheduled_date else { return false }
            return sd < today
        }
    }

    private var dueSoon: [(index: Int, item: BacklogItem)] {
        filtered.filter {
            guard let sd = $0.item.scheduled_date else { return false }
            return sd >= today && sd <= dateString(daysFromNow: 7)
        }
    }

    private var scheduled: [(index: Int, item: BacklogItem)] {
        filtered.filter {
            guard let sd = $0.item.scheduled_date else { return false }
            return sd > dateString(daysFromNow: 7)
        }
    }

    private var unscheduled: [(index: Int, item: BacklogItem)] {
        filtered.filter { $0.item.scheduled_date == nil }
    }

    private var overdueCount: Int { overdue.count }
    private var dueSoonCount: Int { dueSoon.count }
    private var scheduledTotal: Int {
        store.goals.backlog.filter { $0.scheduled_date != nil }.count
    }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                List {
                    if store.goals.backlog.isEmpty && !undo.isVisible {
                        EmptyStateView(
                            icon: "tray",
                            title: "Backlog is empty",
                            subtitle: "Save ideas for later by adding them here or swiping daily goals to backlog"
                        )
                    } else {
                        // Summary header
                        summaryHeader
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)

                        if !overdue.isEmpty {
                            section(title: "Overdue", items: overdue, tint: .red)
                        }
                        if !dueSoon.isEmpty {
                            section(title: "Due This Week", items: dueSoon, tint: .orange)
                        }
                        if !scheduled.isEmpty {
                            section(title: "Scheduled", items: scheduled, tint: .blue)
                        }
                        if !unscheduled.isEmpty {
                            section(title: "Unscheduled", items: unscheduled, tint: .secondary)
                        }
                    }
                }
                .searchable(text: $searchText, prompt: "Search backlog")
                .navigationTitle("Backlog")
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            editingIndex = nil
                            editTitle = ""
                            editNotes = nil
                            editCategory = nil
                            editScheduledDate = nil
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
                        scheduledDate: $editScheduledDate,
                        showDatePicker: true,
                        showCategoryPicker: true
                    ) {
                        guard !editTitle.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        store.addBacklogItem(editTitle, scheduledDate: editScheduledDate, category: editCategory)
                    }
                    .environment(store)
                }
                .sheet(item: $editingIndex) { index in
                    GoalDetailSheet(
                        title: $editTitle,
                        notes: $editNotes,
                        category: $editCategory,
                        scheduledDate: $editScheduledDate,
                        showDatePicker: true,
                        showCategoryPicker: true
                    ) {
                        guard index < store.goals.backlog.count else { return }
                        store.goals.backlog[index].text = editTitle
                        store.goals.backlog[index].attachment = editNotes
                        store.goals.backlog[index].category = editCategory
                        store.goals.backlog[index].scheduled_date = editScheduledDate
                        store.saveGoals()
                    }
                    .environment(store)
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
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(store.goals.backlog.count) items")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("\(scheduledTotal) scheduled")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }

            if overdueCount > 0 || dueSoonCount > 0 {
                HStack(spacing: 12) {
                    if overdueCount > 0 {
                        headerChip(icon: "exclamationmark.circle.fill", count: overdueCount, label: "Overdue", color: .red)
                    }
                    if dueSoonCount > 0 {
                        headerChip(icon: "clock.fill", count: dueSoonCount, label: "Due Soon", color: .orange)
                    }
                    Spacer()
                }
            }
        }
        .padding()
    }

    private func headerChip(icon: String, count: Int, label: String, color: Color) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundStyle(color)
            Text("\(count) \(label)")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .clipShape(Capsule())
    }

    // MARK: - Sections

    private func section(title: String, items: [(index: Int, item: BacklogItem)], tint: Color) -> some View {
        Section {
            ForEach(items, id: \.item.id) { entry in
                backlogRow(item: entry.item, index: entry.index, sectionTint: tint)
            }
        } header: {
            HStack(spacing: 6) {
                Circle()
                    .fill(tint)
                    .frame(width: 8, height: 8)
                Text("\(title) (\(items.count))")
            }
        }
    }

    // MARK: - Row

    private func backlogRow(item: BacklogItem, index: Int, sectionTint: Color) -> some View {
        Button {
            editingIndex = index
            editTitle = item.text
            editNotes = item.attachment
            editCategory = item.category
            editScheduledDate = item.scheduled_date
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.text)
                        .foregroundStyle(.primary)
                    if let sd = item.scheduled_date {
                        HStack(spacing: 4) {
                            Image(systemName: sd < today ? "exclamationmark.circle.fill" : "calendar.badge.clock")
                                .font(.caption2)
                            Text(sd)
                                .font(.caption2)
                        }
                        .foregroundStyle(sd < today ? .red : .orange)
                    }
                }

                Spacer()

                if let catId = item.category, let info = store.categoryInfo(for: catId) {
                    CategoryTag(text: info.text, colorIndex: info.color)
                }
            }
            .padding(.vertical, 4)
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
                moveToTodayWithUndo(at: index)
            } label: {
                Label("Today", systemImage: "calendar.badge.plus")
            }
            .tint(.green)
        }
    }

    // MARK: - Actions

    private func deleteWithUndo(at index: Int) {
        guard index < store.goals.backlog.count else { return }
        let item = store.goals.backlog[index]
        store.deleteBacklogItem(at: IndexSet(integer: index))
        withAnimation { undo.show(item: item, index: index, message: "Deleted") }
    }

    private func moveToTodayWithUndo(at index: Int) {
        guard index < store.goals.backlog.count else { return }
        let item = store.goals.backlog[index]
        store.addBacklogToToday(at: index)
        withAnimation { undo.show(item: item, index: index, message: "Moved to Today") }
    }

    private func performUndo() {
        guard let item = undo.item, let idx = undo.index else { return }

        if undo.message == "Moved to Today" {
            if let dailyIdx = store.goals.daily_goals.lastIndex(where: { $0.text == item.text }) {
                store.goals.daily_goals.remove(at: dailyIdx)
            }
        }

        let insertIdx = min(idx, store.goals.backlog.count)
        store.goals.backlog.insert(item, at: insertIdx)
        store.saveGoals()
        withAnimation { undo.dismiss() }
    }

    // MARK: - Helpers

    private func dateString(daysFromNow days: Int) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Calendar.current.date(byAdding: .day, value: days, to: Date())!)
    }
}
