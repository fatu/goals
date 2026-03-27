import WidgetKit
import SwiftUI

// MARK: - Timeline

struct GoalsEntry: TimelineEntry {
    let date: Date
    let data: WidgetData

    static var placeholder: GoalsEntry {
        GoalsEntry(date: Date(), data: .placeholder)
    }
}

struct GoalsProvider: TimelineProvider {
    func placeholder(in context: Context) -> GoalsEntry {
        .placeholder
    }

    func getSnapshot(in context: Context, completion: @escaping (GoalsEntry) -> Void) {
        completion(currentEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<GoalsEntry>) -> Void) {
        let entry = currentEntry()
        let nextUpdate = Calendar.current.date(byAdding: .hour, value: 1, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func currentEntry() -> GoalsEntry {
        if let data = WidgetData.load() {
            return GoalsEntry(date: data.lastUpdated, data: data)
        }
        return .placeholder
    }
}

// MARK: - Widget Definition

struct GoalsWidget: Widget {
    let kind = "GoalsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: GoalsProvider()) { entry in
            GoalsWidgetView(entry: entry)
                .containerBackground(Color(hex: "f5f5f7"), for: .widget)
        }
        .configurationDisplayName("Goals")
        .description("Track your daily and yearly goals.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

// MARK: - Views

struct GoalsWidgetView: View {
    @Environment(\.widgetFamily) var family
    let entry: GoalsEntry

    var body: some View {
        switch family {
        case .systemSmall:
            SmallGoalsView(data: entry.data)
        case .systemMedium:
            MediumGoalsView(data: entry.data)
        case .systemLarge:
            LargeGoalsView(data: entry.data)
        default:
            MediumGoalsView(data: entry.data)
        }
    }
}

// MARK: - Small

struct SmallGoalsView: View {
    let data: WidgetData

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .stroke(Color(hex: "d0d0d5"), lineWidth: 6)
                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(progressColor, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.easeInOut, value: progress)
                VStack(spacing: 0) {
                    Text("\(data.dailyDone)")
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(Color(hex: "1a1a2e"))
                    Text("of \(data.dailyTotal)")
                        .font(.system(size: 12, weight: .medium, design: .rounded))
                        .foregroundStyle(Color(hex: "888888"))
                }
            }
            .frame(width: 80, height: 80)

            Text("Daily Goals")
                .font(.caption2.weight(.medium))
                .foregroundStyle(Color(hex: "888888"))
        }
    }

    private var progress: Double {
        data.dailyTotal > 0 ? Double(data.dailyDone) / Double(data.dailyTotal) : 0
    }

    private var progressColor: Color {
        if data.dailyTotal > 0 && data.dailyDone == data.dailyTotal {
            return .green
        }
        return Color(hex: "667eea")
    }
}

// MARK: - Medium

struct MediumGoalsView: View {
    let data: WidgetData

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("🎯 Today")
                    .font(.headline)
                    .foregroundStyle(Color(hex: "1a1a2e"))
                Spacer()
                Text("\(data.dailyDone)/\(data.dailyTotal)")
                    .font(.subheadline.bold())
                    .foregroundStyle(Color(hex: "667eea"))
            }

            ProgressBar(progress: dailyProgress)
                .frame(height: 4)

            ForEach(Array(data.dailyGoals.prefix(4).enumerated()), id: \.offset) { _, goal in
                GoalRow(goal: goal)
            }

            if data.dailyGoals.count > 4 {
                Text("+\(data.dailyGoals.count - 4) more")
                    .font(.caption2)
                    .foregroundStyle(Color(hex: "888888"))
            }
        }
    }

    private var dailyProgress: Double {
        data.dailyTotal > 0 ? Double(data.dailyDone) / Double(data.dailyTotal) : 0
    }
}

// MARK: - Large

struct LargeGoalsView: View {
    let data: WidgetData

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Daily section
            HStack {
                Text("📅 Today")
                    .font(.headline)
                    .foregroundStyle(Color(hex: "1a1a2e"))
                Spacer()
                Text("\(data.dailyDone)/\(data.dailyTotal)")
                    .font(.subheadline.bold())
                    .foregroundStyle(Color(hex: "667eea"))
            }

            ProgressBar(progress: dailyProgress)
                .frame(height: 4)

            ForEach(Array(data.dailyGoals.prefix(5).enumerated()), id: \.offset) { _, goal in
                GoalRow(goal: goal)
            }

            if data.dailyGoals.count > 5 {
                Text("+\(data.dailyGoals.count - 5) more")
                    .font(.caption2)
                    .foregroundStyle(Color(hex: "888888"))
            }

            Divider()
                .background(Color(hex: "d0d0d5"))

            // Year section
            HStack {
                Text("🏆 Year")
                    .font(.headline)
                    .foregroundStyle(Color(hex: "1a1a2e"))
                Spacer()
                Text("\(data.yearDone)/\(data.yearTotal)")
                    .font(.subheadline.bold())
                    .foregroundStyle(Color(hex: "667eea"))
            }

            ProgressBar(progress: yearProgress)
                .frame(height: 4)

            ForEach(Array(data.yearGoals.prefix(4).enumerated()), id: \.offset) { _, goal in
                GoalRow(goal: goal)
            }

            if data.yearGoals.count > 4 {
                Text("+\(data.yearGoals.count - 4) more")
                    .font(.caption2)
                    .foregroundStyle(Color(hex: "888888"))
            }
        }
    }

    private var dailyProgress: Double {
        data.dailyTotal > 0 ? Double(data.dailyDone) / Double(data.dailyTotal) : 0
    }

    private var yearProgress: Double {
        data.yearTotal > 0 ? Double(data.yearDone) / Double(data.yearTotal) : 0
    }
}

// MARK: - Shared Components

struct GoalRow: View {
    let goal: WidgetGoalItem

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: statusIcon)
                .font(.caption)
                .foregroundStyle(statusColor)
                .frame(width: 14)
            Text(goal.text)
                .font(.caption)
                .foregroundStyle(goal.status == "done" ? Color(hex: "aaaaaa") : Color(hex: "1a1a2e"))
                .strikethrough(goal.status == "done", color: .gray)
                .lineLimit(1)
        }
    }

    private var statusIcon: String {
        switch goal.status {
        case "done": return "checkmark.circle.fill"
        case "working": return "hammer.circle.fill"
        default: return "circle"
        }
    }

    private var statusColor: Color {
        switch goal.status {
        case "done": return .green
        case "working": return .orange
        default: return .gray
        }
    }
}

struct ProgressBar: View {
    let progress: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(hex: "d0d0d5"))
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(hex: "667eea"))
                    .frame(width: geo.size.width * max(0, min(1, progress)))
            }
        }
    }
}

// MARK: - Preview

#Preview(as: .systemSmall) {
    GoalsWidget()
} timeline: {
    GoalsEntry.placeholder
}

#Preview(as: .systemMedium) {
    GoalsWidget()
} timeline: {
    GoalsEntry.placeholder
}

#Preview(as: .systemLarge) {
    GoalsWidget()
} timeline: {
    GoalsEntry.placeholder
}
