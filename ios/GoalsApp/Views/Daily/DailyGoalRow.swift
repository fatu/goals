import SwiftUI

struct DailyGoalRow: View {
    let goal: DailyGoal
    let index: Int
    @Environment(GoalsStore.self) private var store

    private var status: CheckStatus { store.dailyStatus(at: index) }

    var body: some View {
        HStack(spacing: 12) {
            StatusBadge(status: status) {
                store.toggleDailyStatus(at: index)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(goal.text)
                    .strikethrough(status == .done)
                    .foregroundStyle(status == .done ? .secondary : .primary)

                if let added = goal.added_date {
                    let days = daysSince(added)
                    Text("day \(days)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let files = goal.files, !files.isEmpty {
                Image(systemName: "paperclip")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let catId = goal.category, let info = store.categoryInfo(for: catId) {
                CategoryTag(text: info.text, colorIndex: info.color)
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }

    private func daysSince(_ dateStr: String) -> Int {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: dateStr) else { return 1 }
        return max(1, Calendar.current.dateComponents([.day], from: d, to: Date()).day! + 1)
    }
}
