import SwiftUI

struct UndoToast: View {
    let message: String
    let onUndo: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.uturn.backward.circle.fill")
                .foregroundStyle(.white)
            Text(message)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.white)
                .lineLimit(1)
            Spacer()
            Button("Undo") {
                onUndo()
            }
            .font(.subheadline)
            .fontWeight(.bold)
            .foregroundStyle(.yellow)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.black.opacity(0.85))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 16)
    }
}

@Observable
final class UndoState<Item> {
    var item: Item?
    var index: Int?
    var isVisible = false
    var message = ""
    private var dismissTask: Task<Void, Never>?

    func show(item: Item, index: Int, message: String) {
        dismissTask?.cancel()
        self.item = item
        self.index = index
        self.message = message
        self.isVisible = true

        dismissTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(10))
            guard !Task.isCancelled else { return }
            self.dismiss()
        }
    }

    func dismiss() {
        dismissTask?.cancel()
        isVisible = false
        item = nil
        index = nil
    }
}
