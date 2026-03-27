import Foundation
import SwiftUI

enum CheckStatus: Codable, Equatable {
    case todo
    case working
    case done

    var next: CheckStatus {
        switch self {
        case .todo: return .working
        case .working: return .done
        case .done: return .todo
        }
    }

    var icon: String {
        switch self {
        case .todo: return "circle"
        case .working: return "hammer.circle.fill"
        case .done: return "checkmark.circle.fill"
        }
    }

    var iconColor: Color {
        switch self {
        case .todo: return .gray
        case .working: return .orange
        case .done: return .green
        }
    }

    var label: String {
        switch self {
        case .todo: return "To Do"
        case .working: return "Working"
        case .done: return "Done"
        }
    }

    var emoji: String {
        switch self {
        case .todo: return "\u{2B1C}"     // ⬜
        case .working: return "\u{1F528}"  // 🔨
        case .done: return "\u{2705}"      // ✅
        }
    }

    // Handle backward compat: Bool true→done, false→todo, String "working"/"done"/"todo"
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let boolVal = try? container.decode(Bool.self) {
            self = boolVal ? .done : .todo
        } else if let strVal = try? container.decode(String.self) {
            switch strVal {
            case "done": self = .done
            case "working": self = .working
            default: self = .todo
            }
        } else {
            self = .todo
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .todo: try container.encode("todo")
        case .working: try container.encode("working")
        case .done: try container.encode("done")
        }
    }
}
