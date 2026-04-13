import SwiftUI
import QuickLook

struct GoalDetailSheet: View {
    @Binding var title: String
    @Binding var notes: String?
    @Binding var category: String?
    @Binding var scheduledDate: String?
    let showDatePicker: Bool
    let showCategoryPicker: Bool
    var files: [AttachedFile] = []
    var onSave: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var showPreview = false
    @State private var dateValue = Date()
    @State private var previewURL: URL?
    @State private var isDownloading = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Title") {
                    TextField("Goal title", text: $title)
                }

                if showCategoryPicker {
                    Section("Category") {
                        CategoryPicker(selection: $category)
                    }
                }

                if showDatePicker {
                    Section("Scheduled Date") {
                        Toggle("Set date", isOn: Binding(
                            get: { scheduledDate != nil },
                            set: { newVal in
                                if newVal {
                                    scheduledDate = formatDate(dateValue)
                                } else {
                                    scheduledDate = nil
                                }
                            }
                        ))
                        if scheduledDate != nil {
                            DatePicker("Date", selection: $dateValue, displayedComponents: .date)
                                .onChange(of: dateValue) { _, newVal in
                                    scheduledDate = formatDate(newVal)
                                }
                        }
                    }
                }

                if !files.isEmpty {
                    Section("Attachments") {
                        ForEach(files, id: \.path) { file in
                            Button {
                                openFile(file)
                            } label: {
                                HStack {
                                    Image(systemName: fileIcon(for: file.name))
                                        .foregroundStyle(.blue)
                                    Text(file.name)
                                        .foregroundStyle(.primary)
                                    Spacer()
                                    if isDownloading {
                                        ProgressView()
                                            .controlSize(.small)
                                    } else {
                                        Image(systemName: "eye")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }
                }

                Section {
                    if showPreview {
                        ScrollView {
                            Text(markdownFromNotes)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.vertical, 4)
                        }
                        .frame(minHeight: 200)
                    } else {
                        TextEditor(text: Binding(
                            get: { notes ?? "" },
                            set: { notes = $0.isEmpty ? nil : $0 }
                        ))
                        .frame(minHeight: 200)
                        .font(.system(.body, design: .monospaced))
                    }
                } header: {
                    HStack {
                        Text("Notes")
                        Spacer()
                        Button(showPreview ? "Edit" : "Preview") {
                            showPreview.toggle()
                        }
                        .font(.caption)
                    }
                }
            }
            .navigationTitle("Edit Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave()
                        dismiss()
                    }
                    .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
            .quickLookPreview($previewURL)
            .onAppear {
                if let sd = scheduledDate, let d = parseDate(sd) {
                    dateValue = d
                }
            }
        }
    }

    private func openFile(_ file: AttachedFile) {
        guard let containerURL = FileManager.default.url(forUbiquityContainerIdentifier: Constants.iCloudContainerID) else { return }
        let fileURL = containerURL.appendingPathComponent("Documents/attachments/\(file.path)")

        try? FileManager.default.startDownloadingUbiquitousItem(at: fileURL)

        if FileManager.default.fileExists(atPath: fileURL.path) {
            previewURL = fileURL
        } else {
            isDownloading = true
            Task {
                // Wait for iCloud download
                for _ in 0..<10 {
                    try? await Task.sleep(for: .seconds(1))
                    if FileManager.default.fileExists(atPath: fileURL.path) {
                        await MainActor.run {
                            isDownloading = false
                            previewURL = fileURL
                        }
                        return
                    }
                }
                await MainActor.run { isDownloading = false }
            }
        }
    }

    private func fileIcon(for name: String) -> String {
        let ext = (name as NSString).pathExtension.lowercased()
        switch ext {
        case "pdf": return "doc.richtext"
        case "png", "jpg", "jpeg", "heic": return "photo"
        default: return "doc.fill"
        }
    }

    private var markdownFromNotes: AttributedString {
        guard let notes, !notes.isEmpty else {
            return AttributedString("No notes")
        }
        return (try? AttributedString(markdown: notes)) ?? AttributedString(notes)
    }

    private func formatDate(_ d: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: d)
    }

    private func parseDate(_ s: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: s)
    }
}
