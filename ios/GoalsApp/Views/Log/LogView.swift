import SwiftUI
import Charts

struct LogView: View {
    @Environment(GoalsStore.self) private var store
    @State private var selectedTab = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Picker("View", selection: $selectedTab) {
                    Text("Focus").tag(0)
                    Text("Completed").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()

                if selectedTab == 0 {
                    focusLogView
                } else {
                    completedLogView
                }
            }
            .navigationTitle("Log")
            .refreshable {
                store.load()
            }
        }
    }

    // MARK: - Focus Log

    private var totalSeconds: Int {
        store.focusLog.reduce(0) { $0 + $1.seconds }
    }

    private var dailyAvgSeconds: Int {
        store.focusLog.isEmpty ? 0 : totalSeconds / store.focusLog.count
    }

    private var weekTotals: [String: Int] {
        let cal = Calendar.current
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        var totals: [String: Int] = [:]
        for entry in store.focusLog {
            if let date = f.date(from: entry.date) {
                let year = cal.component(.yearForWeekOfYear, from: date)
                let week = cal.component(.weekOfYear, from: date)
                let key = "\(year)-W\(week)"
                totals[key, default: 0] += entry.seconds
            }
        }
        return totals
    }

    private var currentWeekKey: String {
        let cal = Calendar.current
        let now = Date()
        let year = cal.component(.yearForWeekOfYear, from: now)
        let week = cal.component(.weekOfYear, from: now)
        return "\(year)-W\(week)"
    }

    private var currentWeekSeconds: Int {
        weekTotals[currentWeekKey] ?? 0
    }

    private var weeklyAvgSeconds: Int {
        let past = weekTotals.filter { $0.key != currentWeekKey }
        guard !past.isEmpty else { return 0 }
        return past.values.reduce(0, +) / past.count
    }

    private func formatDuration(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        if h > 0 {
            return String(format: "%dh %02dm", h, m)
        }
        return "\(m)m"
    }

    private var focusLogView: some View {
        let entries = store.focusLog.suffix(14).reversed()
        return List {
            if store.focusLog.isEmpty {
                EmptyStateView(
                    icon: "timer",
                    title: "No focus sessions",
                    subtitle: "Focus time is tracked from the macOS app and will appear here"
                )
            } else {
                // Summary stats
                Section {
                    VStack(spacing: 8) {
                        HStack(spacing: 12) {
                            statCard(title: "Total", value: formatDuration(totalSeconds), color: .blue)
                            statCard(title: "Daily Avg", value: formatDuration(dailyAvgSeconds), color: .green)
                        }
                        HStack(spacing: 12) {
                            statCard(title: "Weekly Avg", value: formatDuration(weeklyAvgSeconds), color: .purple)
                            thisWeekCard
                        }
                    }
                    .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 8, trailing: 0))
                    .listRowBackground(Color.clear)
                }

                Section {
                    Chart(Array(store.focusLog.suffix(14)), id: \.date) { entry in
                        BarMark(
                            x: .value("Date", shortDate(entry.date)),
                            y: .value("Hours", Double(entry.seconds) / 3600.0)
                        )
                        .foregroundStyle(.blue.gradient)
                    }
                    .frame(height: 200)
                    .padding(.vertical, 8)
                } header: {
                    Text("Focus Time (hours)")
                }

                Section {
                    ForEach(Array(entries), id: \.date) { entry in
                        HStack {
                            Text(entry.date)
                                .font(.subheadline)
                            Spacer()
                            Text(entry.formattedDuration)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundStyle(.blue)
                        }
                    }
                } header: {
                    Text("Recent Sessions")
                }
            }
        }
    }

    private var thisWeekCard: some View {
        let diff = currentWeekSeconds - weeklyAvgSeconds
        let hasComparison = weeklyAvgSeconds > 0 && currentWeekSeconds > 0
        return VStack(spacing: 4) {
            Text(formatDuration(currentWeekSeconds))
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.orange)
            if hasComparison {
                HStack(spacing: 2) {
                    Image(systemName: diff >= 0 ? "arrow.up.right" : "arrow.down.right")
                        .font(.system(size: 9))
                    Text(formatDuration(abs(diff)))
                        .font(.system(size: 10))
                }
                .foregroundStyle(diff >= 0 ? .green : .red)
            } else {
                Text("This Week")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Color.orange.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func statCard(title: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(color)
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - Completed Log

    private var completedLogView: some View {
        List {
            if store.completedLog.isEmpty {
                EmptyStateView(
                    icon: "party.popper",
                    title: "No completed goals",
                    subtitle: "Goals you finish will be archived here with their completion date"
                )
            } else {
                Section {
                    ForEach(store.completedLog.reversed()) { entry in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.text)
                                    .font(.subheadline)
                                if let completed = entry.completed_date {
                                    Text(completed)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            if let days = entry.days {
                                Text("\(days)d")
                                    .font(.caption)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 2)
                                    .background(.green.opacity(0.15))
                                    .foregroundStyle(.green)
                                    .clipShape(Capsule())
                            }
                        }
                    }
                } header: {
                    Text("\(store.completedLog.count) completed")
                }
            }
        }
    }

    private func shortDate(_ dateStr: String) -> String {
        // "2026-03-10" -> "3/10"
        let parts = dateStr.split(separator: "-")
        guard parts.count == 3,
              let m = Int(parts[1]),
              let d = Int(parts[2]) else { return dateStr }
        return "\(m)/\(d)"
    }
}
