import SwiftUI

enum Constants {
    static let catColors: [Color] = [
        Color(hex: "667eea"),
        Color(hex: "f39c12"),
        Color(hex: "2ecc71"),
        Color(hex: "e74c3c"),
        Color(hex: "9b59b6"),
        Color(hex: "1abc9c"),
    ]

    static let iCloudContainerID = "iCloud.com.fangbotu.goalsapp"
    static let appGroupID = "group.com.fangbotu.goalsapp"
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
