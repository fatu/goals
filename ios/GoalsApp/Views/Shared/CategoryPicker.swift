import SwiftUI

struct CategoryPicker: View {
    @Binding var selection: String?
    @Environment(GoalsStore.self) private var store

    var body: some View {
        Picker("Category", selection: $selection) {
            Text("None").tag(String?.none)
            ForEach(store.categoryGroups, id: \.yearGoal) { group in
                Section(group.yearGoal) {
                    ForEach(group.subGoals) { sub in
                        Text(sub.text).tag(Optional(sub.id))
                    }
                }
            }
        }
    }
}
