import SwiftUI

struct BulbsView: View {
    @Environment(GoalsStore.self) private var store
    @State private var showAdd = false
    @State private var editingIndex: Int?
    @State private var searchText = ""

    @State private var editTitle = ""
    @State private var editNotes: String?
    @State private var editCategory: String?

    @State private var undo = UndoState<Bulb>()

    private var filtered: [EnumeratedSequence<[Bulb]>.Element] {
        let items = Array(store.goals.bulbs.enumerated())
        if searchText.isEmpty { return items }
        return items.filter { $0.element.text.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                List {
                    if store.goals.bulbs.isEmpty && !undo.isVisible {
                        EmptyStateView(
                            icon: "lightbulb",
                            title: "No ideas yet",
                            subtitle: "Capture quick ideas and thoughts here — move them to today or backlog when ready"
                        )
                    } else {
                        // Summary header
                        summaryHeader
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)

                        Section {
                            ForEach(filtered, id: \.element.id) { index, bulb in
                                Button {
                                    editingIndex = index
                                    editTitle = bulb.text
                                    editNotes = bulb.attachment
                                    editCategory = bulb.category
                                } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "lightbulb.fill")
                                            .font(.subheadline)
                                            .foregroundStyle(.yellow)

                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(bulb.text)
                                                .foregroundStyle(.primary)
                                            if let created = bulb.created {
                                                Text(created)
                                                    .font(.caption2)
                                                    .foregroundStyle(.secondary)
                                            }
                                        }

                                        Spacer()

                                        if let catId = bulb.category, let info = store.categoryInfo(for: catId) {
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
                                        store.bulbToDaily(at: index)
                                    } label: {
                                        Label("Today", systemImage: "calendar.badge.plus")
                                    }
                                    .tint(.green)

                                    Button {
                                        store.bulbToBacklog(at: index)
                                    } label: {
                                        Label("Backlog", systemImage: "tray.and.arrow.down")
                                    }
                                    .tint(.orange)
                                }
                            }
                        } header: {
                            Text("\(filtered.count) ideas")
                        }
                    }
                }
                .searchable(text: $searchText, prompt: "Search ideas")
                .navigationTitle("Bulbs")
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
                        store.addBulb(editTitle, category: editCategory)
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
                        showCategoryPicker: true
                    ) {
                        guard index < store.goals.bulbs.count else { return }
                        store.goals.bulbs[index].text = editTitle
                        store.goals.bulbs[index].attachment = editNotes
                        store.goals.bulbs[index].category = editCategory
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
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("\(store.goals.bulbs.count) ideas")
                    .font(.title2)
                    .fontWeight(.bold)
                if let newest = store.goals.bulbs.first?.created {
                    Text("Latest: \(newest)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
        .padding()
    }

    // MARK: - Actions

    private func deleteWithUndo(at index: Int) {
        guard index < store.goals.bulbs.count else { return }
        let item = store.goals.bulbs[index]
        store.deleteBulb(at: IndexSet(integer: index))
        withAnimation { undo.show(item: item, index: index, message: "Deleted") }
    }

    private func performUndo() {
        guard let item = undo.item, let idx = undo.index else { return }
        let insertIdx = min(idx, store.goals.bulbs.count)
        store.goals.bulbs.insert(item, at: insertIdx)
        store.saveGoals()
        withAnimation { undo.dismiss() }
    }
}
