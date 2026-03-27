import SwiftUI

struct YearGoalCard: View {
    let goal: YearGoal
    let index: Int
    @Environment(GoalsStore.self) private var store
    @State private var showAddSub = false
    @State private var newSubText = ""

    var body: some View {
        let color = Constants.catColors[index % Constants.catColors.count]

        DisclosureGroup {
            // Sub-goals
            ForEach(Array((goal.sub_goals ?? []).enumerated()), id: \.element.id) { subIdx, sub in
                HStack {
                    Circle()
                        .fill(color.opacity(0.5))
                        .frame(width: 6, height: 6)
                    Text(sub.text)
                        .font(.subheadline)
                    Spacer()
                }
                .swipeActions(edge: .trailing) {
                    Button(role: .destructive) {
                        store.deleteSubGoal(yearIndex: index, subIndex: subIdx)
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
            }

            // Add sub-goal
            Button {
                showAddSub = true
            } label: {
                Label("Add sub-goal", systemImage: "plus")
                    .font(.subheadline)
                    .foregroundStyle(color)
            }
            .alert("New Sub-Goal", isPresented: $showAddSub) {
                TextField("Sub-goal", text: $newSubText)
                Button("Add") {
                    guard !newSubText.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                    store.addSubGoal(to: index, text: newSubText)
                    newSubText = ""
                }
                Button("Cancel", role: .cancel) { newSubText = "" }
            }
        } label: {
            HStack(spacing: 10) {
                StatusBadge(status: store.yearStatus(at: index)) {
                    store.toggleYearStatus(at: index)
                }

                Circle()
                    .fill(color)
                    .frame(width: 10, height: 10)

                Text(goal.text)
                    .font(.body)
                    .fontWeight(.medium)

                Spacer()

                let subCount = goal.sub_goals?.count ?? 0
                if subCount > 0 {
                    Text("\(subCount)")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(color.opacity(0.2))
                        .foregroundStyle(color)
                        .clipShape(Capsule())
                }
            }
        }
    }
}
