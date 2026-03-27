import SwiftUI

struct StatusBadge: View {
    let status: CheckStatus
    var onTap: () -> Void

    var body: some View {
        Button {
            let generator = UIImpactFeedbackGenerator(style: status == .working ? .medium : .light)
            generator.impactOccurred()
            withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                onTap()
            }
        } label: {
            Image(systemName: status.icon)
                .font(.title2)
                .foregroundStyle(status.iconColor)
        }
        .buttonStyle(.plain)
    }
}
