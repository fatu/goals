import Foundation
import os

private let logger = Logger(subsystem: "com.fangbotu.goalsapp", category: "iCloudFileManager")

actor iCloudFileManager {
    static let shared = iCloudFileManager()

    private var containerURL: URL?

    func initialize() {
        if let url = FileManager.default.url(forUbiquityContainerIdentifier: Constants.iCloudContainerID) {
            let docsURL = url.appendingPathComponent("Documents")
            if !FileManager.default.fileExists(atPath: docsURL.path) {
                try? FileManager.default.createDirectory(at: docsURL, withIntermediateDirectories: true)
            }
            containerURL = docsURL
            logger.info("Using iCloud at \(docsURL.path)")

            // Trigger download for all JSON files
            for name in ["goals.json", ".daily_state.json", ".year_state.json", "completed_log.json", "focus_log.json"] {
                try? FileManager.default.startDownloadingUbiquitousItem(at: docsURL.appendingPathComponent(name))
            }
        } else {
            #if targetEnvironment(simulator)
            // Simulator can't access ~/Library/Mobile Documents due to sandbox.
            // Use the app's own Documents directory. A build phase script copies
            // the real iCloud data files here for simulator builds.
            let docsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
            containerURL = docsURL
            logger.info("Simulator fallback: using app Documents at \(docsURL.path)")
            #else
            logger.error("iCloud container unavailable — check signing, iCloud entitlement, and iCloud sign-in")
            #endif
        }
    }

    var documentsURL: URL? {
        containerURL
    }

    var isAvailable: Bool {
        containerURL != nil
    }

    func fileURL(for filename: String) -> URL? {
        containerURL?.appendingPathComponent(filename)
    }

    func read<T: Decodable>(_ type: T.Type, from filename: String) -> T? {
        guard let url = fileURL(for: filename) else {
            logger.error("No container URL for \(filename)")
            return nil
        }

        try? FileManager.default.startDownloadingUbiquitousItem(at: url)

        guard FileManager.default.fileExists(atPath: url.path) else {
            logger.warning("File not found: \(filename)")
            return nil
        }

        var result: T?
        var readError: NSError?
        let coordinator = NSFileCoordinator()
        coordinator.coordinate(readingItemAt: url, options: [], error: &readError) { readURL in
            do {
                let data = try Data(contentsOf: readURL)
                result = try JSONDecoder().decode(T.self, from: data)
            } catch {
                logger.error("Read decode error \(filename): \(error)")
            }
        }
        if let error = readError {
            logger.error("Coordinator read error \(filename): \(error)")
        }
        return result
    }

    func write<T: Encodable>(_ value: T, to filename: String) {
        guard let url = fileURL(for: filename) else { return }

        var writeError: NSError?
        let coordinator = NSFileCoordinator()
        coordinator.coordinate(writingItemAt: url, options: .forReplacing, error: &writeError) { writeURL in
            do {
                let encoder = JSONEncoder()
                encoder.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes]
                let data = try encoder.encode(value)
                try data.write(to: writeURL, options: .atomic)
            } catch {
                logger.error("Write error \(filename): \(error)")
            }
        }
        if let error = writeError {
            logger.error("Coordinator write error \(filename): \(error)")
        }
    }

    func attachmentsURL() -> URL? {
        guard let docs = containerURL else { return nil }
        let url = docs.appendingPathComponent("attachments")
        if !FileManager.default.fileExists(atPath: url.path) {
            try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        }
        return url
    }

    func startDownloading(filename: String) {
        guard let url = fileURL(for: filename) else { return }
        try? FileManager.default.startDownloadingUbiquitousItem(at: url)
    }
}
