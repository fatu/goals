import SwiftUI

struct YearGoalsView: View {
    @Environment(GoalsStore.self) private var store
    @State private var showAdd = false
    @State private var newGoalText = ""

    var body: some View {
        NavigationStack {
            List {
                progressSection

                if store.goals.year_goals.isEmpty {
                    EmptyStateView(
                        icon: "star",
                        title: "No year goals",
                        subtitle: "Set your big goals for the year and break them into sub-goals"
                    )
                } else {
                    Section {
                        ForEach(Array(store.goals.year_goals.enumerated()), id: \.element.id) { index, goal in
                            YearGoalCard(goal: goal, index: index)
                                .swipeActions(edge: .trailing) {
                                    Button(role: .destructive) {
                                        store.deleteYearGoal(at: IndexSet(integer: index))
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                        }
                        .onMove { source, destination in
                            store.moveYearGoal(from: source, to: destination)
                        }
                    }
                }
            }
            .navigationTitle("\(currentYear) Goals")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showAdd = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .alert("New Year Goal", isPresented: $showAdd) {
                TextField("Goal", text: $newGoalText)
                Button("Add") {
                    guard !newGoalText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                    store.addYearGoal(newGoalText)
                    newGoalText = ""
                }
                Button("Cancel", role: .cancel) { newGoalText = "" }
            }
            .refreshable {
                store.load()
            }
        }
    }

    private var progressSection: some View {
        Section {
            let total = store.goals.year_goals.count
            let done = (0..<total).filter { store.yearStatus(at: $0) == .done }.count
            VStack(spacing: 8) {
                HStack {
                    Text("\(done)/\(total) completed")
                        .font(.headline)
                    Spacer()
                    if total > 0 {
                        Text("\(Int(Double(done) / Double(total) * 100))%")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                    }
                }
                if total > 0 {
                    ProgressView(value: Double(done), total: Double(total))
                        .tint(done == total ? .green : .blue)
                }
            }
            .padding(.vertical, 4)
        }
    }

    private var currentYear: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy"
        return f.string(from: Date())
    }
}
