import SwiftUI

struct BiweeklyGoalsView: View {
    @Environment(GoalsStore.self) private var store
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var showAdd = false
    @State private var newTitle = ""
    @State private var editingIndex: Int?
    @State private var editTitle = ""
    @State private var undo = UndoState<BiweeklyGoal>()
    @State private var undoCheckedStatus: CheckStatus?

    private var total: Int { store.goals.biweekly_goals.count }
    private var done: Int { (0..<total).filter { store.biweeklyStatus(at: $0) == .done }.count }
    private var working: Int { (0..<total).filter { store.biweeklyStatus(at: $0) == .working }.count }
    private var progress: Double { total > 0 ? Double(done) / Double(total) : 0 }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                List {
                    headerSection
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)

                    if store.goals.biweekly_goals.isEmpty && !undo.isVisible {
                        EmptyStateView(
                            icon: "calendar.badge.clock",
                            title: "No bi-weekly goals",
                            subtitle: "Set goals for this 2-week sprint"
                        )
                    } else {
                        Section {
                            ForEach(Array(store.goals.biweekly_goals.enumerated()), id: \.element.id) { index, goal in
                                Button {
                                    editingIndex = index
                                    editTitle = goal.text
                                } label: {
                                    HStack(spacing: 12) {
                                        StatusBadge(status: store.biweeklyStatus(at: index)) {
                                            store.toggleBiweeklyStatus(at: index)
                                        }
                                        Text(goal.text)
                                            .strikethrough(store.biweeklyStatus(at: index) == .done)
                                            .foregroundStyle(store.biweeklyStatus(at: index) == .done ? .secondary : .primary)
                                        Spacer()
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
                            }
                            .onMove { source, destination in
                                store.moveBiweeklyGoal(from: source, to: destination)
                            }
                        }
                    }
                }
                .navigationTitle("Bi-Weekly")
                .iPadReadableWidth()
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button {
                            newTitle = ""
                            showAdd = true
                        } label: {
                            Image(systemName: "plus")
                        }
                    }
                }
                .alert("New Bi-Weekly Goal", isPresented: $showAdd) {
                    TextField("Goal", text: $newTitle)
                    Button("Cancel", role: .cancel) {}
                    Button("Add") {
                        let trimmed = newTitle.trimmingCharacters(in: .whitespaces)
                        guard !trimmed.isEmpty else { return }
                        store.addBiweeklyGoal(trimmed)
                    }
                }
                .alert("Edit Goal", isPresented: Binding(
                    get: { editingIndex != nil },
                    set: { if !$0 { editingIndex = nil } }
                )) {
                    TextField("Goal", text: $editTitle)
                    Button("Cancel", role: .cancel) { editingIndex = nil }
                    Button("Save") {
                        guard let index = editingIndex, index < store.goals.biweekly_goals.count else { return }
                        let trimmed = editTitle.trimmingCharacters(in: .whitespaces)
                        guard !trimmed.isEmpty else { return }
                        store.goals.biweekly_goals[index].text = trimmed
                        store.saveGoals()
                        editingIndex = nil
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

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: 16) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(BiweeklyState.periodLabel())
                        .font(.title2)
                        .fontWeight(.bold)
                    Text(daysRemaining)
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
                            done == total && total > 0 ? Color.green : Color.purple,
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

    private var daysRemaining: String {
        let (_, end) = BiweeklyState.currentPeriod()
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: Date()), to: end).day ?? 0
        if days == 0 { return "Last day of this period" }
        if days == 1 { return "1 day remaining" }
        return "\(days) days remaining"
    }

    // MARK: - Undo

    private func deleteWithUndo(at index: Int) {
        guard index < store.goals.biweekly_goals.count else { return }
        let item = store.goals.biweekly_goals[index]
        undoCheckedStatus = store.biweeklyStatus(at: index)
        store.deleteBiweeklyGoal(at: IndexSet(integer: index))
        withAnimation { undo.show(item: item, index: index, message: "Deleted") }
    }

    private func performUndo() {
        guard let item = undo.item, let idx = undo.index else { return }
        let insertIdx = min(idx, store.goals.biweekly_goals.count)
        store.goals.biweekly_goals.insert(item, at: insertIdx)
        if let status = undoCheckedStatus {
            store.biweeklyState.checked[String(insertIdx)] = status
        }
        store.saveGoals()
        store.saveBiweeklyState()
        withAnimation { undo.dismiss() }
    }
}
