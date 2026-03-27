import SwiftUI

struct CategoryTag: View {
    let text: String
    let colorIndex: Int

    var body: some View {
        Text(text)
            .font(.caption2)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(Constants.catColors[colorIndex % Constants.catColors.count].opacity(0.8))
            .foregroundStyle(.white)
            .clipShape(Capsule())
    }
}
